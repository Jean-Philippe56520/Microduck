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
# SIM-VIS-A1 is the single opt-in exception to the historic blind smoke.
# It reuses the OEM apartment, frame socket, camera and ToF; no motor trial.
if [ "${DUCK_SIM_VIS_A1:-NO}" = YES ]; then
    export DUCK_SIM_CAMERAS=a
    export DUCK_SIM_SCENE=apartment
    export MUJOCO_GL=osmesa
else
    export DUCK_SIM_CAMERAS=
    export DUCK_SIM_SCENE=
fi
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

# A1 only measures simulated images/ToF. Never combine with motor trials.
if [ "${DUCK_SIM_VIS_A1:-NO}" = YES ]; then
    for motion_flag in "${DUCK_SIM_SHORT_MOVE:-NO}" \
                       "${DUCK_SIM_WALK_TRIAL:-NO}" \
                       "${DUCK_SIM_WALK_COMPARE:-NO}" \
                       "${DUCK_SIM_POLICY_PAIR:-NO}" \
                       "${DUCK_SIM_VX_ONSET:-NO}" \
                       "${DUCK_SIM_SIM_E1:-NO}" \
                       "${DUCK_SIM_X2C_ACCEPTANCE:-NO}" \
                       "${DUCK_SIM_SOLVER_TRACE:-NO}" \
                       "${DUCK_SIM_ACTUATOR_AUDIT:-NO}"; do
        if [ "$motion_flag" = YES ]; then
            printf 'SIM-VIS-A1 refuses mixed motor or trace experiments.\\n' >&2
            exit 2
        fi
    done
    [ -n "${DUCK_SIM_VIS_MODEL:-}" ] || {
        printf 'SIM-VIS-A1 requires the approved public model path.\\n' >&2
        exit 2
    }
fi

# X2-C must never coexist with any opt-in test that commands locomotion.
# An X2-C run only measures read-only OEM telemetry and local SQLite.
if [ "${DUCK_SIM_X2C_ACCEPTANCE:-NO}" = YES ]; then
    for motion_flag in "${DUCK_SIM_SHORT_MOVE:-NO}" \
                       "${DUCK_SIM_WALK_COMPARE:-NO}" \
                       "${DUCK_SIM_WALK_TRIAL:-NO}" \
                       "${DUCK_SIM_POLICY_PAIR:-NO}" \
                       "${DUCK_SIM_VX_ONSET:-NO}"; do
        if [ "$motion_flag" = YES ]; then
            printf 'X2-C refuses simultaneous simulated motor experiments.\\n' >&2
            exit 2
        fi
    done
fi

# SIM-E1 deliberately reuses exactly one existing J2e bounded motor trial.
# The physical robot, other motion experiments, and X2-C are all excluded.
if [ "${DUCK_SIM_SIM_E1:-NO}" = YES ]; then
    for incompatible in "${DUCK_SIM_X2C_ACCEPTANCE:-NO}" \
                        "${DUCK_SIM_SHORT_MOVE:-NO}" \
                        "${DUCK_SIM_WALK_COMPARE:-NO}" \
                        "${DUCK_SIM_WALK_TRIAL:-NO}" \
                        "${DUCK_SIM_POLICY_PAIR:-NO}" \
                        "${DUCK_SIM_VX_ONSET:-NO}" \
                        "${DUCK_SIM_SOLVER_TRACE:-NO}" \
                        "${DUCK_SIM_ACTUATOR_AUDIT:-NO}"; do
        if [ "$incompatible" = YES ]; then
            printf 'SIM-E1 refuses other simulated experiments.\\n' >&2
            exit 2
        fi
    done
fi

# Historical E2H contact evidence is now evaluated only from stopped,
# SHA-256-pinned archives. A live tap writer is not an immutable source.
# Refuse BEFORE launching any simulated motion, even on an old branch.
if [ "${DUCK_SIM_E2H_CONTACT:-NO}" = YES ]; then
    printf "SIM-E2H live audit retired: use the offline archived evidence workflow.\n" >&2
    exit 2
fi
# SIM-E2G must be mutually exclusive with every other motion experiment.
# Never permit an arbitrary local caller to combine J2e with the onset probe.
if [ "${DUCK_SIM_VX_ONSET:-NO}" = YES ]; then
    for incompatible in "${DUCK_SIM_POLICY_PAIR:-NO}" \
                        "${DUCK_SIM_SHORT_MOVE:-NO}" \
                        "${DUCK_SIM_WALK_TRIAL:-NO}" \
                        "${DUCK_SIM_WALK_COMPARE:-NO}" \
                        "${DUCK_SIM_ACTUATOR_AUDIT:-NO}" \
                        "${DUCK_SIM_SIM_E1:-NO}" \
                        "${DUCK_SIM_X2C_ACCEPTANCE:-NO}"; do
        if [ "$incompatible" = YES ]; then
            printf "SIM-E2G refuses concurrent simulated motor experiments.\\n" >&2
            exit 2
        fi
    done
fi

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
        if [ "${DUCK_SIM_VIS_A1:-NO}" = YES ]; then
            # Only the optional simulated-camera smoke needs JPEG + OSMesa.
            uv pip install --python "$DUCK_SIM_RL/.venv/bin/python" \
                'Pillow==11.3.0' 'PyOpenGL==3.1.10'
        fi
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
    if [ "${DUCK_SIM_WALK_COMPARE:-NO}" != YES ] && \
       [ "${DUCK_SIM_E2H_CONTACT:-NO}" != YES ]; then
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
# SIM-VIS-A1b: direct official MuJoCo FrameServer optical control.
# Independent of mediad: 1 rendered frame with NO real-time / IPC claim.
# It is recorded before the OEM media.frame integration check, which must
# still FAIL if the real mediad does not provide its socket.
if [ "${DUCK_SIM_VIS_A1:-NO}" = YES ]; then
    "$DUCK_SIM_RL/.venv/bin/python" -m microduck_companion.sim_visual_direct \
        --camera-port "$DUCK_SIM_FRAME_PORT" \
        --scene-path "$DUCK_SIM_RL/src/mjlab_microduck/robot/microduck/apartment.xml" \
        --model-path "$DUCK_SIM_VIS_MODEL" \
        --output "$DUCK_SIM_STATE/sim-visual-a1b.json" \
        --authorize-sim-render-only
fi

# SIM-VIS-A1: one source-labelled camera/ToF/Yolox diagnostic, no media archived.
if [ "${DUCK_SIM_VIS_A1:-NO}" = YES ]; then
    "$DUCK_SIM_RL/.venv/bin/python" -m microduck_companion.sim_visual_a1 \
        --state-dir "$DUCK_SIM_STATE" \
        --scene-path "$DUCK_SIM_RL/src/mjlab_microduck/robot/microduck/apartment.xml" \
        --model-path "$DUCK_SIM_VIS_MODEL" \
        --output "$DUCK_SIM_STATE/sim-visual-a1.json" \
        --authorize-simulated-snapshot
fi
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
# X2-C: independent real-daemon runs, one NEW shared database. Preserve
# only concise, privacy-free reports (never audio, images or ToF 8x8 grids).
# This is explicitly opt-in on the dedicated GitHub simulator branch.
if [ "${DUCK_SIM_X2C_ACCEPTANCE:-NO}" = YES ]; then
    rm -f "$DUCK_SIM_STATE/x2c-passive.sqlite3" \
          "$DUCK_SIM_STATE/x2c-passive.sqlite3-wal" \
          "$DUCK_SIM_STATE/x2c-passive.sqlite3-shm" \
          "$DUCK_SIM_STATE/x2c-passive-session-a.json" \
          "$DUCK_SIM_STATE/x2c-passive-session-b.json" \
          "$DUCK_SIM_STATE/x2c-acceptance.json"
    python3 -m microduck_companion.sim_passive_cycles \
        --state-dir "$DUCK_SIM_STATE" \
        --database "$DUCK_SIM_STATE/x2c-passive.sqlite3" \
        --session x2c-session-a --cycles 3 --interval 0.6 \
        --output "$DUCK_SIM_STATE/x2c-passive-session-a.json"
    python3 -m microduck_companion.sim_passive_cycles \
        --state-dir "$DUCK_SIM_STATE" \
        --database "$DUCK_SIM_STATE/x2c-passive.sqlite3" \
        --session x2c-session-b --cycles 3 --interval 0.6 \
        --output "$DUCK_SIM_STATE/x2c-passive-session-b.json"
    python3 -m microduck_companion.sim_x2c_acceptance \
        --repo-root "$ROOT" \
        --database "$DUCK_SIM_STATE/x2c-passive.sqlite3" \
        --first "$DUCK_SIM_STATE/x2c-passive-session-a.json" \
        --second "$DUCK_SIM_STATE/x2c-passive-session-b.json" \
        --output "$DUCK_SIM_STATE/x2c-acceptance.json"
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

# SIM-E1: one and only one existing J2e trial with evidence in the same
# SQLite and a counterfactual cognitive comparison; no second motor action.
if [ "${DUCK_SIM_SIM_E1:-NO}" = YES ]; then
    rm -f "$DUCK_SIM_STATE/sim-e1.sqlite3" \
          "$DUCK_SIM_STATE/sim-e1.sqlite3-wal" \
          "$DUCK_SIM_STATE/sim-e1.sqlite3-shm" \
          "$DUCK_SIM_STATE/sim-e1-report.json"
    MICRODUCK_SIM_E1=YES python3 -m microduck_companion.sim_e1_active_experience \
        --state-dir "$DUCK_SIM_STATE" --rl-root "$DUCK_SIM_RL" \
        --database "$DUCK_SIM_STATE/sim-e1.sqlite3" \
        --output "$DUCK_SIM_STATE/sim-e1-report.json" \
        --port "$DUCK_SIM_PORT" --enable-once
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
# after the existing bounded P0b trial returned and confirmed robot.stop.
# E2H uses its own E2G simulator-clock bracket, never P0b replay.
if [ "${DUCK_SIM_SOLVER_TRACE:-NO}" = YES ] && \
   [ "${DUCK_SIM_WALK_COMPARE:-NO}" = YES ]; then
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
# P0i: ONE fixed J2e motor trial on each of TWO fresh official simulator
# boots. This branch-only experiment never patches OEM files, never changes
# safety tuning, and never sends actuator targets directly. The upstream
# robotd remains the only motor authority, and the existing J2e stop/deadman
# verification is reused on both arms. No subsequent automatic retry.
if [ "${DUCK_SIM_POLICY_PAIR:-NO}" = YES ]; then
    # Fresh files from a failed earlier job must never count as evidence.
    rm -f "$DUCK_SIM_STATE/p0i-alpha.json" \
          "$DUCK_SIM_STATE/p0i-velstand.json" \
          "$DUCK_SIM_STATE/p0i-comparison.json" \
          "$DUCK_SIM_STATE/p0i-alpha.sqlite3" \
          "$DUCK_SIM_STATE/p0i-velstand.sqlite3"
    # Arm A is the alpha pair configured by the pinned duck-sim launcher.
    MICRODUCK_SIM_P0I=YES python3 -m microduck_companion.sim_policy_pair \
        --arm alpha --enable-once \
        --state-dir "$DUCK_SIM_STATE" \
        --robot-root "$ROOT/upstream/microduck" \
        --rl-root "$DUCK_SIM_RL" \
        --memory "$DUCK_SIM_STATE/p0i-alpha.sqlite3" \
        --output "$DUCK_SIM_STATE/p0i-alpha.json"

    # Stop ALL OEM services and boot a fresh robot (new body_server PID,
    # simulator time, model sessions and SQLite); repeat NO A trial.
    "$SIM" down
    "$SIM" up
    "$SIM" status
    "$SIM" realtime

    # Only the official robotctl API changes policy slots, not the motors or
    # safety configuration. duck-sim clones its robotd.toml TEMPLATE into
    # the active robotd-duck-a.toml used by the daemon (see OEM --params). Both commands must be accepted and reflected in
    # the live robotd policy report before P0i permits any movement.
    "$SIM" ctl policy --file "$DUCK_SIM_STATE/robotd-duck-a.toml" \
        load walk "$DUCK_SIM_STATE/policies/current/velstand.onnx"
    "$SIM" ctl policy --file "$DUCK_SIM_STATE/robotd-duck-a.toml" \
        load stand none
    sleep 3
    "$SIM" ctl health

    MICRODUCK_SIM_P0I=YES python3 -m microduck_companion.sim_policy_pair \
        --arm velstand --enable-once \
        --state-dir "$DUCK_SIM_STATE" \
        --robot-root "$ROOT/upstream/microduck" \
        --rl-root "$DUCK_SIM_RL" \
        --memory "$DUCK_SIM_STATE/p0i-velstand.sqlite3" \
        --output "$DUCK_SIM_STATE/p0i-velstand.json"

    # Refuse mismatched model identities, same PID, missing stop or absent
    # telemetry. Two measurements remain preliminary, not proof of gait.
    python3 -m microduck_companion.sim_policy_pair --compare \
        --alpha-json "$DUCK_SIM_STATE/p0i-alpha.json" \
        --velstand-json "$DUCK_SIM_STATE/p0i-velstand.json" \
        --output "$DUCK_SIM_STATE/p0i-comparison.json"
fi
# SIM-E2G: exactly ONE higher-speed on-set trial, using the same J2e
# preflight/stop envelope, but with 12 (not 24) ticks to preserve clearance.
# The alpha policies and question derive from
# the independent OEM community report of a slow-speed start threshold (#59).
# No OEM source, model, gain, deadman, policy or physical robot is modified.
if [ "${DUCK_SIM_VX_ONSET:-NO}" = YES ]; then
    # Fail if a previous/mutated report could be mistaken for this run.
    rm -f "$DUCK_SIM_STATE/sim-e2g-report.json" \
          "$DUCK_SIM_STATE/sim-e2g-disposable.sqlite3" \
          "$DUCK_SIM_STATE/sim-e2g-disposable.sqlite3-wal" \
          "$DUCK_SIM_STATE/sim-e2g-disposable.sqlite3-shm"
    MICRODUCK_SIM_E2G=YES python3 -m microduck_companion.sim_e2g_speed_onset \
        --state-dir "$DUCK_SIM_STATE" \
        --robot-root "$ROOT/upstream/microduck" \
        --rl-root "$DUCK_SIM_RL" \
        --memory "$DUCK_SIM_STATE/sim-e2g-disposable.sqlite3" \
        --output "$DUCK_SIM_STATE/sim-e2g-report.json" \
        --enable-once
fi

printf 'Smoke test completed; official simulator is being stopped.\n'
