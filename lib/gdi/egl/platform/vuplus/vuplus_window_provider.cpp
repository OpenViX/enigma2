#include <cstdint>
#include <cstring>
#include <EGL/egl.h>
#include <eglvuplus.h>
#include <lib/base/eerror.h>
#include <lib/gdi/fb.h>
#include <lib/gdi/egl/platform/vuplus/vuplus_window_provider.h>

VuplusWindowProvider::VuplusWindowProvider()
	: m_vugles_handle(nullptr), m_native_window(nullptr), m_client_id(-1), m_platform_inited(false) {
}

VuplusWindowProvider::~VuplusWindowProvider() {
	cleanup();
}

bool VuplusWindowProvider::init(int width, int height) {
	// 1. Initialise libvupl's own platform/default-display handling - this is
	// what does the NxClient_Join()/NXPL_RegisterNexusDisplayPlatform() work
	// internally that GbquadWindowProvider does by hand against the raw
	// Nexus headers (see this class's own header comment). `aspect` is an
	// out-parameter the vendor's own cube demo (libvupl-example-cube)
	// initialises to 1.0f and never reads afterwards - width/height here are
	// enigma2's OSD/skin canvas size, exactly as GbquadWindowProvider passes
	// to NXPL_CreateNativeWindowEXT.
	float aspect = 1.0f;
	vuInitResult res = VUGLES_InitPlatformAndDefaultDisplay("enigma2", &aspect, (uint32_t)width, (uint32_t)height);
	if (res != vuInitSuccess) {
		eDebug("[VuplusWindowProvider] VUGLES_InitPlatformAndDefaultDisplay failed");
		return false;
	}
	m_platform_inited = true;
	eDebug("[VuplusWindowProvider] platform initialised");

	// 2. Register with the platform layer - required before any EGL call,
	// same reasoning as NXPL_RegisterNexusDisplayPlatform() on GigaBlue.
	VUGLES_RegisterDisplayPlatform(&m_vugles_handle);
	if (!m_vugles_handle) {
		eDebug("[VuplusWindowProvider] VUGLES_RegisterDisplayPlatform did not produce a handle");
		cleanup();
		return false;
	}

	// 3. Create and show a full-screen native window through Nexus's own
	// compositor, reached via libvupl - this is what eglCreateWindowSurface()
	// targets below, and what actually reaches the TV as enigma2's OSD.
	VUGLES_NativeWindowInfo win_info;
	VUGLES_GetDefaultNativeWindowInfo(&win_info);
	win_info.width = (uint32_t)width;
	win_info.height = (uint32_t)height;
	win_info.x = 0;
	win_info.y = 0;
	// Same reasoning as GbquadWindowProvider::init()'s own windowInfo.stretch:
	// nothing calls VUGLES_UpdateNativeWindow() when the actual HDMI/video
	// mode changes later (only /proc/stb/video/videomode_* is written - see
	// Components/AVSwitch.py's setMode()), so this window must be told to
	// scale itself to whatever the display's current mode is, rather than
	// being shown pixel-for-pixel against it.
	win_info.stretch = true;

	m_native_window = VUGLES_CreateNativeWindow(&win_info);
	if (!m_native_window) {
		eDebug("[VuplusWindowProvider] VUGLES_CreateNativeWindow failed");
		cleanup();
		return false;
	}

	m_client_id = VUGLES_GetClientID(m_native_window);
	VUGLES_SetVisible(m_client_id, true);

	// 4. fbClass is NOT our render target here, but it is the singleton the
	// rest of enigma2 uses for the framebuffer lock (ImageManager.py's
	// fbClass.getInstance().lock()/unlock() around ofgwrite, gEGLDC::islocked())
	// - and gFBDC, its normal owner, isn't built with EGL (see
	// lib/gdi/Makefile.inc). Mirrors GbquadWindowProvider::init() exactly -
	// see its own comment for the full rationale.
	fbClass* fb = fbClass::getInstance();
	if (!fb)
		fb = new fbClass;
	if (fb->SetMode(width, height, 32) < 0) {
		eDebug("[VuplusWindowProvider] fbClass::SetMode(%dx%d) failed - framebuffer lock unavailable", width, height);
	} else {
		clearFramebuffer();
	}

	eDebug("[VuplusWindowProvider] init %dx%d - platform initialised, native window shown, dvb_client #%d", width, height, m_client_id);
	return true;
}

void VuplusWindowProvider::onResolutionChanged(int width, int height) {
	if (!m_native_window)
		return;

	VUGLES_NativeWindowInfo win_info;
	VUGLES_GetDefaultNativeWindowInfo(&win_info);
	win_info.width = (uint32_t)width;
	win_info.height = (uint32_t)height;
	win_info.x = 0;
	win_info.y = 0;
	win_info.stretch = true;
	// Same as GbquadWindowProvider::onResolutionChanged(): the update is
	// plausibly validated against Nexus's record of THIS window, and the
	// default info's clientID would never match it (the vendor cube demo
	// likewise fills clientID from VUGLES_GetClientID() after creation).
	win_info.clientID = (uint32_t)m_client_id;

	VUGLES_UpdateNativeWindow(m_native_window, &win_info);

	// Force Nexus to re-present the window from scratch - mirrors
	// GbquadWindowProvider's hide/show cycle after its own update.
	VUGLES_SetVisible(m_client_id, false);
	VUGLES_SetVisible(m_client_id, true);

	eDebug("[VuplusWindowProvider] native window resized to %dx%d, clientID=%d", width, height, m_client_id);
}

void VuplusWindowProvider::clearFramebuffer() {
	fbClass* fb = fbClass::getInstance();
	if (fb && fb->lfb && fb->Available() > 0)
		memset(fb->lfb, 0, (size_t)fb->Available());
}

EGLNativeDisplayType VuplusWindowProvider::getNativeDisplay() {
	return EGL_DEFAULT_DISPLAY;
}

EGLNativeWindowType VuplusWindowProvider::getNativeWindow() {
	return (EGLNativeWindowType)m_native_window;
}

void VuplusWindowProvider::cleanup() {
	if (m_native_window) {
		VUGLES_SetVisible(m_client_id, false);
		VUGLES_DestroyNativeWindow(m_native_window);
		m_native_window = nullptr;
		m_client_id = -1;
	}
	if (m_vugles_handle) {
		VUGLES_UnregisterDisplayPlatform(m_vugles_handle);
		m_vugles_handle = nullptr;
	}
	if (m_platform_inited) {
		VUGLES_TermPlatform();
		m_platform_inited = false;
	}
}
