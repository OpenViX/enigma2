#include <lib/gdi/egl/gles_version.h>

namespace gles {
int version = 0; // initialised to 0; set by gEGLDC::initEGL()
bool needsRBSwap = false; // set by gEGLDC::initEGL() from the window provider
bool clientArrays = true; // see setVertexData(); gEGLDC::initEGL() may turn it off
std::string eglVersionString; // set by gEGLDC::tryInitEGL()
std::string glesVersionString; // set by gEGLDC::tryInitEGL()
std::string specializeShaderSource(const char* source) {
	std::string src(source);
	static const char decl[] = "uniform float u_rbswap;";
	size_t pos = src.find(decl);
	if (pos != std::string::npos)
		src.replace(pos, sizeof(decl) - 1, needsRBSwap ? "const float u_rbswap = 1.0;" : "const float u_rbswap = 0.0;");
	return src;
}
}
