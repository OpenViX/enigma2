#pragma once

#include <atomic>
#include <mutex>
#include <vector>
#include <chrono>
#include <EGL/egl.h>
#ifdef HAVE_GLES3
#include <GLES3/gl3.h>
#else
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#endif
#include <lib/gdi/egl/gosd_capture.h>
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

	// Set in tryInitEGL() when a window-surface provider's driver did NOT
	// grant EGL_SWAP_BEHAVIOR_PRESERVED (see the eglSurfaceAttrib() check
	// there). Without it, eglSwapBuffers() is free to hand back a surface
	// with UNDEFINED content on the next frame - fatal for this backend's
	// dirty-rect-only opcode redraw, which assumes the render target
	// already holds the previous frame everywhere it doesn't explicitly
	// touch. Confirmed on real hardware (GigaBlue Quad 4K Pro/Nexus/NXPL):
	// "most areas of screen go black, some areas stay" - exactly the areas
	// each frame's opcodes happened to redraw. When true, every opcode
	// renders into m_shadow_fbo/m_shadow_texture instead - a persistent
	// offscreen target that behaves like a single-buffered "pixmap IS the
	// display" surface (see DreamboxWindowProvider) - and flip() blits its
	// FULL content into the window surface right before eglSwapBuffers().
	bool m_use_shadow_fbo = false;
	GLuint m_shadow_fbo = 0;
	GLuint m_shadow_texture = 0;

	// Diagnostic only, opt-in via ENIGMA_EGL_SHADOW_BLIT_STRIDE (parsed once
	// in tryInitEGL() right next to where m_use_shadow_fbo is decided) - see
	// flip()'s use of these. Default stride is 1, meaning "blit every frame",
	// i.e. today's actual shipping behaviour; unset/invalid values keep that
	// default. This exists purely to empirically find this platform's real
	// window-surface backbuffer count on real hardware (how many consecutive
	// skipped blits it takes before stale/torn content becomes visible),
	// which the previous scoped-blit attempt above had to guess at and got
	// wrong. NOT a proposed fix by itself - production must keep stride 1
	// until that count is known and a real dirty-region scheme is designed
	// around it.
	int m_shadow_blit_stride = 1;
	int m_shadow_blit_frame = 0;
	// Diagnostic, opt-in via ENIGMA_EGL_BLIT_INVALIDATE=1: call
	// glInvalidateFramebuffer() on the window surface right before the shadow
	// blit so a tiled GPU needn't load the stale buffer into tile memory first.
	bool m_blit_invalidate = false;

	// (Re)creates the EGL window surface for the current native window and makes it
	// current; false (leaving no surface) if the driver refused either step. Render
	// thread only.
	bool recreateWindowSurface();
	// Set when a resolution change could not get a usable window surface: nothing
	// can be presented, so exec() keeps retrying (throttled) until it works.
	bool m_surface_lost = false;
	std::chrono::steady_clock::time_point m_surface_retry_time;
	bool createShadowFramebuffer();
	// createShadowFramebuffer() with retries that first release GPU memory
	// (queued texture deletions, cached textures) - a large canvas right after a
	// resolution change can fail to allocate while the old buffers are still alive.
	bool recreateShadowFramebuffer();
	// Creation failed (m_use_shadow_fbo set but no FBO): exec() retries, throttled.
	std::chrono::steady_clock::time_point m_shadow_retry_time;
	void destroyShadowFramebuffer();

	// setResolution() (below) is called directly from Python (skin.py,
	// PicturePlayer, VideoFinetune) on the main thread, but actually
	// applying a resolution change touches GL/EGL state (shader projection
	// matrices, the shadow FBO's texture size, the native window's own
	// authored size) that's only ever valid to touch from gRC's render
	// thread - the only thread that ever makes the EGL context current (see
	// cleanupEGL()'s own comment on this same rule). Doing any of that
	// directly in setResolution() was a silent no-op at best (GL calls
	// issued with no context current on that thread) - confirmed as why a
	// 2560x1440 skin rendered with completely wrong sizes/positions while
	// 1080p ones worked fine: this canvas's *construction-time* size comes
	// from fbClass's boot-time mode (see egl_init.cpp), which commonly
	// happens to already be 1920x1080 - so a 1080p skin's setResolution()
	// call matched it and hit the early-return guard, never exercising this
	// path at all; anything else actually ran it, on the wrong thread.
	// setResolution() now only records the request; applyPendingResolutionChange()
	// - called from the top of flip(), on the render thread - does the real
	// work, at most one frame later.
	// Atomic: set on the main thread after m_pending_width/height are written, polled
	// by the render thread at every opcode - seq_cst makes the sizes visible first.
	std::atomic<bool> m_pending_resolution_change{false};
	int m_pending_width = 0;
	int m_pending_height = 0;
	// Guards m_pending_width/height (a second setResolution() during an apply
	// must not be seen half-written) and m_retired_pixmaps: the staging pixmap a
	// setResolution() replaces may still be in use by the render thread, so it is
	// parked here and only released by the render thread in
	// applyPendingResolutionChange(), never freed under it by the main thread.
	std::mutex m_resolution_mutex;
	std::vector<ePtr<gPixmap>> m_retired_pixmaps;
	void applyPendingResolutionChange();

	// External screenshot support (aio-grab) - see gosd_capture.h. Only
	// started for window-surface providers: on a pixmap-surface provider
	// (Dreambox) the OSD already IS /dev/fb0 memory and aio-grab's own
	// framebuffer path captures it correctly.
	gEGLOSDCapture m_osd_capture;
	void serviceOsdCapture();

	// GPU readback into m_pixmap - see its definition (gegldc.cpp, right
	// after serviceOsdCapture()) for why enableSpinner() needs this.
	void captureBackgroundIntoPixmap(const eRect& rect);
	void dumpSpinnerRestore();

	// GPU-only spinner (see gEGLDC::spinnerGpuPath()): the area under the spinner is copied
	// into a small texture once and redrawn from it (destructively, alpha included) before
	// each icon frame and at the erase, so nothing ever goes through a CPU readback/copy.
	bool m_spinner_gpu = false;
	GLuint m_spinner_bg_tex = 0;
	eRect m_spinner_gpu_rect;
	bool spinnerGpuPath();
	bool captureSpinnerGpu();
	void drawSpinnerGpu(bool with_icon);
	void releaseSpinnerGpu();
	void clearWindowSurfaceTransparent();

	// fbClass lock (ofgwrite's Mode 2 flash, see ImageManager.py) on a
	// window-surface platform: the window surface is a separate layer
	// composited ABOVE /dev/fb0, so ofgwrite's progress screen - drawn into
	// fb0 - stayed hidden under enigma's last frame. While locked, flip()
	// presents one fully transparent frame instead (m_shadow_fbo, enigma's
	// real UI, is left untouched) and nothing else; unlock's flush then
	// presents the preserved UI again. Only with the shadow FBO: without it
	// the window surface's own content is the UI and clearing it would lose it.
	bool m_lock_cleared = false;
	static void onFramebufferLockChanged(bool locked);
	// Wakes the render thread with a flush opcode even while locked
	// (gPainter::flush() is suppressed then).
	void requestFlush();

	// Diagnostic only, opt-in via ENIGMA_EGL_PROFILE=1 (read once in
	// initEGL()): one log line per flip() splitting that frame's render-thread
	// time by where it went. CPU-side wall time - GL calls are asynchronous,
	// so a GPU stall shows up in whichever call is forced to wait for it
	// (buffer map, texture upload, swap), which is exactly what this is for.
	bool m_profile = false;
	struct FrameProfile {
		double text_ms = 0, text_flush_ms = 0, vbo_ms = 0, atlas_ms = 0, band_ms = 0, overlay_ms = 0, other_ms = 0;
		int text_ops = 0, text_flushes = 0, glyphs = 0, atlas_uploads = 0, atlas_rows = 0, band_uploads = 0, band_rows = 0, overlays = 0, other_ops = 0;
		// Rectangle breakdown (see executeRectangle()): flat = basic-shader
		// path, adv1/adv2 = advanced-shader ops drawn in 1 or 2 passes, draws =
		// advanced-shader draw calls, adv_mpx = megapixels of clip-limited
		// area actually shaded by the advanced shader (all passes summed).
		int rect_flat = 0, rect_adv1 = 0, rect_adv2 = 0, rect_adv_draws = 0, rect_fast = 0;
		double rect_adv_mpx = 0;
	} m_prof;
	std::chrono::steady_clock::time_point m_prof_last_flip;
	static double msSince(const std::chrono::steady_clock::time_point& t0) {
		return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
	}

	// Logical canvas size: what the skin/widgets lay out against and what every
	// shader projection and draw coordinate is expressed in.
	int m_width;
	int m_height;

	// Physical render size: the size of the real GL targets (viewport, shadow
	// FBO, window surface). Identical to m_width x m_height unless the canvas
	// is larger than the GPU's GL_MAX_TEXTURE_SIZE / GL_MAX_RENDERBUFFER_SIZE
	// (m_max_tex_size) - e.g. a 2560x1440 skin on VideoCore IV (2048 limit) -
	// in which case it is the same aspect ratio shrunk to fit and everything is
	// rendered scaled by m_scale_x/y (the projection stays logical, so drawing
	// needs no change; scissors, blits and readbacks convert). m_max_tex_size
	// is 0 until the context is current; scale is 1.0 whenever it isn't needed.
	int m_phys_width = 0;
	int m_phys_height = 0;
	float m_scale_x = 1.0f;
	float m_scale_y = 1.0f;
	int m_max_tex_size = 0;
	// The GPU's real limit, kept even when scaling is compiled out (then
	// m_max_tex_size stays 0) - only used to say so in the log.
	int m_gpu_max_tex = 0;
	// The window compositor blends the surface as straight alpha, so the final
	// present pass must un-premultiply the frame (see
	// INativeWindowProvider::needsStraightAlphaPresent()). Forces the shader
	// present path even where glBlitFramebuffer() exists.
	bool m_straight_alpha_present = false;
	float m_unpremult_power = 1.0f;
	// Blits drawn with blending off copy straight RGBA raw; premultiply them in the
	// shader when the frame is premultiplied for a double-alpha compositor (H17).
	bool m_premultiply_blits = false;
	// Raw-overwrite draws write premultiplied colour (see drawFlatRects()).
	bool m_premultiply_overwrites = false;
	// The size the native window/surface was created at (the canvas size at
	// construction - egl_init.cpp hands the provider the same width/height).
	// When the canvas has to be scaled down, a physical size equal to this is
	// preferred (if the aspect ratio matches): the window then never needs to
	// be resized at all, which is both the proven-working configuration and
	// avoids depending on a platform's window-resize path.
	int m_native_width = 0;
	int m_native_height = 0;
	// Diagnostic: how many of the next presented frames to log (GL/EGL error
	// state, sizes) after a resolution change - to tell "nothing is being drawn
	// or swapped" from "drawn fine but not shown by the compositor" from a log.
	int m_log_frames_left = 0;
	// Set only by updatePhysicalSize() on the render thread (never derived from
	// m_width/m_height, which setResolution() changes on the main thread before
	// the render thread has applied the change) - so a GPU that never hits its
	// limit always takes the original, unscaled code paths.
	bool m_scaled = false;
	bool isScaled() const { return m_scaled; }
	void updatePhysicalSize(int logical_w, int logical_h);

	// Uploads the area [left, right) x [top, bottom) of the CPU text-overlay
	// staging pixmap (m_pixmap) into its GL texture. Unscaled: full-width rows,
	// as always (GLES2 has no GL_UNPACK_ROW_LENGTH). When that texture had to be
	// created smaller than the pixmap (see gTextureManager::setMaxTextureSize())
	// only the area itself is downsampled and uploaded, so the cost follows the
	// size of what was drawn, not the width of the screen.
	void uploadOverlayBand(GLuint tex_id, int left, int top, int right, int bottom);

	int m_gles_version; // 2 or 3

	gShader m_basic_shader;
	gAdvancedShader m_advanced_shader;
	gTextureShader m_texture_shader;
	gTextShader m_text_shader;

	gFontAtlas m_font_atlas;
	gTextureManager m_texture_manager;

	std::vector<float> m_text_batch_buffer;
	const size_t MAX_BATCH_GLYPHS = 1024;

	// The clip flushTextBatch() must scissor this batch's glyphs against -
	// captured once, when the batch starts (see renderGlyph()), NOT read
	// live from m_current_clip at flush time, because the batch is drawn
	// later than it's filled: by then m_current_clip may already be a
	// different widget's clip entirely, or (see exec()'s renderText/
	// renderPara handling) have been restored from the narrowed value it
	// was temporarily set to for this specific text draw back to the
	// wider one active around it. Mirrors m_blit_batch_clip below for the
	// identical reason on the blit-batching side.
	//
	// That narrowing is the actual fix this exists for: eTextPara::blit()'s
	// CPU path (font.cpp) always additionally intersects the active clip
	// with the renderText/renderPara opcode's own declared area ("clip &=
	// eRect(area...)") before drawing, which is what stops long text
	// exactly at its own column's edge - the GPU glyph path
	// (renderGlyph()) had no way to replicate that (it never receives
	// `area` at all), so text rendered via the atlas was only ever
	// clipped to the surrounding widget/row's clip, letting it overflow
	// past its own column into whatever's drawn next (observed: EPG title
	// text overflowing into the signal-strength meter column).
	gRegion m_text_batch_clip;

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
	bool m_blit_batch_true_alpha = false;
	eRect m_blit_batch_clip;
	bool m_blit_batch_active = false;

	// Selects which of two different alpha-channel blend formulas the next
	// blended draw uses - see the call sites (executeBlit/flushBlitBatch,
	// executeRectangle, flushTextBatch, compositeTextOverlay, and
	// executeClear's overlay recomposite) and this function's own definition
	// in gegldc.cpp for the full reasoning. In short: this render target's
	// alpha channel is read by the display's hardware compositor to decide
	// how much of the video plane shows through the OSD, and the two kinds
	// of blended content this backend draws need different alpha semantics
	// there - trueAlphaBlend=true (text, blitAlphaBlend/blitAlphaTest
	// images, a rectangle drawn with genuine alphaBlend) accumulates alpha
	// normally so it stays opaque (blocking video, as it should) when
	// layered over already-opaque content; trueAlphaBlend=false (a
	// near-transparent rounded/bordered background like a video window's
	// own "Pig" skin element, which isn't really semi-transparent UI so
	// much as a punched-through hole with decoration) makes the draw's own
	// alpha the absolute, unaccumulated result, since such a widget is
	// deliberately layered over whatever opaque parent/screen background
	// eWidgetDesktop::calcWidgetClipRegion() (lib/gui/ewidgetdesktop.cpp)
	// still paints underneath it and needs to defeat that, not blend with it.
	void setAlphaBlendMode(bool trueAlphaBlend);

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
	void executeClear(const gOpcode* op);
	void flushTextBatch();
	// Draws `vertices` (glyph quads, 8 floats per vertex) with whatever
	// texture is bound, once per m_text_batch_clip rect.
	void drawTextVertices(const std::vector<float>& vertices);

	// See flushTextBatch(): the main atlas texture is only updated before its
	// first use in a frame; glyphs new after that come from per-flush "band"
	// textures, deleted once the frame is presented.
	bool m_atlas_used_this_frame = false;
	std::vector<GLuint> m_atlas_band_textures;
	std::vector<float> m_text_main_scratch;
	std::vector<float> m_text_band_scratch;
	void releaseFrameTextures();
	void setGlScissor(const eRect& rect);

	// executeFill()/executeFillRegion()/executeClear()'s plain-overwrite
	// paths all draw one quad per (disjoint) clip.rects entry, sized to
	// exactly that rect - so, unlike executeRectangle()'s flat branch (which
	// draws the whole opcode area once per rect and relies on the scissor to
	// cut it down), none of them actually need glScissor at all: the quad's
	// own geometry already is the clip. That makes the whole loop just a
	// pile of independent, same-blend-state quads, which is exactly what
	// gShader::drawBatch() draws in one glDrawArrays call instead of one per
	// rect - callers must still bracket this themselves with
	// glDisable/glEnable(GL_BLEND) as before, since that depends on the
	// call site (executeClear()'s erase/recomposite pass wants blend back
	// on immediately after, for instance).
	void drawFlatRects(const gRegion& clip, float r, float g, float b, float a);

	// Shared by gOpcode::renderText and gOpcode::renderPara for whatever
	// glyphs renderGlyph() below didn't handle (border/pre-rendered "image"
	// glyphs, or EGL not initialized - see m_cpu_overlay_dirty): once the
	// software eTextPara::blit() path (called via gDC::exec()) has written
	// those glyphs into m_pixmap's CPU buffer, upload the affected area as a
	// texture and composite it onto the real GPU surface - m_pixmap has no
	// GPU hook of its own, so without this nothing drawn into it ever
	// reaches the display.
	//
	// trueAlphaBlend (default true) is forwarded to setAlphaBlendMode() -
	// real content (glyphs, the spinner icon itself) needs the accumulating
	// mode so it stacks correctly over whatever's already opaque. Erasing
	// content back to a transparent hole (disableSpinner()) needs false:
	// with true, alpha-blending m_pixmap's now-fully-transparent restored
	// pixels onto a destination that still holds the last opaque spinner
	// frame is a no-op (accumulating alpha never decreases), leaving that
	// frame permanently stuck on screen even after the icon stops animating.
	void compositeTextOverlay(eRect area, bool trueAlphaBlend = true);

	// Resets m_pixmap's CPU buffer to fully transparent (raw alpha byte 0,
	// not enigma's inverted gRGB convention - see the call site's comment)
	// across `area` before a border-text renderText draw runs its CPU
	// rasterization - eTextPara::blit() (font.cpp) only writes pixels where
	// it actually draws glyph cells, leaving anything else in that area
	// (padding between/around characters, or simply whatever this shared,
	// screen-sized staging buffer held there from an earlier, unrelated
	// draw at the same screen coordinates - it's never reset between
	// frames otherwise) as stale/untouched bytes that compositeTextOverlay()
	// then uploads and composites right along with the real glyph pixels.
	void clearOverlayArea(const eRect& area);

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
	// True while m_spinner_saved holds a background captured from the
	// *current* render target. A resolution change throws that target (and
	// m_pixmap/its overlay texture) away, so everything saved/positioned for the
	// old canvas is stale: restoring or recompositing it painted old-size
	// leftovers (stripes, a shrunken spinner) over the new canvas. Render
	// thread only (spinner ops and applyPendingResolutionChange() both run there).
	bool m_spinner_active = false;
	void enableSpinner() override;
	void disableSpinner() override;
	void incrementSpinner() override;

#ifdef HAVE_EGL_ANIMATION
	// Window show/hide animations (Layer A, see doc/ANIMATIONS.md). eWindow::show()/hide() send
	// sendShow/sendHide(rect) hints. At the hint the target's content in that rect is copied into
	// a texture ("before": the background for a show, the window for a hide). Once the window's
	// own draw opcodes have run, the first flush takes the second snapshot ("after") and plays
	// the animation here on the render thread, one flip() per frame, then leaves the target
	// holding exactly the real final content.
	struct WinAnim {
		bool pending = false;
		bool show = true;
		eRect rect;
		GLuint before = 0;
		int draw_ops = 0; // draw opcodes seen since the hint (a flush before any means "not painted yet")
		std::chrono::steady_clock::time_point started;
	};
	WinAnim m_winanim;
	static bool isDrawOpcode(int op);
	bool animationUsable() const;
	GLuint captureAnimTexture(const eRect& rect);
	void beginWindowAnimation(bool show, const eRect& hint);
	void cancelWindowAnimation();
	void finishWindowAnimation();
	void runWindowAnimation(bool show, const eRect& rect, GLuint before, GLuint after);
#endif

	static gEGLDC* s_instance;

public:
	// initEGL() performs eglMakeCurrent() and must be called from gRC's own
	// render thread (see gRC::thread() in grc.cpp), NOT from the thread that
	// constructs gEGLDC (eInit/gEGLDCAutoInit) - EGL contexts are per-thread,
	// and gRC::thread() is the only thread that ever issues GL draw calls.
	static gEGLDC* getInstance() { return s_instance; }

	bool initEGL();

	// Tears down the EGL context/surfaces/display. Like initEGL(), this
	// must run on gRC's own render thread and NOT on whatever thread ends
	// up destructing this object (eInit's teardown, driven by ~eMain() on
	// the main thread - see the destructor's own comment) - eglMakeCurrent()/
	// eglDestroyContext() etc. are meaningless (and observed to crash inside
	// the closed-source driver) once called against a context that isn't
	// current on, or was never made current on, the calling thread. gRC's
	// AutoInit priority (eAutoInitNumbers::graphic, see grc.cpp) is HIGHER
	// than gEGLDCAutoInit's (graphic-1), so gRC's own teardown - which joins
	// and ends the render thread - runs BEFORE gEGLDCAutoInit::closeNow()
	// even starts (LIFO close order: higher priority number inits later,
	// closes first). By the time the destructor below would otherwise call
	// this, the render thread is already gone - there is no longer any
	// thread left where these calls would be valid. So gRC::thread()
	// (grc.cpp) calls this itself, still running on the render thread,
	// right before it exits on gOpcode::shutdown. Safe to call again
	// afterward (from the destructor, as a fallback for any window
	// provider/configuration where that ordering assumption doesn't hold) -
	// it's a no-op once m_egl_display is already EGL_NO_DISPLAY.
	void cleanupEGL();

	gEGLDC(INativeWindowProvider* window_provider = nullptr, int width = 1280, int height = 720);
	virtual ~gEGLDC();

	virtual void setResolution(int xres, int yres, int bpp = 32) override;
	virtual void exec(const gOpcode* opcode);

	void flip();
	bool isInitialized() const { return m_egl_context != EGL_NO_CONTEXT; }
	int getGLESVersion() const { return m_gles_version; }

	// gDC::islocked() defaults to 0 (unlocked) and gMainDC never overrides
	// it either - gFBDC is the only other gMainDC subclass, and it forwards
	// to its own fbClass* (see gfbdc.h). Without this override, every
	// gPainter call (fill/blit/renderText/flush/flip/...) skips its
	// `if (m_dc->islocked()) return;` guard (grc.cpp) unconditionally on
	// this backend, so fbClass::lock()/unlock() - already called by
	// ImageManager.py bracketing ofgwrite's Mode 2 (non-active-slot, e2
	// stays running) flash - had no effect here: enigma2 kept drawing and
	// flipping/presenting pages throughout the flash, racing ofgwrite's own
	// direct framebuffer writes for the same physical memory. That race is
	// the progress-screen flicker/corruption seen after gEGLDC's earlier
	// fix restored real triple-buffered presentPixmap() rotation (see
	// project memory) - before that fix a leftover forceSingleBuffer flag
	// meant DM900 never exercised multi-page presentation, so the race was
	// latent. Forwarding to the same fbClass singleton DreamboxWindowProvider
	// already uses (see its init()) makes gEGLDC honor the same lock every
	// other backend does, with no ofgwrite or Python-side change needed.
	int islocked() const override;
};