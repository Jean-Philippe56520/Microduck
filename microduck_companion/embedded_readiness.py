"""F6-A offline-only embedded-readiness inventory; no robot-side service.

All facts about OEM paths are taken from the pinned microduck submodule.
The Yocto data mount is CONDITIONAL; merely seeing /var/lib/robot does not
prove persistence. This module only evaluates CALLER-SUPPLIED evidence and
does not read /proc, connect to a daemon, mkdir, persist, control motors,
or enable Qwen. No result certifies an actual physical board.

For an eventual installation: separately verify mounted data PARTLABEL,
free space, permissions, service users, OEM revision, real resource budget
and graceful startup/shutdown on the physical robot. This module never
authorizes installation or autonomous movement.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from .passive_sources import OEM_API_VERSION, PINNED_OEM_REVISION

YOCTO_SNAPSHOT_REVISION = "91691234f3b518a94ee4391f8567c9486335f507"
DATA_MOUNT = "/var/lib/robot"
COMPANION_STATE_CANDIDATE = DATA_MOUNT + "/companion"
SQLITE_PATH_CANDIDATE = COMPANION_STATE_CANDIDATE + "/experiences.sqlite3"
VOLATILE_SQLITE = ":memory:"
MAX_MOUNTINFO_CHARS = 65536
MAX_MOUNTINFO_LINES = 512

# These are ROUTES from the pinned vendor source, not functioning adapters.
# 'implemented' is true only for the existing, restricted mediad hello probe.
@dataclass(frozen=True)
class OemInterface:
    owner: str
    socket: str
    documented_read_methods: tuple[str, ...]
    implemented_read_methods: tuple[str, ...]
    actuator_access_enabled: bool = False

    def __post_init__(self) -> None:
        if (not self.owner or not self.socket.startswith("/run/")
                or any(x not in self.documented_read_methods
                       for x in self.implemented_read_methods)
                or self.actuator_access_enabled):
            raise ValueError("F6-A interfaces have no actuator authority")


OEM_INTERFACES = (
    OemInterface(
        "robotd", "/run/robotd.sock",
        ("hello", "robot.health", "robot.subscribe"), (),
    ),
    OemInterface(
        "mediad", "/run/mediad/media.sock", ("hello",), ("hello",),
    ),
    OemInterface(
        "tofd", "/run/tofd/tof.sock", ("tof.stream",), (),
    ),
)
OFFLINE_FUNCTIONS = (
    "mock_passive_events",
    "local_motivations_and_intentions",
    "episodic_sqlite_for_fixtures",
    "uncertain_memory_and_corrections_for_fixtures",
    "stationary_silent_default",
)
OPTIONAL_PC_ONLY = ("ollama_qwen_hypotheses",)
NOT_IMPLEMENTED_ON_HARDWARE = (
    "live_mediad_categories",
    "live_tofd_frames",
    "motion_intent_adapter",
    "certified_floor_or_stairs",
    "real_individual_recognition",
    "systemd_companion_installation",
)


@dataclass(frozen=True)
class BoardInspection:
    """Compatibility declared by fixture metadata, NOT live board detection."""

    status: str
    machine: str | None
    compatible: str | None
    physically_verified: bool = False

    def __post_init__(self) -> None:
        if self.physically_verified:
            raise ValueError("F6-A does not verify a physical board")


def inspect_claimed_board(machine: str | None,
                          compatible: str | None) -> BoardInspection:
    """Conservatively match published family strings; neither is a proof."""
    if (machine is not None and type(machine) is not str
            or compatible is not None and type(compatible) is not str):
        raise ValueError("board metadata must be text or unknown")
    families = {
        "microduck-zero3": "radxa,zero3w-aic8800ds2",
        "microduck-beta": "pollen,microduck-beta",
    }
    if machine is None or compatible is None:
        return BoardInspection("unknown", machine, compatible)
    if (machine not in families or compatible != families[machine]):
        return BoardInspection("mismatch_or_unsupported", machine, compatible)
    return BoardInspection("claimed_family_match", machine, compatible)


@dataclass(frozen=True)
class StorageInspection:
    """A positive result is a CANDIDATE, not permission to use eMMC."""

    status: str
    sqlite_candidate: str | None = None
    sqlite_selected: str = VOLATILE_SQLITE
    hardware_validated: bool = False

    def __post_init__(self) -> None:
        if (self.hardware_validated
                or self.sqlite_selected != VOLATILE_SQLITE
                or (self.sqlite_candidate is not None
                    and self.sqlite_candidate != SQLITE_PATH_CANDIDATE)):
            raise ValueError("F6-A cannot enable persistent hardware writes")


def _safe_partlabel_device(partlabel_device: str | None) -> bool:
    # This string is evidence passed by a future independent PARTLABEL=data
    # lookup, NOT a trusted credential or a direct access capability.
    return bool(
        type(partlabel_device) is str
        and re.fullmatch(r"/dev/[A-Za-z0-9_./-]{1,160}", partlabel_device)
        and ".." not in partlabel_device.split("/")
        and "//" not in partlabel_device
        and not partlabel_device.endswith("/")
    )


def inspect_data_mount(mountinfo_text: str, *,
                       partlabel_device: str | None = None) -> StorageInspection:
    """Interpret fixture or manually captured mountinfo, NEVER read the host.

    Requires an independent device name reported by PARTLABEL=data lookup.
    Neither this parser nor that claimed name proves the real label, free
    space, write permissions, fs integrity, or the running Yocto revision.
    """
    if type(mountinfo_text) is not str:
        raise TypeError("mountinfo must be bounded text")
    if (len(mountinfo_text) > MAX_MOUNTINFO_CHARS
            or len(mountinfo_text.splitlines()) > MAX_MOUNTINFO_LINES):
        return StorageInspection("oversized_mountinfo")
    if partlabel_device is not None and not _safe_partlabel_device(
            partlabel_device):
        return StorageInspection("invalid_partlabel_claim")

    matches: list[tuple[list[str], list[str]]] = []
    for line in mountinfo_text.splitlines():
        if " - " not in line:
            # Malformed unrelated entries may be ignored. A malformed entry
            # containing the exact target must NOT be accepted.
            if DATA_MOUNT in line.split():
                return StorageInspection("malformed_data_mount")
            continue
        left, sep, right = line.partition(" - ")
        fields = left.split()
        after = right.split()
        if len(fields) > 4 and fields[4] == DATA_MOUNT:
            if len(fields) < 6 or len(after) < 3 or not sep:
                return StorageInspection("malformed_data_mount")
            matches.append((fields, after))
    if not matches:
        return StorageInspection("mount_missing")
    if len(matches) != 1:
        return StorageInspection("ambiguous_mounts")

    fields, after = matches[0]
    fstype, source = after[0], after[1]
    if fields[3] != "/" or fstype != "ext4":
        return StorageInspection("not_data_ext4")
    # Both mount options and superblock options matter: a read-only
    # filesystem may still have a writable-looking mount-option field.
    if ("rw" not in fields[5].split(",")
            or "rw" not in after[2].split(",")):
        return StorageInspection("not_writable_mount")
    if partlabel_device is None:
        return StorageInspection("partlabel_unconfirmed")
    if source != partlabel_device:
        return StorageInspection("source_mismatch")
    # This is a path candidate ONLY. The selected mode remains :memory:
    # until on-robot label, filesystem, permissions and resource checks.
    return StorageInspection("persistent_mount_candidate",
                             sqlite_candidate=SQLITE_PATH_CANDIDATE)


@dataclass(frozen=True)
class EmbeddedPreparation:
    """Static design assessment. Real OEM interfaces remain disconnected."""

    board: BoardInspection
    storage: StorageInspection
    mode: str = "offline_fixture_only"
    pc_required: bool = False
    oem_sockets_contacted: int = 0
    motor_commands_issued: int = 0
    speaker_commands_issued: int = 0
    live_sensor_authenticated: bool = False
    navigation_authorized: bool = False
    installation_authorized: bool = False
    robot_hardware_validated: bool = False

    def __post_init__(self) -> None:
        if (self.mode != "offline_fixture_only" or self.pc_required
                or self.oem_sockets_contacted != 0
                or self.motor_commands_issued != 0
                or self.speaker_commands_issued != 0
                or self.live_sensor_authenticated
                or self.navigation_authorized
                or self.installation_authorized
                or self.robot_hardware_validated):
            raise ValueError("F6-A is only a read-only, offline plan")


def inspect_embedded_preparation(*, machine: str | None = None,
        compatible: str | None = None, mountinfo_text: str = "",
        partlabel_device: str | None = None) -> EmbeddedPreparation:
    return EmbeddedPreparation(
        inspect_claimed_board(machine, compatible),
        inspect_data_mount(mountinfo_text,
                           partlabel_device=partlabel_device),
    )


def oem_manifest() -> dict[str, object]:
    """Documented OEM routes, not a connection attempt or installation."""
    return {
        "oem_daemon_revision_pinned": PINNED_OEM_REVISION,
        "oem_api_version_documented": OEM_API_VERSION,
        "yocto_source_snapshot": YOCTO_SNAPSHOT_REVISION,
        "interfaces": tuple({
            "service": i.owner,
            "socket": i.socket,
            "documented_read_methods": i.documented_read_methods,
            "implemented_read_methods": i.implemented_read_methods,
            "connected": False,
            "actuator_access_enabled": False,
        } for i in OEM_INTERFACES),
        "offline_functions_fixture_only": OFFLINE_FUNCTIONS,
        "optional_pc_only": OPTIONAL_PC_ONLY,
        "not_implemented_on_hardware": NOT_IMPLEMENTED_ON_HARDWARE,
        "persisted_storage_root_conditional": DATA_MOUNT,
        "hardware_validated": False,
    }
