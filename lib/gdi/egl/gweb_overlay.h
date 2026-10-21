#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <string>
#include <sys/types.h>
#ifdef HAVE_GLES3
#include <GLES3/gl3.h>
#else
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#endif
#include <lib/base/ebase.h>

// An external, out-of-process "web" layer (the WPE/HbbTV browser, wpe_fb) composited by
// gEGLDC itself, instead of that process presenting its own second Nexus window:
//
//   producer (wpe_fb)  -- BGRA premultiplied pixels + dirty rows -->  shared memory file
//   producer           -- 1 datagram per frame                    -->  unix socket
//   main thread        -- eSocketNotifier -> requestFlush()       -->  render thread
//   render thread      -- upload dirty rows, one textured quad, blended over the OSD
//
// The GPU does the scaling (view -> canvas), the BGRA->RGBA swizzle and the
// premultiplied "over" blend, so the producer does no scaling, no un-premultiply and no
// colour conversion, and there is no second window to z-order against the OSD.
//
// Threading: startListening()/stopListening() run on the main thread; everything else
// (initGL, sync, draw, destroyGL) on gEGLDC's render thread with the context current.
 
struct gWebOverlayShm {
	uint32_t magic;      // kMagic, written LAST by the producer once the rest is valid
	uint32_t version;    // kVersion
	uint32_t width;      // pixels
	uint32_t height;
	uint32_t stride;     // bytes, must be width * 4
	uint32_t generation; // bumped by the producer whenever width/height change
	uint32_t visible;    // 0 = draw nothing
	int32_t dst_x;       // destination rectangle in OSD canvas pixels;
	int32_t dst_y;       // dst_w <= 0: the whole canvas
	int32_t dst_w;
	int32_t dst_h;
	uint32_t alpha;      // 0..255 global opacity (255 = as delivered)
	uint32_t lock;       // process-shared spin lock guarding the dirty fields
	uint32_t dirty;      // 1 = rows [dirty_y0, dirty_y1) changed since the consumer last looked
	int32_t dirty_y0;
	int32_t dirty_y1;
	uint32_t seq;        // frames written, for diagnostics
	uint32_t pid;        // producer process; the layer is dropped when it is gone (crash)
	int32_t hole_x;      // a rectangle of the frame (frame pixels) that is NOT drawn, so the picture
	int32_t hole_y;      // behind the layer - the live video plane - shows through it (HbbTV
	int32_t hole_w;      // video/broadcast object, "picture in graphics"); hole_w <= 0: no hole
	int32_t hole_h;
};

class gWebOverlay {
public:
	static const uint32_t kMagic = 0x31564f57; // "WOV1"
	static const uint32_t kVersion = 1;
	static const size_t kHeaderBytes = 4096; // pixels start here (page aligned)

	gWebOverlay();
	~gWebOverlay();

	// Main thread. `wake` is called (main thread) whenever the producer announced a
	// change; gEGLDC passes requestFlush().
	void startListening(std::function<void()> wake);
	void stopListening();

	// Render thread, context current.
	bool initGL();
	void destroyGL();
	// Picks up producer changes (mapping, size, dirty rows) - true when there is
	// something to draw. Cheap when nothing changed.
	bool sync();
	// Draws the layer over the current framebuffer (window surface). `canvas_w/h` is
	// the logical OSD size the destination rectangle is expressed in; the viewport must
	// already cover the whole physical surface. Leaves blend enabled, program unbound.
	void draw(int canvas_w, int canvas_h);

private:
	void onSocket(int what);
	void refresh();
	bool mapFile();
	void unmap();
	void upload();
	bool lockShm();
	void unlockShm();

	// main thread
	int m_sock = -1;
	ePtr<eSocketNotifier> m_notifier;
	std::function<void()> m_wake;
	std::string m_sock_path;

	std::atomic<bool> m_changed{false}; // set by the main thread, consumed by sync()

	// render thread
	std::string m_shm_path;
	gWebOverlayShm* m_shm = nullptr;
	size_t m_map_len = 0;
	ino_t m_ino = 0;
	off_t m_file_size = 0;
	uint32_t m_gen = 0;
	int m_max_tex = 2048;

	GLuint m_program = 0;
	GLint m_tex_loc = -1;
	GLint m_alpha_loc = -1;
	GLuint m_texture = 0;
	int m_tex_w = 0;
	int m_tex_h = 0;
	bool m_full_dirty = false;
	bool m_gl_ok = false;
	bool m_logged_active = false;
	int64_t m_next_alive_check_ms = 0;
};
