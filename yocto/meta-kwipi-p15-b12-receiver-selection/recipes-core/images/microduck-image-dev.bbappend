# P15-B18: opt-in, DEV-only selection of the reviewed four B13-B16 source modules.
# No service, executable enable flag, camera, model, account or motor permission.
# Existing rootfs B10 remains a distinct, unmodified historical artifact.
IMAGE_INSTALL:append = " kwipi-b12-receiver"
