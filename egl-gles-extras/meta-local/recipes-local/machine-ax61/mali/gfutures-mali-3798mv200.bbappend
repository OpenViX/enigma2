# gfutures-mali-utgard.inc (ax61 = MACHINE hd61, GFutures) ships only libMali.so (+ the
# libEGL/libGLESv1_CM/libGLESv2 symlinks onto it) and, like the ABCom one for pulse4k, says
# "The driver is missing EGL/GLES headers and pkgconfig files" - so configure's
# PKG_CHECK_MODULES([egl]/[glesv2]) fails. Same Hi3798MV200 + Mali-450 as pulse4k, so stage
# the same HiSilicon SDK headers (see machine-pulse4k/mali/abcom-mali-3798mv200.bbappend).
# Note gfutures ships an older libMali (gfutures-mali-3798mv200-20181201.zip) than ABCom's
# 20210203 one; its EGLNativeWindowType is expected to be the same fbdev_window* but that
# has not been verified against this particular blob.
# Only EGL, GLES, GLES2 and KHR are staged: libMali is GLES 2.0 only (no GLES3 core
# symbols), and configure.ac turns on HAVE_GLES3 whenever GLES3/gl3.h exists.
SRC_URI:append:openvix = " https://source.mynonpublic.com/dags/hisi3798mv200-opengl-20200915.tar.gz;name=headers"
SRC_URI[headers.sha256sum] = "95f4ecd9c90f07075dd24493baa4a440d6140007d33e9238fc37de111ae2c574"

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
