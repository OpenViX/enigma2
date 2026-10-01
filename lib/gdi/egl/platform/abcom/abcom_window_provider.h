#pragma once

#include <lib/gdi/egl/inative_window_provider.h>

// EGL native-window provider for ABCom's pulse4k/pulse4kmini (HiSilicon
// Hi3798MV200 SoC, ARM Mali-450 MP4 "Utgard" GPU). Confirmed (by reading the
// actual recipes - not auth-gated - meta-brands/meta-abcom/recipes-graphics/
// mali/{abcom-mali-utgard.inc,abcom-mali-3798mv200.bb,
// kernel-module-mali-utgard.inc} in github.com/oe-alliance/oe-alliance-core)
// to ship a Mali Utgard r7p0 kernel driver plus a single combined
// libMali.so userspace blob whose COMPATIBLE_MACHINE is exactly
// "^pulse4k$|^pulse4kmini$".
//
// Unlike GigaBlue/VU+'s Broadcom Nexus/NXPL stack (lib/gdi/egl/platform/
// gbquad, lib/gdi/egl/platform/vuplus), there is no separate compositor
// process to join or register a window with here: abcom-mali-utgard.inc's
// do_install:append symlinks libMali.so directly onto the completely
// standard libEGL.so.1/libGLESv1_CM.so.1/libGLESv2.so.2 sonames, and that
// same .inc file says outright "The driver is missing EGL/GLES headers and
// pkgconfig files" - it DEPENDS on mesa purely to obtain mesa's own
// standard Khronos EGL/GLES headers and egl.pc/glesv2.pc at build time
// (RREPLACES/RCONFLICTS then swap mesa's runtime libEGL/libGLESv2 for
// libMali.so at the package level). So, unlike gbquad4kpro/VU+, this
// platform needs no vendor-specific header or pkg-config module at all -
// configure.ac's generic EGL/GLESv2 PKG_CHECK_MODULES (HAVE_EGL block)
// already resolves straight to it.
//
// That also means EGLNativeWindowType, as seen through mesa's own headless
// (no X11/Wayland) eglplatform.h, is just whatever opaque pointer-sized
// handle mesa defines it as - NOT a vendor-specific typed struct pointer
// like GigaBlue's NXPL_PlatformHandle or VU+'s eglvuplus.h types. The
// concrete struct the Mali Utgard "fbdev" EGL platform backend actually
// expects behind that handle is not shipped by this vendor package at all,
// but is a well-known, independently-documented ABI shared by every Mali
// Utgard fbdev integration for this GPU IP (see e.g. the public, unrelated
// linux-sunxi/sunxi-mali project's own include/EGL/eglplatform_fb.h, which
// defines the identical struct for the same GPU IP's fbdev backend):
//
//   struct mali_native_window { unsigned short width; unsigned short height; };
//
// passed to eglCreateWindowSurface() as a pointer. Presentation goes
// through a genuine EGL window surface (eglCreateWindowSurface +
// eglSwapBuffers) exactly like GbquadWindowProvider/VuplusWindowProvider,
// not a pixmap - the Mali fbdev backend does its own internal double
// buffering against /dev/fb0 - so usesPixmapSurface() stays at its
// base-class default of false.
//
// There is no NXPL-style per-window "stretch" concept on this platform (no
// separate compositor to ask): the EGL window's pixel dimensions are
// authored in the struct above and directly become /dev/fb0's video mode.
// So a later OSD canvas resize (see gEGLDC::setResolution()) cannot be
// handled by telling a compositor to rescale - instead onResolutionChanged()
// updates that struct, and gEGLDC::applyPendingResolutionChange() then
// destroys and recreates the EGL window surface from getNativeWindow(), which
// is what makes the Mali fbdev backend pick up the new size. Whether the
// driver really re-reads it on surface recreation is unconfirmed on hardware.
//
// NOT YET BUILT OR HARDWARE-TESTED on a real pulse4k/pulse4kmini (same
// caveat VuplusWindowProvider carried when it was first added - see its own
// header comment): the mali_native_window ABI above is corroborated by an
// independent public source for the same Mali Utgard GPU IP, not by
// inspecting ABCom's actual libMali.so, and whether fbClass safely sharing
// /dev/fb0 with whatever the Mali driver does internally (see init()'s own
// comment) is unconfirmed. Bring this up on real hardware and check the
// device log (the eDebug output below) before trusting this over rebuilding
// with --without-egl.
class AbcomWindowProvider : public INativeWindowProvider {
private:
	// The vendor ABI struct described above - kept as a persistent member
	// (not a stack temporary) since nothing guarantees the driver only
	// reads through the pointer once, at eglCreateWindowSurface() time,
	// rather than again later (e.g. on some internal mode query).
	struct mali_native_window {
		unsigned short width;
		unsigned short height;
	};
	mali_native_window m_native_window;

public:
	AbcomWindowProvider();
	virtual ~AbcomWindowProvider();

	// INativeWindowProvider
	bool init(int width, int height) override;
	EGLNativeDisplayType getNativeDisplay() override;
	EGLNativeWindowType getNativeWindow() override;
	void cleanup() override;
	void onFramebufferUnlocked() override { clearFramebuffer(); }

	// Updates m_native_window's authored size - see this class's header
	// comment for why that is all this platform can do.
	void onResolutionChanged(int width, int height) override;

	// Zeroes /dev/fb0 (fully transparent) - same rationale as
	// GbquadWindowProvider::clearFramebuffer()/VuplusWindowProvider's own,
	// in case anything (ofgwrite's progress screen, boot leftovers) is left
	// there underneath whatever the Mali driver scans out.
	static void clearFramebuffer();
};
