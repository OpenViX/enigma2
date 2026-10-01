# oe-alliance-core's enigma2.bb only adds libvupl to DEPENDS/RDEPENDS for
# vuduo2/vusolo2/vusolose. The other VU+ models that ship a libvupl package
# (the HAVE_VUPLUS_EGL list in configure.ac) get only virtual/egl +
# virtual/libgles2 = vuplus-libgles, which stages egl.pc/glesv2.pc/nxpl.pc but
# NOT libvupl.pc/eglvuplus.h/libvupl.so - so configure's
# PKG_CHECK_MODULES([VUPL], [libvupl]) fails with "not found in the sysroot".
VUPL_E2EGL_MACHINES = "vuduo4k vuduo4kse vusolo4k vuultimo4k vuuno4k vuuno4kse vuzero4k"

DEPENDS:append:openvix = " ${@bb.utils.contains("MACHINE_FEATURES", "e2egl", bb.utils.contains_any("MACHINE", d.getVar("VUPL_E2EGL_MACHINES"), "libvupl", "", d), "", d)}"
RDEPENDS:${PN}:append:openvix = " ${@bb.utils.contains("MACHINE_FEATURES", "e2egl", bb.utils.contains_any("MACHINE", d.getVar("VUPL_E2EGL_MACHINES"), "libvupl-${MACHINE}", "", d), "", d)}"
