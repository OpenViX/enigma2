#pragma once

// HDR10 OSD brightness for Broadcom Nexus platforms (GigaBlue, VU+): raises the compositor's
// gain for the SDR OSD through NxClient_SetPictureQualitySettings() so that SDR white lands at a
// given level in a PQ (HDR10) output. Used by gEGLDC's HDR10 tone mapping (see
// gEGLDC::updateToneControl()), which assumes the same white level. Header-only so every Nexus
// window provider shares one copy.
//
// NxClient_PictureQualitySettings is four int16 (contrast, saturation, hue, brightness) - the
// layout verified on device with osd_hdr_brightness.py. The symbols are looked up at run time
// instead of linked, in whatever library exports them: libnxclient.so on GigaBlue, VU+'s
// libdvb_client.so (it bundles the NxClient API; there is no libnxclient there). A process
// without them just reports "no control" and the tone mapping stays off. The current settings
// are read first so that only contrast and saturation are ever changed.

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <dlfcn.h>
#include <lib/base/eerror.h>

namespace nexus_hdr_osd {

// SMPTE ST 2084 inverse EOTF: absolute luminance (cd/m2) -> signal 0..1.
inline double pq(double nits)
{
	const double m1 = 2610.0 / 16384, m2 = 2523.0 / 4096 * 128;
	const double c1 = 3424.0 / 4096, c2 = 2413.0 / 4096 * 32, c3 = 2392.0 / 4096 * 32;
	const double y = std::pow(nits / 10000.0, m1);
	return std::pow((c1 + c2 * y) / (1 + c3 * y), m2);
}

// Graphics contrast/saturation value that puts SDR white at `nits` (derived from
// BVDC_P_Cfc_ApplyContrast/ApplySaturationAndHue in nexus.ko: gain = 1 + 3*v/32767 for v > 0,
// (v + 32768)/32768 for v <= 0, on top of the default 100-nit level, PQ 0.508078). Contrast
// scales luma, saturation scales chroma with the same formula, so setting both keeps the balance.
inline int16_t gfxValueForNits(double nits)
{
	const double g = pq(nits) / 0.508078;
	const double v = g >= 1.0 ? (g - 1.0) * 32767.0 / 3.0 : g * 32768.0 - 32768.0;
	return (int16_t)std::max(-32768.0, std::min(32767.0, std::round(v)));
}

// `joined`: this process is a Nexus client (NxClient_Join succeeded, here or inside the
// platform library). nits <= 0 restores the default. Returns true when the driver accepted it.
inline bool setWhiteNits(float nits, bool joined, const char *tag)
{
	typedef int (*SetPqFn)(const void *);
	typedef void (*GetPqFn)(void *);
	static SetPqFn setPq = nullptr;
	static GetPqFn getPq = nullptr;
	static bool looked_up = false;
	if (!looked_up) {
		looked_up = true;
		// A library the platform layer loaded privately is not in the global scope, so also
		// try the usual carriers by name (RTLD_NOLOAD: only if already loaded).
		static const char *names[] = {nullptr, "libnxclient.so", "libnxclient.so.0", "libdvb_client.so", "libdvb_base.so"};
		for (const char *n : names) {
			void *h = n ? dlopen(n, RTLD_LAZY | RTLD_NOLOAD) : RTLD_DEFAULT;
			if (!h)
				continue;
			setPq = (SetPqFn)dlsym(h, "NxClient_SetPictureQualitySettings");
			if (setPq) {
				getPq = (GetPqFn)dlsym(h, "NxClient_GetPictureQualitySettings");
				break;
			}
		}
		if (!setPq)
			eDebug("[%s] HDR10 OSD gain: NxClient_SetPictureQualitySettings not available", tag);
	}
	if (!setPq || !joined)
		return false;
	int16_t pq_settings[32] = {0}; // 64 bytes: the real struct is 8, with slack like the script's buffer
	if (getPq)
		getPq(pq_settings); // keep whatever else is set; only contrast/saturation change below
	pq_settings[0] = pq_settings[1] = nits > 0.0f ? gfxValueForNits(nits) : 0;
	const int rc = setPq(pq_settings);
	eDebug("[%s] HDR10 OSD gain: SDR white %.0f nits -> contrast=saturation=%d (rc=%d)", tag, nits > 0.0f ? nits : 100.0f, (int)pq_settings[0], rc);
	return rc == 0;
}

} // namespace nexus_hdr_osd
