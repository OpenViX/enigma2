#include <cstdint>
#include <cstring>
#include <EGL/egl.h>
#include <lib/base/eerror.h>
// Must come before <nxclient.h>: this header's NEXUS_HAS_DISPLAY/AUDIO/
// GRAPHICS2D defines and its nexus_hdmi_output_hdcp.h include both need to
// be visible before anything reaches nxclient.h's own chain into
// nexus_core_compat.h/nxclient_global.h - see its own comment for why.
#include <lib/gdi/egl/platform/gbquad/gbquad_window_provider.h>
#include <nxclient.h>

GbquadWindowProvider::GbquadWindowProvider()
	: m_nxpl_display_handle(nullptr), m_native_window(nullptr), m_joined_nxclient(false) {
}

GbquadWindowProvider::~GbquadWindowProvider() {
	cleanup();
}

bool GbquadWindowProvider::init(int width, int height) {
	// 1. Join the already-running Nexus server (started at boot, outside
	// enigma2) - every EGL call below aborts with a Broadcom "memory
	// interface not registered" assertion until this has succeeded.
	NxClient_JoinSettings joinSettings;
	NxClient_GetDefaultJoinSettings(&joinSettings);
	NEXUS_Error join_rc = NxClient_Join(&joinSettings);
	if (join_rc != NEXUS_SUCCESS) {
		eDebug("[GbquadWindowProvider] NxClient_Join failed, rc=%d", (int)join_rc);
		return false;
	}
	m_joined_nxclient = true;
	eDebug("[GbquadWindowProvider] joined Nexus server");

	// 2. Register a Nexus display platform with the EGL glue layer - this is
	// what actually satisfies the vendor driver's memory-interface check
	// that a bare eglGetDisplay()/eglInitialize() aborts on otherwise.
	// Passing a null NEXUS_DISPLAYHANDLE registers against the server's
	// default display, exactly as NxClient-based clients are expected to.
	NXPL_RegisterNexusDisplayPlatform(&m_nxpl_display_handle, nullptr);
	if (!m_nxpl_display_handle) {
		eDebug("[GbquadWindowProvider] NXPL_RegisterNexusDisplayPlatform did not produce a handle");
		cleanup();
		return false;
	}

	// 3. Create and show a full-screen native window through Nexus's own
	// compositor - this is what eglCreateWindowSurface() targets below, and
	// what actually reaches the TV: /dev/fb0 is not connected to the display
	// scanout at all on this stack (unlike Dreambox, where the pixmap
	// surface IS the live framebuffer - see DreamboxWindowProvider).
	NXPL_NativeWindowInfoEXT windowInfo;
	NXPL_GetDefaultNativeWindowInfoEXT(&windowInfo);
	windowInfo.width = (uint32_t)width;
	windowInfo.height = (uint32_t)height;
	windowInfo.x = 0;
	windowInfo.y = 0;

	m_native_window = NXPL_CreateNativeWindowEXT(&windowInfo);
	if (!m_native_window) {
		eDebug("[GbquadWindowProvider] NXPL_CreateNativeWindowEXT failed");
		cleanup();
		return false;
	}

	NXPL_ShowNativeWindowEXT(m_native_window, true);

	eDebug("[GbquadWindowProvider] init %dx%d - Nexus joined, display platform registered, native window shown", width, height);
	return true;
}

EGLNativeDisplayType GbquadWindowProvider::getNativeDisplay() {
	return EGL_DEFAULT_DISPLAY;
}

EGLNativeWindowType GbquadWindowProvider::getNativeWindow() {
	return (EGLNativeWindowType)m_native_window;
}

void GbquadWindowProvider::cleanup() {
	if (m_native_window) {
		NXPL_ShowNativeWindowEXT(m_native_window, false);
		NXPL_DestroyNativeWindow(m_native_window);
		m_native_window = nullptr;
	}
	if (m_nxpl_display_handle) {
		NXPL_UnregisterNexusDisplayPlatform(m_nxpl_display_handle);
		m_nxpl_display_handle = nullptr;
	}
	// NxClient_Join() is reference-counted (nxclient.h) - an equal number of
	// NxClient_Uninit() calls is required to detach from Nexus and the
	// server app, unlike the old dlopen-based version of this file, which
	// left libnxclient.so/libnxpl.so dlopen'd (and therefore joined) forever
	// specifically to sidestep a dlclose() safety concern that doesn't apply
	// here: with real linking there's no dlclose() to worry about, only the
	// documented join/uninit symmetry.
	if (m_joined_nxclient) {
		NxClient_Uninit();
		m_joined_nxclient = false;
	}
}
