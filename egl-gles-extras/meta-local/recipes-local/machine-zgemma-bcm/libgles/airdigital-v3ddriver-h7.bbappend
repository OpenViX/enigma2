# airdigital-v3ddriver.inc installs libnxpl/libnexus/libv3ddriver and a "nxpl" pkg-config
# module but, like GigaBlue's gb-v3ddriver.inc, no headers and no egl.pc/glesv2.pc ("The driver
# is missing EGL/GLES headers and pkgconfig files"), and DEPENDS has no headers recipe: mesa in
# its DEPENDS never provides the matching ones. This stages the Broadcom Nexus/EGL/GLES headers
# from GigaBlue's gb-nexus-headers.zip (the same unauthenticated zip gb-v3ddriver-headers.bb
# installs; the NXPL window-info struct in its default_nexus.h was checked against this
# driver's libnxpl.so by disassembly, see gbquad_window_provider.h) and generates the pc files.
# The zip also carries the Nexus headers the provider includes (nxclient.h, default_nexus.h).
# NOTE: no libnxclient.so is shipped here, hence HAVE_NXPL_NO_NXCLIENT in configure.ac.
SRC_URI:append:openvix = " https://source.mynonpublic.com/gigablue/v3ddriver/gb-nexus-headers.zip;name=headers"
SRC_URI[headers.sha256sum] = "4cfda443d72ec56965f989b9306c0af6f85cbac55fc6a70b0d081ea605c192aa"

DEPENDS:remove:openvix = "mesa"

do_install:append:openvix() {
    install -d ${D}${includedir}
    for f in ${UNPACKDIR}/*.h; do
        install -m 0644 $f ${D}${includedir}/
    done
    for d in EGL GLES GLES2 GLES3 KHR; do
        install -d ${D}${includedir}/$d
        for f in ${UNPACKDIR}/$d/*.h; do
            install -m 0644 $f ${D}${includedir}/$d/
        done
    done

    cat > ${D}${libdir}/pkgconfig/egl.pc <<EOF
prefix=${prefix}
exec_prefix=${exec_prefix}
libdir=${libdir}
includedir=${includedir}

Name: EGL
Description: Broadcom V3D EGL
Version: ${PV}
Libs: -L${libdir} -lEGL
Cflags: -I${includedir}
EOF

    cat > ${D}${libdir}/pkgconfig/glesv2.pc <<EOF
prefix=${prefix}
exec_prefix=${exec_prefix}
libdir=${libdir}
includedir=${includedir}

Name: GLESv2
Description: Broadcom V3D GLESv2
Version: ${PV}
Libs: -L${libdir} -lGLESv2
Cflags: -I${includedir}
EOF
}

FILES:${PN}-dev:append:openvix = " ${libdir}/pkgconfig/egl.pc ${libdir}/pkgconfig/glesv2.pc"
