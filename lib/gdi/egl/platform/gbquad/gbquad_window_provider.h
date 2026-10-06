#pragma once

#include <lib/gdi/egl/inative_window_provider.h>

// nexus_core_compat.h (pulled in below by default_nexus.h, and separately by
// nxclient.h's own chain in the .cpp) provides placeholder typedefs for
// subsystems it assumes nothing else already defined - guarded by #ifndef
// NEXUS_HAS_<X>. But nxclient.h's own includes (nexus_surface_compositor_types.h/
// nexus_types.h) already pull in the REAL, complete display/audio/graphics2d
// type headers first, so nexus_core_compat.h's placeholders for exactly
// those three collide with them ("conflicting declaration"/"redefinition").
// Confirmed by the actual build error: it's specifically and only these
// three that conflict - sage/transport/video-encoder do NOT, meaning their
// real headers are genuinely not part of this include chain and must keep
// using nexus_core_compat.h's placeholders normally (do not add those three
// here without seeing the same conflicting-declaration error first).
#define NEXUS_HAS_DISPLAY 1
#define NEXUS_HAS_AUDIO 1
#define NEXUS_HAS_GRAPHICS2D 1

// Separately: nxclient_global.h (via nxclient.h) references
// NEXUS_HdmiOutputHdcpError and NEXUS_HdmiInputHandle unconditionally, with
// no #ifndef guard. Both are real types that exist in this exact SDK drop -
// NEXUS_HdmiOutputHdcpError in nexus_hdmi_output_hdcp.h, NEXUS_HdmiInputHandle
// in nexus_hdmi_input.h (which the former #includes) - nxclient_global.h
// just never includes either header itself. Actually #including
// nexus_hdmi_output_hdcp.h here was the first attempt at fixing this, but it
// backfires: that header pulls in the complete real nexus_hdmi_output.h/
// nexus_i2c.h, which then conflict with nexus_core_compat.h's placeholders
// for every OTHER HDMI-output/I2C type those headers also declare
// (NEXUS_HdmiOutputHandle, NEXUS_I2cHandle, NEXUS_HdmiOutputStatus, etc.) -
// the same class of collision NEXUS_HAS_DISPLAY/AUDIO/GRAPHICS2D above fixes,
// just for two subsystems we have no reason to also declare fully available.
// So instead of including anything, these two are copied verbatim from the
// real nexus_hdmi_output_hdcp.h/nexus_hdmi_input.h in this exact SDK drop
// (enum values are declaration-order-sequential with no explicit initializers
// in the original, so order here must - and does - match exactly): neither
// name is among nexus_core_compat.h's own placeholders (confirmed: not in
// either conflict list this has produced), so there's nothing left to
// collide with.
typedef struct NEXUS_HdmiInput *NEXUS_HdmiInputHandle;

typedef enum NEXUS_HdmiOutputHdcpError
{
	NEXUS_HdmiOutputHdcpError_eSuccess,
	NEXUS_HdmiOutputHdcpError_eRxBksvError,
	NEXUS_HdmiOutputHdcpError_eRxBksvRevoked,
	NEXUS_HdmiOutputHdcpError_eRxBksvI2cReadError,
	NEXUS_HdmiOutputHdcpError_eTxAksvError,
	NEXUS_HdmiOutputHdcpError_eTxAksvI2cWriteError,
	NEXUS_HdmiOutputHdcpError_eReceiverAuthenticationError,
	NEXUS_HdmiOutputHdcpError_eRepeaterAuthenticationError,
	NEXUS_HdmiOutputHdcpError_eRxDevicesExceeded,
	NEXUS_HdmiOutputHdcpError_eRepeaterDepthExceeded,
	NEXUS_HdmiOutputHdcpError_eRepeaterFifoNotReady,
	NEXUS_HdmiOutputHdcpError_eRepeaterDeviceCount0,
	NEXUS_HdmiOutputHdcpError_eRepeaterLinkFailure,
	NEXUS_HdmiOutputHdcpError_eLinkRiFailure,
	NEXUS_HdmiOutputHdcpError_eLinkPjFailure,
	NEXUS_HdmiOutputHdcpError_eFifoUnderflow,
	NEXUS_HdmiOutputHdcpError_eFifoOverflow,
	NEXUS_HdmiOutputHdcpError_eMultipleAnRequest,
	NEXUS_HdmiOutputHdcpError_eMax
} NEXUS_HdmiOutputHdcpError;

#include <default_nexus.h>

// EGL native-window provider for GigaBlue Quad 4K Pro's Broadcom Nexus stack
// (same BCM7252S SoC/V3D GPU family as Dreambox dm900/dm920, but a different
// vendor middleware layer). Unlike Dreambox's VC5/BEGL stack - which talks to
// the GPU driver directly and has no separate display-owning process - this
// platform uses Broadcom's CLIENT/SERVER Nexus architecture: a privileged
// Nexus server (started at boot, outside enigma2) owns the GPU/display
// memory heaps exclusively, and any process wanting EGL must first join that
// running server (NxClient_Join) and register a Nexus display platform with
// the EGL-Nexus glue layer (NXPL_RegisterNexusDisplayPlatform) before
// eglGetDisplay()/eglInitialize() will succeed - skipping this aborts with a
// Broadcom assertion ("Memory interface not registered", gmem_abstract.c).
//
// Presentation goes through Nexus's own compositor via a genuine EGL window
// surface (NXPL_CreateNativeWindowEXT + eglCreateWindowSurface +
// eglSwapBuffers), not the framebuffer: on this stack /dev/fb0 is a separate
// display layer composited BENEATH that window (ofgwrite's progress screen,
// drawn into fb0, showed up under enigma2's UI), unlike Dreambox (where the
// "pixmap" surface IS the live framebuffer memory - see
// DreamboxWindowProvider). So usesPixmapSurface() stays at its base-class
// default of false and gEGLDC's existing generic eglCreateWindowSurface/
// eglSwapBuffers path (see gegldc.cpp's tryInitEGL()) needs no changes at
// all for this platform.
//
// nxclient.h/default_nexus.h are the real vendor headers, staged into the
// normal sysroot include dir by oe-alliance-core's gb-v3ddriver-headers.bb
// (meta-brands/meta-gigablue/recipes-graphics/libgles); libnxclient.so/
// libnxpl.so/libnexus.so are linked normally via the "nxpl" pkg-config
// module gb-v3ddriver.inc installs (see configure.ac's HAVE_GBQUAD_EGL
// block and main/Makefile.am's @NXPL_LIBS@) - no dlopen/dlsym needed. This
// mirrors the fix validated on real gbquad4kpro hardware by the reference
// HbbTV2 EGL port (xcentaurix/hbbtv2, WebKit patch "join and register with
// Nexus before any EGL call").
//
// Zgemma's h7/h17 (BCM7251S, meta-airdigital's airdigital-v3ddriver) ship the same
// libnxpl/libnexus/libv3ddriver trio but no libnxclient.so, so those boxes define
// HAVE_NXPL_NO_NXCLIENT and join with NEXUS_Platform_AuthenticatedJoin(NULL) instead
// (see init()). Their libnxpl.so was disassembled to confirm the rest matches:
// NXPL_NativeWindowInfoEXT is the same 0x58-byte layout (colorBlend at 0x1c,
// alphaBlend at 0x38, magic at 0x54) and NXPL_CreateNativeWindowEXT ends in
// NEXUS_SurfaceClient_Acquire(info.clientID), as on GigaBlue.
class GbquadWindowProvider : public INativeWindowProvider {
private:
	NXPL_PlatformHandle m_nxpl_display_handle; // handle from NXPL_RegisterNexusDisplayPlatform
	void* m_native_window;                     // handle from NXPL_CreateNativeWindowEXT
	bool m_joined_nxclient;                    // NxClient_Join() succeeded - must be balanced by NxClient_Uninit()

public:
	GbquadWindowProvider();
	virtual ~GbquadWindowProvider();

	// INativeWindowProvider
	bool init(int width, int height) override;
	EGLNativeDisplayType getNativeDisplay() override;
	EGLNativeWindowType getNativeWindow() override;
	void cleanup() override;
	void onFramebufferUnlocked() override { clearFramebuffer(); }
	bool premultipliesOverwrites() override;
	bool needsStraightAlphaPresent() override;
	float presentUnpremultiplyPower() override;
	bool premultipliesBlits() override;

	// `stretch` (set in init(), see its own comment there) makes Nexus's
	// compositor scale THIS window's authored width/height to fill the
	// display regardless of the current output resolution - but nothing
	// updates that authored size if the OSD canvas itself changes size
	// after init() already ran (e.g. a skin whose resolution differs from
	// whatever this was constructed with - see gEGLDC::setResolution()).
	// Without this, content gets rendered for the new canvas size but
	// Nexus keeps scaling as if the window were still its original size -
	// every widget's position/size reads as wrong relative to the display.
	void onResolutionChanged(int width, int height) override;

	// Zeroes /dev/fb0 (fully transparent) - it's a display layer beneath this
	// provider's window, so stale content there (ofgwrite's progress screen
	// after a failed flash, boot leftovers) shows through transparent OSD.
	static void clearFramebuffer();
};
