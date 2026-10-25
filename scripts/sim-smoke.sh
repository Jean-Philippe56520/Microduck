#!/bin/sh
# Read-only MuJoCo Companion smoke test. Run from a checked-out Git repository.
# DUCK_SIM_DEP_MODE=runtime installs only the official body-server dependencies,
# which is useful on headless CI runners; default full uses the RL uv.lock.
# Does not enable movements from the autonomous brain; official duck-sim may
# move its own simulated robot to stand when started.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
MODE=${1:-check}
SIM="$ROOT/upstream/microduck/scripts/duck-sim"
export DUCK_SIM_RL="$ROOT/upstream/microduck_rl"
export DUCK_SIM_STATE="${DUCK_SIM_STATE:-$HOME/.cache/duck-sim-companion}"
export DUCK_SIM_PORT="${DUCK_SIM_PORT:-17801}"
export DUCK_SIM_FRAME_PORT="${DUCK_SIM_FRAME_PORT:-17901}"
export DUCK_SIM_DUCKS=1
export DUCK_SIM_VIEWER=0
export DUCK_SIM_CAMERAS=
export DUCK_SIM_SCENE=
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

check() {
    missing=0
    for program in git cargo uv python3; do
        if ! command -v "$program" >/dev/null 2>&1; then
            printf 'Missing prerequisite: %s\n' "$program" >&2
            missing=1
        fi
    done
    if ! git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        printf 'Run this script inside a Git checkout of Microduck.\n' >&2
        missing=1
    fi
    if [ "$missing" -ne 0 ]; then
        printf 'Simulator not started. Install prerequisites on Linux/WSL2.\n' >&2
        return 2
    fi
    printf 'Prerequisites present. State dir: %s ; MuJoCo TCP: %s\n' \
        "$DUCK_SIM_STATE" "$DUCK_SIM_PORT"
}

case "$MODE" in
    check)
        check
        exit 0
        ;;
    run)
        check
        ;;
    *)
        printf 'Usage: sh scripts/sim-smoke.sh [check|run]\n' >&2
        exit 2
        ;;
esac

git -C "$ROOT" submodule update --init --recursive
[ -x "$SIM" ] || { printf 'Missing official duck-sim script\n' >&2; exit 2; }
[ -f "$DUCK_SIM_RL/pyproject.toml" ] || {
    printf 'Missing official microduck_rl checkout\n' >&2
    exit 2
}
# The complete RL environment contains training dependencies (including PyTorch).
# For the official headless *body server only*, its imports require just MuJoCo,
# NumPy and ONNX Runtime. Pin versions verified in GitHub Actions smoke run
# 40145369078; this optional runtime mode does not install or modify
# the motor policies, the official daemons, or the simulator's source.
case "${DUCK_SIM_DEP_MODE:-full}" in
    full)
        (
            cd "$DUCK_SIM_RL"
            uv sync --frozen --python 3.12
        )
        ;;
    runtime)
        uv venv --python 3.12 "$DUCK_SIM_RL/.venv"
        uv pip install --python "$DUCK_SIM_RL/.venv/bin/python" \
            'mujoco==3.10.0' 'numpy==2.5.4' 'onnxruntime==1.28.0'
        # The lean environment deliberately skips editable RL-package
        # installation. Python must therefore find its pinned source tree.
        export PYTHONPATH="$DUCK_SIM_RL/src:$PYTHONPATH"
        "$DUCK_SIM_RL/.venv/bin/python" -c \
            'import mjlab_microduck.sim.body_server'
        ;;
    *)
        printf 'Unknown DUCK_SIM_DEP_MODE (use full or runtime)\n' >&2
        exit 2
        ;;
esac

started=0
cleanup() {
    if [ "$started" -eq 1 ]; then
        "$SIM" down || true
    fi
}
trap cleanup EXIT HUP INT TERM
started=1
"$SIM" up
"$SIM" status
"$SIM" ctl health
"$SIM" realtime
python3 -m microduck_companion.sim_probe --state-dir "$DUCK_SIM_STATE"
python3 -m microduck_companion.sim_observer --state-dir "$DUCK_SIM_STATE"
python3 -m microduck_companion.sim_zone_probe --state-dir "$DUCK_SIM_STATE" \
    --rl-root "$DUCK_SIM_RL" --port "$DUCK_SIM_PORT"
# This double-opt-in is valid ONLY for the verified flat-floor simulator.
# On main/manual smoke runs it is disabled; no movement is emitted by default.
if [ "${DUCK_SIM_SHORT_MOVE:-NO}" = YES ]; then
    MICRODUCK_SIM_MOTION_TEST=YES python3 -m microduck_companion.sim_motion_demo \
        --state-dir "$DUCK_SIM_STATE" --rl-root "$DUCK_SIM_RL" \
        --port "$DUCK_SIM_PORT" --enable-once
fi
printf 'Smoke test completed; official simulator is being stopped.\n'
