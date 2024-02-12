#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <string.h>

#include <lib/base/cfile.h>
#include <lib/base/init.h>
#include <lib/base/init_num.h>
#include <lib/base/eerror.h>
#include <lib/base/ebase.h>
#include <lib/driver/avswitch.h>

const char *__MODULE__ = "eAVSwitch";
const char *proc_hdmi_rx_monitor = "/proc/stb/hdmi-rx/0/hdmi_rx_monitor";
const char *proc_hdmi_rx_monitor_audio = "/proc/stb/audio/hdmi_rx_monitor";
const char *proc_policy169 = "/proc/stb/video/policy2";
const char *proc_policy43 = "/proc/stb/video/policy";
const char *proc_videoaspect_r = "/proc/stb/vmpeg/0/aspect";
const char *proc_videoaspect_w = "/proc/stb/video/aspect";
const char *proc_videomode = "/proc/stb/video/videomode";
const char *proc_videomode_50 = "/proc/stb/video/videomode_50hz";
const char *proc_videomode_60 = "/proc/stb/video/videomode_60hz";
const char *proc_videomode_24 = "/proc/stb/video/videomode_24hz";

eAVSwitch *eAVSwitch::instance = 0;

eAVSwitch::eAVSwitch()
{
	ASSERT(!instance);
	instance = this;
	m_video_mode = 0;
	m_active = false;
	m_fp_fd = open("/dev/dbox/fp0", O_RDONLY|O_NONBLOCK);
	if (m_fp_fd == -1)
	{
		eDebug("[eAVSwitch] failed to open /dev/dbox/fp0 to monitor vcr scart slow blanking changed: %m");
		m_fp_notifier=0;
	}
	else
	{
		m_fp_notifier = eSocketNotifier::create(eApp, m_fp_fd, eSocketNotifier::Read|POLLERR);
		CONNECT(m_fp_notifier->activated, eAVSwitch::fp_event);
	}
}

#ifndef FP_IOCTL_GET_EVENT
#define FP_IOCTL_GET_EVENT 20
#endif

#ifndef FP_IOCTL_GET_VCR
#define FP_IOCTL_GET_VCR 7
#endif

#ifndef FP_EVENT_VCR_SB_CHANGED
#define FP_EVENT_VCR_SB_CHANGED 1
#endif

int eAVSwitch::getVCRSlowBlanking()
{
	int val=0;
	if (m_fp_fd >= 0)
	{
		CFile f("/proc/stb/fp/vcr_fns", "r");
		if (f)
		{
			if (fscanf(f, "%d", &val) != 1)
				eDebug("[eAVSwitch] read /proc/stb/fp/vcr_fns failed: %m");
		}
		else if (ioctl(m_fp_fd, FP_IOCTL_GET_VCR, &val) < 0)
			eDebug("[eAVSwitch] FP_GET_VCR failed: %m");
	}
	return val;
}

void eAVSwitch::fp_event(int what)
{
	if (what & POLLERR) // driver not ready for fp polling
	{
		eDebug("[eAVSwitch] fp driver not read for polling.. so disable polling");
		m_fp_notifier->stop();
	}
	else
	{
		CFile f("/proc/stb/fp/events", "r");
		if (f)
		{
			int events;
			if (fscanf(f, "%d", &events) != 1)
				eDebug("[eAVSwitch] read /proc/stb/fp/events failed: %m");
			else if (events & FP_EVENT_VCR_SB_CHANGED)
				/* emit */ vcr_sb_notifier(getVCRSlowBlanking());
		}
		else
		{
			int val = FP_EVENT_VCR_SB_CHANGED;  // ask only for this event
			if (ioctl(m_fp_fd, FP_IOCTL_GET_EVENT, &val) < 0)
				eDebug("[eAVSwitch] FP_IOCTL_GET_EVENT failed: %m");
			else if (val & FP_EVENT_VCR_SB_CHANGED)
				/* emit */ vcr_sb_notifier(getVCRSlowBlanking());
		}
	}
}

eAVSwitch::~eAVSwitch()
{
	if ( m_fp_fd >= 0 )
		close(m_fp_fd);
}

eAVSwitch *eAVSwitch::getInstance()
{
	return instance;
}

bool eAVSwitch::haveScartSwitch()
{
	char tmp[255] = {};
	int fd = open("/proc/stb/avs/0/input_choices", O_RDONLY);
	if(fd < 0) {
		eDebug("[eAVSwitch] cannot open /proc/stb/avs/0/input_choices: %m");
		return false;
	}
	if (read(fd, tmp, 255) < 1)
	{
		eDebug("[eAVSwitch] failed to read data from /proc/stb/avs/0/input_choices: %m");
		return false;
	}
	close(fd);
	return !!strstr(tmp, "scart");
}

bool eAVSwitch::isActive()
{
	return m_active;
}

// Get video aspect
int eAVSwitch::getAspect(int defaultVal, int flags) const
{
	int value = 0;
	CFile::parseIntHex(&value, proc_videoaspect_r, __MODULE__, flags);
	if (flags & FLAGS_DEBUG)
		eDebug("[%s] %s: %d", __MODULE__, "getAspect", value);
	return defaultVal;
}

// read the preferred video modes
// parameters flags bit ( 1 = DEBUG , 2 = SUPPRESS_NOT_EXISTS , 4 = SUPPRESS_READWRITE_ERROR)
std::string eAVSwitch::getPreferredModes(int flags) const
{

	const char *fileName = "/proc/stb/video/videomode_edid";
	const char *fileName2 = "/proc/stb/video/videomode_preferred";

	std::string result = "";

	if (access(fileName, R_OK) == 0)
	{
		result = CFile::read(fileName, __MODULE__, flags);
		if (!result.empty() && result[result.length() - 1] == '\n')
		{
			result.erase(result.length() - 1);
		}
	}

	if (result.empty() && access(fileName2, R_OK) == 0)
	{
		result = CFile::read(fileName2, __MODULE__, flags);
		if (!result.empty() && result[result.length() - 1] == '\n')
		{
			result.erase(result.length() - 1);
		}
	}

	return result;
}

// readAvailableModes
// parameters flags bit ( 1 = DEBUG , 2 = SUPPRESS_NOT_EXISTS , 4 = SUPPRESS_READWRITE_ERROR)
std::string eAVSwitch::readAvailableModes(int flags) const
{

	const char *fileName = "/proc/stb/video/videomode_choices";
	std::string result = "";
	if (access(fileName, R_OK) == 0)
	{
		result = CFile::read(fileName, __MODULE__, flags);
	}

	if (!result.empty() && result[result.length() - 1] == '\n')
	{
		result.erase(result.length() - 1);
	}
	if (flags & FLAGS_DEBUG)
		eDebug("[%s] %s: %s", __MODULE__, "readAvailableModes", result.c_str());
	return result;
}

// Get progressive
bool eAVSwitch::getProgressive(int flags) const
{
	int value = 0;
	CFile::parseIntHex(&value, "/proc/stb/vmpeg/0/progressive", __MODULE__, flags);
	if (flags & FLAGS_DEBUG)
		eDebug("[%s] %s: %d", __MODULE__, "getProgressive", value);
	return value == 1;
}

// Get screen resolution X
// parameters defaultVal = 0
// parameters flags bit ( 1 = DEBUG , 2 = SUPPRESS_NOT_EXISTS , 4 = SUPPRESS_READWRITE_ERROR)
// @return resolution value
int eAVSwitch::getResolutionX(int defaultVal, int flags) const
{
	int value;
	int ret = CFile::parseIntHex(&value, "/proc/stb/vmpeg/0/xres", __MODULE__, flags);

	if (ret != 0)
	{
		value = defaultVal;
	}
	else if (flags & FLAGS_DEBUG)
		eDebug("[%s] %s: %d", __MODULE__, "getResolutionX", value);

	return value;
}

// Get screen resolution Y
// parameters defaultVal = 0
// parameters flags bit (1 = DEBUG , 2 = SUPPRESS_NOT_EXISTS , 4 = SUPPRESS_READWRITE_ERROR)
// @return resolution value
int eAVSwitch::getResolutionY(int defaultVal, int flags) const
{

	int value;
	int ret = CFile::parseIntHex(&value, "/proc/stb/vmpeg/0/yres", __MODULE__, flags);

	if (ret != 0)
	{
		value = defaultVal;
	}
	else if (flags & FLAGS_DEBUG)
		eDebug("[%s] %s: %d", __MODULE__, "getResolutionY", value);
	return value;
}

// Get FrameRate
// parameters defaultVal
// parameters flags bit ( 1 = DEBUG , 2 = SUPPRESS_NOT_EXISTS , 4 = SUPPRESS_READWRITE_ERROR)
// @return
int eAVSwitch::getFrameRate(int defaultVal, int flags) const
{

	const char *fileName = "/proc/stb/vmpeg/0/framerate";
	int value = 0;
	int ret = CFile::parseInt(&value, fileName, __MODULE__, flags);
	if (ret != 0)
	{
		value = defaultVal;
	}
	else if (flags & FLAGS_DEBUG)
		eDebug("[%s] %s: %d", __MODULE__, "getFrameRate", value);

	return value;
}

// Get VideoMode
// parameters defaultVal
// parameters flags bit ( 1 = DEBUG , 2 = SUPPRESS_NOT_EXISTS , 4 = SUPPRESS_READWRITE_ERROR)
// @return
std::string eAVSwitch::getVideoMode(const std::string &defaultVal, int flags) const
{
	std::string result = CFile::read(proc_videomode, __MODULE__, flags);
	if (!result.empty() && result[result.length() - 1] == '\n')
	{
		result.erase(result.length() - 1);
	}
	if (flags & FLAGS_DEBUG)
		eDebug("[%s] %s: %s", __MODULE__, "getVideoMode", result.c_str());

	return result;
}

void eAVSwitch::setInput(int val)
{
	/*
	0-encoder
	1-scart
	2-aux
	*/

	const char *input[] = {"encoder", "scart", "aux"};

	int fd;

	m_active = val == 0;

	if((fd = open("/proc/stb/avs/0/input", O_WRONLY)) < 0) {
		eDebug("[eAVSwitch] cannot open /proc/stb/avs/0/input: %m");
		return;
	}

	if (write(fd, input[val], strlen(input[val])) < 0)
	{
		eDebug("[eAVSwitch] setInput failed %m");
	}
	close(fd);
}

// set VideoMode --> newMode
void eAVSwitch::setVideoMode(const std::string &newMode, int flags) const
{
	CFile::writeStr(proc_videomode, newMode, __MODULE__, flags);
	if (flags & FLAGS_DEBUG)
		eDebug("[%s] %s: %s", __MODULE__, "setVideoMode", newMode.c_str());
}

// @brief setAspect
// parameters newFormat (auto, 4:3, 16:9, 16:10)
// parameters flags bit ( 1 = DEBUG , 2 = SUPPRESS_NOT_EXISTS , 4 = SUPPRESS_READWRITE_ERROR)
void eAVSwitch::setAspect(const std::string &newFormat, int flags) const
{
	CFile::writeStr(proc_videoaspect_w, newFormat, __MODULE__, flags);
	if (flags & FLAGS_DEBUG)
		eDebug("[%s] %s: %s", __MODULE__, "setAspect", newFormat.c_str());
}

void eAVSwitch::setColorFormat(int format)
{
	/*
	0-CVBS
	1-RGB
	2-S-Video
	*/
	const char *fmt = "";
	int fd;

	if (access("/proc/stb/avs/0/colorformat", W_OK))
		return;  // no colorformat file...

	switch (format) {
		case 0: fmt = "cvbs";   break;
		case 1: fmt = "rgb";    break;
		case 2: fmt = "svideo"; break;
		case 3: fmt = "yuv";    break;
	}
	if (*fmt == '\0')
		return; // invalid format

	if ((fd = open("/proc/stb/avs/0/colorformat", O_WRONLY)) < 0) {
		eDebug("[eAVSwitch] cannot open /proc/stb/avs/0/colorformat: %m");
		return;
	}

	if (write(fd, fmt, strlen(fmt)) < 1)
	{
		eDebug("[eAVSwitch] setColorFormat failed %m");
	}
	close(fd);
}

void eAVSwitch::setAspectRatio(int ratio)
{
	/*
	0-4:3 Letterbox
	1-4:3 PanScan
	2-16:9
	3-16:9 forced ("panscan")
	4-16:10 Letterbox
	5-16:10 PanScan
	6-16:9 forced ("letterbox")
	*/
	const char *aspect[] = {"4:3", "4:3", "any", "16:9", "16:10", "16:10", "16:9", "16:9"};
	const char *policy[] = {"letterbox", "panscan", "bestfit", "panscan", "letterbox", "panscan", "letterbox"};

	int fd;
	if((fd = open("/proc/stb/video/aspect", O_WRONLY)) < 0) {
		eDebug("[eAVSwitch] cannot open /proc/stb/video/aspect: %m");
		return;
	}
//	eDebug("set aspect to %s", aspect[ratio]);
	if (write(fd, aspect[ratio], strlen(aspect[ratio])) < 1)
	{
		eDebug("[eAVSwitch] setAspectRatio failed %m");
	}
	close(fd);

	if((fd = open("/proc/stb/video/policy", O_WRONLY)) < 0) {
		eDebug("[eAVSwitch] cannot open /proc/stb/video/policy: %m");
		return;
	}
//	eDebug("set ratio to %s", policy[ratio]);
	if (write(fd, policy[ratio], strlen(policy[ratio])) < 1)
	{
		eDebug("[eAVSwitch] setAspectRatio policy failed %m");
	}
	close(fd);

}

void eAVSwitch::setVideomode(int mode)
{
	const char *pal="pal";
	const char *ntsc="ntsc";

	if (mode == m_video_mode)
		return;

	if (mode == 2)
	{
		int fd1 = open("/proc/stb/video/videomode_50hz", O_WRONLY);
		if(fd1 < 0) {
			eDebug("[eAVSwitch] cannot open /proc/stb/video/videomode_50hz: %m");
			return;
		}
		int fd2 = open("/proc/stb/video/videomode_60hz", O_WRONLY);
		if(fd2 < 0) {
			eDebug("[eAVSwitch] cannot open /proc/stb/video/videomode_60hz: %m");
			close(fd1);
			return;
		}
		if (write(fd1, pal, strlen(pal)) < 1)
		{
			eDebug("[eAVSwitch] setVideomode pal failed %m");
		}
		if (write(fd2, ntsc, strlen(ntsc)) < 1)
		{
			eDebug("[eAVSwitch] setVideomode ntsc failed %m");
		}
		close(fd1);
		close(fd2);
	}
	else
	{
		int fd = open("/proc/stb/video/videomode", O_WRONLY);
		if(fd < 0) {
			eDebug("[eAVSwitch] cannot open /proc/stb/video/videomode: %m");
			return;
		}
		switch(mode) {
			case 0:
				if (write(fd, pal, strlen(pal)) < 1)
				{
					eDebug("[eAVSwitch] setVideomode pal failed %m");
				}
				break;
			case 1:
				if (write(fd, ntsc, strlen(ntsc)) < 1)
				{
					eDebug("[eAVSwitch] setVideomode ntsc failed %m");
				}
				break;
			default:
				eDebug("[eAVSwitch] unknown videomode %d", mode);
		}
		close(fd);
	}

	m_video_mode = mode;
}

void eAVSwitch::setWSS(int val) // 0 = auto, 1 = auto(4:3_off)
{
	int fd;
	if((fd = open("/proc/stb/denc/0/wss", O_WRONLY)) < 0) {
		eDebug("[eAVSwitch] cannot open /proc/stb/denc/0/wss: %m");
		return;
	}
	const char *wss[] = {
		"off", "auto", "auto(4:3_off)", "4:3_full_format", "16:9_full_format",
		"14:9_letterbox_center", "14:9_letterbox_top", "16:9_letterbox_center",
		"16:9_letterbox_top", ">16:9_letterbox_center", "14:9_full_format"
	};
	if (write(fd, wss[val], strlen(wss[val])) < 1)
	{
		eDebug("[eAVSwitch] setWSS failed %m");
	}
//	eDebug("set wss to %s", wss[val]);
	close(fd);
}

// set Policy43
void eAVSwitch::setPolicy43(const std::string &newPolicy, int flags) const
{

	CFile::writeStr(proc_policy43, newPolicy, __MODULE__, flags);

	if (flags & FLAGS_DEBUG)
		eDebug("[%s] %s: %s", __MODULE__, "setPolicy43", newPolicy.c_str());
}

// set Policy169
// parameters newPolicy
void eAVSwitch::setPolicy169(const std::string &newPolicy, int flags) const
{

	CFile::writeStr(proc_policy169, newPolicy, __MODULE__, flags);

	if (flags & FLAGS_DEBUG)
		eDebug("[%s] %s: %s", __MODULE__, "setPolicy169", newPolicy.c_str());
}

// set VideoSize
// param top, left, width, height 
void eAVSwitch::setVideoSize(int top, int left, int width, int height, int flags) const
{

	CFile::writeIntHex("/proc/stb/vmpeg/0/dst_top", top, __MODULE__, flags);
	CFile::writeIntHex("/proc/stb/vmpeg/0/dst_left", left, __MODULE__, flags);
	CFile::writeIntHex("/proc/stb/vmpeg/0/dst_width", width, __MODULE__, flags);
	CFile::writeIntHex("/proc/stb/vmpeg/0/dst_height", height, __MODULE__, flags);
	CFile::writeInt("/proc/stb/vmpeg/0/dst_apply", 1, __MODULE__, flags);

	if (flags & FLAGS_DEBUG)
		eDebug("[%s] %s: T:%d L:%d W:%d H:%d", __MODULE__, "setVideoSize", top, left, width, height);
}

//FIXME: correct "run/startlevel"
eAutoInitP0<eAVSwitch> init_avswitch(eAutoInitNumbers::rc, "AVSwitch Driver");
