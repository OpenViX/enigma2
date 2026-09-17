#include <lib/base/eerror.h>
#include <lib/gdi/egl/gles_version.h>
#include <lib/gdi/egl/gtexture_manager.h>
#include <algorithm>
#include <cstring>

static gTextureManager* s_active_manager = nullptr;

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

GLuint gTextureManager::createTextureFromPixmap(gPixmap* pixmap) {
	if (!pixmap || !pixmap->surface)
		return 0;

	GLuint texture_id = createTextureFromDmabuf(pixmap);
	if (texture_id != 0)
		return texture_id;

	gUnmanagedSurface* surface = pixmap->surface;
	int width = surface->x;
	int height = surface->y;

	glGenTextures(1, &texture_id);
	glBindTexture(GL_TEXTURE_2D, texture_id);

	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);

	if (surface->bpp == 32) {
		// This render target's fragment-shader output ends up read back by
		// the display in the opposite R/B order from what GL writes (see
		// gshader.cpp's fragment shader for the ground-truth test that
		// proved this). A GL_TEXTURE_SWIZZLE here would have been the
		// spec-correct way to compensate for a *sampler* quirk, but this
		// isn't one - it's a *render-target-vs-scanout* mismatch, unrelated
		// to how a texture is sampled. Adding a swizzle on top of data
		// that's already the right bytes to compensate for the mismatch
		// (see below) just swaps it back to wrong, which is exactly what a
		// swizzle here did until this was untangled with a controlled
		// synthetic-texture test.
		//
		// e2's 32bpp surfaces are natively BGRA in memory (see gpixmap.h's
		// gRGB struct: {b,g,r,a} on little-endian). Uploading that memory
		// as-is while *telling* glTexImage2D it's GL_RGBA means the sampler
		// reads back (r=trueB, g=trueG, b=trueR) - i.e. already pre-swapped
		// - which is exactly what's needed to cancel out the render target's
		// own R/B swap on the way to the screen. No CPU-side byte swapping,
		// and no texture swizzle, needed.
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
		if (row_pixels == width) {
			glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, surface->data);
#if defined(HAVE_GLES3)
		} else if (gles::isGLES3()) {
			// GL_UNPACK_ROW_LENGTH tells GL the source buffer's actual row
			// length in pixels, so it can skip the padding itself instead
			// of a CPU-side repack.
			glPixelStorei(GL_UNPACK_ROW_LENGTH, row_pixels);
			glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, surface->data);
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
			glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, packed.data());
		}
	} else if (surface->bpp == 8 && surface->clut.data) {
		// 8-bit paletted image (often used for picons/skins).
		// gles 3.0 does not support indexed color textures natively anymore,
		// so we expand it to 32-bit rgba on the cpu before uploading.
		std::vector<uint32_t> rgba_buffer(width * height);
		uint8_t* src_pixels = (uint8_t*)surface->data;
		gRGB* palette = surface->clut.data;
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
		std::vector<uint8_t> local_src((size_t)src_stride * height);
		memcpy(local_src.data(), src_pixels, local_src.size());

		for (int y = 0; y < height; ++y) {
			const uint8_t* row = local_src.data() + (size_t)y * src_stride;
			for (int x = 0; x < width; ++x) {
				// gRGB::argb() returns the native {b,g,r,a} memory order
				// (see gpixmap.h) with alpha still in enigma2's inverted
				// "0=opaque" convention - XOR the top byte to fix alpha.
				// No R/B swap here (see the bpp==32 branch above): argb()'s
				// native BGRA memory order, uploaded while telling
				// glTexImage2D it's GL_RGBA, already comes out pre-swapped
				// in exactly the way needed to cancel this render target's
				// own R/B swap on the way to the screen.
				rgba_buffer[y * width + x] = palette[row[x]].argb() ^ 0xFF000000;
			}
		}

		glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, rgba_buffer.data());
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
	return texture_id;
}

GLuint gTextureManager::getTexture(gPixmap* pixmap) {
	if (!pixmap || !pixmap->surface)
		return 0;

	if (pixmap->surface->gl_texture_id != 0) {
		return pixmap->surface->gl_texture_id;
	}

	GLuint new_texture = createTextureFromPixmap(pixmap);
	if (new_texture) {
		pixmap->surface->gl_texture_id = new_texture;
		++m_live_texture_count;
		eDebug("[gTextureManager] +texture id=%u live=%ld %dx%d bpp=%d", new_texture, m_live_texture_count,
			pixmap->surface->x, pixmap->surface->y, pixmap->surface->bpp);
	}
	return new_texture;
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

void gTextureManager::processDeletions() {
	std::lock_guard<std::mutex> lock(m_deletion_mutex);
	if (!m_pending_deletions.empty()) {
		glDeleteTextures(m_pending_deletions.size(), m_pending_deletions.data());
		m_live_texture_count -= (long)m_pending_deletions.size();

		PFNEGLDESTROYIMAGEKHRPROC eglDestroyImageKHR = (PFNEGLDESTROYIMAGEKHRPROC)eglGetProcAddress("eglDestroyImageKHR");
		for (GLuint texture_id : m_pending_deletions) {
			auto it = m_texture_to_image_map.find(texture_id);
			if (it != m_texture_to_image_map.end()) {
				if (eglDestroyImageKHR && m_egl_display != EGL_NO_DISPLAY) {
					eglDestroyImageKHR(m_egl_display, it->second);
				}
				m_texture_to_image_map.erase(it);
			}
		}

		eDebug("[gTextureManager] -texture count=%zu live=%ld", m_pending_deletions.size(), m_live_texture_count);
		m_pending_deletions.clear();
	}
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