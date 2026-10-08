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

	// Lean program for the common case (batched blits with no corner rounding and
	// no premultiply/unpremultiply mode): no SDF, no mode branches, no v_pos
	// varying - just sample * alpha. The full program above handles the rest.
	GLuint m_plain_program_id = 0;
	GLint m_plain_projection_location = -1;
	GLint m_plain_texture_location = -1;
	GLint m_plain_alpha_location = -1;
	GLuint buildPlainProgram();

	GLint m_projection_location;
	GLint m_texture_location;
	GLint m_alpha_location;
	GLint m_unpremult_location = -1;
	bool m_unpremultiply = false;
	float m_unpremultiply_power = 1.0f;
	bool m_premultiply = false;

	GLint m_rect_size_location;
	GLint m_radius_location;
	GLint m_edges_location;

	// ES2-only per-corner radius uniforms (replaces integer bitmask u_edges)
	GLint m_edges_tl_location;
	GLint m_edges_tr_location;
	GLint m_edges_bl_location;
	GLint m_edges_br_location;

	GLuint compileShader(GLenum type, const char* source);
	// Feeds vertex_count vertices (x, y, u, v) through gles::setVertexData()
	// and draws them as triangles.
	void drawVertices(const float* vertex_data, int vertex_count);

public:
	gTextureShader();
	~gTextureShader();

	bool init();
	void bind();

	// See gShader::destroy()'s comment - same reasoning and requirement
	// (must run while this thread's EGL context is still current).
	void destroy();

	void setResolution(float width, float height);

	// While set, every draw divides the sampled colour by its alpha - i.e.
	// converts premultiplied pixels to straight alpha. Used only by gEGLDC's
	// final present pass when the window compositor blends the surface as
	// straight alpha (see INativeWindowProvider::needsStraightAlphaPresent());
	// must be cleared again right after.
	void setUnpremultiply(bool on, float power = 1.0f) { m_unpremultiply = on; m_unpremultiply_power = power; }
	// Multiply colour by alpha on output: for blits drawn with blending off (raw overwrite)
	// into a premultiplied frame.
	void setPremultiply(bool on) { m_premultiply = on; }
	void drawTexture(float x, float y, float width, float height, GLuint texture_id, float global_alpha = 1.0f, float radius = 0.0f, uint8_t edges = 0);

	// Same rounded-rect texture draw as drawTexture(), but only covers the
	// sub-rectangle (sx, sy, sw, sh) of the rect (x, y, width, height): the SDF
	// still uses the whole rect's shape, the UVs map the whole texture onto the
	// whole rect. Lets a rounded blit run the costly SDF fragment shader only
	// over its corner squares and draw the rest through drawBatch().
	void drawTextureSub(float x, float y, float width, float height, float sx, float sy, float sw, float sh, GLuint texture_id, float radius, uint8_t edges);

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