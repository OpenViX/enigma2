#pragma once

#ifdef HAVE_GLES3
#include <GLES3/gl3.h>
#else
#include <GLES2/gl2.h>
#endif
#include <GLES2/gl2ext.h>

#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <lib/gdi/gpixmap.h>
#include <algorithm>
#include <cstdint>
#include <mutex>
#include <unordered_map>
#include <vector>

class gTextureManager {
private:
	// thread safe garbage collection for destroyed pixmaps
	std::vector<GLuint> m_pending_deletions;
	std::mutex m_deletion_mutex;
	EGLDisplay m_egl_display;
	std::unordered_map<GLuint, EGLImageKHR> m_texture_to_image_map;

	// Diagnostic only (see gTextureManager::createTextureFromPixmap()/
	// processDeletions()): tracks how many GL textures this manager
	// currently believes are live, so a genuine unbounded leak (count keeps
	// climbing) can be told apart from a legitimate-but-too-high working set
	// (count plateaus, then the next alloc past that plateau fails). Both
	// the increment (getTexture(), on the render/GL thread) and the
	// decrement (processDeletions(), same thread) only ever run on the
	// single EGL context thread, so this doesn't need its own lock.
	long m_live_texture_count = 0;

	// Approximate GPU bytes held by the textures counted above (width*height*
	// bytes-per-pixel as uploaded), so a GL_OUT_OF_MEMORY can be read against a
	// real number: a small total at failure means leaked/unavailable driver
	// memory, a large one means the working set really is too big. Same
	// single-thread rule as m_live_texture_count.
	std::unordered_map<GLuint, size_t> m_texture_bytes;

	// texture name -> the surface that owns it, guarded by m_deletion_mutex
	// (touched by the render thread and by ~gSurface() on any thread). Lets
	// evictLRU() find textures to free under memory pressure, and lets a dying
	// surface release only a texture it still owns.
	std::unordered_map<GLuint, gUnmanagedSurface*> m_texture_owner;
	unsigned int m_frame = 0;
	bool m_last_upload_oom = false;
	int m_max_texture_size = 0;

	// Frees least-recently-used textures (not drawn this frame, not pinned, not
	// DMA-BUF imports) until about `bytes_wanted` are released. Their surfaces
	// simply re-upload on next use. Returns the bytes released.
	// `max_count` bounds how many textures are deleted in one call (the rest wait for the next call), so a trim can be spread over
	// several frames instead of stalling one.
	// min_age: textures drawn fewer than this many frames ago are kept (1 = only skip the current frame).
	size_t evictLRU(size_t bytes_wanted, size_t max_count = (size_t)-1, unsigned int min_age = 1);
	size_t m_live_texture_bytes = 0;

	// Soft ceiling for the live textures, 0 = none. ENIGMA_TEX_BUDGET_MB sets it; otherwise it is learned from the first
	// GL_OUT_OF_MEMORY (a fraction of what was live at that moment), so from then on textures are released gradually every frame
	// instead of all at once inside the draw that ran out of memory.
	size_t m_soft_budget = 0;
	bool m_budget_fixed = false;

	// 8-bit paletted pixmaps are uploaded as a single-channel index texture plus a 256x1 palette texture and resolved in the fragment
	// shader (see gTextureShader), instead of being expanded to RGBA on the CPU. ENIGMA_EGL_GPU_PALETTE=0 restores the CPU expansion.
	// GL thread only, like the other GL state here.
	struct PaletteInfo {
		GLuint tex = 0;
		int w = 0, h = 0;
	};
	// Index+palette texture pairs of dead picons, kept for re-use instead of glDeleteTextures + glGenTextures/glTexImage2D: the driver
	// allocation is what shows up as 5-100 ms stalls in the upload timing. Keyed by (w << 32 | h). GL thread only.
	struct PooledPalTex {
		GLuint idx, pal;
		unsigned int frame; // when it was released; reused only a few frames later so no in-flight draw still samples it
	};
	std::unordered_map<unsigned long long, std::vector<PooledPalTex>> m_pal_pool;
	size_t m_pal_pool_count = 0;
	std::unordered_map<GLuint, PaletteInfo> m_palettes; // index texture -> its palette
	PaletteInfo m_last_palette; // set by createTextureFromPixmap() for the texture it just made
	void dropPalette(GLuint texture_id);

	// unified method to generate and upload the texture based on bpp
	GLuint createTextureFromPixmap(gPixmap* pixmap);
	GLuint createTextureFromDmabuf(gPixmap* pixmap);

public:
	gTextureManager();
	~gTextureManager();

	void setDisplay(EGLDisplay display) { m_egl_display = display; }

	// The GPU's largest usable texture dimension (GL_MAX_TEXTURE_SIZE), set by
	// gEGLDC once its context is current. 0 = unknown/unlimited. A pixmap
	// wider or taller than this can't be uploaded as-is (glTexImage2D raises
	// GL_INVALID_VALUE and the texture is left empty), so createTextureFromPixmap()
	// box-downsamples it to fit instead - UVs are normalised, so callers drawing
	// the texture into a logical-size rect need no change. Never triggers on a
	// GPU whose limit covers the pixmap.
	void setMaxTextureSize(int max_dim) { m_max_texture_size = max_dim; }
	int maxTextureSize() const { return m_max_texture_size; }

	// True if `texture_id` holds palette indices: `palette_tex` is its 256x1 palette and (w, h) the index texture's size.
	bool indexedInfo(GLuint texture_id, GLuint& palette_tex, int& w, int& h) const {
		if (m_palettes.empty())
			return false;
		auto it = m_palettes.find(texture_id);
		if (it == m_palettes.end())
			return false;
		palette_tex = it->second.tex;
		w = it->second.w;
		h = it->second.h;
		return true;
	}

	// returns the gl texture id, creating it on the fly if not cached
	GLuint getTexture(gPixmap* pixmap);

	// called by enigma2 main thread when a pixmap dies
	void queueForDeletion(GLuint texture_id);

	// called by our egl context thread at the start of exec() to free vram
	void processDeletions();
	// True if any texture is queued for deletion. Callers must draw any
	// pending batch that may reference such a texture (gEGLDC::flushBlitBatch())
	// BEFORE calling processDeletions(), or that draw samples a deleted texture.
	bool hasPendingDeletions();

	// Frees every evictable texture (not pinned, not DMA-BUF), including ones used
	// this frame - they re-upload on next draw. For making room for a large GPU
	// allocation (e.g. the shadow framebuffer after a resolution change).
	size_t releaseUnusedTextures() {
		++m_frame;
		return evictLRU((size_t)-1);
	}

	// Evicts least-recently-used textures (not used this frame) until the live ones hold at most `max_bytes`; returns the bytes
	// released. The manager has no budget of its own: it keeps every texture until the driver runs out of memory. That is fine
	// while enigma2 is alone on the GPU, but the GPU heap is also used by the web browser (HbbTV) and it cannot evict.
	// min_age > 1 spares textures the GPU may still be reading from frames in flight: deleting those can make the driver wait for them.
	size_t trimTo(size_t max_bytes, size_t max_count = (size_t)-1, unsigned int min_age = 1) {
		return m_live_texture_bytes > max_bytes ? evictLRU(m_live_texture_bytes - max_bytes, max_count, min_age) : 0;
	}
	// How many textures a per-frame trim to `max_bytes` should delete: enough to cover the overage (estimated with the average texture
	// size), never fewer than `min_count` nor more than `max_count`. A fixed small cap cannot keep up while fast scrolling uploads more
	// textures per frame than it frees, so the live set creeps up past the budget; deleting is far cheaper than the uploads anyway.
	size_t trimCountFor(size_t max_bytes, size_t min_count, size_t max_count) const {
		if (m_live_texture_bytes <= max_bytes || m_live_texture_count <= 0)
			return min_count;
		const size_t avg = std::max<size_t>(m_live_texture_bytes / (size_t)m_live_texture_count, 1);
		const size_t need = (m_live_texture_bytes - max_bytes) / avg + 1;
		return std::min(std::max(need, min_count), max_count);
	}
	// Platform default for the soft budget (small GPU heap): applied from the start so textures are trimmed gradually every frame
	// instead of piling up until the first out-of-memory. Ignored when ENIGMA_TEX_BUDGET_MB is set; a lower learned value still wins.
	void setDefaultBudget(size_t bytes) {
		if (!m_budget_fixed && bytes && (!m_soft_budget || bytes < m_soft_budget))
			m_soft_budget = bytes;
	}
	size_t softBudget() const { return m_soft_budget; }
	size_t liveBytes() const { return m_live_texture_bytes; }

	// Called once per presented frame: defines 'this frame' for LRU purposes.
	void nextFrame() { ++m_frame; }
	// Release a surface's texture from ~gSurface(), only if it still owns it.
	void releaseSurfaceTexture(GLuint texture_id, const void* surface);
};

// Size-limit helpers shared by gTextureManager and gEGLDC's CPU text overlay.
// Largest size with the same aspect ratio as (w, h) whose longer side is
// <= max_dim; (w, h) unchanged when max_dim <= 0 or it already fits.
void gtexFitSize(int w, int h, int max_dim, int& out_w, int& out_h);

// Bilinear downsample of 32-bit BGRA/RGBA pixels (the usual case here is a
// 0.5x-1x reduction, where bilinear is as good as a box filter and several times
// cheaper). Source is src_w x src_h with a row stride of src_stride_px pixels;
// taps are clamped to the clip rect [clip_l, clip_r) x [clip_t, clip_b) so
// nothing outside it (stale/uninitialised memory around a partially updated
// area) can bleed in. Writes destination pixels [dst_x0, dst_x1) x [dst_y0,
// dst_y1) of a dst_w x dst_h image, densely packed ((dst_x1 - dst_x0) per row)
// into `dst`. Fully opaque neighbourhoods take a packed integer fast path;
// translucent edges are alpha-weighted so transparent pixels don't darken them.
void gtexDownscaleBGRA(const uint32_t* src, int src_stride_px, int src_w, int src_h, int clip_l, int clip_t, int clip_r, int clip_b, uint32_t* dst, int dst_w, int dst_h, int dst_x0, int dst_y0,
					   int dst_x1, int dst_y1);
