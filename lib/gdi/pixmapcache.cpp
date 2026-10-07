#include <lib/gdi/pixmapcache.h>

#include <algorithm>
#include <cstdlib>
#include <map>
#include <string>
#include <vector>
#include <lib/base/elock.h>

// Byte budget, not an item count: the previous version of this cache capped
// itself at a flat 100 entries regardless of size, so one 24x24 icon and one
// 799x480 poster each counted as "1 slot" - a skin/bouquet mix skewed toward
// small icons could never fill available memory, while one skewed toward
// large posters/SVG-rasterized picons could blow well past it, still only
// counting as 100 items. This tracks each entry's actual footprint instead
// (see pixmapBytes() below) and evicts LRU entries until the running total
// fits, so it naturally allows many small icons or few large images rather
// than always exactly 100 of either.
//
// On the GLES/EGL backend every cached pixmap also gets its own GPU texture
// (gTextureManager, lib/gdi/egl/gtexture_manager.cpp) the first time it's
// blitted, roughly doubling the real memory cost of each entry (CPU decode
// buffer + GPU texture) versus the CPU-only renderer - pixmapBytes() accounts
// for that. Exceeding a memory-constrained set-top box's available graphics
// memory has previously surfaced as the vendor GLES driver's own internal
// ION allocation failing (and segfaulting on the failure - a driver bug we
// can't fix directly) during heavy list scrolling, so this default is a
// conservative starting point, not a measured-safe ceiling for any specific
// box. Override via ENIGMA_PIXMAP_CACHE_MAX_BYTES (bytes) to tune per box/skin
// without a rebuild - raise it gradually on real hardware while watching for
// that failure mode, don't just pick a big number.
static size_t defaultMaximumBytes()
{
	const char *env = getenv("ENIGMA_PIXMAP_CACHE_MAX_BYTES");
	if (env)
	{
		char *end = nullptr;
		unsigned long long v = strtoull(env, &end, 10);
		if (end != env && v > 0)
			return (size_t)v;
	}
	return 32u * 1024 * 1024; // 32MB
}
size_t PixmapCache::MaximumBytes = defaultMaximumBytes();

static size_t pixmapBytes(gPixmap *pixmap)
{
	gUnmanagedSurface *surface = pixmap->surface;
	if (!surface)
		return 0;
	size_t bytes = (size_t)surface->stride * (size_t)surface->y;
	if (surface->clut.data)
		bytes += (size_t)surface->clut.colors * sizeof(gRGB);
#ifdef HAVE_EGL
	bytes *= 2;
#endif
	return bytes;
}

// Cache objects work best when we manage the ref counting manually. ePtr brings memory protection violations on shutdown
// We track the filesize and modified date of the file. If either change, the item is considered stale is removedand must be reloaded
// We also track the last used time so the cache can remove least recently used items when it gets too full, and each
// item's own byte cost (computed once at insert time - see pixmapBytes()) so eviction can track total memory used
// without re-walking every entry's surface on every Set().
struct CacheItem
{
public:
	CacheItem()
	{
	}

	CacheItem& operator=(const CacheItem& p)
	{
		pixmap = p.pixmap;
		filesize = p.filesize;
		modifiedDate = p.modifiedDate;
		lastUsed = p.lastUsed;
		bytes = p.bytes;
		return *this;
	}

	CacheItem(gPixmap* p, off_t s, time_t m, size_t b)
	{
		pixmap = p;
		filesize = s;
		modifiedDate = m;
		lastUsed = ::time(0);
		bytes = b;
	};

	gPixmap* pixmap;
	off_t filesize;
	time_t modifiedDate;
	int lastUsed;
	size_t bytes;
};

typedef std::map<std::string, CacheItem> NameToPixmap;

static bool CompareLastUsed(NameToPixmap::value_type i, NameToPixmap::value_type j)
{
	return i.second.lastUsed < j.second.lastUsed;
}

static eSingleLock pixmapCacheLock;
static NameToPixmap pixmapCache;
static size_t pixmapCacheBytes = 0; // sum of every live entry's CacheItem::bytes - guarded by pixmapCacheLock, same as pixmapCache itself

/* The "dispose" method isn't very efficient, but not called unless
 * a pixmap is being replaced by another when the cache is full and even then,
 * not loading the same pixmap repeatedly will probably make up for that.
 * There is a race condition, when two threads load the same image,
 * the worst case scenario is then that the pixmap is loaded twice. This
 * isn't any worse than before, and all the UI pixmaps will be loaded
 * from the same thread anyway. */
void PixmapCache::PixmapDisposed(gPixmap* pixmap)
{
	eSingleLocker lock(pixmapCacheLock);

	for (NameToPixmap::iterator it = pixmapCache.begin();
		 it != pixmapCache.end();
		 ++it)
	{
		if (it->second.pixmap == pixmap)
		{
			pixmapCacheBytes -= it->second.bytes;
			pixmapCache.erase(it);
			break;
		}
	}
}

gPixmap* PixmapCache::Get(const char *filename, const char *cachekey)
{
	if (!cachekey)
		cachekey = filename;

	gPixmap* disposePixmap = NULL;
	{
		eSingleLocker lock(pixmapCacheLock);
		NameToPixmap::iterator it = pixmapCache.find(cachekey);
		if (it != pixmapCache.end())
		{
			// find out whether the image has been modified
			// if so, it'll need to be reloaded from disk
			struct stat img_stat = {};
			if (stat(filename, &img_stat) == 0 && img_stat.st_mtime == it->second.modifiedDate && img_stat.st_size == it->second.filesize)
			{
				// file still exists and hasn't been modified
				it->second.lastUsed = ::time(0);
				return it->second.pixmap;
			}
			else
			{
				// file no longer exists, has been modified or changed size, so remove from the cache
				// (read the pixmap pointer BEFORE erase() - erase() invalidates `it`, so reading
				// it->second afterwards is a dangling-iterator access: it can silently skip the
				// Release() below, leaking the evicted pixmap's accel-backed memory forever)
				disposePixmap = it->second.pixmap;
				pixmapCacheBytes -= it->second.bytes;
				pixmapCache.erase(it);
			}
		}
	}

	// Release might cause a callback into PixmapDisposed
	// Avoid the risk of a deadlock by doing the release outside the lock
	if (disposePixmap)
		disposePixmap->Release();

	return NULL;
}

void PixmapCache::Set(const char *filename, gPixmap* pixmap, const char *cachekey)
{
	if (!cachekey)
		cachekey = filename;

	gPixmap* disposePixmap = NULL;
	std::vector<gPixmap*> evicted;
	{
		eSingleLocker lock(pixmapCacheLock);
		struct stat img_stat = {};
		if (stat(filename, &img_stat) == 0)
		{
			size_t bytes = pixmapBytes(pixmap);
			NameToPixmap::iterator it = pixmapCache.find(cachekey);
			if (it != pixmapCache.end())
			{
				// need to release the pixmap being replaced after we've finished updating the cache
				disposePixmap = it->second.pixmap;
				pixmapCacheBytes -= it->second.bytes;

				// swap in the updated pixmap
				pixmap->AddRef();
				it->second.pixmap = pixmap;
				it->second.filesize = img_stat.st_size;
				it->second.modifiedDate = img_stat.st_mtime;
				it->second.bytes = bytes;
				pixmapCacheBytes += bytes;
			}
			else
			{
				// Evict least-recently-used entries until this one fits the
				// byte budget. If a single entry's own footprint exceeds the
				// whole budget by itself (e.g. one oversized poster), this
				// empties the cache and still inserts it anyway rather than
				// refusing to cache - simplest graceful degradation, and the
				// next insert starts evicting immediately again.
				while (!pixmapCache.empty() && (pixmapCacheBytes + bytes) > MaximumBytes)
				{
					NameToPixmap::iterator victim = std::min_element(pixmapCache.begin(), pixmapCache.end(), &CompareLastUsed);
					if (victim == pixmapCache.end())
						break;
					// need to release the pixmap being removed after we've finished updating the cache
					// (read victim->second BEFORE erase() - see the identical comment in Get() above)
					evicted.push_back(victim->second.pixmap);
					pixmapCacheBytes -= victim->second.bytes;
					pixmapCache.erase(victim);
				}

				pixmap->AddRef();
				NameToPixmap::value_type pr = std::make_pair(std::string(cachekey), CacheItem(pixmap, img_stat.st_size, img_stat.st_mtime, bytes));
				pixmapCache.insert(pr);
				pixmapCacheBytes += bytes;
			}
		}
	}

	// Release might cause a callback into PixmapDisposed
	// Avoid the risk of a deadlock by doing the release outside the lock
	if (disposePixmap)
		disposePixmap->Release();
	for (gPixmap *p : evicted)
		p->Release();
}
