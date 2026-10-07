#include <lib/base/eerror.h>
#include <lib/gdi/egl/platform/dreambox/dreambox_window_provider.h>
#include <lib/gdi/fb.h>

#ifdef HAVE_GLES3
#include <GLES3/gl3.h>
#else
#include <GLES2/gl2.h>
#endif

// drm/drm_fourcc.h's DRM_FORMAT_ABGR8888. A diagnostic pass (comparing
// known-good source-image RGB values against the bytes actually handed to
// glTexImage2D/glTexSubImage2D for both text and picon uploads) proved the
// GPU texture pipeline puts the right byte in the right place every time -
// so the visible R/B swap users saw was never in texture uploads at all.
// This is the one remaining untested link: it tells the vendor's native-
// pixmap EGL surface how to interpret the live scanout framebuffer memory
// that GL renders directly into and the display controller reads from.
// ARGB8888 (memory order B,G,R,A) matched gTextureManager's own BGRA
// assumption for enigma2 surfaces, but that's a fact about *enigma2's* CPU
// pixmaps, not about what this SoC's display plane actually expects -
// several Broadcom-based STB graphics stacks are known to swap R/B in their
// hardware compositor's native order. Try ABGR8888 (memory order R,G,B,A).
#define DRM_FORMAT_ABGR8888 0x34324241

DreamboxWindowProvider::DreamboxWindowProvider() : m_page_count(1), m_height(0), m_page_bytes(0) {
	memset(m_pixmaps, 0, sizeof(m_pixmaps));
}

DreamboxWindowProvider::~DreamboxWindowProvider() {
	cleanup();
}

bool DreamboxWindowProvider::init(int width, int height) {
	fbClass* fb = fbClass::getInstance();
	if (!fb) {
		// gFBDC (the classic gDC) is not built when EGL is enabled (see
		// lib/gdi/Makefile.inc) - it used to be the sole owner of fbClass's
		// construction (gFBDC::gFBDC() does "fb = new fbClass;"), so we take
		// over that responsibility here since we're now the sole consumer of
		// the live framebuffer.
		fb = new fbClass;
		if (!fb) {
			eDebug("[DreamboxWindowProvider] failed to construct fbClass");
			return false;
		}
	}

	// fbClass only opens the device and reads the *boot-time* mode in its
	// constructor - stride is left uninitialized and lfb unmapped until
	// SetMode() actually programs the mode (this is what gFBDC::setResolution()
	// normally does; gFBDC is not built when EGL is enabled, so we do it here).
	if (fb->SetMode(width, height, 32) < 0) {
		eDebug("[DreamboxWindowProvider] fbClass::SetMode(%dx%d) failed", width, height);
		return false;
	}

	m_height = height;

	// fbClass::SetMode() allocates fb->getNumPages() pages stacked in one
	// mmap'd virtual framebuffer (fb->lfb, offset 0 = page 0's base) - describe
	// each as its own pixmap so gEGLDC can create one EGLSurface per page and
	// ping-pong rendering between them (see gEGLDC::flip()/tryInitEGL())
	// instead of always rendering into (and therefore visibly drawing into)
	// whichever page is currently on screen - see the class comment.
	m_page_count = fb->getNumPages();
	if (m_page_count < 1)
		m_page_count = 1;
	if (m_page_count > kMaxPages)
		m_page_count = kMaxPages;

	m_page_bytes = (unsigned long)fb->Stride() * (unsigned long)height;
	for (int i = 0; i < m_page_count; ++i) {
		m_pixmaps[i].mem.magic = DMEGL_PIXMAP_MAGIC;
		m_pixmaps[i].mem.length = m_page_bytes;
		m_pixmaps[i].mem.offset = 0;
		m_pixmaps[i].mem.fd = -1; // no separate fd: addr is already mapped below
		m_pixmaps[i].mem.phys = (uintptr_t)fb->getPhysAddr() + (uintptr_t)i * m_page_bytes;
		m_pixmaps[i].mem.addr = fb->lfb + (size_t)i * m_page_bytes;

		m_pixmaps[i].width = (unsigned int)width;
		m_pixmaps[i].height = (unsigned int)height;
		m_pixmaps[i].pitch = fb->Stride();
		m_pixmaps[i].format = DRM_FORMAT_ABGR8888;
	}

	// Show page 0 initially - gEGLDC starts rendering into a *different*
	// page (see its m_render_page initialization in tryInitEGL()) so the
	// very first frame never renders into what's simultaneously on screen.
	fb->setOffset(0);

	eDebug("[DreamboxWindowProvider] init %dx%d pitch=%u pages=%d phys=0x%lx", width, height, m_pixmaps[0].pitch, m_page_count, (unsigned long)m_pixmaps[0].mem.phys);
	return true;
}

EGLNativeDisplayType DreamboxWindowProvider::getNativeDisplay() {
	return EGL_DEFAULT_DISPLAY;
}

void* DreamboxWindowProvider::getNativePixmap(int page) {
	if (page < 0 || page >= m_page_count)
		return nullptr;
	return &m_pixmaps[page];
}

void DreamboxWindowProvider::presentPixmap(int page) {
	// TEST: the glReadPixels forced-copy that used to live here was added
	// based on a readback diagnostic captured *before* the gRC-thread EGL
	// context-affinity fix (see grc.cpp/egl_init.cpp) - at that time NOTHING
	// rendered at all (viewport was (0,0,0,0)), so of course the native
	// "driver writes directly into the described pixmap memory" mechanism
	// looked broken. That was a symptom of the real bug, not proof this path
	// is bad. Now that rendering actually happens on the correct thread with
	// a correct viewport, trust the vendor's native pixmap-surface write
	// mechanism again and just wait for completion - glReadPixels may have
	// been misinterpreting this GPU's internal tiled/compressed render
	// target layout as plain linear memory, which would explain banding.
	glFinish();

	// Multi-page: page just finished rendering (and, per glFinish() above,
	// is actually done) - pan the display to it. Single-page (m_page_count
	// == 1, e.g. this platform's fbdev only granted one buffer): nothing to
	// pan between, same as the old behavior.
	if (m_page_count > 1) {
		fbClass* fb = fbClass::getInstance();
		if (fb) {
			// Wait for vsync BEFORE panning, not after: FBIOPAN_DISPLAY takes
			// effect relative to whatever point in the scan cycle it's
			// issued at, so panning at an arbitrary moment can apply
			// mid-scan and tear the frame between the old and new page.
			// This is the same wait-then-pan order gfbdc.cpp's classic 2D
			// path uses for gOpcode::flush's CONFIG_ION branch.
			fb->waitVSync();
			fb->setOffset(page * m_height);
		}
	}
}

void DreamboxWindowProvider::copyPageContent(int from, int to) {
	if (from < 0 || from >= m_page_count || to < 0 || to >= m_page_count || from == to || m_page_bytes == 0)
		return;

	// Plain CPU memcpy between two pages of the same mmap'd framebuffer -
	// both are already the "trust this as plain linear memory" pixmap
	// representation this whole provider relies on (see the DRM_FORMAT_ABGR8888
	// comment above and presentPixmap()), so no GPU/EGL involvement is needed
	// or safe to assume here: `from` was already fully resolved by a prior
	// glFinish() (see presentPixmap()) before this is ever called, and `to`
	// has not been made the EGL draw target's *content* yet at this point in
	// gEGLDC::flip() (only eglMakeCurrent'd, no draws issued) - so this is the
	// first and only writer touching `to` this frame.
	memcpy(m_pixmaps[to].mem.addr, m_pixmaps[from].mem.addr, m_page_bytes);
}

void DreamboxWindowProvider::cleanup() {
	// Nothing to release: the framebuffer memory is owned by fbClass, not us.
}
