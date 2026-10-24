#!/bin/sh
# Microduck Companion — audit de ressources en lecture seule
# Aucun login, profil Wi-Fi, image, son, adresse IP ou secret n'est collecté.
# À lancer uniquement avec un accès shell autorisé sur une unité de développement.
set -u
printf '\n=== Microduck resource audit (local) ===\n'
date -u '+UTC: %Y-%m-%d %H:%M:%S' 2>/dev/null || true
printf '\n-- Board and kernel --\n'
uname -sr 2>/dev/null || true
if [ -r /proc/device-tree/model ]; then tr '\000' '\n' < /proc/device-tree/model; fi
if [ -r /proc/device-tree/compatible ]; then
    printf 'device-tree compatible (first entries):\n'
    tr '\000' '\n' < /proc/device-tree/compatible | head -n 3
fi
printf '\n-- Physical and available memory (kB) --\n'
if [ -r /proc/meminfo ]; then
    grep -E '^(MemTotal|MemFree|MemAvailable|Buffers|Cached|SwapTotal|SwapFree|CmaTotal|CmaFree):' /proc/meminfo
fi
printf '\n-- Storage and filesystem capacity --\n'
for mount in / /var/lib/robot /opt/robot; do
    if [ -e "$mount" ]; then
        printf '%s:\n' "$mount"
        df -h "$mount" 2>/dev/null | tail -n 1
    fi
done
printf '\n-- Persistent data subdirectories (sizes may be inaccessible) --\n'
for path in /var/lib/robot /opt/robot/daemon /opt/robot/detector /opt/robot/policies; do
    if [ -d "$path" ]; then du -sh "$path" 2>/dev/null || true; fi
done
printf '\n-- Memory and CPU of running processes (RSS in KiB) --\n'
ps -eo pid,comm,rss,%cpu 2>/dev/null | head -n 28 || true
printf '\n-- Active service RAM (bytes; if accounting enabled) --\n'
if command -v systemctl >/dev/null 2>&1; then
    for unit in robotd mediad tofd btd configd updaterd nfcd; do
        result=$(systemctl show "$unit.service" -p MemoryCurrent --value 2>/dev/null) || result=
        if [ -n "$result" ] && [ "$result" != "[not set]" ]; then
            printf '%s: %s\n' "$unit" "$result"
        fi
    done
fi
printf '\n-- SoC thermal sensors (millidegrees C) --\n'
for p in /sys/class/thermal/thermal_zone*; do
    if [ -r "$p/type" ] && [ -r "$p/temp" ]; then
        printf '%s : %s\n' "$(cat "$p/type")" "$(cat "$p/temp")"
    fi
done
printf '\n-- CPU maximum frequencies (kHz) --\n'
for p in /sys/devices/system/cpu/cpufreq/policy*; do
    if [ -r "$p/scaling_max_freq" ]; then
        printf '%s scaling_max=%s' "$p" "$(cat "$p/scaling_max_freq")"
        if [ -r "$p/cpuinfo_max_freq" ]; then
            printf ' cpuinfo_max=%s' "$(cat "$p/cpuinfo_max_freq")"
        fi
        printf '\n'
    fi
done
printf '\nEND. Run once at idle, once with camera/detector, and once with allowed movement.\n'
printf 'Keep private serial numbers, identity, network settings and personal data out of shared logs.\n'
