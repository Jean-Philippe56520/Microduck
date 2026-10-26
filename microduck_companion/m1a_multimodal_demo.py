"""M1-A two-process compact visual+sound memory demo (synthetic fixtures).

Both invocations use the SAME SQLite file; no raw image/PCM or private memory
is shared except during extraction. Does not contact a PC, camera, microphone,
OEM daemon, motor or speaker. Neither semantic classification nor identity is
verified, even if a category string is present.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import struct

from .compact_multimodal_memory import CompactPatternMemory
from .episodic_memory import ExperienceMemory

FIXTURE_WALL = 1_780_000_000.


def _synthetic_pixels(brightness: int = 0) -> bytes:
    pixels = [35 + brightness] * 1024
    for y in range(4, 16):
        for x in range(5, 17):
            pixels[y * 32 + x] = 185 + brightness
    return bytes(pixels)


def _synthetic_audio(volume: float = 5000.) -> bytes:
    # One 440Hz synthetic tone; NOT a pet sound or recorded speech.
    points = tuple(
        round(volume * math.sin(2 * math.pi * 440 * i / 8000))
        for i in range(1024)
    )
    return struct.pack("<1024h", *points)


def run_demo(path: Path, *, session: str) -> dict:
    if session not in ("first", "second"):
        raise ValueError("session is first or second only")
    if not isinstance(path, Path):
        raise TypeError("SQLite destination must be an explicit test Path")
    memory = ExperienceMemory(path)
    try:
        patterns = CompactPatternMemory(memory)
        if session == "first":
            image = patterns.observe_image(
                _synthetic_pixels(), category="object",
                now_wall_epoch_s=FIXTURE_WALL,
                pc_opt_in=True, interest=.9,
            )
            audio = patterns.observe_audio(
                _synthetic_audio(), category="ambient",
                now_wall_epoch_s=FIXTURE_WALL + .1,
                pc_opt_in=True, interest=.9,
            )
            if (image.status != "new_pattern_unverified"
                    or audio.status != "new_pattern_unverified"
                    or not image.pc_review_suggested
                    or not audio.pc_review_suggested
                    or patterns.count() != 2):
                raise RuntimeError("M1-A expected two initial mock discoveries")
            status = "two_new_synthetic_patterns"
            hints = 2
        else:
            results = []
            for i in range(1, 10):
                results.append(patterns.observe_image(
                    _synthetic_pixels(brightness=12), now_wall_epoch_s=FIXTURE_WALL+i,
                    pc_opt_in=True, interest=1.,
                ))
                results.append(patterns.observe_audio(
                    _synthetic_audio(volume=8000.), now_wall_epoch_s=FIXTURE_WALL+i+.1,
                    pc_opt_in=True, interest=1.,
                ))
            if (any(r.status != "similar_pattern_unverified"
                    or r.pc_review_suggested for r in results)
                    or patterns.count() != 2):
                raise RuntimeError("M1-A repeat dedup failed")
            status = "nine_more_sightings_each_no_pc_hints"
            hints = 0
        rows = memory.conn.execute("""
            SELECT modality,category,sightings,length(fingerprint) AS bytes,
                   source FROM m1a_compact_patterns
            ORDER BY modality
        """).fetchall()
        found = tuple(
            (r["modality"],r["category"],r["sightings"],r["bytes"],r["source"])
            for r in rows
        )
        target = 1 if session == "first" else 10
        if (len(found)!=2 or any(r[2]!=target for r in found)
                or patterns.signature_storage_bytes()!=80
                or memory.experience_count()!=0):
            raise RuntimeError("M1-A compact counts or media retention failed")
        return {
            "scenario":"synthetic_multimodal_compact_memory",
            "session":session,
            "status":status,
            "pattern_count":patterns.count(),
            "encounters_per_pattern":target,
            "fingerprint_blob_bytes_total":patterns.signature_storage_bytes(),
            "storage_bytes_are_not_sqlite_file_size":True,
            "pc_review_suggestions_no_requests":hints,
            "pc_network_requests":0,
            "raw_photos_stored":0,
            "raw_audio_files_stored":0,
            "robot_camera_or_microphone_connected":False,
            "motor_commands_issued":0,
            "same_object_or_voice_verified":False,
            "robot_hardware_validated":False,
        }
    finally:
        memory.close()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--database", type=Path, required=True)
    p.add_argument("--session", choices=("first","second"), required=True)
    args = p.parse_args()
    print(json.dumps(run_demo(args.database, session=args.session),
                     sort_keys=True, allow_nan=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
