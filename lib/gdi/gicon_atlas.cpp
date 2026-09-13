#include <lib/gdi/gicon_atlas.h>
#include <lib/base/eerror.h>
#include <algorithm>
#include <cstring>

gIconAtlas::gIconAtlas() : m_atlas_width(0), m_atlas_height(0), m_is_dirty(false), m_current_x(0), m_current_y(0), m_current_row_height(0) {}

gIconAtlas::~gIconAtlas() {
	// m_pixmap is managed by ePtr
}

bool gIconAtlas::init(int width, int height) {
	m_atlas_width = width;
	m_atlas_height = height;

	// accelNever: this is repeatedly memcpy'd into (addIcon()) and
	// glTexSubImage2D'd (gEGLDC::uploadIconAtlas()) from the CPU side, same
	// as gEGLDC's own m_pixmap - it must never take the DMA-BUF/ION
	// accelerated path on its first upload (see that pixmap's constructor
	// comment in gegldc.cpp for the full explanation). Unlike gFontAtlas's
	// 8bpp atlas, this one is 32bpp, so it can't rely on
	// createTextureFromDmabuf()'s bpp!=32 check to skip that path for it.
	m_pixmap = new gPixmap(eSize(width, height), 32, gPixmap::accelNever);
	memset(m_pixmap->surface->data, 0, (size_t)width * height * 4);

	m_is_dirty = false;
	m_dirty_rect = eRect();

	eDebug("[gIconAtlas] initialized %dx%d icon atlas", width, height);
	return true;
}

bool gIconAtlas::getIcon(icon_key_t key, icon_uv& uv) {
	auto it = m_icons.find(key);
	if (it != m_icons.end()) {
		uv = it->second;
		return true;
	}
	return false;
}

bool gIconAtlas::addIcon(icon_key_t key, gPixmap* pixmap, icon_uv& uv) {
	if (!m_pixmap || !pixmap || !pixmap->surface)
		return false;

	gUnmanagedSurface* surface = pixmap->surface;
	int width = surface->x;
	int height = surface->y;

	if (width <= 0 || height <= 0)
		return false;

	// Only formats we know how to expand to RGBA cheaply: direct 32bpp, or
	// 8bpp palette+CLUT (typical picon/icon formats). A plain 8bpp surface
	// with no palette is glyph coverage-mask data, not an icon - that goes
	// through gFontAtlas instead.
	bool has_clut = surface->bpp == 8 && surface->clut.data;
	if (surface->bpp != 32 && !has_clut)
		return false;

	// Refuse anything bigger than a generous picon/icon size, not just
	// anything too big to physically fit a page. Without this cap, a single
	// large image (a full-screen background or oversized cover-art blitted
	// through the same opcode path as picons) could consume most of one
	// atlas page by itself, forcing frequent full resets (see below) for the
	// many small icons that actually benefit from sharing this atlas -
	// exactly the "ATLAS FULL" pathology this class exists to avoid. Caller
	// falls back to a standalone texture for it, same as any other reject.
	static const int kMaxIconDimension = 512;
	if (width > kMaxIconDimension || height > kMaxIconDimension)
		return false;

	// Too big to ever fit even a freshly-reset page - can't happen given the
	// cap above unless the atlas itself was initialized smaller than that,
	// but keep the check for safety.
	if (width > m_atlas_width || height > m_atlas_height)
		return false;

	if (m_current_x + width > m_atlas_width) {
		m_current_x = 0;
		m_current_y += m_current_row_height + 1; // 1px padding
		m_current_row_height = 0;
	}

	if (m_current_y + height > m_atlas_height) {
		eDebug("[gIconAtlas] ATLAS FULL! Resetting atlas...");
		m_current_x = 0;
		m_current_y = 0;
		m_current_row_height = 0;
		m_icons.clear();
		memset(m_pixmap->surface->data, 0, (size_t)m_atlas_width * m_atlas_height * 4);
		m_is_dirty = true;
		m_dirty_rect = eRect(0, 0, m_atlas_width, m_atlas_height);
	}

	uint8_t* dst_base = (uint8_t*)m_pixmap->surface->data;
	int dst_stride = m_atlas_width * 4;

	if (surface->bpp == 32) {
		// Straight byte copy - surface->data is already in the same native
		// BGRA-in-memory order (see gtexture_manager.cpp's bpp==32 branch)
		// that this atlas's own pixels are in, so no conversion is needed;
		// gEGLDC::uploadIconAtlas() uploads the whole atlas texture with the
		// same "tell GL it's GL_RGBA while the bytes are native BGRA" trick
		// already used for every other 32bpp texture in this backend.
		const uint8_t* src = (const uint8_t*)surface->data;
		int src_stride = surface->stride;
		for (int row = 0; row < height; ++row) {
			memcpy(dst_base + (size_t)(m_current_y + row) * dst_stride + (size_t)m_current_x * 4, src + (size_t)row * src_stride, (size_t)width * 4);
		}
	} else {
		// 8bpp palette+CLUT - expand to RGBA once, at pack time, using the
		// same formula as gTextureManager::createTextureFromPixmap()'s
		// equivalent branch (including the alpha-convention XOR).
		const uint8_t* src = (const uint8_t*)surface->data;
		int src_stride = surface->stride;
		gRGB* palette = surface->clut.data;
		for (int row = 0; row < height; ++row) {
			const uint8_t* src_row = src + (size_t)row * src_stride;
			uint32_t* dst_row = (uint32_t*)(dst_base + (size_t)(m_current_y + row) * dst_stride + (size_t)m_current_x * 4);
			for (int x = 0; x < width; ++x) {
				dst_row[x] = palette[src_row[x]].argb() ^ 0xFF000000;
			}
		}
	}

	if (!m_is_dirty) {
		m_dirty_rect = eRect(m_current_x, m_current_y, width, height);
		m_is_dirty = true;
	} else {
		int min_x = std::min(m_dirty_rect.left(), m_current_x);
		int min_y = std::min(m_dirty_rect.top(), m_current_y);
		int max_x = std::max(m_dirty_rect.right(), m_current_x + width);
		int max_y = std::max(m_dirty_rect.bottom(), m_current_y + height);
		m_dirty_rect = eRect(min_x, min_y, max_x - min_x, max_y - min_y);
	}

	uv.width = width;
	uv.height = height;
	uv.u0 = (float)m_current_x / (float)m_atlas_width;
	uv.v0 = (float)m_current_y / (float)m_atlas_height;
	uv.u1 = (float)(m_current_x + width) / (float)m_atlas_width;
	uv.v1 = (float)(m_current_y + height) / (float)m_atlas_height;

	m_icons[key] = uv;

	m_current_x += width + 1; // 1px padding
	if (height > m_current_row_height) {
		m_current_row_height = height;
	}

	return true;
}
