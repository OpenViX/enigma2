#pragma once
#ifdef HAVE_GLES3
#include <GLES3/gl3.h>
#else
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#endif
#include <lib/gdi/gfont_atlas.h>

class gTextShader {
private:
	GLuint m_program_id;
#if defined(HAVE_GLES3)
	GLuint m_vao; // GLES3 only; 0 in GLES2 mode
#endif
	GLuint m_vbo;

	GLint m_projection_location;
	GLint m_color_location;
	GLint m_texture_location;
	GLint m_rbswap_location;

	GLuint compileShader(GLenum type, const char* source);

public:
	gTextShader();
	~gTextShader();

	bool init();
	void bind();

	// See gShader::destroy()'s comment - same reasoning and requirement
	// (must run while this thread's EGL context is still current).
	void destroy();

	// flushTextBatch() (gegldc.cpp) builds its own batched glyph vertices
	// (pos_uv + color, 8 floats each) and issues glDrawArrays() itself - it
	// must bracket those draws with setVertexData()/endVertexData() so this
	// shader's attribute layout is the one in effect (see
	// gles::setVertexData()).
	void setVertexData(const float* vertex_data, int vertex_count);
	void endVertexData();

	void setResolution(float width, float height, float sx = 1.0f, float sy = 1.0f, float tx = 0.0f, float ty = 0.0f);
};