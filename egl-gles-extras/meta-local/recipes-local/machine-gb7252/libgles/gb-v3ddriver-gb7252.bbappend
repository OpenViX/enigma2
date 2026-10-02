do_install:append:openvix() {
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
