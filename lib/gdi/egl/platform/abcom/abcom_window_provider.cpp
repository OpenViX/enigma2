#include <cstdint>
#include <cstring>
#include <EGL/egl.h>
#include <lib/base/eerror.h>
#include <lib/gdi/fb.h>
#include <lib/gdi/egl/platform/abcom/abcom_window_provider.h>

AbcomWindowProvider::AbcomWindowProvider() {
	memset(&m_native_window, 0, sizeof(m_native_window));
}

AbcomWindowProvider::~AbcomWindowProvider() {
	cleanup();
}

bool AbcomWindowProvider::init(int width, int height) {
	// This is the whole of what this provider needs to do before EGL itself
	// takes over (see this class's own header comment) - unlike
	// GbquadWindowProvider/VuplusWindowProvider there is no separate Nexus
	// server to join and no compositor window to create/show first: the
	// struct below is handed to eglCreateWindowSurface() by gEGLDC itself
	// (see gegldc.cpp's tryInitEGL()), and everything from eglGetDisplay()
	// onward is generic.
	m_native_window.width = (unsigned short)width;
	m_native_window.height = (unsigned short)height;

	// fbClass is NOT necessarily our render target here (see this class's
	// header comment on the unconfirmed /dev/fb0 sharing question), but it
	// is the singleton the rest of enigma2 uses for the framebuffer lock
	// (ImageManager.py's fbClass.getInstance().lock()/unlock() around
	// ofgwrite, gEGLDC::islocked()) - and gFBDC, its normal owner, isn't
	// built with EGL (see lib/gdi/Makefile.inc). Mirrors
	// GbquadWindowProvider::init()/VuplusWindowProvider::init() exactly -
	// see their own comments for the full rationale. Not fatal on failure -
	// the EGL window created afterward is what actually displays enigma2.
	fbClass* fb = fbClass::getInstance();
	if (!fb)
		fb = new fbClass;
	if (fb->SetMode(width, height, 32) < 0) {
		eDebug("[AbcomWindowProvider] fbClass::SetMode(%dx%d) failed - framebuffer lock unavailable", width, height);
	} else {
		clearFramebuffer();
	}

	eDebug("[AbcomWindowProvider] init %dx%d (Mali Utgard fbdev native window)", width, height);
	return true;
}

void AbcomWindowProvider::onResolutionChanged(int width, int height) {
	// Called before gEGLDC destroys and recreates the window surface from
	// getNativeWindow() (see gEGLDC::applyPendingResolutionChange()), so the
	// new surface is created against the updated size.
	m_native_window.width = (unsigned short)width;
	m_native_window.height = (unsigned short)height;
	eDebug("[AbcomWindowProvider] native window resized to %dx%d", width, height);
}

void AbcomWindowProvider::clearFramebuffer() {
	fbClass* fb = fbClass::getInstance();
	if (fb && fb->lfb && fb->Available() > 0)
		memset(fb->lfb, 0, (size_t)fb->Available());
}

EGLNativeDisplayType AbcomWindowProvider::getNativeDisplay() {
	return EGL_DEFAULT_DISPLAY;
}

EGLNativeWindowType AbcomWindowProvider::getNativeWindow() {
	// (uintptr_t) round-trip rather than a direct pointer cast: stays
	// correct regardless of whether this build's mesa headers alias
	// EGLNativeWindowType to a real pointer type or (as headless,
	// no-X11/Wayland builds typically do) an integer handle type merely the
	// same width as one - see this class's header comment.
	return (EGLNativeWindowType)(uintptr_t)&m_native_window;
}

void AbcomWindowProvider::cleanup() {
	// Nothing to release: no join/register handle exists on this platform
	// (see this class's header comment) - EGL context/surface teardown
	// itself is handled generically by gEGLDC, not this provider.
}
