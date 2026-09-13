#pragma once

#include <lib/gdi/gpixmap.h>
#include <lib/gdi/erect.h>
#include <unordered_map>

// Identity key for a packed icon - mirrors glyph_key_t (gfont_atlas.h): the
// source pixmap's raw buffer address. Like glyph_key_t, this assumes that
// address stays stable for the pixmap's lifetime and is not reused by an
// unrelated pixmap while a stale m_icons entry for the old one still exists -
// the same tradeoff gFontAtlas already accepts for glyphs.
typedef const void* icon_key_t;

struct icon_uv {
	float u0, v0;
	float u1, v1;
	int width, height;
};

// Packs many small RGBA images (service list picons, list/menu icons) into
// one shared texture so gEGLDC::flushBlitBatch() can draw many of them - even
// though each is visually a different image - in a single glDrawArrays()
// call, keyed only by which GL texture is bound (the atlas) with a per-quad
// UV sub-rect, exactly like gFontAtlas already does for glyphs. Without this,
// batching in gegldc.cpp can only merge blits that happen to share the exact
// same standalone texture (e.g. a repeated "no picon" placeholder) - it does
// nothing for a scrolling channel list, where every row's picon is a
// genuinely distinct image with its own texture id.
class gIconAtlas {
private:
	ePtr<gPixmap> m_pixmap;
	int m_atlas_width;
	int m_atlas_height;

	bool m_is_dirty;
	eRect m_dirty_rect;

	// Simple shelf/row packer - same strategy and same full-reset-on-overflow
	// behavior as gFontAtlas (see addIcon()). Good enough here for the same
	// reason it's good enough there: only the working set actually on screen
	// (or recently scrolled past) needs to stay packed at once.
	int m_current_x;
	int m_current_y;
	int m_current_row_height;

	std::unordered_map<icon_key_t, icon_uv> m_icons;

public:
	gIconAtlas();
	~gIconAtlas();

	bool init(int width = 2048, int height = 2048);

	// Returns true and fills uv if key is already packed.
	bool getIcon(icon_key_t key, icon_uv& uv);

	// Expands pixmap's pixels to RGBA (if needed) and packs them into the
	// atlas, filling uv. Returns false, making no change, if pixmap's format
	// isn't one this atlas knows how to expand (see the .cpp - direct 32bpp,
	// or 8bpp palette+CLUT; a plain 8bpp coverage mask, i.e. a font glyph, is
	// not - that already has its own atlas, gFontAtlas) or if pixmap is
	// larger than the whole atlas page. Either way the caller must fall back
	// to a standalone per-pixmap texture for it, exactly as if this atlas
	// didn't exist.
	bool addIcon(icon_key_t key, gPixmap* pixmap, icon_uv& uv);

	gPixmap* getPixmap() const { return m_pixmap; }
	bool isDirty() const { return m_is_dirty; }
	eRect getDirtyRect() const { return m_dirty_rect; }
	void clearDirty() {
		m_is_dirty = false;
		m_dirty_rect = eRect();
	}
};
