#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <EGL/egl.h>
#include <lib/base/eerror.h>
#include <lib/gdi/fb.h>
// Must come before <nxclient.h>: this header's NEXUS_HAS_DISPLAY/AUDIO/
// GRAPHICS2D defines and its nexus_hdmi_output_hdcp.h include both need to
// be visible before anything reaches nxclient.h's own chain into
// nexus_core_compat.h/nxclient_global.h - see its own comment for why.
#include <lib/gdi/egl/platform/gbquad/gbquad_window_provider.h>
#include <nxclient.h>

// Logs the window compositor's blend equations (whatever
// NXPL_GetDefaultNativeWindowInfoEXT() returned) and, only when
// ENIGMA_EGL_NXPL_BLEND is set, replaces them - experiment for content whose
// alpha the Nexus compositor composites differently from the OSD hardware the
// non-EGL build relies on. Nexus equation form: a*b +/- c*d +/- e.
//   premult  : color = S*1 + D*(1-Sa)      (source treated as premultiplied)
//   straight : color = S*Sa + D*(1-Sa)     (source treated as straight alpha)
// alpha (both) = Sa*1 + Da*(1-Sa), unless the mode also contains "keepalpha".
static void applyWindowBlendOverride(NXPL_NativeWindowInfoEXT& info, const char* where) {
	auto dump = [&](const char* tag) {
		const NEXUS_BlendEquation& c = info.colorBlend;
		const NEXUS_BlendEquation& a = info.alphaBlend;
		eDebug("[GbquadWindowProvider] %s (%s) colorBlend a=%d b=%d subCD=%d c=%d d=%d subE=%d e=%d | alphaBlend a=%d b=%d subCD=%d c=%d d=%d subE=%d e=%d", tag, where, (int)c.a, (int)c.b,
			   (int)c.subtract_cd, (int)c.c, (int)c.d, (int)c.subtract_e, (int)c.e, (int)a.a, (int)a.b, (int)a.subtract_cd, (int)a.c, (int)a.d, (int)a.subtract_e, (int)a.e);
	};
	dump("window blend defaults");

#ifdef HAVE_NXPL_NO_NXCLIENT
	// Without libnxclient nothing here can change the window's blend: a top-level
	// surface client's composition is server-owned (nexus_surface_client.h) and set
	// from a client only through NxClient_SetSurfaceClientComposition(), which this
	// driver drop doesn't ship (its libnxpl.so imports no NxClient_* symbol at all
	// and never reads colorBlend/alphaBlend). The compositor keeps its default
	// straight-alpha equation, so gEGLDC un-premultiplies the frame instead - see
	// needsStraightAlphaPresent().
	(void)where;
	return;
#endif

	// Default "premult,keepalpha": the OSD content is effectively premultiplied
	// (GL blending over a transparent area, like the CPU framebuffer path),
	// but the compositor's default colour equation is straight-alpha over
	// (S*Sa + D*(1-Sa)), which multiplies by alpha twice and renders
	// translucent overlays over video too dark. Confirmed on gbquad4kpro with
	// the Cosmos infobar-top strip. The default alpha equation is kept.
	// ENIGMA_EGL_NXPL_BLEND=default restores the compositor's own equations;
	// "straight" / "premult" (optionally + ",keepalpha") select others.
	const char* mode = getenv("ENIGMA_EGL_NXPL_BLEND");
	if (!mode)
		mode = "premult,keepalpha";
	if (strstr(mode, "default") != nullptr)
		return;
	const bool premult = strstr(mode, "premult") != nullptr;
	const bool straight = strstr(mode, "straight") != nullptr;
	if (!premult && !straight)
		return;

	NEXUS_BlendEquation color;
	memset(&color, 0, sizeof(color));
	color.a = NEXUS_BlendFactor_eSourceColor;
	color.b = premult ? NEXUS_BlendFactor_eOne : NEXUS_BlendFactor_eSourceAlpha;
	color.subtract_cd = false;
	color.c = NEXUS_BlendFactor_eDestinationColor;
	color.d = NEXUS_BlendFactor_eInverseSourceAlpha;
	color.subtract_e = false;
	color.e = NEXUS_BlendFactor_eZero;

	NEXUS_BlendEquation alpha;
	memset(&alpha, 0, sizeof(alpha));
	alpha.a = NEXUS_BlendFactor_eSourceAlpha;
	alpha.b = NEXUS_BlendFactor_eOne;
	alpha.subtract_cd = false;
	alpha.c = NEXUS_BlendFactor_eDestinationAlpha;
	alpha.d = NEXUS_BlendFactor_eInverseSourceAlpha;
	alpha.subtract_e = false;
	alpha.e = NEXUS_BlendFactor_eZero;

	info.colorBlend = color;
	// "keepalpha": leave the compositor's default alpha equation (Sa + Da) alone
	// and change only the colour equation.
	if (strstr(mode, "keepalpha") == nullptr)
		info.alphaBlend = alpha;
	dump(premult ? "window blend OVERRIDDEN premult" : "window blend OVERRIDDEN straight");
}


// True while the window blend override is premultiplied (the default - see
// applyWindowBlendOverride()), so raw-overwrite draws must write premultiplied
// colour as well.
bool GbquadWindowProvider::premultipliesOverwrites() {
#ifdef HAVE_NXPL_NO_NXCLIENT
	return false; // compositor blends straight alpha, see applyWindowBlendOverride()
#endif
	const char* mode = getenv("ENIGMA_EGL_NXPL_BLEND");
	if (!mode)
		return true;
	return strstr(mode, "default") == nullptr && strstr(mode, "premult") != nullptr;
}

// True when the compositor blends this window as straight alpha, i.e. the window
// blend override could not be applied (no libnxclient) - the premultiplied frame
// must then be un-premultiplied in gEGLDC's present pass or translucent areas
// come out too dark. ENIGMA_EGL_STRAIGHT_ALPHA=0 turns it off (as on VU+).
bool GbquadWindowProvider::needsStraightAlphaPresent() {
#ifdef HAVE_NXPL_NO_NXCLIENT
	static const bool s_enabled = !(getenv("ENIGMA_EGL_STRAIGHT_ALPHA") && atoi(getenv("ENIGMA_EGL_STRAIGHT_ALPHA")) == 0);
	return s_enabled;
#else
	return false;
#endif
}

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
#ifdef HAVE_NXPL_NO_NXCLIENT
	// Zgemma's driver drop ships no libnxclient.so (NxClient_Join doesn't exist
	// there), only a libnexus.so that exports the underlying
	// NEXUS_Platform_AuthenticatedJoin() - what NxClient_Join() calls first.
	// Kodi's runtime NXPL init (stb-kodi 0029-vuplus-arm-runtime-nxpl.patch) uses the
	// same NULL-settings join as its fallback when NxClient_Join is unavailable.
	NEXUS_Error join_rc = NEXUS_Platform_AuthenticatedJoin(nullptr);
	if (join_rc != NEXUS_SUCCESS) {
		eDebug("[GbquadWindowProvider] NEXUS_Platform_AuthenticatedJoin failed, rc=%d", (int)join_rc);
		return false;
	}
#else
	NxClient_JoinSettings joinSettings;
	NxClient_GetDefaultJoinSettings(&joinSettings);
	NEXUS_Error join_rc = NxClient_Join(&joinSettings);
	if (join_rc != NEXUS_SUCCESS) {
		eDebug("[GbquadWindowProvider] NxClient_Join failed, rc=%d", (int)join_rc);
		return false;
	}
#endif
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
	// what actually reaches the TV as enigma2's OSD: /dev/fb0 is only a
	// separate layer beneath it on this stack (unlike Dreambox, where the
	// pixmap surface IS the live framebuffer - see DreamboxWindowProvider).
	NXPL_NativeWindowInfoEXT windowInfo;
	NXPL_GetDefaultNativeWindowInfoEXT(&windowInfo);
	windowInfo.width = (uint32_t)width;
	windowInfo.height = (uint32_t)height;
	windowInfo.x = 0;
	windowInfo.y = 0;
	applyWindowBlendOverride(windowInfo, "init");

	// width/height above are enigma2's OSD/skin canvas size (its own gEGLDC
	// constructor comment) - NOT the current HDMI/video-mode resolution.
	// Nothing calls NXPL_UpdateNativeWindowEXT() when the actual video mode
	// changes later (VideoWizard/VideoSetup only ever write to
	// /proc/stb/video/videomode_*, see Components/AVSwitch.py's setMode()) -
	// `stretch` below is what makes that a non-issue, letting Nexus rescale
	// to whatever the display's current mode is on its own. The OSD canvas
	// SIZE itself (this window's own authored width/height) is a separate
	// thing and does change later, if the loaded skin's resolution differs
	// from whatever this was first constructed with (see
	// gEGLDC::setResolution()) - see onResolutionChanged() below for that.
	// Without this, NXPL_GetDefaultNativeWindowInfoEXT()'s default (false,
	// confirmed by reading default_nexus.h - see this struct's own comment)
	// leaves Nexus's compositor showing this window's canvas pixel-for-pixel
	// against the display's active area instead of scaling it to fit: at any
	// output resolution below the canvas size (e.g. HDMI at 720p against a
	// 1920x1080 canvas) the OSD renders correctly internally but the display
	// only ever shows its unscaled top-left corner - every widget's own pixel
	// size stays literal, so relative to the now-smaller visible frame
	// everything reads as oversized, with the right/bottom edge of the UI
	// simply never reaching the screen. `stretch` (this exact field, same
	// struct - see NXPL_NativeWindowInfoEXT in default_nexus.h from
	// gb-v3ddriver-headers.bb) is Nexus's own per-window "author at a fixed
	// size, scale that to fill the display regardless of its current output
	// resolution" flag - setting it once here covers every later video-mode
	// change too, since re-scaling to the display's current mode is exactly
	// what this flag asks Nexus's compositor to keep doing.
	windowInfo.stretch = true;

	m_native_window = NXPL_CreateNativeWindowEXT(&windowInfo);
	if (!m_native_window) {
		eDebug("[GbquadWindowProvider] NXPL_CreateNativeWindowEXT failed");
		cleanup();
		return false;
	}

	NXPL_ShowNativeWindowEXT(m_native_window, true);

	// 4. fbClass is NOT our render target here, but it is the singleton the
	// rest of enigma2 uses for the framebuffer lock (ImageManager.py's
	// fbClass.getInstance().lock()/unlock() around ofgwrite, gEGLDC::islocked())
	// - and gFBDC, its normal owner, isn't built with EGL (see
	// lib/gdi/Makefile.inc), so without this getInstance() returned None and
	// the lock silently did nothing. SetMode() is required too: unlock()
	// re-applies xRes/yRes/bpp, which only SetMode() initializes. Not fatal on
	// failure - the EGL window above is what actually displays enigma2.
	fbClass* fb = fbClass::getInstance();
	if (!fb)
		fb = new fbClass;
	if (fb->SetMode(width, height, 32) < 0) {
		eDebug("[GbquadWindowProvider] fbClass::SetMode(%dx%d) failed - framebuffer lock unavailable", width, height);
	} else {
		// fb0 is composited UNDER the Nexus window, so anything left in it
		// (boot splash leftovers) would show wherever the OSD is transparent.
		clearFramebuffer();
	}

	eDebug("[GbquadWindowProvider] init %dx%d - Nexus joined, display platform registered, native window shown", width, height);
	return true;
}

void GbquadWindowProvider::onResolutionChanged(int width, int height) {
	if (!m_native_window)
		return;

	// Same struct/fields as init()'s own NXPL_CreateNativeWindowEXT() call -
	// NXPL_GetDefaultNativeWindowInfoEXT() resets stretch to its own default
	// (false, per that call's own comment), so it must be set true again
	// here too, or this update would silently undo the earlier fix for
	// oversized-at-lower-output-resolution rendering.
	NXPL_NativeWindowInfoEXT windowInfo;
	NXPL_GetDefaultNativeWindowInfoEXT(&windowInfo);
	windowInfo.width = (uint32_t)width;
	windowInfo.height = (uint32_t)height;
	windowInfo.x = 0;
	windowInfo.y = 0;
	applyWindowBlendOverride(windowInfo, "resize");
	windowInfo.stretch = true;

	// clientID identifies THIS window to Nexus - default_nexus.h separately
	// exposes NXPL_GetClientID(native) as its own query, which only makes
	// sense if it's a real per-window identity Nexus tracks, not a cosmetic
	// setting. init() never sets it explicitly either (same
	// NXPL_GetDefaultNativeWindowInfoEXT() default this struct already has),
	// which is fine for a brand-new window at NXPL_CreateNativeWindowEXT()
	// time - but NXPL_UpdateNativeWindowEXT() plausibly validates the passed
	// windowInfo against what Nexus has on record for THIS already-existing
	// window, and a default/zero clientID here would never match that,
	// which would explain why both the plain update and a hide/show cycle
	// around it (tried and confirmed safe, but ALSO confirmed not sufficient
	// on real hardware - still oversized/running off screen either way) had
	// no visible effect: the update itself may simply have been silently
	// rejected every time, no error surfaced either way.
	windowInfo.clientID = NXPL_GetClientID(m_native_window);

	NXPL_UpdateNativeWindowEXT(m_native_window, &windowInfo);

	// Kept from the earlier (individually confirmed insufficient, but also
	// confirmed harmless) attempt - forces Nexus to re-present the window
	// from scratch, in case the clientID fix above needs this too to
	// actually take visual effect. Both NXPL_ShowNativeWindowEXT() calls are
	// already-exercised operations on this exact window (see init()/
	// cleanup()), unlike recreating the EGL surface (tried and reverted:
	// locked the box).
	NXPL_ShowNativeWindowEXT(m_native_window, false);
	NXPL_ShowNativeWindowEXT(m_native_window, true);

	eDebug("[GbquadWindowProvider] native window resized to %dx%d, clientID=%u", width, height, windowInfo.clientID);
}

void GbquadWindowProvider::clearFramebuffer() {
	fbClass* fb = fbClass::getInstance();
	if (fb && fb->lfb && fb->Available() > 0)
		memset(fb->lfb, 0, (size_t)fb->Available());
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
#ifdef HAVE_NXPL_NO_NXCLIENT
		NEXUS_Platform_Uninit(); // pairs with NEXUS_Platform_AuthenticatedJoin() in init()
#else
		NxClient_Uninit();
#endif
		m_joined_nxclient = false;
	}
}
