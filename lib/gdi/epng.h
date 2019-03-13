#ifndef __png_h
#define __png_h

#include <lib/gdi/gpixmap.h>

SWIG_VOID(int) loadPNG(ePtr<gPixmap> &SWIG_OUTPUT, const char *filename, int accel = 0, int cached = 1);
SWIG_VOID(int) loadJPG(ePtr<gPixmap> &SWIG_OUTPUT, const char *filename, int cached = 0);
SWIG_VOID(int) loadJPG(ePtr<gPixmap> &SWIG_OUTPUT, const char *filename, ePtr<gPixmap> alpha, int cached = 0);

int savePNG(const char *filename, gPixmap *pixmap);

#endif
