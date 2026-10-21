#include <lib/gdi/egl/gweb_overlay.h>
#include <lib/gdi/egl/gles_version.h>
#include <lib/base/eerror.h>
#include <libsig_comp.h>

#include <utility>
#include <errno.h>
#include <signal.h>
#include <time.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <unistd.h>

// GLSL ES 1.00 is accepted by GLES2 and GLES3 contexts alike, so one pair of sources serves
// every platform (the same reasoning as gshader's ES2 fallbacks).
//
// The producer delivers WPE's native memory order, B,G,R,A (Skia kBGRA_8888, premultiplied).
// It is uploaded as plain GL_RGBA - the swizzle happens here, so neither the producer nor
// the driver needs GL_BGRA_EXT.
static const char* overlay_vs = R"(#version 100
    attribute vec4 pos_uv;
    varying vec2 v_uv;
    void main() {
        gl_Position = vec4(pos_uv.xy, 0.0, 1.0);
        v_uv = pos_uv.zw;
    }
)";

static const char* overlay_fs_swizzle = R"(#version 100
    precision mediump float;
    varying vec2 v_uv;
    uniform sampler2D u_texture;
    uniform float u_alpha;
    void main() {
        gl_FragColor = texture2D(u_texture, v_uv).bgra * u_alpha;
    }
)";

// Platforms whose scanout reads the render target with R and B exchanged (Dreambox, see
// gles::needsRBSwap) get the producer's B,G,R,A bytes unswizzled: sampled as r=B, g=G, b=R and
// written as is, the display swaps them back into the right colours - the same rule the
// pixmap uploads of gtexture_manager follow.
static const char* overlay_fs_raw = R"(#version 100
    precision mediump float;
    varying vec2 v_uv;
    uniform sampler2D u_texture;
    uniform float u_alpha;
    void main() {
        gl_FragColor = texture2D(u_texture, v_uv) * u_alpha;
    }
)";

static GLuint compile(GLenum type, const char* src)
{
	GLuint s = glCreateShader(type);
	glShaderSource(s, 1, &src, nullptr);
	glCompileShader(s);
	GLint ok = 0;
	glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
	if (!ok) {
		char log[512] = "";
		glGetShaderInfoLog(s, sizeof(log) - 1, nullptr, log);
		eDebug("[gWebOverlay] shader compile failed: %s", log);
		glDeleteShader(s);
		return 0;
	}
	return s;
}

static std::string basePath()
{
	const char* env = getenv("ENIGMA_WEB_OVERLAY_PATH");
	return env && *env ? env : "/tmp/e2_webov";
}
 
gWebOverlay::gWebOverlay()
{
	const std::string base = basePath();
	m_shm_path = base + ".shm";
	m_sock_path = base + ".sock";
}

gWebOverlay::~gWebOverlay()
{
	stopListening();
	unmap();
}

// ----------------------------------------------------------------------------------------
// main thread
// ----------------------------------------------------------------------------------------

bool gWebOverlay::bindSocket()
{
	int fd = socket(AF_UNIX, SOCK_DGRAM | SOCK_NONBLOCK | SOCK_CLOEXEC, 0);
	if (fd < 0) {
		eDebug("[gWebOverlay] socket: %m");
		return false;
	}
	sockaddr_un addr;
	memset(&addr, 0, sizeof(addr));
	addr.sun_family = AF_UNIX;
	if (m_sock_path.size() >= sizeof(addr.sun_path)) {
		close(fd);
		return false;
	}
	strcpy(addr.sun_path, m_sock_path.c_str());
	unlink(m_sock_path.c_str());
	if (bind(fd, (sockaddr*)&addr, sizeof(addr)) < 0) {
		eDebug("[gWebOverlay] bind %s: %m", m_sock_path.c_str());
		close(fd);
		return false;
	}
	struct stat st;
	m_sock_ino = stat(m_sock_path.c_str(), &st) == 0 ? st.st_ino : 0;
	m_sock = fd;
	m_notifier = eSocketNotifier::create(eApp, m_sock, eSocketNotifier::Read);
	CONNECT(m_notifier->activated, gWebOverlay::onSocket);
	return true;
}

void gWebOverlay::startListening(std::function<void()> wake)
{
	if (m_sock >= 0)
		return;
	if (!eApp) {
		eDebug("[gWebOverlay] no main loop yet - not listening");
		return;
	}
	m_wake = std::move(wake);
	if (!bindSocket())
		return;
	eDebug("[gWebOverlay] listening on %s, frames from %s", m_sock_path.c_str(), m_shm_path.c_str());
	m_heal = eTimer::create(eApp);
	CONNECT(m_heal->timeout, gWebOverlay::onHeal);
	m_heal->start(1000, false);
}

// The producer addresses the socket by path. If the file is gone or belongs to someone else (a second
// gEGLDC bound the same path and the first one's teardown removed it, a tmp cleaner ...), the producer's
// datagrams go nowhere and the layer never updates: bind again, and look at the frame file once.
void gWebOverlay::onHeal()
{
	if (m_sock < 0)
		return;
	struct stat st;
	if (stat(m_sock_path.c_str(), &st) == 0 && st.st_ino == m_sock_ino)
		return;
	eDebug("[gWebOverlay] socket %s was removed or replaced - binding it again", m_sock_path.c_str());
	m_notifier = 0;
	close(m_sock);
	m_sock = -1;
	if (!bindSocket())
		return;
	m_changed = true;
	if (m_wake)
		m_wake();
}

void gWebOverlay::stopListening()
{
	m_heal = 0;
	m_notifier = 0;
	if (m_sock >= 0) {
		close(m_sock);
		struct stat st;
		if (stat(m_sock_path.c_str(), &st) == 0 && st.st_ino == m_sock_ino)
			unlink(m_sock_path.c_str());
		m_sock = -1;
	}
}

void gWebOverlay::onSocket(int)
{
	char buf[64];
	while (recv(m_sock, buf, sizeof(buf), 0) > 0) {
	}
	m_changed = true;
	if (m_wake)
		m_wake();
}

// ----------------------------------------------------------------------------------------
// render thread: GL objects
// ----------------------------------------------------------------------------------------

bool gWebOverlay::initGL()
{
	GLint max_tex = 0;
	glGetIntegerv(GL_MAX_TEXTURE_SIZE, &max_tex);
	if (max_tex > 0)
		m_max_tex = max_tex;

	GLuint vs = compile(GL_VERTEX_SHADER, overlay_vs);
	GLuint fs = compile(GL_FRAGMENT_SHADER, gles::needsRBSwap ? overlay_fs_raw : overlay_fs_swizzle);
	if (!vs || !fs) {
		if (vs)
			glDeleteShader(vs);
		if (fs)
			glDeleteShader(fs);
		return false;
	}
	m_program = glCreateProgram();
	glBindAttribLocation(m_program, 0, "pos_uv");
	glAttachShader(m_program, vs);
	glAttachShader(m_program, fs);
	glLinkProgram(m_program);
	glDeleteShader(vs);
	glDeleteShader(fs);
	GLint ok = 0;
	glGetProgramiv(m_program, GL_LINK_STATUS, &ok);
	if (!ok) {
		eDebug("[gWebOverlay] program link failed");
		glDeleteProgram(m_program);
		m_program = 0;
		return false;
	}
	m_tex_loc = glGetUniformLocation(m_program, "u_texture");
	m_alpha_loc = glGetUniformLocation(m_program, "u_alpha");
	m_gl_ok = true;
	return true;
}

void gWebOverlay::destroyGL()
{
	if (m_texture)
		glDeleteTextures(1, &m_texture);
	m_texture = 0;
	m_tex_w = m_tex_h = 0;
	if (m_program)
		glDeleteProgram(m_program);
	m_program = 0;
	m_gl_ok = false;
}

// ----------------------------------------------------------------------------------------
// render thread: the shared frame
// ----------------------------------------------------------------------------------------

void gWebOverlay::unmap()
{
	if (m_shm)
		munmap(m_shm, m_map_len);
	m_shm = nullptr;
	m_map_len = 0;
	m_ino = 0;
	m_file_size = 0;
}

bool gWebOverlay::mapFile()
{
	int fd = open(m_shm_path.c_str(), O_RDWR | O_CLOEXEC);
	if (fd < 0)
		return false;
	struct stat st;
	if (fstat(fd, &st) < 0 || (size_t)st.st_size < kHeaderBytes + 4) {
		close(fd);
		return false;
	}
	void* p = mmap(nullptr, (size_t)st.st_size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
	close(fd);
	if (p == MAP_FAILED)
		return false;
	gWebOverlayShm* h = (gWebOverlayShm*)p;
	const uint32_t magic = __atomic_load_n(&h->magic, __ATOMIC_ACQUIRE);
	const size_t need = kHeaderBytes + (size_t)h->stride * h->height;
	if (magic != kMagic || h->version != kVersion || h->width == 0 || h->height == 0 ||
		(int)h->width > m_max_tex || (int)h->height > m_max_tex || h->stride != h->width * 4 || (size_t)st.st_size < need) {
		munmap(p, (size_t)st.st_size);
		return false;
	}
	m_shm = h;
	m_map_len = (size_t)st.st_size;
	m_ino = st.st_ino;
	m_file_size = st.st_size;
	m_gen = h->generation;
	m_tex_w = m_tex_h = 0; // the texture is (re)allocated in upload()
	m_full_dirty = true;
	return true;
}

// Re-evaluates what the producer has published: the file may be new (a new wpe_fb), replaced,
// resized or gone.
void gWebOverlay::refresh()
{
	struct stat st;
	if (stat(m_shm_path.c_str(), &st) != 0) {
		unmap();
		return;
	}
	if (m_shm && (st.st_ino != m_ino || st.st_size != m_file_size || m_shm->generation != m_gen))
		unmap();
	if (!m_shm && !mapFile())
		return;
}

bool gWebOverlay::lockShm()
{
	for (int i = 0; i < 2000; ++i) {
		if (!__atomic_exchange_n(&m_shm->lock, 1u, __ATOMIC_ACQUIRE))
			return true;
	}
	return false; // a crashed producer can leave it set: never hang the render thread
}

void gWebOverlay::unlockShm()
{
	__atomic_store_n(&m_shm->lock, 0u, __ATOMIC_RELEASE);
}

void gWebOverlay::upload()
{
	const int w = (int)m_shm->width, h = (int)m_shm->height;
	if (!m_texture)
		glGenTextures(1, &m_texture);
	glActiveTexture(GL_TEXTURE0);
	glBindTexture(GL_TEXTURE_2D, m_texture);
	glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
	const uint8_t* pixels = (const uint8_t*)m_shm + kHeaderBytes;

	if (m_tex_w != w || m_tex_h != h) {
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
		glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, pixels);
		m_tex_w = w;
		m_tex_h = h;
		m_full_dirty = false;
		// whatever the producer marked dirty so far is part of this upload
		if (lockShm()) {
			m_shm->dirty = 0;
			unlockShm();
		}
		glBindTexture(GL_TEXTURE_2D, 0);
		return;
	}

	int y0 = 0, y1 = 0;
	bool have = false;
	if (m_full_dirty) {
		y0 = 0;
		y1 = h;
		have = true;
		m_full_dirty = false;
	}
	if (__atomic_load_n(&m_shm->dirty, __ATOMIC_ACQUIRE)) {
		if (lockShm()) {
			int a = m_shm->dirty_y0, b = m_shm->dirty_y1;
			m_shm->dirty = 0;
			unlockShm();
			if (a < 0)
				a = 0;
			if (b > h)
				b = h;
			if (b > a) {
				y0 = have ? (a < y0 ? a : y0) : a;
				y1 = have ? (b > y1 ? b : y1) : b;
				have = true;
			}
		} else
			m_changed = true; // try again next frame
	}
	// Whole rows only: plain GLES2 has no GL_UNPACK_ROW_LENGTH, and the hbbtv2 measurements on
	// this GPU family found narrow sub-rectangle uploads pathologically slow (tiled textures),
	// while a full-width band is one linear copy. A row still being written when we read it is
	// simply dirty again - the producer marks it after its copy - so the next frame fixes it.
	//
	// Diagnostic, ENIGMA_WEB_OVERLAY_UPLOAD (read once): "rows" = the dirty rows only (default);
	// "full" = the whole frame with glTexSubImage2D whenever anything changed (rules out the dirty
	// bookkeeping); "orphan" = the whole frame with glTexImage2D, i.e. new storage every time, so
	// the texture is never modified while a frame still in flight on the GPU reads it (this
	// driver is known to corrupt a texture updated after earlier draws used it, see gegldc.cpp's
	// atlas band textures).
	static const int mode = []() {
		const char* e = getenv("ENIGMA_WEB_OVERLAY_UPLOAD");
		if (e && !strcmp(e, "full"))
			return 1;
		if (e && !strcmp(e, "orphan"))
			return 2;
		return 0;
	}();
	if (have && mode == 2) {
		glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, pixels);
	} else if (have && y1 > y0) {
		if (mode == 1) {
			y0 = 0;
			y1 = h;
		}
		glTexSubImage2D(GL_TEXTURE_2D, 0, 0, y0, w, y1 - y0, GL_RGBA, GL_UNSIGNED_BYTE, pixels + (size_t)y0 * m_shm->stride);
	}
	glBindTexture(GL_TEXTURE_2D, 0);
}

bool gWebOverlay::sync()
{
	if (!m_gl_ok)
		return false;
	if (m_changed.exchange(false))
		refresh();
	if (m_shm && __atomic_load_n(&m_shm->visible, __ATOMIC_ACQUIRE)) {
		// A producer that crashed cannot hide its layer: drop it once its process is gone.
		timespec ts;
		clock_gettime(CLOCK_MONOTONIC, &ts);
		const int64_t now_ms = (int64_t)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
		if (now_ms >= m_next_alive_check_ms) {
			m_next_alive_check_ms = now_ms + 1000;
			if (m_shm->pid && kill((pid_t)m_shm->pid, 0) != 0 && errno == ESRCH) {
				eDebug("[gWebOverlay] producer %u is gone - dropping the layer", m_shm->pid);
				unmap();
				unlink(m_shm_path.c_str());
			}
		}
	}
	if (!m_shm || !__atomic_load_n(&m_shm->visible, __ATOMIC_ACQUIRE)) {
		if (m_logged_active) {
			m_logged_active = false;
			eDebug("[gWebOverlay] layer hidden");
		}
		return false;
	}
	upload();
	if (!m_logged_active) {
		m_logged_active = true;
		eDebug("[gWebOverlay] layer visible: %ux%u frame, texture limit %d", m_shm->width, m_shm->height, m_max_tex);
	}
	return m_texture != 0;
}

void gWebOverlay::draw(int canvas_w, int canvas_h)
{
	if (!m_program || !m_texture || !m_shm || canvas_w <= 0 || canvas_h <= 0)
		return;

	float x = 0.0f, y = 0.0f, w = (float)canvas_w, h = (float)canvas_h;
	if (m_shm->dst_w > 0 && m_shm->dst_h > 0) {
		x = (float)m_shm->dst_x;
		y = (float)m_shm->dst_y;
		w = (float)m_shm->dst_w;
		h = (float)m_shm->dst_h;
	}
	// The frame is drawn in up to four pieces around the hole (if any): above, below, left and right
	// of it. Each piece is a rectangle of the frame (frame pixels) mapped onto the same rectangle of
	// the destination, so the pieces join seamlessly and the hole shows what is behind the layer.
	const float fw = (float)m_shm->width, fh = (float)m_shm->height;
	float pieces[4][4]; // fx0, fy0, fx1, fy1
	int npieces = 0;
	int hx0 = 0, hy0 = 0, hx1 = 0, hy1 = 0;
	if (m_shm->hole_w > 0 && m_shm->hole_h > 0) {
		hx0 = m_shm->hole_x < 0 ? 0 : m_shm->hole_x;
		hy0 = m_shm->hole_y < 0 ? 0 : m_shm->hole_y;
		hx1 = m_shm->hole_x + m_shm->hole_w > (int)fw ? (int)fw : m_shm->hole_x + m_shm->hole_w;
		hy1 = m_shm->hole_y + m_shm->hole_h > (int)fh ? (int)fh : m_shm->hole_y + m_shm->hole_h;
	}
	if (hx1 > hx0 && hy1 > hy0) {
		if (hy0 > 0) { pieces[npieces][0] = 0; pieces[npieces][1] = 0; pieces[npieces][2] = fw; pieces[npieces][3] = (float)hy0; ++npieces; }
		if (hy1 < (int)fh) { pieces[npieces][0] = 0; pieces[npieces][1] = (float)hy1; pieces[npieces][2] = fw; pieces[npieces][3] = fh; ++npieces; }
		if (hx0 > 0) { pieces[npieces][0] = 0; pieces[npieces][1] = (float)hy0; pieces[npieces][2] = (float)hx0; pieces[npieces][3] = (float)hy1; ++npieces; }
		if (hx1 < (int)fw) { pieces[npieces][0] = (float)hx1; pieces[npieces][1] = (float)hy0; pieces[npieces][2] = fw; pieces[npieces][3] = (float)hy1; ++npieces; }
	} else {
		pieces[0][0] = 0; pieces[0][1] = 0; pieces[0][2] = fw; pieces[0][3] = fh;
		npieces = 1;
	}
	if (npieces == 0)
		return;

	// canvas pixels -> clip space; the framebuffer is top-down like the texture, so the top edge
	// (canvas y = 0, texture v = 0) is clip y = +1.
	float quad[4 * 24];
	for (int i = 0; i < npieces; ++i) {
		const float u0 = pieces[i][0] / fw, v0 = pieces[i][1] / fh, u1 = pieces[i][2] / fw, v1 = pieces[i][3] / fh;
		const float x0 = 2.0f * (x + u0 * w) / canvas_w - 1.0f, x1 = 2.0f * (x + u1 * w) / canvas_w - 1.0f;
		const float y0 = 1.0f - 2.0f * (y + v0 * h) / canvas_h, y1 = 1.0f - 2.0f * (y + v1 * h) / canvas_h;
		const float q[24] = {
			x0, y0, u0, v0,  x0, y1, u0, v1,  x1, y0, u1, v0,
			x1, y0, u1, v0,  x0, y1, u0, v1,  x1, y1, u1, v1};
		memcpy(quad + i * 24, q, sizeof(q));
	}

	glUseProgram(m_program);
	glActiveTexture(GL_TEXTURE0);
	glBindTexture(GL_TEXTURE_2D, m_texture);
	glUniform1i(m_tex_loc, 0);
	uint32_t a = __atomic_load_n(&m_shm->alpha, __ATOMIC_RELAXED);
	glUniform1f(m_alpha_loc, a >= 255 ? 1.0f : (float)a / 255.0f);

	// The frame is premultiplied (WPE/Skia), and so is the OSD in the window surface on every
	// platform that gets here (gEGLDC skips the layer where the compositor needs straight
	// alpha): plain premultiplied "over" for colour and alpha alike.
	glEnable(GL_BLEND);
	glBlendFuncSeparate(GL_ONE, GL_ONE_MINUS_SRC_ALPHA, GL_ONE, GL_ONE_MINUS_SRC_ALPHA);

	// client-side vertex data: valid with VAO 0 bound (see gles::setVertexData())
#if defined(HAVE_GLES3)
	if (gles::isGLES3())
		glBindVertexArray(0);
#endif
	glBindBuffer(GL_ARRAY_BUFFER, 0);
	glVertexAttribPointer(0, 4, GL_FLOAT, GL_FALSE, 4 * sizeof(float), quad);
	glEnableVertexAttribArray(0);
	glDrawArrays(GL_TRIANGLES, 0, 6 * npieces);
	glDisableVertexAttribArray(0);

	// Diagnostic, ENIGMA_WEB_OVERLAY_FINISH=1: wait for the GPU to finish this frame, so the next
	// frame's texture upload can never overlap a draw still in flight.
	static const bool finish = getenv("ENIGMA_WEB_OVERLAY_FINISH") && atoi(getenv("ENIGMA_WEB_OVERLAY_FINISH")) != 0;
	if (finish)
		glFinish();

	glBindTexture(GL_TEXTURE_2D, 0);
}
