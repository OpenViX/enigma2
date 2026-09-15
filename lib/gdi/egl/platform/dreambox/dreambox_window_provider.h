#pragma once

#include <EGL/dreameglplatform.h>
#include <lib/gdi/egl/inative_window_provider.h>

// EGL native-pixmap provider for Dreambox's VC5/BEGL stack (libvc5dream.so /
// libv3ddriver.so). This platform only implements eglCreatePlatformPixmapSurfaceEXT
// with a struct dmegl_pixmap_handle (see EGL/dreameglplatform.h, shipped by
// Dream Property GmbH in the libvc5dream-dev package) - there is no fbdev_window
// or other native-window surface type here, unlike the Amlogic/Mali-fbdev backend.
//
// Rather than allocating a separate offscreen pixmap and then needing an
// undocumented ioctl to composite it onto the visible display, this provider
// describes the *existing* framebuffer memory (the same one fbClass/gFBDC
// already renders the CPU/2D path into) as a set of pixmaps, one per page
// fbClass::SetMode() actually allocated (typically 3, for triple buffering -
// see fb.cpp). gEGLDC creates one EGLSurface per page and ping-pongs
// rendering between them (see gEGLDC::flip()), panning the display
// (FBIOPAN_DISPLAY, via fbClass::setOffset()) to whichever page a frame just
// finished rendering into.
class DreamboxWindowProvider : public INativeWindowProvider {
private:
	static const int kMaxPages = 3;
	dmegl_pixmap_handle m_pixmaps[kMaxPages];
	int m_page_count;
	int m_height; // page N's scanout line offset is N * m_height (see presentPixmap())
	unsigned long m_page_bytes; // one page's size in bytes (see copyPageContent())

public:
	DreamboxWindowProvider();
	virtual ~DreamboxWindowProvider();

	// INativeWindowProvider
	bool init(int width, int height) override;
	EGLNativeDisplayType getNativeDisplay() override;
	bool usesPixmapSurface() const override { return true; }
	int getPageCount() const override { return m_page_count; }
	void* getNativePixmap(int page) override;
	void presentPixmap(int page) override;
	void copyPageContent(int from, int to) override;
	void cleanup() override;
};
