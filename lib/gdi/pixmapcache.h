#ifndef __pixmapcache_h
#define __pixmapcache_h

#include <lib/gdi/gpixmap.h>

#ifndef SWIG

class PixmapCache
{
private:
	// Byte budget, not an item count - see pixmapcache.cpp's comment on this
	// (and on pixmapBytes()) for why, and ENIGMA_PIXMAP_CACHE_MAX_BYTES for
	// how to tune it without a rebuild.
	static size_t MaximumBytes;
public:
	static void PixmapDisposed(gPixmap *pixmap);

	// `filename` must be a real, on-disk path - it's stat()'d to detect a
	// stale/modified entry. `cachekey` is what the entry is actually looked
	// up/stored by; when null, filename doubles as the cache key too (the
	// PNG/JPEG case, where one file only ever needs one cached rendering).
	// SVG rasterization varies by requested size/scale, so multiple distinct
	// cached pixmaps can exist for the same on-disk file - loadSVG() (epng.cpp)
	// synthesizes a separate `cachefile` key (filename+size) for exactly this,
	// but MUST pass the real filename here too, or the stat() below always
	// fails (no file named e.g. "foo.svg15" exists) and Set() silently never
	// actually inserts anything - see the incident this fixed: every
	// SVG-sourced picon was being fully re-rasterized and re-uploaded to a
	// fresh GPU texture on every single redraw, since it was never actually
	// being cached at all despite appearing to request caching.
	static gPixmap* Get(const char *filename, const char *cachekey = nullptr);
	static void Set(const char *filename, gPixmap *pixmap, const char *cachekey = nullptr);
};

#endif

#endif
