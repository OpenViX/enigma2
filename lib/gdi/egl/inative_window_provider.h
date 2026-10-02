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

	// True if this platform's actual display scanout reads back gEGLDC's
	// render target colors in the opposite R/B order from what GL writes -
	// see gles::needsRBSwap's comment (gles_version.h) for the full
	// explanation and which shader/upload sites compensate for it. Proven
	// true on Dreambox's VC5/BEGL pixmap-surface scanout via a ground-truth
	// debug swatch (see DreamboxWindowProvider's override) - NOT assumed
	// true for other platforms, since it's a hardware/driver quirk, not
	// general EGL/GLES behavior. Default false.
	virtual bool needsRenderTargetRBSwap() const { return false; }

	// Called (on the unlocking thread) when fbClass::unlock() ends an
	// external framebuffer user's session (ofgwrite, see ImageManager.py) -
	// lets a provider whose window is a layer ABOVE /dev/fb0 wipe whatever
	// that user left there, since nothing of enigma2's ever overwrites it.
	// Default no-op.
	virtual void onFramebufferUnlocked() {}

	// width/height are the PHYSICAL render size: equal to the OSD canvas size,
	// except when the canvas exceeds the GPU's texture/renderbuffer limit and
	// gEGLDC renders it scaled down (see gEGLDC::m_phys_width) - the window must
	// match what is actually rendered, and `stretch` fills the display from it.
	//
	// Called from gEGLDC::applyPendingResolutionChange() (render thread,
	// EGL context current) when the OSD canvas's resolution changes after
	// this provider's window/pixmap was already created (see
	// gEGLDC::setResolution()) - lets a provider whose native window was
	// given a fixed authored size at creation (e.g. GbquadWindowProvider,
	// which tells Nexus's compositor to scale that fixed size to fill the
	// display) update it to match. Default no-op - a provider whose window
	// naturally tracks this canvas's size some other way (or that only ever
	// runs at one fixed resolution) needs nothing here.
	virtual void onResolutionChanged(int width, int height) {}

	// True when the platform's window compositor blends this window as
	// STRAIGHT alpha (colour * alpha + background * (1 - alpha)) and the
	// provider has no way to change that equation (GbquadWindowProvider can,
	// via its window's blend equations - see applyWindowBlendOverride()). The
	// OSD frame is rendered premultiplied (GL blending over a transparent
	// target), so such a compositor multiplies by alpha a second time and every
	// translucent area comes out too dark. gEGLDC then un-premultiplies the
	// frame in its final present pass instead. Default false.
	virtual bool needsStraightAlphaPresent() { return false; }

	// False when resizing this provider's native window after init() does not
	// work (VU+: VUGLES_UpdateNativeWindow + surface recreation leaves the
	// window rendering correctly - grabs are fine - but never visible on screen,
	// for ANY size change). gEGLDC then keeps the window and EGL surface at the
	// size they were created with and renders every canvas, larger or smaller,
	// scaled into it (see gEGLDC::updatePhysicalSize()). Default true.
	virtual bool canResizeWindow() { return true; }

	// Cleans up platform-specific resources.
	virtual void cleanup() = 0;
};
