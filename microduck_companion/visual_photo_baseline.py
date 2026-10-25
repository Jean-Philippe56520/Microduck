"""F3-B: tiny RGB-feature kNN baseline on REAL, externally hosted CC0 photos.

Standalone PC/CI experiment, NOT a Microduck vision detector. No pretrained
weights, ONNX, NPU, mediad, person recognition or motor output. Inputs are
32? -> actually resized 16x16 RGB thumbnails; the original JPEG bytes never
enter SQLite or GitHub. Thresholds are selected on validation ONLY.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
from io import BytesIO
import math
import time
from typing import Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from .visual_photo_catalog import PHOTO_CATALOG, PublicPhoto, CC0_LICENSE

SIDE = 16
MAX_JPEG_BYTES = 1_200_000
_MAX_WAIT_S = 10
_CLASSES = ("cat", "dog")
_SPLITS = ("train", "validation", "test")
_VOTE_THRESHOLDS = (.50, .60, .70, .80, .90, 1.)
_DISTANCE_THRESHOLDS = (.09, .13, .18, .23, .28, .36, .48, 1.)
MAX_NETWORK_RETRIES = 3


class PhotoBaselineError(ValueError):
    """Unverifiable input or failed external fetch: never guess measurements."""


@dataclass(frozen=True)
class ImageFeature:
    category: str
    split: str
    group: str
    content_sha256: str
    values: tuple[float, ...]


@dataclass(frozen=True)
class Prediction:
    category: str
    confidence: float  # kNN vote ratio: NOT a calibrated probability
    distance: float


@dataclass(frozen=True)
class DecisionThreshold:
    vote_fraction: float
    maximum_distance: float


@dataclass(frozen=True)
class PhotoBaselineMetrics:
    """Scores from original, CC0 Flickr-like photos on Linux PC/CI only."""

    samples: int
    correct: int
    accuracy: float
    known_support: int
    unknown_support: int
    known_recall: float
    unknown_recall: float
    coverage: float
    false_known_on_unknown: int
    confusion: tuple[tuple[str, str, int], ...]
    per_class: tuple[tuple[str, int, int, float, float, float], ...]


def validate_catalog(photos: tuple[PublicPhoto, ...] = PHOTO_CATALOG) -> None:
    if type(photos) is not tuple or not photos:
        raise PhotoBaselineError("empty/invalid public catalog")
    names: set[str] = set()
    group_splits: dict[str, str] = {}
    counts = Counter()
    for photo in photos:
        if not isinstance(photo, PublicPhoto):
            raise PhotoBaselineError("malformed catalog entry")
        if (photo.category not in (*_CLASSES, "unknown")
                or photo.split not in _SPLITS
                or photo.license != CC0_LICENSE
                or not photo.filename.endswith(".jpg")
                or "/" in photo.filename or "\\" in photo.filename
                or not photo.author.strip()):
            raise PhotoBaselineError("invalid catalog: label/licence/origin")
        if photo.filename in names:
            raise PhotoBaselineError("duplicate external photo")
        names.add(photo.filename)
        if (photo.author in group_splits
                and group_splits[photo.author] != photo.split):
            raise PhotoBaselineError("same credited author leaks between splits")
        group_splits[photo.author] = photo.split
        if photo.category == "unknown" and photo.split == "train":
            raise PhotoBaselineError("unknown must not be trained as cat/dog")
        counts[(photo.split, photo.category)] += 1
    for split in _SPLITS:
        if any(counts[(split, category)] == 0 for category in _CLASSES):
            raise PhotoBaselineError("both cat and dog required in every split")
    for split in ("validation", "test"):
        if counts[(split, "unknown")] == 0:
            raise PhotoBaselineError("unknown holdouts required")


def _check_jpeg_bytes(response: object) -> bytes:
    """Validate redirect, content type and byte budget; refuse HTML/errors."""
    url = response.geturl()
    parsed = urlparse(url)
    if (parsed.scheme != "https"
            or parsed.hostname not in ("upload.wikimedia.org",
                                       "commons.wikimedia.org")):
        raise PhotoBaselineError(f"unexpected image redirect host: {parsed.scheme}://{parsed.hostname}")
    ctype = response.headers.get("Content-Type", "").split(";")[0].strip()
    if ctype not in ("image/jpeg", "image/jpg"):
        raise PhotoBaselineError("download not a JPEG image")
    data = response.read(MAX_JPEG_BYTES + 1)
    if (len(data) > MAX_JPEG_BYTES or len(data) < 100
            or not data.startswith(b"\xff\xd8")
            or not data.endswith(b"\xff\xd9")):
        raise PhotoBaselineError("invalid/oversized JPEG payload")
    return data


def fetch_thumbnail(
    photo: PublicPhoto, *, opener: Callable = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
) -> bytes:
    if photo not in PHOTO_CATALOG:
        raise PhotoBaselineError("external source must be curated in code")
    req = Request(
        photo.thumbnail_url, headers={
            "User-Agent": "MicroduckCompanionF3B/0.1 (research; public CC0 catalog)",
            "Accept": "image/jpeg",
        })
    last = None
    for attempt in range(MAX_NETWORK_RETRIES):
        try:
            with opener(req, timeout=_MAX_WAIT_S) as response:
                return _check_jpeg_bytes(response)
        except PhotoBaselineError:
            raise  # Never retry on a forged host or malformed response.
        except (URLError, HTTPError, TimeoutError, OSError) as exc:
            last = exc
            if attempt + 1 < MAX_NETWORK_RETRIES:
                sleeper(float(attempt + 1))
    raise PhotoBaselineError("public thumbnail unavailable; no score") from last


def rgb_features(rgb: bytes) -> tuple[float, ...]:
    """Deterministic tiny feature representation from a 16x16 RGB tensor.

    This is a handcrafted weak baseline; it may classify backgrounds instead
    of animals. It is not a detector, semantic model or calibrated inference.
    """
    if type(rgb) is not bytes or len(rgb) != SIDE * SIDE * 3:
        raise PhotoBaselineError("must supply exactly 16x16 RGB bytes")
    hist = [[0] * 4 for _ in range(3)]
    luma = [0.] * (SIDE * SIDE)
    grid = [0.] * 16
    rsum = gsum = bsum = sat = 0.
    for n in range(SIDE * SIDE):
        r, g, b = rgb[3*n:3*n+3]
        vals = r, g, b
        for channel, value in enumerate(vals):
            hist[channel][value // 64] += 1
        rsum += r
        gsum += g
        bsum += b
        sat += (max(vals) - min(vals)) / 255.
        brightness = (77*r + 150*g + 29*b)/(256.*255.)
        luma[n] = brightness
        x, y = n % SIDE, n // SIDE
        grid[(y // 4)*4+(x // 4)] += brightness / 16.
    horizontal = sum(
        abs(luma[y*SIDE+x] - luma[y*SIDE+x+1])
        for y in range(SIDE) for x in range(SIDE-1)
    ) / (SIDE*(SIDE-1))
    vertical = sum(
        abs(luma[y*SIDE+x] - luma[(y+1)*SIDE+x])
        for y in range(SIDE-1) for x in range(SIDE)
    ) / (SIDE*(SIDE-1))
    features = (
        [v/256. for channel in hist for v in channel]
        + grid
        + [rsum/(256.*255.),gsum/(256.*255.),bsum/(256.*255.),
           sat/256., horizontal, vertical]
    )
    return tuple(features)


def features_from_jpeg(data: bytes) -> tuple[float, ...]:
    """Pillow is needed ONLY for this real-photo benchmark, never F1/F2."""
    try:
        from PIL import Image, ImageOps
        with Image.open(BytesIO(data)) as image:
            if image.format != "JPEG" or image.width < 32 or image.height < 32:
                raise PhotoBaselineError("invalid image format or dimensions")
            oriented = ImageOps.exif_transpose(image)
            resized = ImageOps.fit(oriented.convert("RGB"), (SIDE, SIDE),
                                   method=Image.Resampling.LANCZOS)
            return rgb_features(resized.tobytes())
    except (ImportError, OSError, ValueError) as exc:
        raise PhotoBaselineError("Pillow/JPEG decoding failed") from exc


def sample_features(
    photo: PublicPhoto, data: bytes,
    *, extractor: Callable[[bytes], tuple[float, ...]] = features_from_jpeg,
) -> ImageFeature:
    if photo not in PHOTO_CATALOG:
        raise PhotoBaselineError("unreviewed source")
    digest = hashlib.sha256(data).hexdigest()
    values = extractor(data)
    if (type(values) is not tuple or not values
            or any(type(v) is not float or not math.isfinite(v) for v in values)):
        raise PhotoBaselineError("feature extraction failed")
    return ImageFeature(photo.category, photo.split, photo.author, digest, values)


def validate_samples(samples: tuple[ImageFeature, ...]) -> None:
    if type(samples) is not tuple or not samples:
        raise PhotoBaselineError("no photo features")
    if len(samples) != len(PHOTO_CATALOG):
        raise PhotoBaselineError("incomplete dataset: no partial benchmark")
    expected = Counter((p.category,p.split,p.author) for p in PHOTO_CATALOG)
    actual = Counter((x.category,x.split,x.group) for x in samples)
    if actual != expected:
        raise PhotoBaselineError("curated source/label/split mismatch")
    dim = len(samples[0].values)
    if dim != 34 or any(len(x.values) != dim for x in samples):
        raise PhotoBaselineError("incompatible features")
    if (len({x.content_sha256 for x in samples}) != len(samples)
            or any(len(x.content_sha256) != 64 for x in samples)):
        raise PhotoBaselineError("duplicate/corrupt content fingerprint")


def _distance(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return math.sqrt(sum((x-y)**2 for x,y in zip(a,b)) / len(a))


class TinyRGBKNN:
    """8 public photo prototypes, no weights, no motor authority."""

    def __init__(self, train: tuple[ImageFeature, ...]) -> None:
        if not train or any(
            s.split != "train" or s.category not in _CLASSES for s in train
        ):
            raise PhotoBaselineError("train must have known categories only")
        self._train = train
        if len({len(s.values) for s in train}) != 1:
            raise PhotoBaselineError("mismatched training feature shapes")

    def predict(self, values: tuple[float, ...]) -> Prediction:
        if (len(values) != len(self._train[0].values)
                or any(not math.isfinite(v) for v in values)):
            raise PhotoBaselineError("invalid RGB features")
        near = sorted(
            ((_distance(values, record.values), record.category)
             for record in self._train),
            key=lambda x: (x[0], x[1]),
        )[:3]
        weights = Counter()
        for distance, label in near:
            weights[label] += 1. / (0.02 + distance)**2
        label = max(_CLASSES, key=lambda key: (weights[key], key))
        return Prediction(
            label, weights[label]/sum(weights.values()),
            min(d for d, cat in near if cat == label),
        )


def classify(prediction: Prediction, limits: DecisionThreshold) -> str:
    if prediction.confidence < limits.vote_fraction:
        return "unknown"
    if prediction.distance > limits.maximum_distance:
        return "unknown"
    return prediction.category


def choose_threshold(
    model: TinyRGBKNN, validation: tuple[ImageFeature, ...]
) -> DecisionThreshold:
    """Freeze a conservative rejection threshold before touching TEST data."""
    if not validation or any(s.split != "validation" for s in validation):
        raise PhotoBaselineError("threshold requires held-out validation")
    if not any(s.category == "unknown" for s in validation):
        raise PhotoBaselineError("validation must contain out-of-domain unknown")
    precomputed = tuple((s.category, model.predict(s.values)) for s in validation)
    best_score = None
    best = None
    for vote in _VOTE_THRESHOLDS:
        for dist in _DISTANCE_THRESHOLDS:
            t = DecisionThreshold(vote, dist)
            pairs = [(truth, classify(pred, t)) for truth,pred in precomputed]
            known = [(truth,pred) for truth,pred in pairs if truth in _CLASSES]
            unknown = [(truth,pred) for truth,pred in pairs if truth == "unknown"]
            kr = sum(a==b for a,b in known)/len(known)
            ur = sum(b=="unknown" for _,b in unknown)/len(unknown)
            # Primary objective: balanced recall of known and unknown.
            # Ties prefer safety (unknown recall) then known correctness.
            score = (kr+ur, ur, kr, -vote, -dist)
            if best_score is None or score > best_score:
                best_score, best = score, t
    assert best is not None
    return best


def evaluate_holdout(
    model: TinyRGBKNN, test: tuple[ImageFeature, ...],
    limits: DecisionThreshold,
) -> PhotoBaselineMetrics:
    if not test or any(s.split != "test" for s in test):
        raise PhotoBaselineError("metrics only on TEST split")
    predictions = [(s.category, classify(model.predict(s.values),limits))
                   for s in test]
    confusion = Counter(predictions)
    n = len(test)
    correct = sum(a==b for a,b in predictions)
    known = [(a,b) for a,b in predictions if a in _CLASSES]
    unknown = [(a,b) for a,b in predictions if a == "unknown"]
    scores=[]
    for label in _CLASSES:
        support=sum(a==label for a,_ in predictions)
        announced=sum(b==label for _,b in predictions)
        tp=confusion[(label,label)]
        precision=tp/announced if announced else 0.
        recall=tp/support if support else 0.
        f1=2*precision*recall/(precision+recall) if precision+recall else 0.
        scores.append((label,support,announced,precision,recall,f1))
    return PhotoBaselineMetrics(
        n,correct,correct/n,len(known),len(unknown),
        sum(a==b for a,b in known)/len(known) if known else 0.,
        sum(b=="unknown" for _,b in unknown)/len(unknown) if unknown else 0.,
        sum(b!="unknown" for _,b in predictions)/n,
        sum(b!="unknown" for _,b in unknown),
        tuple(sorted((a,b,v) for (a,b),v in confusion.items())),
        tuple(scores),
    )
