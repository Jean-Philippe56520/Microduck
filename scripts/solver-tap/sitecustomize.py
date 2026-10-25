"""P0d opt-in startup hook; path is prepended only in the diagnostic CI branch.

For all other Python processes this is a complete no-op. When running in
the exact pinned headless OEM body_server Python process, it installs the
read-only mj_step instrumentation. No upstream source files are changed.
"""
import os

if os.environ.get("MICRODUCK_SIM_SOLVER_TRACE") == "YES":
    from microduck_companion.sim_live_solver_tap import activate_if_exact_body_server
    activate_if_exact_body_server()
