#include <lib/base/eerror.h>
#include <lib/gdi/egl/gles_version.h>
#include <lib/gdi/egl/gtexture_manager.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <vector>

#ifndef GL_BGRA_EXT
#define GL_BGRA_EXT 0x80E1
#endif

// Temporary diagnostic for the "scrolling a picon-heavy list starts slow
// then speeds up" report: separates the CPU-side work this function does
// itself (bpp==8 palette expansion, the GLES2 tight-repack fallback) from
// the actual glTexImage2D upload, so the next device log says which one is
// actually the cost instead of guessing - epng.cpp/picload.cpp already
// force accelNever for HAVE_EGL (see project_egl_texture_leak.md - letting
// these compete with the vendor driver's own ION pool crashed it), so every
// picon takes this CPU-copy path, never the createTextureFromDmabuf() one.
#define TEX_UPLOAD_TIMING 1
#if TEX_UPLOAD_TIMING
static inline double ms_since(const std::chrono::steady_clock::time_point& t0) {
	return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
}
#endif

static gTextureManager* s_active_manager = nullptr;

void gtexFitSize(int w, int h, int max_dim, int& out_w, int& out_h) {
	out_w = w;
	out_h = h;
	if (max_dim <= 0 || w <= 0 || h <= 0)
		return;
	const int longest = std::max(w, h);
	if (longest <= max_dim)
		return;
	const double s = (double)max_dim / (double)longest;
	out_w = std::max(1, std::min(max_dim, (int)(w * s + 0.5)));
	out_h = std::max(1, std::min(max_dim, (int)(h * s + 0.5)));
}

// Lerp of two packed 8-bit-per-channel pixels, t in 0..256, two channels per
// 32-bit multiply (each 16-bit lane holds at most 255 * 256, so it never overflows).
static inline uint32_t gtexLerp32(uint32_t a, uint32_t b, uint32_t t) {
	const uint32_t ag = (((a >> 8) & 0x00FF00FFu) * (256 - t) + ((b >> 8) & 0x00FF00FFu) * t) & 0xFF00FF00u;
	const uint32_t rb = ((((a & 0x00FF00FFu) * (256 - t)) + ((b & 0x00FF00FFu) * t)) >> 8) & 0x00FF00FFu;
	return ag | rb;
}

// Translucent neighbourhood: bilinear weights, alpha-weighted colour.
static uint32_t gtexBlendTranslucent(const uint32_t p[4], uint32_t wx0, uint32_t wx1, uint32_t wy0, uint32_t wy1) {
	const uint32_t w[4] = {(wx0 * wy0) >> 8, (wx1 * wy0) >> 8, (wx0 * wy1) >> 8, (wx1 * wy1) >> 8};
	const uint32_t wsum = w[0] + w[1] + w[2] + w[3];
	uint32_t asum = 0, b = 0, g = 0, r = 0;
	for (int i = 0; i < 4; ++i) {
		const uint32_t wa = w[i] * (p[i] >> 24);
		asum += wa;
		b += wa * (p[i] & 0xFF);
		g += wa * ((p[i] >> 8) & 0xFF);
		r += wa * ((p[i] >> 16) & 0xFF);
	}
	if (asum == 0 || wsum == 0)
		return 0;
	const float inv = 1.0f / (float)asum;
	const uint32_t a8 = std::min(255u, (uint32_t)((float)asum / (float)wsum + 0.5f));
	const uint32_t r8 = std::min(255u, (uint32_t)((float)r * inv + 0.5f));
	const uint32_t g8 = std::min(255u, (uint32_t)((float)g * inv + 0.5f));
	const uint32_t b8 = std::min(255u, (uint32_t)((float)b * inv + 0.5f));
	return (a8 << 24) | (r8 << 16) | (g8 << 8) | b8;
}

void gtexDownscaleBGRA(const uint32_t* src, int src_stride_px, int src_w, int src_h, int clip_l, int clip_t, int clip_r, int clip_b, uint32_t* dst, int dst_w, int dst_h, int dst_x0, int dst_y0,
					   int dst_x1, int dst_y1) {
	clip_l = std::max(0, clip_l);
	clip_t = std::max(0, clip_t);
	clip_r = std::min(src_w, clip_r);
	clip_b = std::min(src_h, clip_b);
	dst_x0 = std::max(0, dst_x0);
	dst_y0 = std::max(0, dst_y0);
	dst_x1 = std::min(dst_w, dst_x1);
	dst_y1 = std::min(dst_h, dst_y1);
	if (!src || !dst || dst_w <= 0 || dst_h <= 0 || clip_r <= clip_l || clip_b <= clip_t || dst_x1 <= dst_x0 || dst_y1 <= dst_y0)
		return;

	const float sx = (float)src_w / (float)dst_w;
	const float sy = (float)src_h / (float)dst_h;
	const int out_w = dst_x1 - dst_x0;

	// Per destination column: the two source columns and the 0..256 weight of the
	// second - computed once instead of per pixel.
	struct Tap {
		int x0, x1;
		uint32_t f;
	};
	std::vector<Tap> taps((size_t)out_w);
	for (int dx = dst_x0; dx < dst_x1; ++dx) {
		const float fx = ((float)dx + 0.5f) * sx - 0.5f;
		const int x0 = (int)std::floor(fx);
		Tap& t = taps[(size_t)(dx - dst_x0)];
		t.f = (uint32_t)((fx - (float)x0) * 256.0f + 0.5f);
		t.x0 = std::min(std::max(x0, clip_l), clip_r - 1);
		t.x1 = std::min(std::max(x0 + 1, clip_l), clip_r - 1);
	}

	for (int dy = dst_y0; dy < dst_y1; ++dy) {
		const float fy = ((float)dy + 0.5f) * sy - 0.5f;
		const int y0 = (int)std::floor(fy);
		const uint32_t ty = (uint32_t)((fy - (float)y0) * 256.0f + 0.5f);
		const uint32_t* r0 = src + (size_t)std::min(std::max(y0, clip_t), clip_b - 1) * src_stride_px;
		const uint32_t* r1 = src + (size_t)std::min(std::max(y0 + 1, clip_t), clip_b - 1) * src_stride_px;
		uint32_t* out = dst + (size_t)(dy - dst_y0) * out_w;

		for (int i = 0; i < out_w; ++i) {
			const Tap& t = taps[(size_t)i];
			const uint32_t p00 = r0[t.x0], p01 = r0[t.x1], p10 = r1[t.x0], p11 = r1[t.x1];
			if (((p00 & p01 & p10 & p11) >> 24) == 0xFFu) {
				out[i] = gtexLerp32(gtexLerp32(p00, p01, t.f), gtexLerp32(p10, p11, t.f), ty);
			} else if (((p00 | p01 | p10 | p11) >> 24) == 0) {
				out[i] = 0;
			} else {
				const uint32_t p[4] = {p00, p01, p10, p11};
				out[i] = gtexBlendTranslucent(p, 256 - t.f, t.f, 256 - ty, ty);
			}
		}
	}
}

gTextureManager::gTextureManager() : m_egl_display(EGL_NO_DISPLAY) {
	s_active_manager = this;
}

gTextureManager::~gTextureManager() {
	if (s_active_manager == this)
		s_active_manager = nullptr;
}

#ifndef EGL_LINUX_DMA_BUF_EXT
#define EGL_LINUX_DMA_BUF_EXT 0x3270
#endif
#ifndef EGL_LINUX_DRM_FOURCC_EXT
#define EGL_LINUX_DRM_FOURCC_EXT 0x3271
#endif
#ifndef EGL_DMA_BUF_PLANE0_FD_EXT
#define EGL_DMA_BUF_PLANE0_FD_EXT 0x3272
#endif
#ifndef EGL_DMA_BUF_PLANE0_OFFSET_EXT
#define EGL_DMA_BUF_PLANE0_OFFSET_EXT 0x3273
#endif
#ifndef EGL_DMA_BUF_PLANE0_PITCH_EXT
#define EGL_DMA_BUF_PLANE0_PITCH_EXT 0x3274
#endif

// DRM FourCC formats
#define DRM_FORMAT_ARGB8888 0x34325241

#include <lib/gdi/fb.h>

GLuint gTextureManager::createTextureFromDmabuf(gPixmap* pixmap) {
#ifdef CONFIG_ION
	fbClass* fb = fbClass::getInstance();
	if (!fb || fb->m_accel_fd < 0 || m_egl_display == EGL_NO_DISPLAY)
		return 0;

	gUnmanagedSurface* surface = pixmap->surface;
	if (surface->bpp != 32 || surface->data_phys == 0)
		return 0;

	unsigned long offset = surface->data_phys - fb->getAccelPhysAddr();
	int width = surface->x;
	int height = surface->y;
	int stride = surface->stride;

	EGLint attribs[] = {
		EGL_WIDTH, width,
		EGL_HEIGHT, height,
		EGL_LINUX_DRM_FOURCC_EXT, DRM_FORMAT_ARGB8888,
		EGL_DMA_BUF_PLANE0_FD_EXT, fb->m_accel_fd,
		EGL_DMA_BUF_PLANE0_OFFSET_EXT, (EGLint)offset,
		EGL_DMA_BUF_PLANE0_PITCH_EXT, stride,
		EGL_NONE
	};

	PFNEGLCREATEIMAGEKHRPROC eglCreateImageKHR = (PFNEGLCREATEIMAGEKHRPROC)eglGetProcAddress("eglCreateImageKHR");
	PFNGLEGLIMAGETARGETTEXTURE2DOESPROC glEGLImageTargetTexture2DOES = (PFNGLEGLIMAGETARGETTEXTURE2DOESPROC)eglGetProcAddress("glEGLImageTargetTexture2DOES");

	if (!eglCreateImageKHR || !glEGLImageTargetTexture2DOES) {
		eDebug("[gTextureManager] EGL dmabuf extensions not available");
		return 0;
	}

	EGLImageKHR image = eglCreateImageKHR(m_egl_display, EGL_NO_CONTEXT, EGL_LINUX_DMA_BUF_EXT, (EGLClientBuffer)NULL, attribs);
	if (image == EGL_NO_IMAGE_KHR) {
		eDebug("[gTextureManager] eglCreateImageKHR failed: 0x%x", eglGetError());
		return 0;
	}

	GLuint texture_id;
	glGenTextures(1, &texture_id);
	glBindTexture(GL_TEXTURE_2D, texture_id);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);

	glEGLImageTargetTexture2DOES(GL_TEXTURE_2D, image);
	glBindTexture(GL_TEXTURE_2D, 0);

	m_texture_to_image_map[texture_id] = image;
	return texture_id;
#else
	return 0;
#endif
}

// Diagnostic, opt-in via ENIGMA_EGL_TEX_CHECK=1: logs when a pixmap is about
// to be uploaded with every source byte zero (in e2's inverted-alpha
// convention that is fully OPAQUE BLACK) - i.e. a picture uploaded before its
// decoder finished writing it, or from recycled/cleared memory. That texture
// is then cached on the surface until the pixmap dies, which would show up as
// a black square that stays black. Copies the source first (ION memory is
// slow to read with scalar loads, see the palette branch below).
static void checkPixmapAllZero(const gUnmanagedSurface* surface, int width, int height) {
	static const bool enabled = getenv("ENIGMA_EGL_TEX_CHECK") && atoi(getenv("ENIGMA_EGL_TEX_CHECK")) != 0;
	if (!enabled || !surface->data || surface->stride <= 0)
		return;
	std::vector<uint8_t> local((size_t)surface->stride * height);
	memcpy(local.data(), surface->data, local.size());
	const size_t row_bytes = (size_t)width * (surface->bpp == 32 ? 4 : 1);
	for (int y = 0; y < height; ++y) {
		const uint8_t* row = local.data() + (size_t)y * surface->stride;
		for (size_t i = 0; i < row_bytes; ++i)
			if (row[i])
				return;
	}
	eDebug("[gTextureManager] TEX_CHECK: uploading ALL-ZERO pixmap %dx%d bpp=%d stride=%d data=%p - will render as black", width, height, surface->bpp, surface->stride, surface->data);
}

GLuint gTextureManager::createTextureFromPixmap(gPixmap* pixmap) {
	m_last_upload_oom = false;
	if (!pixmap || !pixmap->surface)
		return 0;

#if TEX_UPLOAD_TIMING
	auto t_total0 = std::chrono::steady_clock::now();
#endif

	GLuint texture_id = createTextureFromDmabuf(pixmap);
	if (texture_id != 0) {
#if TEX_UPLOAD_TIMING
		eDebug("[gTextureManager] timing: dmabuf import %dx%d bpp=%d took %.2fms", pixmap->surface->x, pixmap->surface->y, pixmap->surface->bpp, ms_since(t_total0));
#endif
		return texture_id;
	}

	gUnmanagedSurface* surface = pixmap->surface;
	int width = surface->x;
	int height = surface->y;

	if (surface->bpp == 32 || surface->bpp == 8)
		checkPixmapAllZero(surface, width, height);

	// See the bpp==32 branch below for the full explanation - shared here so
	// the bpp==8 paletted branch (which uploads the same native BGRA memory
	// order via gRGB::argb()) can use the same platform-dependent format.
	GLenum src_format = gles::needsRBSwap ? GL_RGBA : GL_BGRA_EXT;

	// Drain any error left over from earlier, unrelated GL calls so the
	// glGetError() after the upload below can only be this upload's own.
	for (int i = 0; i < 8 && glGetError() != GL_NO_ERROR; ++i) {
	}

	glGenTextures(1, &texture_id);
	glBindTexture(GL_TEXTURE_2D, texture_id);

	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);

	// Wider/taller than the GPU's max texture size (see setMaxTextureSize()):
	// glTexImage2D would raise GL_INVALID_VALUE and leave the texture empty.
	// Expand to BGRA on the CPU, box-downsample to the largest size that fits,
	// and upload that. Only for the 32bpp / paletted formats, whose upload goes
	// through full BGRA anyway; never taken when the pixmap already fits.
	int tex_w = width, tex_h = height;
	if (surface->bpp == 32 || (surface->bpp == 8 && surface->clut.data))
		gtexFitSize(width, height, m_max_texture_size, tex_w, tex_h);

	if (tex_w != width || tex_h != height) {
		std::vector<uint32_t> full((size_t)width * height);
		if (surface->bpp == 32) {
			const uint8_t* src = (const uint8_t*)surface->data;
			for (int row = 0; row < height; ++row)
				memcpy(full.data() + (size_t)row * width, src + (size_t)row * surface->stride, (size_t)width * 4);
		} else {
			// Same palette rule as the paletted branch below.
			uint32_t pal[256];
			const int n = std::min(surface->clut.colors, 256);
			for (int i = 0; i < n; ++i)
				pal[i] = surface->clut.data[i].argb() ^ 0xFF000000;
			for (int i = std::max(n, 0); i < 256; ++i)
				pal[i] = (0x010101 * i) | 0xFF000000;
			const uint8_t* src = (const uint8_t*)surface->data;
			for (int y = 0; y < height; ++y) {
				const uint8_t* row = src + (size_t)y * surface->stride;
				uint32_t* out = full.data() + (size_t)y * width;
				for (int x = 0; x < width; ++x)
					out[x] = pal[row[x]];
			}
		}
		std::vector<uint32_t> scaled((size_t)tex_w * tex_h);
		gtexDownscaleBGRA(full.data(), width, width, height, 0, 0, width, height, scaled.data(), tex_w, tex_h, 0, 0, tex_w, tex_h);
		glTexImage2D(GL_TEXTURE_2D, 0, src_format, tex_w, tex_h, 0, src_format, GL_UNSIGNED_BYTE, scaled.data());
		eDebug("[gTextureManager] %dx%d bpp=%d exceeds GL_MAX_TEXTURE_SIZE=%d - uploaded downscaled to %dx%d", width, height, surface->bpp, m_max_texture_size, tex_w, tex_h);
	} else if (surface->bpp == 32) {
		// e2's 32bpp surfaces are natively BGRA in memory (see gpixmap.h's
		// gRGB struct: {b,g,r,a} on little-endian). On a platform where this
		// render target's fragment-shader output ends up read back by the
		// display in the opposite R/B order from what GL writes (see
		// gshader.cpp's fragment shader for the ground-truth test that
		// proved this true on Dreambox - gles::needsRBSwap, gles_version.h),
		// uploading that memory as-is while *telling* glTexImage2D it's
		// GL_RGBA means the sampler reads back (r=trueB, g=trueG, b=trueR) -
		// i.e. already pre-swapped - which is exactly what's needed to
		// cancel out the render target's own R/B swap on the way to the
		// screen. A GL_TEXTURE_SWIZZLE here would have been the spec-correct
		// way to compensate for a *sampler* quirk, but this isn't one - it's
		// a *render-target-vs-scanout* mismatch, unrelated to how a texture
		// is sampled; adding a swizzle on top of already-compensated data
		// just swaps it back to wrong.
		//
		// On a platform WITHOUT that scanout quirk (gles::needsRBSwap ==
		// false), the correct upload instead just tells GL the truth about
		// the source memory layout (GL_BGRA_EXT, confirmed advertised by
		// this hardware's GL_EXTENSIONS as GL_EXT_texture_format_BGRA8888) -
		// no pre-swap, no swizzle, the sampler just reads it right (src_format,
		// declared above).
		//
		// glTexImage2D() assumes each row is tightly packed (row length ==
		// width, no padding) - true for e2's own pixmap allocations, but
		// NOT guaranteed for a pixmap loaded from an externally-decoded
		// image (e.g. a JPEG sized to an arbitrary widget width), whose
		// stride can be padded wider than width*bypp. Uploading that
		// directly reads each row starting a few bytes short of where it
		// actually begins, and the error compounds every row - producing
		// exactly the diagonal-shear/sheared-image corruption seen with
		// e.g. TMDBCockpit's cover/backdrop pictures (the CPU renderer
		// never hits this because gPixmap::fill()/blit() always address
		// rows via surface->stride explicitly, never assume width*bypp).
		int row_pixels = surface->stride / surface->bypp;
#if TEX_UPLOAD_TIMING
		auto t_upload0 = std::chrono::steady_clock::now();
#endif
		if (row_pixels == width) {
			glTexImage2D(GL_TEXTURE_2D, 0, src_format, width, height, 0, src_format, GL_UNSIGNED_BYTE, surface->data);
#if defined(HAVE_GLES3)
		} else if (gles::isGLES3()) {
			// GL_UNPACK_ROW_LENGTH tells GL the source buffer's actual row
			// length in pixels, so it can skip the padding itself instead
			// of a CPU-side repack.
			glPixelStorei(GL_UNPACK_ROW_LENGTH, row_pixels);
			glTexImage2D(GL_TEXTURE_2D, 0, src_format, width, height, 0, src_format, GL_UNSIGNED_BYTE, surface->data);
			glPixelStorei(GL_UNPACK_ROW_LENGTH, 0);
#endif
		} else {
			// GLES2 has no GL_UNPACK_ROW_LENGTH - repack into a tightly
			// packed buffer first, same technique as the paletted branch
			// below already uses for its own stride-vs-width mismatch.
			std::vector<uint32_t> packed((size_t)width * height);
			const uint8_t* src = (const uint8_t*)surface->data;
			for (int row = 0; row < height; ++row)
				memcpy(packed.data() + (size_t)row * width, src + (size_t)row * surface->stride, (size_t)width * 4);
			glTexImage2D(GL_TEXTURE_2D, 0, src_format, width, height, 0, src_format, GL_UNSIGNED_BYTE, packed.data());
		}
#if TEX_UPLOAD_TIMING
		eDebug("[gTextureManager] timing: bpp32 upload %dx%d (row_pixels=%d) took %.2fms", width, height, row_pixels, ms_since(t_upload0));
#endif
	} else if (surface->bpp == 8 && surface->clut.data) {
		// 8-bit paletted image (often used for picons/skins).
		// gles 3.0 does not support indexed color textures natively anymore,
		// so we expand it to 32-bit rgba on the cpu before uploading.
		std::vector<uint32_t> rgba_buffer(width * height);
		uint8_t* src_pixels = (uint8_t*)surface->data;
		// Same rule as gpixmap.cpp's convert_palette(): entries beyond the
		// palette size are an opaque grey ramp. The previous direct
		// palette[row[x]] had no bounds check, so an index >= clut.colors read
		// past the end of the palette's heap block - zero/stale memory there
		// is opaque BLACK (inverted alpha), a nondeterministic black picture.
		uint32_t pal[256];
		{
			int n = std::min(surface->clut.colors, 256);
			for (int i = 0; i < n; ++i)
				pal[i] = surface->clut.data[i].argb() ^ 0xFF000000;
			for (int i = std::max(n, 0); i < 256; ++i)
				pal[i] = (0x010101 * i) | 0xFF000000;
		}
		int max_index = 0;
		int src_stride = surface->stride; // bytes per row in the *source* -
		// may differ from width for externally-loaded images (e.g. a PNG
		// decoder's own row alignment), unlike gPixmap's own allocations
		// (stride == width for those). Indexing with a flat i = y*width+x
		// instead of respecting stride is exactly what produces a sheared/
		// distorted image once stride != width.

		// This source pixmap can be ION/accelerated memory, which on this
		// hardware is mapped as ARM "Device" type for GPU coherency - a
		// bulk memcpy of it is fast (benefits from burst reads), but this
		// loop reading it one byte at a time via scalar loads (row[x]) is
		// NOT: Device memory disallows the burst/speculative access a
		// vectorized memcpy implementation uses, so each individual scalar
		// load pays full memory latency (measured: ~30-45ms for a 400x240
		// image, vs <1ms via memcpy of the same bytes). Copying the source
		// rows to an ordinary heap buffer first with that same fast memcpy,
		// then reading *that* in the loop, sidesteps it - this is what
		// turned "screen takes 3s to open the first time" into a sub-second
		// open.
#if TEX_UPLOAD_TIMING
		auto t_expand0 = std::chrono::steady_clock::now();
#endif
		std::vector<uint8_t> local_src((size_t)src_stride * height);
		memcpy(local_src.data(), src_pixels, local_src.size());

		for (int y = 0; y < height; ++y) {
			const uint8_t* row = local_src.data() + (size_t)y * src_stride;
			for (int x = 0; x < width; ++x) {
				// gRGB::argb() returns the native {b,g,r,a} memory order
				// (see gpixmap.h) with alpha still in enigma2's inverted
				// "0=opaque" convention - XOR the top byte to fix alpha.
				// No CPU-side R/B swap here regardless of platform (see the
				// bpp==32 branch above and its src_format) - argb()'s native
				// BGRA memory order is uploaded as-is either way, with
				// src_format telling GL the truth or the pre-swap lie as
				// appropriate for this platform.
				rgba_buffer[y * width + x] = pal[row[x]];
				if (row[x] > max_index)
					max_index = row[x];
			}
		}
#if TEX_UPLOAD_TIMING
		double expand_ms = ms_since(t_expand0);
		auto t_upload0 = std::chrono::steady_clock::now();
#endif

		// ENIGMA_EGL_TEX_CHECK=1: one line per indexed upload with what was actually
		// read - palette size/start, its first entries as uploaded, index range and
		// how many pixels are index 0 - to tell an empty/zero palette or all-zero
		// indices (both render black) from a rendering-side problem.
		static const bool tex_check = getenv("ENIGMA_EGL_TEX_CHECK") && atoi(getenv("ENIGMA_EGL_TEX_CHECK")) != 0;
		if (tex_check) {
			size_t zero_px = 0, opaque_black = 0;
			for (size_t i = 0; i < rgba_buffer.size(); ++i) {
				zero_px += (local_src[(i / width) * src_stride + (i % width)] == 0);
				opaque_black += (rgba_buffer[i] == 0xFF000000u);
			}
			eDebug("[gTextureManager] TEX_CHECK bpp8 %dx%d stride=%d clut.colors=%d clut.start=%d data=%p pal0=%08x pal1=%08x pal2=%08x maxIndex=%d index0Px=%zu/%zu opaqueBlackPx=%zu",
				width, height, src_stride, surface->clut.colors, surface->clut.start, (void*)surface->clut.data, pal[0], pal[1], pal[2], max_index, zero_px, rgba_buffer.size(), opaque_black);
		}

		if (max_index >= surface->clut.colors)
			eDebug("[gTextureManager] bpp8 %dx%d has pixel index %d beyond its palette size %d - unmapped entries use the CPU renderer's grey ramp", width, height, max_index, surface->clut.colors);

		glTexImage2D(GL_TEXTURE_2D, 0, src_format, width, height, 0, src_format, GL_UNSIGNED_BYTE, rgba_buffer.data());
#if TEX_UPLOAD_TIMING
		eDebug("[gTextureManager] timing: bpp8 palette-expand %dx%d took %.2fms, glTexImage2D took %.2fms", width, height, expand_ms, ms_since(t_upload0));
#endif
	} else if (surface->bpp == 8) {
		// Plain 8-bit grayscale surface with no palette - this is what the
		// font glyph atlas (gFontAtlas) is: a single-channel coverage/alpha
		// map, not an indexed-color image. Previously this fell into the
		// "unsupported" branch below, leaving flushTextBatch() uploading
		// glyph data into a texture object that was never actually created
		// (id 0) - glyphs rendered as garbage/invisible as a result.
		// epng.cpp's loadPNG() now always builds a real (identity, for plain
		// grayscale) clut for anything decoded from a PNG file, so gFontAtlas
		// - built directly in memory by the font rasterizer, never round-
		// tripped through a PNG - is the only remaining legitimate producer
		// of a clut-less bpp==8 surface reaching this branch. A regression
		// there (e.g. a skin's plain-grayscale PNG asset losing its clut
		// again) would otherwise be sampled as single-channel alpha against
		// whatever color a later draw binds, instead of its own color - see
		// epng.cpp's PNG_COLOR_TYPE_GRAY branch for the incident this fixed.
		GLenum internal_fmt = gles::isGLES3() ? GL_R8 : GL_LUMINANCE;
		GLenum src_fmt = gles::isGLES3() ? GL_RED : GL_LUMINANCE;
		glTexImage2D(GL_TEXTURE_2D, 0, internal_fmt, width, height, 0, src_fmt, GL_UNSIGNED_BYTE, surface->data);
	} else {
		eDebug("[gTextureManager] unsupported surface format (bpp: %d)", surface->bpp);
		glDeleteTextures(1, &texture_id);
		return 0;
	}

	glBindTexture(GL_TEXTURE_2D, 0);

	// A failed upload (typically GL_OUT_OF_MEMORY from the driver, e.g. while
	// its buffers are being reallocated for a larger resolution) leaves this
	// texture with no storage - it samples as solid black - and getTexture()
	// would cache that id on the surface forever, so the picture would stay
	// black even after the memory pressure is gone. Report it and hand back 0
	// instead: nothing is cached, and the next draw retries the upload.
	// Only GL_OUT_OF_MEMORY is treated as a failed upload. Any other error is
	// logged but the texture is kept: this driver may raise a non-fatal error
	// on an upload that still works (the code never checked before), and
	// dropping such a texture would make the picture vanish instead.
	GLenum upload_err = glGetError();
	if (upload_err == GL_OUT_OF_MEMORY) {
		eDebug("[gTextureManager] texture upload FAILED (out of memory) %dx%d bpp=%d - not caching, will retry on next draw [live textures=%ld, ~%.1fMB tracked]", width, height, surface->bpp, m_live_texture_count, m_live_texture_bytes / 1048576.0);
		glDeleteTextures(1, &texture_id);
		m_last_upload_oom = true;
		return 0;
	}
	if (upload_err != GL_NO_ERROR)
		eDebug("[gTextureManager] texture upload raised glError=0x%x %dx%d bpp=%d (kept)", upload_err, width, height, surface->bpp);
#if TEX_UPLOAD_TIMING
	eDebug("[gTextureManager] timing: createTextureFromPixmap total %dx%d bpp=%d took %.2fms", width, height, surface->bpp, ms_since(t_total0));
#endif
	return texture_id;
}

GLuint gTextureManager::getTexture(gPixmap* pixmap) {
	if (!pixmap || !pixmap->surface)
		return 0;

	gUnmanagedSurface* sf = pixmap->surface;
	if (sf->gl_texture_id != 0) {
		sf->gl_last_used_frame = m_frame;
		return sf->gl_texture_id;
	}

	GLuint new_texture = createTextureFromPixmap(pixmap);

	// The driver ran out of memory: free least-recently-used textures (which
	// simply re-upload the next time they are drawn) and try again, instead of
	// leaving this picture blank. At most two rounds, each freeing more.
	if (!new_texture && m_last_upload_oom) {
		const size_t need = (size_t)sf->x * sf->y * 4;
		size_t want = std::max<size_t>(need * 2, 4u << 20);
		for (int round = 0; round < 2 && !new_texture; ++round, want *= 4) {
			if (evictLRU(want) == 0)
				break;
			new_texture = createTextureFromPixmap(pixmap);
		}
	}

	if (new_texture) {
		sf->gl_texture_id = new_texture;
		sf->gl_last_used_frame = m_frame;
		{
			std::lock_guard<std::mutex> lock(m_deletion_mutex);
			m_texture_owner[new_texture] = sf;
		}
		++m_live_texture_count;
		// Bytes as uploaded: paletted (with a clut) and 32bpp surfaces are RGBA8,
		// a clut-less 8bpp surface (glyph atlas) is single channel.
		size_t bytes = (size_t)sf->x * sf->y * ((sf->bpp == 8 && !sf->clut.data) ? 1 : 4);
		m_texture_bytes[new_texture] = bytes;
		m_live_texture_bytes += bytes;
		eDebug("[gTextureManager] +texture id=%u live=%ld ~%.1fMB %dx%d bpp=%d", new_texture, m_live_texture_count, m_live_texture_bytes / 1048576.0,
			sf->x, sf->y, sf->bpp);
	}
	return new_texture;
}

size_t gTextureManager::evictLRU(size_t bytes_wanted) {
	struct Cand {
		unsigned int last_used;
		GLuint id;
		gUnmanagedSurface* surface;
	};
	std::vector<Cand> cands;
	size_t freed = 0;
	int evicted = 0;

	// Held for the whole operation: ~gSurface() releases through the same lock,
	// so a surface in this map cannot be destroyed while we touch it.
	std::lock_guard<std::mutex> lock(m_deletion_mutex);
	for (const auto& kv : m_texture_owner) {
		gUnmanagedSurface* sf = kv.second;
		if (sf->gl_texture_pinned || sf->gl_last_used_frame == m_frame)
			continue; // in use this frame, or updated in place
		if (m_texture_to_image_map.count(kv.first))
			continue; // DMA-BUF import, needs eglDestroyImage - leave alone
		cands.push_back({sf->gl_last_used_frame, kv.first, sf});
	}
	std::sort(cands.begin(), cands.end(), [](const Cand& a, const Cand& b) { return a.last_used < b.last_used; });

	for (const Cand& c : cands) {
		if (freed >= bytes_wanted)
			break;
		glDeleteTextures(1, &c.id);
		c.surface->gl_texture_id = 0;
		m_texture_owner.erase(c.id);
		auto bit = m_texture_bytes.find(c.id);
		if (bit != m_texture_bytes.end()) {
			freed += bit->second;
			m_live_texture_bytes -= std::min(m_live_texture_bytes, bit->second);
			m_texture_bytes.erase(bit);
		}
		--m_live_texture_count;
		++evicted;
	}
	if (evicted)
		eDebug("[gTextureManager] out of memory: evicted %d least-recently-used textures (~%.1fMB), now live=%ld ~%.1fMB", evicted, freed / 1048576.0, m_live_texture_count,
			m_live_texture_bytes / 1048576.0);
	return freed;
}

void gTextureManager::releaseSurfaceTexture(GLuint texture_id, const void* surface) {
	if (texture_id == 0)
		return;
	{
		std::lock_guard<std::mutex> lock(m_deletion_mutex);
		auto it = m_texture_owner.find(texture_id);
		// Not found / owned by someone else: this surface's texture was already
		// evicted (and the name possibly reused) - nothing to release.
		if (it == m_texture_owner.end() || it->second != surface)
			return;
		m_texture_owner.erase(it);
	}
	queueForDeletion(texture_id);
}

void gTextureManager::queueForDeletion(GLuint texture_id) {
	if (texture_id == 0)
		return;

	std::lock_guard<std::mutex> lock(m_deletion_mutex);
	m_pending_deletions.push_back(texture_id);
	// If this queue depth climbs and stays high, processDeletions() isn't
	// being reached often enough (rather than surfaces simply never dying) -
	// a different problem from the live_texture_count in getTexture()/
	// processDeletions() ever growing, which would mean surfaces are dying
	// but their textures are never queued/deleted at all.
	eDebug("[gTextureManager] queued texture id=%u for deletion, pending=%zu", texture_id, m_pending_deletions.size());
}

bool gTextureManager::hasPendingDeletions() {
	std::lock_guard<std::mutex> lock(m_deletion_mutex);
	return !m_pending_deletions.empty();
}

void gTextureManager::processDeletions() {
	std::lock_guard<std::mutex> lock(m_deletion_mutex);
	if (!m_pending_deletions.empty()) {
		glDeleteTextures(m_pending_deletions.size(), m_pending_deletions.data());
		m_live_texture_count -= (long)m_pending_deletions.size();

		PFNEGLDESTROYIMAGEKHRPROC eglDestroyImageKHR = (PFNEGLDESTROYIMAGEKHRPROC)eglGetProcAddress("eglDestroyImageKHR");
		for (GLuint texture_id : m_pending_deletions) {
			auto bit = m_texture_bytes.find(texture_id);
			if (bit != m_texture_bytes.end()) {
				m_live_texture_bytes -= std::min(m_live_texture_bytes, bit->second);
				m_texture_bytes.erase(bit);
			}
			auto it = m_texture_to_image_map.find(texture_id);
			if (it != m_texture_to_image_map.end()) {
				if (eglDestroyImageKHR && m_egl_display != EGL_NO_DISPLAY) {
					eglDestroyImageKHR(m_egl_display, it->second);
				}
				m_texture_to_image_map.erase(it);
			}
		}

		eDebug("[gTextureManager] -texture count=%zu live=%ld ~%.1fMB", m_pending_deletions.size(), m_live_texture_count, m_live_texture_bytes / 1048576.0);
		m_pending_deletions.clear();
	}
}

extern "C" void egl_release_surface_texture(unsigned int gl_texture_id, const void* surface);
void egl_release_surface_texture(unsigned int gl_texture_id, const void* surface) {
	if (s_active_manager)
		s_active_manager->releaseSurfaceTexture(gl_texture_id, surface);
	else
		eDebug("[gTextureManager] egl_release_surface_texture(%u) called with no active manager - texture leaked", gl_texture_id);
}

extern "C" void egl_queue_texture_deletion(unsigned int gl_texture_id);
void egl_queue_texture_deletion(unsigned int gl_texture_id) {
	if (s_active_manager) {
		s_active_manager->queueForDeletion(gl_texture_id);
	} else {
		// Diagnostic only: if this ever prints, ~gSurface() is running and
		// trying to release its texture, but there is no live gTextureManager
		// to hand it to - the id (and the GPU/ION memory behind it) is
		// silently dropped on the floor right here instead of being queued.
		eDebug("[gTextureManager] egl_queue_texture_deletion(%u) called with no active manager - texture leaked", gl_texture_id);
	}
}