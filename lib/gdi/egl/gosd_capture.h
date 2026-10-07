#pragma once

#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <mutex>
#include <thread>
#include <vector>

class gDC;

// Serves the current OSD to external screenshot tools (aio-grab's "e2egl"
// path, see its getosd_e2egl()) over a UNIX socket. Needed because on a
// window-surface platform (GigaBlue Nexus/NXPL) the OSD lives in a
// compositor-owned surface, not in /dev/fb0 - aio-grab's framebuffer fallback
// there only ever sees an empty OSD, so webif screenshots came out video-only.
//
// Protocol (fixed by aio-grab): on connect the server sends one header
// {char magic[8] = "E2EGL01", uint32 width, height, stride, format = 1 (BGRA)}
// followed by height rows of stride bytes, top-down, then closes. A client
// that gets no header treats the capture as failed.
//
// Threading: accept()/send() run on this class's own thread; the GL readback
// must run on gRC's render thread (the only one with the EGL context current),
// so a request submits a gOpcode::flush to wake it and gEGLDC::flip() hands the
// pixels back via complete()/fail() when isPending().
class gEGLOSDCapture {
public:
	gEGLOSDCapture() = default;
	~gEGLOSDCapture();

	bool start(gDC* dc);
	void stop();

	bool isPending() const { return m_pending.load(std::memory_order_acquire); }

	// Render thread only. `rgba` is raw glReadPixels(GL_RGBA) output (bottom-up
	// rows); conversion to top-down BGRA happens on the capture thread so the
	// render thread only pays for the readback itself. rbSwapped is
	// gles::needsRBSwap: the render target's R/B are already pre-swapped there,
	// so the bytes are BGRA as read.
	void complete(std::vector<uint8_t>& rgba, int width, int height, bool rbSwapped);
	void fail();

private:
	void run();
	void serveClient(int fd);
	bool capture(std::vector<uint8_t>& bgra, int& width, int& height);

	gDC* m_dc = nullptr;
	int m_listen_fd = -1;
	int m_wake_pipe[2] = {-1, -1};
	std::thread m_thread;

	std::mutex m_mutex;
	std::condition_variable m_cond;
	std::atomic<bool> m_pending{false};
	bool m_stopping = false;
	bool m_done = false;
	bool m_failed = false;
	bool m_rb_swapped = false;
	int m_width = 0;
	int m_height = 0;
	std::vector<uint8_t> m_frame;
};
