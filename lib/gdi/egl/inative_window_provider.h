#pragma once

#include <EGL/egl.h>

class INativeWindowProvider {
public:
	virtual ~INativeWindowProvider() = default;

	// Initialises the platform-specific windowing system.
	virtual bool init(int width, int height) = 0;

	// Returns the native display (e.g. wl_display for Wayland).
	virtual EGLNativeDisplayType getNativeDisplay() = 0;

	// True if this provider surfaces via a pixmap (eglCreatePlatformPixmapSurfaceEXT)
	// rather than a window (eglCreateWindowSurface) - see getNativePixmap(). Some
	// platforms (Dreambox's VC5/BEGL stack) only implement the pixmap path.
	virtual bool usesPixmapSurface() const { return false; }

	// Returns the native window (e.g. wl_egl_window for Wayland). Only called when
	// usesPixmapSurface() is false.
	virtual EGLNativeWindowType getNativeWindow() { return (EGLNativeWindowType)0; }

	// Number of independent pixmap pages this provider can describe (see
	// getNativePixmap()) - only meaningful when usesPixmapSurface() is true.
	// gEGLDC creates one EGLSurface per page and ping-pongs rendering between
	// them (see gEGLDC::flip()) instead of always rendering into - and
	// therefore presenting - the same one. A provider whose "pixmap" IS live
	// display memory (e.g. Dreambox, where there is no separate present/blit
	// step) needs more than one page for this to actually double-buffer;
	// with just 1 (the default), every frame renders directly into whatever
	// the display is currently scanning out, and a frame slower than one
	// vblank is visibly drawn on screen mid-frame.
	virtual int getPageCount() const { return 1; }

	// Returns a pointer to the platform's native pixmap descriptor (its concrete
	// type is platform-defined, e.g. dmegl_pixmap_handle for Dreambox) describing
	// page `page` (0..getPageCount()-1), for use with
	// eglCreatePlatformPixmapSurfaceEXT. Only called when usesPixmapSurface() is true.
	virtual void* getNativePixmap(int page) { return nullptr; }

	// Called once per frame, after rendering into page `page` (see
	// getPageCount()), instead of eglSwapBuffers() when usesPixmapSurface()
	// is true, since eglSwapBuffers() is only defined for window surfaces.
	// Must ensure the GPU work targeting that page is actually complete
	// (e.g. glFinish()) and, for a multi-page provider, make that page the
	// one actually shown by the display (e.g. FBIOPAN_DISPLAY). Default is
	// a no-op.
	virtual void presentPixmap(int page) {}

	// Copies the full content of page `from` into page `to` - called by
	// gEGLDC::flip() right after switching the render target to a new back
	// buffer (see getPageCount()), before any opcodes for the new frame are
	// processed. Needed because the compositor above this (eWidgetDesktop)
	// tracks *dirty regions*, not full-screen state: it assumes whatever it
	// renders into already holds the previous frame's content and only
	// patches in what changed. That assumption holds for a single buffer
	// (the render target IS the display) but not for N-way ping-ponging,
	// where a given page is only rendered into once every N frames and
	// otherwise holds a patchwork of whichever partial updates happened to
	// land on it - displaying it shows stale/blank content anywhere outside
	// this frame's dirty region. Seeding each new back buffer with an exact
	// copy of what's currently on screen restores the single-buffer
	// assumption before the incremental redraw runs. Default is a no-op
	// (single-page providers never switch pages, so there's nothing to seed).
	virtual void copyPageContent(int from, int to) {}

	// Cleans up platform-specific resources.
	virtual void cleanup() = 0;
};
