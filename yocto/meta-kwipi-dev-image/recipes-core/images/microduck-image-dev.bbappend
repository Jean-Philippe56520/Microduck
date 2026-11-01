# PER-P14C: only the official microduck-image-dev.bb (no recipe version suffix).
# This layer is optional, and deliberately never matches microduck-image.bb.
# No daemon service, model, motor privileges or production package.
IMAGE_INSTALL:append = " kwipi-companion"
