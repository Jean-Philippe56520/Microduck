"""P15-B6-P: explicit, cached, offline local do_package gate (never an image).

Default is read-only preflight. --run must be explicitly supplied by an
operator on a host with an existing KAS/Yocto build and pinned repo cache.
This script cannot attest a BitBake run that it did not execute.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time

OEM = "942e58e3aa6dbb28e7037203fff11866122c7567"
RL = "b02fdea4902c2b93b7d34a83a6f05da4ececb7d3"
YOCTO = "1ee58387810cebb67ae0d634c351d95024483bce"
KAS_REPOS = {
    "openembedded-core": "ae5a301091f5b0574ea7444aab40b309b6d9f3f2",
    "bitbake": "6e260eb6ab1631607ea414d9ff8ede1155faa5d9",
    "meta-yocto": "79b6d87030178bed0088ad3b00aa6dfbabac37c4",
    "meta-openembedded": "f28a144aa0a0ae05ca2ee91e1aef6aa05f6a12db",
    "meta-rockchip": "f2fa9fd14571b855bb59a51da11616904a65f36d",
    "meta-rauc": "38da0e5866a953e664001ba90b5edad68d68cd5d",
}
PASS = "bitbake_passive_addon_package_files_verified_only"
CHECK = "p15b6p_local_cached_preflight_only"
SPACE = 16 * 1024**3


class Refused(ValueError):
    """A required pinned source, cache or safety gate is absent."""


@dataclass(frozen=True)
class Config:
    project: Path
    yocto: Path
    work: Path
    build: Path
    scratch: Path
    expected_sha: str


def _git(path: Path, *cmd: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *cmd], check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
    return result.stdout.strip()


def _pin(path: Path, sha: str) -> None:
    if not path.is_dir() or path.is_symlink() or _git(path, "rev-parse", "HEAD") != sha:
        raise Refused("missing or wrong pinned Git repository: " + path.name)
    if _git(path, "status", "--porcelain", "--untracked-files=no"):
        raise Refused("tracked changes in pinned repository: " + path.name)


def _safe_new_path(path: Path, inputs: tuple[Path, ...]) -> None:
    if not path.is_absolute() or path.exists() or path.is_symlink():
        raise Refused("scratch must be an ABSOLUTE and unused directory")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise Refused("scratch parent must already exist and not be a symlink")
    resolved = path.resolve(strict=False)
    for item in inputs:
        base = item.resolve(strict=True)
        if resolved == base or resolved.is_relative_to(base) or base.is_relative_to(resolved):
            raise Refused("scratch overlaps a source checkout, KAS workdir or cached build")


def _cmake_native_completed(stamps: Path) -> bool:
    # A stamp is only a prerequisite cache hint, not proof B6 is packaged.
    # Do not trust the presence of a .sigdata file as a completed task.
    # OE STAMP = .../${PN}/${PV}-${PR}: task name is appended to the VERSION FILE, not a nested task directory.
    for item in stamps.glob("**/cmake-native/*do_populate_sysroot*"):
        if (item.is_file() and not item.is_symlink()
                and ".sigdata." not in item.name
                and ".sigbasedata." not in item.name
                and "_setscene" not in item.name):
            return True
    return False


def preflight(cfg: Config) -> dict:
    if not re.fullmatch("[a-f0-9]{40}", cfg.expected_sha):
        raise Refused("explicit --expected-sha must be a 40-character lowercase SHA")
    paths = (cfg.project, cfg.yocto, cfg.work, cfg.build)
    if any(any(c in str(p) for c in (":", "\r", "\n")) for p in (*paths, cfg.scratch)):
        raise Refused("unsafe newline/colon in KAS source or scratch path")
    if any(not p.is_absolute() or not p.is_dir() or p.is_symlink() for p in paths):
        raise Refused("all checkouts and cache paths must be existing absolute real directories")
    if (cfg.project.resolve() == cfg.yocto.resolve()
            or cfg.work.resolve() == cfg.build.resolve()):
        raise Refused("project/Yocto or work/build paths coincide")
    _safe_new_path(cfg.scratch, paths)
    _pin(cfg.project, cfg.expected_sha)
    _pin(cfg.yocto, YOCTO)
    _pin(cfg.project / "upstream/microduck", OEM)
    _pin(cfg.project / "upstream/microduck_rl", RL)
    if _git(cfg.project, "rev-parse", "HEAD:upstream/microduck") != OEM:
        raise Refused("Companion gitlink for OEM differs from pinned revision")
    if _git(cfg.project, "rev-parse", "HEAD:upstream/microduck_rl") != RL:
        raise Refused("Companion gitlink for MuJoCo differs from pinned revision")
    for name, sha in KAS_REPOS.items():
        _pin(cfg.work / name, sha)

    if not (cfg.yocto / "kas/microduck.yml").is_file():
        raise Refused("pinned OEM KAS configuration missing")
    if not (cfg.build / "conf/local.conf").is_file():
        raise Refused("local KAS build configuration missing; no cache proof")
    stamps = cfg.build / "tmp/stamps"
    if not stamps.is_dir() or stamps.is_symlink():
        raise Refused("cached BitBake stamps missing")
    if not (cfg.build / "tmp/work").is_dir():
        raise Refused("cached BitBake work directory missing")
    if not _cmake_native_completed(stamps):
        raise Refused("no completed cached cmake-native sysroot stamp: stop before a cold build")
    if shutil.disk_usage(cfg.build).free < SPACE:
        raise Refused("free disk below 16 GiB")

    return {
        "status": CHECK, "source_revision": cfg.expected_sha,
        "oem_sha": OEM, "yocto_sha": YOCTO, "pinned_kas_repositories": len(KAS_REPOS),
        "existing_cmake_native_sysroot_stamp": True,
        "existing_bitbake_cache": True,
        "minimum_free_gib": 16,
        "scratch_written": False, "bitbake_run": False, "package_verified": False,
        "robot_access": False, "image_built": False, "motor_commands": 0,
    }


def _check_kas() -> None:
    if shutil.which("kas") is None or shutil.which("cargo") is None:
        raise Refused("kas 5.2 and cargo are required on the WSL2 host")
    version = subprocess.run(
        ["kas", "--version"], check=True, capture_output=True,
        text=True, timeout=15).stdout.strip()
    if not re.search(r"\b5\.2(?:\.0)?\b", version):
        raise Refused("kas must be pinned to version 5.2: " + version)


def _execute(args: list[str], env: dict[str, str], *,
             timeout: int, cwd: Path, capture: bool = False) -> str:
    # A POSIX process group makes timeout fail-closed, including BitBake children.
    proc = subprocess.Popen(
        args, env=env, cwd=cwd, text=True,
        stdout=subprocess.PIPE if capture else None,
        start_new_session=True)
    try:
        out, _ = proc.communicate(timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
        reason = "interrupted" if isinstance(exc, KeyboardInterrupt) else "expired"
        raise Refused("command " + reason + " without package proof: " + args[0]) from exc
    if proc.returncode != 0:
        raise Refused("command failed (" + str(proc.returncode) + "): " + args[0])
    return out or ""


def _overlay(cfg: Config) -> str:
    root = cfg.scratch
    return (
        "header:\n  version: 14\n"
        "repos:\n"
        "  kwipi:\n    path: " + json.dumps(str(root / "meta-kwipi")) + "\n    layers:\n      .:\n"
        "  kwipipy:\n    path: " + json.dumps(str(root / "meta-kwipi-python")) + "\n    layers:\n      .:\n"
        "  kwipipassive:\n    path: " + json.dumps(str(root / "meta-kwipi-passive")) + "\n    layers:\n      .:\n"
        "  kwipidev:\n    path: " + json.dumps(str(cfg.project / "yocto/meta-kwipi-dev-image")) + "\n    layers:\n      .:\n"
        "local_conf_header:\n"
        "  kwipi-b6p-offline: |\n"
        "    BB_NO_NETWORK = \"1\"\n"
    )


def _task_command(scratch: Path) -> str:
    q = lambda path: shlex.quote(str(scratch / path))
    return (
        "set -euo pipefail; "
        "bitbake -p && "
        f"bitbake -e kwipi-passive-fixture > {q('recipe-env.txt')} && "
        f"bitbake -e microduck-image-dev > {q('dev-env.txt')} && "
        f"bitbake -e microduck-image > {q('shipping-env.txt')} && "
        f"bitbake-getvar -r kwipi-passive-fixture -f p15b6.sha256sum --value SRC_URI > {q('checksum.txt')} && "
        "bitbake -c package kwipi-passive-fixture"
    )


def execute(cfg: Config) -> dict:
    preflight(cfg)
    _check_kas()
    env = dict(os.environ)
    env.update({
        "PYTHONDONTWRITEBYTECODE": "1", "CARGO_NET_OFFLINE": "true",
        "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "protocol.https.allow", "GIT_CONFIG_VALUE_0": "never",
        "KAS_WORK_DIR": str(cfg.work), "KAS_BUILD_DIR": str(cfg.build),
        "KAS_CLONE_DEPTH": "1",
    })
    cfg.scratch.mkdir(mode=0o700)
    commands = [
        [sys.executable, "-m", "scripts.per_p11_v1_source_release",
         "--project", str(cfg.project), "--oem-checkout",
         str(cfg.project / "upstream/microduck"),
         "--output-dir", str(cfg.scratch / "source")],
        [sys.executable, "-m", "scripts.per_p12_yocto_layer", "stage",
         "--yocto", str(cfg.yocto), "--source-dir", str(cfg.scratch / "source"),
         "--output", str(cfg.scratch / "meta-kwipi")],
        [sys.executable, "-m", "scripts.per_p14b_yocto_python_layer", "stage",
         "--root", str(cfg.project), "--output", str(cfg.scratch / "meta-kwipi-python")],
        [sys.executable, "-m", "scripts.per_p15b6_passive_python_addon", "stage",
         "--root", str(cfg.project), "--output", str(cfg.scratch / "meta-kwipi-passive")],
    ]
    for command in commands:
        _execute(command, env, timeout=240, cwd=cfg.project)
    overlay = cfg.scratch / "p15b6p-offline.yml"
    overlay.write_text(_overlay(cfg), encoding="utf-8")
    config = str(cfg.yocto / "kas/microduck.yml") + ":" + str(overlay)
    start = time.monotonic()
    _execute(["kas", "shell", "--skip", "repos_checkout", config,
              "-c", _task_command(cfg.scratch)],
             env, timeout=1600, cwd=cfg.project)
    duration = time.monotonic() - start
    proof = cfg.scratch / "package-proof.json"
    audit = [
        sys.executable, "-m", "scripts.per_p15b6_bitbake_package_gate",
        "--root", str(cfg.project),
        "--base-layer", str(cfg.scratch / "meta-kwipi-python"),
        "--addon-layer", str(cfg.scratch / "meta-kwipi-passive"),
        "--dev-layer", str(cfg.project / "yocto/meta-kwipi-dev-image"),
        "--recipe-env", str(cfg.scratch / "recipe-env.txt"),
        "--dev-env", str(cfg.scratch / "dev-env.txt"),
        "--shipping-env", str(cfg.scratch / "shipping-env.txt"),
        "--checksum-value-file", str(cfg.scratch / "checksum.txt"),
        "--output", str(proof),
    ]
    _execute(audit, env, timeout=90, cwd=cfg.project)
    data = json.loads(proof.read_text(encoding="utf-8"))
    if data.get("status") != PASS or data.get("source_revision") != cfg.expected_sha:
        raise Refused("package proof status or SHA mismatched actual source")
    # Recheck pinned sources after kas (no OEM code changes are authorized).
    _pin(cfg.project, cfg.expected_sha)
    _pin(cfg.yocto, YOCTO)
    for name, sha in KAS_REPOS.items():
        _pin(cfg.work / name, sha)
    return {
        "status": PASS, "source_revision": cfg.expected_sha,
        "bitbake_do_package_exit_code": 0,
        "bitbake_duration_s": round(duration, 1),
        "package_proof_path": str(proof),
        "files_hash_verified": data["package_split_files_verified"],
        "robot_access": False, "image_built": False, "motor_commands": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true",
                        help="Read-only preflight; no source staging or BitBake")
    action.add_argument("--run", action="store_true",
                        help="Explicitly stage and run bounded local BitBake do_package")
    for name in ("project", "yocto", "work-dir", "build-dir", "scratch"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    opt = parser.parse_args()
    cfg = Config(*(getattr(opt, n).expanduser() for n in (
        "project", "yocto", "work_dir", "build_dir", "scratch")),
        opt.expected_sha)
    try:
        result = execute(cfg) if opt.run else preflight(cfg)
        print(json.dumps(result, sort_keys=True))
    except (Refused, ValueError, OSError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        parser.exit(1, "P15-B6-P-CACHE STOP: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
