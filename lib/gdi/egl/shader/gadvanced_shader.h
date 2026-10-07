#pragma once

#ifdef HAVE_GLES3
#include <GLES3/gl3.h>
#else
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#endif
#include <lib/gdi/gpixmap.h>
#include <vector>

class gAdvancedShader {
private:
	GLuint m_program_id;
#if defined(HAVE_GLES3)
	GLuint m_vao; // GLES3 only; 0 in GLES2 mode
#endif
	GLuint m_vbo;

	GLint m_projection_location;
	GLint m_rect_size_location;
	GLint m_radius_location;
	GLint m_edges_location;
	GLint m_solid_color_location;
	GLint m_border_width_location;
	GLint m_border_color_location;
	GLint m_alphablend_location;
	GLint m_rbswap_location;
	GLint m_coverage_alpha_location;

	// Gradient uniforms
	GLint m_gradient_colors_location;
	GLint m_gradient_stops_location; // array of floats
	GLint m_num_stops_location;
	GLint m_gradient_orientation_location;

	// ES2-only per-corner radius uniforms (replaces integer bitmask u_edges)
	// GLSL ES 1.00 does not support bitwise operations on integer uniforms.
	GLint m_edges_tl_location; // u_r_tl
	GLint m_edges_tr_location; // u_r_tr
	GLint m_edges_bl_location; // u_r_bl
	GLint m_edges_br_location; // u_r_br

	GLuint compileShader(GLenum type, const char* source);

public:
	gAdvancedShader();
	~gAdvancedShader();

	bool init();
	void bind();

	// See gShader::destroy()'s comment - same reasoning and requirement
	// (must run while this thread's EGL context is still current).
	void destroy();

	void setResolution(float width, float height, float sx = 1.0f, float sy = 1.0f, float tx = 0.0f, float ty = 0.0f);

	void drawAdvancedRect(float x, float y, float width, float height, int radius, uint8_t edges, const std::vector<gRGB>& gradient_colors, uint8_t orientation, bool alphablend, float alpha,
						  const gRGB& solid_color, int border_width, const gRGB& border_color, bool coverage_alpha = false, const float* quad = nullptr);
	// quad, if non-null, is {x, y, w, h}: draw only that sub-area of the
	// rect (x, y, width, height) - the shader still evaluates against the
	// full rect's uniforms, so the result is identical to the corresponding
	// part of a full-rect draw. Used to shade only a rounded rect's corners.
};
