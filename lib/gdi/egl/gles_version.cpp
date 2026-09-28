#include <lib/gdi/egl/gles_version.h>

namespace gles {
int version = 0; // initialised to 0; set by gEGLDC::initEGL()
bool needsRBSwap = false; // set by gEGLDC::initEGL() from the window provider
bool clientArrays = true; // see setVertexData(); gEGLDC::initEGL() may turn it off
}
