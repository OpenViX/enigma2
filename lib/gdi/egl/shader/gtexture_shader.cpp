#include <lib/gdi/egl/shader/gtexture_shader.h>
#include <lib/gdi/egl/gles_version.h>
#include <lib/base/eerror.h>
#include <stdlib.h>

// ---------------------------------------------------------------------------
// GLES 3.0 shader sources
// ---------------------------------------------------------------------------
#if defined(HAVE_GLES3)
static const char *vertex_shader_es3 = R"(#version 300 es
	layout(location = 0) in vec4 pos_uv;
	uniform mat4 u_projection;
	out vec2 v_uv;
	out vec2 v_pos;
	void main() {
		gl_Position = u_projection * vec4(pos_uv.xy, 0.0, 1.0);
		v_uv  = pos_uv.zw;
		v_pos = pos_uv.xy;
	}
)";

static const char *fragment_shader_es3 = R"(#version 300 es
	precision mediump float;
	
	in vec2 v_uv;
	in vec2 v_pos;
	out vec4 frag_color;
	
	uniform sampler2D u_texture;
	uniform float u_global_alpha;
	uniform float u_unpremultiply;
	
	uniform vec4 u_rect_size;
	uniform float u_radius;
	uniform int u_edges;

	float udRoundBox(vec2 p, vec2 b, float r) {
		vec2 d = abs(p) - b + vec2(r);
		return min(max(d.x, d.y), 0.0) + length(max(d, 0.0)) - r;
	}

	void main() {
		float coverage = 1.0;

		if (u_radius > 0.0) {
			vec2 half_size = u_rect_size.zw * 0.5;
			vec2 center = vec2(u_rect_size.x, u_rect_size.y) + half_size;
			vec2 p = v_pos - center;
			float r = u_radius;

			if (p.x < 0.0 && p.y < 0.0 && (u_edges & 1) == 0) r = 0.0;
			if (p.x > 0.0 && p.y < 0.0 && (u_edges & 2) == 0) r = 0.0;
			if (p.x < 0.0 && p.y > 0.0 && (u_edges & 4) == 0) r = 0.0;
			if (p.x > 0.0 && p.y > 0.0 && (u_edges & 8) == 0) r = 0.0;

			float dist = udRoundBox(p, half_size, r);
			// Analytic coverage ramp instead of a hard discard - see
			// gadvanced_shader.cpp's fragment shader for why (same technique,
			// kept consistent here so a rounded background image blitted
			// under a rounded solid-color overlay - e.g. eListboxServiceContent's
			// per-item background pixmap plus its selection highlight rect,
			// which can legitimately use two different radii - doesn't show a
			// seam where this shader's old hard edge disagreed with the
			// other shader's soft one.
			coverage = clamp(0.5 - dist, 0.0, 1.0);
			if (coverage <= 0.0) discard;
		}

		vec4 tex_color = texture(u_texture, v_uv);
		// Only the final present pass sets this (see setUnpremultiply()).
		vec3 rgb = tex_color.rgb;
		float out_a = tex_color.a;
		if (u_unpremultiply < -0.5)
			rgb *= tex_color.a; // raw-overwrite blit: store premultiplied (setPremultiply())
		else if (u_unpremultiply > 2.5 && tex_color.a > 0.0) {
			// Compositor computes S*A^2 + D*(1-A): pick the smallest A >= a for which
			// S = P/A^2 still fits in [0,1], so the colour term P is reproduced exactly.
			// P can never exceed a in a premultiplied frame - clamp stray values.
			rgb = min(rgb, vec3(tex_color.a));
			out_a = max(tex_color.a, sqrt(max(rgb.r, max(rgb.g, rgb.b))));
			rgb = min(rgb / (out_a * out_a), vec3(1.0));
		} else if (u_unpremultiply > 0.5 && tex_color.a > 0.0)
			rgb = min(rgb / tex_color.a, vec3(1.0));
		frag_color = vec4(rgb, out_a * u_global_alpha * coverage);
	}
)";
#endif

// ---------------------------------------------------------------------------
// GLES 2.0 shader sources
// ---------------------------------------------------------------------------
static const char *vertex_shader_es2 = R"(#version 100
	attribute vec4 pos_uv;
	uniform mat4 u_projection;
	varying vec2 v_uv;
	varying vec2 v_pos;
	void main() {
		gl_Position = u_projection * vec4(pos_uv.xy, 0.0, 1.0);
		v_uv  = pos_uv.zw;
		v_pos = pos_uv.xy;
	}
)";

static const char *fragment_shader_es2 = R"(#version 100
	precision mediump float;
	
	varying vec2 v_uv;
	varying vec2 v_pos;
	
	uniform sampler2D u_texture;
	uniform float u_global_alpha;
	uniform float u_unpremultiply;
	
	uniform vec4 u_rect_size;
	uniform float u_radius;
	// Per-corner radii (GLSL ES 1.00 has no bitwise ops on integers)
	uniform float u_r_tl;
	uniform float u_r_tr;
	uniform float u_r_bl;
	uniform float u_r_br;

	float udRoundBox(vec2 p, vec2 b, float r) {
		vec2 d = abs(p) - b + vec2(r);
		return min(max(d.x, d.y), 0.0) + length(max(d, 0.0)) - r;
	}

	void main() {
		float coverage = 1.0;

		if (u_radius > 0.0) {
			vec2 half_size = u_rect_size.zw * 0.5;
			vec2 center = vec2(u_rect_size.x, u_rect_size.y) + half_size;
			vec2 p = v_pos - center;
			float r = u_radius;

			if (p.x < 0.0 && p.y < 0.0) r = u_r_tl;
			if (p.x > 0.0 && p.y < 0.0) r = u_r_tr;
			if (p.x < 0.0 && p.y > 0.0) r = u_r_bl;
			if (p.x > 0.0 && p.y > 0.0) r = u_r_br;

			float dist = udRoundBox(p, half_size, r);
			// See the ES3 fragment shader above for why this is a coverage
			// ramp instead of a hard discard.
			coverage = clamp(0.5 - dist, 0.0, 1.0);
			if (coverage <= 0.0) discard;
		}

		vec4 tex_color = texture2D(u_texture, v_uv);
		// Only the final present pass sets this (see setUnpremultiply()).
		vec3 rgb = tex_color.rgb;
		float out_a = tex_color.a;
		if (u_unpremultiply < -0.5)
			rgb *= tex_color.a; // raw-overwrite blit: store premultiplied (setPremultiply())
		else if (u_unpremultiply > 2.5 && tex_color.a > 0.0) {
			// Compositor computes S*A^2 + D*(1-A): pick the smallest A >= a for which
			// S = P/A^2 still fits in [0,1], so the colour term P is reproduced exactly.
			// P can never exceed a in a premultiplied frame - clamp stray values.
			rgb = min(rgb, vec3(tex_color.a));
			out_a = max(tex_color.a, sqrt(max(rgb.r, max(rgb.g, rgb.b))));
			rgb = min(rgb / (out_a * out_a), vec3(1.0));
		} else if (u_unpremultiply > 0.5 && tex_color.a > 0.0)
			rgb = min(rgb / tex_color.a, vec3(1.0));
		gl_FragColor = vec4(rgb, out_a * u_global_alpha * coverage);
	}
)";

// ---------------------------------------------------------------------------
// Plain (no rounding / no unpremultiply) variants - see gTextureShader::drawBatch()
// ---------------------------------------------------------------------------
#if defined(HAVE_GLES3)
static const char *plain_vertex_shader_es3 = R"(#version 300 es
	layout(location = 0) in vec4 pos_uv;
	uniform mat4 u_projection;
	out vec2 v_uv;
	void main() {
		gl_Position = u_projection * vec4(pos_uv.xy, 0.0, 1.0);
		v_uv = pos_uv.zw;
	}
)";

static const char *plain_fragment_shader_es3 = R"(#version 300 es
	precision mediump float;
	in vec2 v_uv;
	out vec4 frag_color;
	uniform sampler2D u_texture;
	uniform float u_global_alpha;
	void main() {
		vec4 c = texture(u_texture, v_uv);
		frag_color = vec4(c.rgb, c.a * u_global_alpha);
	}
)";
#endif

static const char *plain_vertex_shader_es2 = R"(#version 100
	attribute vec4 pos_uv;
	uniform mat4 u_projection;
	varying vec2 v_uv;
	void main() {
		gl_Position = u_projection * vec4(pos_uv.xy, 0.0, 1.0);
		v_uv = pos_uv.zw;
	}
)";

static const char *plain_fragment_shader_es2 = R"(#version 100
	precision mediump float;
	varying vec2 v_uv;
	uniform sampler2D u_texture;
	uniform float u_global_alpha;
	void main() {
		vec4 c = texture2D(u_texture, v_uv);
		gl_FragColor = vec4(c.rgb, c.a * u_global_alpha);
	}
)";

// ---------------------------------------------------------------------------

#if defined(HAVE_GLES3)
gTextureShader::gTextureShader() : m_program_id(0), m_vao(0), m_vbo(0)
#else
gTextureShader::gTextureShader() : m_program_id(0), m_vbo(0)
#endif
{
}

gTextureShader::~gTextureShader()
{
	destroy();
}

void gTextureShader::destroy()
{
#if defined(HAVE_GLES3)
	if (gles::isGLES3() && m_vao) glDeleteVertexArrays(1, &m_vao);
	m_vao = 0;
#endif
	if (m_vbo) glDeleteBuffers(1, &m_vbo);
	m_vbo = 0;
	if (m_program_id) glDeleteProgram(m_program_id);
	m_program_id = 0;
	if (m_plain_program_id) glDeleteProgram(m_plain_program_id);
	m_plain_program_id = 0;
}

GLuint gTextureShader::buildPlainProgram()
{
#if defined(HAVE_GLES3)
	const char *vs_src = gles::isGLES3() ? plain_vertex_shader_es3   : plain_vertex_shader_es2;
	const char *fs_src = gles::isGLES3() ? plain_fragment_shader_es3 : plain_fragment_shader_es2;
#else
	const char *vs_src = plain_vertex_shader_es2;
	const char *fs_src = plain_fragment_shader_es2;
#endif
	GLuint vs = compileShader(GL_VERTEX_SHADER, vs_src);
	GLuint fs = compileShader(GL_FRAGMENT_SHADER, fs_src);
	if (!vs || !fs) {
		if (vs) glDeleteShader(vs);
		if (fs) glDeleteShader(fs);
		return 0;
	}
	GLuint prog = glCreateProgram();
	if (!gles::isGLES3())
		glBindAttribLocation(prog, 0, "pos_uv");
	glAttachShader(prog, vs);
	glAttachShader(prog, fs);
	glLinkProgram(prog);
	glDeleteShader(vs);
	glDeleteShader(fs);
	GLint linked = 0;
	glGetProgramiv(prog, GL_LINK_STATUS, &linked);
	if (!linked) {
		eDebug("[gTextureShader] plain program link failed - using the full program for batches");
		glDeleteProgram(prog);
		return 0;
	}
	m_plain_projection_location = glGetUniformLocation(prog, "u_projection");
	m_plain_texture_location    = glGetUniformLocation(prog, "u_texture");
	m_plain_alpha_location      = glGetUniformLocation(prog, "u_global_alpha");
	return prog;
}

GLuint gTextureShader::compileShader(GLenum type, const char *source)
{
	GLuint shader = glCreateShader(type);
	glShaderSource(shader, 1, &source, nullptr);
	glCompileShader(shader);

	GLint success;
	glGetShaderiv(shader, GL_COMPILE_STATUS, &success);
	if (!success) {
		GLchar info_log[512];
		glGetShaderInfoLog(shader, 512, nullptr, info_log);
		eDebug("[gTextureShader] compilation failed: %s", info_log);
		return 0;
	}
	return shader;
}

bool gTextureShader::init()
{
#if defined(HAVE_GLES3)
	const char *vs_src = gles::isGLES3() ? vertex_shader_es3   : vertex_shader_es2;
	const char *fs_src = gles::isGLES3() ? fragment_shader_es3 : fragment_shader_es2;
#else
	const char *vs_src = vertex_shader_es2;
	const char *fs_src = fragment_shader_es2;
#endif

	GLuint vertex_shader   = compileShader(GL_VERTEX_SHADER,   vs_src);
	GLuint fragment_shader = compileShader(GL_FRAGMENT_SHADER, fs_src);

	if (!vertex_shader || !fragment_shader) return false;

	m_program_id = glCreateProgram();

	if (!gles::isGLES3()) {
		glBindAttribLocation(m_program_id, 0, "pos_uv");
	}

	glAttachShader(m_program_id, vertex_shader);
	glAttachShader(m_program_id, fragment_shader);
	glLinkProgram(m_program_id);

	glDeleteShader(vertex_shader);
	glDeleteShader(fragment_shader);

	m_projection_location  = glGetUniformLocation(m_program_id, "u_projection");
	m_texture_location     = glGetUniformLocation(m_program_id, "u_texture");
	m_alpha_location       = glGetUniformLocation(m_program_id, "u_global_alpha");
	m_unpremult_location   = glGetUniformLocation(m_program_id, "u_unpremultiply");
	m_rect_size_location   = glGetUniformLocation(m_program_id, "u_rect_size");
	m_radius_location      = glGetUniformLocation(m_program_id, "u_radius");
	m_edges_location       = glGetUniformLocation(m_program_id, "u_edges");

	// Optional: if it fails to build, batches just keep using the full program.
	// ENIGMA_EGL_PLAIN_TEXTURE=0 disables it (A/B testing).
	if (!(getenv("ENIGMA_EGL_PLAIN_TEXTURE") && atoi(getenv("ENIGMA_EGL_PLAIN_TEXTURE")) == 0))
		m_plain_program_id = buildPlainProgram();

	if (!gles::isGLES3()) {
		m_edges_tl_location = glGetUniformLocation(m_program_id, "u_r_tl");
		m_edges_tr_location = glGetUniformLocation(m_program_id, "u_r_tr");
		m_edges_bl_location = glGetUniformLocation(m_program_id, "u_r_bl");
		m_edges_br_location = glGetUniformLocation(m_program_id, "u_r_br");
	}

#if defined(HAVE_GLES3)
	if (gles::isGLES3()) {
		glGenVertexArrays(1, &m_vao);
		glBindVertexArray(m_vao);
	}
#endif

	glGenBuffers(1, &m_vbo);
	glBindBuffer(GL_ARRAY_BUFFER, m_vbo);
	// Sized for the largest single upload this shader ever does: a batched
	// draw of up to kMaxBatchQuads quads (see drawBatch()), 6 vertices x 4
	// floats (x, y, u, v) each. A single drawTexture() call just uploads
	// its 6 vertices into the front of this same, larger buffer.
	glBufferData(GL_ARRAY_BUFFER, sizeof(float) * 6 * 4 * kMaxBatchQuads, nullptr, GL_DYNAMIC_DRAW);
	
	glVertexAttribPointer(0, 4, GL_FLOAT, GL_FALSE, 4 * sizeof(float), (void*)0);
	glEnableVertexAttribArray(0);
	
	glBindBuffer(GL_ARRAY_BUFFER, 0);
#if defined(HAVE_GLES3)
	if (gles::isGLES3()) glBindVertexArray(0);
#endif

	return true;
}

void gTextureShader::bind()
{
	glUseProgram(m_program_id);
}

// pos_uv (x, y, u, v) - must match init()'s VAO layout.
static const gles::VertexAttrib texture_attribs[] = {{0, 4, 0}};

void gTextureShader::drawVertices(const float* vertex_data, int vertex_count)
{
#if defined(HAVE_GLES3)
	GLuint vao = m_vao;
#else
	GLuint vao = 0;
#endif
	gles::setVertexData(vao, m_vbo, vertex_data, (GLsizeiptr)vertex_count * 4 * sizeof(float), 4, texture_attribs, 1);
	glDrawArrays(GL_TRIANGLES, 0, vertex_count);
	gles::endVertexData(texture_attribs, 1);
}

void gTextureShader::setResolution(float width, float height)
{
	bind();
	float ortho[16] = {
		2.0f / width, 0.0f, 0.0f, 0.0f,
		0.0f, -2.0f / height, 0.0f, 0.0f,
		0.0f, 0.0f, -1.0f, 0.0f,
		-1.0f, 1.0f, 0.0f, 1.0f
	};
	glUniformMatrix4fv(m_projection_location, 1, GL_FALSE, ortho);
	if (m_plain_program_id) {
		glUseProgram(m_plain_program_id);
		glUniformMatrix4fv(m_plain_projection_location, 1, GL_FALSE, ortho);
		glUseProgram(m_program_id);
	}
}

void gTextureShader::drawTexture(float x, float y, float width, float height, GLuint texture_id, float global_alpha, float radius, uint8_t edges)
{
	bind();
	
	glActiveTexture(GL_TEXTURE0);
	glBindTexture(GL_TEXTURE_2D, texture_id);
	glUniform1i(m_texture_location, 0);
	glUniform1f(m_alpha_location, global_alpha);
	
	glUniform1f(m_unpremult_location, m_premultiply ? -1.0f : (m_unpremultiply ? m_unpremultiply_power : 0.0f));
	glUniform4f(m_rect_size_location, x, y, width, height);
	glUniform1f(m_radius_location, radius);

	if (gles::isGLES3()) {
		glUniform1i(m_edges_location, (int)edges);
	} else {
		glUniform1f(m_edges_tl_location, (edges & 1) ? radius : 0.0f);
		glUniform1f(m_edges_tr_location, (edges & 2) ? radius : 0.0f);
		glUniform1f(m_edges_bl_location, (edges & 4) ? radius : 0.0f);
		glUniform1f(m_edges_br_location, (edges & 8) ? radius : 0.0f);
	}

	// x, y, u, v
	float vertices[24] = {
		x,         y,          0.0f, 0.0f,
		x,         y + height, 0.0f, 1.0f,
		x + width, y,          1.0f, 0.0f,
		x + width, y,          1.0f, 0.0f,
		x,         y + height, 0.0f, 1.0f,
		x + width, y + height, 1.0f, 1.0f
	};

	drawVertices(vertices, 6);
}

void gTextureShader::drawTextureSub(float x, float y, float width, float height, float sx, float sy, float sw, float sh, GLuint texture_id, float radius, uint8_t edges)
{
	bind();

	glActiveTexture(GL_TEXTURE0);
	glBindTexture(GL_TEXTURE_2D, texture_id);
	glUniform1i(m_texture_location, 0);
	glUniform1f(m_alpha_location, 1.0f);

	glUniform1f(m_unpremult_location, m_premultiply ? -1.0f : (m_unpremultiply ? m_unpremultiply_power : 0.0f));
	glUniform4f(m_rect_size_location, x, y, width, height);
	glUniform1f(m_radius_location, radius);

	if (gles::isGLES3()) {
		glUniform1i(m_edges_location, (int)edges);
	} else {
		glUniform1f(m_edges_tl_location, (edges & 1) ? radius : 0.0f);
		glUniform1f(m_edges_tr_location, (edges & 2) ? radius : 0.0f);
		glUniform1f(m_edges_bl_location, (edges & 4) ? radius : 0.0f);
		glUniform1f(m_edges_br_location, (edges & 8) ? radius : 0.0f);
	}

	const float u0 = (sx - x) / width, u1 = (sx + sw - x) / width;
	const float v0 = (sy - y) / height, v1 = (sy + sh - y) / height;
	float vertices[24] = {
		sx,      sy,      u0, v0,
		sx,      sy + sh, u0, v1,
		sx + sw, sy,      u1, v0,
		sx + sw, sy,      u1, v0,
		sx,      sy + sh, u0, v1,
		sx + sw, sy + sh, u1, v1
	};

	drawVertices(vertices, 6);
}

void gTextureShader::drawBatch(const float* vertex_data, int vertex_count, GLuint texture_id, float global_alpha)
{
	if (m_plain_program_id && !m_premultiply && !m_unpremultiply) {
		glUseProgram(m_plain_program_id);
		glActiveTexture(GL_TEXTURE0);
		glBindTexture(GL_TEXTURE_2D, texture_id);
		glUniform1i(m_plain_texture_location, 0);
		glUniform1f(m_plain_alpha_location, global_alpha);
		drawVertices(vertex_data, vertex_count);
		return;
	}

	bind();

	glActiveTexture(GL_TEXTURE0);
	glBindTexture(GL_TEXTURE_2D, texture_id);
	glUniform1i(m_texture_location, 0);
	glUniform1f(m_alpha_location, global_alpha);

	glUniform1f(m_unpremult_location, m_premultiply ? -1.0f : (m_unpremultiply ? m_unpremultiply_power : 0.0f));

	// No rounding for a batch - see the header comment on drawBatch().
	glUniform1f(m_radius_location, 0.0f);

	drawVertices(vertex_data, vertex_count);
}