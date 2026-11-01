SUMMARY = "Kwipi developer-only one-shot read-only OEM health probe"
DESCRIPTION = "No motors, no media, no memory, no network; manually started dev probe."
# Companion source redistribution rights are unresolved. Development candidate only.
LICENSE = "CLOSED"

inherit allarch systemd

FILESEXTRAPATHS:prepend := "${THISDIR}/files:"
SRC_URI = "file://health_probe.py file://kwipi-readonly-probe.service"
S = "${UNPACKDIR}"

RDEPENDS:${PN} += "kwipi-companion python3-core python3-json"

SYSTEMD_PACKAGES = "${PN}"
SYSTEMD_SERVICE:${PN} = "kwipi-readonly-probe.service"
SYSTEMD_AUTO_ENABLE:${PN} = "disable"

do_install() {
    install -d "${D}${libexecdir}/kwipi" "${D}${systemd_system_unitdir}"
    install -m 0644 "${UNPACKDIR}/health_probe.py" "${D}${libexecdir}/kwipi/health_probe.py"
    sed -e "s|@LIBEXECDIR@|${libexecdir}|g" "${UNPACKDIR}/kwipi-readonly-probe.service" > "${D}${systemd_system_unitdir}/kwipi-readonly-probe.service"
    chmod 0644 "${D}${systemd_system_unitdir}/kwipi-readonly-probe.service"
}

FILES:${PN} += "${libexecdir}/kwipi/health_probe.py ${systemd_system_unitdir}/kwipi-readonly-probe.service"
