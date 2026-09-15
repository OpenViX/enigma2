#pragma once

#include <lib/gdi/gpixmap.h>
#include <lib/gdi/erect.h>
#include <map>
#include <stdint.h>

// A glyph's (face, size, glyph index) identity, packed by the caller (see
// eTextPara::blit() in font.cpp) - stable and reusable across draws, unlike
// a pointer to any particular rendered bitmap.
typedef uint64_t glyph_key_t;

struct glyph_uv {
    float u0, v0;
    float u1, v1;
    int width, height;
};

class gFontAtlas
{
private:
    ePtr<gPixmap> m_pixmap;
    int m_atlas_width;
    int m_atlas_height;
    
    bool m_is_dirty;
    eRect m_dirty_rect;
    
    int m_current_x;
    int m_current_y;
    int m_current_row_height;

    std::map<glyph_key_t, glyph_uv> m_glyphs;

public:
    gFontAtlas();
    ~gFontAtlas();

    bool init(int width = 2048, int height = 2048);
    void bind();
    
    bool getGlyph(glyph_key_t key, glyph_uv &uv);
    // src_pitch is the byte stride of a source row in data, which may exceed
    // width (FreeType pads/aligns its small-bitmap cache rows) - copying
    // width bytes per row at that stride, not at a tightly-packed "row*width"
    // offset, is required or every row past the first is read from the wrong
    // place, shearing the glyph into diagonal garbage in the atlas.
    void addGlyph(glyph_key_t key, int width, int height, const uint8_t *data, int src_pitch, glyph_uv &uv);

    // True if adding a glyph of this size would trigger the "atlas full"
    // reset path in addGlyph() (m_glyphs.clear() + full-buffer memset) - the
    // *only* case that actually invalidates anything already queued/batched
    // by a caller but not yet drawn (a plain row-advance, by contrast,
    // leaves every existing glyph's data and UVs untouched). Callers that
    // flush a pending batch before addGlyph() purely to protect against
    // that invalidation only need to do so when this returns true.
    bool wouldOverflow(int width, int height) const;

    gPixmap* getPixmap() const { return m_pixmap; }
    bool isDirty() const { return m_is_dirty; }
    eRect getDirtyRect() const { return m_dirty_rect; }
    void clearDirty() { m_is_dirty = false; m_dirty_rect = eRect(); }
};
