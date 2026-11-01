"""P15-B9-R: opt-in cached WSL2 DEV-only do_rootfs and independent identity gate.

--check is read-only. --run may change the existing BitBake build cache but
never calls do_image, WIC, RAUC, service start, robotctl or a motor command.
No automatic retries, source downloads or cache cleans. A failure is STOP.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import time

from scripts import per_p15b6_cached_package_runner as cached
from scripts import per_p15b9_rootfs_preflight as preflight
from scripts.per_p13a_bitbake_env_gate import bbvar
from scripts.per_p15b9_rootfs_identity_gate import STATUS, verify_rootfs

MIN_FREE = 32 * 1024**3
MAX_METADATA_SECONDS = 1650
MAX_ROOTFS_SECONDS = 3600
SUCCESS = "p15b9r_cached_dev_do_rootfs_identity_verified_only"


def _environment(cfg: cached.Config) -> dict[str, str]:
    result = dict(os.environ)
    result.update({
        "PYTHONDONTWRITEBYTECODE": "1", "CARGO_NET_OFFLINE": "true",
        "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "protocol.https.allow",
        "GIT_CONFIG_VALUE_0": "never",
        "KAS_WORK_DIR": str(cfg.work), "KAS_BUILD_DIR": str(cfg.build),
        "KAS_CLONE_DEPTH": "1",
    })
    return result


def _overlay(cfg: cached.Config) -> str:
    paths = (
        ("kwipi", cfg.scratch / "meta-kwipi"),
        ("kwipipy", cfg.scratch / "meta-kwipi-python"),
        ("kwipidev", cfg.project / "yocto/meta-kwipi-dev-image"),
        ("kwipip15", cfg.project / "yocto/meta-kwipi-p15-readonly"),
        ("kwipiaccount", cfg.project / "yocto/meta-kwipi-p15-account"),
    )
    result = ("header:\n  version: 14\nrepos:\n"
              "  microduck_os:\n    path: " + json.dumps(str(cfg.yocto)) + "\n")
    for name, path in paths:
        result += ("  " + name + ":\n    path: " + json.dumps(str(path))
                   + "\n    layers:\n      .:\n")
    result += ('local_conf_header:\n  kwipi-p15b9r-offline: |\n'
               '    BB_NO_NETWORK = "1"\n')
    return result


def _stage(cfg: cached.Config, env: dict[str, str]) -> str:
    cfg.scratch.mkdir(mode=0o700)
    commands = [
        [sys.executable, "-m", "scripts.per_p11_v1_source_release",
         "--project", str(cfg.project), "--oem-checkout",
         str(cfg.project / "upstream/microduck"),
         "--output-dir", str(cfg.scratch / "source")],
        [sys.executable, "-m", "scripts.per_p12_yocto_layer", "stage",
         "--yocto", str(cfg.yocto),
         "--source-dir", str(cfg.scratch / "source"),
         "--output", str(cfg.scratch / "meta-kwipi")],
        [sys.executable, "-m", "scripts.per_p14b_yocto_python_layer", "stage",
         "--root", str(cfg.project),
         "--output", str(cfg.scratch / "meta-kwipi-python")],
    ]
    for command in commands:
        cached._execute(command, env, timeout=240, cwd=cfg.project, capture=True)
    config = cfg.yocto / "kas/microduck.yml"
    if not config.is_file() or config.is_symlink():
        raise cached.Refused("pinned OEM KAS file is missing or linked")
    copy = cfg.scratch / "microduck-pinned.yml"
    copy.write_bytes(config.read_bytes())
    if copy.read_bytes() != config.read_bytes():
        raise cached.Refused("KAS OEM source copy differs")
    overlay = cfg.scratch / "p15b9r-offline.yml"
    overlay.write_text(_overlay(cfg), encoding="utf-8")
    combined = str(copy) + ":" + str(overlay)
    # KAS 5.2 forbids concatenating a tracked YAML with an untracked one.
    cached._execute(["kas", "dump", combined], env, timeout=60,
                    cwd=cfg.project, capture=True)
    return combined


def _private(path: Path) -> None:
    # Pre-create BEFORE BitBake: the evaluated environment contains OEM hashes.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    os.close(fd)
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise cached.Refused("BitBake private environment file not mode 0600")


def _metadata_command(scratch: Path) -> str:
    q = lambda name: shlex.quote(str(scratch / name))
    return (
        "set -euo pipefail; bitbake -p && "
        "bitbake -e microduck-image-dev > " + q("dev-env.txt") + " && "
        "bitbake -e microduck-image > " + q("shipping-env.txt") + " && "
        "bitbake -e kwipi-readonly-probe > " + q("p15a-env.txt") + " && "
        "bitbake-layers show-appends > " + q("appends.txt")
    )


def _metadata(cfg: cached.Config, config: str, env: dict[str, str]) -> str:
    for name in ("dev-env.txt", "shipping-env.txt", "p15a-env.txt"):
        _private(cfg.scratch / name)
    # BB sanity requires umask 022; files are already securely created 0600.
    old_umask = os.umask(0o022)
    try:
        cached._execute(
            ["kas", "shell", "--skip", "repos_checkout", config,
             "-c", _metadata_command(cfg.scratch)],
            env, timeout=MAX_METADATA_SECONDS, cwd=cfg.project,
        )
    finally:
        os.umask(old_umask)
    for name in ("dev-env.txt", "shipping-env.txt", "p15a-env.txt", "appends.txt"):
        path = cfg.scratch / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
            raise cached.Refused("missing or linked effective BitBake metadata")
    for name in ("dev-env.txt", "shipping-env.txt", "p15a-env.txt"):
        if (cfg.scratch / name).stat().st_mode & 0o077:
            raise cached.Refused("effective BitBake environment exposed")
    # P15A also verifies P14B and P14C source bytes, APPENDs and DEV/shipping.
    p15a_report = cfg.scratch / "p15a-gate.json"
    cmd = [
        sys.executable, "-m", "scripts.per_p15a_bitbake_env_gate",
        "--recipe-env", str(cfg.scratch / "p15a-env.txt"),
        "--dev-env", str(cfg.scratch / "dev-env.txt"),
        "--shipping-env", str(cfg.scratch / "shipping-env.txt"),
        "--appends", str(cfg.scratch / "appends.txt"),
        "--p15-layer", str(cfg.project / "yocto/meta-kwipi-p15-readonly"),
        "--dev-layer", str(cfg.project / "yocto/meta-kwipi-dev-image"),
        "--py-layer", str(cfg.scratch / "meta-kwipi-python"),
        "--yocto", str(cfg.yocto),
        "--root", str(cfg.project),
        "--report", str(p15a_report),
    ]
    cached._execute(cmd, env, timeout=120, cwd=cfg.project, capture=True)
    b9_report = cfg.scratch / "p15b9-gate.json"
    cmd = [
        sys.executable, "-m", "scripts.per_p15b9_dev_account_env_gate",
        "--dev-env", str(cfg.scratch / "dev-env.txt"),
        "--shipping-env", str(cfg.scratch / "shipping-env.txt"),
        "--appends", str(cfg.scratch / "appends.txt"),
        "--account-layer", str(cfg.project / "yocto/meta-kwipi-p15-account"),
        "--report", str(b9_report),
    ]
    cached._execute(cmd, env, timeout=120, cwd=cfg.project, capture=True)
    p15 = json.loads(p15a_report.read_text(encoding="utf-8"))
    account = json.loads(b9_report.read_text(encoding="utf-8"))
    if (p15.get("status") != "real_bitbake_p15a_metadata_dev_only_verified"
            or account.get("status") != "bitbake_effective_dev_only_kwipi_account_metadata_pass"
            or p15.get("systemd_auto_enable") != "disable"
            or account.get("dev_identity_commands") != 3
            or account.get("shipping_identity_commands") != 1):
        raise cached.Refused("effective DEV/shipping metadata gates are not all PASS")
    dev = (cfg.scratch / "dev-env.txt").read_text(encoding="utf-8")
    ship = (cfg.scratch / "shipping-env.txt").read_text(encoding="utf-8")
    for name, blob in (( "dev", dev), ("shipping", ship)):
        install = bbvar(blob, "IMAGE_INSTALL").replace("\\n", " ").split()
        # P15-B6 add-on deliberately remains CLOSED and unselected in both.
        if "kwipi-passive-fixture" in install:
            raise cached.Refused("unreviewed P15-B6 package selected in " + name)
    return dev


def _paths(cfg: cached.Config, dev_env: str) -> tuple[Path, Path]:
    work = Path(bbvar(dev_env, "WORKDIR"))
    logdir = Path(bbvar(dev_env, "T"))
    rootfs = Path(bbvar(dev_env, "IMAGE_ROOTFS"))
    anchor = (cfg.build / "tmp/work").resolve(strict=True)
    if (not all(x.is_absolute() for x in (work, logdir, rootfs))
            or not work.resolve(strict=False).is_relative_to(anchor)
            or rootfs.parent.resolve(strict=False) != work.resolve(strict=False)
            or logdir.parent.resolve(strict=False) != work.resolve(strict=False)
            or rootfs.name != "rootfs" or logdir.name != "temp"
            or rootfs.is_symlink() or logdir.is_symlink()):
        raise cached.Refused("effective rootfs/log paths escape pinned build workspace")
    return rootfs, logdir


def _logs(folder: Path) -> set[tuple[str, int, int, int]]:
    if not folder.exists():
        return set()
    if not folder.is_dir() or folder.is_symlink():
        raise cached.Refused("BitBake task log folder is linked or invalid")
    return {
        (p.name, p.stat().st_ino, p.stat().st_mtime_ns, p.stat().st_size)
        for p in folder.glob("log.do_rootfs.*")
        if p.is_file() and not p.is_symlink()
    }


def _deploy_artifacts(build: Path) -> dict[str, tuple[int, int]]:
    deploy = build / "tmp/deploy/images"
    if not deploy.is_dir():
        return {}
    return {
        str(p.relative_to(deploy)): (p.stat().st_size, p.stat().st_mtime_ns)
        for p in deploy.rglob("*")
        if p.is_file() and not p.is_symlink()
        and (".wic" in p.name or p.name.endswith((".raucb", ".bmap")))
    }


def execute(cfg: cached.Config) -> dict:
    preflight.check(cfg)
    if shutil.disk_usage(cfg.build).free < MIN_FREE:
        raise cached.Refused("less than 32 GiB free before DEV do_rootfs")
    env = _environment(cfg)
    config = _stage(cfg, env)
    dev_env = _metadata(cfg, config, env)
    rootfs, logdir = _paths(cfg, dev_env)
    prior_logs = _logs(logdir)
    prior_artifacts = _deploy_artifacts(cfg.build)

    old_umask = os.umask(0o022)
    started = time.monotonic()
    try:
        cached._execute(
            ["kas", "shell", "--skip", "repos_checkout", config,
             "-c", "set -euo pipefail; bitbake -c rootfs microduck-image-dev"],
            env, timeout=MAX_ROOTFS_SECONDS, cwd=cfg.project,
        )
    finally:
        os.umask(old_umask)
    duration = round(time.monotonic() - started, 1)
    if not (_logs(logdir) - prior_logs):
        raise cached.Refused("do_rootfs had no new or changed real task log")
    if prior_artifacts != _deploy_artifacts(cfg.build):
        raise cached.Refused("WIC/RAUC deploy artifacts changed unexpectedly")
    identity = verify_rootfs(rootfs)
    if identity.get("status") != STATUS:
        raise cached.Refused("independent installed account audit failed")
    cached._pin(cfg.project, cfg.expected_sha)
    cached._pin(cfg.yocto, cached.YOCTO)
    for name, sha in cached.KAS_REPOS.items():
        cached._pin(cfg.work / name, sha)
    report = {
        "status": SUCCESS,
        "source_revision": cfg.expected_sha,
        "oem_sha": cached.OEM,
        "yocto_sha": cached.YOCTO,
        "bitbake_do_rootfs_exit_code": 0,
        "bitbake_do_rootfs_new_log": True,
        "bitbake_rootfs_task_duration_s": duration,
        "account_present_in_new_rootfs_verified": True,
        "identity_report": identity,
        "wic_or_rauc_artifacts_changed": False,
        "shipping_rootfs_built": False,
        "robot_validated": False,
        "motor_commands_issued": 0,
    }
    (cfg.scratch / "rootfs-proof.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--run", action="store_true",
                        help="explicit cached do_rootfs with no image/signature")
    for name in ("project", "yocto", "work-dir", "build-dir", "scratch"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args()
    cfg = cached.Config(
        *(getattr(args, name).expanduser() for name in
          ("project", "yocto", "work_dir", "build_dir", "scratch")),
        args.expected_sha,
    )
    try:
        report = execute(cfg) if args.run else preflight.check(cfg)
    except (cached.Refused, OSError, ValueError, KeyError) as exc:
        parser.exit(1, "P15-B9-R DO_ROOTFS STOP: " + str(exc) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
