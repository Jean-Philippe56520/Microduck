# PER-P15A: target only the OEM DEV image, never microduck-image shipping.
# The unit has no [Install] section and is not started at boot.
IMAGE_INSTALL:append = " kwipi-readonly-probe"
