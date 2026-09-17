#include <algorithm>
#include <cstring>
#include <lib/base/eerror.h>
#include <lib/base/init.h>
#include <lib/base/init_num.h>
#include <lib/gdi/egl/gegldc.h>
#include <lib/gdi/egl/gles_version.h>
#include <lib/gdi/fb.h>
#include <lib/gdi/font.h>

#ifndef EGL_OPENGL_ES3_BIT_KHR
#define EGL_OPENGL_ES3_BIT_KHR 0x00000040
#endif
#ifndef GL_BGRA_EXT
#define GL_BGRA_EXT 0x80E1
#endif

// Initialization is now managed by gEGLDCAutoInit in egl_init.cpp
// to support runtime fallback to FBDC/SDLDC.

// ---------------------------------------------------------------------------
// tryInitEGL – attempts to create an EGL context for a specific GLES version.
// Returns true on success.  On failure the EGL state is left clean so that the
// caller can immediately try again with a different version.
// ---------------------------------------------------------------------------
bool gEGLDC::tryInitEGL(int version) {
	// 1. get the native display from our platform provider
	EGLNativeDisplayType native_display = m_window_provider->getNativeDisplay();

	m_egl_display = eglGetDisplay(native_display);
	if (m_egl_display == EGL_NO_DISPLAY) {
		eDebug("[gEGLDC] error: eglGetDisplay failed.");
		return false;
	}

	// 2. initialize EGL (only on first call; harmless to call again)
	EGLint major, minor;
	if (!eglInitialize(m_egl_display, &major, &minor)) {
		eDebug("[gEGLDC] error: eglInitialize failed.");
		return false;
	}
	eDebug("[gEGLDC] EGL version %d.%d initialised", major, minor);

	// 3. choose EGL config for the requested GLES version
	EGLint renderable_type = (version >= 3) ? EGL_OPENGL_ES3_BIT_KHR : EGL_OPENGL_ES2_BIT;
	bool pixmap_mode = m_window_provider->usesPixmapSurface();
	EGLint surface_type_bit = pixmap_mode ? EGL_PIXMAP_BIT : EGL_WINDOW_BIT;

	const EGLint config_attribs[] = {
		EGL_SURFACE_TYPE, surface_type_bit, EGL_RENDERABLE_TYPE, renderable_type, EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_ALPHA_SIZE, 8, EGL_DEPTH_SIZE, 0, EGL_STENCIL_SIZE, 0,
		EGL_NONE};

	EGLint num_configs = 0;
	if (!eglChooseConfig(m_egl_display, config_attribs, &m_egl_config, 1, &num_configs) || num_configs == 0) {
		eDebug("[gEGLDC] no suitable EGL config found for GLES%d.", version);
		return false;
	}

	// 4. create the context
	const EGLint context_attribs[] = {EGL_CONTEXT_CLIENT_VERSION, version, EGL_NONE};

	m_egl_context = eglCreateContext(m_egl_display, m_egl_config, EGL_NO_CONTEXT, context_attribs);
	if (m_egl_context == EGL_NO_CONTEXT) {
		eDebug("[gEGLDC] eglCreateContext for GLES%d failed.", version);
		return false;
	}

	// 5. create the rendering surface(s) - a pixmap surface per available
	// framebuffer page for platforms that only implement EGL_EXT_platform_base's
	// pixmap path (e.g. Dreambox's VC5/BEGL stack, where the "pixmap" IS live
	// display memory - see DreamboxWindowProvider's class comment), so this
	// can ping-pong rendering between pages instead of always rendering into
	// (and presenting) the one currently on screen - see flip(). A single
	// window surface otherwise, which already gets real double-buffering for
	// free via eglSwapBuffers().
	for (int i = 0; i < MAX_EGL_SURFACES; ++i)
		m_egl_surfaces[i] = EGL_NO_SURFACE;

	if (pixmap_mode) {
		PFNEGLCREATEPLATFORMPIXMAPSURFACEEXTPROC eglCreatePlatformPixmapSurfaceEXT =
			(PFNEGLCREATEPLATFORMPIXMAPSURFACEEXTPROC)eglGetProcAddress("eglCreatePlatformPixmapSurfaceEXT");
		if (!eglCreatePlatformPixmapSurfaceEXT) {
			eDebug("[gEGLDC] eglCreatePlatformPixmapSurfaceEXT not available.");
			eglDestroyContext(m_egl_display, m_egl_context);
			m_egl_context = EGL_NO_CONTEXT;
			return false;
		}

		m_page_count = std::max(1, std::min(m_window_provider->getPageCount(), MAX_EGL_SURFACES));
		for (int i = 0; i < m_page_count; ++i) {
			void* native_pixmap = m_window_provider->getNativePixmap(i);
			m_egl_surfaces[i] = eglCreatePlatformPixmapSurfaceEXT(m_egl_display, m_egl_config, native_pixmap, nullptr);
			if (m_egl_surfaces[i] == EGL_NO_SURFACE) {
				eDebug("[gEGLDC] eglCreatePlatformPixmapSurfaceEXT failed for page %d. EGL error: 0x%x", i, eglGetError());
				for (int j = 0; j < i; ++j)
					eglDestroySurface(m_egl_display, m_egl_surfaces[j]);
				eglDestroyContext(m_egl_display, m_egl_context);
				m_egl_context = EGL_NO_CONTEXT;
				return false;
			}
		}
	} else {
		m_page_count = 1;
		EGLNativeWindowType native_window = m_window_provider->getNativeWindow();
		m_egl_surfaces[0] = eglCreateWindowSurface(m_egl_display, m_egl_config, native_window, nullptr);
		if (m_egl_surfaces[0] == EGL_NO_SURFACE) {
			eDebug("[gEGLDC] eglCreateWindowSurface failed. EGL error: 0x%x", eglGetError());
			eglDestroyContext(m_egl_display, m_egl_context);
			m_egl_context = EGL_NO_CONTEXT;
			return false;
		}
	}

	// 6. make context current against the page the first frame will render
	// into. Start one page *ahead* of whatever the provider is showing at
	// startup (page 0 - see DreamboxWindowProvider::init()'s initial
	// setOffset(0)) so the very first frame never renders into the page
	// that's simultaneously being scanned out.
	m_render_page = (m_page_count > 1) ? 1 : 0;
	if (!eglMakeCurrent(m_egl_display, m_egl_surfaces[m_render_page], m_egl_surfaces[m_render_page], m_egl_context)) {
		eDebug("[gEGLDC] eglMakeCurrent failed.");
		for (int i = 0; i < m_page_count; ++i)
			eglDestroySurface(m_egl_display, m_egl_surfaces[i]);
		eglDestroyContext(m_egl_display, m_egl_context);
		m_egl_context = EGL_NO_CONTEXT;
		return false;
	}

	m_gles_version = version;

	// One-time dump of what this driver/hardware actually advertises, as
	// opposed to what the vendor SDK headers merely *declare* - header
	// presence (EGL_KHR_partial_update, EGL_KHR_fence_sync, etc. all exist
	// in eglext.h) says nothing about whether libvc5dream's V3D driver on
	// this specific box actually implements them. Logged once at startup so
	// this can be checked against the log rather than guessed at.
	{
		const char* egl_ext = eglQueryString(m_egl_display, EGL_EXTENSIONS);
		const char* gl_ext = (const char*)glGetString(GL_EXTENSIONS);
		eDebug("[gEGLDC] EGL_EXTENSIONS: %s", egl_ext ? egl_ext : "(null)");
		eDebug("[gEGLDC] GL_EXTENSIONS: %s", gl_ext ? gl_ext : "(null)");
	}

	return true;
}

// ---------------------------------------------------------------------------
// initEGL – cascades from GLES3 down to GLES2, then initialises shaders.
// ---------------------------------------------------------------------------
bool gEGLDC::initEGL() {
	// Try GLES3 first, fall back to GLES2
	if (!tryInitEGL(3)) {
		eDebug("[gEGLDC] GLES3 not available, falling back to GLES2.");
		if (!tryInitEGL(2)) {
			eDebug("[gEGLDC] error: neither GLES3 nor GLES2 could be initialised.");
			return false;
		}
	}

	// Publish the detected version so all shaders can query it
	gles::version = m_gles_version;
	eDebug("[gEGLDC] GLES%d context created.", m_gles_version);

	m_texture_manager.setDisplay(m_egl_display);

	// 7. basic GL state
	glViewport(0, 0, m_width, m_height);
	eglSwapInterval(m_egl_display, 1);

	// GL_BLEND and GL_SCISSOR_TEST are left enabled for the lifetime of the
	// context instead of being toggled on/off around every single opcode -
	// every draw call in this backend uses this same blend func, and for a
	// fully opaque source (alpha=1.0, the common case: solid fills,
	// backgrounds, non-alpha-blended blits) it produces exactly the same
	// result as blending disabled (src*1 + dst*0 == src), so there's no
	// correctness difference, only fewer state-change calls per frame.
	// Scissor is always set to the exact intended draw area immediately
	// before each draw (see setGlScissor() call sites), so a stale rect
	// left over from an earlier, unrelated opcode can never clip a draw
	// incorrectly. The one exception is gpuCopyPageContent()'s
	// glBlitFramebuffer(), which is also subject to the scissor test and
	// resets it to the full surface before blitting - see its comment.
	glEnable(GL_BLEND);
	// RGB always blends as normal "over" (GL_SRC_ALPHA,
	// GL_ONE_MINUS_SRC_ALPHA) - what makes a translucent widget visually
	// look tinted/composited against whatever real content (another
	// widget, the desktop) is behind it, exactly like gPixmap's own CPU
	// blendPixel() (gpixmap.cpp) does for the same case. The alpha channel
	// is different: this render target's own alpha is read by the
	// display's hardware compositor to decide how much of the video plane
	// shows through the OSD, and two genuinely different kinds of "blended"
	// draw need two different formulas there - see setAlphaBlendMode()
	// (called at every blend-enabling call site) for which and why. Default
	// to the "true" alphaBlend formula here since it's what the overwhelming
	// majority of blended draws (text, alphaBlend/alphaTest images) need;
	// callers that need the other one set it explicitly right before their
	// own draw.
	setAlphaBlendMode(true);
	glEnable(GL_SCISSOR_TEST);

	// 8. initialise shaders and resources
	if (!m_basic_shader.init()) {
		eFatal("[gEGLDC] failed to initialise basic shader!");
		return false;
	}
	if (!m_advanced_shader.init()) {
		eFatal("[gEGLDC] failed to initialise advanced shader!");
		return false;
	}
	if (!m_texture_shader.init()) {
		eFatal("[gEGLDC] failed to initialise texture shader!");
		return false;
	}
	if (!m_text_shader.init()) {
		eFatal("[gEGLDC] failed to initialise text shader!");
		return false;
	}
	if (!m_font_atlas.init()) {
		eFatal("[gEGLDC] failed to initialise font atlas!");
		return false;
	}

	// 9. upload projection matrices
	m_basic_shader.setResolution((float)m_width, (float)m_height);
	m_advanced_shader.setResolution((float)m_width, (float)m_height);
	m_texture_shader.setResolution((float)m_width, (float)m_height);
	m_text_shader.setResolution((float)m_width, (float)m_height);

	eDebug("[gEGLDC] GLES%d successfully initialised (%dx%d)", m_gles_version, m_width, m_height);
	return true;
}

void gEGLDC::setGlScissor(const eRect& rect) {
	int sx = rect.x();
	int sy = m_height - (rect.y() + rect.height());
	glScissor(sx, sy, rect.width(), rect.height());
}

void gEGLDC::setAlphaBlendMode(bool trueAlphaBlend) {
	// RGB factors are identical either way - see the call sites' comments
	// and initEGL()'s for the full picture. Only the alpha factors differ:
	//
	// trueAlphaBlend: standard Porter-Duff "over" (dst factor
	// GL_ONE_MINUS_SRC_ALPHA) - out.a = src.a + dst.a*(1-src.a). Stacks
	// correctly (an opaque destination stays opaque; two translucent
	// layers compound) and matches gPixmap's own CPU blendPixel() alpha
	// math. This is what text glyphs, blitAlphaBlend/blitAlphaTest images,
	// and a rectangle drawn with genuine alphaBlend need: they're real
	// translucent *content*, and should still fully block the video plane
	// wherever they sit over already-opaque UI, exactly as they visually
	// appear to (tinted, not see-through-to-video).
	//
	// !trueAlphaBlend: dst factor GL_ZERO - out.a = src.a, unconditionally
	// overwriting whatever alpha was already in the framebuffer. This is
	// for draws that aren't really translucent *content* so much as a
	// deliberately-near-transparent hole with decoration - a video
	// widget's own rounded/bordered background (e.g. a "Pig" skin element
	// with backgroundColor close to fully transparent). eWidgetDesktop
	// still paints whatever opaque parent/screen background sits behind
	// such a widget first (see calcWidgetClipRegion(), which keeps a
	// rounded/alphaBlend widget's backdrop visible/painted specifically so
	// normal translucent widgets CAN blend against it) - accumulating
	// "over" that already-opaque destination can never read back as
	// anything but opaque, no matter how transparent the widget's own
	// color is, which defeats the whole point of a near-transparent video
	// window background. Ignoring the destination entirely instead makes
	// this draw's own alpha the absolute truth for video-plane visibility
	// at the pixels it touches.
	if (trueAlphaBlend)
		glBlendFuncSeparate(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_ONE, GL_ONE_MINUS_SRC_ALPHA);
	else
		glBlendFuncSeparate(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_ONE, GL_ZERO);
}

void gEGLDC::executeFill(const gOpcode* op) {
	// A pending blit or text batch (see executeBlit()/renderGlyph()) hasn't
	// been drawn yet - flush both first so this fill lands in the correct
	// z-order relative to them, instead of ending up underneath content that
	// was actually submitted before it.
	flushBlitBatch();
	flushTextBatch();

	float r = m_foreground_color_rgb.r / 255.0f;
	float g = m_foreground_color_rgb.g / 255.0f;
	float b = m_foreground_color_rgb.b / 255.0f;
	float a = 1.0f - (m_foreground_color_rgb.a / 255.0f);

	eRect area = op->parm.fill->area;
	area.moveBy(m_current_offset);
	gRegion clip = m_current_clip & area;

	// The CPU/software renderer's gPixmap::fill() is a raw pixel overwrite
	// that never honors alpha (see its "*dst++ = col" loop in gpixmap.cpp) -
	// a plain fill/rectangle/clear opcode is expected to flatly overwrite
	// regardless of the color's alpha, matching that. Blend is left enabled
	// by default (see initEGL()) for the paths that always genuinely need
	// it (gradients, blits, text), so it must be explicitly turned off here
	// or a widget with a non-fully-opaque background color would start
	// alpha-blending with whatever stale content is already on screen
	// instead of overwriting it.
	glDisable(GL_BLEND);
	for (unsigned int i = 0; i < clip.rects.size(); ++i) {
		eRect r_area = clip.rects[i];
		setGlScissor(r_area);
		m_basic_shader.drawRect(r_area.x(), r_area.y(), r_area.width(), r_area.height(), r, g, b, a);
	}
	glEnable(GL_BLEND);
}

void gEGLDC::executeFillRegion(const gOpcode* op) {
	// See executeFill() above for why pending blit/text batches must flush first.
	flushBlitBatch();
	flushTextBatch();

	float r = m_foreground_color_rgb.r / 255.0f;
	float g = m_foreground_color_rgb.g / 255.0f;
	float b = m_foreground_color_rgb.b / 255.0f;
	float a = 1.0f - (m_foreground_color_rgb.a / 255.0f);

	gRegion region = op->parm.fillRegion->region;
	region.moveBy(m_current_offset);
	gRegion clip = m_current_clip & region;

	// See executeFill() above for why blend must be forced off here.
	glDisable(GL_BLEND);
	for (unsigned int i = 0; i < clip.rects.size(); ++i) {
		eRect r_area = clip.rects[i];
		setGlScissor(r_area);
		m_basic_shader.drawRect(r_area.x(), r_area.y(), r_area.width(), r_area.height(), r, g, b, a);
	}
	glEnable(GL_BLEND);
}

void gEGLDC::executeRectangle(const gOpcode* op) {
	// gDC::exec()'s own gOpcode::rectangle handling (grc.cpp) always resets
	// m_border_width/m_radius/m_radius_edges/the gradient state after every
	// rectangle draw so it never leaks into the next one - this backend
	// intercepts gOpcode::rectangle entirely (see exec()'s switch below) and
	// never calls through to gDC::exec() for it, so it must repeat that same
	// reset itself, on every return path (including the empty-clip one
	// below, which grc.cpp's equivalent also reaches unconditionally since
	// the reset there runs after gPixmap::drawRectangle() regardless of
	// whether that call's region ended up empty).
	if (m_current_clip.rects.empty()) {
		m_border_width = 0;
		m_radius = 0;
		m_radius_edges = 0;
		m_gradient_orientation = 0;
		m_gradient_fullSize = 0;
		m_gradient_alphablend = false;
		m_gradient_colors.clear();
		return;
	}

	// See executeFill() above for why pending blit/text batches must flush first.
	flushBlitBatch();
	flushTextBatch();

	if (m_radius > 0 || m_gradient_colors.size() > 0 || m_border_width > 0) {
		// useNew is eWidget.cpp's own proxy for "is this rectangle genuinely
		// alphaBlend" (see setAlphaBlendMode()'s comment) - it's literally
		// what gets passed as m_alphaBlend at every drawRectangle() call
		// site in lib/gui/ewidget.cpp.
		setAlphaBlendMode(op->parm.rectangle->useNew);
		for (unsigned int i = 0; i < m_current_clip.rects.size(); ++i) {
			setGlScissor(m_current_clip.rects[i]);
			m_advanced_shader.drawAdvancedRect(op->parm.rectangle->area.x() + m_current_offset.x(), op->parm.rectangle->area.y() + m_current_offset.y(), op->parm.rectangle->area.width(),
											   op->parm.rectangle->area.height(), m_radius, m_radius_edges, m_gradient_colors, m_gradient_orientation, m_gradient_alphablend > 0,
											   1.0f - (m_background_color_rgb.a / 255.0f), m_background_color_rgb, m_border_width, m_border_color);
		}
	} else {
		float r = m_background_color_rgb.r / 255.0f;
		float g = m_background_color_rgb.g / 255.0f;
		float b = m_background_color_rgb.b / 255.0f;
		float a = 1.0f - (m_background_color_rgb.a / 255.0f);

		// See executeFill()'s comment for why blend must be forced off for
		// a plain flat-color rectangle, to match the CPU renderer's raw
		// overwrite semantics.
		glDisable(GL_BLEND);
		for (unsigned int i = 0; i < m_current_clip.rects.size(); ++i) {
			setGlScissor(m_current_clip.rects[i]);
			m_basic_shader.drawRect(op->parm.rectangle->area.x() + m_current_offset.x(), op->parm.rectangle->area.y() + m_current_offset.y(), op->parm.rectangle->area.width(),
									op->parm.rectangle->area.height(), r, g, b, a);
		}
		glEnable(GL_BLEND);
	}

	m_border_width = 0;
	m_radius = 0;
	m_radius_edges = 0;
	m_gradient_orientation = 0;
	m_gradient_fullSize = 0;
	m_gradient_alphablend = false;
	m_gradient_colors.clear();
}

void gEGLDC::executeClear(const gOpcode* op) {
	// See executeFill() above for why pending blit/text batches must flush first.
	flushBlitBatch();
	flushTextBatch();

	float r = m_background_color_rgb.r / 255.0f;
	float g = m_background_color_rgb.g / 255.0f;
	float b = m_background_color_rgb.b / 255.0f;
	float a = 1.0f - (m_background_color_rgb.a / 255.0f);

	// A widget that hides/repaints submits a gOpcode::clear for its own
	// area, but NOT necessarily a new gOpcode::renderText if it no longer
	// has any text to draw there. Since text is composited from a
	// completely separate overlay (m_pixmap's texture, see
	// gOpcode::renderText below) rather than drawn into this same GPU
	// target, clearing the background alone does not erase any
	// previously-composited text sitting at this location - it would just
	// stay visible forever (e.g. an infobar that "doesn't disappear").
	//
	// m_text_overlay_region tracks the union of every area
	// compositeTextOverlay() has painted into that hasn't since been erased
	// here. The overwhelming majority of clears (list row highlights,
	// scrolling backgrounds, plain-color fills) never touched any text and
	// can skip the erase-and-recomposite work below entirely - only pay for
	// it when this clear's area actually overlaps something the overlay
	// drew.
	GLuint overlay_tex = m_pixmap->surface->gl_texture_id;
	bool maybe_has_overlay = overlay_tex != 0 && !m_text_overlay_region.empty();

	// The blend func's alpha factors are global GL state that persists
	// across opcodes (see setAlphaBlendMode()) - an earlier rectangle/blit
	// in this same frame may have left it in the "not true alphaBlend"
	// mode, which would be wrong for this recomposite: it's uploading real
	// per-pixel-alpha rendered text/border content back onto the screen,
	// same as flushTextBatch()/compositeTextOverlay(), so it needs the
	// normal accumulating formula.
	if (maybe_has_overlay)
		setAlphaBlendMode(true);

	for (unsigned int i = 0; i < m_current_clip.rects.size(); ++i) {
		eRect area = m_current_clip.rects[i];
		setGlScissor(area);
		// See executeFill()'s comment: this flat background overwrite must
		// not blend with whatever's already on screen, matching the CPU
		// renderer's raw-overwrite clear semantics - unlike the erase/
		// recomposite block below, which is genuinely alpha-aware and
		// relies on blend being enabled (the default - see initEGL()).
		glDisable(GL_BLEND);
		m_basic_shader.drawRect(area.x(), area.y(), area.width(), area.height(), r, g, b, a);
		glEnable(GL_BLEND);

		if (!maybe_has_overlay)
			continue;

		gRegion overlap = gRegion(area) & m_text_overlay_region;
		if (overlap.empty())
			continue;

		int pw = m_pixmap->size().width();
		int ph = m_pixmap->size().height();
		uint8_t* base = (uint8_t*)m_pixmap->surface->data;
		int stride = pw * 4;

		for (unsigned int j = 0; j < overlap.rects.size(); ++j) {
			eRect erase_area = overlap.rects[j];
			int left = std::max(0, erase_area.left());
			int top = std::max(0, erase_area.top());
			int right = std::min(pw, erase_area.left() + erase_area.width());
			int bottom = std::min(ph, erase_area.top() + erase_area.height());
			if (right <= left || bottom <= top)
				continue;

			for (int y = top; y < bottom; ++y)
				memset(base + (size_t)y * stride + (size_t)left * 4, 0, (size_t)(right - left) * 4);

			glBindTexture(GL_TEXTURE_2D, overlay_tex);
			glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
			glTexSubImage2D(GL_TEXTURE_2D, 0, 0, top, pw, bottom - top, GL_RGBA, GL_UNSIGNED_BYTE, base + (size_t)top * stride);

			setGlScissor(eRect(left, top, right - left, bottom - top));
			m_texture_shader.drawTexture(0, 0, (float)m_width, (float)m_height, overlay_tex);
		}

		m_text_overlay_region -= overlap;
	}
}

void gEGLDC::executeLine(const gOpcode* op) {
	float r = m_foreground_color_rgb.r / 255.0f;
	float g = m_foreground_color_rgb.g / 255.0f;
	float b = m_foreground_color_rgb.b / 255.0f;
	float a = 1.0f - (m_foreground_color_rgb.a / 255.0f);

	if (m_current_clip.rects.empty())
		return;

	// See executeFill()'s comment for why pending blit/text batches must flush first.
	flushBlitBatch();
	flushTextBatch();

	// See executeFill()'s comment: gPixmap::line() is a raw-overwrite
	// Bresenham rasterizer with no alpha blending, so this must match.
	glDisable(GL_BLEND);
	for (unsigned int i = 0; i < m_current_clip.rects.size(); ++i) {
		setGlScissor(m_current_clip.rects[i]);
		m_basic_shader.drawLine(op->parm.line->start.x() + m_current_offset.x(), op->parm.line->start.y() + m_current_offset.y(), op->parm.line->end.x() + m_current_offset.x(),
								op->parm.line->end.y() + m_current_offset.y(), r, g, b, a);
	}
	glEnable(GL_BLEND);
}

void gEGLDC::executeBlit(const gOpcode* opcode) {
	const gOpcode::para::pblit* op = opcode->parm.blit;

	// gPainter::blit() (grc.cpp) AddRef()s op->pixmap when it queues this
	// opcode, precisely so the pixmap survives even if its last Python/C++
	// reference goes away before the render thread gets around to processing
	// this blit. gDC::exec()'s generic (non-EGL) blit case (grc.cpp) balances
	// that with pixmap->Release() plus delete o->parm.blit once it's done -
	// but gEGLDC::exec() calls executeBlit() directly instead of going
	// through gDC::exec()'s switch, and this function never did either of
	// those. Every single blit through this backend - not just the first
	// time a given pixmap is drawn, EVERY draw of it - permanently leaked one
	// AddRef() (and the heap-allocated pblit struct itself), so a pixmap's
	// underlying refcount could never reach zero no matter how thoroughly
	// its Python/C++ owners let go of it: it had already accumulated more
	// AddRef()s than any amount of caller-side cleanup could ever release.
	// That's what made gSurface::~gSurface() (and with it, the GPU texture
	// release in gTextureManager) never run - not a missing-check bug in any
	// specific caller, but every blit call site leaking equally, just at a
	// rate proportional to how often each was actually drawn (which is why
	// eListbox's orGrid content, redrawing many distinct large images far
	// more often than a typical orVertical/orHorizontal list, exhausted
	// GPU/ION memory so much faster despite going through the exact same
	// leak). This guard's destructor runs on every exit path below,
	// including every early return, so it always releases exactly the one
	// reference/allocation this specific opcode is responsible for.
	struct BlitOpcodeGuard {
		const gOpcode::para::pblit* op;
		~BlitOpcodeGuard() {
			if (op->pixmap)
				op->pixmap->Release();
			delete op;
		}
	} guard{op};

	if (!op->pixmap)
		return;

	// Reclaim any textures already queued for deletion (their source
	// gPixmap died - e.g. Python replaced a grid/list entry's pixmap
	// reference on redraw, see gSurface::~gSurface() in gpixmap.cpp)
	// BEFORE getTexture() below potentially allocates GPU memory for a new
	// one. processDeletions() is normally only reached once per real frame
	// (at gOpcode::flush/flip, see exec()'s switch), which is too late for
	// this specific ordering problem: a widget that rebuilds its content
	// (a content grid navigating to a new selection, say) releases its OLD
	// pixmaps - which queues their textures for deletion - and then
	// submits blit opcodes for the NEW ones, ALL within the same frame,
	// before that frame's own flush/flip is ever reached. Deletion only
	// happening at the end meant the old and new textures were both
	// GPU-resident simultaneously for the whole frame instead of the old
	// one's memory being reclaimed first - a transient doubling of GPU
	// texture memory that's exactly what a content grid with many visible,
	// uncached, per-item images (poster art, thumbnails - anything not
	// going through PixmapCache) would hit on every navigation step. Cheap
	// when there's nothing queued (a mutex lock + empty check - see
	// gTextureManager::processDeletions()), so safe to call this often.
	m_texture_manager.processDeletions();

	GLuint tex_id = m_texture_manager.getTexture(op->pixmap);
	if (tex_id == 0)
		return;

	// Replicate gPixmap::blit()'s (gpixmap.cpp) own position/size resolution
	// exactly - that CPU function is this codebase's ground truth for what
	// the blitScale/blitKeepAspectRatio/alignment flags mean, and this
	// backend has to match it since a plain (non-blitScale) blit's
	// op->position is NOT a real target size to stretch to: callers like
	// ePixmap::event(evtPaint) (lib/gui/epixmap.cpp) always pass the
	// widget's full box as position regardless of whether scaling was
	// actually requested, with only the flags bit distinguishing the two -
	// unconditionally treating position as the destination size (as this
	// used to) force-stretched/distorted every non-scaled icon to its
	// widget's box and silently dropped blitKeepAspectRatio's letterboxing
	// for every scaled one.
	const eSize src_size = op->pixmap->size();
	eRect pos = op->position;

	if (!(op->flags & gPixmap::blitScale)) {
		// pos' size is ignored if left or top aligning; if its size isn't
		// set, centre/right/bottom aligning is ignored.
		if (pos.size().isValid()) {
			eRect box = pos;
			if (op->flags & gPixmap::blitHAlignCenter)
				pos.setLeft(box.left() + (box.width() - src_size.width()) / 2);
			else if (op->flags & gPixmap::blitHAlignRight)
				pos.setLeft(box.right() - src_size.width());

			if (op->flags & gPixmap::blitVAlignCenter)
				pos.setTop(box.top() + (box.height() - src_size.height()) / 2);
			else if (op->flags & gPixmap::blitVAlignBottom)
				pos.setTop(box.bottom() - src_size.height());
		}
		pos.setWidth(src_size.width());
		pos.setHeight(src_size.height());
	} else if (pos.size() != src_size && (op->flags & gPixmap::blitKeepAspectRatio) && src_size.width() > 0 && src_size.height() > 0) {
		eRect box = pos;
		// Compare box.width()/src.width() vs box.height()/src.height()
		// without floating point, the same comparison gPixmap::blit() makes
		// via its FIX-point scale_x/scale_y - cross-multiply instead.
		if ((long long)box.width() * src_size.height() > (long long)box.height() * src_size.width()) {
			// vertical is full height, shrink horizontal to preserve aspect
			int w = src_size.width() * box.height() / src_size.height();
			pos.setWidth(w);
			if (op->flags & gPixmap::blitHAlignCenter)
				pos.moveBy((box.width() - w) / 2, 0);
			else if (op->flags & gPixmap::blitHAlignRight)
				pos.moveBy(box.width() - w, 0);
		} else {
			// horizontal is full width, shrink vertical to preserve aspect
			int h = src_size.height() * box.width() / src_size.width();
			pos.setHeight(h);
			if (op->flags & gPixmap::blitVAlignCenter)
				pos.moveBy(0, (box.height() - h) / 2);
			else if (op->flags & gPixmap::blitVAlignBottom)
				pos.moveBy(0, box.height() - h);
		}
	}
	// else: blitScale is set and either pos already equals src_size, or
	// blitKeepAspectRatio wasn't requested - pos is already the correct
	// (possibly non-uniformly stretched) target rect as given.

	pos.moveBy(m_current_offset);

	gRegion clip;
	if (op->clip.valid()) {
		eRect c = op->clip;
		c.moveBy(m_current_offset);
		clip = gRegion(c) & m_current_clip;
	} else {
		clip = m_current_clip;
	}

	if (clip.rects.empty())
		return;

	// Unlike our own solid-color fills (where we compute alpha=1.0 ourselves
	// for "opaque"), a plain blit's alpha comes from the source pixmap's own
	// data, which this backend doesn't control - a caller that didn't pass
	// blitAlphaBlend/blitAlphaTest wants a fast, fully opaque copy that
	// ignores whatever the source's alpha channel happens to contain, so
	// blend must stay data-independent rather than being left always-on
	// like scissor.
	bool enable_blend = (op->flags & (gPixmap::blitAlphaBlend | gPixmap::blitAlphaTest)) || (m_radius > 0);

	// See setAlphaBlendMode()'s comment. A blit's own blitAlphaBlend/
	// blitAlphaTest flag means the source pixmap's alpha is genuine
	// translucent content (icons with soft edges, etc.) - the accumulating
	// formula. A blit that's only blending because of a corner radius
	// (rounding forces blend on so the SDF edge anti-aliases smoothly, even
	// for an otherwise fully opaque image) isn't declaring itself
	// translucent content in that same sense, so it gets the other formula
	// - harmless for its opaque interior (src.a=1 either way) and only
	// matters for the 1px rounded-corner AA fringe.
	bool true_alpha_blend = (op->flags & (gPixmap::blitAlphaBlend | gPixmap::blitAlphaTest)) != 0;

	float x = pos.x();
	float y = pos.y();
	float width = pos.width();
	float height = pos.height();

	// Batching needs exactly one scissor rect (a batched draw call has only
	// one active scissor for every quad in it) and no rounding (the texture
	// shader's corner SDF uses a single u_rect_size uniform sized for one
	// quad - wrong for every quad but the first in a batch). Anything else
	// falls back to the original immediate per-rect draw.
	bool can_batch = clip.rects.size() == 1 && m_radius <= 0;

	if (!can_batch) {
		flushBlitBatch();
		flushTextBatch();
		if (enable_blend) {
			setAlphaBlendMode(true_alpha_blend);
			glEnable(GL_BLEND);
		} else
			glDisable(GL_BLEND);
		for (unsigned int i = 0; i < clip.rects.size(); ++i) {
			setGlScissor(clip.rects[i]);
			m_texture_shader.drawTexture(x, y, width, height, tex_id, 1.0f, m_radius, m_radius_edges);
		}
		if (!enable_blend)
			glEnable(GL_BLEND);
		return;
	}

	const eRect& r = clip.rects[0];
	bool state_changed = m_blit_batch_active && (tex_id != m_blit_batch_tex_id || enable_blend != m_blit_batch_blend || true_alpha_blend != m_blit_batch_true_alpha || r != m_blit_batch_clip);
	bool full = m_blit_batch_buffer.size() >= (size_t)gTextureShader::kMaxBatchQuads * 24;
	if (state_changed || full)
		flushBlitBatch();

	if (!m_blit_batch_active) {
		// Starting a fresh blit batch: flush any pending text batch first so
		// text queued *before* this blit (e.g. a label drawn just before an
		// icon in the same row) still draws before it, not after - see
		// executeFill()'s comment for the general reasoning.
		flushTextBatch();
		m_blit_batch_tex_id = tex_id;
		m_blit_batch_blend = enable_blend;
		m_blit_batch_true_alpha = true_alpha_blend;
		m_blit_batch_clip = r;
		m_blit_batch_active = true;
	}

	// x, y, u, v per vertex - same layout/winding as gTextureShader::drawTexture().
	float quad[24] = {x,		 y,			 0.0f, 0.0f, x,			y + height, 0.0f, 1.0f, x + width, y,			 1.0f, 0.0f,
					  x + width, y,			 1.0f, 0.0f, x,			y + height, 0.0f, 1.0f, x + width, y + height, 1.0f, 1.0f};
	m_blit_batch_buffer.insert(m_blit_batch_buffer.end(), quad, quad + 24);
}

void gEGLDC::flushBlitBatch() {
	if (!m_blit_batch_active)
		return;
	m_blit_batch_active = false;

	if (m_blit_batch_buffer.empty())
		return;

	if (m_blit_batch_blend) {
		setAlphaBlendMode(m_blit_batch_true_alpha);
		glEnable(GL_BLEND);
	} else
		glDisable(GL_BLEND);

	setGlScissor(m_blit_batch_clip);
	int vertex_count = (int)(m_blit_batch_buffer.size() / 4);
	m_texture_shader.drawBatch(m_blit_batch_buffer.data(), vertex_count, m_blit_batch_tex_id, 1.0f);

	if (!m_blit_batch_blend)
		glEnable(GL_BLEND);

	m_blit_batch_buffer.clear();
}

bool gEGLDC::renderGlyph(const ePoint& pos, const uint8_t* data, int width, int height, int pitch, const gRGB& color, uint64_t glyph_key) {
	if (!isInitialized())
		return false; // let eTextPara::blit() (font.cpp) fall back to its CPU path

	if (width <= 0 || height <= 0)
		return true; // nothing to draw (e.g. a space), but this glyph *is* handled

	if (m_text_batch_buffer.empty()) {
		// Starting a fresh text batch: flush any pending blit batch first so
		// a blit queued *before* this text (e.g. an icon drawn just before a
		// label in the same row) still draws before it, not after - see
		// executeFill()'s comment for the general reasoning. Also capture
		// the clip this batch will be drawn under - see m_text_batch_clip's
		// declaration comment for why flushTextBatch() must use this
		// snapshot rather than reading m_current_clip live.
		flushBlitBatch();
		m_text_batch_clip = m_current_clip;
	}

	glyph_uv uv;
	bool was_cached = m_font_atlas.getGlyph(glyph_key, uv);

	if (!was_cached) {
		// Only flush the current batch first if this glyph would actually
		// trigger addGlyph()'s atlas-full reset (which clears m_glyphs and
		// would leave any already-batched-but-undrawn quad's UVs pointing at
		// whatever glyph ends up reoccupying that texture region) - NOT on
		// every cache miss unconditionally. A plain row-advance (the
		// overwhelming majority of additions - the atlas is 2048x2048,
		// rarely actually full) leaves all existing glyphs' data and UVs
		// untouched, so there's nothing to protect against, and flushing
		// here anyway means uploading the atlas's dirty region and drawing
		// with it once per *individual* new glyph instead of batching many
		// new glyphs' worth of atlas changes into one upload+draw at the
		// next real flush point - each of those premature per-glyph flushes
		// measured 4.5-13ms (a texture the GPU is still using getting
		// modified mid-frame forces a pipeline sync), which is what made a
		// screen with many not-yet-cached glyphs (a first-ever open) take
		// seconds instead of a couple hundred milliseconds.
		if (m_font_atlas.wouldOverflow(width, height))
			flushTextBatch();
		m_font_atlas.addGlyph(glyph_key, width, height, data, pitch, uv);
	}

	if (uv.width == 0 || uv.height == 0)
		return true; // empty-space glyph already recorded in the atlas map

	// pos is already an absolute destination-surface pixel position (same
	// rxbase/rybase eTextPara::blit()'s CPU path writes to directly) - not
	// relative to m_current_offset like fill/rectangle/blit's opcode-supplied
	// coordinates are, so unlike executeFill() etc. it must NOT be added
	// again here, or a GPU-handled glyph would land at a different position
	// than a CPU-handled one (border text, say) drawn for the very same
	// eTextPara whenever m_current_offset is non-zero.
	float r = color.r / 255.0f;
	float g = color.g / 255.0f;
	float b = color.b / 255.0f;
	float a = 1.0f - (color.a / 255.0f);

	float x = (float)pos.x();
	float y = (float)pos.y();
	float w = (float)uv.width;
	float h = (float)uv.height;

	// 6 vertices × 8 floats: x, y, u, v, r, g, b, a
	float vertices[48] = {x,	 y, uv.u0, uv.v0, r, g, b, a, x, y + h, uv.u0, uv.v1, r, g, b, a, x + w, y,		uv.u1, uv.v0, r, g, b, a,
						  x + w, y, uv.u1, uv.v0, r, g, b, a, x, y + h, uv.u0, uv.v1, r, g, b, a, x + w, y + h, uv.u1, uv.v1, r, g, b, a};

	m_text_batch_buffer.insert(m_text_batch_buffer.end(), vertices, vertices + 48);

	if (m_text_batch_buffer.size() >= MAX_BATCH_GLYPHS * 48) {
		flushTextBatch();
	}

	return true;
}

void gEGLDC::flushTextBatch() {
	if (m_text_batch_buffer.empty())
		return;
	// m_text_batch_clip, not m_current_clip - see its declaration comment:
	// this batch must be scissored against the clip captured when it
	// started, not whatever the active clip happens to be right now.
	if (m_text_batch_clip.rects.empty()) {
		m_text_batch_buffer.clear();
		return;
	}

	m_text_shader.bind();

	// Text glyphs are real translucent content (anti-aliased coverage *
	// color alpha) - see setAlphaBlendMode()'s comment for why this needs
	// the accumulating ("true" alphaBlend) formula, overriding whatever an
	// earlier, unrelated draw this frame may have left the blend func's
	// alpha factors set to.
	setAlphaBlendMode(true);

	// Bind the atlas pixmap
	gPixmap* atlas_pix = m_font_atlas.getPixmap();
	GLuint tex_id = m_texture_manager.getTexture(atlas_pix);
	glActiveTexture(GL_TEXTURE0);
	glBindTexture(GL_TEXTURE_2D, tex_id);

	if (m_font_atlas.isDirty()) {
		eRect dirty = m_font_atlas.getDirtyRect();

		// GLES 2.0 does not support GL_UNPACK_ROW_LENGTH, so we cannot easily upload
		// an arbitrary sub-rectangle. Instead, we upload full contiguous scanlines
		// for the dirty Y range.
		int start_y = dirty.top();
		int height = dirty.height();
		int stride = atlas_pix->size().width();

		const uint8_t* data = (const uint8_t*)atlas_pix->surface->data;
		data += (start_y * stride);

		glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
		GLenum src_fmt = gles::isGLES3() ? GL_RED : GL_LUMINANCE;
		glTexSubImage2D(GL_TEXTURE_2D, 0, 0, start_y, stride, height, src_fmt, GL_UNSIGNED_BYTE, data);
		glPixelStorei(GL_UNPACK_ALIGNMENT, 4);

		m_font_atlas.clearDirty();
	}

	// Bind the text shader's own VBO + vertex attribute layout (pos_uv +
	// color) before touching GL_ARRAY_BUFFER - without this, whatever another
	// shader (e.g. gShader's 2-float-per-vertex layout from an earlier
	// executeFill/executeRectangle in this same frame) last bound is still
	// active, and this batch's data gets completely misinterpreted.
	m_text_shader.bindVAO();

	gles::uploadDynamicVBO(m_text_batch_buffer.size() * sizeof(float), m_text_batch_buffer.data());

	int vertex_count = m_text_batch_buffer.size() / 8; // 8 floats per vertex

	for (unsigned int i = 0; i < m_text_batch_clip.rects.size(); ++i) {
		setGlScissor(m_text_batch_clip.rects[i]);
		glDrawArrays(GL_TRIANGLES, 0, vertex_count);
	}

	m_text_shader.unbindVAO();

	m_text_batch_buffer.clear();
}

void gEGLDC::clearOverlayArea(const eRect& area) {
	int pw = m_pixmap->size().width();
	int ph = m_pixmap->size().height();
	int left = std::max(0, area.left());
	int top = std::max(0, area.top());
	int right = std::min(pw, area.left() + area.width());
	int bottom = std::min(ph, area.top() + area.height());
	if (right <= left || bottom <= top)
		return;

	// pw*4, not surface->stride: m_pixmap is this backend's own allocation
	// (see the constructor), always tightly packed - same assumption
	// executeClear()'s equivalent erase loop and compositeTextOverlay()'s
	// row_width already make for this same buffer.
	uint8_t* base = (uint8_t*)m_pixmap->surface->data;
	int stride = pw * 4;
	for (int y = top; y < bottom; ++y)
		memset(base + (size_t)y * stride + (size_t)left * 4, 0, (size_t)(right - left) * 4);
}

void gEGLDC::compositeTextOverlay(eRect area, bool trueAlphaBlend) {
	// See executeFill()'s comment for why a pending blit batch must flush
	// first - this also uses m_texture_shader's shared VBO, which a
	// pending batch's data still occupies until drawn. Also flush any
	// pending GPU-atlas text batch left over from an *earlier* renderText/
	// renderPara opcode (this call only runs for the CPU-fallback portion of
	// the *current* one - see m_cpu_overlay_dirty) - otherwise that older,
	// still-undrawn text would end up rendered after this opcode's overlay
	// texture instead of before it.
	flushBlitBatch();
	flushTextBatch();

	// Clamp to the pixmap's actual bounds - a scrolling list widget's
	// per-row offset can legitimately place a row partially or fully
	// outside (e.g. mid-scroll, or a row whose valign correction pushes it
	// off the bottom).
	int pw = m_pixmap->size().width();
	int ph = m_pixmap->size().height();
	int left = std::max(0, area.left());
	int top = std::max(0, area.top());
	int right = std::min(pw, area.left() + area.width());
	int bottom = std::min(ph, area.top() + area.height());
	if (right <= left || bottom <= top)
		return;
	area = eRect(left, top, right - left, bottom - top);

	// Incremental glTexSubImage2D update instead of deleting and recreating
	// a full 1920x1080 texture on every single text/para draw (which was
	// both very slow and, before the use-after-free above was fixed, the
	// apparent source of visible corruption of unrelated content).
	GLuint tex_id = m_pixmap->surface->gl_texture_id;
	if (tex_id == 0) {
		tex_id = m_texture_manager.getTexture(m_pixmap);
	} else {
		glBindTexture(GL_TEXTURE_2D, tex_id);
		int row_width = m_pixmap->size().width();
		const uint8_t* src = (const uint8_t*)m_pixmap->surface->data;
		src += (size_t)area.top() * row_width * 4;
		// No CPU-side R/B swap here (see gtexture_manager.cpp's bpp==32
		// branch for the full explanation): m_pixmap is natively BGRA in
		// memory, and uploading that as-is while telling GL it's GL_RGBA
		// already produces exactly the pre-swapped bytes needed to cancel
		// this render target's own R/B swap on the way to the screen.
		glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
		glTexSubImage2D(GL_TEXTURE_2D, 0, 0, area.top(), row_width, area.height(), GL_RGBA, GL_UNSIGNED_BYTE, src);
	}
	if (tex_id) {
		// m_pixmap is only valid within the text's own bounding area - the
		// rest of that 1920x1080 CPU buffer is stale/uninitialized content
		// from whenever it was last (re)allocated. Scissor the fragment
		// writes down to just the area this opcode actually populated so
		// nothing outside it can be touched.
		setGlScissor(area);
		// Real rendered text/border pixel content normally needs the
		// accumulating ("true" alphaBlend) formula rather than whatever an
		// earlier, unrelated draw this frame may have left the blend func's
		// alpha factors set to - see setAlphaBlendMode()'s comment. A caller
		// erasing content back to transparent (disableSpinner()) instead
		// passes false, so its now-fully-transparent source pixels actually
		// overwrite the destination's alpha instead of leaving whatever
		// opaque content was already there untouched.
		setAlphaBlendMode(trueAlphaBlend);
		m_texture_shader.drawTexture(0, 0, (float)m_width, (float)m_height, tex_id);

		// Record that the overlay now has content here so executeClear()
		// knows to erase-and-recomposite this area before painting a plain
		// background over it later - see the comment there.
		m_text_overlay_region |= gRegion(area);
	}
}

void gEGLDC::enableSpinner() {
	gDC::enableSpinner();
	// m_spinner_pos is a screen-absolute rect (the spinner is a global
	// overlay, not part of any widget's offset-relative coordinate space),
	// so unlike renderText/renderPara's area it must NOT have
	// m_current_offset applied here.
	//
	// false, not the default true - see disableSpinner()'s comment. This
	// first frame's m_pixmap content is already the full background+icon
	// composite (gDC::enableSpinner() just built it), not translucent
	// content to layer over whatever the GPU target previously held there,
	// so it needs the same unconditional-overwrite blend disableSpinner()
	// and incrementSpinner() use.
	compositeTextOverlay(m_spinner_pos, false);
}

void gEGLDC::disableSpinner() {
	gDC::disableSpinner();
	// false, not the default true: gDC::disableSpinner() just restored
	// m_spinner_pos back to fully-transparent pixels in m_pixmap, and this
	// needs to actually erase the last spinner frame already baked into the
	// GPU render target, not accumulate on top of it. With the default
	// accumulating blend, a fully-transparent source leaves an opaque
	// destination's alpha unchanged (out.a = src.a + dst.a*(1-src.a), which
	// for src.a=0 is just dst.a) - the icon would stay stuck on screen
	// forever once the animation itself stops (no more enableSpinner()/
	// incrementSpinner() calls to eventually paint over it). false makes
	// this draw's own (transparent) alpha the absolute truth for that
	// region instead, actually punching the hole back through to video.
	compositeTextOverlay(m_spinner_pos, false);
}

void gEGLDC::incrementSpinner() {
	gDC::incrementSpinner();
	// false, not the default true - same reasoning as disableSpinner()
	// above, just mid-animation instead of at the end. gDC::incrementSpinner()
	// already recomposited this whole rect from scratch (background copied
	// in fresh, then this frame's rotated icon alpha-blended on top on the
	// CPU side), so m_pixmap here holds the complete, final pixel content
	// for the region, not translucent content to accumulate over the GPU
	// target's existing pixels. The icon's opaque footprint moves every
	// frame as it rotates; with the default accumulating blend, the pixels
	// it just vacated (now transparent, src.a=0, in this frame's composite)
	// leave the destination's alpha/color untouched (out.a = dst.a for
	// src.a=0), so the previous frame's icon stayed baked into the render
	// target as a trailing ghost for the whole animation. false makes this
	// draw's alpha the absolute truth for the region instead, so the
	// vacated pixels are actually erased back to background every frame.
	compositeTextOverlay(m_spinner_pos, false);
}

void gEGLDC::exec(const gOpcode* opcode) {
	if (!isInitialized())
		return;

	switch (opcode->opcode) {
		// fill/fillRegion/rectangle/line/blit are all handled entirely by
		// this backend's own executeXXX() helpers instead of falling through
		// to gDC::exec(opcode) - unlike renderText/renderPara/clear below,
		// which call gDC::exec(opcode) themselves and get its disposal
		// (delete o->parm.X, plus Release() on any refcounted member) for
		// free. These five never did, so their heap-allocated opcode struct
		// (new'd by gPainter's queuing side - see e.g. gPainter::blit() in
		// grc.cpp) was never freed. blit is the severe case (op->pixmap also
		// carries an AddRef() from gPainter::blit() that must be Release()'d
		// - see executeBlit()'s own BlitOpcodeGuard); the rest hold no
		// refcounted resource, so a plain delete here is enough.
		case gOpcode::fill:
			executeFill(opcode);
			delete opcode->parm.fill;
			break;

		case gOpcode::fillRegion:
			executeFillRegion(opcode);
			delete opcode->parm.fillRegion;
			break;

		case gOpcode::rectangle:
			executeRectangle(opcode);
			delete opcode->parm.rectangle;
			break;

		case gOpcode::line:
			executeLine(opcode);
			delete opcode->parm.line;
			break;

		case gOpcode::blit:
			executeBlit(opcode);
			break;

		case gOpcode::renderText: {
			// eTextPara::blit() (lib/gdi/font.cpp) draws most glyphs straight
			// to the GPU via renderGlyph()/the atlas below now, but border
			// text and pre-rendered "image" glyphs (see grc.h's
			// gDC::renderGlyph() comment) still fall back to pure software
			// rasterization directly into dc.getPixmap()'s CPU buffer
			// (gDC::m_pixmap). compositeTextOverlay() uploads that CPU
			// result and composites it onto the real GPU surface, the same
			// way any other pixmap (icons etc.) is drawn via executeBlit() -
			// m_cpu_overlay_dirty (set by onGlyphCpuDrawn()) tracks whether
			// this particular draw actually used that fallback, so a glyph
			// fully handled on the GPU doesn't get compositeTextOverlay()
			// re-painting whatever unrelated old content still sits in
			// m_pixmap at this screen position on top of it.
			//
			// CRITICAL: capture area BEFORE calling gDC::exec(opcode) - its
			// renderText handling (grc.cpp) does "delete o->parm.renderText;"
			// as its very last step. Reading opcode->parm.renderText->area
			// afterward is a use-after-free.
			eRect area = opcode->parm.renderText->area;
			// See executeFill()'s comment: a pending blit batch queued
			// before this text must draw before it, not after.
			flushBlitBatch();
			m_cpu_overlay_dirty = false;

			// Flush any pending text batch from an *earlier*, different
			// renderText/renderPara draw first: a batch only remembers ONE
			// clip (m_text_batch_clip), captured once when it starts - if
			// this text's glyphs got appended to a still-open batch from a
			// prior, differently-positioned text field (e.g. a list row's
			// channel-name field immediately followed by its event-title
			// field, with no clip-changing opcode between them to trigger a
			// flush on its own), they'd wrongly inherit that earlier
			// field's clip instead of this one's own area below.
			flushTextBatch();

			// Narrow the active clip to this text's own declared area for
			// the duration of this draw, exactly like eTextPara::blit()'s
			// CPU path (font.cpp) already does for itself ("clip &=
			// eRect(area...)") - the GPU glyph path (renderGlyph(), via
			// m_text_batch_clip above) has no other way to replicate that,
			// since it never receives `area` itself. Without this,
			// GPU-rendered text was only ever clipped to the surrounding
			// widget/row's clip, letting it overflow past its own column
			// into whatever's drawn next (e.g. EPG title text running into
			// the signal-strength meter column).
			gRegion saved_clip = m_current_clip;
			eRect clip_area = area;
			clip_area.moveBy(m_current_offset);
			m_current_clip = m_current_clip & clip_area;

			// Border text (textBColor/textBWidth) always takes the CPU
			// fallback (eTextPara::blit()'s two-pass border+fill technique -
			// see grc.cpp's renderText handling) - pre-clear its area to
			// transparent so whatever's NOT actual glyph/border ink (the
			// padding within this text's own bounding box, or plain stale
			// content left over from an earlier, unrelated draw at these
			// same screen coordinates in this shared staging buffer) doesn't
			// get uploaded and composited as an opaque block - this is what
			// made bordered text render with a solid background instead of
			// staying transparent. Gated on ->border specifically (rather
			// than unconditionally) since it's known up front here, before
			// gDC::exec() runs, and the overwhelming majority of text draws
			// have no border and are fully GPU-rendered - no need to pay for
			// a clear they'll never actually need composited.
			if (opcode->parm.renderText->border) {
				eRect clear_area = area;
				clear_area.moveBy(m_current_offset);
				clearOverlayArea(clear_area);
			}

			gDC::exec(opcode);
			m_current_clip = saved_clip;
			if (m_cpu_overlay_dirty) {
				area.moveBy(m_current_offset);
				compositeTextOverlay(area);
			}
			break;
		}

		case gOpcode::renderPara: {
			// eListboxPythonMultiContent (templated lists - channel/EPG
			// lists etc.) uses gPainter::renderPara() for some entries
			// instead of renderText(), a completely separate opcode that
			// this switch never handled - text rendered through it was
			// correctly software-blitted into m_pixmap but never composited
			// to the GPU surface at all (fell into the default: case),
			// exactly matching "list text missing in templated lists".
			//
			// CRITICAL (same reasoning as renderText above): grc.cpp's
			// renderPara handling calls "textpara->Release()" then
			// "delete o->parm.renderPara" as its last steps, so the area
			// must be captured before gDC::exec(opcode) runs.
			eTextPara* textpara = opcode->parm.renderPara->textpara;
			eRect area = textpara->getArea();
			area.moveBy(opcode->parm.renderPara->offset);
			// See executeFill()'s comment: a pending blit batch queued
			// before this text must draw before it, not after.
			flushBlitBatch();
			m_cpu_overlay_dirty = false;

			// See the renderText case above for why this flush and the
			// clip narrowing below are both needed.
			flushTextBatch();
			gRegion saved_clip = m_current_clip;
			eRect clip_area = area;
			clip_area.moveBy(m_current_offset);
			m_current_clip = m_current_clip & clip_area;

			gDC::exec(opcode);
			m_current_clip = saved_clip;
			if (m_cpu_overlay_dirty) {
				area.moveBy(m_current_offset);
				compositeTextOverlay(area);
			}
			break;
		}

		case gOpcode::clear:
			executeClear(opcode);
			gDC::exec(opcode);
			break;

		case gOpcode::flush:
			// This, not gOpcode::flip, is the real "end of frame" signal for
			// this system: eWidgetDesktop runs in cmImmediate composition
			// mode (see eWidgetDesktop::paint()'s cmImmediate branch, and
			// note cmBuffered's own redrawComposition() call is literally
			// commented out) - cmImmediate's paint() calls gPainter::flush()
			// (-> gOpcode::flush), never gPainter::flip(). The comment that
			// used to be on the flip case below ("gPainter::flip() already
			// submits this opcode at the end of every frame") was simply
			// wrong for this composition mode: flip() was being called from
			// an opcode that never fires during normal UI navigation, so our
			// present/resolve step (-> presentPixmap()/eglSwapBuffers()) was
			// never actually running on a real frame boundary at all -
			// confirmed by a ground-truth debug draw hooked into flip() that
			// never once fired despite extensive navigation. Content still
			// rendered because the GPU/driver eventually flushes its tile
			// buffer on its own with no explicit sync point, which likely
			// also explains earlier slowness/latency symptoms.
			//
			// processDeletions() moved here too: it used to run at the top
			// of exec() for every single opcode, taking a mutex lock just
			// to check for pending texture frees even though a list row's
			// worth of opcodes (5-10 of them) all belong to the same frame
			// - freeing a texture a few opcodes later than the very next
			// one after its pixmap died is harmless, so this only needs to
			// happen once per real frame boundary, same as flip() itself.
			m_texture_manager.processDeletions();
			flushBlitBatch();
			flushTextBatch();
			flip();
			gDC::exec(opcode);
			break;

		case gOpcode::flip:
			m_texture_manager.processDeletions();
			flushBlitBatch();
			flushTextBatch();
			flip();
			gDC::exec(opcode);
			break;

		default:
			// Unknown to this backend's own opcode handlers - flush any
			// pending batch first in case it draws something (e.g. a
			// monoBlit/blitScale variant), same reasoning as executeFill()'s
			// comment above.
			flushBlitBatch();
			flushTextBatch();
			gDC::exec(opcode);
			break;
	}

	// Removed: presenting (glFinish()/resolve) after every single opcode
	// instead of once per real frame boundary is architecturally wrong for a
	// tile-based deferred GPU (V3D) - it forces a premature resolve mid-frame
	// for every tiny draw call, which is both very slow (matches the "list
	// builds up slowly" symptom) and a plausible cause of the partial/
	// corrupted content seen across multiple unrelated elements (z-order-like
	// symptoms, missing scrollbar/icon content) once real work started
	// happening on the correct thread. gOpcode::flip (handled above, and
	// submitted by gPainter::flip() at the end of every real frame) is the
	// correct, single place this should happen.
}

gEGLDC* gEGLDC::s_instance = nullptr;

gEGLDC::gEGLDC(INativeWindowProvider* window_provider, int width, int height) : gMainDC() {
	s_instance = this;
	int xres = width, yres = height, bpp = 32;

	if (!window_provider) {
		if (fbClass::getInstance()) {
			fbClass::getInstance()->getMode(xres, yres, bpp);
		}
		width = xres;
		height = yres;
#ifdef DREAMNEXTGEN
		window_provider = new AmlogicWindowProvider(width, height);
#endif
	}

	m_window_provider = window_provider;
	m_width = width;
	m_height = height;
	m_gles_version = 0;
	m_egl_display = EGL_NO_DISPLAY;
	for (int i = 0; i < MAX_EGL_SURFACES; ++i)
		m_egl_surfaces[i] = EGL_NO_SURFACE;
	m_page_count = 1;
	m_render_page = 0;
	m_egl_context = EGL_NO_CONTEXT;
	m_cpu_overlay_dirty = false;

	// accelNever: this pixmap is a plain CPU-side staging buffer for text
	// compositing (see gOpcode::renderText handling below) that we
	// repeatedly glTexSubImage2D() into - it must never get a physical/ION
	// accelerated buffer, or createTextureFromPixmap() takes the DMA-BUF
	// import path (DRM_FORMAT_ARGB8888) on first use instead of a plain
	// glTexImage2D (GL_BGRA_EXT) texture, and our later glTexSubImage2D
	// calls (which assume the latter) operate on the wrong kind of texture
	// object entirely - a very likely source of the wrong colors seen.
	m_pixmap = new gPixmap(eSize(width, height), 32, gPixmap::accelNever);
}

gEGLDC::~gEGLDC() {
	cleanupEGL();
	// gEGLDCAutoInit::initNow() (egl_init.cpp) transfers ownership of the
	// provider it constructs to us via the constructor below - nothing else
	// ever deletes it, so without this DreamboxWindowProvider::cleanup()
	// (correctly wired to its own destructor) never actually runs, and the
	// provider itself leaks for the life of the process.
	delete m_window_provider;
	m_window_provider = nullptr;
	if (s_instance == this)
		s_instance = nullptr;
}

void gEGLDC::cleanupEGL() {
	if (m_egl_display != EGL_NO_DISPLAY) {
		// Free every shader's GL objects (program/VBO/VAO) HERE, while this
		// thread's context is still current, rather than leaving it to
		// their destructors: those run later as part of gEGLDC's own
		// member teardown, invoked from ~gEGLDC() on a completely different
		// thread (eInit's teardown, on the main thread - see this
		// function's own declaration comment) *after* the context this
		// function is about to destroy is already gone. A glDelete* call
		// with no current context at all on that thread is exactly what
		// was crashing the driver on shutdown even after moving the EGL
		// context teardown itself to the correct thread - freeing them
		// here first closes that gap. Each destroy() is safe to call again
		// later (idempotent), so the destructors calling it a second time
		// as a fallback is harmless.
		m_basic_shader.destroy();
		m_advanced_shader.destroy();
		m_texture_shader.destroy();
		m_text_shader.destroy();

		eglMakeCurrent(m_egl_display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
		if (m_egl_context != EGL_NO_CONTEXT) {
			eglDestroyContext(m_egl_display, m_egl_context);
		}
		for (int i = 0; i < MAX_EGL_SURFACES; ++i) {
			if (m_egl_surfaces[i] != EGL_NO_SURFACE) {
				eglDestroySurface(m_egl_display, m_egl_surfaces[i]);
			}
		}
		eglTerminate(m_egl_display);
	}
	m_egl_display = EGL_NO_DISPLAY;
	for (int i = 0; i < MAX_EGL_SURFACES; ++i)
		m_egl_surfaces[i] = EGL_NO_SURFACE;
	m_page_count = 1;
	m_render_page = 0;
	m_egl_context = EGL_NO_CONTEXT;
	m_gles_version = 0;
	gles::version = 0;
}

void gEGLDC::setResolution(int xres, int yres, int bpp) {
	if (m_width == xres && m_height == yres)
		return;

	m_width = xres;
	m_height = yres;
	// See the constructor for why accelNever is required here.
	m_pixmap = new gPixmap(eSize(xres, yres), bpp, gPixmap::accelNever);
	// The new pixmap has no gl_texture_id and no content yet - any area
	// tracked from the old one is meaningless now.
	m_text_overlay_region = gRegion();

	if (isInitialized()) {
		m_basic_shader.setResolution((float)m_width, (float)m_height);
		m_texture_shader.setResolution((float)m_width, (float)m_height);
		m_text_shader.setResolution((float)m_width, (float)m_height);
	}
}

bool gEGLDC::gpuCopyPageContent(int from, int to) {
#ifdef HAVE_GLES3
	if (!gles::isGLES3())
		return false;

	// Asymmetric draw/read: glBlitFramebuffer() below copies from whatever
	// is bound as GL_READ_FRAMEBUFFER (framebuffer 0 of the *read* surface)
	// into GL_DRAW_FRAMEBUFFER (framebuffer 0 of the *draw* surface) - EGL
	// supports different draw and read surfaces for exactly this kind of
	// surface-to-surface copy.
	if (!eglMakeCurrent(m_egl_display, m_egl_surfaces[to], m_egl_surfaces[from], m_egl_context)) {
		eDebug("[gEGLDC] eglMakeCurrent (draw=%d read=%d) failed for GPU copy-forward: 0x%x", to, from, eglGetError());
		return false;
	}

	// glBlitFramebuffer() is subject to the scissor test like any other
	// draw, and GL_SCISSOR_TEST is left permanently enabled (see initEGL())
	// with whatever rect the last opcode drawn set - reset it to the full
	// surface first or this copy would silently only cover a leftover
	// unrelated widget's clip rect instead of the whole page.
	glScissor(0, 0, m_width, m_height);
	glBlitFramebuffer(0, 0, m_width, m_height, 0, 0, m_width, m_height, GL_COLOR_BUFFER_BIT, GL_NEAREST);
	return true;
#else
	(void)from;
	(void)to;
	return false;
#endif
}

void gEGLDC::flip() {
	if (isInitialized() && m_egl_display != EGL_NO_DISPLAY && m_egl_surfaces[m_render_page] != EGL_NO_SURFACE) {
		// eglSwapBuffers() is only defined for window surfaces; a pixmap-surface
		// platform (Dreambox) presents via the provider instead - see
		// presentPixmap(). m_render_page is the page this frame was just
		// rendered into (see tryInitEGL()'s initial value and the rotation
		// below).
		if (m_window_provider->usesPixmapSurface()) {
			int shown_page = m_render_page;
			m_window_provider->presentPixmap(shown_page);

			if (m_page_count > 1) {
				// Rotate to the next page for the *next* frame's rendering -
				// never re-render into the page we just told the provider to
				// show. This is what actually makes rendering happen
				// off-screen instead of visibly drawing into live scanout
				// memory (the single-page behavior this replaces rendered
				// directly into whatever the display was concurrently
				// showing, so any frame slower than one vblank was visibly
				// drawn on screen mid-frame no matter how few GL draw calls
				// it took).
				m_render_page = (m_render_page + 1) % m_page_count;

				// Seed the new back buffer with what's now actually on screen
				// (shown_page) before any of the next frame's opcodes run -
				// needed because the compositor above only redraws dirty
				// regions, an assumption that only holds if the render
				// target already reflects the previous frame. Prefer doing
				// this through the GL pipeline itself (gpuCopyPageContent(),
				// GLES3's glBlitFramebuffer against asymmetric draw/read
				// surfaces) over a plain CPU memcpy of the page's backing
				// memory (INativeWindowProvider::copyPageContent()): this
				// GPU's tile-based deferred renderer appears to track a
				// surface's content by what it last wrote through the GL
				// pipeline, not by re-reading the surface's backing memory
				// on demand, so a CPU memcpy that bypasses the GL pipeline
				// can be partially invisible to it on the next frame's
				// render into that same surface - the actual cause behind
				// an infobar that looked "half updated" with the memcpy
				// version despite the copied bytes being correct in memory.
				bool gpu_copied = gpuCopyPageContent(shown_page, m_render_page);
				bool seeded = gpu_copied;

				if (gpu_copied) {
					// gpuCopyPageContent() already left draw=m_render_page
					// current (its read surface is stale/irrelevant now -
					// normal rendering opcodes never read from the
					// framebuffer). A render-target switch is not cheap on
					// this tile-based GPU (it has to resolve/flush whatever
					// was pending for the previous target), so don't pay for
					// a second one here just to "restore" a draw binding
					// that's already correct.
				} else {
					// GPU copy wasn't available or failed - draw is still
					// whatever it was before rotation (or in an unknown
					// state if gpuCopyPageContent()'s own eglMakeCurrent
					// partially failed). Explicitly bind the new page for
					// both draw and read before falling back to the CPU copy.
					if (!eglMakeCurrent(m_egl_display, m_egl_surfaces[m_render_page], m_egl_surfaces[m_render_page], m_egl_context)) {
						eDebug("[gEGLDC] eglMakeCurrent to page %d failed after flip: 0x%x", m_render_page, eglGetError());
						seeded = false;
					} else {
						m_window_provider->copyPageContent(shown_page, m_render_page);
						seeded = true;
					}
				}

				if (!seeded) {
					// Both the GL blit and the CPU-copy fallback failed to
					// seed the new page with shown_page's content. Every
					// draw opcode from here on only touches its own dirty
					// rect on the assumption the render target already
					// holds the previous frame - rendering into this
					// unseeded page now would bake whatever stale content
					// it happens to still have (e.g. an already-erased
					// spinner frame from `page_count` flips ago) back onto
					// the screen the next time rotation shows it again,
					// with no later event guaranteed to ever fully repaint
					// that specific page and clear it. Abandon the rotation
					// for this frame and go back to rendering into
					// shown_page instead: it was just presented, so it's
					// known to hold fully correct, current content. This
					// re-accepts the single-buffer tearing risk the
					// rotation above exists to avoid, but only for this one
					// rare failure frame - far better than a page that can
					// silently resurrect old content indefinitely.
					m_render_page = shown_page;
					if (!eglMakeCurrent(m_egl_display, m_egl_surfaces[shown_page], m_egl_surfaces[shown_page], m_egl_context))
						eDebug("[gEGLDC] eglMakeCurrent back to shown page %d failed: 0x%x", shown_page, eglGetError());
				}
			}
		} else {
			eglSwapBuffers(m_egl_display, m_egl_surfaces[0]);
		}
	}
}