"""P15-B9: effective BitBake -e DEV vs shipping identity gate, no rootfs.

Read two private, offline BitBake environments. Never print or publish their
contents: OEM operator password hashes may be expanded in EXTRA_USERS_PARAMS.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex

from scripts.per_p13a_bitbake_env_gate import EnvRefused, bbvar, show_appends_selects_file

LAYER_REL = "yocto/meta-kwipi-p15-account"
APPEND_REL = "recipes-core/images/microduck-image-dev.bbappend"
SCHEMA = "kwipi-p15b9-dev-only-account-metadata-v1"
EXPECTED_KWIPI_COMMANDS = (
    ["groupadd", "-r", "kwipi"],
    ["useradd", "-r", "-g", "kwipi", "-M", "-s", "/sbin/nologin",
     "-p", "!", "kwipi"],
)
EXPECTED_OEM_GROUPS = "robot,sudo,audio,video,dialout,i2c,plugdev,input"


def _commands(value: str) -> list[list[str]]:
    segments = value.split(";")
    if not segments or segments[-1].strip():
        raise EnvRefused("unterminated EXTRA_USERS_PARAMS command")
    if any(not part.strip() for part in segments[:-1]):
        raise EnvRefused("empty or duplicated EXTRA_USERS_PARAMS command")
    try:
        return [shlex.split(part, posix=True) for part in segments[:-1]]
    except ValueError as exc:
        raise EnvRefused("invalid EXTRA_USERS_PARAMS quoting") from exc


def _layers(env: str) -> set[Path]:
    value = bbvar(env, "BBLAYERS")
    return {Path(item).resolve() for item in value.replace("\\n", " ")
            .replace("\\t", " ").split()}


def validate(dev_env: str, shipping_env: str, appends: str,
             *, account_layer: Path) -> dict:
    """Require exactly the two extra DEV commands; no new shipping users."""
    if bbvar(dev_env, "PN") != "microduck-image-dev":
        raise EnvRefused("incorrect DEV recipe")
    if bbvar(shipping_env, "PN") != "microduck-image":
        raise EnvRefused("incorrect shipping recipe")
    if account_layer.is_symlink() or not account_layer.is_dir():
        raise EnvRefused("account layer missing or symbolic")
    layer = account_layer.resolve(strict=True)
    if layer not in _layers(dev_env) or layer not in _layers(shipping_env):
        raise EnvRefused("opt-in account layer missing from BBLAYERS")
    if not show_appends_selects_file(
            appends, recipe="microduck-image-dev.bb",
            expected=layer / APPEND_REL):
        raise EnvRefused("exact DEV-only bbappend not recognized by BitBake")

    ship_commands = _commands(bbvar(shipping_env, "EXTRA_USERS_PARAMS"))
    dev_commands = _commands(bbvar(dev_env, "EXTRA_USERS_PARAMS"))
    if len(ship_commands) != 1:
        raise EnvRefused("shipping account commands changed")
    operator = ship_commands[0]
    if (len(operator) != 9
            or operator[:5] != ["useradd", "-m", "-s", "/bin/bash", "-G"]
            or operator[5] != EXPECTED_OEM_GROUPS
            or operator[6] != "-p" or not operator[7]
            or operator[8] != "microduck"):
        raise EnvRefused("pinned OEM operator account not preserved")
    if dev_commands != ship_commands + list(EXPECTED_KWIPI_COMMANDS):
        raise EnvRefused("DEV identity differs from locked private user")
    return {
        "schema": SCHEMA,
        "status": "bitbake_effective_dev_only_kwipi_account_metadata_pass",
        "dev_identity_commands": len(dev_commands),
        "shipping_identity_commands": len(ship_commands),
        "oem_operator_command_preserved": True,
        "kwipi_group_declared_dev_only": True,
        "kwipi_user_declared_dev_only": True,
        "kwipi_has_motor_group": False,
        "locked_password_requested": True,
        "noninteractive_shell_requested": True,
        "bitbake_metadata_examined": True,
        "do_rootfs_executed_by_gate": False,
        "new_image_or_wic_built": False,
        "account_present_in_new_rootfs_verified": False,
        "real_socket_acl_verified": False,
        "robot_validated": False,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dev-env", type=Path, required=True)
    p.add_argument("--shipping-env", type=Path, required=True)
    p.add_argument("--appends", type=Path, required=True)
    p.add_argument("--account-layer", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    try:
        if args.report.exists() or args.report.is_symlink():
            raise EnvRefused("report already exists")
        sources = (args.dev_env, args.shipping_env, args.appends)
        if any(not x.is_file() or x.is_symlink() for x in sources):
            raise EnvRefused("effective BitBake source missing or symbolic")
        result = validate(args.dev_env.read_text(encoding="utf-8"),
                          args.shipping_env.read_text(encoding="utf-8"),
                          args.appends.read_text(encoding="utf-8"),
                          account_layer=args.account_layer)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
    except (OSError, ValueError) as exc:
        p.exit(1, f"P15-B9 METADATA STOP: {type(exc).__name__}\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
