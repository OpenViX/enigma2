#include <lib/base/eerror.h>
#include <lib/gdi/egl/gles_version.h>
#include <lib/gdi/egl/shader/gshader.h>
#include <vector>

// ---------------------------------------------------------------------------
// GLES 3.0 shader sources
// Uses layout(location=N), out vec4 frag_color
// ---------------------------------------------------------------------------
#if defined(HAVE_GLES3)
static const char* vertex_shader_es3 = R"(#version 300 es
    layout(location = 0) in vec2 position;
    layout(location = 1) in vec4 color;
    uniform mat4 u_projection;
    out vec4 v_color;
    void main() {
        gl_Position = u_projection * vec4(position, 0.0, 1.0);
        v_color = color;
    }
)";

static const char* fragment_shader_es3 = R"(#version 300 es
    precision mediump float;
    in vec4 v_color;
    uniform float u_rbswap;
    out vec4 frag_color;
    void main() {
        // On platforms where this render target's GL writes end up read
        // back in the opposite R/B order by the display scanout (proven via
        // a ground-truth debug swatch on Dreambox: a plain (1,0,0,1) uniform
        // came out blue, while textured draws - which get an equivalent
        // correction via their own upload trick in gtexture_manager.cpp -
        // came out correct), solid-color draws have no texture/swizzle stage
        // to piggyback on, so swap here instead - see gles::needsRBSwap's
        // comment (gles_version.h) for why this is now a per-platform
        // uniform rather than unconditional (NOT every EGL backend has this
        // scanout quirk - see gEGLDC::initEGL()).
        frag_color = mix(v_color, v_color.bgra, u_rbswap);
    }
)";
#endif

// ---------------------------------------------------------------------------
// GLES 2.0 shader sources
// Uses attribute/varying, gl_FragColor
// ---------------------------------------------------------------------------
static const char* vertex_shader_es2 = R"(#version 100
    attribute vec2 position;
    attribute vec4 color;
    uniform mat4 u_projection;
    varying vec4 v_color;
    void main() {
        gl_Position = u_projection * vec4(position, 0.0, 1.0);
        v_color = color;
    }
)";

static const char* fragment_shader_es2 = R"(#version 100
    precision mediump float;
    varying vec4 v_color;
    uniform float u_rbswap;
    void main() {
        // See the GLES3 fragment shader above for why this swap is here.
        gl_FragColor = mix(v_color, v_color.bgra, u_rbswap);
    }
)";

// ---------------------------------------------------------------------------

#if defined(HAVE_GLES3)
gShader::gShader() : m_program_id(0), m_vao(0), m_vbo(0) {}
#else
gShader::gShader() : m_program_id(0), m_vbo(0) {}
#endif

gShader::~gShader() {
	destroy();
}

void gShader::destroy() {
#if defined(HAVE_GLES3)
	if (gles::isGLES3() && m_vao)
		glDeleteVertexArrays(1, &m_vao);
	m_vao = 0;
#endif
	if (m_vbo)
		glDeleteBuffers(1, &m_vbo);
	m_vbo = 0;
	if (m_program_id)
		glDeleteProgram(m_program_id);
	m_program_id = 0;
}

GLuint gShader::compileShader(GLenum type, const char* source) {
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
		eDebug("[gShader] shader compilation failed: %s", info_log);
		return 0;
	}
	return shader;
}

bool gShader::init() {
#if defined(HAVE_GLES3)
	const char* vs_src = gles::isGLES3() ? vertex_shader_es3 : vertex_shader_es2;
	const char* fs_src = gles::isGLES3() ? fragment_shader_es3 : fragment_shader_es2;
#else
	const char* vs_src = vertex_shader_es2;
	const char* fs_src = fragment_shader_es2;
#endif

	GLuint vertex_shader = compileShader(GL_VERTEX_SHADER, vs_src);
	GLuint fragment_shader = compileShader(GL_FRAGMENT_SHADER, fs_src);

	if (!vertex_shader || !fragment_shader)
		return false;

	m_program_id = glCreateProgram();

	// For GLES2 we must bind attribute locations before linking
	if (!gles::isGLES3()) {
		glBindAttribLocation(m_program_id, 0, "position");
		glBindAttribLocation(m_program_id, 1, "color");
	}

	glAttachShader(m_program_id, vertex_shader);
	glAttachShader(m_program_id, fragment_shader);
	glLinkProgram(m_program_id);

	glDeleteShader(vertex_shader);
	glDeleteShader(fragment_shader);

	m_projection_location = glGetUniformLocation(m_program_id, "u_projection");
	m_rbswap_location = glGetUniformLocation(m_program_id, "u_rbswap");

	// VAO is a GLES3 core feature; in GLES2 we re-specify attribs per draw call
#if defined(HAVE_GLES3)
	if (gles::isGLES3()) {
		glGenVertexArrays(1, &m_vao);
		glBindVertexArray(m_vao);
	}
#endif

	glGenBuffers(1, &m_vbo);
	glBindBuffer(GL_ARRAY_BUFFER, m_vbo);
	// Sized for the largest single upload this shader ever does: a batched
	// draw of up to kMaxBatchQuads quads (see drawBatch()), 6 vertices x 6
	// floats (x, y, r, g, b, a) each. drawRect()/drawLine() just upload their
	// own, much smaller vertex count into the front of this same buffer.
	glBufferData(GL_ARRAY_BUFFER, sizeof(float) * 6 * 6 * kMaxBatchQuads, nullptr, GL_DYNAMIC_DRAW);

	glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 6 * sizeof(float), (void*)0);
	glEnableVertexAttribArray(0);
	glVertexAttribPointer(1, 4, GL_FLOAT, GL_FALSE, 6 * sizeof(float), (void*)(2 * sizeof(float)));
	glEnableVertexAttribArray(1);

	glBindBuffer(GL_ARRAY_BUFFER, 0);
#if defined(HAVE_GLES3)
	if (gles::isGLES3())
		glBindVertexArray(0);
#endif

	return true;
}

void gShader::bind() {
	glUseProgram(m_program_id);
	// Session-wide constant (see gles::needsRBSwap's comment) - cheap to set
	// on every bind() rather than adding a separate call site everywhere
	// this shader gets used.
	glUniform1f(m_rbswap_location, gles::needsRBSwap ? 1.0f : 0.0f);
}

void gShader::setResolution(float width, float height, float sx, float sy, float tx, float ty) {
	bind();
	// sx/sy/tx/ty: optional scale + move applied to every vertex before the projection (see gEGLDC::applyTransform())
	float ortho[16] = {2.0f * sx / width, 0.0f, 0.0f, 0.0f, 0.0f, -2.0f * sy / height, 0.0f, 0.0f, 0.0f, 0.0f, -1.0f, 0.0f, 2.0f * tx / width - 1.0f, 1.0f - 2.0f * ty / height, 0.0f, 1.0f};
	glUniformMatrix4fv(m_projection_location, 1, GL_FALSE, ortho);
}

// position (x, y) + color (r, g, b, a) - must match init()'s VAO layout.
static const gles::VertexAttrib shader_attribs[] = {{0, 2, 0}, {1, 4, 2}};

void gShader::drawVertices(GLenum mode, const float* vertex_data, int vertex_count) {
#if defined(HAVE_GLES3)
	GLuint vao = m_vao;
#else
	GLuint vao = 0;
#endif
	gles::setVertexData(vao, m_vbo, vertex_data, (GLsizeiptr)vertex_count * 6 * sizeof(float), 6, shader_attribs, 2);
	glDrawArrays(mode, 0, vertex_count);
	gles::endVertexData(shader_attribs, 2);
}

void gShader::drawRect(float x, float y, float width, float height, float r, float g, float b, float a) {
	bind();

	float vertices[36] = {x,			y,			   r, g, b, a, x,			y + height, r, g, b, a, x + width, y,			  r, g, b, a,
						   x + width, y,			   r, g, b, a, x,			y + height, r, g, b, a, x + width, y + height, r, g, b, a};

	drawVertices(GL_TRIANGLES, vertices, 6);
}

void gShader::drawLine(float x1, float y1, float x2, float y2, float r, float g, float b, float a) {
	bind();

	float vertices[12] = {x1, y1, r, g, b, a, x2, y2, r, g, b, a};

	drawVertices(GL_LINES, vertices, 2);
}

void gShader::drawBatch(const float* vertex_data, int vertex_count) {
	bind();
	drawVertices(GL_TRIANGLES, vertex_data, vertex_count);
}