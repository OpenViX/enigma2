#pragma once

#include <EGL/egl.h>
#ifdef HAVE_GLES3
#include <GLES3/gl3.h>
#else
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#endif
#include <lib/gdi/egl/gtexture_manager.h>
#include <lib/gdi/egl/inative_window_provider.h>
#include <lib/gdi/egl/shader/gadvanced_shader.h>
#include <lib/gdi/egl/shader/gshader.h>
#include <lib/gdi/egl/shader/gtext_shader.h>
#include <lib/gdi/egl/shader/gtexture_shader.h>
#include <lib/gdi/gfont_atlas.h>
#include <lib/gdi/gmaindc.h>

class gEGLDCAutoInit;

class gEGLDC : public gMainDC {
private:
	INativeWindowProvider* m_window_provider;
	EGLDisplay m_egl_display;
	EGLConfig m_egl_config;
	EGLContext m_egl_context;

	// One EGLSurface per framebuffer page for a pixmap-surface provider (see
	// tryInitEGL()/flip()) so rendering can ping-pong between pages instead
	// of always targeting the one currently being scanned out - just [0] for
	// a window-surface provider (real double buffering there is free via
	// eglSwapBuffers()). MAX_EGL_SURFACES bounds this to fbClass's own
	// practical maximum (triple buffering - see fb.cpp).
	static const int MAX_EGL_SURFACES = 3;
	EGLSurface m_egl_surfaces[MAX_EGL_SURFACES];
	int m_page_count; // 1 unless a multi-page pixmap-surface provider
	int m_render_page; // index into m_egl_surfaces currently bound for rendering

	int m_width;
	int m_height;
	int m_gles_version; // 2 or 3
	GLint m_max_texture_size;

	gShader m_basic_shader;
	gAdvancedShader m_advanced_shader;
	gTextureShader m_texture_shader;
	gTextShader m_text_shader;

	gFontAtlas m_font_atlas;
	gTextureManager m_texture_manager;

	std::vector<float> m_text_batch_buffer;
	const size_t MAX_BATCH_GLYPHS = 1024;

	// Batches consecutive gOpcode::blit calls that share the same texture,
	// blend requirement, and a single clip rect into one draw call instead
	// of one glDrawArrays per blit - targets sequences like
	// eWindowStyleSkinned::drawBorder()'s tiled border blits (many small
	// blits of the same tile pixmap in a row) and repeated same-icon
	// blits, without needing a shared texture atlas. Flushed the instant
	// anything that would change per-draw state appears (different
	// texture/blend/clip, rounding, or any other opcode type at all - see
	// flushBlitBatch()'s call sites), so this never reorders draws
	// relative to other opcodes and is visually identical to drawing them
	// one at a time.
	std::vector<float> m_blit_batch_buffer;
	GLuint m_blit_batch_tex_id = 0;
	bool m_blit_batch_blend = false;
	eRect m_blit_batch_clip;
	bool m_blit_batch_active = false;

	void flushBlitBatch();

	// Union of every area compositeTextOverlay() has painted into that
	// hasn't since been erased by executeClear() - lets executeClear() skip
	// its (CPU memset + texture upload + extra draw call) stale-text erase
	// entirely for the common case of a background clear that never had any
	// text composited over it, instead of paying that cost on every single
	// clear opcode once any text exists anywhere on screen.
	gRegion m_text_overlay_region;

	// Set by onGlyphCpuDrawn() whenever eTextPara::blit() (font.cpp) actually
	// wrote glyph pixels into m_pixmap's CPU buffer during the current
	// renderText/renderPara opcode - i.e. renderGlyph() declined a glyph (not
	// initialized) or blit() never offered one at all (border/pre-rendered
	// "image" glyphs). Reset before each blit() call in exec() and checked
	// afterward so compositeTextOverlay() only runs, and only re-uploads
	// m_pixmap's (possibly stale, untouched-this-draw) content, when the CPU
	// path actually ran - otherwise a glyph fully handled by renderGlyph()
	// (drawn straight to the GPU via the atlas/batch below, never touching
	// m_pixmap) would have compositeTextOverlay() paint whatever unrelated
	// old content happens to still sit in m_pixmap's buffer at that screen
	// position on top of it.
	bool m_cpu_overlay_dirty;

	bool tryInitEGL(int version);
	void cleanupEGL();

	// Copies page `from`'s content into page `to` entirely through the GL
	// pipeline (eglMakeCurrent with asymmetric draw/read surfaces, then
	// glBlitFramebuffer) instead of the INativeWindowProvider's CPU memcpy
	// fallback (see flip()) - see the comment at its call site for why this
	// exists: this GPU's tile-based deferred renderer appears to track a
	// surface's content by what it last wrote through the GL pipeline, not
	// by re-reading the surface's backing memory, so a CPU memcpy into that
	// memory can be partially invisible to it. Requires GLES3
	// (glBlitFramebuffer); returns false (no-op) on GLES2 or if
	// eglMakeCurrent fails, in which case the caller should fall back to
	// the CPU path. On success this leaves EGL's current surfaces as
	// draw=`to`, read=`from` (asymmetric, needed for the blit itself) - the
	// caller must restore the normal draw=read=`to` current state
	// afterward regardless of whether this returns true or false.
	bool gpuCopyPageContent(int from, int to);

	// dedicated opcode handlers
	void executeFill(const gOpcode* op);
	void executeFillRegion(const gOpcode* op);
	void executeRectangle(const gOpcode* op);
	void executeLine(const gOpcode* op);
	void executeBlit(const gOpcode* op);
	void executeDrawGlyph(const gOpcode* op);
	void executeClear(const gOpcode* op);
	void flushTextBatch();
	void setGlScissor(const eRect& rect);

	// Shared by gOpcode::renderText and gOpcode::renderPara for whatever
	// glyphs renderGlyph() below didn't handle (border/pre-rendered "image"
	// glyphs, or EGL not initialized - see m_cpu_overlay_dirty): once the
	// software eTextPara::blit() path (called via gDC::exec()) has written
	// those glyphs into m_pixmap's CPU buffer, upload the affected area as a
	// texture and composite it onto the real GPU surface - m_pixmap has no
	// GPU hook of its own, so without this nothing drawn into it ever
	// reaches the display.
	void compositeTextOverlay(eRect area);

	bool isHardwareAccelerated() const { return true; }
	bool renderGlyph(const ePoint& pos, const uint8_t* data, int width, int height, int pitch, const gRGB& color, uint64_t glyph_key) override;
	void onGlyphCpuDrawn() override { m_cpu_overlay_dirty = true; }

	// gDC::enableSpinner()/disableSpinner()/incrementSpinner() (grc.cpp) draw
	// the busy spinner with plain gPixmap::blit() calls straight into
	// m_pixmap's CPU buffer - entirely outside the gOpcode queue, so
	// gEGLDC::exec() never sees them. That's fine for a backend where
	// m_pixmap *is* the displayed framebuffer, but here m_pixmap is only a
	// CPU-side staging buffer for text (see compositeTextOverlay()'s
	// comment) - without composing m_spinner_pos to the real GPU surface
	// after each of these, the spinner is drawn but never actually reaches
	// the screen.
	void enableSpinner() override;
	void disableSpinner() override;
	void incrementSpinner() override;

	static gEGLDC* s_instance;

public:
	// initEGL() performs eglMakeCurrent() and must be called from gRC's own
	// render thread (see gRC::thread() in grc.cpp), NOT from the thread that
	// constructs gEGLDC (eInit/gEGLDCAutoInit) - EGL contexts are per-thread,
	// and gRC::thread() is the only thread that ever issues GL draw calls.
	static gEGLDC* getInstance() { return s_instance; }

	bool initEGL();
	gEGLDC(INativeWindowProvider* window_provider = nullptr, int width = 1280, int height = 720);
	virtual ~gEGLDC();

	virtual void setResolution(int xres, int yres, int bpp = 32) override;
	virtual void exec(const gOpcode* opcode);

	void flip();
	bool isInitialized() const { return m_egl_context != EGL_NO_CONTEXT; }
	int getGLESVersion() const { return m_gles_version; }
};