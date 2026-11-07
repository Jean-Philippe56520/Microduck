"""Opt-in diagnostic hook for the pinned MuJoCo body process; never OEM."""
import os
if os.environ.get("KWIPI_B2_INSTRUMENT") == "1":
    from experiments.sim1db2_instrument import install
    install()
