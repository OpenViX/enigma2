#include <lib/driver/rc.h>

#include <asm/types.h>
#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/time.h>

#include <lib/base/init.h>
#include <lib/base/init_num.h>
#include <lib/base/eerror.h>
#include <lib/gdi/grc.h>

/*
 *  note on the enigma input layer:
 *  the enigma input layer (rc*) supports n different devices which
 *  all have completely different interfaces, mapped down to 32bit +
 *  make/break/release codes mapped down (via xml files) to "actions".
 *  this was necessary to support multiple remote controls with proprietary
 *  interfaces. now everybody is using input devices, and thus adding
 *  another input layer seems to be a bit overkill. BUT:
 *  image a remote control with two hundred buttons. each and every function
 *  in enigma can be bound to a button. no need to use them twice.
 *  for example, you would have KEY_MENU assigned to a menu for setup etc.,
 *  but no audio and video settings, since you have special keys for that,
 *  and you don't want to display a big menu with entries that are available
 *  with another single key.
 *  then image a remote control with ten buttons. do you really want to waste
 *  KEY_MENU for a simple menu? you need the audio/video settings there too.
 *  take this just as a (bad) example. another (better) example might be front-
 *  button-keys. usually you have KEY_UP, KEY_DOWN, KEY_POWER. you don't want
 *  them to behave like the remote-control-KEY_UP, KEY_DOWN and KEY_POWER,
 *  don't you?
 *  so here we can map same keys of different input devices to different
 *  actions. have fun.
 */

eRCDevice::eRCDevice(std::string id, eRCDriver *driver): driver(driver), id(id)
{
	input=driver->getInput();
	driver->addCodeListener(this);
	eRCInput::getInstance()->addDevice(id, this);
}

eRCDevice::~eRCDevice()
{
	driver->removeCodeListener(this);
	eRCInput::getInstance()->removeDevice(id.c_str());
}

int eRCDevice::setKeyMapping(const std::unordered_map<unsigned int, unsigned int>& remaps)
{
	return eRCInput::remapUnsupported;
}

eRCDriver::eRCDriver(eRCInput *input): input(input), enabled(1)
{
}

eRCDriver::~eRCDriver()
{
	for (std::list<eRCDevice*>::iterator i=listeners.begin(); i!=listeners.end(); ++i)
		delete *i;
}

void eRCShortDriver::keyPressed(int)
{
	uint16_t rccode;
	while (1)
	{
		if (read(handle, &rccode, 2)!=2)
			break;
		if (enabled && !input->islocked())
			for (std::list<eRCDevice*>::iterator i(listeners.begin()); i!=listeners.end(); ++i)
				(*i)->handleCode(rccode);
	}
}

eRCShortDriver::eRCShortDriver(const char *filename): eRCDriver(eRCInput::getInstance())
{
	handle=open(filename, O_RDONLY|O_NONBLOCK);
	if (handle<0)
	{
		eDebug("[eRCShortDriver] cannot open %s: %m", filename);
		sn=0;
	} else
	{
		sn=eSocketNotifier::create(eApp, handle, eSocketNotifier::Read);
		CONNECT(sn->activated, eRCShortDriver::keyPressed);
	}
}

eRCShortDriver::~eRCShortDriver()
{
	if (handle>=0)
		close(handle);
}

void eRCInputEventDriver::keyPressed(int)
{
	struct input_event evs[64];
	while (1)
	{
		ssize_t len = read(handle, evs, sizeof(evs));
		if (len < (ssize_t)sizeof(input_event))
			break;
		int n = len / sizeof(input_event);
		for (int k = 0; k < n; ++k)
			m_pending.push_back(evs[k]);
	}
	processPending();
}

/* newer kernel headers dropped input_event.time (64 bit time_t) in favour of input_event_sec/usec */
#ifdef input_event_sec
#define ev_sec(e) ((e).input_event_sec)
#define ev_usec(e) ((e).input_event_usec)
#else
#define ev_sec(e) ((e).time.tv_sec)
#define ev_usec(e) ((e).time.tv_usec)
#endif

static bool keyTraceEnabled()
{
	static const bool enabled = []() {
		const char *e = getenv("ENIGMA_KEY_TRACE");
		return e && atoi(e) != 0;
	}();
	return enabled;
}

/* Tells apart the two possible reasons for a key repeat that stalls:
 *  - "driver gap": the kernel timestamps of two consecutive events of the key are far apart, or the key was
 *    released and pressed again (a press restarts the repeat delay): the driver/remote did not deliver events.
 *  - "late": the event was timestamped long before enigma2 handled it: the main loop was busy (rendering,
 *    Python, GL) and is the one to look at.
 * "dropped" counts repeats discarded by the coalescing in processPending() since the last delivered one. */
void eRCInputEventDriver::traceKey(const struct input_event &ev, bool dropped)
{
	if (ev.type != EV_KEY)
		return;
	struct timeval now;
	gettimeofday(&now, NULL);
	long late = (now.tv_sec - (long)ev_sec(ev)) * 1000 + (now.tv_usec - (long)ev_usec(ev)) / 1000;
	long gap = -1;
	if (m_trace_last_code == ev.code)
		gap = ((long)ev_sec(ev) - m_trace_last_time.tv_sec) * 1000 + ((long)ev_usec(ev) - m_trace_last_time.tv_usec) / 1000;
	if (dropped)
		++m_trace_dropped;
	if (!dropped && (late > 80 || (gap > 250 && ev.value == 2) || (ev.value == 1 && m_trace_last_value == 0 && gap >= 0 && gap < 400) || (ev.value == 0 && m_trace_last_value == 2 && gap >= 0 && gap < 60)))
		eDebug("[eRCInputEventDriver] key trace: code=%d value=%d late=%ldms gap_to_previous=%ldms (prev value=%d) dropped_since_last=%d pending=%zu",
			ev.code, ev.value, late, gap, m_trace_last_value, m_trace_dropped, m_pending.size());
	if (!dropped)
		m_trace_dropped = 0;
	m_trace_last_code = ev.code;
	m_trace_last_value = ev.value;
	m_trace_last_time.tv_sec = ev_sec(ev);
	m_trace_last_time.tv_usec = ev_usec(ev);
}

void eRCInputEventDriver::deliver(const struct input_event &ev)
{
	if (enabled && !input->islocked())
		for (std::list<eRCDevice*>::iterator i(listeners.begin()); i!=listeners.end(); ++i)
			(*i)->handleCode((long)&ev);
}

/* Key repeat workarounds for the gbquad4kpro remote driver (dvb.ko sends a spurious release+press
 * while a key is held) and a slow renderer. Compiled in only for that box; other remotes are untouched. */
#ifdef HWGBQUAD4KPRO
#define HOLD_BRIDGE_MS 70

/* A held key repeats faster than a slow screen can be drawn. The selection moves at once but the
 * render thread is still busy with the frames before it, so the screen keeps scrolling for many steps
 * after the key was released. While more than this many frames are waiting, repeats are not delivered. */
#define MAX_FRAMES_BEHIND 2

static bool renderBusy()
{
	gRC *rc = gRC::getInstance();
	return rc && rc->pendingFrames() > MAX_FRAMES_BEHIND;
}

static struct input_event makeKeyEvent(int code, int value)
{
	struct input_event ev;
	memset(&ev, 0, sizeof(ev));
	struct timeval now;
	gettimeofday(&now, NULL);
	ev_sec(ev) = now.tv_sec;
	ev_usec(ev) = now.tv_usec;
	ev.type = EV_KEY;
	ev.code = code;
	ev.value = value;
	return ev;
}

/* the held back release turned out to be a real one */
void eRCInputEventDriver::flushRelease()
{
	if (!m_release_pending)
		return;
	m_release_pending = false;
	m_bridge_timer->stop();
	m_synth_timer->stop();
	const int code = m_held_code;
	m_held_code = -1;
	deliver(makeKeyEvent(code, 0));
}

void eRCInputEventDriver::synthTick()
{
	if (m_held_code < 0 || m_release_pending)
	{
		m_synth_timer->stop();
		return;
	}
	if (!renderBusy())
		deliver(makeKeyEvent(m_held_code, 2));
}

/* returns true when the event has been consumed */
bool eRCInputEventDriver::bridgeHold(struct input_event &ev)
{
	if (ev.value == 2)
	{
		if (m_release_pending)
			return true; /* stale repeat behind a release */
		m_synth_timer->stop(); /* real repeats are back */
		m_held_code = ev.code;
		return false;
	}
	if (m_release_pending)
	{
		if (ev.value == 1 && ev.code == m_held_code)
		{
			/* release + press of a held key: the key never went up */
			m_release_pending = false;
			m_bridge_timer->stop();
			if (keyTraceEnabled())
				eDebug("[eRCInputEventDriver] bridged a release/press glitch of key %d", ev.code);
			ev.value = 2;
			unsigned int rep[2] = {0, 0};
			if (::ioctl(handle, EVIOCGREP, rep) < 0 || rep[1] < 20)
				rep[1] = 80;
			m_synth_timer->start(rep[1], false);
			return false;
		}
		flushRelease(); /* anything else: the release was real */
		return false;
	}
	if (ev.value == 0 && ev.code == m_held_code)
	{
		m_synth_timer->stop();
		m_release_pending = true;
		m_bridge_timer->start(HOLD_BRIDGE_MS, true);
		return true;
	}
	if (ev.value == 1 && ev.code != m_held_code)
	{
		m_synth_timer->stop();
		m_held_code = -1;
	}
	return false;
}
#endif /* HWGBQUAD4KPRO */

void eRCInputEventDriver::processPending()
{
	while (!m_pending.empty())
	{
		struct input_event ev = m_pending.front();
		m_pending.pop_front();

		/* A screen that redraws slower than the key repeat rate would queue up
		 * repeats and keep scrolling after the key is released. When a newer
		 * repeat of the same key is already waiting, drop this one. If the key
		 * has meanwhile been released (the release is queued behind this repeat),
		 * drop it too, so scrolling stops at once instead of replaying the
		 * repeats that piled up while the screen was busy. */
		const bool trace = keyTraceEnabled();
		if (ev.type == EV_KEY && ev.value == 2)
		{
			bool obsolete = false;
			for (std::deque<struct input_event>::const_iterator i(m_pending.begin()); i != m_pending.end(); ++i)
				if (i->type == EV_KEY && i->code == ev.code && (i->value == 2 || i->value == 0))
				{
					obsolete = true;
					break;
				}
			if (obsolete)
			{
				if (trace)
					traceKey(ev, true);
				continue;
			}
		}

#ifdef HWGBQUAD4KPRO
		/* repeats are only an invitation to move on: skip them while the screen has not caught up */
		if (ev.type == EV_KEY && ev.value == 2 && m_remote_control && renderBusy())
		{
			if (trace)
				traceKey(ev, true);
			continue;
		}
#endif

		if (trace)
			traceKey(ev, false);

#ifdef HWGBQUAD4KPRO
		if (ev.type == EV_KEY && m_remote_control && bridgeHold(ev))
			continue;
#endif

		deliver(ev);

		/* A key can start a screen switch (e.g. EXIT closing a menu) which the session completes
		 * from a 0 ms timer, and until then no screen accepts keys. Deliver at most one key per
		 * main loop iteration so such timers run before the next key is handled; otherwise fast
		 * repeated presses hit the gap and show up as "unhandled key". */
		if (ev.type == EV_KEY && !m_pending.empty())
		{
			m_pending_timer->start(0, true);
			return;
		}
	}
}

eRCInputEventDriver::eRCInputEventDriver(const char *filename): eRCDriver(eRCInput::getInstance())
{
	m_pending_timer = eTimer::create(eApp);
	memset(&m_trace_last_time, 0, sizeof(m_trace_last_time));
	m_trace_last_code = m_trace_last_value = m_trace_dropped = 0;
	CONNECT(m_pending_timer->timeout, eRCInputEventDriver::processPending);
#ifdef HWGBQUAD4KPRO
	m_bridge_timer = eTimer::create(eApp);
	m_synth_timer = eTimer::create(eApp);
	CONNECT(m_bridge_timer->timeout, eRCInputEventDriver::flushRelease);
	CONNECT(m_synth_timer->timeout, eRCInputEventDriver::synthTick);
	m_held_code = -1;
	m_release_pending = false;
#endif
	handle=open(filename, O_RDONLY|O_NONBLOCK);
	if (handle<0)
	{
		eDebug("[eRCInputEventDriver] cannot open %s: %m", filename);
		sn=0;
	} else
	{
		sn=eSocketNotifier::create(eApp, handle, eSocketNotifier::Read);
		CONNECT(sn->activated, eRCInputEventDriver::keyPressed);
		memset(keyCaps, 0, sizeof(keyCaps));
		::ioctl(handle, EVIOCGBIT(EV_KEY, sizeof(keyCaps)), keyCaps);
		memset(evCaps, 0, sizeof(evCaps));
		::ioctl(handle, EVIOCGBIT(0, sizeof(evCaps)), evCaps);
#if DUMPKEYS
		int i;
		eDebugNoNewLineStart("[eRCInputEventDriver] %s keycaps: ", filename);
		for (i = 0; i< sizeof(keyCaps); i++)
			eDebugNoNewLine(" %02X", keyCaps[i]);
		eDebugNoNewLine("\n");
		eDebugNoNewLineStart("[eRCInputEventDriver] %s evcaps: ", filename);
		for (i = 0; i< sizeof(evCaps); i++)
			eDebugNoNewLine(" %02X", evCaps[i]);
		eDebugNoNewLine("\n");
#endif
	m_remote_control = getDeviceName().find("remote control") != std::string::npos; /* assume remote control when name says so */
	}
}

std::string eRCInputEventDriver::getDeviceName()
{
	char name[128]="";
	if (handle >= 0) {
		::ioctl(handle, EVIOCGNAME(128), name);
		eDebug("[eRCInputEventDriver] devicename=%s", name);
	}
#ifdef FORCE_ADVANCED_REMOTE
	if (!strcmp(name, "dreambox remote control (native)")) return "dreambox advanced remote control (native)";
#endif
	return name;
}

void eRCInputEventDriver::setExclusive(bool b)
{
	if (handle >= 0)
	{
		int grab = b;
		if (::ioctl(handle, EVIOCGRAB, grab) < 0)
			eDebug("[eRCInputEventDriver] EVIOCGRAB: %m");
	}
}

bool eRCInputEventDriver::hasCap(unsigned char *caps, int bit)
{
	return (caps[bit / 8] & (1 << (bit % 8)));
}

bool eRCInputEventDriver::isKeyboard()
{
	if (m_remote_control)
		return false;
	/* check whether the input device has KEY_A, in which case we assume it is a keyboard */
	return hasCap(keyCaps, KEY_A);
}

bool eRCInputEventDriver::isPointerDevice()
{
	if (m_remote_control)
		return false;
	return hasCap(evCaps, EV_REL) || hasCap(evCaps, EV_ABS);
}

eRCInputEventDriver::~eRCInputEventDriver()
{
	if (handle>=0)
		close(handle);
}

eRCConfig::eRCConfig()
{
	reload();
}

eRCConfig::~eRCConfig()
{
	save();
}

void eRCConfig::set( int delay, int repeat )
{
	rdelay = delay;
	rrate = repeat;
}

void eRCConfig::reload()
{
	rdelay=500;
	rrate=100;
}

void eRCConfig::save()
{
}

eRCInput *eRCInput::instance;

eRCInput::eRCInput()
{
	ASSERT( !instance);
	instance=this;
	locked = 0;
	keyboardMode = kmNone;
}

eRCInput::~eRCInput()
{
}

void eRCInput::close()
{
}

bool eRCInput::open()
{
	return false;
}

void eRCInput::lock()
{
	locked=1;
	for (std::map<std::string,eRCDevice*>::iterator i=devices.begin(); i != devices.end(); ++i)
		i->second->setExclusive(false);
}

void eRCInput::unlock()
{
	locked=0;
	for (std::map<std::string,eRCDevice*>::iterator i=devices.begin(); i != devices.end(); ++i)
		i->second->setExclusive(true);
}

void eRCInput::addDevice(const std::string &id, eRCDevice *dev)
{
	devices.insert(std::pair<std::string,eRCDevice*>(id, dev));
}

void eRCInput::removeDevice(const std::string &id)
{
	devices.erase(id);
}

int eRCInput::setKeyMapping(const std::string &id, ePyObject keyRemap)
{
	eRCDevice *dev = getDevice(id);
	if (dev)
	{
		std::unordered_map<unsigned int, unsigned int> remaps;
		if (!PyDict_Check(keyRemap))
			return remapFormatErr;
		PyObject *from, *to;
		Py_ssize_t pos=0;
		while (PyDict_Next(keyRemap, &pos, &from, &to)) {
			if (!PyLong_Check(from) || !PyLong_Check(to))
				return remapFormatErr;
			remaps[PyLong_AsLong(from)] = PyLong_AsLong(to);
		}
		return dev->setKeyMapping(remaps);
	}
	return remapNoSuchDevice;
}

eRCDevice *eRCInput::getDevice(const std::string &id)
{
	std::map<std::string,eRCDevice*>::iterator i=devices.find(id);
	if (i == devices.end())
	{
		eDebug("[eRCDevice] failed, possible choices are:");
		for (std::map<std::string,eRCDevice*>::iterator i=devices.begin(); i != devices.end(); ++i)
			eDebug("[eRCDevice]     %s", i->first.c_str());
		return 0;
	}
	return i->second;
}

std::map<std::string,eRCDevice*,eRCInput::lstr> &eRCInput::getDevices()
{
	return devices;
}

eAutoInitP0<eRCInput> init_rcinput(eAutoInitNumbers::rc, "RC Input layer");
