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

# P0d: external live solver tap. Only explicit opt-in, only on pinned CI branch.
# The startup hook applies solely to the EXACT official body_server process;
# it writes snapshots to a bounded asynchronous queue after native mj_step.
if [ "${DUCK_SIM_SOLVER_TRACE:-NO}" = YES ]; then
    if [ "${DUCK_SIM_WALK_COMPARE:-NO}" != YES ]; then
        printf 'P0d requires the verified single P0b trial.\n' >&2
        exit 2
    fi
    python3 -c 'import os,pathlib; from microduck_companion.sim_flat_zone import verify_flat_scene; verify_flat_scene(pathlib.Path(os.environ["DUCK_SIM_RL"]))'
    rm -f "$DUCK_SIM_STATE/solver-tap.jsonl" "$DUCK_SIM_STATE/solver-analysis.json"
    export MICRODUCK_SIM_SOLVER_TRACE=YES
    if [ "${DUCK_SIM_ACTUATOR_AUDIT:-NO}" = YES ]; then
        export MICRODUCK_SIM_ACTUATOR_AUDIT=YES
        rm -f "$DUCK_SIM_STATE/actuator-gain-audit.json"
    fi
    export PYTHONPATH="$ROOT/scripts/solver-tap:$PYTHONPATH"
fi

if [ "${DUCK_SIM_ACTUATOR_AUDIT:-NO}" = YES ] && \
   [ "${DUCK_SIM_SOLVER_TRACE:-NO}" != YES ]; then
    printf 'P0e actuator audit requires the live solver probe.\n' >&2
    exit 2
fi

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
# P2b: two separate read-only sessions on a single persistent SQLite database.
# Only the P2b simulation branch opts in. No robot.move / robot.stop is issued.
if [ "${DUCK_SIM_PASSIVE_CYCLES:-NO}" = YES ]; then
    rm -f "$DUCK_SIM_STATE/p2b-passive.sqlite3"
    python3 -m microduck_companion.sim_passive_cycles \
        --state-dir "$DUCK_SIM_STATE" \
        --database "$DUCK_SIM_STATE/p2b-passive.sqlite3" \
        --session p2b-session-a --cycles 3 --interval 0.6 \
        --output "$DUCK_SIM_STATE/p2b-passive-session-a.json"
    python3 -m microduck_companion.sim_passive_cycles \
        --state-dir "$DUCK_SIM_STATE" \
        --database "$DUCK_SIM_STATE/p2b-passive.sqlite3" \
        --session p2b-session-b --cycles 3 --interval 0.6 \
        --output "$DUCK_SIM_STATE/p2b-passive-session-b.json"
fi
python3 -m microduck_companion.sim_zone_probe --state-dir "$DUCK_SIM_STATE" \
    --rl-root "$DUCK_SIM_RL" --port "$DUCK_SIM_PORT"
# P0a: passive read-only OEM body joints and robotd policy; NO motor commands.
# Foot contacts and per-joint targets are not available via this protocol.
python3 -m microduck_companion.sim_joint_trace \
    --state-dir "$DUCK_SIM_STATE" --rl-root "$DUCK_SIM_RL" \
    --port "$DUCK_SIM_PORT" --samples 8 --hz 5 \
    --output "$DUCK_SIM_STATE/joint-trace.json"
# P0f: one READ-ONLY policy contract audit in a separate ONNX CPU session.
# It does NOT inspect robotd internal input/state or drive motors.
if [ "${DUCK_SIM_POLICY_AUDIT:-NO}" = YES ]; then
    rm -f "$DUCK_SIM_STATE/policy-contract.json"
    "$DUCK_SIM_RL/.venv/bin/python" -m microduck_companion.sim_policy_contract \
        --robot-root "$ROOT/upstream/microduck" \
        --rl-root "$DUCK_SIM_RL" \
        --state-dir "$DUCK_SIM_STATE" \
        --output "$DUCK_SIM_STATE/policy-contract.json"
fi
# P0h: compare the ACTUAL seeded alpha and velstand ONNX in independent
# read-only CPU sessions. No changed robotd policy, robot.move or mj_step.
if [ "${DUCK_SIM_POLICY_LINEAGE:-NO}" = YES ]; then
    rm -f "$DUCK_SIM_STATE/policy-lineage.json"
    "$DUCK_SIM_RL/.venv/bin/python" -m microduck_companion.sim_policy_lineage \
        --robot-root "$ROOT/upstream/microduck" \
        --rl-root "$DUCK_SIM_RL" \
        --state-dir "$DUCK_SIM_STATE" \
        --output "$DUCK_SIM_STATE/policy-lineage.json"
fi
# P0g: independent temporary XML copies at an identical STAND pose.
# No motor command, no mj_step, no changes to the manufacturer checkout.
if [ "${DUCK_SIM_GEOMETRY_COMPARE:-NO}" = YES ]; then
    rm -f "$DUCK_SIM_STATE/compiled-geometry-variants.json"
    "$DUCK_SIM_RL/.venv/bin/python" -m microduck_companion.sim_geometry_variants \
        --rl-root "$DUCK_SIM_RL" \
        --output "$DUCK_SIM_STATE/compiled-geometry-variants.json"
fi

# This double-opt-in is valid ONLY for the verified flat-floor simulator.
# On main/manual smoke runs it is disabled; no movement is emitted by default.
if [ "${DUCK_SIM_SHORT_MOVE:-NO}" = YES ]; then
    MICRODUCK_SIM_MOTION_TEST=YES python3 -m microduck_companion.sim_motion_demo \
        --state-dir "$DUCK_SIM_STATE" --rl-root "$DUCK_SIM_RL" \
        --port "$DUCK_SIM_PORT" --enable-once
fi
# P0b: opt-in single existing J2e walking trial, with read-only joint trace.
# Never run this branch-only experiment on main or the physical robot.
if [ "${DUCK_SIM_WALK_COMPARE:-NO}" = YES ]; then
    if MICRODUCK_SIM_WALK_COMPARE=YES python3 -m microduck_companion.sim_walk_compare \
        --state-dir "$DUCK_SIM_STATE" --rl-root "$DUCK_SIM_RL" \
        --memory "$DUCK_SIM_STATE/companion-p0b.sqlite" \
        --port "$DUCK_SIM_PORT" --enable-once \
        --output "$DUCK_SIM_STATE/walk-comparison.json"; then
        printf 'P0B_TRANSLATION=OBSERVED_ONCE (not a validated gait)\n'
    else
        status=$?
        if [ "$status" -eq 3 ]; then
            printf 'P0B_TRANSLATION=NOT_MET (negative progress confirmed; stop acknowledged)\n'
        else
            exit "$status"
        fi
    fi
fi
# P0d: analyze the native post-mj_step contact/force/control stream ONLY
# after the existing bounded trial returned and confirmed robot.stop.
if [ "${DUCK_SIM_SOLVER_TRACE:-NO}" = YES ]; then
    sleep 0.3 # allow the non-blocking diagnostic writer to drain
    python3 -m microduck_companion.sim_live_solver_analyze \
        --input "$DUCK_SIM_STATE/solver-tap.jsonl" \
        --p0b "$DUCK_SIM_STATE/walk-comparison.json" \
        --output "$DUCK_SIM_STATE/solver-analysis.json"
fi

# P0e: OFFLINE compare exact pre-step MuJoCo actuator parameters with
# the native solver's force output after J2e's verified robot.stop.
if [ "${DUCK_SIM_ACTUATOR_AUDIT:-NO}" = YES ]; then
    python3 -m microduck_companion.sim_actuator_gain_audit \
        --input "$DUCK_SIM_STATE/solver-tap.jsonl" \
        --p0b "$DUCK_SIM_STATE/walk-comparison.json" \
        --output "$DUCK_SIM_STATE/actuator-gain-audit.json"
fi

# P0c: replay contact geometry OFFLINE from the already stopped P0b trial.
# Uses pinned MJCF in an independent MuJoCo model; no extra motor command.
if [ "${DUCK_SIM_CONTACT_REPLAY:-NO}" = YES ]; then
    "$DUCK_SIM_RL/.venv/bin/python" -m microduck_companion.sim_contact_replay \
        --rl-root "$DUCK_SIM_RL" \
        --input "$DUCK_SIM_STATE/walk-comparison.json" \
        --output "$DUCK_SIM_STATE/contact-replay.json"
fi
# Opt-in J2e: one fixed-speed simulated gait trial with observed SQLite outcome.
# Never run this on a physical robot; safety checks require pinned MuJoCo.
if [ "${DUCK_SIM_WALK_TRIAL:-NO}" = YES ]; then
    # Exit 3 means the experiment completed safely, but measured <1 cm.
    # Treat it as an observed negative outcome, NOT validated locomotion.
    # Errors/stop refusals still fail the integration run.
    if MICRODUCK_SIM_WALK_TEST=YES python3 -m microduck_companion.sim_walk_demo \
        --state-dir "$DUCK_SIM_STATE" --rl-root "$DUCK_SIM_RL" \
        --memory "$DUCK_SIM_STATE/companion-motion.sqlite" \
        --port "$DUCK_SIM_PORT" --enable-once; then
        printf "WALK_TRANSLATION_ACCEPTANCE=OBSERVED_OVER_THRESHOLD\n"
    else
        status=$?
        if [ "$status" -eq 3 ]; then
            printf "WALK_TRANSLATION_ACCEPTANCE=NOT_MET (observed no progress; stop confirmed)\n"
        else
            exit "$status"
        fi
    fi
fi
printf 'Smoke test completed; official simulator is being stopped.\n'
