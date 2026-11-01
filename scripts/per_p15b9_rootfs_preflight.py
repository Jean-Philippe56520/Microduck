"""P15-B9-R: read-only preflight before any cached DEV rootfs attempt.

Reuses P15-B6-P's pinned cached WSL2 gate; never stages, builds, or writes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts import per_p15b6_cached_package_runner as cached
from scripts.per_p15a_bitbake_env_gate import verify_source as verify_p15a
from tests.test_per_p15b9_dev_account import (
    EXPECTED_APPEND, EXPECTED_CONF, APPEND, CONF,
)

ROOT_LAYERS = (
    "yocto/meta-kwipi-dev-image",
    "yocto/meta-kwipi-p15-readonly",
    "yocto/meta-kwipi-p15-account",
)
ACCOUNT = ROOT_LAYERS[-1]


def _account_layer(root: Path) -> None:
    layer = root / ACCOUNT
    if layer.is_symlink() or not layer.is_dir():
        raise cached.Refused("P15-B9 account layer missing or symlinked")
    entries = {
        p.relative_to(layer).as_posix()
        for p in layer.rglob("*") if p.is_file() or p.is_symlink()
    }
    if entries != {CONF, APPEND}:
        raise cached.Refused("P15-B9 account source manifest differs")
    for rel, exact in ((CONF, EXPECTED_CONF), (APPEND, EXPECTED_APPEND)):
        p = layer / rel
        if p.is_symlink() or p.read_text(encoding="utf-8") != exact:
            raise cached.Refused("P15-B9 account file differs: " + rel)


def check(cfg: cached.Config) -> dict:
    result = cached.preflight(cfg)  # pinned repos, cache, disk, kas, no writes
    root = cfg.project
    for rel in ROOT_LAYERS:
        layer = root / rel
        if layer.is_symlink() or not layer.is_dir():
            raise cached.Refused("required DEV layer absent or linked: " + rel)
    _account_layer(root)
    probe = verify_p15a(root / ROOT_LAYERS[1])
    if probe["reviewed_source_unchanged"] is not True:
        raise cached.Refused("P15A reviewed source differs")
    # P14C source and P14B package are checked again with effective BitBake
    # variables at the separate run gate; this is not an installation proof.
    return {
        "status": "p15b9r_cached_rootfs_readonly_preflight_only",
        "source_revision": result["source_revision"],
        "oem_sha": result["oem_sha"],
        "yocto_sha": result["yocto_sha"],
        "pinned_kas_repositories": result["pinned_kas_repositories"],
        "cache_available": result["existing_bitbake_cache"],
        "account_layer_exact": True,
        "p15a_source_reviewed": True,
        "rootfs_built": False,
        "account_present_in_new_rootfs_verified": False,
        "shipping_unchanged_by_this_check": True,
        "bitbake_executed": False,
        "scratch_written": False,
        "robot_validated": False,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("project", "yocto", "work-dir", "build-dir", "scratch"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--expected-sha", required=True)
    args = p.parse_args()
    cfg = cached.Config(
        *(getattr(args, name).expanduser() for name in (
            "project", "yocto", "work_dir", "build_dir", "scratch"
        )), args.expected_sha
    )
    try:
        print(json.dumps(check(cfg), sort_keys=True))
    except (cached.Refused, OSError, ValueError) as exc:
        p.exit(1, "P15-B9-R PREFLIGHT STOP: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
