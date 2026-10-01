#pragma once

#include <lib/gdi/egl/inative_window_provider.h>

// EGL native-window provider for VU+'s Broadcom Nexus stack (vuduo2,
// vuduo4k, vuduo4kse, vusolo2, vusolo4k, vusolose, vuultimo4k, vuuno4k,
// vuuno4kse, vuzero4k - the models oe-alliance-core's meta-vuplus layer ships
// a libvupl/libgles pair for). Confirmed (by downloading and inspecting the
// actual vendor tarballs referenced from oe-alliance-core's
// meta-brands/meta-vuplus/recipes-graphics/{libgles,libvupl} recipes - the
// SRC_URIs there are not auth-gated) to be the SAME underlying
// Nexus/NXPL/V3D driver family as GigaBlue Quad 4K Pro (see
// lib/gdi/egl/platform/gbquad): the libgles package ships libnxpl.so,
// libv3ddriver.so, libdvb_base.so and libdvb_client.so, and its own
// nxpl.pc advertises "Broadcom/Vu+ Nexus platform layer".
//
// Unlike GigaBlue, this platform's vendor package also ships a small VU+-own
// wrapper library (libvupl.so / <eglvuplus.h>, "Vu+ API for EGL/OpenGLES")
// that does the NxClient_Join()/NXPL_RegisterNexusDisplayPlatform() dance
// internally and exposes a much smaller surface (VUGLES_InitPlatform*/
// VUGLES_CreateNativeWindow/VUGLES_SetPosition/...) - so, unlike
// GbquadWindowProvider, this provider never touches nxclient.h/
// default_nexus.h (or any other raw Nexus header) directly at all; only
// <eglvuplus.h> (installed by the "libvupl" package/pkg-config module) and
// plain EGL are needed. eglvuplus.h's VUGLES_NativeWindowInfo carries the
// exact same per-window `stretch` flag as GbquadWindowProvider's
// NXPL_NativeWindowInfoEXT (both are the same underlying NXPL concept, just
// exposed through this thinner wrapper) - see onResolutionChanged() below
// for why that flag matters.
//
// Presentation goes through Nexus's own compositor via a genuine EGL window
// surface (VUGLES_CreateNativeWindow + eglCreateWindowSurface +
// eglSwapBuffers, exactly as the vendor's own cube demo - libvupl-example-cube
// in meta-vuplus/recipes-graphics/libvupl-examples - does it), not the
// framebuffer, so usesPixmapSurface() stays at its base-class default of
// false. As on GigaBlue, /dev/fb0 is expected to be a separate display layer
// composited BENEATH this window on the same Nexus stack - clearFramebuffer()
// mirrors GbquadWindowProvider's for exactly that reason - but this has not
// yet been confirmed on real VU+ hardware (GigaBlue's was verified against a
// physical gbquad4kpro; treat this specific assumption as carried over by
// architecture family, not independently proven here).
//
// Shadow FBO: libvupl-example-cube gives no evidence either way (it glClear()s
// and redraws every frame and never sets EGL_SWAP_BEHAVIOR), and the
// vuuno4k/vusolo4k libv3ddriver.so advertise no swap-preservation extension.
// Being the same V3D/NXPL family as gbquad4kpro (where preservation was
// refused), assume gEGLDC's runtime EGL_BUFFER_PRESERVED probe falls back to
// the shadow FBO here too. On the GLES2-only models (vuduo4kse, vusolo4k,
// vuultimo4k) that fallback presents via a textured quad, not
// glBlitFramebuffer() - see gEGLDC::flip().
//
// configure.ac's HAVE_EGL block carries a standing warning that
// vuduo4kse/vusolo4k/vuultimo4k previously hit link failures ("undefined
// reference to glBindVertexArray") when generically probed for
// --with-egl - their SDK's pkg-config metadata does not by itself guarantee
// a fully working GLES3 backend. That warning predates this provider and is
// about the GENERIC EGL/GLES2/GLES3 probe, not this platform's own
// NXPL-family window path, but it is still a reason to bring each VU+ model
// up and test individually rather than assuming the whole
// HAVE_VUPLUS_EGL-enabled set works identically.
class VuplusWindowProvider : public INativeWindowProvider {
private:
	void *m_vugles_handle;    // handle from VUGLES_RegisterDisplayPlatform
	void *m_native_window;    // handle from VUGLES_CreateNativeWindow
	int m_client_id;          // dvb_client id for this window, from VUGLES_GetClientID
	bool m_platform_inited;   // VUGLES_InitPlatformAndDefaultDisplay succeeded - must be balanced by VUGLES_TermPlatform

public:
	VuplusWindowProvider();
	virtual ~VuplusWindowProvider();

	// INativeWindowProvider
	bool init(int width, int height) override;
	EGLNativeDisplayType getNativeDisplay() override;
	EGLNativeWindowType getNativeWindow() override;
	void cleanup() override;
	void onFramebufferUnlocked() override { clearFramebuffer(); }

	// Same rationale as GbquadWindowProvider::onResolutionChanged(): `stretch`
	// (set in init(), see its own comment there) makes Nexus's compositor
	// scale THIS window's authored width/height to fill the display
	// regardless of the current output resolution, but nothing updates that
	// authored size if the OSD canvas itself changes size after init()
	// already ran. VUGLES_UpdateNativeWindow() (unlike
	// NXPL_UpdateNativeWindowEXT()) does not reset stretch to a default on
	// its own - but it is set explicitly again here anyway, to stay obviously
	// correct regardless of that detail and to mirror GbquadWindowProvider's
	// same defensive re-set.
	void onResolutionChanged(int width, int height) override;

	// Zeroes /dev/fb0 (fully transparent) - see this class's own comment on
	// why fb0 is assumed to sit beneath this provider's window, mirroring
	// GbquadWindowProvider::clearFramebuffer().
	static void clearFramebuffer();
};
