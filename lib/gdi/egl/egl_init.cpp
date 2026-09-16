#include <lib/base/eerror.h>
#include <lib/base/init.h>
#include <lib/base/init_num.h>
#include <lib/gdi/egl/gegldc.h>
#include <lib/gdi/fb.h>

#ifdef DREAMNEXTGEN
#include <lib/gdi/egl/platform/amlogic/amlogic_window_provider.h>
#endif

#ifdef HAVE_DREAMBOX_EGL
#include <lib/gdi/egl/platform/dreambox/dreambox_window_provider.h>
#endif

class gEGLDCAutoInit : protected eAutoInit
{
	// ePtr, not a raw owning pointer: gEGLDC derives from gMainDC, which is a
	// refcounted iObject accessed elsewhere via ePtr<gMainDC> (main.cpp's
	// gMainDC::getInstance(), eWidgetDesktop::setDC(), gRC::setSpinnerDC()
	// all AddRef() it). A raw pointer here that gets explicit `delete`d in
	// closeNow() raced those other holders: whichever one released its last
	// reference first (typically main.cpp's local ePtr<gMainDC>, which goes
	// out of scope before eMain - and therefore before eInit - is even
	// destroyed) already called `delete this` via Release() while this
	// AutoInit's raw pointer kept pointing at the now-freed object; closeNow()
	// then deleted it a second time, corrupting the heap and crashing with a
	// wild-jump PC a moment later, on Ctrl+C shutdown. Holding an ePtr here
	// keeps the refcount above zero for as long as this AutoInit is alive, so
	// the object is only ever actually destroyed once, from closeNow() below
	// - exactly like every other gMainDC backend (gFBDC, gSDLDC) already does
	// via the generic eAutoInitPtr<T> template.
	ePtr<gEGLDC> m_dc;
	void initNow() override
	{
		// eInit::resumeInit() (called from StartEnigma.py around every plugin
		// scan, via enigma.pauseInit()/enigma.resumeInit()) unconditionally
		// re-invokes initNow() on every already-registered AutoInit, not just
		// new ones (see eInit::resumeInit() in lib/base/init.cpp) - every other
		// AutoInit in this codebase guards against that (see eAutoInitP0's
		// "if (t == nullptr)" in lib/base/init.h); without this guard we would
		// construct a second gEGLDC, and gMainDC's ASSERT(m_instance == 0)
		// would abort the process.
		if (m_dc)
			return;

		INativeWindowProvider *provider = nullptr;

#ifdef DREAMNEXTGEN
		provider = new AmlogicWindowProvider();
#elif defined(HAVE_DREAMBOX_EGL)
		provider = new DreamboxWindowProvider();
#else
		// Fallback for other platforms (SDL/Wayland) once implemented
		// For now, if not HWDREAMONE/HAVE_DREAMBOX_EGL, we don't have a default provider here
		// unless we add SDLWindowProvider or WaylandWindowProvider detection.
#endif

		if (provider)
		{
			int xres = 1920, yres = 1080, bpp = 32;
			if (fbClass::getInstance())
				fbClass::getInstance()->getMode(xres, yres, bpp);

			if (!provider->init(xres, yres))
			{
				eDebug("[gEGLDC] window provider init failed, falling back...");
				delete provider;
				return;
			}

			eDebug("[eInit] + (%d) gEGLDC", rl);
			// Do NOT call initEGL() here: it does eglMakeCurrent(), and EGL
			// contexts are bound per-thread. This runs on the eInit/main
			// thread, but every actual render opcode executes on gRC's own
			// worker thread (gRC::thread(), priority (10) - after this one -
			// see grc.cpp), so that thread would have no current context and
			// every GL call would silently no-op (matches what was observed:
			// no GL errors, glGetIntegerv(GL_VIEWPORT) reading back all
			// zeroes, nothing ever rendering). gRC::thread() calls
			// gEGLDC::getInstance()->initEGL() itself at startup instead,
			// mirroring the existing USE_LIBVUGLES2 pattern in that function.
			m_dc = new gEGLDC(provider, xres, yres);
		}
	}

	void closeNow() override
	{
		// Release() (not delete): m_dc is an ePtr now, see its declaration
		// comment. This drops our reference; the object is only actually
		// destroyed here if we're the last one holding it, which by this
		// point (eInit teardown) every other holder already is.
		m_dc = 0;
	}

public:
	gEGLDCAutoInit()
		// graphic-1, not graphic-2 (gAccel's own priority): gEGLDC's teardown
		// (cleanupEGL()'s eglMakeCurrent/eglDestroyContext/eglTerminate) calls
		// into the vendor EGL/GLES driver, which depends on the BCM graphics
		// core that gAccel::~gAccel() releases via bcm_accel_close(). At the
		// same priority the two would close in registration/link order
		// (undefined in practice); graphic-1 - the same priority gFBDC and
		// gSDLDC already use for exactly this reason - guarantees gEGLDC
		// closes before gAccel (and still inits after it), regardless of link
		// order. Getting this wrong crashes inside the closed-source EGL
		// driver on shutdown with an unhelpful backtrace (PC == fault address,
		// no useful frames) since it's dereferencing state gAccel already
		// tore down.
		: eAutoInit(eAutoInitNumbers::graphic - 1, "gEGLDC"), m_dc(nullptr)
	{
		eInit::add(rl, this);
	}

	~gEGLDCAutoInit()
	{
		eInit::remove(rl, this);
	}
};

static gEGLDCAutoInit init_gEGLDC_custom;
