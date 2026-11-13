#ifndef __png_h
#define __png_h

#include <lib/gdi/gpixmap.h>

SWIG_VOID(int) loadPNG(ePtr<gPixmap> &SWIG_OUTPUT, const char *filename, int accel = 0, int cached = 1);
SWIG_VOID(int) loadJPG(ePtr<gPixmap> &SWIG_OUTPUT, const char *filename, int cached = 0);
SWIG_VOID(int) loadJPG(ePtr<gPixmap> &SWIG_OUTPUT, const char *filename, ePtr<gPixmap> alpha, int cached = 0);
SWIG_VOID(int) loadSVG(ePtr<gPixmap> &SWIG_OUTPUT, const char *filename, int cached = 1, int width = 0, int height = 0, float scale = 0, int keepAspect = 0, int align = 0);

SWIG_VOID(int) loadImage(ePtr<gPixmap> &SWIG_OUTPUT, const char *filename, int accel = 0, int width = 0, int height = 0, int cached = -1, float scale = 0, int keepAspect = 0, int align = 0);
int savePNG(const char *filename, gPixmap *pixmap);

#ifndef SWIG
#include <vector>
// A decoded PNG held in plain memory: pngDecodeToBuffer() touches neither gPixmap nor PixmapCache, so it may run on a
// worker thread; pngBufferToPixmap() (main thread) turns it into the same pixmap loadPNG() would have produced.
struct PngDecoded
{
	bool ok = false;
	int width = 0, height = 0, bpp = 0;
	bool transparent = false;
	size_t rowbytes = 0;
	std::vector<unsigned char> pixels;
	bool setClut = false;       // the palette fields below apply
	int clutColors = 0;
	std::vector<gRGB> clut;     // empty with setClut: a palette image without usable palette
};
void pngDecodeToBuffer(const char *filename, PngDecoded &out);
// Box filter (alpha weighted) down to maxWidth pixels wide, keeping the aspect ratio; 32 bit images wider than that only.
void pngDownscale(PngDecoded &d, int maxWidth);
ePtr<gPixmap> pngBufferToPixmap(const char *filename, PngDecoded &decoded, int accel, int cached);
#endif

#endif
