#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <EGL/egl.h>
#include <eglvuplus.h>
#include <lib/base/eerror.h>
#include <lib/gdi/fb.h>
#include <lib/gdi/egl/platform/vuplus/vuplus_window_provider.h>

// Layout of the object VUGLES_CreateNativeWindow()/NXPL_CreateNativeWindowEXT()
// return: its first 0x58 bytes are the NXPL_NativeWindowInfoEXT it was created
// from (NXPL_UpdateNativeWindowEXT() is a memcpy of exactly those bytes) - see
// default_nexus.h. Only the pieces needed here.
static const uint32_t kNxplWindowMagic = 0xabba601d;
static const size_t kNxplWindowMagicOffset = 0x54;

// colorBlend (NEXUS_BlendEquation = {a, b, subtract_cd, c, d, subtract_e, e}) sits
// at +0x1c of that same info, alphaBlend at +0x38.
static const size_t kNxplWindowColorBlendOffset = 0x1c;
// NEXUS_BlendFactor values (nexus_graphics2d.h)
enum { kBlendZero = 0, kBlendOne = 2, kBlendSrcColor = 3, kBlendSrcAlpha = 5, kBlendInvSrcAlpha = 6, kBlendDstColor = 7 };

VuplusWindowProvider::VuplusWindowProvider()
	: m_vugles_handle(nullptr), m_native_window(nullptr), m_client_id(-1), m_platform_inited(false), m_window_resizable(false), m_blend_applied(false) {
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

	const uint32_t* window_words = (const uint32_t*)m_native_window;
	m_window_resizable = window_words[kNxplWindowMagicOffset / 4] == kNxplWindowMagic;
	if (!m_window_resizable)
		eDebug("[VuplusWindowProvider] native window object has no NXPL magic (found 0x%08x) - window will not be resized", window_words[kNxplWindowMagicOffset / 4]);

	applyWindowBlend();

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

	if (!m_window_resizable)
		return;

	// width/height are the first two words of the window object (see
	// kNxplWindowMagic above and the header comment on canResizeWindow() for why
	// VUGLES_UpdateNativeWindow() must not be used). Nothing else about the
	// window - position, stretch, clientID, blend, magic - changes. libnxpl
	// rebuilds the Nexus composition (virtual display = this size) from the
	// window object when gEGLDC recreates the EGL surface right after this.
	uint32_t* window_words = (uint32_t*)m_native_window;
	window_words[0] = (uint32_t)width;
	window_words[1] = (uint32_t)height;

	eDebug("[VuplusWindowProvider] native window resized to %dx%d, clientID=%d", width, height, m_client_id);
}

// Same fix GbquadWindowProvider::applyWindowBlendOverride() applies through
// NXPL_NativeWindowInfoEXT: the OSD frame is premultiplied, the compositor's
// default colour equation (S*Sa + D*(1-Sa)) multiplies by alpha a second time
// and translucent areas come out too dark. libvupl's own window info cannot
// carry blend equations, but the window object IS an NXPL_NativeWindowInfoEXT
// (see kNxplWindowMagic), and libnxpl's window-surface creation callback
// rebuilds the Nexus surface-client composition (virtual display, position,
// colorBlend, alphaBlend) from it every time an EGL window surface is created.
// So the equation has to be changed here, in the window object - changing the
// composition directly (tried first) is overwritten by the next
// eglCreateWindowSurface(). Only done when the object still holds exactly
// NXPL's default equation. ENIGMA_EGL_NXPL_BLEND=default leaves it alone.
void VuplusWindowProvider::applyWindowBlend() {
	const char* mode = getenv("ENIGMA_EGL_NXPL_BLEND");
	if (mode && strstr(mode, "default"))
		return;
	if (!m_window_resizable)
		return; // layout not confirmed (no magic) - do not write into it

	uint32_t* color = (uint32_t*)m_native_window + kNxplWindowColorBlendOffset / 4;
	eDebug("[VuplusWindowProvider] window colorBlend a=%u b=%u subCD=%u c=%u d=%u subE=%u e=%u", color[0], color[1], color[2], color[3], color[4], color[5], color[6]);
	if (color[0] != kBlendSrcColor || color[1] != kBlendSrcAlpha || color[2] != 0 || color[3] != kBlendDstColor || color[4] != kBlendInvSrcAlpha || color[5] != 0 || color[6] != kBlendZero) {
		eDebug("[VuplusWindowProvider] unexpected window colorBlend - left unchanged");
		return;
	}

	color[1] = kBlendOne; // premultiplied: S*1 + D*(1-Sa)
	m_blend_applied = true;
	eDebug("[VuplusWindowProvider] window colour blend set to premultiplied (S + D*(1-Sa)) - applied by the next eglCreateWindowSurface()");
}

bool VuplusWindowProvider::needsStraightAlphaPresent() {
	if (m_blend_applied)
		return false;
	static const bool s_enabled = !(getenv("ENIGMA_EGL_STRAIGHT_ALPHA") && atoi(getenv("ENIGMA_EGL_STRAIGHT_ALPHA")) == 0);
	return s_enabled;
}

bool VuplusWindowProvider::canResizeWindow() {
	const char* env = getenv("ENIGMA_EGL_VUPL_RESIZE");
	if (env && atoi(env) == 0)
		return false;
	return m_window_resizable;
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
