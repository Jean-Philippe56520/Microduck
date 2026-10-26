#!/bin/sh
# F6-D Microduck: read-only hardware resource SURVEY, not a robot test.
# Never starts vision, moves motors, stops robotd, installs software,
# writes records or queries PC/Qwen. Output is for PRIVATE operator review.
# Run only on a development unit with authorized shell and OEM protections.
set -u

usage() {
    cat <<'HELP'
Microduck F6-D resource survey (read-only, no motion)

  sh scripts/resource-audit.sh --plan
      Show an OFFLINE checklist; no host hardware is queried.
  sh scripts/resource-audit.sh --phase idle --operator-confirmed
      Take one stationary read-only snapshot on an authorized RK3566 dev unit.
  sh scripts/resource-audit.sh --phase vision --operator-confirmed --idle-reviewed --vision-already-enabled
      Take one supervised stationary snapshot. The OEM operator must have
      started vision separately; this script NEVER starts or stops services.
  sh scripts/resource-audit.sh --phase movement
      DENIED by F6-D. Requires independent locomotion and safety validation.

Never treat --operator-confirmed as authentication or hardware certification.
A survey does NOT measure motor 50-Hz deadline misses, battery endurance,
actual power draw, real recognition accuracy or a reliable floor boundary.
Do NOT upload unreviewed logs: board model, device paths and service names
may still be sensitive in your environment.
HELP
}

plan() {
    printf '%s\n' 'F6-D OFFLINE PLAN; NO HARDWARE WAS QUERIED.'
    printf '%s\n' '1. Identify hardware revision, firmware/OEM API and operator-approved access.'
    printf '%s\n' '2. Stationary idle: available RAM, process RSS/CPU, filesystem, thermal, frequency.'
    printf '%s\n' '3. Verify the data PARTLABEL mount separately; df on a directory is not proof.'
    printf '%s\n' '4. Review OEM motor control cadence independently; this script cannot read ticks.'
    printf '%s\n' '5. Supervised stationary vision using OEM controls, only after idle review.'
    printf '%s\n' '6. Movement NOT AUTHORIZED by F6-D; reopen only after locomotion and safety.'
    printf '%s\n' 'STOP: missing/uncertain sensor, OEM service unhealthy, reduced memory,'
    printf '%s\n' 'thermal throttling, CPU-frequency collapse or any motor deadline miss.'
    printf '%s\n' 'Compare each stage against the same actual device; no guessed limits.'
    printf '%s\n' 'No systemd change, data write, model execution, motion or Internet access.'
}

if [ "$#" -eq 1 ] && [ "$1" = "--plan" ]; then
    plan
    exit 0
fi

if [ "$#" -eq 0 ]; then
    usage >&2
    exit 2
fi

phase=
confirmed=no
vision_confirmed=no
idle_reviewed=no
while [ "$#" -gt 0 ]; do
    case "$1" in
        --phase)
            if [ "$#" -lt 2 ] || [ -n "$phase" ]; then
                usage >&2
                exit 2
            fi
            phase=$2
            shift 2
            ;;
        --operator-confirmed)
            if [ "$confirmed" = yes ]; then exit 2; fi
            confirmed=yes
            shift
            ;;
        --vision-already-enabled)
            if [ "$vision_confirmed" = yes ]; then exit 2; fi
            vision_confirmed=yes
            shift
            ;;
        --idle-reviewed)
            if [ "$idle_reviewed" = yes ]; then exit 2; fi
            idle_reviewed=yes
            shift
            ;;
        *)
            usage >&2
            exit 2
            ;;
    esac
done

case "$phase" in
    movement|move|walking)
        printf '%s\n' 'F6-D BLOCKED: never start or audit live movement in this phase.' >&2
        exit 3
        ;;
    idle|vision) ;;
    *)
        usage >&2
        exit 2
        ;;
esac
if [ "$confirmed" != yes ]; then
    printf '%s\n' 'F6-D BLOCKED: explicit authorized-development-unit confirmation required.' >&2
    exit 3
fi
if [ "$phase" = vision ] && { [ "$vision_confirmed" != yes ] || [ "$idle_reviewed" != yes ]; }; then
    printf '%s\n' 'F6-D BLOCKED: reviewed idle baseline and independent supervised vision required.' >&2
    exit 3
fi
if [ "$phase" = idle ] && { [ "$vision_confirmed" = yes ] || [ "$idle_reviewed" = yes ]; }; then
    printf '%s\n' 'F6-D BLOCKED: vision-related claim conflicts with idle phase.' >&2
    exit 3
fi

# A deliberate fail-closed platform gate. This is only a plausibility test:
# architecture and device-tree strings DO NOT authenticate a genuine robot.
architecture=$(uname -m 2>/dev/null) || architecture=
case "$architecture" in
    aarch64|arm64) ;;
    *)
        printf '%s\n' 'F6-D BLOCKED: ARM64 RK3566 development unit not detected.' >&2
        exit 3
        ;;
esac
if [ ! -r /proc/device-tree/compatible ]; then
    printf '%s\n' 'F6-D BLOCKED: unreadable device-tree compatible list.' >&2
    exit 3
fi
if ! tr '\000' '\n' </proc/device-tree/compatible | grep -qi 'rk3566'; then
    printf '%s\n' 'F6-D BLOCKED: device-tree did not declare RK3566.' >&2
    exit 3
fi

# ONE snapshot only; neither temperature nor CPU sampling is continuous.
printf '\nF6D_SURVEY_ONLY=YES\n'
printf 'PHASE=%s\n' "$phase"
printf 'PLATFORM_GATE=rk3566_claim_only_not_authenticated\n'
printf 'ROBOT_HARDWARE_VALIDATED=NO\n'
printf 'MOTION_AUTHORIZED=NO\n'
printf 'OPERATOR_CLAIM_NOT_AUTHENTICATION=YES\n'
printf 'IDLE_REVIEW_OPERATOR_CLAIM=%s\n' "$idle_reviewed"
printf 'UTC='
date -u '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || printf 'unavailable\n'

printf '\n-- Architecture and board model (no serial number) --\n'
uname -sr 2>/dev/null || true
if [ -r /proc/device-tree/model ]; then
    tr '\000' '\n' </proc/device-tree/model | head -n 1
fi
printf '%s\n' 'Compatible entries declaring RK3566:'
tr '\000' '\n' </proc/device-tree/compatible | grep -i 'rk3566' | head -n 2

printf '\n-- Available physical memory (kB; not a safe deployment budget) --\n'
if [ -r /proc/meminfo ]; then
    grep -E '^(MemTotal|MemFree|MemAvailable|SwapTotal|SwapFree|CmaTotal|CmaFree):' /proc/meminfo
else
    printf '%s\n' 'MEMINFO=unavailable'
fi

printf '\n-- Filesystems (df is NOT persistent-mount proof) --\n'
for mountpoint in / /var/lib/robot /opt/robot; do
    if [ -d "$mountpoint" ]; then
        printf 'DF_PATH=%s\n' "$mountpoint"
        df -P -k "$mountpoint" 2>/dev/null | tail -n 1 || true
    fi
done
printf '\n-- Exact data mount evidence from /proc/self/mountinfo --\n'
if [ -r /proc/self/mountinfo ]; then
    awk '
      $5 == "/var/lib/robot" {
          found++
          for (i = 1; i <= NF; i++) if ($i == "-") {
              printf "DATA_MOUNT=listed mount_opts=%s fstype=%s source=%s super_opts=%s\n",
                  $6, $(i+1), $(i+2), $(i+3)
              break
          }
      }
      END {
          if (found != 1)
              printf "DATA_MOUNT=unknown_or_ambiguous count=%d\n", found
      }
    ' /proc/self/mountinfo
else
    printf '%s\n' 'DATA_MOUNT=unavailable'
fi
if [ -e /dev/disk/by-partlabel/data ]; then
    printf '%s\n' 'DATA_PARTLABEL_SYMLINK=present_not_verified'
else
    printf '%s\n' 'DATA_PARTLABEL_SYMLINK=missing'
fi
printf '%s\n' 'PERSISTENT_STORAGE_VALIDATED=NO (requires separate mount/label/fs/permission review)'

printf '\n-- OEM-related processes only (RSS KiB, CPU process-average) --\n'
if command -v ps >/dev/null 2>&1 && command -v awk >/dev/null 2>&1; then
    ps -eo comm,rss,%cpu 2>/dev/null | awk '
      NR == 1 || $1 ~ /^(robotd|mediad|tofd|configd|duck-detect|companion|python3)$/ {print}
    ' || true
else
    printf '%s\n' 'PS=unavailable'
fi

printf '\n-- OEM service state and optional MemoryCurrent (bytes) --\n'
if command -v systemctl >/dev/null 2>&1; then
    for unit in robotd mediad tofd; do
        status=$(systemctl show "$unit.service" -p ActiveState --value 2>/dev/null) || status=
        memory=$(systemctl show "$unit.service" -p MemoryCurrent --value 2>/dev/null) || memory=
        [ -n "$status" ] || status=unknown
        [ -n "$memory" ] || memory=unknown
        printf 'OEM_SERVICE=%s status=%s MemoryCurrent_bytes=%s\n' \
            "$unit" "$status" "$memory"
    done
else
    printf '%s\n' 'SYSTEMCTL=unavailable'
fi

printf '\n-- SoC thermal zones (millidegrees C; no dynamic stop capability) --\n'
for path in /sys/class/thermal/thermal_zone*; do
    if [ -r "$path/type" ] && [ -r "$path/temp" ]; then
        printf 'THERMAL_ZONE=%s temp_mC=%s\n' \
            "$(cat "$path/type" 2>/dev/null)" "$(cat "$path/temp" 2>/dev/null)"
    fi
done

printf '\n-- CPU operating/max frequency (kHz) --\n'
for path in /sys/devices/system/cpu/cpufreq/policy*; do
    if [ -r "$path/scaling_cur_freq" ]; then
        printf 'CPU_POLICY=%s current_kHz=%s' "$path" "$(cat "$path/scaling_cur_freq" 2>/dev/null)"
        if [ -r "$path/scaling_max_freq" ]; then
            printf ' permitted_max_kHz=%s' "$(cat "$path/scaling_max_freq" 2>/dev/null)"
        fi
        printf '\n'
    fi
done

printf '\nMOTOR_50HZ_DEADLINE_MISSES=NOT_MEASURED\n'
printf 'SENSOR_FRAME_LATENCY=NOT_MEASURED\n'
printf 'BATTERY_POWER_AND_ENDURANCE=NOT_MEASURED\n'
printf 'F6D_RESULT=SNAPSHOT_ONLY_MANUAL_REVIEW_REQUIRED\n'
printf '%s\n' 'Do not claim hardware validation from this snapshot. Review logs privately.'
