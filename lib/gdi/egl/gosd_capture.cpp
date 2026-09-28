#include <cerrno>
#include <chrono>
#include <cstring>
#include <fcntl.h>
#include <poll.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <utility>
#include <lib/base/eerror.h>
#include <lib/gdi/egl/gosd_capture.h>
#include <lib/gdi/grc.h>

#define OSD_CAPTURE_SOCKET "/tmp/e2egl-osd.socket"
#define OSD_CAPTURE_FORMAT_BGRA 1U

namespace {

struct CaptureHeader {
	char magic[8];
	uint32_t width;
	uint32_t height;
	uint32_t stride;
	uint32_t format;
};

const char capture_magic[8] = {'E', '2', 'E', 'G', 'L', '0', '1', 0};

// aio-grab gives up after 2s without data (SO_RCVTIMEO); stay below that so a
// busy render thread yields a clean "no header" failure instead of a
// half-written image.
const auto render_wait = std::chrono::milliseconds(1500);

bool sendAll(int fd, const void* data, size_t len) {
	const uint8_t* ptr = static_cast<const uint8_t*>(data);
	while (len) {
		ssize_t n = send(fd, ptr, len, MSG_NOSIGNAL);
		if (n < 0) {
			if (errno == EINTR)
				continue;
			return false;
		}
		ptr += n;
		len -= (size_t)n;
	}
	return true;
}

} // namespace

gEGLOSDCapture::~gEGLOSDCapture() {
	stop();
}

bool gEGLOSDCapture::start(gDC* dc) {
	if (m_thread.joinable())
		return true;

	m_dc = dc;
	m_stopping = false;

	m_listen_fd = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
	if (m_listen_fd < 0) {
		eDebug("[gEGLOSDCapture] socket failed: %m");
		return false;
	}

	sockaddr_un addr;
	memset(&addr, 0, sizeof(addr));
	addr.sun_family = AF_UNIX;
	strncpy(addr.sun_path, OSD_CAPTURE_SOCKET, sizeof(addr.sun_path) - 1);

	// A previous enigma2 that crashed leaves the socket file behind; bind()
	// would fail on it.
	unlink(OSD_CAPTURE_SOCKET);
	if (bind(m_listen_fd, (sockaddr*)&addr, sizeof(addr)) < 0 || listen(m_listen_fd, 2) < 0) {
		eDebug("[gEGLOSDCapture] bind/listen on %s failed: %m", OSD_CAPTURE_SOCKET);
		close(m_listen_fd);
		m_listen_fd = -1;
		return false;
	}

	if (pipe2(m_wake_pipe, O_CLOEXEC) < 0) {
		eDebug("[gEGLOSDCapture] pipe failed: %m");
		close(m_listen_fd);
		m_listen_fd = -1;
		unlink(OSD_CAPTURE_SOCKET);
		return false;
	}

	m_thread = std::thread(&gEGLOSDCapture::run, this);
	eDebug("[gEGLOSDCapture] serving OSD captures on %s", OSD_CAPTURE_SOCKET);
	return true;
}

void gEGLOSDCapture::stop() {
	if (!m_thread.joinable())
		return;

	{
		std::lock_guard<std::mutex> lock(m_mutex);
		m_stopping = true;
	}
	// Release a capture waiting on the render thread - stop() is normally
	// called FROM the render thread (gEGLDC::cleanupEGL()), which will never
	// service it now.
	m_cond.notify_all();
	if (write(m_wake_pipe[1], "x", 1) < 0) {
		// Nothing more to do: poll() below also returns on the closed fds.
	}
	m_thread.join();

	close(m_listen_fd);
	close(m_wake_pipe[0]);
	close(m_wake_pipe[1]);
	m_listen_fd = m_wake_pipe[0] = m_wake_pipe[1] = -1;
	unlink(OSD_CAPTURE_SOCKET);
	m_pending.store(false, std::memory_order_release);
	m_frame.clear();
	m_frame.shrink_to_fit();
}

void gEGLOSDCapture::run() {
	for (;;) {
		pollfd fds[2];
		fds[0].fd = m_listen_fd;
		fds[0].events = POLLIN;
		fds[1].fd = m_wake_pipe[0];
		fds[1].events = POLLIN;
		if (poll(fds, 2, -1) < 0) {
			if (errno == EINTR)
				continue;
			eDebug("[gEGLOSDCapture] poll failed: %m");
			return;
		}
		if (fds[1].revents)
			return;
		if (!(fds[0].revents & POLLIN))
			continue;

		int client = accept4(m_listen_fd, nullptr, nullptr, SOCK_CLOEXEC);
		if (client < 0)
			continue;
		serveClient(client);
		close(client);
	}
}

void gEGLOSDCapture::serveClient(int fd) {
	timeval timeout;
	timeout.tv_sec = 2;
	timeout.tv_usec = 0;
	setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));

	std::vector<uint8_t> frame;
	int width = 0, height = 0;
	if (!capture(frame, width, height))
		return; // closing without a header is the protocol's failure signal

	CaptureHeader header;
	memcpy(header.magic, capture_magic, sizeof(header.magic));
	header.width = (uint32_t)width;
	header.height = (uint32_t)height;
	header.stride = (uint32_t)width * 4U;
	header.format = OSD_CAPTURE_FORMAT_BGRA;

	if (!sendAll(fd, &header, sizeof(header)) || !sendAll(fd, frame.data(), frame.size()))
		eDebug("[gEGLOSDCapture] client went away during send: %m");
}

bool gEGLOSDCapture::capture(std::vector<uint8_t>& bgra, int& width, int& height) {
	gRC* rc = gRC::getInstance();
	// A locked DC means ofgwrite owns the framebuffer (see gEGLDC::islocked()) -
	// don't force a present into the middle of a flash.
	if (!rc || !m_dc || m_dc->islocked())
		return false;

	std::unique_lock<std::mutex> lock(m_mutex);
	if (m_stopping)
		return false;
	m_done = false;
	m_failed = false;
	m_pending.store(true, std::memory_order_release);
	lock.unlock();

	// Wake the render thread: gEGLDC::flip() services the request at the next
	// frame boundary, and a flush guarantees one happens even on an idle UI.
	// gRC::submit() is mutex-protected, and o.dc's reference is released by
	// the render thread after exec() like any other opcode.
	gOpcode o;
	o.opcode = gOpcode::flush;
	m_dc->AddRef();
	o.dc = m_dc;
	rc->submit(o);

	lock.lock();
	bool signalled = m_cond.wait_for(lock, render_wait, [this] { return m_done || m_stopping; });
	m_pending.store(false, std::memory_order_release);
	if (!signalled || !m_done || m_failed) {
		if (!signalled)
			eDebug("[gEGLOSDCapture] render thread did not service the capture in time");
		return false;
	}

	width = m_width;
	height = m_height;
	bool rb_swapped = m_rb_swapped;
	bgra.swap(m_frame);
	m_frame.clear();
	lock.unlock();

	// glReadPixels rows are bottom-up (the shaders' projection puts screen
	// y=0 at the top of the GL framebuffer); the protocol wants top-down BGRA.
	const size_t row_bytes = (size_t)width * 4U;
	std::vector<uint8_t> tmp(row_bytes);
	for (int y = 0; y < height / 2; ++y) {
		uint8_t* top = bgra.data() + (size_t)y * row_bytes;
		uint8_t* bottom = bgra.data() + (size_t)(height - 1 - y) * row_bytes;
		memcpy(tmp.data(), top, row_bytes);
		memcpy(top, bottom, row_bytes);
		memcpy(bottom, tmp.data(), row_bytes);
	}
	if (!rb_swapped) {
		for (size_t i = 0; i < bgra.size(); i += 4)
			std::swap(bgra[i], bgra[i + 2]);
	}
	return true;
}

void gEGLOSDCapture::complete(std::vector<uint8_t>& rgba, int width, int height, bool rbSwapped) {
	{
		std::lock_guard<std::mutex> lock(m_mutex);
		// The requester may already have timed out; its answer is gone.
		if (!m_pending.load(std::memory_order_acquire) || m_done)
			return;
		m_frame.swap(rgba);
		m_width = width;
		m_height = height;
		m_rb_swapped = rbSwapped;
		m_failed = false;
		m_done = true;
	}
	m_cond.notify_all();
}

void gEGLOSDCapture::fail() {
	{
		std::lock_guard<std::mutex> lock(m_mutex);
		if (!m_pending.load(std::memory_order_acquire) || m_done)
			return;
		m_failed = true;
		m_done = true;
	}
	m_cond.notify_all();
}
