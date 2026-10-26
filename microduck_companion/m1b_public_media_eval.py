"""M1-B OPTIONAL PUBLIC-MEDIA spot check on Wikimedia CC0 sources.

Never runs implicitly, never stores downloaded media or recognises people.
Only allowlisted Wikimedia Commons photos and two CC0 environmental sounds.
External declarations of CC0 are NOT a warranty. Requires explicit --public.
The images are independent PHOTOS, NOT views of one verified physical object.
The positive tests are brightness/gain changes to the SAME recording only,
NOT evidence of view/voice/source recognition in a home.

Dependencies ONLY for this optional HOST benchmark: Pillow + ffmpeg\n(binary may be supplied by optional pinned imageio-ffmpeg wheel).
No files created; JPEG/OGG decoded in RAM. Network timeouts/refusals are
honestly reported as unavailable, not turned into invented measurements.
"""
from __future__ import annotations

from dataclasses import dataclass
import argparse
import hashlib
from io import BytesIO
import json
import math
import shutil
import struct
import subprocess
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from .compact_multimodal_memory import image_fingerprint,audio_fingerprint
from .episodic_memory import ExperienceMemory
from .multiview_pattern_memory import MultiviewPatternMemory
from .visual_photo_baseline import fetch_thumbnail
from .visual_photo_catalog import PHOTO_CATALOG

# Independent user-uploaded work, Commons file pages declared CC0 1.0.
# Source pages must be re-checked before any reuse, do not collect voices.
PUBLIC_SOUNDS = (
    ("Door_knocker_audio.ogg", "knock",
     "https://commons.wikimedia.org/wiki/File:Door_knocker_audio.ogg"),
    ("Sound_Effect_-_Door_Bell.ogg", "ambient",
     "https://commons.wikimedia.org/wiki/File:Sound_Effect_-_Door_Bell.ogg"),
)
PHOTO_NAMES = (
    "Cat_looking.jpg", "Cute_cat_2024.jpg",
    "Dog_in_forest.jpg", "My_cute_dog.jpg",
    "Flower_photo_normal.jpg", "Bird_image.jpg",
)
MAX_PUBLIC_OGG = 200_000
MAX_PCM_DECODED = 8_000 * 2 * 5
SAMPLE_COUNT = 1024
TIME0 = 1_780_000_000.


def commons_audio_url(filename: str) -> str:
    if (type(filename) is not str
            or filename not in {a for a,_,_ in PUBLIC_SOUNDS}):
        raise ValueError("audio source must be on the curated CC0 list")
    signature=hashlib.md5(filename.encode("utf8")).hexdigest()
    return ("https://upload.wikimedia.org/wikipedia/commons/"
            f"{signature[0]}/{signature[:2]}/"
            + quote(filename,safe="._-"))


def load_cc0_ogg(filename: str, *, opener=urlopen) -> bytes:
    """Bounded download, whitelist redirect and type; no disk writes."""
    url=commons_audio_url(filename)
    request=Request(url,headers={
        "User-Agent":"Microduck-Companion-M1B-CC0-Research/0.1",
        "Accept":"audio/ogg,application/ogg",
    })
    with opener(request,timeout=10) as response:
        target=urlparse(response.geturl())
        if target.scheme!="https" or target.hostname!="upload.wikimedia.org":
            raise ValueError("unexpected CC0 sound redirect")
        ctype=response.headers.get("Content-Type","").split(";")[0].lower()
        if ctype not in ("application/ogg","audio/ogg",
                         "application/octet-stream"):
            raise ValueError("unexpected CC0 sound content type")
        raw=response.read(MAX_PUBLIC_OGG+1)
    if not 500 < len(raw) <= MAX_PUBLIC_OGG or not raw.startswith(b"OggS"):
        raise ValueError("malformed/oversized public audio")
    return raw


def _host_ffmpeg() -> str:
    """Find system ffmpeg or the optional pinned imageio-ffmpeg host wheel."""
    system=shutil.which("ffmpeg")
    if system:
        return system
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, OSError, RuntimeError) as exc:
        raise RuntimeError("ffmpeg host decoder is unavailable") from exc


def decoded_loudest_pcm(raw: bytes) -> bytes:
    """Decode public OGG to 8kHz mono PCM in memory, then choose one window."""
    if type(raw) is not bytes or not raw.startswith(b"OggS") or len(raw)>MAX_PUBLIC_OGG:
        raise ValueError("expected bounded OGG bytes")
    decoder=_host_ffmpeg()
    result=subprocess.run([
        decoder,"-hide_banner","-loglevel","error",
        "-i","pipe:0","-t","5","-ac","1","-ar","8000",
        "-f","s16le","pipe:1",
    ],input=raw,capture_output=True,timeout=15,check=False)
    pcm=result.stdout
    if (result.returncode or len(pcm)>MAX_PCM_DECODED
            or len(pcm)<SAMPLE_COUNT*2):
        raise ValueError("invalid bounded public audio decode")
    values=struct.unpack("<"+str(len(pcm)//2)+"h",pcm)
    best_start=0
    best_energy=-1
    for start in range(0,len(values)-SAMPLE_COUNT+1,512):
        energy=sum(v*v for v in values[start:start+SAMPLE_COUNT])
        if energy>best_energy:
            best_energy,best_start=energy,start
    chosen=values[best_start:best_start+SAMPLE_COUNT]
    return struct.pack("<1024h",*chosen)


def public_image_gray32(photo_name: str) -> bytes:
    if photo_name not in PHOTO_NAMES:
        raise ValueError("public photo outside study list")
    photo=next(p for p in PHOTO_CATALOG if p.filename==photo_name)
    if photo.license!="CC0-1.0" or photo.split!="validation":
        raise ValueError("unreviewed public photo declaration")
    try:
        from PIL import Image,ImageOps
    except ImportError as exc:
        raise RuntimeError("Pillow required for optional host photo decode") from exc
    jpeg=fetch_thumbnail(photo)
    with Image.open(BytesIO(jpeg)) as img:
        transformed=ImageOps.exif_transpose(img).convert("L")
        scaled=ImageOps.fit(transformed,(32,32),method=Image.Resampling.BILINEAR)
        pixels=scaled.tobytes()
    # No image/RAW/PIL handle is kept or written to SQLite.
    return pixels


def brightness_variant(pixels: bytes, delta: int = 12) -> bytes:
    return bytes(min(255, max(0, p + delta)) for p in pixels)


def audio_gain_variant(pcm: bytes, multiplier: float = .8) -> bytes:
    samples=struct.unpack("<"+str(len(pcm)//2)+"h",pcm)
    data=[max(-32768,min(32767,round(p*multiplier))) for p in samples]
    return struct.pack("<"+str(len(data))+"h",*data)


def run_public_spot_check() -> dict:
    """Real samples only if all curated sources can be independently fetched.

    One missing source yields an explicit 'unavailable' exception, not
    an apparent successful evaluation on a smaller hidden test set.
    """
    _host_ffmpeg()  # Fail before network if decoder is absent.
    images=tuple(
        (filename,public_image_gray32(filename))
        for filename in PHOTO_NAMES
    )
    sounds=tuple(
        (filename,category,decoded_loudest_pcm(load_cc0_ogg(filename)))
        for filename,category,_ in PUBLIC_SOUNDS
    )
    db=ExperienceMemory()
    try:
        mem=MultiviewPatternMemory(db)
        image_repeats=0
        image_false_merges=0
        for i,(filename,pixels) in enumerate(images):
            src=next(p for p in PHOTO_CATALOG if p.filename==filename)
            label="object" if src.category=="unknown" else src.category
            start=mem.observe_image(
                pixels,category=label,now_wall_epoch_s=TIME0+2*i,
            )
            if start.status=="similar_group_unverified":
                # Each catalog image is credited to a distinct photographer.
                # That does not PROVE distinct real physical animals, but is
                # a useful proxy for measuring suspicious cross-file merges.
                image_false_merges+=1
            candidate=mem.observe_image(
                brightness_variant(pixels),category=label,
                now_wall_epoch_s=TIME0+2*i+1,
            )
            if candidate.status=="similar_group_unverified" and (
                    candidate.group_id==start.group_id):
                image_repeats+=1
        sound_repeats=0
        sound_false_merges=0
        for i,(name,label,pcm) in enumerate(sounds):
            start=mem.observe_audio(
                pcm,category=label,
                now_wall_epoch_s=TIME0+100+2*i,
            )
            if start.status=="similar_group_unverified":
                sound_false_merges+=1
            duplicate=mem.observe_audio(
                audio_gain_variant(pcm),category=label,
                now_wall_epoch_s=TIME0+101+2*i,
            )
            if duplicate.status=="similar_group_unverified" and (
                    duplicate.group_id==start.group_id):
                sound_repeats+=1
        stats=mem.stats()
        return {
            "kind":"independent_public_CC0_samples_host_spot_check",
            "image_sources":len(images),
            "audio_sources":len(sounds),
            "image_same_file_brightness_pairs_recalled":image_repeats,
            "image_pairs_tested":len(images),
            "audio_same_recording_gain_pairs_recalled":sound_repeats,
            "audio_pairs_tested":len(sounds),
            "image_cross_file_auto_merges_proxy":image_false_merges,
            "audio_cross_recording_auto_merges_proxy":sound_false_merges,
            "fingerprint_fields_bytes":stats["fingerprint_bytes"],
            "sqlite_allocated_pages_bytes_excludes_wal":
                stats["sqlite_allocated_pages_bytes"],
            "real_same_object_views_tested":False,
            "real_same_animal_identification_tested":False,
            "real_camera_or_microphone_tested":False,
            "robot_hardware_validated":False,
            "raw_media_files_stored":0,
            "motor_commands":0,
            "network_calls_to_curated_public_commons_only":True,
        }
    finally:
        db.close()


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-cc0",action="store_true",
                        help="explicitly fetch only the curated public CC0 sample files")
    args=parser.parse_args(argv)
    if not args.public_cc0:
        parser.error("no network by default; --public-cc0 is required")
    result=run_public_spot_check()
    print(json.dumps(result,sort_keys=True,allow_nan=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
