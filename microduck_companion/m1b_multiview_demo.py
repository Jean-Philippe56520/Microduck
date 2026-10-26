"""M1-B two-process synthetic multiview proof and host-only cost sampler.

No input media, Qwen, OEM socket or motors. The grouped association is
declared by the fixture generator, not discovered or physically verified.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import time

from .episodic_memory import ExperienceMemory
from .m1a_multimodal_demo import FIXTURE_WALL,_synthetic_audio,_synthetic_pixels
from .multiview_pattern_memory import MultiviewPatternMemory,MultiviewLimits


def run_demo(database: Path,session: str) -> dict:
    if session not in ("first","second"):
        raise ValueError("M1-B session must be first/second")
    if not isinstance(database,Path):
        raise TypeError("explicit mock SQLite path required")
    db=ExperienceMemory(database)
    try:
        m=MultiviewPatternMemory(db)
        now=FIXTURE_WALL
        if session=="first":
            img=m.observe_image(
                _synthetic_pixels(),category="object",
                now_wall_epoch_s=now,interest=.8,pc_opt_in=True,
            )
            snd=m.observe_audio(
                _synthetic_audio(),category="ambient",
                now_wall_epoch_s=now+.1,interest=.8,pc_opt_in=True,
            )
            if (img.status!="new_group_unverified"
                    or snd.status!="new_group_unverified"
                    or img.group_id==snd.group_id):
                raise RuntimeError("M1-B initial synthetic groups not created")
            label="two_unverified_groups_one_exemplar_each"
            expected=1
        else:
            img=m.observe_image(
                _synthetic_pixels(brightness=12),
                now_wall_epoch_s=now+1,
                pc_opt_in=True,interest=1.,
            )
            snd=m.observe_audio(
                _synthetic_audio(volume=8000),
                now_wall_epoch_s=now+1.1,
                pc_opt_in=True,interest=1.,
            )
            if (img.status!="similar_group_unverified"
                    or snd.status!="similar_group_unverified"):
                raise RuntimeError("M1-B existing patterns not recalled")
            label="familiar_motifs_no_new_stored_media"
            expected=2
        stats=m.stats()
        groups=db.conn.execute("""
            SELECT modality,sightings FROM m1b_groups ORDER BY modality
        """).fetchall()
        counts={r["modality"]:r["sightings"] for r in groups}
        if (stats["groups"]!=2 or stats["signatures"]!=2
                or stats["fingerprint_bytes"]!=80
                or counts!={"audio":expected,"image":expected}):
            raise RuntimeError("M1-B compact grouping was not retained")
        return {
            "experiment":"synthetic_multiview_storage_only",
            "session":session,
            "status":label,
            "groups":stats["groups"],
            "signatures":stats["signatures"],
            "fingerprint_fields_bytes":stats["fingerprint_bytes"],
            "sqlite_allocated_pages_bytes_excludes_wal":
                stats["sqlite_allocated_pages_bytes"],
            "sightings_each":expected,
            "pc_review_hint_only_no_network":session=="first",
            "raw_media_stored":False,
            "real_same_source_verified":False,
            "real_sensor_access":False,
            "robot_motor_commands":0,
            "robot_hardware_validated":False,
        }
    finally:
        db.close()


def run_host_scaling() -> dict:
    # Stress high-water points on the host only; generated 32x32 pixels are
    # deliberately random unrelated fixtures, not a class labelled dataset.
    from .compact_multimodal_memory import image_fingerprint
    import random
    db=ExperienceMemory()
    try:
        m=MultiviewPatternMemory(db,MultiviewLimits(
            max_groups=1024,max_signatures=1024,
            max_signatures_per_group=4,max_fingerprint_bytes=65536,
            max_comparisons=1024,
        ))
        durations=[]
        for i in range(512):
            rnd=random.Random(i+11000)
            grid=[rnd.choice((12,95,230)) for _ in range(64)]
            pixels=bytes(grid[(y//4)*8 + (x//4)]
                         for y in range(32) for x in range(32))
            start=time.perf_counter_ns()
            m.observe_image(pixels,now_wall_epoch_s=FIXTURE_WALL+i)
            durations.append((time.perf_counter_ns()-start)/1e6)
        snap=m.stats()
        if (snap["groups"]>512 or snap["signatures"]>512
                or snap["fingerprint_bytes"]>32768):
            raise RuntimeError("bounded host scaling regression")
        # Percentiles are of full Python+SQLite cycle, not native NPU time.
        return {
            "kind":"host_only_512_synthetic_32x32_images",
            "attempts":512,"groups":snap["groups"],
            "signatures":snap["signatures"],
            "fingerprint_fields_bytes":snap["fingerprint_bytes"],
            "sqlite_allocated_pages_bytes_excludes_wal":
                snap["sqlite_allocated_pages_bytes"],
            "cycle_latency_median_ms":statistics.median(durations),
            "cycle_latency_max_ms":max(durations),
            "robot_validated":False,"models_loaded":0,
            "oem_commands":0,
        }
    finally:
        db.close()


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database",type=Path)
    parser.add_argument("--session",choices=("first","second"))
    parser.add_argument("--host-scaling",action="store_true")
    args=parser.parse_args(argv)
    if args.host_scaling and args.database is None and args.session is None:
        value=run_host_scaling()
    elif (not args.host_scaling and args.database is not None
          and args.session is not None):
        value=run_demo(args.database,args.session)
    else:
        parser.error("choose either --host-scaling or --database and --session")
    print(json.dumps(value,sort_keys=True,allow_nan=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
