#pragma once

#ifdef HAVE_GLES3
#include <GLES3/gl3.h>
#else
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#endif

class gTextureShader {
public:
	// Upper bound on quads per drawBatch() call - the VBO is sized for
	// exactly this many up front (see init()) so a batch never needs to
	// grow the buffer mid-frame; gEGLDC's blit-batch accumulator flushes
	// once it reaches this many quads.
	static const int kMaxBatchQuads = 256;

private:
	GLuint m_program_id;
#if defined(HAVE_GLES3)
	GLuint m_vao; // GLES3 only; 0 in GLES2 mode
#endif
	GLuint m_vbo;

	GLint m_projection_location;
	GLint m_texture_location;
	GLint m_alpha_location;

	GLint m_rect_size_location;
	GLint m_radius_location;
	GLint m_edges_location;

	// ES2-only per-corner radius uniforms (replaces integer bitmask u_edges)
	GLint m_edges_tl_location;
	GLint m_edges_tr_location;
	GLint m_edges_bl_location;
	GLint m_edges_br_location;

	GLuint compileShader(GLenum type, const char* source);
	void bindVAO();
	void unbindVAO();

public:
	gTextureShader();
	~gTextureShader();

	bool init();
	void bind();

	// See gShader::destroy()'s comment - same reasoning and requirement
	// (must run while this thread's EGL context is still current).
	void destroy();

	void setResolution(float width, float height);
	void drawTexture(float x, float y, float width, float height, GLuint texture_id, float global_alpha = 1.0f, float radius = 0.0f, uint8_t edges = 0);

	// Draws multiple quads (vertex_count/6 of them, each 4 floats/vertex:
	// x,y,u,v - see drawTexture()'s "vertices" layout) sharing one texture
	// and one draw call, for callers that have accumulated several
	// same-texture quads themselves (see gEGLDC's blit batching). No corner
	// rounding support: u_rect_size/u_radius are for a single quad's SDF
	// calculation and would be wrong for every quad but the first in a
	// batch, so this always draws with radius 0 - callers must not batch
	// blits that need rounding.
	void drawBatch(const float* vertex_data, int vertex_count, GLuint texture_id, float global_alpha = 1.0f);
};