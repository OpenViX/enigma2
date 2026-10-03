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
// process to join: libMali.so is symlinked onto the standard libEGL.so.1/
// libGLESv2.so.2 sonames. The vendor package ships no headers/pkg-config
// files; egl-gles-extras/meta-local stages the HiSilicon SDK ones (see its
// abcom-mali-3798mv200.bbappend), whose eglplatform.h defines
// EGLNativeWindowType as fbdev_window*.
//
// ABI, verified by libMali.so (__egl_platform_window_valid_fbdev,
// __egl_platform_get_window_size_fbdev): the window handle is a pointer to
//
//   struct fbdev_window { unsigned short width; unsigned short height; };
//
// (1..4096 each), and the native display is EGL_DEFAULT_DISPLAY (0). It is
// identical to <EGL/fbdev_window.h>'s fbdev_window, mirrored below as
// mali_native_window so this file does not depend on that header.
// Presentation goes through a genuine EGL window surface, so
// usesPixmapSurface() stays at its base-class default of false.
//
// There is no per-window "stretch" concept here, and libMali's fbdev backend
// reads /dev/fb0's current mode instead of setting one from the window size
// (it only compares the window against fb0's xres/yres).
//
// hifb (/dev/fb0) refuses any mode above 1920x1080 (FBIOPUT_VSCREENINFO returns
// EPERM for 2560x1440 and 3840x2160, verified on device). So canResizeWindow()
// is false: the window and EGL surface stay at the boot fb size and gEGLDC
// renders every canvas scaled into them (see gEGLDC::updatePhysicalSize()) - a
// manually installed 1440p skin included, whether or not the build has
// E2EGL_WQHD_FEATURE. onResolutionChanged() is therefore never called.
//
// libMali is GLES 2.0 only (no GLES3 core, no GL_EXT_texture_rg). That needs no
// special handling: single-channel textures already take the GL_LUMINANCE path
// whenever gles::isGLES3() is false, and the shaders sample .r.

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

	// Updates m_native_window's authored size. Not reached while
	// canResizeWindow() is false; kept so the struct stays consistent.
	void onResolutionChanged(int width, int height) override;

	// See this class's header comment: hifb cannot go above 1920x1080.
	bool canResizeWindow() override { return false; }
	// Zeroes /dev/fb0 (fully transparent) - same rationale as
	// GbquadWindowProvider::clearFramebuffer()/VuplusWindowProvider's own,
	// in case anything (ofgwrite's progress screen, boot leftovers) is left
	// there underneath whatever the Mali driver scans out.
	static void clearFramebuffer();
};
