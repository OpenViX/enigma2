#include <unistd.h>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>
#include <cstdlib> 
#include <cstring>
#include <lib/base/eerror.h>
#include <lib/base/init.h>
#include <lib/base/init_num.h>
#include <lib/gdi/egl/gegldc.h>
#include <lib/gdi/egl/gles_version.h>
#ifdef HAVE_EGL_ANIMATION
#include <lib/gdi/egl/ganimation.h>
#include <thread>
#endif
#include <lib/gdi/fb.h>
#include <lib/gdi/font.h>

#ifndef EGL_OPENGL_ES3_BIT_KHR
#define EGL_OPENGL_ES3_BIT_KHR 0x00000040
#endif
#ifndef EGL_SWAP_BEHAVIOR_PRESERVED_BIT
#define EGL_SWAP_BEHAVIOR_PRESERVED_BIT 0x0400
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
	m_use_shadow_fbo = false;

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

	// gPainter's compositor above this (eWidgetDesktop) only ever redraws
	// *dirty* regions, on the assumption that the render target already
	// holds the previous frame's content everywhere else. For pixmap-mode
	// providers that's true by construction (the "pixmap" IS persistent
	// memory - see DreamboxWindowProvider). For a real window surface,
	// eglSwapBuffers() is free to hand back a buffer with UNDEFINED content
	// on the next frame (EGL's default EGL_BUFFER_DESTROYED swap behavior) -
	// so without preservation, only the first frame (which paints the whole
	// screen) looks right; every frame after that only patches its own
	// dirty rect into a fresh/undefined buffer, leaving everything outside
	// that rect black. Ask for EGL_SWAP_BEHAVIOR_PRESERVED_BIT up front so a
	// driver that supports it hands back the same, previously-rendered
	// buffer every time (see the eglSurfaceAttrib() call after surface
	// creation below) - retry without it if no matching config exists, since
	// plenty of drivers don't advertise it at all.
	EGLint window_surface_type_bit = surface_type_bit;
	if (!pixmap_mode)
		window_surface_type_bit |= EGL_SWAP_BEHAVIOR_PRESERVED_BIT;

	EGLint config_attribs[] = {
		EGL_SURFACE_TYPE, window_surface_type_bit, EGL_RENDERABLE_TYPE, renderable_type, EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_ALPHA_SIZE, 8, EGL_DEPTH_SIZE, 0, EGL_STENCIL_SIZE, 0,
		EGL_NONE};

	EGLint num_configs = 0;
	if (!eglChooseConfig(m_egl_display, config_attribs, &m_egl_config, 1, &num_configs) || num_configs == 0) {
		if (!pixmap_mode && window_surface_type_bit != surface_type_bit) {
			eDebug("[gEGLDC] no EGL config with EGL_SWAP_BEHAVIOR_PRESERVED_BIT for GLES%d, retrying without it.", version);
			config_attribs[1] = surface_type_bit;
			if (!eglChooseConfig(m_egl_display, config_attribs, &m_egl_config, 1, &num_configs) || num_configs == 0) {
				eDebug("[gEGLDC] no suitable EGL config found for GLES%d.", version);
				return false;
			}
		} else {
			eDebug("[gEGLDC] no suitable EGL config found for GLES%d.", version);
			return false;
		}
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
	// window surface otherwise, presented via eglSwapBuffers() - see the
	// EGL_SWAP_BEHAVIOR_PRESERVED handling above/below for why that alone is
	// NOT sufficient for correctness with this compositor's dirty-rect-only
	// redraw model.
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

		// Best-effort: ask this specific surface to actually preserve its
		// content across eglSwapBuffers() (see the config_attribs comment
		// above) - a config merely advertising the capability doesn't turn
		// it on by itself. Not fatal if the driver refuses/ignores this:
		// logged so a "renders once then goes black" report can be checked
		// against whether preservation was actually granted, rather than
		// re-derived from scratch.
		if (!eglSurfaceAttrib(m_egl_display, m_egl_surfaces[0], EGL_SWAP_BEHAVIOR, EGL_BUFFER_PRESERVED)) {
			eDebug("[gEGLDC] eglSurfaceAttrib(EGL_SWAP_BEHAVIOR, EGL_BUFFER_PRESERVED) failed/unsupported: 0x%x - window surface content is NOT preserved across eglSwapBuffers(); rendering into a persistent shadow framebuffer instead (see createShadowFramebuffer()).", eglGetError());
			m_use_shadow_fbo = true;

			// Diagnostic only - see m_shadow_blit_stride's comment (gegldc.h).
			// Lets someone testing on the actual box pick the stride without
			// a rebuild: ENIGMA_EGL_SHADOW_BLIT_STRIDE=3 enigma2 blits (and
			// logs) only 1 frame in every 3, skipping the other 2 entirely -
			// still calling eglSwapBuffers() every frame, exactly like real
			// steady-state playback. Watch the screen (scrolling text/lists
			// are the most sensitive case) for stale/torn content and raise
			// the stride until it just barely stays clean; that's this
			// platform's real backbuffer count.
			const char *stride_env = getenv("ENIGMA_EGL_SHADOW_BLIT_STRIDE");
			if (stride_env) {
				int stride = atoi(stride_env);
				if (stride >= 1)
					m_shadow_blit_stride = stride;
				else
					eDebug("[gEGLDC] ignoring ENIGMA_EGL_SHADOW_BLIT_STRIDE=%s (must be >= 1)", stride_env);
			}
			if (m_shadow_blit_stride != 1)
				eDebug("[gEGLDC] shadow-blit diagnostic stride=%d (blitting 1 in every %d frames - DO NOT ship this, see m_shadow_blit_stride's comment)", m_shadow_blit_stride, m_shadow_blit_stride);
		} else {
			eDebug("[gEGLDC] window surface swap behavior set to EGL_BUFFER_PRESERVED.");
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

	// The context is current now: learn the GPU's size limits before anything
	// sized to the canvas (shadow FBO, viewport, textures) is created. Only
	// matters when the canvas exceeds them - see updatePhysicalSize().
	{
		GLint max_tex = 0, max_rb = 0;
		glGetIntegerv(GL_MAX_TEXTURE_SIZE, &max_tex);
		glGetIntegerv(GL_MAX_RENDERBUFFER_SIZE, &max_rb);
		m_gpu_max_tex = (max_tex > 0 && max_rb > 0) ? std::min((int)max_tex, (int)max_rb) : std::max((int)max_tex, (int)max_rb);
#ifdef HAVE_EGL_CANVAS_SCALING
		m_max_tex_size = m_gpu_max_tex;
		eDebug("[gEGLDC] canvas scaling is ENABLED in this build (--enable-egl-canvas-scaling): GPU texture limit %d", m_max_tex_size);
#else
		// Canvas scaling not enabled for this build (see configure.ac's
		// --enable-egl-canvas-scaling): leave the limit at 0 = "unlimited", which
		// makes every size helper a no-op - the limits are only logged.
		m_max_tex_size = 0;
#endif
		m_texture_manager.setMaxTextureSize(m_max_tex_size);
		const char* renderer = (const char*)glGetString(GL_RENDERER);
		eDebug("[gEGLDC] GL_RENDERER=%s GL_MAX_TEXTURE_SIZE=%d GL_MAX_RENDERBUFFER_SIZE=%d", renderer ? renderer : "(null)", (int)max_tex, (int)max_rb);
		updatePhysicalSize(m_width, m_height);

		m_straight_alpha_present = m_window_provider && m_window_provider->needsStraightAlphaPresent();
		m_premultiply_overwrites = m_window_provider && m_window_provider->premultipliesOverwrites();
		m_unpremult_power = m_window_provider ? m_window_provider->presentUnpremultiplyPower() : 1.0f;
		m_premultiply_blits = m_window_provider && m_window_provider->premultipliesBlits();
		if (m_premultiply_overwrites)
			eDebug("[gEGLDC] raw-overwrite draws will write premultiplied colour");
		if (m_straight_alpha_present)
			eDebug("[gEGLDC] present pass will un-premultiply the frame (compositor blends this window as straight alpha)");
	}

	if (m_use_shadow_fbo && !createShadowFramebuffer()) {
		eDebug("[gEGLDC] failed to create shadow framebuffer.");
		for (int i = 0; i < m_page_count; ++i)
			eglDestroySurface(m_egl_display, m_egl_surfaces[i]);
		eglDestroyContext(m_egl_display, m_egl_context);
		m_egl_context = EGL_NO_CONTEXT;
		return false;
	}

	m_gles_version = version;

	{
		const char* egl_ver = eglQueryString(m_egl_display, EGL_VERSION);
		const char* gl_ver = (const char*)glGetString(GL_VERSION);
		gles::eglVersionString = egl_ver ? egl_ver : "";
		gles::glesVersionString = gl_ver ? gl_ver : "";
		eDebug("[gEGLDC] EGL_VERSION=%s GL_VERSION=%s", egl_ver ? egl_ver : "(null)", gl_ver ? gl_ver : "(null)");
	}

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

		// Probe for buffer-age / damage support the driver might implement
		// without advertising it (only the SDK headers declare these).
		EGLint age = -1;
		EGLBoolean age_ok = eglQuerySurface(m_egl_display, m_egl_surfaces[0], 0x313D /* EGL_BUFFER_AGE_KHR */, &age);
		eDebug("[gEGLDC] probe: eglQuerySurface(EGL_BUFFER_AGE) ok=%d age=%d err=0x%x", (int)age_ok, (int)age, age_ok ? 0 : eglGetError());
		eDebug("[gEGLDC] probe: eglSwapBuffersWithDamageKHR=%p eglSwapBuffersWithDamageEXT=%p eglSetDamageRegionKHR=%p eglPostSubBufferNV=%p",
			(void*)eglGetProcAddress("eglSwapBuffersWithDamageKHR"), (void*)eglGetProcAddress("eglSwapBuffersWithDamageEXT"),
			(void*)eglGetProcAddress("eglSetDamageRegionKHR"), (void*)eglGetProcAddress("eglPostSubBufferNV"));

		const char* inv_env = getenv("ENIGMA_EGL_BLIT_INVALIDATE");
		m_blit_invalidate = inv_env && atoi(inv_env) != 0;
		if (m_blit_invalidate)
			eDebug("[gEGLDC] shadow blit will glInvalidateFramebuffer() the window surface first (ENIGMA_EGL_BLIT_INVALIDATE)");
	}

	return true;
}

// ---------------------------------------------------------------------------
// createShadowFramebuffer / destroyShadowFramebuffer – see m_use_shadow_fbo's
// comment in gegldc.h. FBOs and glFramebufferTexture2D()/
// glCheckFramebufferStatus() are core in both GLES2 and GLES3, so this needs
// no version gating (only flip()'s glBlitFramebuffer() presentation step
// does - that's GLES3-only).
// ---------------------------------------------------------------------------
bool gEGLDC::createShadowFramebuffer() {
	while (glGetError() != GL_NO_ERROR) {
	}
	glGenTextures(1, &m_shadow_texture);
	glBindTexture(GL_TEXTURE_2D, m_shadow_texture);
	glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, m_phys_width, m_phys_height, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
	const GLenum alloc_err = glGetError();
	if (alloc_err != GL_NO_ERROR)
		eDebug("[gEGLDC] shadow texture %dx%d allocation raised glError=0x%x", m_phys_width, m_phys_height, alloc_err);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);

	glGenFramebuffers(1, &m_shadow_fbo);
	glBindFramebuffer(GL_FRAMEBUFFER, m_shadow_fbo);
	glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, m_shadow_texture, 0);

	GLenum status = glCheckFramebufferStatus(GL_FRAMEBUFFER);
	if (status != GL_FRAMEBUFFER_COMPLETE) {
		eDebug("[gEGLDC] shadow framebuffer incomplete: 0x%x", status);
		destroyShadowFramebuffer();
		glBindFramebuffer(GL_FRAMEBUFFER, 0);
		return false;
	}

	// Start from a clean, fully transparent canvas - every opcode from here
	// on renders into this texture instead of the window surface's own
	// default framebuffer (see flip()), so its initial content is the only
	// thing that ever needs explicitly clearing.
	glClearColor(0.0f, 0.0f, 0.0f, 0.0f);
	glClear(GL_COLOR_BUFFER_BIT);

	eDebug("[gEGLDC] shadow framebuffer created (%dx%d).", m_phys_width, m_phys_height);
	return true;
}

bool gEGLDC::recreateWindowSurface() {
	if (m_egl_surfaces[0] != EGL_NO_SURFACE) {
		eglMakeCurrent(m_egl_display, EGL_NO_SURFACE, EGL_NO_SURFACE, m_egl_context);
		eglDestroySurface(m_egl_display, m_egl_surfaces[0]);
		m_egl_surfaces[0] = EGL_NO_SURFACE;
	}
	EGLNativeWindowType native_window = m_window_provider->getNativeWindow();
	eDebug("[gEGLDC] resize: creating EGL window surface");
	m_egl_surfaces[0] = eglCreateWindowSurface(m_egl_display, m_egl_config, native_window, nullptr);
	if (m_egl_surfaces[0] == EGL_NO_SURFACE) {
		eDebug("[gEGLDC] eglCreateWindowSurface failed (physical %dx%d). EGL error: 0x%x", m_phys_width, m_phys_height, eglGetError());
		return false;
	}
	// Best-effort, same as tryInitEGL()'s own attempt - doesn't
	// change m_use_shadow_fbo, already decided once for this driver.
	eglSurfaceAttrib(m_egl_display, m_egl_surfaces[0], EGL_SWAP_BEHAVIOR, EGL_BUFFER_PRESERVED);
	m_render_page = 0;
	if (!eglMakeCurrent(m_egl_display, m_egl_surfaces[0], m_egl_surfaces[0], m_egl_context)) {
		eDebug("[gEGLDC] eglMakeCurrent failed after recreating window surface: 0x%x - discarding the surface", eglGetError());
		eglMakeCurrent(m_egl_display, EGL_NO_SURFACE, EGL_NO_SURFACE, m_egl_context);
		// Deliberately NOT eglDestroySurface()'d: a surface that fails
		// eglMakeCurrent() with EGL_BAD_NATIVE_WINDOW (0x300b) is bound to a native
		// window Nexus hasn't finished settling, and libnxpl dereferences that
		// window's null internal state (SIGSEGV, fault address 0x4) when asked to
		// destroy it. Dropping our handle leaks a small EGL surface per failed
		// attempt (bounded by the retry loop) instead of crashing the box.
		m_egl_surfaces[0] = EGL_NO_SURFACE;
		return false;
	}
	return true;
}

bool gEGLDC::recreateShadowFramebuffer() {
	for (int attempt = 0; attempt < 4; ++attempt) {
		if (attempt > 0) {
			glFinish();
			m_texture_manager.processDeletions();
			if (attempt > 1)
				m_texture_manager.releaseUnusedTextures();
			glFinish();
			eDebug("[gEGLDC] retrying shadow framebuffer creation (attempt %d)", attempt + 1);
		}
		if (createShadowFramebuffer())
			return true;
	}
	return false;
}

void gEGLDC::destroyShadowFramebuffer() {
	if (m_shadow_fbo) {
		glDeleteFramebuffers(1, &m_shadow_fbo);
		m_shadow_fbo = 0;
	}
	if (m_shadow_texture) {
		glDeleteTextures(1, &m_shadow_texture);
		m_shadow_texture = 0;
	}
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
	// See gles::setVertexData(): client-side vertex arrays by default;
	// ENIGMA_EGL_CLIENT_ARRAYS=0 restores the per-shader buffer uploads for
	// A/B comparison on the box without a rebuild.
	const char* client_arrays_env = getenv("ENIGMA_EGL_CLIENT_ARRAYS");
	gles::clientArrays = !(client_arrays_env && atoi(client_arrays_env) == 0);
	eDebug("[gEGLDC] vertex data via %s", gles::clientArrays ? "client-side arrays" : "buffer uploads");
	gles::needsRBSwap = m_window_provider->needsRenderTargetRBSwap();
	eDebug("[gEGLDC] GLES%d context created. needsRBSwap=%d", m_gles_version, gles::needsRBSwap ? 1 : 0);

	m_texture_manager.setDisplay(m_egl_display);

	// 7. basic GL state
	glViewport(0, 0, m_phys_width, m_phys_height);
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

	if (!m_window_provider->usesPixmapSurface())
		m_osd_capture.start(this);
	if (m_use_shadow_fbo)
		fbClass::lockChanged = &gEGLDC::onFramebufferLockChanged;

	clearWindowSurfaceTransparent();

	const char* profile_env = getenv("ENIGMA_EGL_PROFILE");
	m_profile = profile_env && atoi(profile_env) > 0;
	if (m_profile) {
		eDebug("[gEGLDC] per-frame profiling enabled (ENIGMA_EGL_PROFILE) - diagnostic only");
		m_prof_last_flip = std::chrono::steady_clock::now();
	}
	return true;
}

// See m_phys_width's comment (gegldc.h). A no-op (physical == logical, scale 1)
// unless the canvas is larger than the GPU can create a texture/renderbuffer for.
void gEGLDC::updatePhysicalSize(int logical_w, int logical_h) {
	int pw = logical_w, ph = logical_h;
	const bool fixed_window = m_window_provider && !m_window_provider->canResizeWindow() && m_native_width > 0 && m_native_height > 0;
	if (fixed_window) {
		// This platform's native window cannot be resized (see
		// INativeWindowProvider::canResizeWindow()): whatever the canvas size,
		// render into the size the window was created with. Independent of the
		// GPU texture limit - a 720p canvas is scaled UP to the window just as a
		// 1440p one is scaled down.
		pw = m_native_width;
		ph = m_native_height;
	} else {
		gtexFitSize(logical_w, logical_h, m_max_tex_size, pw, ph);
	}
	m_phys_width = pw;
	m_phys_height = ph;
	m_scale_x = logical_w > 0 ? (float)pw / (float)logical_w : 1.0f;
	m_scale_y = logical_h > 0 ? (float)ph / (float)logical_h : 1.0f;
	m_scaled = (pw != logical_w || ph != logical_h);
	if (m_max_tex_size == 0 && m_gpu_max_tex > 0 && std::max(logical_w, logical_h) > m_gpu_max_tex)
		eDebug("[gEGLDC] WARNING: canvas %dx%d exceeds the GPU texture limit %d but canvas scaling is NOT enabled in this build (configure --enable-egl-canvas-scaling / HAVE_EGL_CANVAS_SCALING) - textures wider/taller than the limit will be blank and the window resize will likely fail", logical_w, logical_h, m_gpu_max_tex);
	if (isScaled() && fixed_window)
		eDebug("[gEGLDC] native window cannot be resized on this platform - rendering canvas %dx%d scaled (%.3f x %.3f) into the existing %dx%d window", logical_w, logical_h, m_scale_x, m_scale_y, pw, ph);
	else if (isScaled())
		eDebug("[gEGLDC] canvas %dx%d exceeds GPU texture limit %d - rendering at %dx%d (scale %.3f x %.3f) and letting the display stretch it", logical_w, logical_h, m_max_tex_size, pw, ph, m_scale_x, m_scale_y);
}

void gEGLDC::uploadOverlayBand(GLuint tex_id, int left, int top, int right, int bottom) {
	const int pw = m_pixmap->size().width();
	const int ph = m_pixmap->size().height();
	left = std::max(0, left);
	top = std::max(0, top);
	right = std::min(pw, right);
	bottom = std::min(ph, bottom);
	if (bottom <= top || right <= left)
		return;

	const uint8_t* base = (const uint8_t*)m_pixmap->surface->data;
	const size_t stride = (size_t)pw * 4;

	glBindTexture(GL_TEXTURE_2D, tex_id);
	glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
	// m_pixmap is natively BGRA in memory - see gtexture_manager.cpp's bpp==32
	// branch / gles::needsRBSwap's comment (gles_version.h) for why this
	// format token is platform-dependent.
	const GLenum fmt = gles::needsRBSwap ? GL_RGBA : GL_BGRA_EXT;

	// The overlay texture is created by gTextureManager, which shrinks anything
	// over the GPU's texture limit with the same gtexFitSize() rule used here.
	int tw = pw, th = ph;
	gtexFitSize(pw, ph, m_texture_manager.maxTextureSize(), tw, th);
	if (tw == pw && th == ph) {
		glTexSubImage2D(GL_TEXTURE_2D, 0, 0, top, pw, bottom - top, fmt, GL_UNSIGNED_BYTE, base + (size_t)top * stride);
		return;
	}

	const float sx = (float)tw / (float)pw;
	const float sy = (float)th / (float)ph;
	const int dx0 = std::max(0, (int)std::floor(left * sx));
	const int dx1 = std::min(tw, (int)std::ceil(right * sx));
	const int dy0 = std::max(0, (int)std::floor(top * sy));
	const int dy1 = std::min(th, (int)std::ceil(bottom * sy));
	if (dx1 <= dx0 || dy1 <= dy0)
		return;
	std::vector<uint32_t> small((size_t)(dx1 - dx0) * (size_t)(dy1 - dy0));
	gtexDownscaleBGRA((const uint32_t*)base, pw, pw, ph, left, top, right, bottom, small.data(), tw, th, dx0, dy0, dx1, dy1);
	glTexSubImage2D(GL_TEXTURE_2D, 0, dx0, dy0, dx1 - dx0, dy1 - dy0, fmt, GL_UNSIGNED_BYTE, small.data());
}

void gEGLDC::setGlScissor(const eRect& rect) {
	if (!isScaled()) {
		int sx = rect.x();
		int sy = m_height - (rect.y() + rect.height());
		glScissor(sx, sy, rect.width(), rect.height());
		return;
	}

	// Logical (top-down) rect -> physical (bottom-up) pixels. Rounded outwards
	// so a scaled-down edge never loses its partially covered pixel row/column.
	int x0 = std::max(0, (int)std::floor(rect.x() * m_scale_x));
	int x1 = std::min(m_phys_width, (int)std::ceil((rect.x() + rect.width()) * m_scale_x));
	int y0 = std::max(0, (int)std::floor(rect.y() * m_scale_y));
	int y1 = std::min(m_phys_height, (int)std::ceil((rect.y() + rect.height()) * m_scale_y));
	glScissor(x0, m_phys_height - y1, std::max(0, x1 - x0), std::max(0, y1 - y0));
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

// Diagnostic ONLY: ENIGMA_EGL_SKIP_DRAW=fill,rect,blit,text (any subset) makes
// that class of draw a no-op, so combined with ENIGMA_EGL_PROFILE_FINISH the
// drop in the logged GPU drain time attributes the frame's GPU cost to it. The
// screen renders wrongly by design - never ship it enabled.
enum { SKIP_FILL = 1, SKIP_RECT = 2, SKIP_BLIT = 4, SKIP_TEXT = 8 };
static unsigned skipDrawMask() {
	static const unsigned mask = []() {
		unsigned m = 0;
		if (const char* e = getenv("ENIGMA_EGL_SKIP_DRAW")) {
			if (strstr(e, "fill")) m |= SKIP_FILL;
			if (strstr(e, "rect")) m |= SKIP_RECT;
			if (strstr(e, "blit")) m |= SKIP_BLIT;
			if (strstr(e, "text")) m |= SKIP_TEXT;
			eDebug("[gEGLDC] DIAGNOSTIC skip-draw mask=%u (from ENIGMA_EGL_SKIP_DRAW=%s) - display will be wrong", m, e);
		}
		return m;
	}();
	return mask;
}

// Texture deletion order. DEFAULT = the original behaviour: queued texture
// deletions are processed BEFORE the pending blit batch is drawn. Setting
// ENIGMA_EGL_FLUSH_BEFORE_DELETE=1 opts into drawing the pending batch first
// (plus an extra flush in executeBlit()). That was meant to stop a picon whose
// texture was deleted before its batch drew from rendering black, but on real
// hardware it caused stale selections and broken redraws, so it is off unless
// explicitly requested for testing.
static bool legacyTexDeletion() {
	static const bool opt_in = getenv("ENIGMA_EGL_FLUSH_BEFORE_DELETE") && atoi(getenv("ENIGMA_EGL_FLUSH_BEFORE_DELETE")) != 0;
	return !opt_in;
}

void gEGLDC::drawFlatRects(const gRegion& clip, float r, float g, float b, float a) {
	if (skipDrawMask() & SKIP_FILL)
		return;
	unsigned int count = clip.rects.size();
	if (count == 0)
		return;

	// The framebuffer is premultiplied everywhere (blended draws write
	// S*Sa + D*(1-Sa), and the Nexus/VU+ compositor is set to / converted for
	// premultiplied content), so a raw-overwrite colour must be premultiplied
	// too. Otherwise a fully transparent colour such as the skin's
	// "transparent" (#ffffffff = white, alpha 0) leaves white RGB at alpha 0:
	// the compositor adds that white on top of the video (white lines/bands),
	// and later blends against it leak white into translucent pixmaps.
	if (m_premultiply_overwrites) {
		r *= a;
		g *= a;
		b *= a;
	}

	// GL_SCISSOR_TEST is left permanently enabled for the whole context (see
	// initEGL()) - every draw call here relies on the immediately preceding
	// setGlScissor() to cut it down to the right area, since nothing resets
	// it in between. Each quad below is already sized to exactly its own
	// clip rect, so it needs no *additional* clipping - but skipping
	// setGlScissor() entirely would leave whatever rect the previous,
	// unrelated opcode last set still active, silently clipping this draw
	// to some stale leftover area instead. Widen it to the full surface once
	// so the scissor test is a no-op and the quads' own geometry is the only
	// thing that actually clips them - same fix as flip()'s
	// glBlitFramebuffer() comment already applies for the same reason.
	setGlScissor(eRect(0, 0, m_width, m_height));

	std::vector<float> vertices;
	vertices.reserve((size_t)std::min(count, (unsigned int)gShader::kMaxBatchQuads) * 36);

	unsigned int i = 0;
	while (i < count) {
		vertices.clear();
		unsigned int chunk = std::min(count - i, (unsigned int)gShader::kMaxBatchQuads);
		for (unsigned int j = 0; j < chunk; ++j, ++i) {
			const eRect& area = clip.rects[i];
			float x = area.x(), y = area.y(), w = area.width(), h = area.height();
			float quad[36] = {x, y, r, g, b, a, x, y + h, r, g, b, a, x + w, y, r, g, b, a, x + w, y, r, g, b, a, x, y + h, r, g, b, a, x + w, y + h, r, g, b, a};
			vertices.insert(vertices.end(), quad, quad + 36);
		}
		m_basic_shader.drawBatch(vertices.data(), (int)(chunk * 6));
	}
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
	drawFlatRects(clip, r, g, b, a);
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
	drawFlatRects(clip, r, g, b, a);
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
	if (m_current_clip.rects.empty() || (skipDrawMask() & SKIP_RECT)) {
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
		// Mirror the CPU renderer's two rectangle paths exactly (see
		// gPixmap::drawRectangle(), gpixmap.cpp):
		//
		// - drawRectangleNew() (no gradient, and useNew or border+radius):
		//   every pixel, edge included, is blended with the accumulating
		//   "over" equation - trueAlphaBlend.
		//
		// - otherwise the classic path: the interior OVERWRITES the
		//   destination (translucent color included - that's what lets a
		//   non-alphablend widget punch a video hole), while a rounded edge
		//   pixel is a straight lerp by coverage in all four channels
		//   (blendPixelRounded(), drawing.cpp): out = c*cov + dst*(1-cov),
		//   alpha included. So over an opaque parent the edge alpha only
		//   eases from the parent's toward the widget's own. The previous
		//   "ignore dst alpha" mode wrote a*cov there instead, leaving each
		//   rounded edge MORE transparent than both the widget and its
		//   parent - a ring of video poking through instead of antialiasing.
		//
		// The coverage lerp needs a factor (1-cov) that differs from the
		// color's own alpha, which one blend equation can't express, so it
		// takes two passes: RGB lerp + dst alpha *= (1-cov), then an
		// alpha-only pass adding a*cov. For a fully opaque shape both paths
		// reduce to the same single accumulating pass, so that's used there.
		const bool no_gradient = m_gradient_colors.empty();
		const bool accumulate = no_gradient && (op->parm.rectangle->useNew || (m_border_width > 0 && m_radius > 0));

		bool opaque = m_border_width <= 0 || m_border_color.a == 0;
		if (no_gradient || m_gradient_alphablend)
			opaque = opaque && m_background_color_rgb.a == 0;
		else
			for (const gRGB& c : m_gradient_colors)
				opaque = opaque && c.a == 0;

		const float x = op->parm.rectangle->area.x() + m_current_offset.x();
		const float y = op->parm.rectangle->area.y() + m_current_offset.y();
		const float w = op->parm.rectangle->area.width();
		const float h = op->parm.rectangle->area.height();
		const float alpha = 1.0f - (m_background_color_rgb.a / 255.0f);
		auto drawPass = [&](bool coverage_alpha) {
			for (unsigned int i = 0; i < m_current_clip.rects.size(); ++i) {
				if (m_profile) {
					const eRect& cr = m_current_clip.rects[i];
					float ix = std::max(0.0f, std::min((float)(cr.left() + cr.width()), x + w) - std::max((float)cr.left(), x));
					float iy = std::max(0.0f, std::min((float)(cr.top() + cr.height()), y + h) - std::max((float)cr.top(), y));
					m_prof.rect_adv_draws++;
					m_prof.rect_adv_mpx += (double)ix * iy / 1e6;
				}
				setGlScissor(m_current_clip.rects[i]);
				m_advanced_shader.drawAdvancedRect(x, y, w, h, m_radius, m_radius_edges, m_gradient_colors, m_gradient_orientation, m_gradient_alphablend > 0, alpha,
												   m_background_color_rgb, m_border_width, m_border_color, coverage_alpha);
			}
		};

		// Fast path (ENIGMA_EGL_RECT_FASTPATH=0 disables, for A/B): profiling
		// on gbquad4kpro (advShadedMpx vs GPU drain time) showed the advanced
		// shader costs ~10ns/pixel, and translucent rounded/gradient panels
		// run it over their whole area (twice) although coverage is exactly 1
		// everywhere except the corner squares. Instead: the interior
		// (everything outside the rounded corners' r x r squares) is drawn
		// with the cheap flat shader, its colour - solid or piecewise-linear
		// gradient, which vertex-colour interpolation reproduces exactly -
		// baked into the vertices; only the corner squares still go through
		// the advanced shader. Borders, degenerate gradients and radii larger
		// than half the rect keep the original path.
		static const bool s_rect_fastpath = !(getenv("ENIGMA_EGL_RECT_FASTPATH") && atoi(getenv("ENIGMA_EGL_RECT_FASTPATH")) == 0);
		const size_t nstops = m_gradient_colors.size();
		// A border is fine too: its inner edge lies on whole pixels (integer
		// widths), so outside the corner squares each pixel is exactly border or
		// fill - drawn as flat quads (border bands + fill) around the same corner squares.
		const bool fast = s_rect_fastpath && (nstops == 0 || (nstops >= 2 && nstops <= 16)) && w > 0 && h > 0 && (m_radius <= 0 || 2.0f * m_radius <= std::min(w, h)) &&
						  (m_border_width <= 0 || 2.0f * m_border_width <= std::min(w, h));

		if (fast) {
			const float rad = m_radius > 0 ? (float)m_radius : 0.0f;
			const bool c_tl = rad > 0 && (m_radius_edges & 1), c_tr = rad > 0 && (m_radius_edges & 2);
			const bool c_bl = rad > 0 && (m_radius_edges & 4), c_br = rad > 0 && (m_radius_edges & 8);
			const bool one_pass = accumulate || opaque;
			const bool grad_alphablend = m_gradient_alphablend > 0;

			// Mirrors the advanced fragment shader's colour (see
			// gadvanced_shader.cpp) at a position where coverage == 1.
			auto colorAtStraight = [&](float px, float py, float out[4]) {
				float sr = m_background_color_rgb.r / 255.0f, sg = m_background_color_rgb.g / 255.0f, sb = m_background_color_rgb.b / 255.0f;
				out[0] = sr; out[1] = sg; out[2] = sb; out[3] = alpha;
				if (nstops == 0)
					return;
				float t = m_gradient_orientation == 1 ? (px - x) / w : (py - y) / h;
				t = std::min(1.0f, std::max(0.0f, t));
				const float scaled = t * (float)(nstops - 1);
				size_t i = std::min((size_t)scaled, nstops - 2);
				const float f = scaled - (float)i;
				auto stopColor = [&](size_t k, float c[4]) {
					const gRGB& g = m_gradient_colors[k];
					c[0] = g.r / 255.0f; c[1] = g.g / 255.0f; c[2] = g.b / 255.0f;
					c[3] = grad_alphablend ? alpha : (1.0f - (g.a / 255.0f));
				};
				float c0[4], c1[4], gc[4];
				stopColor(i, c0);
				stopColor(i + 1, c1);
				for (int k = 0; k < 4; ++k)
					gc[k] = c0[k] + (c1[k] - c0[k]) * f;
				if (grad_alphablend) {
					out[0] = sr + (gc[0] - sr) * gc[3];
					out[1] = sg + (gc[1] - sg) * gc[3];
					out[2] = sb + (gc[2] - sb) * gc[3];
				} else {
					out[0] = gc[0]; out[1] = gc[1]; out[2] = gc[2]; out[3] = gc[3];
				}
			};
			// These quads are drawn with blending OFF when the shape is translucent (the
			// classic overwrite semantics: the colour REPLACES what is there, alpha
			// included). In a frame that is premultiplied everywhere (see
			// m_premultiply_overwrites / drawFlatRects()) the stored colour must then be
			// rgb*alpha as well, or the straight-alpha present pass divides it by alpha a
			// second time and translucent panels come out wrong. Blended (one-pass) draws
			// get the premultiplication from the blend function already.
			const bool premult_quads = m_premultiply_overwrites && !one_pass;
			auto colorAt = [&](float px, float py, float out[4]) {
				colorAtStraight(px, py, out);
				if (premult_quads) {
					out[0] *= out[3];
					out[1] *= out[3];
					out[2] *= out[3];
				}
			};

			std::vector<float> verts;
			verts.reserve(64 * 36);
			auto flushVerts = [&]() {
				if (!verts.empty()) {
					m_basic_shader.drawBatch(verts.data(), (int)(verts.size() / 6));
					verts.clear();
				}
			};
			auto pushQuad = [&](float ax, float ay, float bx, float by) {
				float c00[4], c10[4], c01[4], c11[4];
				colorAt(ax, ay, c00); colorAt(bx, ay, c10); colorAt(ax, by, c01); colorAt(bx, by, c11);
				const float* cs[6] = {c00, c01, c10, c10, c01, c11};
				const float xs[6] = {ax, ax, bx, bx, ax, bx};
				const float ys[6] = {ay, by, ay, ay, by, by};
				for (int k = 0; k < 6; ++k) {
					verts.push_back(xs[k]); verts.push_back(ys[k]);
					verts.insert(verts.end(), cs[k], cs[k] + 4);
				}
				if (verts.size() >= (size_t)gShader::kMaxBatchQuads * 36 - 36)
					flushVerts();
			};
			// One piece, split at gradient stop boundaries along the gradient axis.
			auto pushPiece = [&](float x0, float y0, float x1, float y1) {
				if (x1 <= x0 || y1 <= y0)
					return;
				if (nstops < 2) {
					pushQuad(x0, y0, x1, y1);
					return;
				}
				const bool horiz = m_gradient_orientation == 1;
				const float lo = horiz ? x0 : y0, hi = horiz ? x1 : y1;
				const float origin = horiz ? x : y, span = horiz ? w : h;
				float prev = lo;
				for (size_t s = 1; s + 1 <= nstops - 1; ++s) {
					float b = origin + span * (float)s / (float)(nstops - 1);
					if (b > prev && b < hi) {
						if (horiz) pushQuad(prev, y0, b, y1); else pushQuad(x0, prev, x1, b);
						prev = b;
					}
				}
				if (horiz) pushQuad(prev, y0, hi, y1); else pushQuad(x0, prev, x1, hi);
			};

			// With a border, a piece splits into the fill part (inside the border
			// inset) and up to four border bands, which take the border colour.
			const float bw = m_border_width > 0 ? (float)m_border_width : 0.0f;
			auto pushFlat = [&](float ax, float ay, float bx, float by, const float c[4]) {
				if (bx <= ax || by <= ay)
					return;
				const float xs[6] = {ax, ax, bx, bx, ax, bx};
				const float ys[6] = {ay, by, ay, ay, by, by};
				for (int k = 0; k < 6; ++k) {
					verts.push_back(xs[k]); verts.push_back(ys[k]);
					verts.insert(verts.end(), c, c + 4);
				}
				if (verts.size() >= (size_t)gShader::kMaxBatchQuads * 36 - 36)
					flushVerts();
			};
			auto pushBordered = [&](float x0, float y0, float x1, float y1) {
				if (bw <= 0) {
					pushPiece(x0, y0, x1, y1);
					return;
				}
				const float ba = 1.0f - (m_border_color.a / 255.0f);
				const float bm = premult_quads ? ba : 1.0f;
				const float bc[4] = {m_border_color.r / 255.0f * bm, m_border_color.g / 255.0f * bm, m_border_color.b / 255.0f * bm, ba};
				const float fx0 = std::max(x0, x + bw), fy0 = std::max(y0, y + bw), fx1 = std::min(x1, x + w - bw), fy1 = std::min(y1, y + h - bw);
				if (fx1 <= fx0 || fy1 <= fy0) {
					pushFlat(x0, y0, x1, y1, bc);
					return;
				}
				pushPiece(fx0, fy0, fx1, fy1);
				pushFlat(x0, y0, x1, fy0, bc);
				pushFlat(x0, fy1, x1, y1, bc);
				pushFlat(x0, fy0, fx0, fy1, bc);
				pushFlat(fx1, fy0, x1, fy1, bc);
			};

			// Interior = middle band + the strips above/below it between the corner squares.
			const float rt = (c_tl || c_tr) ? rad : 0.0f, rb = (c_bl || c_br) ? rad : 0.0f;
			struct Piece { float x0, y0, x1, y1; };
			Piece pieces[3];
			int npieces = 0;
			pieces[npieces++] = {x, y + rt, x + w, y + h - rb};
			if (rt > 0)
				pieces[npieces++] = {x + (c_tl ? rad : 0.0f), y, x + w - (c_tr ? rad : 0.0f), y + rt};
			if (rb > 0)
				pieces[npieces++] = {x + (c_bl ? rad : 0.0f), y + h - rb, x + w - (c_br ? rad : 0.0f), y + h};

			if (one_pass)
				setAlphaBlendMode(true);
			else
				glDisable(GL_BLEND);
			// Geometry is clipped to each clip rect below, so the scissor must be a no-op (see drawFlatRects()).
			setGlScissor(eRect(0, 0, m_width, m_height));
			for (const eRect& cr : m_current_clip.rects) {
				const float cl = cr.left(), ct = cr.top(), cr_r = cr.left() + cr.width(), cb = cr.top() + cr.height();
				for (int p = 0; p < npieces; ++p)
					pushBordered(std::max(pieces[p].x0, cl), std::max(pieces[p].y0, ct), std::min(pieces[p].x1, cr_r), std::min(pieces[p].y1, cb));
			}
			flushVerts();
			if (!one_pass)
				glEnable(GL_BLEND);

			if (m_profile)
				m_prof.rect_fast++;

			if (rad > 0) {
				const float corner[4][4] = {{x, y, rad, rad}, {x + w - rad, y, rad, rad}, {x, y + h - rad, rad, rad}, {x + w - rad, y + h - rad, rad, rad}};
				const bool present[4] = {c_tl, c_tr, c_bl, c_br};
				auto cornerPass = [&](bool coverage_alpha) {
					for (const eRect& cr : m_current_clip.rects) {
						for (int c = 0; c < 4; ++c) {
							if (!present[c])
								continue;
							const float* q = corner[c];
							if (q[0] >= cr.left() + cr.width() || q[0] + q[2] <= cr.left() || q[1] >= cr.top() + cr.height() || q[1] + q[3] <= cr.top())
								continue;
							if (m_profile) {
								m_prof.rect_adv_draws++;
								m_prof.rect_adv_mpx += (double)q[2] * q[3] / 1e6;
							}
							setGlScissor(cr);
							m_advanced_shader.drawAdvancedRect(x, y, w, h, m_radius, m_radius_edges, m_gradient_colors, m_gradient_orientation, grad_alphablend, alpha, m_background_color_rgb,
															   m_border_width, m_border_color, coverage_alpha, q);
						}
					}
				};
				if (one_pass) {
					setAlphaBlendMode(true);
					cornerPass(false);
				} else {
					glBlendFuncSeparate(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_ZERO, GL_ONE_MINUS_SRC_ALPHA);
					cornerPass(true);
					glColorMask(GL_FALSE, GL_FALSE, GL_FALSE, GL_TRUE);
					glBlendFuncSeparate(GL_ZERO, GL_ONE, GL_ONE, GL_ONE);
					cornerPass(false);
					glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
					setAlphaBlendMode(true);
				}
			} else if (!one_pass) {
				setAlphaBlendMode(true);
			}
		} else {
			if (m_profile) {
				if (accumulate || opaque)
					m_prof.rect_adv1++;
				else
					m_prof.rect_adv2++;
			}
			if (accumulate || opaque) {
				setAlphaBlendMode(true);
				drawPass(false);
			} else {
				// Pass 1: shader alpha = coverage. rgb = c*cov + dst*(1-cov),
				// dst alpha *= (1-cov).
				glBlendFuncSeparate(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_ZERO, GL_ONE_MINUS_SRC_ALPHA);
				drawPass(true);
				// Pass 2, alpha only: shader alpha = a*cov, added on top.
				glColorMask(GL_FALSE, GL_FALSE, GL_FALSE, GL_TRUE);
				glBlendFuncSeparate(GL_ZERO, GL_ONE, GL_ONE, GL_ONE);
				drawPass(false);
				glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
				setAlphaBlendMode(true);
			}
		}
	} else {
		float r = m_background_color_rgb.r / 255.0f;
		float g = m_background_color_rgb.g / 255.0f;
		float b = m_background_color_rgb.b / 255.0f;
		float a = 1.0f - (m_background_color_rgb.a / 255.0f);

		// See executeFill()'s comment for why blend must be forced off for
		// a plain flat-color rectangle, to match the CPU renderer's raw
		// overwrite semantics - except when useNew is set: the CPU path
		// then goes through drawRectangleNew(), which blends the fill
		// ("over") against what's behind. Overwriting here instead made
		// an alphaBlend widget (e.g. a scrollbar over a pixmap
		// background) punch a hole to the video plane.
		const bool blend_flat = op->parm.rectangle->useNew;
		if (blend_flat)
			setAlphaBlendMode(true);
		else {
			glDisable(GL_BLEND);
			// raw overwrite: keep the framebuffer premultiplied (see drawFlatRects())
			if (m_premultiply_overwrites) {
				r *= a;
				g *= a;
				b *= a;
			}
		}
		if (m_profile)
			m_prof.rect_flat++;
		for (unsigned int i = 0; i < m_current_clip.rects.size(); ++i) {
			setGlScissor(m_current_clip.rects[i]);
			m_basic_shader.drawRect(op->parm.rectangle->area.x() + m_current_offset.x(), op->parm.rectangle->area.y() + m_current_offset.y(), op->parm.rectangle->area.width(),
									op->parm.rectangle->area.height(), r, g, b, a);
		}
		if (!blend_flat)
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

	// See executeFill()'s comment: this flat background overwrite must not
	// blend with whatever's already on screen, matching the CPU renderer's
	// raw-overwrite clear semantics - unlike the erase/recomposite pass
	// below, which is genuinely alpha-aware and relies on blend being
	// enabled (the default - see initEGL()). Every rect here is independent
	// of every other (disjoint areas), so drawing them all first and running
	// the erase/recomposite pass across all of them afterward instead of
	// interleaving the two per-rect changes nothing about the result.
	glDisable(GL_BLEND);
	drawFlatRects(m_current_clip, r, g, b, a);
	glEnable(GL_BLEND);

	if (!maybe_has_overlay)
		return;

	for (unsigned int i = 0; i < m_current_clip.rects.size(); ++i) {
		eRect area = m_current_clip.rects[i];

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

			// Uploads rows [top, bottom) of m_pixmap (natively BGRA - see
			// uploadOverlayBand()), downsampled if the texture is smaller.
			uploadOverlayBand(overlay_tex, left, top, right, bottom);

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
	// premultiplied framebuffer - see drawFlatRects()
	if (m_premultiply_overwrites) {
		r *= a;
		g *= a;
		b *= a;
	}
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
	//
	// The same guard also does what gDC::exec()'s generic blit case does after
	// every blit (grc.cpp): reset the one-shot corner radius that
	// gPainter::setRadius() queued for it. Without that reset a rounded blit
	// (e.g. a poster with cornerRadius) left m_radius set, and the next blit -
	// say an icon in a listbox row redrawn after the poster changed - was drawn
	// with that stale radius, rounded into a distorted blob.
	struct BlitOpcodeGuard {
		const gOpcode::para::pblit* op;
		int& radius;
		uint8_t& radius_edges;
		~BlitOpcodeGuard() {
			radius = 0;
			radius_edges = 0;
			if (op->pixmap)
				op->pixmap->Release();
			delete op;
		}
	} guard{op, m_radius, m_radius_edges};

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
	// A pending batch (quads queued but not yet drawn) may reference a texture
	// that is queued for deletion - draw it first, or that draw would sample a
	// deleted texture (black) or one whose id getTexture() below just reused.
	if (!legacyTexDeletion() && m_texture_manager.hasPendingDeletions())
		flushBlitBatch();
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
	// formula, which is what we want here too: a corner radius's antialiased
	// fringe always carries a coverage-attenuated (genuinely low) alpha, and
	// unlike the accumulating formula, the other ("ignore dst") one would
	// wipe out whatever opacity the destination already had there, letting
	// whatever's behind it show through as a dark/black halo hugging the
	// rounded corner - see executeRectangle()'s matching comment. Unlike a
	// rectangle, a blit has no equivalent "deliberately near-transparent
	// hole" use case that actually needs that destructive formula, so this
	// is always safe: identical result in the (assumed fully opaque)
	// interior, correct instead of destructive at the fringe.
	bool true_alpha_blend = true;

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
		} else {
			glDisable(GL_BLEND);
			// Raw overwrite of the source's straight RGBA: store it premultiplied like
			// every other write into the frame (the present pass divides by alpha).
			m_texture_shader.setPremultiply(m_premultiply_blits);
		}
		// Rounded blit fast path (ENIGMA_EGL_RECT_FASTPATH=0 disables, like the
		// rectangle one): the SDF fragment shader is only needed in the corner
		// squares, coverage is exactly 1 everywhere else - so draw the interior
		// with the plain texture path and run the SDF shader over just the corner
		// r x r squares.
		static const bool s_blit_fastpath = !(getenv("ENIGMA_EGL_RECT_FASTPATH") && atoi(getenv("ENIGMA_EGL_RECT_FASTPATH")) == 0);
		const float rad = (float)m_radius;
		if (s_blit_fastpath && m_radius > 0 && width > 0 && height > 0 && 2.0f * rad <= std::min(width, height)) {
			const bool c_tl = m_radius_edges & 1, c_tr = m_radius_edges & 2, c_bl = m_radius_edges & 4, c_br = m_radius_edges & 8;
			const float rt = (c_tl || c_tr) ? rad : 0.0f, rb = (c_bl || c_br) ? rad : 0.0f;
			struct Piece { float x0, y0, x1, y1; };
			Piece pieces[3];
			int npieces = 0;
			pieces[npieces++] = {x, y + rt, x + width, y + height - rb};
			if (rt > 0)
				pieces[npieces++] = {x + (c_tl ? rad : 0.0f), y, x + width - (c_tr ? rad : 0.0f), y + rt};
			if (rb > 0)
				pieces[npieces++] = {x + (c_bl ? rad : 0.0f), y + height - rb, x + width - (c_br ? rad : 0.0f), y + height};
			const float corner[4][4] = {{x, y, rad, rad}, {x + width - rad, y, rad, rad}, {x, y + height - rad, rad, rad}, {x + width - rad, y + height - rad, rad, rad}};
			const bool present[4] = {c_tl, c_tr, c_bl, c_br};

			for (unsigned int i = 0; i < clip.rects.size(); ++i) {
				const eRect& cr = clip.rects[i];
				setGlScissor(cr);
				float verts[3 * 24];
				int nv = 0;
				for (int p = 0; p < npieces; ++p) {
					const float x0 = std::max(pieces[p].x0, (float)cr.left()), y0 = std::max(pieces[p].y0, (float)cr.top());
					const float x1 = std::min(pieces[p].x1, (float)(cr.left() + cr.width())), y1 = std::min(pieces[p].y1, (float)(cr.top() + cr.height()));
					if (x1 <= x0 || y1 <= y0)
						continue;
					const float u0 = (x0 - x) / width, u1 = (x1 - x) / width, v0 = (y0 - y) / height, v1 = (y1 - y) / height;
					const float q[24] = {x0, y0, u0, v0, x0, y1, u0, v1, x1, y0, u1, v0, x1, y0, u1, v0, x0, y1, u0, v1, x1, y1, u1, v1};
					memcpy(verts + nv * 4, q, sizeof(q));
					nv += 6;
				}
				if (nv)
					m_texture_shader.drawBatch(verts, nv, tex_id, 1.0f);
				for (int c = 0; c < 4; ++c) {
					if (!present[c])
						continue;
					const float* q = corner[c];
					if (q[0] >= cr.left() + cr.width() || q[0] + q[2] <= cr.left() || q[1] >= cr.top() + cr.height() || q[1] + q[3] <= cr.top())
						continue;
					m_texture_shader.drawTextureSub(x, y, width, height, q[0], q[1], q[2], q[3], tex_id, rad, m_radius_edges);
				}
			}
		} else {
			for (unsigned int i = 0; i < clip.rects.size(); ++i) {
				setGlScissor(clip.rects[i]);
				m_texture_shader.drawTexture(x, y, width, height, tex_id, 1.0f, m_radius, m_radius_edges);
			}
		}
		if (!enable_blend) {
			m_texture_shader.setPremultiply(false);
			glEnable(GL_BLEND);
		}
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

	if (skipDrawMask() & SKIP_BLIT) {
		m_blit_batch_buffer.clear();
		return;
	}

	if (m_blit_batch_blend) {
		setAlphaBlendMode(m_blit_batch_true_alpha);
		glEnable(GL_BLEND);
	} else {
		glDisable(GL_BLEND);
		m_texture_shader.setPremultiply(m_premultiply_blits);
	}

	setGlScissor(m_blit_batch_clip);
	int vertex_count = (int)(m_blit_batch_buffer.size() / 4);
	m_texture_shader.drawBatch(m_blit_batch_buffer.data(), vertex_count, m_blit_batch_tex_id, 1.0f);

	if (!m_blit_batch_blend) {
		m_texture_shader.setPremultiply(false);
		glEnable(GL_BLEND);
	}

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
	if (m_text_batch_clip.rects.empty() || (skipDrawMask() & SKIP_TEXT)) {
		m_text_batch_buffer.clear();
		return;
	}

	std::chrono::steady_clock::time_point prof_t0;
	if (m_profile) {
		prof_t0 = std::chrono::steady_clock::now();
		m_prof.text_flushes++;
		m_prof.glyphs += (int)(m_text_batch_buffer.size() / 48);
	}

	m_text_shader.bind();

	// Text glyphs are real translucent content (anti-aliased coverage *
	// color alpha) - see setAlphaBlendMode()'s comment for why this needs
	// the accumulating ("true" alphaBlend) formula, overriding whatever an
	// earlier, unrelated draw this frame may have left the blend func's
	// alpha factors set to.
	setAlphaBlendMode(true);

	gPixmap* atlas_pix = m_font_atlas.getPixmap();
	GLuint tex_id = m_texture_manager.getTexture(atlas_pix);
	// Updated in place by row (glTexSubImage2D) - must never be evicted.
	if (atlas_pix && atlas_pix->surface)
		atlas_pix->surface->gl_texture_pinned = true;
	glActiveTexture(GL_TEXTURE0);
	glBindTexture(GL_TEXTURE_2D, tex_id);

	// Modifying a texture that draws already queued this frame sample from
	// makes this tile-based GPU's driver flush the half-built frame first:
	// ENIGMA_EGL_PROFILE measured 10-15ms per glTexSubImage2D of a mere
	// ~20 atlas rows, i.e. 100-130ms per grid-EPG scroll step with fresh
	// titles. So the main atlas texture is only ever updated BEFORE its first
	// use in a frame; glyphs that become new after that are drawn from a
	// freshly created texture holding just the dirty rows (a brand-new
	// texture object can't be in use, so creating it never stalls), and the
	// main atlas catches up at the next frame's first text flush.
	if (m_font_atlas.isDirty() && !m_atlas_used_this_frame) {
		eRect dirty = m_font_atlas.getDirtyRect();

		// GLES 2.0 does not support GL_UNPACK_ROW_LENGTH, so we cannot easily upload
		// an arbitrary sub-rectangle. Instead, we upload full contiguous scanlines
		// for the dirty Y range.
		int start_y = dirty.top();
		int height = dirty.height();
		int stride = atlas_pix->size().width();

		const uint8_t* data = (const uint8_t*)atlas_pix->surface->data;
		data += (start_y * stride);

		std::chrono::steady_clock::time_point atlas_t0;
		if (m_profile)
			atlas_t0 = std::chrono::steady_clock::now();

		glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
		GLenum src_fmt = gles::isGLES3() ? GL_RED : GL_LUMINANCE;
		glTexSubImage2D(GL_TEXTURE_2D, 0, 0, start_y, stride, height, src_fmt, GL_UNSIGNED_BYTE, data);
		glPixelStorei(GL_UNPACK_ALIGNMENT, 4);

		m_font_atlas.clearDirty();

		if (m_profile) {
			m_prof.atlas_ms += msSince(atlas_t0);
			m_prof.atlas_uploads++;
			m_prof.atlas_rows += height;
		}
	}

	if (!m_font_atlas.isDirty()) {
		drawTextVertices(m_text_batch_buffer);
		m_atlas_used_this_frame = true;
	} else {
		// Every glyph added since the main atlas was last uploaded lies
		// entirely inside the dirty row band (addGlyph() grows the dirty rect
		// to cover it); anything not entirely inside was uploaded already.
		const eRect dirty = m_font_atlas.getDirtyRect();
		const float atlas_h = (float)atlas_pix->size().height();
		const float band_top = (float)dirty.top();
		const float band_h = (float)dirty.height();

		m_text_main_scratch.clear();
		m_text_band_scratch.clear();
		// 48 floats per glyph quad: 6 vertices x (x, y, u, v, r, g, b, a);
		// vertex 0 carries v0, vertex 1 carries v1 (see renderGlyph()).
		for (size_t q = 0; q + 48 <= m_text_batch_buffer.size(); q += 48) {
			const float* quad = &m_text_batch_buffer[q];
			const float top = quad[3] * atlas_h;
			const float bottom = quad[11] * atlas_h;
			if (top >= band_top - 0.5f && bottom <= band_top + band_h + 0.5f) {
				m_text_band_scratch.insert(m_text_band_scratch.end(), quad, quad + 48);
				float* band_quad = &m_text_band_scratch[m_text_band_scratch.size() - 48];
				for (int v = 0; v < 6; ++v)
					band_quad[v * 8 + 3] = (band_quad[v * 8 + 3] * atlas_h - band_top) / band_h;
			} else {
				m_text_main_scratch.insert(m_text_main_scratch.end(), quad, quad + 48);
			}
		}

		if (!m_text_main_scratch.empty()) {
			drawTextVertices(m_text_main_scratch);
			m_atlas_used_this_frame = true;
		}

		if (!m_text_band_scratch.empty()) {
			std::chrono::steady_clock::time_point band_t0;
			if (m_profile)
				band_t0 = std::chrono::steady_clock::now();

			const int width = atlas_pix->size().width();
			const uint8_t* data = (const uint8_t*)atlas_pix->surface->data + (size_t)dirty.top() * width;
			GLuint band_tex = 0;
			glGenTextures(1, &band_tex);
			glBindTexture(GL_TEXTURE_2D, band_tex);
			// Same sampling as the main atlas (gTextureManager's defaults).
			glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
			glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
			glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
			glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
			glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
			GLenum internal_fmt = gles::isGLES3() ? GL_R8 : GL_LUMINANCE;
			GLenum src_fmt = gles::isGLES3() ? GL_RED : GL_LUMINANCE;
			glTexImage2D(GL_TEXTURE_2D, 0, internal_fmt, width, dirty.height(), 0, src_fmt, GL_UNSIGNED_BYTE, data);
			glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
			// Deleted after this frame is presented (see flip()); the driver
			// keeps the storage alive until the GPU is done with it anyway.
			m_atlas_band_textures.push_back(band_tex);

			if (m_profile) {
				m_prof.band_ms += msSince(band_t0);
				m_prof.band_uploads++;
				m_prof.band_rows += dirty.height();
			}

			drawTextVertices(m_text_band_scratch);
			glBindTexture(GL_TEXTURE_2D, tex_id);
		}
	}

	m_text_batch_buffer.clear();

	if (m_profile)
		m_prof.text_flush_ms += msSince(prof_t0);
}

void gEGLDC::drawTextVertices(const std::vector<float>& vertices) {
	const int vertex_count = (int)(vertices.size() / 8); // 8 floats per vertex
	const std::vector<eRect>& rects = m_text_batch_clip.rects;

	if (rects.size() > 1) {
		// A multi-rect clip used to re-submit the WHOLE batch once per rect and let
		// the scissor discard most of it. Submit only the glyph quads that touch
		// each rect instead. Quad layout (see renderGlyph()): 48 floats, vertex 0 =
		// (x, y), vertex 1 y = y + h, vertex 2 x = x + w.
		static std::vector<float> s_cull; // render thread only
		for (unsigned int i = 0; i < rects.size(); ++i) {
			const float rl = (float)rects[i].left(), rt = (float)rects[i].top();
			const float rr = rl + (float)rects[i].width(), rb = rt + (float)rects[i].height();
			s_cull.clear();
			for (size_t q = 0; q + 48 <= vertices.size(); q += 48) {
				const float* quad = &vertices[q];
				if (quad[16] <= rl || quad[0] >= rr || quad[9] <= rt || quad[1] >= rb)
					continue;
				s_cull.insert(s_cull.end(), quad, quad + 48);
			}
			if (s_cull.empty())
				continue;
			std::chrono::steady_clock::time_point vbo_t0;
			if (m_profile)
				vbo_t0 = std::chrono::steady_clock::now();
			m_text_shader.setVertexData(s_cull.data(), (int)(s_cull.size() / 8));
			if (m_profile)
				m_prof.vbo_ms += msSince(vbo_t0);
			setGlScissor(rects[i]);
			glDrawArrays(GL_TRIANGLES, 0, (int)(s_cull.size() / 8));
			m_text_shader.endVertexData();
		}
		return;
	}

	std::chrono::steady_clock::time_point vbo_t0;
	if (m_profile)
		vbo_t0 = std::chrono::steady_clock::now();
	m_text_shader.setVertexData(vertices.data(), vertex_count);
	if (m_profile)
		m_prof.vbo_ms += msSince(vbo_t0);

	// m_text_batch_clip, not m_current_clip - see its declaration comment.
	for (unsigned int i = 0; i < rects.size(); ++i) {
		setGlScissor(rects[i]);
		glDrawArrays(GL_TRIANGLES, 0, vertex_count);
	}

	m_text_shader.endVertexData();
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

	std::chrono::steady_clock::time_point prof_t0;
	if (m_profile)
		prof_t0 = std::chrono::steady_clock::now();

	// Incremental glTexSubImage2D update instead of deleting and recreating
	// a full 1920x1080 texture on every single text/para draw (which was
	// both very slow and, before the use-after-free above was fixed, the
	// apparent source of visible corruption of unrelated content).
	GLuint tex_id = m_pixmap->surface->gl_texture_id;
	if (tex_id == 0) {
		tex_id = m_texture_manager.getTexture(m_pixmap);
		// CPU text-overlay staging texture, updated in place - never evict.
		m_pixmap->surface->gl_texture_pinned = true;
	} else {
		uploadOverlayBand(tex_id, area.left(), area.top(), area.left() + area.width(), area.top() + area.height());
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

	if (m_profile) {
		m_prof.overlays++;
		m_prof.overlay_ms += msSince(prof_t0);
	}
}

// GPU-only spinner, used where window-surface readbacks are unreliable (libMali:
// conservativeReadback()) - the CPU path (captureBackgroundIntoPixmap() + gDC's m_pixmap
// compositing) showed stripes and a leftover square there. ENIGMA_EGL_SPINNER_GPU=0 forces
// the old path, =1 forces this one on every provider. Unscaled canvases only.
bool gEGLDC::spinnerGpuPath() {
	static const int mode = getenv("ENIGMA_EGL_SPINNER_GPU") ? atoi(getenv("ENIGMA_EGL_SPINNER_GPU")) : -1;
	if (mode == 0 || isScaled() || !m_spinner_pic || m_spinner_num <= 0 || !m_window_provider)
		return false;
	return mode == 1 || m_window_provider->conservativeReadback();
}

void gEGLDC::releaseSpinnerGpu() {
	if (m_spinner_bg_tex) {
		glDeleteTextures(1, &m_spinner_bg_tex);
		m_spinner_bg_tex = 0;
	}
	m_spinner_gpu = false;
}

bool gEGLDC::captureSpinnerGpu() {
	flushBlitBatch();
	flushTextBatch();
	releaseSpinnerGpu();

	const int left = std::max(0, m_spinner_pos.left());
	const int top = std::max(0, m_spinner_pos.top());
	const int w = std::min(m_width, m_spinner_pos.left() + m_spinner_pos.width()) - left;
	const int h = std::min(m_height, m_spinner_pos.top() + m_spinner_pos.height()) - top;
	if (w <= 0 || h <= 0)
		return false;

	while (glGetError() != GL_NO_ERROR) {
	}
	glBindFramebuffer(GL_FRAMEBUFFER, m_use_shadow_fbo ? m_shadow_fbo : 0);
	glGenTextures(1, &m_spinner_bg_tex);
	glBindTexture(GL_TEXTURE_2D, m_spinner_bg_tex);
	// glCopyTexImage2D's y is measured from the bottom of the framebuffer.
	glCopyTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, left, m_height - top - h, w, h, 0);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
	glBindTexture(GL_TEXTURE_2D, 0);
	const GLenum err = glGetError();
	static bool s_logged = false;
	if (!s_logged) {
		s_logged = true;
		eDebug("[gEGLDC] GPU spinner: background copy %dx%d at %d,%d glError=0x%x", w, h, left, top, err);
	}
	if (err != GL_NO_ERROR) {
		releaseSpinnerGpu();
		while (glGetError() != GL_NO_ERROR) {
		}
		return false;
	}
	m_spinner_gpu_rect = eRect(left, top, w, h);
	m_spinner_gpu = true;
	return true;
}

// Redraws the saved background over the spinner rect (blend off: an exact overwrite, alpha
// included, so transparent areas stay transparent) and, if asked, the next icon frame over it.
void gEGLDC::drawSpinnerGpu(bool with_icon) {
	if (!m_spinner_gpu || !m_spinner_bg_tex)
		return;
	flushBlitBatch();
	flushTextBatch();
	m_texture_manager.processDeletions();

	glBindFramebuffer(GL_FRAMEBUFFER, m_use_shadow_fbo ? m_shadow_fbo : 0);
	setGlScissor(m_spinner_gpu_rect);
	const float x0 = (float)m_spinner_gpu_rect.left(), y0 = (float)m_spinner_gpu_rect.top();
	const float x1 = x0 + (float)m_spinner_gpu_rect.width(), y1 = y0 + (float)m_spinner_gpu_rect.height();
	// The copy is bottom-up (GL framebuffer origin), so V runs 1 at the top edge.
	const float quad[24] = {x0, y0, 0.0f, 1.0f, x0, y1, 0.0f, 0.0f, x1, y0, 1.0f, 1.0f, x1, y0, 1.0f, 1.0f, x0, y1, 0.0f, 0.0f, x1, y1, 1.0f, 0.0f};
	glDisable(GL_BLEND);
	m_texture_shader.setUnpremultiply(false);
	m_texture_shader.drawBatch(quad, 6, m_spinner_bg_tex, 1.0f);

	// ENIGMA_EGL_SPINNER_TEST (diagnostic): 1 = redraw only the saved background, no icon;
	// 2 = icon but never animated (always frame 0). If artifacts still show with 1, the
	// content is not the problem - presenting these small 10 Hz updates is.
	static const int s_test = getenv("ENIGMA_EGL_SPINNER_TEST") ? atoi(getenv("ENIGMA_EGL_SPINNER_TEST")) : 0;
	if (with_icon && s_test != 1) {
		gPixmap* pic = m_spinner_pic[s_test == 2 ? 0 : m_spinner_i];
		if (s_test != 2)
			m_spinner_i = (m_spinner_i + 1) % m_spinner_num;
		if (pic && pic->surface) {
			GLuint tex = m_texture_manager.getTexture(pic);
			if (tex) {
				setAlphaBlendMode(true);
				glEnable(GL_BLEND);
				m_texture_shader.drawTexture(x0, y0, x1 - x0, y1 - y0, tex);
			}
		}
	}
	glEnable(GL_BLEND);
}

// A fresh window surface's buffers are opaque black on libMali (alpha 1): anywhere the UI
// has not painted yet - exactly where the boot spinner appears - the screen shows a black
// square instead of the video/boot picture underneath, and the spinner saves and restores
// that black as its "background". Clear every buffer to fully transparent once, so
// unpainted areas show through. Window surfaces without a shadow FBO only (the shadow
// FBO is created transparent already and overwrites the window each frame).
void gEGLDC::clearWindowSurfaceTransparent() {
	if (!m_window_provider || m_window_provider->usesPixmapSurface() || m_use_shadow_fbo || m_egl_surfaces[0] == EGL_NO_SURFACE)
		return;
	static const bool s_enabled = !(getenv("ENIGMA_EGL_CLEAR_WINDOW") && atoi(getenv("ENIGMA_EGL_CLEAR_WINDOW")) == 0);
	if (!s_enabled)
		return;
	glBindFramebuffer(GL_FRAMEBUFFER, 0);
	glScissor(0, 0, m_phys_width, m_phys_height);
	glClearColor(0.0f, 0.0f, 0.0f, 0.0f);
	// Clear + present enough times to cover every buffer of the swap chain.
	for (int i = 0; i < 3; ++i) {
		glClear(GL_COLOR_BUFFER_BIT);
		eglSwapBuffers(m_egl_display, m_egl_surfaces[0]);
	}
	eDebug("[gEGLDC] window surface cleared to transparent (3 buffers)");
}

void gEGLDC::enableSpinner() {
	// The main thread (busy loading a skin - exactly when the spinner shows) has
	// already swapped m_pixmap for the new size but the GL targets are still the
	// old ones until applyPendingResolutionChange(): nothing valid to capture or
	// draw into yet. incrementSpinner() restarts the spinner afterwards.
	if (m_pending_resolution_change) {
		m_spinner_active = false;
		return;
	}
	m_spinner_active = true;
	if (spinnerGpuPath() && captureSpinnerGpu()) {
		drawSpinnerGpu(true);
		return;
	}
	// gDC::enableSpinner() (grc.cpp) is about to do
	// "m_spinner_saved->blit(*m_pixmap, ...)" to remember what's under the
	// spinner for every later restore - written for a backend where
	// m_pixmap IS the real displayed framebuffer (gFBDC), so that blit
	// captures genuine on-screen pixels there. Not true here (see this
	// class's constructor: m_pixmap is only ever a CPU staging buffer for
	// text on this backend) - without first overwriting m_pixmap's spinner
	// rect with a real GPU readback, that save captures whatever m_pixmap
	// already held there (normally nothing, fully transparent), and every
	// later destructive composite (see compositeTextOverlay(..., false)
	// below and in incrementSpinner()/disableSpinner() - the deliberate fix
	// for the spinner otherwise ghosting between frames) paints that
	// emptiness straight over the real screen: the spinner appeared to
	// punch a transparent hole through whatever was on screen instead of
	// animating over it. See captureBackgroundIntoPixmap()'s own comment.
	captureBackgroundIntoPixmap(m_spinner_pos);
	gDC::enableSpinner();
	// m_spinner_pos is a screen-absolute rect (the spinner is a global
	// overlay, not part of any widget's offset-relative coordinate space),
	// so unlike renderText/renderPara's area it must NOT have
	// m_current_offset applied here.
	//
	// false, not the default true - see disableSpinner()'s comment. This
	// first frame's m_pixmap content is already the full background+icon
	// composite (gDC::enableSpinner() just built it, from the real
	// background captureBackgroundIntoPixmap() just seeded it with), not
	// translucent content to layer over whatever the GPU target previously
	// held there, so it needs the same unconditional-overwrite blend
	// disableSpinner() and incrementSpinner() use.
	compositeTextOverlay(m_spinner_pos, false);
}

// ENIGMA_EGL_SPINNER_DUMP=1: writes what disableSpinner() is about to paint over the
// screen (m_pixmap's spinner rect right after gDC::disableSpinner() restored the saved
// background) to /tmp/spinner_restore_<n>.ppm (RGB) and .alpha.pgm (raw alpha byte), so a bad
// erase can be told apart from a bad capture (see captureBackgroundIntoPixmap()).
void gEGLDC::dumpSpinnerRestore() {
	static const bool s_dump = getenv("ENIGMA_EGL_SPINNER_DUMP") && atoi(getenv("ENIGMA_EGL_SPINNER_DUMP")) != 0;
	if (!s_dump || !m_pixmap || !m_pixmap->surface)
		return;
	static int s_n = 0;
	const int pw = m_pixmap->size().width();
	const int ph = m_pixmap->size().height();
	const int left = std::max(0, m_spinner_pos.left());
	const int top = std::max(0, m_spinner_pos.top());
	const int w = std::min(pw, m_spinner_pos.left() + m_spinner_pos.width()) - left;
	const int h = std::min(ph, m_spinner_pos.top() + m_spinner_pos.height()) - top;
	if (w <= 0 || h <= 0)
		return;
	const uint8_t* base = (const uint8_t*)m_pixmap->surface->data;
	char path[64];
	snprintf(path, sizeof(path), "/tmp/spinner_restore_%d.ppm", s_n);
	if (FILE* f = fopen(path, "wb")) {
		fprintf(f, "P6\n%d %d\n255\n", w, h);
		for (int row = 0; row < h; ++row) {
			const uint8_t* src = base + (size_t)(top + row) * pw * 4 + (size_t)left * 4;
			for (int x = 0; x < w; ++x) {
				fputc(src[x * 4 + 2], f); // BGRA in memory -> R G B
				fputc(src[x * 4 + 1], f);
				fputc(src[x * 4 + 0], f);
			}
		}
		fclose(f);
	}
	snprintf(path, sizeof(path), "/tmp/spinner_restore_%d.alpha.pgm", s_n);
	if (FILE* f = fopen(path, "wb")) {
		fprintf(f, "P5\n%d %d\n255\n", w, h);
		for (int row = 0; row < h; ++row) {
			const uint8_t* src = base + (size_t)(top + row) * pw * 4 + (size_t)left * 4;
			for (int x = 0; x < w; ++x)
				fputc(src[x * 4 + 3], f);
		}
		fclose(f);
	}
	eDebug("[gEGLDC] spinner restore frame %d dumped to /tmp/spinner_restore_%d.{ppm,alpha.pgm}", s_n, s_n);
	++s_n;
}

void gEGLDC::disableSpinner() {
	// Nothing of ours is on the current target (never enabled, or a resolution
	// change recreated it): restoring m_spinner_saved would paint the old
	// canvas' background over the new one.
	const bool was_active = m_spinner_active;
	m_spinner_active = false;
	if (!was_active || m_pending_resolution_change)
		return;
	if (m_spinner_gpu) {
		drawSpinnerGpu(false); // exact restore of what was there
		releaseSpinnerGpu();
		return;
	}
	gDC::disableSpinner();
	dumpSpinnerRestore();
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
	if (m_pending_resolution_change)
		return;
	if (!m_spinner_active) {
		// Spinner was running across a resolution change: start over against
		// the new target (fresh background capture) instead of recompositing
		// the stale one.
		enableSpinner();
		return;
	}
	if (m_spinner_gpu) {
		drawSpinnerGpu(true);
		return;
	}
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

	// No usable window surface (see applyPendingResolutionChange()): retry, throttled.
	if (m_surface_lost && !m_pending_resolution_change && std::chrono::steady_clock::now() - m_surface_retry_time > std::chrono::milliseconds(500)) {
		m_surface_retry_time = std::chrono::steady_clock::now();
		if (m_window_provider && recreateWindowSurface()) {
			m_surface_lost = false;
			eDebug("[gEGLDC] window surface recovered");
			glViewport(0, 0, m_phys_width, m_phys_height);
			if (m_use_shadow_fbo) {
				destroyShadowFramebuffer();
				recreateShadowFramebuffer();
			}
			requestFlush();
		}
	}
	// A failed shadow FBO (e.g. out of GPU memory right after a resolution
	// change) must not leave rendering on the window surface, which does not
	// preserve content between frames (partial redraws would lose elements).
	if (m_use_shadow_fbo && m_shadow_fbo == 0 && !m_pending_resolution_change &&
		std::chrono::steady_clock::now() - m_shadow_retry_time > std::chrono::milliseconds(200)) {
		flushBlitBatch();
		flushTextBatch();
		m_shadow_retry_time = std::chrono::steady_clock::now();
		if (recreateShadowFramebuffer()) {
			eDebug("[gEGLDC] shadow framebuffer recovered");
			requestFlush(); // the new buffer is blank: ask for a repaint
		}
	}

	// A resolution change recreates the shadow FBO / window surface, which throws
	// away everything drawn into the old ones. Applying it only at flip() (after
	// the frame's opcodes) discarded the first paint of whatever the skin switch
	// showed (e.g. the new infobar) - the desktop believes it was painted and never
	// repaints it. Apply it before the first opcode that follows setResolution()
	// instead, so that paint lands in the new target.
	if (m_pending_resolution_change) {
#ifdef HAVE_EGL_ANIMATION
		cancelWindowAnimation();
#endif
		flushBlitBatch();
		flushTextBatch();
		applyPendingResolutionChange();
	}

	// Captured up front: several cases below free opcode->parm.
	const int prof_op = opcode->opcode;
	std::chrono::steady_clock::time_point prof_t0;
	if (m_profile)
		prof_t0 = std::chrono::steady_clock::now();

#ifdef HAVE_EGL_ANIMATION
	if (m_winanim.pending && isDrawOpcode(opcode->opcode))
		++m_winanim.draw_ops;
#endif

	switch (opcode->opcode) {
#ifdef HAVE_EGL_ANIMATION
		case gOpcode::sendShow:
		case gOpcode::sendHide:
			// Window show/hide hints: see beginWindowAnimation(). gDC::exec() does not free these
			// opcodes' heap parameter, so it is freed here.
			beginWindowAnimation(opcode->opcode == gOpcode::sendShow,
				eRect(opcode->parm.setShowHideInfo->point, opcode->parm.setShowHideInfo->size));
			delete opcode->parm.setShowHideInfo;
			break;

#endif
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
			// eTextPara::blit() (lib/gdi/font.cpp) draws glyphs straight to
			// the GPU via renderGlyph()/the atlas below - both the plain
			// FTC-cache glyph path AND, as of the fix documented at its
			// i->image branch, the pre-stroked border-pass/fill-pass glyphs
			// bordered text uses. Only GS_INVERT'd glyphs (a flat color swap
			// renderGlyph() can't express) and a renderGlyph() call made
			// before this backend finished initializing still fall back to
			// pure software rasterization directly into dc.getPixmap()'s CPU
			// buffer (gDC::m_pixmap). compositeTextOverlay() uploads that CPU
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

			// Border text (textBColor/textBWidth, eTextPara::blit()'s
			// two-pass border+fill technique - see grc.cpp's renderText
			// handling) now normally goes through the same GPU atlas path as
			// plain text (see the i->image branch's comment in font.cpp) and
			// won't touch this CPU staging buffer at all - but it still can,
			// for a GS_INVERT'd bordered glyph or if renderGlyph() is called
			// before this backend finished initializing (see its own early
			// return). This pre-clear is cheap (a memset scoped to just this
			// text's own small bounding box, not the whole screen - see
			// clearOverlayArea()) and must run before gDC::exec() regardless,
			// since it protects against whatever CPU rasterization *might*
			// happen during it, which isn't known until after it runs.
			// Gated on ->border specifically rather than unconditionally
			// since it's known up front here, and the overwhelming majority
			// of text draws have no border to begin with.
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

			// Same reasoning as renderText's ->border pre-clear above, for a
			// different trigger: GS_INVERT (a marked/selected character, e.g.
			// ConfigText's select-all-on-focus state) forces its glyph through
			// the CPU fallback (font.cpp skips offering it to renderGlyph() -
			// invert isn't a flat color renderGlyph() can express), so this
			// call will end up compositeTextOverlay()-ing the CPU buffer over
			// this WHOLE area, not just that one glyph's cell. Without
			// clearing first, every position outside that one glyph is
			// whatever's stale in this shared staging buffer from an earlier,
			// unrelated draw - compositing that over an otherwise fully
			// GPU-batched string (every other glyph here has no reason to take
			// the CPU path) erased the batch-rendered text underneath it
			// instead of leaving it alone. Checked upfront, before gDC::exec()
			// runs, same as ->border - most renderPara calls have no inverted
			// glyph and skip this entirely.
			bool has_invert_glyph = false;
			for (int g = 0; g < textpara->size(); ++g) {
				if (textpara->getGlyphFlags(g) & GS_INVERT) {
					has_invert_glyph = true;
					break;
				}
			}
			if (has_invert_glyph) {
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
			// Batches first: a pending blit batch may still reference a
			// texture that is queued for deletion (its pixmap's last ref was
			// dropped by executeBlit()'s own guard) - deleting it before
			// that batch is drawn renders the picture black.
			if (legacyTexDeletion()) {
				m_texture_manager.processDeletions();
				flushBlitBatch();
				flushTextBatch();
			} else {
				flushBlitBatch();
				flushTextBatch();
				m_texture_manager.processDeletions();
			}
#ifdef HAVE_EGL_ANIMATION
			finishWindowAnimation();
#endif
			flip();
			gDC::exec(opcode);
			break;

		case gOpcode::flip:
			if (legacyTexDeletion()) {
				m_texture_manager.processDeletions();
				flushBlitBatch();
				flushTextBatch();
			} else {
				flushBlitBatch();
				flushTextBatch();
				m_texture_manager.processDeletions();
			}
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

	// flush/flip are accounted inside flip() itself (blit/swap split).
	if (m_profile && prof_op != gOpcode::flush && prof_op != gOpcode::flip) {
		double ms = msSince(prof_t0);
		if (prof_op == gOpcode::renderText || prof_op == gOpcode::renderPara) {
			m_prof.text_ops++;
			m_prof.text_ms += ms;
		} else {
			m_prof.other_ops++;
			m_prof.other_ms += ms;
		}
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

// gDC::getRGB() (grc.cpp) resolves a palette-index colour (gColor) through
// m_pixmap->surface->clut, and falls back to gRGB(col, col, col) - i.e. near
// black - when there is no palette. gFBDC gives its 32bpp surface a 256-entry
// palette for exactly this (gfbdc.cpp), because legacy painters such as
// eGauge (needles), which call setPalette() and then pick colours by index,
// depend on it. This backend's staging pixmap had none, so those colours all
// rendered black. Same allocation as gFBDC: 256 zeroed entries, filled in by
// the gOpcode::setPalette handling in gDC::exec().
static void allocStagingPalette(gPixmap* pixmap) {
	if (!pixmap || !pixmap->surface || pixmap->surface->clut.data)
		return;
	pixmap->surface->clut.colors = 256;
	pixmap->surface->clut.start = 0;
	pixmap->surface->clut.data = new gRGB[256];
	memset(static_cast<void*>(pixmap->surface->clut.data), 0, sizeof(gRGB) * 256);
}

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
	m_phys_width = width;
	m_phys_height = height;
	m_native_width = width;
	m_native_height = height;
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
	allocStagingPalette(m_pixmap);
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
	// Before the context goes away: nothing can service a capture after this.
	m_osd_capture.stop();
	if (fbClass::lockChanged == &gEGLDC::onFramebufferLockChanged)
		fbClass::lockChanged = nullptr;

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
		destroyShadowFramebuffer();
		releaseFrameTextures();

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
	m_use_shadow_fbo = false;
}

void gEGLDC::setResolution(int xres, int yres, int bpp) {
	if (m_width == xres && m_height == yres)
		return;

	m_width = xres;
	m_height = yres;
	// See the constructor for why accelNever is required here. Safe to do
	// immediately (unlike the GL/EGL work below) - plain CPU allocation, no
	// GL context needed.
	ePtr<gPixmap> new_pixmap = new gPixmap(eSize(xres, yres), bpp, gPixmap::accelNever);
	allocStagingPalette(new_pixmap);

	// See m_pending_resolution_change's comment (gegldc.h) for why the rest
	// of this can't happen here: it's GL/EGL work, only valid on gRC's
	// render thread, which this call (from Python - skin.py/PicturePlayer/
	// VideoFinetune) is not running on. applyPendingResolutionChange(),
	// called from the top of flip(), does it instead.
	{
		std::lock_guard<std::mutex> lock(m_resolution_mutex);
		// The render thread may still be mid-opcode on the old pixmap (a fast
		// skin switch calls this repeatedly): park it instead of freeing it here.
		m_retired_pixmaps.push_back(m_pixmap);
		m_pixmap = new_pixmap;
		m_pending_width = xres;
		m_pending_height = yres;
	}
	m_pending_resolution_change = true;
}

void gEGLDC::applyPendingResolutionChange() {
	if (!m_pending_resolution_change)
		return;
	m_pending_resolution_change = false;

	// Consistent snapshot of the request (a fast skin switch can call
	// setResolution() again at any moment), and release the staging pixmaps it
	// replaced - safe now, this thread is between opcodes.
	int pending_w, pending_h;
	std::vector<ePtr<gPixmap>> retired;
	{
		std::lock_guard<std::mutex> lock(m_resolution_mutex);
		pending_w = m_pending_width;
		pending_h = m_pending_height;
		retired.swap(m_retired_pixmaps);
	}
	retired.clear();
	eDebug("[gEGLDC] applying resolution change to canvas %dx%d", pending_w, pending_h);

	// Everything queued against the old surface/buffers must have completed
	// before the window is resized or its surface destroyed: back-to-back skin
	// switches otherwise tear a surface down under in-flight frames, which can
	// wedge the Nexus window/swap chain (no error, the UI just stops).
	if (isInitialized())
		glFinish();

	// The new pixmap (already swapped in by setResolution()) has no
	// gl_texture_id and no content yet - any area tracked from the old one
	// is meaningless now.
	m_text_overlay_region = gRegion();
	// Same for the spinner's saved background: it is for the old canvas, so it
	// must never be restored/recomposited. Where the surface is recreated the
	// icon is wiped with it; where it survives (fixed-size window, e.g. Hisi -
	// see updatePhysicalSize()) the skin's full repaint covers the old icon.
	// See m_spinner_active's comment (gegldc.h).
	const bool spinner_was_active = m_spinner_active;
	m_spinner_active = false;
	releaseSpinnerGpu();

	// Physical size first: everything below that touches the real GL targets
	// (native window, surface, viewport, shadow FBO) uses it, while shader
	// projections stay in the logical size. Equal to the pending size unless
	// it exceeds the GPU's texture/renderbuffer limit. The previous physical
	// size is kept as a fallback in case the driver refuses the new one.
	const int prev_phys_w = m_phys_width;
	const int prev_phys_h = m_phys_height;
	updatePhysicalSize(pending_w, pending_h);

	// Nothing about the real window/surface changed (the canvas is being
	// rendered scaled to the size it already had): leave the native window and
	// EGL surface completely alone and only update the GL state below.
	m_log_frames_left = 5;
	const bool physical_unchanged = (m_phys_width == prev_phys_w && m_phys_height == prev_phys_h);
	if (physical_unchanged)
		eDebug("[gEGLDC] physical size stays %dx%d for canvas %dx%d - native window and EGL surface left untouched", m_phys_width, m_phys_height, pending_w, pending_h);

	// Nexus (or whichever platform's provider this is) needs to be told its
	// window's own authored size changed too - see
	// GbquadWindowProvider::onResolutionChanged() for why (stretch scales to
	// whatever size Nexus was last told, not this canvas's actual current
	// size). That size is the physical one, not the logical canvas.
	if (m_window_provider && !physical_unchanged) {
		eDebug("[gEGLDC] resize: updating native window to %dx%d", m_phys_width, m_phys_height);
		m_window_provider->onResolutionChanged(m_phys_width, m_phys_height);
		eDebug("[gEGLDC] resize: native window updated");
	}

	// Confirmed on real hardware via a diagnostic eglQuerySurface() (now
	// removed): the EGL window surface's real backing buffer does NOT
	// follow onResolutionChanged() above - it stayed at the OLD size
	// (matching fbClass's boot-time mode) while the canvas/shadow FBO/
	// shaders were all correctly the NEW size, so flip()'s full-screen blit
	// (dst rect = m_width/m_height, the NEW size) was silently clipping
	// against a surface whose real bounds were still the OLD, smaller size.
	//
	// A first attempt at destroying and recreating m_egl_surfaces[0] here
	// locked the box - this retry differs in one specific way: it releases
	// the context from the surface first (eglMakeCurrent to EGL_NO_SURFACE)
	// before destroying it, which the first attempt skipped. Destroying a
	// surface that's still the current draw/read target is undefined
	// behavior by the EGL spec even where a given driver happens to
	// tolerate it, and NXPL/Nexus's driver plausibly doesn't - this is the
	// standard, spec-correct release sequence used any time an EGL app
	// resizes a window surface. Not a guaranteed fix (this driver's exact
	// failure mode was never confirmed), but a real candidate rather than
	// another blind guess.
	if (isInitialized() && m_window_provider && !m_window_provider->usesPixmapSurface() && !physical_unchanged) {
		// Give the old shadow buffer's GPU memory back BEFORE the surface (and its
		// buffers) is recreated at the new size: holding both at once is what made
		// the new 2560x1440 shadow texture fail to allocate on the GigaBlue.
		if (m_use_shadow_fbo) {
			destroyShadowFramebuffer();
			glFinish();
		}
		eDebug("[gEGLDC] resize: releasing context and destroying EGL surface");
		eglMakeCurrent(m_egl_display, EGL_NO_SURFACE, EGL_NO_SURFACE, m_egl_context);

		if (m_egl_surfaces[0] != EGL_NO_SURFACE) {
			eglDestroySurface(m_egl_display, m_egl_surfaces[0]);
			m_egl_surfaces[0] = EGL_NO_SURFACE;
		}
		eDebug("[gEGLDC] resize: EGL surface destroyed");

		// The Nexus native window settles asynchronously after the update/hide/show
		// above: a surface created too early can come back "valid" yet fail
		// eglMakeCurrent() with EGL_BAD_NATIVE_WINDOW (0x300b), which left the
		// context with no usable surface - video playing, UI invisible. So retry
		// with growing pauses, and re-send the window update late in the sequence.
		auto recreate_surface = [&]() -> bool {
			for (int attempt = 0; attempt < 6; ++attempt) {
				if (attempt > 0) {
					usleep(100000 * attempt);
					if (attempt == 3 && m_window_provider) {
						eDebug("[gEGLDC] resize: re-sending native window update");
						m_window_provider->onResolutionChanged(m_phys_width, m_phys_height);
						usleep(200000);
					}
					eDebug("[gEGLDC] resize: retrying window surface creation (attempt %d)", attempt + 1);
				}
				if (recreateWindowSurface()) {
					EGLint surf_w = -1, surf_h = -1;
					eglQuerySurface(m_egl_display, m_egl_surfaces[0], EGL_WIDTH, &surf_w);
					eglQuerySurface(m_egl_display, m_egl_surfaces[0], EGL_HEIGHT, &surf_h);
					eDebug("[gEGLDC] after surface recreation: canvas=%dx%d, physical=%dx%d, EGL window surface now reports %dx%d",
						pending_w, pending_h, m_phys_width, m_phys_height, (int)surf_w, (int)surf_h);
					return true;
				}
			}
			return false;
		};

		if (!recreate_surface() && (prev_phys_w != m_phys_width || prev_phys_h != m_phys_height) && prev_phys_w > 0 && prev_phys_h > 0) {
			// The driver refused the new window size. Leaving the context with
			// no surface at all means video with no UI, so retry at the size
			// that was working before and render the new canvas scaled into it
			// (aspect may differ from the canvas; this is only a fallback).
			eDebug("[gEGLDC] falling back to the previous physical size %dx%d for canvas %dx%d", prev_phys_w, prev_phys_h, pending_w, pending_h);
			m_phys_width = prev_phys_w;
			m_phys_height = prev_phys_h;
			m_scale_x = (float)prev_phys_w / (float)pending_w;
			m_scale_y = (float)prev_phys_h / (float)pending_h;
			m_scaled = true;
			m_window_provider->onResolutionChanged(prev_phys_w, prev_phys_h);
			recreate_surface();
		}
		m_surface_lost = (m_egl_surfaces[0] == EGL_NO_SURFACE);
		if (!m_surface_lost)
			clearWindowSurfaceTransparent();
		if (m_surface_lost) {
			eDebug("[gEGLDC] resize: no usable window surface after retries - will keep trying");
			m_surface_retry_time = std::chrono::steady_clock::now();
		}
	}

	// Fixed-size window (libMali/Hisi): the surface survives the resize, so the last
	// spinner frame drawn for the old canvas stays in its buffers - the skin is still
	// loading, nothing repaints it, and the restarted spinner (new canvas, new position)
	// then shows up as a second, rotating icon beside this frozen one. Wipe the buffers.
	// Skipped for a shadow FBO (flip() overwrites the window from it) and when the surface
	// was recreated above (already cleared there).
	if (spinner_was_active && physical_unchanged && isInitialized() && !m_surface_lost)
		clearWindowSurfaceTransparent();

	if (isInitialized()) {
		// Set once in initEGL() (right after context creation, same "basic GL
		// state" step) and never touched again until now - a stale viewport
		// still sized for the OLD resolution clips/rescales everything
		// through the NDC-to-framebuffer-pixel transform after the shader
		// projection matrices below already start mapping pixel coordinates
		// to NDC using the NEW resolution: the two disagreeing is exactly
		// what turns into elements clipped away entirely (anything outside
		// the stale, smaller-or-differently-shaped viewport rect) or
		// stretched/squashed wrong (anything inside it) - not just
		// mispositioned, which the shader-matrix fix alone already covered.
		glViewport(0, 0, m_phys_width, m_phys_height);

		m_basic_shader.setResolution((float)pending_w, (float)pending_h);
		m_advanced_shader.setResolution((float)pending_w, (float)pending_h);
		m_texture_shader.setResolution((float)pending_w, (float)pending_h);
		m_text_shader.setResolution((float)pending_w, (float)pending_h);
	}

	// m_shadow_fbo/m_shadow_texture were sized for whatever resolution was
	// current when createShadowFramebuffer() first ran (initEGL(), against
	// this canvas's construction-time size - see egl_init.cpp) and never
	// resized since. Recreate at the new size, same as initEGL() does the
	// first time.
	if (m_use_shadow_fbo) {
		destroyShadowFramebuffer();
		if (!recreateShadowFramebuffer()) {
			eDebug("[gEGLDC] failed to recreate shadow framebuffer at %dx%d after resolution change - will keep retrying.", pending_w, pending_h);
			m_shadow_retry_time = std::chrono::steady_clock::now();
		}
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
	glScissor(0, 0, m_phys_width, m_phys_height);
	glBlitFramebuffer(0, 0, m_phys_width, m_phys_height, 0, 0, m_phys_width, m_phys_height, GL_COLOR_BUFFER_BIT, GL_NEAREST);
	return true;
#else
	(void)from;
	(void)to;
	return false;
#endif
}

int gEGLDC::islocked() const {
	fbClass* fb = fbClass::getInstance();
	return fb ? fb->islocked() : 0;
}

void gEGLDC::onFramebufferLockChanged(bool locked) {
	// Main (Python) thread - the actual clear/restore of the OSD happens in
	// flip() on the render thread, which islocked() tells which one to do.
	if (!s_instance)
		return;
	if (!locked && s_instance->m_window_provider)
		s_instance->m_window_provider->onFramebufferUnlocked();
	s_instance->requestFlush();
}

void gEGLDC::requestFlush() {
	gRC* rc = gRC::getInstance();
	if (!rc)
		return;
	gOpcode o;
	o.opcode = gOpcode::flush;
	AddRef(); // released by gRC::thread() after exec(), like any opcode's dc
	o.dc = this;
	rc->submit(o);
}

// End of frame for the glyph atlas scheme in flushTextBatch(): the next
// frame may update the main atlas again before first use, and this frame's
// band textures are no longer needed (glDeleteTextures() on a texture the GPU
// is still reading is safe - the driver defers the actual free).
void gEGLDC::releaseFrameTextures() {
	if (!m_atlas_band_textures.empty()) {
		glDeleteTextures((GLsizei)m_atlas_band_textures.size(), m_atlas_band_textures.data());
		m_atlas_band_textures.clear();
	}
	m_atlas_used_this_frame = false;
}

// Reads back the frame flip() is about to present, for gEGLOSDCapture. Runs
// before presenting because afterwards a non-preserving window surface's
// content is undefined - the shadow FBO (or the preserved back buffer) is the
// only place the complete frame is guaranteed to exist.
void gEGLDC::serviceOsdCapture() {
	// The real (physical) render target - when the canvas had to be scaled down
	// to fit the GPU's limits, that is what actually exists to read back.
	const int width = m_phys_width;
	const int height = m_phys_height;
	if (width <= 0 || height <= 0) {
		m_osd_capture.fail();
		return;
	}

	// Clear stale errors so the check below only reflects this readback.
	while (glGetError() != GL_NO_ERROR) {
	}

	// Already the bound framebuffer in both cases (rendering targets it) -
	// bound explicitly so the readback never depends on that.
	glBindFramebuffer(GL_FRAMEBUFFER, m_use_shadow_fbo ? m_shadow_fbo : 0);

	std::vector<uint8_t> pixels((size_t)width * (size_t)height * 4U);
	glPixelStorei(GL_PACK_ALIGNMENT, 4);
	glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());

	GLenum err = glGetError();
	if (err != GL_NO_ERROR) {
		eDebug("[gEGLDC] OSD capture readback failed: 0x%x", err);
		m_osd_capture.fail();
		return;
	}
	m_osd_capture.complete(pixels, width, height, gles::needsRBSwap);
}

// Reads back `rect` (clamped to the canvas) from whichever framebuffer
// object currently holds this backend's real, presented content (same
// shadow-FBO-or-0 selection as serviceOsdCapture() above) and writes it into
// m_pixmap's own buffer at that exact rect, as top-down BGRA - m_pixmap's
// byte convention regardless of gles::needsRBSwap (see compositeTextOverlay()'s
// comment: the format token passed to glTexSubImage2D is what varies, not
// the bytes' own order).
//
// Used by enableSpinner() (see its own comment) to give gDC's base-class
// spinner save/restore logic (grc.cpp: enableSpinner()/incrementSpinner()/
// disableSpinner(), all written for a backend where m_pixmap IS the real
// displayed framebuffer - true for gFBDC, NOT for this one, see the
// constructor's accelNever comment) something real to save. Without this,
// m_spinner_saved captured whatever m_pixmap already held under the
// spinner's rect - normally nothing (fully transparent), since this backend
// only ever writes into m_pixmap via CPU-fallback text - so every
// subsequent destructive composite (compositeTextOverlay(..., false), the
// deliberate fix for the spinner icon otherwise ghosting/never fully
// erasing between frames - see incrementSpinner()'s own comment) painted
// that emptiness straight over the real GPU surface: the spinner appeared
// to punch a transparent hole through whatever was on screen instead of
// animating over it.
void gEGLDC::captureBackgroundIntoPixmap(const eRect& rect) {
	// Shouldn't be anything pending at this idle-loop call site (see the
	// call site's comment), but a queued-and-not-yet-drawn batch would
	// otherwise be invisible to the glReadPixels() below - cheap to guard
	// unconditionally, same as every other GPU-state-reading spot in this
	// file (e.g. compositeTextOverlay()'s own opening lines).
	flushBlitBatch();
	flushTextBatch();

	const int pw = m_pixmap->size().width();
	const int ph = m_pixmap->size().height();
	const int left = std::max(0, rect.left());
	const int top = std::max(0, rect.top());
	const int right = std::min(pw, rect.left() + rect.width());
	const int bottom = std::min(ph, rect.top() + rect.height());
	const int w = right - left;
	const int h = bottom - top;
	if (w <= 0 || h <= 0)
		return;

	while (glGetError() != GL_NO_ERROR) {
	}

	glBindFramebuffer(GL_FRAMEBUFFER, m_use_shadow_fbo ? m_shadow_fbo : 0);

	const bool conservative_readback = m_window_provider && m_window_provider->conservativeReadback();
	{
		static bool s_path_logged = false;
		if (!s_path_logged) {
			s_path_logged = true;
			eDebug("[gEGLDC] spinner capture: conservative=%d shadowFbo=%d scaled=%d gpuCopyEnabled=%d", conservative_readback ? 1 : 0, m_use_shadow_fbo ? 1 : 0, isScaled() ? 1 : 0,
				!(getenv("ENIGMA_EGL_SPINNER_GPUCOPY") && atoi(getenv("ENIGMA_EGL_SPINNER_GPUCOPY")) == 0) ? 1 : 0);
		}
	}
	std::vector<uint8_t> pixels((size_t)w * (size_t)h * 4U);
	glPixelStorei(GL_PACK_ALIGNMENT, 4);
	if (!isScaled()) {
		// glReadPixels' y is measured from the BOTTOM of the framebuffer (GL
		// convention) - m_height (the real GPU canvas), not ph (m_pixmap can
		// briefly differ right after setResolution(), see there).
		// Spinner-only "shadow": copy the rect into a small texture on the GPU
		// (glCopyTexImage2D - never touches the CPU) and read THAT back through a
		// temporary FBO. libMali's glReadPixels() of the window surface itself comes
		// back striped / stale; an FBO texture read does not. The texture is padded to
		// a multiple of 16 pixels wide (narrow, unaligned reads were the striped ones).
		// ENIGMA_EGL_SPINNER_GPUCOPY=0 turns it off; any failure falls back below.
		static const bool s_gpucopy = !(getenv("ENIGMA_EGL_SPINNER_GPUCOPY") && atoi(getenv("ENIGMA_EGL_SPINNER_GPUCOPY")) == 0);
		bool copied = false;
		if (conservative_readback && !m_use_shadow_fbo && s_gpucopy) {
			const int cw = std::min(m_width, (w + 15) & ~15);
			const int x0 = std::min(left, m_width - cw);
			GLuint tex = 0, fbo = 0;
			std::vector<uint8_t> band((size_t)cw * (size_t)h * 4U);
			glBindFramebuffer(GL_FRAMEBUFFER, 0);
			glGenTextures(1, &tex);
			glBindTexture(GL_TEXTURE_2D, tex);
			glCopyTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, x0, m_height - top - h, cw, h, 0);
			glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
			glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
			glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
			glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
			glGenFramebuffers(1, &fbo);
			glBindFramebuffer(GL_FRAMEBUFFER, fbo);
			glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, tex, 0);
			const GLenum fbo_status = glCheckFramebufferStatus(GL_FRAMEBUFFER);
			const GLenum copy_err = glGetError();
			static bool s_logged = false;
			if (!s_logged) {
				s_logged = true;
				eDebug("[gEGLDC] spinner background via GPU copy: fboStatus=0x%x glError=0x%x rect=%dx%d at %d,%d (copy %dx%d from x=%d)", fbo_status, copy_err, w, h, left, top, cw, h, x0);
			}
			if (fbo_status == GL_FRAMEBUFFER_COMPLETE && copy_err == GL_NO_ERROR) {
				glReadPixels(0, 0, cw, h, GL_RGBA, GL_UNSIGNED_BYTE, band.data());
				for (int row = 0; row < h; ++row)
					memcpy(pixels.data() + (size_t)row * w * 4U, band.data() + ((size_t)row * cw + (left - x0)) * 4U, (size_t)w * 4U);
				copied = true;
			}
			glBindFramebuffer(GL_FRAMEBUFFER, 0);
			glDeleteFramebuffers(1, &fbo);
			glBindTexture(GL_TEXTURE_2D, 0);
			glDeleteTextures(1, &tex);
			if (!copied) {
				while (glGetError() != GL_NO_ERROR) {
				}
			}
		}
		if (copied) {
			// pixels were filled from the GPU copy above
		} else if (conservative_readback) {
			// Full-width rows, cropped afterwards, rather than a small sub-rect:
			// libMali (Utgard) window-surface readbacks of a narrow, unaligned
			// rect have come back striped, which then got baked into every
			// spinner frame and the final restore. glFinish() first so the
			// readback sees the completed (deferred, tile-based) render of the
			// preserved frame. See INativeWindowProvider::conservativeReadback().
			glFinish();
			std::vector<uint8_t> band((size_t)m_width * (size_t)h * 4U);
			glReadPixels(0, m_height - top - h, m_width, h, GL_RGBA, GL_UNSIGNED_BYTE, band.data());
			for (int row = 0; row < h; ++row)
				memcpy(pixels.data() + (size_t)row * w * 4U, band.data() + ((size_t)row * m_width + left) * 4U, (size_t)w * 4U);
		} else {
			glReadPixels(left, m_height - top - h, w, h, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());
		}
	} else {
		// Canvas is rendered scaled down: read the physical pixels covering
		// the rect, then nearest-neighbour them back up to logical size so the
		// conversion loop below (and m_pixmap) stay in logical coordinates.
		// Full physical width + glFinish() on conservativeReadback() platforms,
		// same reason as the unscaled branch above.
		if (conservative_readback)
			glFinish();
		const int px0 = conservative_readback ? 0 : std::max(0, (int)std::floor(left * m_scale_x));
		const int px1 = conservative_readback ? m_phys_width : std::min(m_phys_width, std::max(px0 + 1, (int)std::ceil(right * m_scale_x)));
		const int py0 = std::max(0, (int)std::floor(top * m_scale_y));
		const int py1 = std::min(m_phys_height, std::max(py0 + 1, (int)std::ceil(bottom * m_scale_y)));
		const int rw = px1 - px0;
		const int rh = py1 - py0;
		std::vector<uint8_t> phys((size_t)rw * (size_t)rh * 4U);
		glReadPixels(px0, m_phys_height - py1, rw, rh, GL_RGBA, GL_UNSIGNED_BYTE, phys.data());
		for (int row = 0; row < h; ++row) { // row: 0 = bottom of the logical rect
			const int ly = top + (h - 1 - row);
			const int from_top = std::min(rh - 1, std::max(0, (int)(ly * m_scale_y) - py0));
			const uint8_t* src_row = phys.data() + (size_t)(rh - 1 - from_top) * rw * 4U;
			uint8_t* dst_row = pixels.data() + (size_t)row * w * 4U;
			for (int col = 0; col < w; ++col) {
				const int from_left = std::min(rw - 1, std::max(0, (int)((left + col) * m_scale_x) - px0));
				memcpy(dst_row + (size_t)col * 4U, src_row + (size_t)from_left * 4U, 4U);
			}
		}
	}

	if (glGetError() != GL_NO_ERROR) {
		eDebug("[gEGLDC] spinner background capture failed");
		return; // m_pixmap keeps whatever it already held there - see call site
	}

	// Bottom-up GL rows -> top-down, and RGBA -> BGRA when this platform's
	// render target isn't already pre-swapped - same conversion as
	// gEGLOSDCapture::capture() (gosd_capture.cpp), which this mirrors.
	uint8_t* dst_base = (uint8_t*)m_pixmap->surface->data;
	const int dst_stride = pw * 4; // tightly packed - see clearOverlayArea()'s comment
	const size_t row_bytes = (size_t)w * 4U;
	for (int row = 0; row < h; ++row) {
		const uint8_t* src_row = pixels.data() + (size_t)(h - 1 - row) * row_bytes;
		uint8_t* dst_row = dst_base + (size_t)(top + row) * dst_stride + (size_t)left * 4;
		memcpy(dst_row, src_row, row_bytes);
	}
	if (!gles::needsRBSwap) {
		for (int row = 0; row < h; ++row) {
			uint8_t* dst_row = dst_base + (size_t)(top + row) * dst_stride + (size_t)left * 4;
			for (int x = 0; x < w; ++x)
				std::swap(dst_row[x * 4 + 0], dst_row[x * 4 + 2]);
		}
	}

	// Diagnostic: ENIGMA_EGL_SPINNER_DUMP=1 writes each captured spinner
	// background (what every later frame is composited over) to
	// /tmp/spinner_bg_<n>.ppm, so stripes/old frames in the readback itself can
	// be told apart from a presentation problem. Never on by default.
	static const bool s_dump = getenv("ENIGMA_EGL_SPINNER_DUMP") && atoi(getenv("ENIGMA_EGL_SPINNER_DUMP")) != 0;
	if (s_dump) {
		static int s_dump_n = 0;
		char path[64];
		snprintf(path, sizeof(path), "/tmp/spinner_bg_%d.ppm", s_dump_n++);
		if (FILE* f = fopen(path, "wb")) {
			fprintf(f, "P6\n%d %d\n255\n", w, h);
			for (int row = 0; row < h; ++row) {
				const uint8_t* s = pixels.data() + (size_t)(h - 1 - row) * row_bytes; // RGBA, as read
				for (int x = 0; x < w; ++x)
					fwrite(s + x * 4, 1, 3, f);
			}
			fclose(f);
			eDebug("[gEGLDC] spinner background %dx%d at %d,%d (conservative=%d) dumped to %s", w, h, left, top, conservative_readback ? 1 : 0, path);
		}
		// Alpha as its own greyscale image - a striped alpha is invisible in the RGB dump.
		snprintf(path, sizeof(path), "/tmp/spinner_bg_%d.alpha.pgm", s_dump_n - 1);
		if (FILE* f = fopen(path, "wb")) {
			fprintf(f, "P5\n%d %d\n255\n", w, h);
			for (int row = 0; row < h; ++row) {
				const uint8_t* src = pixels.data() + (size_t)(h - 1 - row) * row_bytes;
				for (int x = 0; x < w; ++x)
					fputc(src[x * 4 + 3], f);
			}
			fclose(f);
		}
	}
}

#ifdef HAVE_EGL_ANIMATION
// ---------------------------------------------------------------------------------------
// Window show/hide animations (Layer A, doc/ANIMATIONS.md). Everything below runs on gRC's
// render thread. The animation is a sequence of ordinary frames in the normal render
// target: restore the "base" snapshot over the window rect (exact overwrite), draw the moving
// snapshot over it with the preset's transform, flip(). Because each step goes through
// flip(), every presentation mode (pixmap pages, shadow FBO, plain window surface) works
// unchanged, and the last step writes back the real final content before the normal frame
// is presented.
// ---------------------------------------------------------------------------------------

namespace {
void makeAnimQuad(float* q, float x0, float y0, float x1, float y1) {
	// Snapshots come from glCopyTexImage2D, i.e. bottom-up: v = 1 is the top edge.
	const float v[24] = {x0, y0, 0.0f, 1.0f, x0, y1, 0.0f, 0.0f, x1, y0, 1.0f, 1.0f, x1, y0, 1.0f, 1.0f, x0, y1, 0.0f, 0.0f, x1, y1, 1.0f, 0.0f};
	std::memcpy(q, v, sizeof(v));
}

float msBetween(const std::chrono::steady_clock::time_point& a, const std::chrono::steady_clock::time_point& b) {
	return std::chrono::duration<float, std::milli>(b - a).count();
}
} // namespace

bool gEGLDC::isDrawOpcode(int op) {
	switch (op) {
		case gOpcode::renderText:
		case gOpcode::renderPara:
		case gOpcode::fill:
		case gOpcode::fillRegion:
		case gOpcode::clear:
		case gOpcode::blit:
		case gOpcode::gradient:
		case gOpcode::rectangle:
		case gOpcode::line:
			return true;
		default:
			return false;
	}
}

// The same conditions the GPU spinner needs: an unscaled canvas, a settled surface and a
// target that really holds the previous frame.
bool gEGLDC::animationUsable() const {
	if (!ganim::getPreset(ganim::currentPreset()))
		return false;
	if (!isInitialized() || isScaled() || m_pending_resolution_change || m_surface_lost || islocked())
		return false;
	if (m_use_shadow_fbo && m_shadow_fbo == 0)
		return false;
	if (m_spinner_active || m_spinner_gpu)
		return false;
	return true;
}

GLuint gEGLDC::captureAnimTexture(const eRect& rect) {
	while (glGetError() != GL_NO_ERROR) {
	}
	GLuint tex = 0;
	glBindFramebuffer(GL_FRAMEBUFFER, m_use_shadow_fbo ? m_shadow_fbo : 0);
	glGenTextures(1, &tex);
	glBindTexture(GL_TEXTURE_2D, tex);
	// glCopyTexImage2D's y is measured from the bottom of the framebuffer.
	glCopyTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, rect.left(), m_height - rect.top() - rect.height(), rect.width(), rect.height(), 0);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
	glBindTexture(GL_TEXTURE_2D, 0);
	if (glGetError() != GL_NO_ERROR) {
		glDeleteTextures(1, &tex);
		while (glGetError() != GL_NO_ERROR) {
		}
		return 0;
	}
	return tex;
}

void gEGLDC::cancelWindowAnimation() {
	if (m_winanim.before)
		glDeleteTextures(1, &m_winanim.before);
	m_winanim = WinAnim();
}

void gEGLDC::beginWindowAnimation(bool show, const eRect& hint) {
	cancelWindowAnimation();
	if (!animationUsable())
		return;
	const eRect rect = hint & eRect(0, 0, m_width, m_height);
	if (rect.width() < 16 || rect.height() < 16)
		return;

	flushBlitBatch();
	flushTextBatch();
	const GLuint tex = captureAnimTexture(rect);
	if (!tex)
		return;

	m_winanim.pending = true;
	m_winanim.show = show;
	m_winanim.rect = rect;
	m_winanim.before = tex;
	m_winanim.draw_ops = 0;
	m_winanim.started = std::chrono::steady_clock::now();
}

// Called from the flush opcode, after the pending batches were flushed and before the
// frame is presented.
void gEGLDC::finishWindowAnimation() {
	if (!m_winanim.pending)
		return;
	if (msBetween(m_winanim.started, std::chrono::steady_clock::now()) > 1000.0f) {
		cancelWindowAnimation(); // the window never painted: give up
		return;
	}
	if (m_winanim.draw_ops == 0)
		return; // this flush belongs to something else, the window is not painted yet
	if (!animationUsable()) {
		cancelWindowAnimation();
		return;
	}

	const bool show = m_winanim.show;
	const eRect rect = m_winanim.rect;
	const GLuint before = m_winanim.before;
	m_winanim = WinAnim();

	const GLuint after = captureAnimTexture(rect);
	if (after) {
		runWindowAnimation(show, rect, before, after);
		glDeleteTextures(1, &after);
	}
	glDeleteTextures(1, &before);
}

void gEGLDC::runWindowAnimation(bool show, const eRect& rect, GLuint before, GLuint after) {
	const ganim::Preset* preset = ganim::getPreset(ganim::currentPreset());
	if (!preset)
		return;
	const float total_ms = (float)ganim::durationMs(*preset, ganim::currentSpeed());
	// A show moves the new window over the old background, a hide moves the old window away
	// over the (already repainted) background.
	const GLuint base_tex = show ? before : after;
	const GLuint anim_tex = show ? after : before;
	const float rx = (float)rect.left(), ry = (float)rect.top();
	const float rw = (float)rect.width(), rh = (float)rect.height();

	m_texture_shader.setPremultiply(false);
	m_texture_shader.setUnpremultiply(false);

	float quad[24];
	const std::chrono::steady_clock::time_point t0 = std::chrono::steady_clock::now();
	for (;;) {
		const std::chrono::steady_clock::time_point frame_t0 = std::chrono::steady_clock::now();
		const float t = msBetween(t0, frame_t0) / total_ms;
		if (t >= 1.0f)
			break;
		const float amount = ganim::amountAt(*preset, show, t);

		glBindFramebuffer(GL_FRAMEBUFFER, m_use_shadow_fbo ? m_shadow_fbo : 0);
		setGlScissor(rect);
		glDisable(GL_BLEND);
		makeAnimQuad(quad, rx, ry, rx + rw, ry + rh);
		m_texture_shader.drawBatch(quad, 6, base_tex, 1.0f);

		// The target holds premultiplied pixels: convert the snapshot to straight alpha so
		// the usual SRC_ALPHA blend gives the premultiplied-correct result at any opacity.
		glEnable(GL_BLEND);
		setAlphaBlendMode(true);
		m_texture_shader.setUnpremultiply(true, 1.0f);
		if (preset->stripes) {
			const int stripe_h = 24;
			const int n = (rect.height() + stripe_h - 1) / stripe_h;
			for (int i = 0; i < n; ++i) {
				const float f = std::min(1.0f, (amount - 0.5f * (float)i / (float)std::max(1, n)) / 0.5f);
				if (f <= 0.0f)
					continue;
				const int sy = rect.top() + i * stripe_h;
				const int sh = std::min(stripe_h, rect.top() + rect.height() - sy);
				const int sw = std::max(1, (int)(rw * f));
				const int sx = (i & 1) ? rect.left() + rect.width() - sw : rect.left();
				setGlScissor(eRect(sx, sy, sw, sh));
				makeAnimQuad(quad, rx, ry, rx + rw, ry + rh);
				m_texture_shader.drawBatch(quad, 6, anim_tex, 1.0f);
			}
		} else {
			const ganim::Transform tr = ganim::evaluate(*preset, amount);
			float d[4];
			ganim::destRect(tr, rx, ry, rw, rh, d);
			makeAnimQuad(quad, d[0], d[1], d[2], d[3]);
			m_texture_shader.drawBatch(quad, 6, anim_tex, tr.alpha);
		}
		m_texture_shader.setUnpremultiply(false);

		flip();

		// Cap at ~70 fps if the present did not block on vsync.
		const float frame_ms = msBetween(frame_t0, std::chrono::steady_clock::now());
		if (frame_ms < 14.0f)
			std::this_thread::sleep_for(std::chrono::microseconds((int)((14.0f - frame_ms) * 1000.0f)));
	}

	// Leave the target holding exactly the real final content, then restore GL state.
	glBindFramebuffer(GL_FRAMEBUFFER, m_use_shadow_fbo ? m_shadow_fbo : 0);
	setGlScissor(rect);
	glDisable(GL_BLEND);
	makeAnimQuad(quad, rx, ry, rx + rw, ry + rh);
	m_texture_shader.drawBatch(quad, 6, after, 1.0f);
	glEnable(GL_BLEND);
	glScissor(0, 0, m_phys_width, m_phys_height);
}
#endif // HAVE_EGL_ANIMATION

void gEGLDC::flip() {
	// Defines "this frame" for the texture manager's LRU eviction.
	m_texture_manager.nextFrame();
	std::chrono::steady_clock::time_point prof_t0;
	double prof_blit_ms = 0, prof_present_ms = 0;
	if (m_profile)
		prof_t0 = std::chrono::steady_clock::now();

	// See m_pending_resolution_change's comment (gegldc.h) - must run before
	// anything else below touches m_shadow_fbo/the shaders/the native
	// window, all of which this may just have resized/recreated.
	applyPendingResolutionChange();

	if (m_osd_capture.isPending() && isInitialized())
		serviceOsdCapture();

	if (isInitialized() && m_egl_display != EGL_NO_DISPLAY && m_egl_surfaces[m_render_page] != EGL_NO_SURFACE) {
		// eglSwapBuffers() is only defined for window surfaces; a pixmap-surface
		// platform (Dreambox) presents via the provider instead - see
		// presentPixmap(). m_render_page is the page this frame was just
		// rendered into (see tryInitEGL()'s initial value and the rotation
		// below).
		if (m_window_provider->usesPixmapSurface()) {
			int shown_page = m_render_page;
			std::chrono::steady_clock::time_point present_t0;
			if (m_profile)
				present_t0 = std::chrono::steady_clock::now();
			m_window_provider->presentPixmap(shown_page);
			if (m_profile)
				prof_present_ms = msSince(present_t0);

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
		} else if (m_use_shadow_fbo && islocked()) {
			// See m_lock_cleared's comment (gegldc.h): uncover fb0 once, then
			// present nothing until unlocked.
			if (!m_lock_cleared) {
				glBindFramebuffer(GL_FRAMEBUFFER, 0);
				glScissor(0, 0, m_phys_width, m_phys_height);
				glClearColor(0.0f, 0.0f, 0.0f, 0.0f);
				glClear(GL_COLOR_BUFFER_BIT);
				eglSwapBuffers(m_egl_display, m_egl_surfaces[0]);
				glBindFramebuffer(GL_FRAMEBUFFER, m_shadow_fbo);
				m_lock_cleared = true;
				eDebug("[gEGLDC] framebuffer locked - OSD surface cleared so /dev/fb0 shows");
			}
		} else {
			if (m_lock_cleared) {
				m_lock_cleared = false;
				eDebug("[gEGLDC] framebuffer unlocked - presenting UI again");
			}
			bool shadow_presented = false;
#ifdef HAVE_GLES3
			if (m_use_shadow_fbo && gles::isGLES3() && !m_straight_alpha_present) {
				// MUST be a full-screen blit every single frame, regardless
				// of what actually changed: eglSwapBuffers() on a surface
				// that doesn't preserve content almost certainly cycles
				// between multiple physical backbuffers under the hood
				// (double/triple buffering), not just one. A previous
				// version of this scoped the blit down to only this frame's
				// dirty region as a performance optimization - that broke
				// correctness, because it only ever fully populated
				// whichever ONE buffer happened to be bound at the time:
				// the moment the swap rotated to a different underlying
				// buffer that had never received a full copy, it showed
				// stale/undefined content (observed as "renders once, then
				// goes black" again). m_shadow_fbo is the only buffer in
				// this whole scheme guaranteed to hold the complete, correct
				// picture - every physical backbuffer the driver cycles
				// through must be re-synced from it every frame, not just
				// the ones something happened to redraw into this frame.
				//
				// m_shadow_blit_stride > 1 deliberately violates that rule -
				// it's the diagnostic from m_shadow_blit_stride's comment
				// (gegldc.h), never true unless ENIGMA_EGL_SHADOW_BLIT_STRIDE
				// was set for this one test run. Stride 1 (the default) skips
				// nothing and matches production behaviour exactly.
				bool do_blit = (m_shadow_blit_stride <= 1) ||
					((m_shadow_blit_frame % m_shadow_blit_stride) == 0);

				if (m_shadow_blit_stride != 1)
					eDebug("[gEGLDC] shadow-blit diagnostic: frame=%d stride=%d %s",
						m_shadow_blit_frame, m_shadow_blit_stride, do_blit ? "BLIT" : "skip");

				std::chrono::steady_clock::time_point blit_t0;
				// Diagnostic (needs ENIGMA_EGL_PROFILE=1 too): ENIGMA_EGL_PROFILE_FINISH=1
				// drains the GPU before timing the blit, so the frame's real
				// GPU render time is logged as "finish" and blit= is then the
				// pure copy cost. Adds a stall - never leave enabled.
				static const bool s_prof_finish = getenv("ENIGMA_EGL_PROFILE_FINISH") && atoi(getenv("ENIGMA_EGL_PROFILE_FINISH")) != 0;
				if (m_profile && s_prof_finish) {
					std::chrono::steady_clock::time_point fin_t0 = std::chrono::steady_clock::now();
					glFinish();
					eDebug("[gEGLDC] profile: GPU render drain (finish)=%.2fms", msSince(fin_t0));
				}
				if (m_profile)
					blit_t0 = std::chrono::steady_clock::now();
				if (do_blit) {
					// Tried replacing this with a textured-quad draw through
					// m_texture_shader (the same path every other texture in
					// this renderer uses) on the theory that glBlitFramebuffer()
					// itself was the expensive part of presenting into a
					// Nexus-compositor-owned window surface. Confirmed wrong
					// on real gbquad4kpro hardware: same cost either way (and
					// the shader path came out V-flipped, since drawTexture()
					// assumes CPU-uploaded top-down textures, not a GPU-
					// rendered bottom-up FBO texture like m_shadow_texture).
					// The expense is the full-screen transfer into that
					// surface itself, not which GL call performs it - so
					// there's no cheaper mechanism to swap in here; the only
					// axis that actually changed cost was skipping frames
					// entirely (m_shadow_blit_stride), which is unsafe (see
					// its own comment - confirmed by visible corruption on
					// real hardware even at stride 2).
					glBindFramebuffer(GL_READ_FRAMEBUFFER, m_shadow_fbo);
					glBindFramebuffer(GL_DRAW_FRAMEBUFFER, 0);
					glScissor(0, 0, m_phys_width, m_phys_height);
					if (m_blit_invalidate) {
						const GLenum att = GL_COLOR;
						glInvalidateFramebuffer(GL_DRAW_FRAMEBUFFER, 1, &att);
					}
					glBlitFramebuffer(0, 0, m_phys_width, m_phys_height, 0, 0, m_phys_width, m_phys_height, GL_COLOR_BUFFER_BIT, GL_NEAREST);
					glBindFramebuffer(GL_FRAMEBUFFER, m_shadow_fbo);
				}
				if (m_profile)
					prof_blit_ms = msSince(blit_t0);
				++m_shadow_blit_frame;
				shadow_presented = true;
			}
#endif
			if (m_use_shadow_fbo && !shadow_presented) {
				// GLES2 has no glBlitFramebuffer() (e.g. VU+ vuduo4kse/
				// vusolo4k/vuultimo4k, whose libv3ddriver.so is GLES1/2-only
				// - see configure.ac's GLES3 probe), so copy the shadow
				// canvas into the window surface with a full-screen textured
				// quad instead. Same full-frame-every-frame rule as the blit
				// path above applies. m_shadow_texture is a GPU-rendered,
				// bottom-up texture, whereas the quad geometry below follows
				// gTextureShader::drawTexture()'s top-down CPU-texture
				// convention - hence V is flipped (v=1 at y=0).
				const float w = (float)m_width, h = (float)m_height;
				const float quad[24] = {
					0.0f, 0.0f, 0.0f, 1.0f,  0.0f, h,    0.0f, 0.0f,  w, 0.0f, 1.0f, 1.0f,
					w,    0.0f, 1.0f, 1.0f,  0.0f, h,    0.0f, 0.0f,  w, h,    1.0f, 0.0f};
				glBindFramebuffer(GL_FRAMEBUFFER, 0);
				glScissor(0, 0, m_phys_width, m_phys_height);
				glDisable(GL_BLEND);
				// A compositor that blends straight alpha would multiply the
				// premultiplied frame by alpha a second time (translucent areas
				// too dark) - convert to straight alpha on the way out.
				m_texture_shader.setUnpremultiply(m_straight_alpha_present, m_unpremult_power);
				m_texture_shader.drawBatch(quad, 6, m_shadow_texture, 1.0f);
				m_texture_shader.setUnpremultiply(false);
				glEnable(GL_BLEND);
				glBindFramebuffer(GL_FRAMEBUFFER, m_shadow_fbo);
			}
			std::chrono::steady_clock::time_point swap_t0;
			if (m_profile)
				swap_t0 = std::chrono::steady_clock::now();
			EGLBoolean swap_ok = eglSwapBuffers(m_egl_display, m_egl_surfaces[0]);
			if (m_log_frames_left > 0) {
				--m_log_frames_left;
				const EGLint egl_err = eglGetError();
				const GLenum gl_err = glGetError();
				eDebug("[gEGLDC] frame presented after resolution change: swap=%d eglError=0x%x glError=0x%x canvas=%dx%d physical=%dx%d shadow=%d surface=%p", (int)swap_ok, (int)egl_err, (int)gl_err, m_width, m_height,
					   m_phys_width, m_phys_height, m_use_shadow_fbo ? 1 : 0, (void*)m_egl_surfaces[0]);
			}
			if (m_profile)
				prof_present_ms = msSince(swap_t0);
		}
	}

	releaseFrameTextures();

	if (m_profile) {
		// gap = wall time since the previous flip() returned: the render
		// thread's share of it is the sum of the opcode columns; the rest is
		// time it sat idle waiting for the main thread to queue work.
		double gap_ms = std::chrono::duration<double, std::milli>(prof_t0 - m_prof_last_flip).count();
		eDebug("[gEGLDC] frame: gap=%.1fms text=%d/%.2fms (flush=%d/%.2fms glyphs=%d vbo=%.2fms atlas=%d/%drows/%.2fms band=%d/%drows/%.2fms) cpuOverlay=%d/%.2fms other=%d/%.2fms blit=%.2fms present=%.2fms flip=%.2fms clientArrays=%d",
			gap_ms, m_prof.text_ops, m_prof.text_ms, m_prof.text_flushes, m_prof.text_flush_ms, m_prof.glyphs, m_prof.vbo_ms, m_prof.atlas_uploads, m_prof.atlas_rows, m_prof.atlas_ms,
			m_prof.band_uploads, m_prof.band_rows, m_prof.band_ms, m_prof.overlays, m_prof.overlay_ms, m_prof.other_ops, m_prof.other_ms, prof_blit_ms, prof_present_ms, msSince(prof_t0),
			gles::clientArrays ? 1 : 0);
		eDebug("[gEGLDC] rects: flat=%d fast=%d adv1pass=%d adv2pass=%d advDraws=%d advShadedMpx=%.2f (screen=%.2fMpx)",
			m_prof.rect_flat, m_prof.rect_fast, m_prof.rect_adv1, m_prof.rect_adv2, m_prof.rect_adv_draws, m_prof.rect_adv_mpx, (double)m_width * m_height / 1e6);
		m_prof = FrameProfile();
		m_prof_last_flip = std::chrono::steady_clock::now();
	}
}