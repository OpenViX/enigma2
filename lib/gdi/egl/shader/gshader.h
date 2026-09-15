#pragma once

#ifdef HAVE_GLES3
#include <GLES3/gl3.h>
#else
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#endif

class gShader {
private:
	GLuint m_program_id;
#if defined(HAVE_GLES3)
	GLuint m_vao; // GLES3 only; 0 in GLES2 mode
#endif
	GLuint m_vbo;

	GLint m_projection_location;
	GLint m_color_location;

	GLuint compileShader(GLenum type, const char* source);
	void bindVAO();
	void unbindVAO();

public:
	gShader();
	~gShader();

	bool init();
	void bind();

	// Frees this shader's GL objects (program/VBO/VAO) - MUST be called
	// while this thread still has the owning EGL context current (see
	// gEGLDC::cleanupEGL()'s comment: that's the only guarantee normally
	// held here, since the destructor below runs later, on a different
	// thread, after the context is long gone - GL calls with no current
	// context at all are what actually crashed the driver on shutdown).
	// Safe to call more than once (idempotent - a second call sees zeroed
	// handles and does nothing), which is what makes it safe for the
	// destructor to also call it as a fallback/no-op.
	void destroy();

	void setResolution(float width, float height);
	void drawRect(float x, float y, float width, float height, float r, float g, float b, float a);
	void drawLine(float x1, float y1, float x2, float y2, float r, float g, float b, float a);
};