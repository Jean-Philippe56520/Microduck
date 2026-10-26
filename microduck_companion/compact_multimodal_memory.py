"""M1-A: compact VISUAL / AUDIO feature fingerprints on synthetic data ONLY.

No camera, microphone, OEM socket, PC request or actuator is accessed.
Pixel and PCM payloads are discarded after pure stdlib feature extraction.
This is NOT an object/voice classifier, biometric identifier, or robust
instance-recognition model. All category names are UNVERIFIED FIXTURE claims.

Store rows in the EXISTING ExperienceMemory SQLite connection, never a
second database, image/audio file, transcription or persistent media buffer.
A strict row count and expiration bound metadata; SQLite's allocated file
may remain larger than its live rows. Real persistent storage still requires
independent F6-A/F6-D mount and resource validation on the physical robot.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct
from typing import Literal

from .episodic_memory import ExperienceMemory

Modality = Literal["image", "audio"]
IMAGE_SIDE = 32
IMAGE_FEATURES = 64
AUDIO_RATE_HZ = 8000
AUDIO_BLOCK_SAMPLES = 128
AUDIO_FEATURES = 16
MAX_AUDIO_SAMPLES = 4096
MIN_AUDIO_SAMPLES = 512
MAX_PATTERNS = 256
RETENTION_S = 180 * 24 * 3600
MIN_IMAGE_CONTRAST = 16.
MIN_AUDIO_RMS = 160.
MATCH_IMAGE = .94
MATCH_AUDIO = .93
AMBIGUITY_GAP = .025
PC_INTEREST_THRESHOLD = .7
MAX_WALL_EPOCH_S = 1e11
OBJECT_CATEGORIES = frozenset({"unknown", "object", "cat", "dog", "person"})
SOUND_CATEGORIES = frozenset({
    "unknown", "ambient", "knock", "bark", "meow", "speech",
})
_FFT_BANDS = 12
_HANN = tuple(
    .5 - .5 * math.cos(2 * math.pi * n / (AUDIO_BLOCK_SAMPLES - 1))
    for n in range(AUDIO_BLOCK_SAMPLES)
)
_GOERTZEL_COEFFS = tuple(
    2 * math.cos(2 * math.pi * k / AUDIO_BLOCK_SAMPLES)
    for k in range(2, 49)
)


def _bounded_real(value: object, *, upper: float, name: str) -> float:
    if type(value) not in (int, float):
        raise ValueError(name + " must be a finite bounded number")
    try:
        if not math.isfinite(value) or not 0 <= value <= upper:
            raise ValueError(name + " out of range")
        return float(value)
    except OverflowError as exc:
        # An attacker-controlled Python integer may have thousands of bits.
        # Reject rather than crash the passive cognition loop.
        raise ValueError(name + " is unrepresentable") from exc


def _time(value: object) -> float:
    return _bounded_real(value, upper=MAX_WALL_EPOCH_S,
                         name="fixture wall clock")


def _interest(value: object) -> float:
    return _bounded_real(value, upper=1., name="fixture interest")


def image_fingerprint(gray8: bytes) -> bytes:
    """64-byte normalized coarse *appearance* of one synthetic 32x32 image.

    Pixel normalization removes a simple global brightness offset. It does
    NOT provide invariance to scale, camera movement, pose or occlusion.
    A stored feature is still potentially sensitive, unlike raw pixels.
    """
    if type(gray8) is not bytes or len(gray8) != IMAGE_SIDE ** 2:
        raise ValueError("fixture image must be exactly 32x32 grayscale bytes")
    tiles: list[float] = []
    for row in range(8):
        for col in range(8):
            total = 0
            for dy in range(4):
                start = (row * 4 + dy) * IMAGE_SIDE + col * 4
                total += sum(gray8[start:start + 4])
            tiles.append(total / 16.)
    low, high = min(tiles), max(tiles)
    if high - low < MIN_IMAGE_CONTRAST:
        raise ValueError("low-contrast image is not a useful instance sample")
    return bytes(round((x - low) * 255 / (high - low)) for x in tiles)


def _goertzel_power(samples: tuple[float, ...], coefficient: float) -> float:
    a = b = 0.
    for sample in samples:
        a, b = sample + coefficient * a - b, a
    return max(0., a * a + b * b - coefficient * a * b)


def audio_fingerprint(pcm16le: bytes, *, sample_rate_hz: int = AUDIO_RATE_HZ) -> bytes:
    """16-byte energy histogram of short, synthetic mono 8kHz PCM16-LE.

    Twelve coarse frequency bands and four normalized temporal envelopes.
    This is simple signal processing, NOT a speech, bark or meow detector.
    No waveform or voice identity is retained. Changing room acoustics,
    noise, distance or pitch may invalidate a match.
    """
    if type(sample_rate_hz) is not int or sample_rate_hz != AUDIO_RATE_HZ:
        raise ValueError("only synthetic 8kHz mono PCM is supported")
    if (type(pcm16le) is not bytes or len(pcm16le) % 2
            or not 2 * MIN_AUDIO_SAMPLES <= len(pcm16le)
            <= 2 * MAX_AUDIO_SAMPLES):
        raise ValueError("bounded PCM16-LE input required")
    count = len(pcm16le) // 2
    if count % AUDIO_BLOCK_SAMPLES:
        raise ValueError("sample count must be a multiple of 128")
    samples = struct.unpack("<" + str(count) + "h", pcm16le)
    dc = sum(samples) / count
    centered = tuple(v - dc for v in samples)
    rms = math.sqrt(sum(v * v for v in centered) / count)
    if rms < MIN_AUDIO_RMS:
        raise ValueError("silent or uninformative audio fixture")

    band_power = [0.] * _FFT_BANDS
    envelopes = [0.] * 4
    chunks = count // AUDIO_BLOCK_SAMPLES
    for block_no in range(chunks):
        block = centered[
            block_no * AUDIO_BLOCK_SAMPLES:(block_no + 1) * AUDIO_BLOCK_SAMPLES
        ]
        frame = tuple(block[i] * _HANN[i] for i in range(AUDIO_BLOCK_SAMPLES))
        envelopes[min(3, (4 * block_no) // chunks)] += sum(v * v for v in block)
        for index, coeff in enumerate(_GOERTZEL_COEFFS):
            band = min(_FFT_BANDS - 1,
                       (index * _FFT_BANDS) // len(_GOERTZEL_COEFFS))
            band_power[band] += _goertzel_power(frame, coeff)
    power_total = sum(band_power)
    if not math.isfinite(power_total) or power_total <= 1.:
        raise ValueError("no useful frequency energy")
    peak = max(envelopes)
    if peak <= 0:
        raise ValueError("no temporal activity")
    spectrum = [round(255 * math.sqrt(x / power_total)) for x in band_power]
    dynamics = [round(255 * math.sqrt(x / peak)) for x in envelopes]
    return bytes(spectrum + dynamics)


@dataclass(frozen=True)
class CompactEncounter:
    """A pattern match is ONLY a similarity hint, not proven identity."""

    modality: str
    status: str
    category: str
    pattern_id: int | None
    sightings: int
    similarity: float | None
    fingerprint_bytes: int
    pc_review_suggested: bool
    category_verified: bool = False
    same_individual_verified: bool = False
    physical_robot_validated: bool = False
    raw_media_stored_bytes: int = 0
    network_requests: int = 0
    motor_commands_issued: int = 0

    def __post_init__(self) -> None:
        if (self.category_verified or self.same_individual_verified
                or self.physical_robot_validated or self.raw_media_stored_bytes
                or self.network_requests or self.motor_commands_issued):
            raise ValueError("M1-A cannot certify provenance or perform I/O")


class CompactPatternMemory:
    """Single-process fixture memory; shares the existing SQLite connection.

    Do not use it as proof of real-world recognition or cross-process lock
    safety. Callers must independently approve all real media processing.
    """

    def __init__(self, memory: ExperienceMemory) -> None:
        if not isinstance(memory, ExperienceMemory):
            raise TypeError("existing ExperienceMemory required")
        self.memory = memory
        with memory.conn:
            memory.conn.execute("""
                CREATE TABLE IF NOT EXISTS m1a_compact_patterns(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    modality TEXT NOT NULL CHECK(modality IN ('image','audio')),
                    category TEXT NOT NULL,
                    source TEXT NOT NULL CHECK(source='synthetic_fixture_claim'),
                    feature_version INTEGER NOT NULL CHECK(feature_version=1),
                    fingerprint BLOB NOT NULL CHECK(length(fingerprint) IN (16,64)),
                    sightings INTEGER NOT NULL CHECK(sightings BETWEEN 1 AND 2147483647),
                    first_seen_epoch_s REAL NOT NULL,
                    last_seen_epoch_s REAL NOT NULL,
                    UNIQUE(modality, feature_version, fingerprint)
                )
            """)
            memory.conn.execute("""
                CREATE INDEX IF NOT EXISTS m1a_patterns_recent
                ON m1a_compact_patterns(last_seen_epoch_s DESC,id DESC)
            """)

    def _prune(self, now: float) -> None:
        con = self.memory.conn
        con.execute(
            "DELETE FROM m1a_compact_patterns WHERE last_seen_epoch_s < ?",
            (now - RETENTION_S,),
        )
        con.execute("""
            DELETE FROM m1a_compact_patterns WHERE id NOT IN (
                SELECT id FROM m1a_compact_patterns
                ORDER BY last_seen_epoch_s DESC,id DESC LIMIT ?
            )
        """, (MAX_PATTERNS,))

    def prune(self, *, now_wall_epoch_s: float) -> None:
        now = _time(now_wall_epoch_s)
        with self.memory.conn:
            self._prune(now)

    def count(self) -> int:
        return self.memory.conn.execute(
            "SELECT COUNT(*) FROM m1a_compact_patterns"
        ).fetchone()[0]

    def signature_storage_bytes(self) -> int:
        return int(self.memory.conn.execute(
            "SELECT COALESCE(SUM(length(fingerprint)), 0) "
            "FROM m1a_compact_patterns"
        ).fetchone()[0])

    def observe_image(
        self, gray8: bytes, *, now_wall_epoch_s: float,
        category: str = "unknown", pc_opt_in: bool = False, interest: float = 0.,
    ) -> CompactEncounter:
        if type(category) is not str or category not in OBJECT_CATEGORIES:
            raise ValueError("unsupported generic visual fixture category")
        if category == "person":
            raise ValueError("no person appearance fingerprints in M1-A")
        return self._observe(
            "image", image_fingerprint(gray8), now_wall_epoch_s=now_wall_epoch_s,
            category=category, pc_opt_in=pc_opt_in, interest=interest,
        )

    def observe_audio(
        self, pcm16le: bytes, *, now_wall_epoch_s: float,
        category: str = "unknown", pc_opt_in: bool = False, interest: float = 0.,
    ) -> CompactEncounter:
        if type(category) is not str or category not in SOUND_CATEGORIES:
            raise ValueError("unsupported generic audio fixture category")
        if category == "speech":
            raise ValueError("no voice or speech fingerprints in M1-A")
        return self._observe(
            "audio", audio_fingerprint(pcm16le),
            now_wall_epoch_s=now_wall_epoch_s,
            category=category, pc_opt_in=pc_opt_in, interest=interest,
        )

    def _observe(self, modality: Modality, feature: bytes, *,
                 now_wall_epoch_s: float, category: str,
                 pc_opt_in: bool, interest: float) -> CompactEncounter:
        now, interest = _time(now_wall_epoch_s), _interest(interest)
        if type(pc_opt_in) is not bool:
            raise ValueError("fixture PC opt-in must be boolean")
        threshold = MATCH_IMAGE if modality == "image" else MATCH_AUDIO
        conn = self.memory.conn
        with conn:
            # Protect against an accidental clock rollback after reboot.
            newest = conn.execute(
                "SELECT MAX(last_seen_epoch_s) FROM m1a_compact_patterns"
            ).fetchone()[0]
            if newest is not None and now + 60 < float(newest):
                raise ValueError("fixture wall clock regressed")
            self._prune(now)
            rows = conn.execute("""
                SELECT id,category,fingerprint,sightings
                FROM m1a_compact_patterns
                WHERE modality=? AND feature_version=1
            """, (modality,)).fetchall()
            ranked = sorted(
                (
                    (1. - sum(abs(a - b) for a, b in zip(feature, row["fingerprint"]))
                     / (255. * len(feature)), row)
                    for row in rows
                ),
                key=lambda x: (-x[0], x[1]["id"]),
            )
            if ranked and ranked[0][0] >= threshold:
                best_similarity, best = ranked[0]
                ambiguous = (
                    (len(ranked) > 1
                     and ranked[1][0] >= threshold
                     and best_similarity - ranked[1][0] < AMBIGUITY_GAP)
                    or (category != "unknown" and best["category"] != "unknown"
                        and category != best["category"])
                )
                if ambiguous:
                    return CompactEncounter(
                        modality, "ambiguous_unverified", "unknown",
                        None, 0, best_similarity, len(feature),
                        pc_review_suggested=(
                            pc_opt_in and category == "unknown"
                            and interest >= PC_INTEREST_THRESHOLD),
                    )
                target_id = int(best["id"])
                new_category = (
                    category if best["category"] == "unknown"
                    and category != "unknown" else best["category"]
                )
                conn.execute("""
                    UPDATE m1a_compact_patterns
                    SET sightings=MIN(2147483647,sightings+1),
                        last_seen_epoch_s=MAX(last_seen_epoch_s,?),
                        category=?
                    WHERE id=?
                """, (now, new_category, target_id))
                current = min(2147483647, int(best["sightings"]) + 1)
                return CompactEncounter(
                    modality, "similar_pattern_unverified", new_category,
                    target_id, current, best_similarity, len(feature), False,
                )
            if len(rows) >= MAX_PATTERNS:
                conn.execute("""
                    DELETE FROM m1a_compact_patterns WHERE id=(
                        SELECT id FROM m1a_compact_patterns
                        ORDER BY last_seen_epoch_s ASC,id ASC LIMIT 1
                    )
                """)
            result = conn.execute("""
                INSERT INTO m1a_compact_patterns(
                    modality,category,source,feature_version,fingerprint,
                    sightings,first_seen_epoch_s,last_seen_epoch_s)
                VALUES (?,?,'synthetic_fixture_claim',1,?,1,?,?)
            """, (modality, category, feature, now, now))
            return CompactEncounter(
                modality, "new_pattern_unverified", category,
                int(result.lastrowid), 1, None, len(feature),
                pc_review_suggested=(
                    pc_opt_in and category in {"unknown", "object", "ambient"}
                    and interest >= PC_INTEREST_THRESHOLD),
            )
