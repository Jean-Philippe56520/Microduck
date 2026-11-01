# P15-B9: isolated, locked service identity for the optional DEV image only.
# Preserve OEM microduck operator and the shipping image untouched.
# The OEM image already inherits extrausers. No service is enabled here.
EXTRA_USERS_PARAMS:append = " groupadd -r kwipi; useradd -r -g kwipi -M -s /sbin/nologin -p '!' kwipi;"
