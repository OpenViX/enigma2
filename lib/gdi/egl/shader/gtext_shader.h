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

	GLuint compileShader(GLenum type, const char* source);

public:
	gTextShader();
	~gTextShader();

	bool init();
	void bind();

	// See gShader::destroy()'s comment - same reasoning and requirement
	// (must run while this thread's EGL context is still current).
	void destroy();

	// flushTextBatch() (gegldc.cpp) builds its own batched vertex buffer
	// across many glyphs and issues glBufferSubData()/glDrawArrays() itself -
	// it must bracket that with bindVAO()/unbindVAO() so the correct VBO and
	// vertex attribute layout (pos_uv + color) are active, since whatever
	// another shader (e.g. gShader, 2 floats/vertex) last bound would
	// otherwise still be in effect and the batch data would be
	// misinterpreted.
	void bindVAO();
	void unbindVAO();

	void setResolution(float width, float height);
};