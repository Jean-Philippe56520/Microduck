"""Explicit, interpreter-scoped hook for B2-E1; does not touch other Python."""
import os
import sys
if (os.environ.get("KWIPI_B2E1_INSTRUMENT") == "1"
        and os.path.realpath(sys.executable)
            == os.path.realpath(os.environ.get("KWIPI_B2E1_PYTHON", "/nonexistent"))):
    from experiments.sim1db2e1_instrument import install
    install()
