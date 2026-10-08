#include <lib/gdi/egl/shader/gtext_shader.h>
#include <lib/gdi/egl/gles_version.h>
#include <lib/base/eerror.h>

// ---------------------------------------------------------------------------
// GLES 3.0 shader sources
// Two vertex attributes: pos_uv (location 0) and color (location 1)
// ---------------------------------------------------------------------------
#if defined(HAVE_GLES3)
static const char *vertex_shader_es3 = R"(#version 300 es
	layout(location = 0) in vec4 pos_uv;
	layout(location = 1) in vec4 color;
	
	uniform mat4 u_projection;
	
	out vec2 v_uv;
	out vec4 v_color;
	
	void main() {
		gl_Position = u_projection * vec4(pos_uv.xy, 0.0, 1.0);
		v_uv    = pos_uv.zw;
		v_color = color;
	}
)";

static const char *fragment_shader_es3 = R"(#version 300 es
	precision mediump float;
	
	in vec2 v_uv;
	in vec4 v_color;
	
	uniform sampler2D u_texture;
	uniform float u_rbswap;
	out vec4 frag_color;

	void main() {
		float mask = texture(u_texture, v_uv).r;
		// See gshader.cpp's fragment shader / gles::needsRBSwap's comment
		// (gles_version.h) for why this per-platform swap is here. Unlike
		// gtexture_shader.cpp (which relies on its *texture upload* already
		// being pre-swapped BGRA-as-RGBA on platforms that need it),
		// v_color here comes straight from gEGLDC::renderGlyph()'s own
		// color.r/g/b (semantically correct, not pre-swapped), so this
		// shader needs the same explicit uniform-driven swap gshader.cpp/
		// gadvanced_shader.cpp do on their own solid-color output.
		vec4 straight = vec4(v_color.rgb, v_color.a * mask);
		vec4 swapped = vec4(v_color.b, v_color.g, v_color.r, v_color.a * mask);
		frag_color = mix(straight, swapped, u_rbswap);
	}
)";
#endif

// ---------------------------------------------------------------------------
// GLES 2.0 shader sources
// Note: texture().r is replaced with texture2D().r; with GL_LUMINANCE the
// luminance value is replicated into r, g and b, so .r still returns the mask.
// ---------------------------------------------------------------------------
static const char *vertex_shader_es2 = R"(#version 100
	attribute vec4 pos_uv;
	attribute vec4 color;
	
	uniform mat4 u_projection;
	
	varying vec2 v_uv;
	varying vec4 v_color;
	
	void main() {
		gl_Position = u_projection * vec4(pos_uv.xy, 0.0, 1.0);
		v_uv    = pos_uv.zw;
		v_color = color;
	}
)";

static const char *fragment_shader_es2 = R"(#version 100
	precision mediump float;
	
	varying vec2 v_uv;
	varying vec4 v_color;
	
	uniform sampler2D u_texture;
	uniform float u_rbswap;

	void main() {
		// In GL_LUMINANCE textures the single channel is replicated into r/g/b
		float mask = texture2D(u_texture, v_uv).r;
		// See the GLES3 fragment shader above for why this swap is needed here.
		vec4 straight = vec4(v_color.rgb, v_color.a * mask);
		vec4 swapped = vec4(v_color.b, v_color.g, v_color.r, v_color.a * mask);
		gl_FragColor = mix(straight, swapped, u_rbswap);
	}
)";

// ---------------------------------------------------------------------------

#if defined(HAVE_GLES3)
gTextShader::gTextShader() : m_program_id(0), m_vao(0), m_vbo(0)
#else
gTextShader::gTextShader() : m_program_id(0), m_vbo(0)
#endif
{
}

gTextShader::~gTextShader()
{
	destroy();
}

void gTextShader::destroy()
{
#if defined(HAVE_GLES3)
	if (gles::isGLES3() && m_vao) glDeleteVertexArrays(1, &m_vao);
	m_vao = 0;
#endif
	if (m_vbo) glDeleteBuffers(1, &m_vbo);
	m_vbo = 0;
	if (m_program_id) glDeleteProgram(m_program_id);
	m_program_id = 0;
}

GLuint gTextShader::compileShader(GLenum type, const char *source)
{
	GLuint shader = glCreateShader(type);
	const std::string specialized = gles::specializeShaderSource(source);
	const char* specialized_src = specialized.c_str();
	glShaderSource(shader, 1, &specialized_src, nullptr);
	glCompileShader(shader);

	GLint success;
	glGetShaderiv(shader, GL_COMPILE_STATUS, &success);
	if (!success) {
		GLchar info_log[512];
		glGetShaderInfoLog(shader, 512, nullptr, info_log);
		eDebug("[gTextShader] shader compilation failed: %s", info_log);
		return 0;
	}
	return shader;
}

bool gTextShader::init()
{
	int max_glyphs        = 1024;
	int floats_per_vertex = 8;  // x, y, u, v, r, g, b, a
	int vertices_per_glyph = 6;
	int buffer_size = max_glyphs * vertices_per_glyph * floats_per_vertex * sizeof(float);

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
		glBindAttribLocation(m_program_id, 1, "color");
	}

	glAttachShader(m_program_id, vertex_shader);
	glAttachShader(m_program_id, fragment_shader);
	glLinkProgram(m_program_id);

	glDeleteShader(vertex_shader);
	glDeleteShader(fragment_shader);

	m_projection_location = glGetUniformLocation(m_program_id, "u_projection");
	m_color_location      = glGetUniformLocation(m_program_id, "u_text_color");
	m_texture_location    = glGetUniformLocation(m_program_id, "u_texture");
	m_rbswap_location     = glGetUniformLocation(m_program_id, "u_rbswap");

#if defined(HAVE_GLES3)
	if (gles::isGLES3()) {
		glGenVertexArrays(1, &m_vao);
		glBindVertexArray(m_vao);
	}
#endif

	glGenBuffers(1, &m_vbo);
	glBindBuffer(GL_ARRAY_BUFFER, m_vbo);
	glBufferData(GL_ARRAY_BUFFER, buffer_size, nullptr, GL_DYNAMIC_DRAW);

	// Attribute 0: pos_uv (4 floats)
	glVertexAttribPointer(0, 4, GL_FLOAT, GL_FALSE, floats_per_vertex * sizeof(float), (void*)0);
	glEnableVertexAttribArray(0);

	// Attribute 1: color (4 floats)
	glVertexAttribPointer(1, 4, GL_FLOAT, GL_FALSE, floats_per_vertex * sizeof(float), (void*)(4 * sizeof(float)));
	glEnableVertexAttribArray(1);
	
	glBindBuffer(GL_ARRAY_BUFFER, 0);
#if defined(HAVE_GLES3)
	if (gles::isGLES3()) glBindVertexArray(0);
#endif

	return true;
}

void gTextShader::bind()
{
	glUseProgram(m_program_id);
	// gEGLDC::flushTextBatch() (gegldc.cpp) drives this shader directly -
	// uploading its own VBO data and issuing glDrawArrays() itself, with no
	// other call site that sets the sampler uniform - so it's set here
	// instead, unconditionally on every bind().
	glUniform1i(m_texture_location, 0);
	glUniform1f(m_rbswap_location, gles::needsRBSwap ? 1.0f : 0.0f);
}

// pos_uv (x, y, u, v) + color (r, g, b, a) - must match init()'s VAO layout.
static const gles::VertexAttrib text_attribs[] = {{0, 4, 0}, {1, 4, 4}};

void gTextShader::setVertexData(const float* vertex_data, int vertex_count)
{
#if defined(HAVE_GLES3)
	GLuint vao = m_vao;
#else
	GLuint vao = 0;
#endif
	gles::setVertexData(vao, m_vbo, vertex_data, (GLsizeiptr)vertex_count * 8 * sizeof(float), 8, text_attribs, 2);
}

void gTextShader::endVertexData()
{
	gles::endVertexData(text_attribs, 2);
}

void gTextShader::setResolution(float width, float height)
{
	bind();
	float ortho[16] = {
		2.0f / width,  0.0f,           0.0f,  0.0f,
		0.0f,         -2.0f / height,  0.0f,  0.0f,
		0.0f,          0.0f,          -1.0f,  0.0f,
	   -1.0f,          1.0f,           0.0f,  1.0f
	};
	glUniformMatrix4fv(m_projection_location, 1, GL_FALSE, ortho);
}

