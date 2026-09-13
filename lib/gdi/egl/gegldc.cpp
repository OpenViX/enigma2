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

void gEGLDC::executeFill(const gOpcode* op) {
	float r = m_foreground_color_rgb.r / 255.0f;
	float g = m_foreground_color_rgb.g / 255.0f;
	float b = m_foreground_color_rgb.b / 255.0f;
	float a = 1.0f - (m_foreground_color_rgb.a / 255.0f);

	eRect area = op->parm.fill->area;
	area.moveBy(m_current_offset);
	gRegion clip = m_current_clip & area;

	for (unsigned int i = 0; i < clip.rects.size(); ++i) {
		eRect r_area = clip.rects[i];
		m_basic_shader.drawRect(r_area.x(), r_area.y(), r_area.width(), r_area.height(), r, g, b, a);
	}
}

void gEGLDC::executeFillRegion(const gOpcode* op) {
	float r = m_foreground_color_rgb.r / 255.0f;
	float g = m_foreground_color_rgb.g / 255.0f;
	float b = m_foreground_color_rgb.b / 255.0f;
	float a = 1.0f - (m_foreground_color_rgb.a / 255.0f);

	gRegion region = op->parm.fillRegion->region;
	region.moveBy(m_current_offset);
	gRegion clip = m_current_clip & region;

	for (unsigned int i = 0; i < clip.rects.size(); ++i) {
		eRect r_area = clip.rects[i];
		m_basic_shader.drawRect(r_area.x(), r_area.y(), r_area.width(), r_area.height(), r, g, b, a);
	}
}

void gEGLDC::executeRectangle(const gOpcode* op) {
	if (m_current_clip.rects.empty())
		return;

	if (m_radius > 0 || m_gradient_colors.size() > 0) {
		glEnable(GL_BLEND);
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
		glEnable(GL_SCISSOR_TEST);
		for (unsigned int i = 0; i < m_current_clip.rects.size(); ++i) {
			setGlScissor(m_current_clip.rects[i]);
			m_advanced_shader.drawAdvancedRect(op->parm.rectangle->area.x() + m_current_offset.x(), op->parm.rectangle->area.y() + m_current_offset.y(), op->parm.rectangle->area.width(),
											   op->parm.rectangle->area.height(), m_radius, m_radius_edges, m_gradient_colors, m_gradient_orientation, m_gradient_alphablend > 0,
											   1.0f - (m_background_color_rgb.a / 255.0f), m_background_color_rgb);
		}
		glDisable(GL_SCISSOR_TEST);
		glDisable(GL_BLEND);
	} else {
		float r = m_background_color_rgb.r / 255.0f;
		float g = m_background_color_rgb.g / 255.0f;
		float b = m_background_color_rgb.b / 255.0f;
		float a = 1.0f - (m_background_color_rgb.a / 255.0f);

		glEnable(GL_SCISSOR_TEST);
		for (unsigned int i = 0; i < m_current_clip.rects.size(); ++i) {
			setGlScissor(m_current_clip.rects[i]);
			m_basic_shader.drawRect(op->parm.rectangle->area.x() + m_current_offset.x(), op->parm.rectangle->area.y() + m_current_offset.y(), op->parm.rectangle->area.width(),
									op->parm.rectangle->area.height(), r, g, b, a);
		}
		glDisable(GL_SCISSOR_TEST);
	}
}

void gEGLDC::executeClear(const gOpcode* op) {
	float r = m_background_color_rgb.r / 255.0f;
	float g = m_background_color_rgb.g / 255.0f;
	float b = m_background_color_rgb.b / 255.0f;
	float a = 1.0f - (m_background_color_rgb.a / 255.0f);

	static int s_diag_count = 0;
	if (s_diag_count < 20) {
		s_diag_count++;
		eDebug("[gEGLDC] DIAG executeClear rects=%u rgba=(%.2f,%.2f,%.2f,%.2f)",
			(unsigned)m_current_clip.rects.size(), r, g, b, a);
		for (unsigned int i = 0; i < m_current_clip.rects.size() && i < 3; ++i) {
			eRect dr = m_current_clip.rects[i];
			eDebug("[gEGLDC] DIAG   rect[%u]=(%d,%d,%d,%d)", i, dr.x(), dr.y(), dr.width(), dr.height());
		}
	}

	for (unsigned int i = 0; i < m_current_clip.rects.size(); ++i) {
		eRect area = m_current_clip.rects[i];
		m_basic_shader.drawRect(area.x(), area.y(), area.width(), area.height(), r, g, b, a);

		// TEMPORARY: for an opaque, non-trivial-sized rect, immediately read
		// back a pixel from *inside the exact rect we just drew* (not a fixed
		// sample point elsewhere on screen) to check whether the draw call
		// itself is landing anywhere at all, independent of any later
		// present/copy timing.
		if (s_diag_count <= 20 && a > 0.99f && area.width() > 4 && area.height() > 4) {
			glFinish();
			unsigned char px[4] = {0, 0, 0, 0};
			glReadPixels(area.x() + area.width() / 2, m_height - (area.y() + area.height() / 2), 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, px);
			eDebug("[gEGLDC] DIAG immediate readback at (%d,%d) [rect (%d,%d,%d,%d)] = %02x%02x%02x%02x (expected ~%02x%02x%02x%02x)",
				area.x() + area.width() / 2, area.y() + area.height() / 2,
				area.x(), area.y(), area.width(), area.height(),
				px[0], px[1], px[2], px[3],
				(unsigned)(r * 255), (unsigned)(g * 255), (unsigned)(b * 255), (unsigned)(a * 255));
		}

		// A widget that hides/repaints submits a gOpcode::clear for its own
		// area, but NOT necessarily a new gOpcode::renderText if it no longer
		// has any text to draw there. Since text is composited from a
		// completely separate overlay (m_pixmap's texture, see
		// gOpcode::renderText below) rather than drawn into this same GPU
		// target, clearing the background alone does not erase any
		// previously-composited text sitting at this location - it would
		// just stay visible forever (e.g. an infobar that "doesn't
		// disappear"). Erase the corresponding region of m_pixmap's CPU
		// buffer too and re-composite it (now transparent) so stale text
		// actually goes away.
		if (m_pixmap->surface->gl_texture_id != 0) {
			int pw = m_pixmap->size().width();
			int ph = m_pixmap->size().height();
			int left = std::max(0, area.left());
			int top = std::max(0, area.top());
			int right = std::min(pw, area.left() + area.width());
			int bottom = std::min(ph, area.top() + area.height());
			if (right > left && bottom > top) {
				uint8_t* base = (uint8_t*)m_pixmap->surface->data;
				int stride = pw * 4;
				for (int y = top; y < bottom; ++y)
					memset(base + (size_t)y * stride + (size_t)left * 4, 0, (size_t)(right - left) * 4);

				glBindTexture(GL_TEXTURE_2D, m_pixmap->surface->gl_texture_id);
				glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
				glTexSubImage2D(GL_TEXTURE_2D, 0, 0, top, pw, bottom - top, GL_RGBA, GL_UNSIGNED_BYTE, base + (size_t)top * stride);

				glEnable(GL_BLEND);
				glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
				glEnable(GL_SCISSOR_TEST);
				setGlScissor(eRect(left, top, right - left, bottom - top));
				m_texture_shader.drawTexture(0, 0, (float)m_width, (float)m_height, m_pixmap->surface->gl_texture_id);
				glDisable(GL_SCISSOR_TEST);
				glDisable(GL_BLEND);
			}
		}
	}
}

void gEGLDC::executeLine(const gOpcode* op) {
	float r = m_foreground_color_rgb.r / 255.0f;
	float g = m_foreground_color_rgb.g / 255.0f;
	float b = m_foreground_color_rgb.b / 255.0f;
	float a = 1.0f - (m_foreground_color_rgb.a / 255.0f);

	if (m_current_clip.rects.empty())
		return;

	glEnable(GL_SCISSOR_TEST);
	for (unsigned int i = 0; i < m_current_clip.rects.size(); ++i) {
		setGlScissor(m_current_clip.rects[i]);
		m_basic_shader.drawLine(op->parm.line->start.x() + m_current_offset.x(), op->parm.line->start.y() + m_current_offset.y(), op->parm.line->end.x() + m_current_offset.x(),
								op->parm.line->end.y() + m_current_offset.y(), r, g, b, a);
	}
	glDisable(GL_SCISSOR_TEST);
}

void gEGLDC::executeBlit(const gOpcode* opcode) {
	const gOpcode::para::pblit* op = opcode->parm.blit;
	if (!op->pixmap)
		return;

	GLuint tex_id = m_texture_manager.getTexture(op->pixmap);
	if (tex_id == 0)
		return;

	eRect pos = op->position;
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

	bool enable_blend = (op->flags & (gPixmap::blitAlphaBlend | gPixmap::blitAlphaTest)) || (m_radius > 0);
	if (enable_blend) {
		glEnable(GL_BLEND);
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
	}

	float x = pos.x();
	float y = pos.y();
	float width = pos.width() > 0 ? pos.width() : op->pixmap->size().width();
	float height = pos.height() > 0 ? pos.height() : op->pixmap->size().height();

	glEnable(GL_SCISSOR_TEST);
	for (unsigned int i = 0; i < clip.rects.size(); ++i) {
		setGlScissor(clip.rects[i]);
		m_texture_shader.drawTexture(x, y, width, height, tex_id, 1.0f, m_radius, m_radius_edges);
	}
	glDisable(GL_SCISSOR_TEST);

	if (enable_blend) {
		glDisable(GL_BLEND);
	}
}

void gEGLDC::renderGlyph(const ePoint& pos, gPixmap* glyph_mask, const gRGB& color) {
	if (!glyph_mask)
		return;

	glyph_uv uv;
	glyph_key_t key = reinterpret_cast<glyph_key_t>(glyph_mask->surface->data);

	static int s_diag_count = 0;
	bool do_diag = s_diag_count < 40;
	bool was_cached = m_font_atlas.getGlyph(key, uv);

	if (!was_cached) {
		// Flush the current batch before uploading a new glyph to the atlas.
		flushTextBatch();

		int w = glyph_mask->size().width();
		int h = glyph_mask->size().height();
		uint8_t* data = (uint8_t*)glyph_mask->surface->data;

		if (do_diag) {
			int nonzero = 0;
			for (int i = 0; i < w * h; ++i)
				if (data[i]) nonzero++;
			eDebug("[gEGLDC] DIAG renderGlyph MISS key=%p w=%d h=%d nonzero_bytes=%d/%d pos=(%d,%d)",
				(void*)key, w, h, nonzero, w * h, pos.x(), pos.y());
		}

		m_font_atlas.addGlyph(key, w, h, data, uv);
	} else if (do_diag) {
		eDebug("[gEGLDC] DIAG renderGlyph HIT  key=%p uv=(%.4f,%.4f,%.4f,%.4f) wh=(%u,%u) pos=(%d,%d)",
			(void*)key, uv.u0, uv.v0, uv.u1, uv.v1, uv.width, uv.height, pos.x(), pos.y());
	}
	if (do_diag) s_diag_count++;

	float r = color.r / 255.0f;
	float g = color.g / 255.0f;
	float b = color.b / 255.0f;
	float a = 1.0f - (color.a / 255.0f);

	float x = pos.x() + m_current_offset.x();
	float y = pos.y() + m_current_offset.y();
	float w = (float)uv.width;
	float h = (float)uv.height;

	// 6 vertices × 8 floats: x, y, u, v, r, g, b, a
	float vertices[48] = {x,	 y, uv.u0, uv.v0, r, g, b, a, x, y + h, uv.u0, uv.v1, r, g, b, a, x + w, y,		uv.u1, uv.v0, r, g, b, a,
						  x + w, y, uv.u1, uv.v0, r, g, b, a, x, y + h, uv.u0, uv.v1, r, g, b, a, x + w, y + h, uv.u1, uv.v1, r, g, b, a};

	m_text_batch_buffer.insert(m_text_batch_buffer.end(), vertices, vertices + 48);

	if (m_text_batch_buffer.size() >= MAX_BATCH_GLYPHS * 48) {
		flushTextBatch();
	}
}

void gEGLDC::flushTextBatch() {
	if (m_text_batch_buffer.empty())
		return;
	if (m_current_clip.rects.empty()) {
		m_text_batch_buffer.clear();
		return;
	}

	glEnable(GL_BLEND);
	glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);

	m_text_shader.bind();

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

	glBufferSubData(GL_ARRAY_BUFFER, 0, m_text_batch_buffer.size() * sizeof(float), m_text_batch_buffer.data());

	int vertex_count = m_text_batch_buffer.size() / 8; // 8 floats per vertex

	glEnable(GL_SCISSOR_TEST);
	for (unsigned int i = 0; i < m_current_clip.rects.size(); ++i) {
		setGlScissor(m_current_clip.rects[i]);
		glDrawArrays(GL_TRIANGLES, 0, vertex_count);
	}
	glDisable(GL_SCISSOR_TEST);

	m_text_shader.unbindVAO();

	glDisable(GL_BLEND);

	m_text_batch_buffer.clear();
}

void gEGLDC::compositeTextOverlay(eRect area) {
	static int s_diag_count = 0;
	bool do_diag = s_diag_count < 2000;
	if (do_diag) s_diag_count++;

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
	if (right <= left || bottom <= top) {
		if (do_diag)
			eDebug("[gEGLDC] DIAG compositeTextOverlay SKIPPED (degenerate clamp) area=(%d,%d,%d,%d) pw=%d ph=%d",
				area.x(), area.y(), area.width(), area.height(), pw, ph);
		return;
	}
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
		if (do_diag) {
			GLenum err = glGetError();
			eDebug("[gEGLDC] DIAG compositeTextOverlay subimage glGetError=0x%x tex_id=%u yoff=%d rows=%d", err, tex_id, area.top(), area.height());
		}
	}
	if (do_diag)
		eDebug("[gEGLDC] DIAG compositeTextOverlay tex_id=%u area=(%d,%d,%d,%d)", tex_id, area.x(), area.y(), area.width(), area.height());
	if (tex_id) {
		// m_pixmap is only valid within the text's own bounding area - the
		// rest of that 1920x1080 CPU buffer is stale/uninitialized content
		// from whenever it was last (re)allocated. Scissor the fragment
		// writes down to just the area this opcode actually populated so
		// nothing outside it can be touched.
		glEnable(GL_BLEND);
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
		glEnable(GL_SCISSOR_TEST);
		setGlScissor(area);
		m_texture_shader.drawTexture(0, 0, (float)m_width, (float)m_height, tex_id);
		glDisable(GL_SCISSOR_TEST);
		glDisable(GL_BLEND);
	}
}

void gEGLDC::exec(const gOpcode* opcode) {
	if (!isInitialized())
		return;

	m_texture_manager.processDeletions();

	switch (opcode->opcode) {
		case gOpcode::fill:
			executeFill(opcode);
			break;

		case gOpcode::fillRegion:
			executeFillRegion(opcode);
			break;

		case gOpcode::rectangle:
			executeRectangle(opcode);
			break;

		case gOpcode::line:
			executeLine(opcode);
			break;

		case gOpcode::blit:
			executeBlit(opcode);
			break;

		case gOpcode::renderText: {
			// eTextPara::blit() (lib/gdi/font.cpp) draws glyphs via pure
			// software rasterization directly into dc.getPixmap()'s CPU
			// buffer (gDC::m_pixmap) - it has no virtual GPU hook in this
			// codebase. compositeTextOverlay() uploads the result and
			// composites it onto the real GPU surface, the same way any
			// other pixmap (icons etc.) is drawn via executeBlit().
			//
			// CRITICAL: capture area BEFORE calling gDC::exec(opcode) - its
			// renderText handling (grc.cpp) does "delete o->parm.renderText;"
			// as its very last step. Reading opcode->parm.renderText->area
			// afterward is a use-after-free.
			eRect area = opcode->parm.renderText->area;
			gDC::exec(opcode);
			area.moveBy(m_current_offset);
			compositeTextOverlay(area);
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
			gDC::exec(opcode);
			area.moveBy(m_current_offset);
			compositeTextOverlay(area);
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
			flushTextBatch();
			flip();
			gDC::exec(opcode);
			break;

		case gOpcode::flip:
			flushTextBatch();
			flip();
			gDC::exec(opcode);
			break;

		default:
			gDC::exec(opcode);
			flushTextBatch();
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
	if (s_instance == this)
		s_instance = nullptr;
}

void gEGLDC::cleanupEGL() {
	if (m_egl_display != EGL_NO_DISPLAY) {
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

				if (!eglMakeCurrent(m_egl_display, m_egl_surfaces[m_render_page], m_egl_surfaces[m_render_page], m_egl_context)) {
					eDebug("[gEGLDC] eglMakeCurrent to page %d failed after flip: 0x%x", m_render_page, eglGetError());
				} else if (!gpu_copied) {
					m_window_provider->copyPageContent(shown_page, m_render_page);
				}
			}
		} else {
			eglSwapBuffers(m_egl_display, m_egl_surfaces[0]);
		}
	}
}