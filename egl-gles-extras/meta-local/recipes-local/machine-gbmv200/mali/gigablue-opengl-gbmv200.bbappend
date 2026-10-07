# gigablue-opengl.inc already stages the EGL/GLES/GLES2/KHR headers (from
# gbmv200-opengl-20180301.tar.gz, byte-identical to Octagon's hisi3798mv200 one, whose
# EGL/eglplatform.h defines EGLNativeWindowType as fbdev_window*) but ships no pkg-config
# files, so configure's PKG_CHECK_MODULES([egl]/[glesv2]) fails. Generate them. No GLES3
# headers are staged.
do_install:append:openvix() {
    for d in EGL GLES GLES2 KHR; do
        install -d ${D}${includedir}/$d
        for f in ${UNPACKDIR}/usr/include/$d/*.h; do
            install -m 0644 $f ${D}${includedir}/$d/
        done
    done

    install -d ${D}${libdir}/pkgconfig
    cat > ${D}${libdir}/pkgconfig/egl.pc <<EOF
prefix=${prefix}
exec_prefix=${exec_prefix}
libdir=${libdir}
includedir=${includedir}

Name: EGL
Description: Mali Utgard fbdev EGL
Version: 1.4
Libs: -L${libdir} -lEGL
Cflags: -I${includedir}
EOF

    cat > ${D}${libdir}/pkgconfig/glesv2.pc <<EOF
prefix=${prefix}
exec_prefix=${exec_prefix}
libdir=${libdir}
includedir=${includedir}

Name: GLESv2
Description: Mali Utgard GLESv2
Version: 2.0
Libs: -L${libdir} -lGLESv2
Cflags: -I${includedir}
EOF
}

FILES:${PN}-dev:append:openvix = " ${libdir}/pkgconfig/egl.pc ${libdir}/pkgconfig/glesv2.pc"
