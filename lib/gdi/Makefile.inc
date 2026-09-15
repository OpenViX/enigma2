noinst_LIBRARIES += gdi/libenigma_gdi.a

gdi_libenigma_gdi_a_CXXFLAGS = $(LIBSDL_CFLAGS)

gdi_libenigma_gdi_a_SOURCES = \
	gdi/accel.cpp \
	gdi/bcm.cpp \
	gdi/color.cpp \
	gdi/compositing.cpp \
	gdi/drawing.cpp \
	gdi/epng.cpp \
	gdi/erect.cpp \
	gdi/fb.cpp \
	gdi/fblcd.cpp \
	gdi/font.cpp \
	gdi/font_arabic.cpp \
	gdi/gfont.cpp \
	gdi/gfont_atlas.cpp \
	gdi/glcddc.cpp \
	gdi/gmaindc.cpp \
	gdi/gpixmap.cpp \
	gdi/grc.cpp \
	gdi/lcd.cpp \
	gdi/picexif.cpp \
	gdi/picload.cpp \
	gdi/pixmapcache.cpp \
	gdi/region.cpp

gdiincludedir = $(pkgincludedir)/lib/gdi
gdiinclude_HEADERS = \
	gdi/accel.h \
	gdi/color.h \
	gdi/compositing.h \
	gdi/drawing.h \
	gdi/epng.h \
	gdi/epoint.h \
	gdi/erect.h \
	gdi/esize.h \
	gdi/fb.h \
	gdi/fblcd.h \
	gdi/font.h \
	gdi/gfont.h \
	gdi/gfont_atlas.h \
	gdi/glcddc.h \
	gdi/gpixmap.h \
	gdi/grc.h \
	gdi/lcd.h \
	gdi/picexif.h \
	gdi/picload.h \
	gdi/pixmapcache.h \
	gdi/region.h

if HAVE_EGL
gdi_libenigma_gdi_a_SOURCES += \
	gdi/egl/egl_config.cpp \
	gdi/egl/egl_init.cpp \
	gdi/egl/gegldc.cpp \
	gdi/egl/gles_version.cpp \
	gdi/egl/gtexture_manager.cpp \
	gdi/egl/shader/gadvanced_shader.cpp \
	gdi/egl/shader/gshader.cpp \
	gdi/egl/shader/gtext_shader.cpp \
	gdi/egl/shader/gtexture_shader.cpp
gdiinclude_HEADERS += \
	gdi/egl/egl_config.h \
	gdi/egl/gegldc.h \
	gdi/egl/gles_version.h \
	gdi/egl/gtexture_manager.h \
	gdi/egl/inative_window_provider.h \
	gdi/egl/shader/gadvanced_shader.h \
	gdi/egl/shader/gshader.h \
	gdi/egl/shader/gtext_shader.h \
	gdi/egl/shader/gtexture_shader.h
endif

if HAVE_DREAMBOX_EGL
gdi_libenigma_gdi_a_SOURCES += \
	gdi/egl/platform/dreambox/dreambox_window_provider.cpp
gdiinclude_HEADERS += \
	gdi/egl/platform/dreambox/dreambox_window_provider.h
endif

# gMainDC is a strict singleton (see gmaindc.cpp: ASSERT(m_instance == 0) in its
# constructor). gEGLDC is itself a gMainDC, registered via its own AutoInit in
# gdi/egl/egl_init.cpp, so when EGL is enabled it must be the ONLY gMainDC this
# binary constructs - building gfbdc.cpp/sdl.cpp alongside it double-constructs
# the singleton and aborts at startup.
if HAVE_EGL
else
if HAVE_LIBSDL
gdi_libenigma_gdi_a_SOURCES += \
	gdi/sdl.cpp \
	gdi/sdl.h
else
gdi_libenigma_gdi_a_SOURCES += \
	gdi/gfbdc.cpp \
	gdi/gfbdc.h
endif
endif
