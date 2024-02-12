from os import path

from enigma import eAVSwitch, getDesktop

from Components.config import ConfigBoolean, ConfigEnableDisable, ConfigNothing, ConfigSelection, ConfigSelectionNumber, ConfigSlider, ConfigSubDict, ConfigSubsection, ConfigYesNo, NoSave, config
from Components.SystemInfo import SystemInfo
from Tools.CList import CList
from Tools.Directories import isPluginInstalled
# from Tools.HardwareInfo import HardwareInfo

config.av = ConfigSubsection()


class AVSwitch:

	rates = {}  # high-level, use selectable modes.
	modes = {}  # a list of (high-level) modes for a certain port.

	rates["PAL"] = {"50Hz": {50: "pal"}, "60Hz": {60: "pal60"}, "multi": {50: "pal", 60: "pal60"}}
	rates["NTSC"] = {"60Hz": {60: "ntsc"}}
	rates["Multi"] = {"multi": {50: "pal", 60: "ntsc"}}
	rates["480i"] = {"60Hz": {60: "480i"}}
	rates["576i"] = {"50Hz": {50: "576i"}}
	rates["480p"] = {"60Hz": {60: "480p"}}
	rates["576p"] = {"50Hz": {50: "576p"}}
	rates["720p"] = {"50Hz": {50: "720p50"},
				"60Hz": {60: "720p"},
				"multi": {50: "720p50", 60: "720p"},
				"auto": {50: "720p50", 60: "720p", 24: "720p24"}}
	rates["1080i"] = {"50Hz": {50: "1080i50"},
				"60Hz": {60: "1080i"},
				"multi": {50: "1080i50", 60: "1080i"},
				"auto": {50: "1080i50", 60: "1080i", 24: "1080i24"}}
	rates["1080p"] = {"50Hz": {50: "1080p50"},
				"60Hz": {60: "1080p"},
				"multi": {50: "1080p50", 60: "1080p"},
				"auto": {50: "1080p50", 60: "1080p", 24: "1080p24"}}
	rates["2160p30"] = {"25Hz": {50: "2160p25"},
				"30Hz": {60: "2160p30"},
				"multi": {50: "2160p25", 60: "2160p30"},
				"auto": {50: "2160p25", 60: "2160p30", 24: "2160p24"}}
	rates["2160p"] = {"50Hz": {50: "2160p50"},
				"60Hz": {60: "2160p"},
				"multi": {50: "2160p50", 60: "2160p"},
				"auto": {50: "2160p50", 60: "2160p", 24: "2160p24"}}

	rates["PC"] = {
		"1024x768": {60: "1024x768"},  # not possible on DM7025
		"800x600": {60: "800x600"},  # also not possible
		"720x480": {60: "720x480"},
		"720x576": {60: "720x576"},
		"1280x720": {60: "1280x720"},
		"1280x720 multi": {50: "1280x720_50", 60: "1280x720"},
		"1920x1080": {60: "1920x1080"},
		"1920x1080 multi": {50: "1920x1080", 60: "1920x1080_50"},
		"1280x1024": {60: "1280x1024"},
		"1366x768": {60: "1366x768"},
		"1366x768 multi": {50: "1366x768", 60: "1366x768_50"},
		"1280x768": {60: "1280x768"},
		"640x480": {60: "640x480"}
	}

	modes["HDMI"] = SystemInfo["VideoModes"][0]
	widescreen_modes = SystemInfo["VideoModes"][1]

	if SystemInfo["hasYUV"]:
		modes["YPbPr"] = modes["HDMI"]

	if SystemInfo["hasScartYUV"]:
		modes["Scart-YPbPr"] = modes["HDMI"]

	if SystemInfo["hasRCA"]:
		modes["RCA"] = ["PAL", "NTSC", "Multi"]

	if SystemInfo["hasJack"]:
		modes["Jack"] = ["PAL", "NTSC", "Multi"]

	if SystemInfo["hasScart"]:
		modes["Scart"] = ["PAL", "NTSC", "Multi"]

	print(f"[AVSwitch] Modes found are: {modes}")

	def __init__(self):
		self.last_modes_preferred = []
		self.on_hotplug = CList()
		self.current_mode = None
		self.current_port = None
		self.readAvailableModes()
		self.readPreferredModes()
		self.createConfig()

	def readAvailableModes(self):
		SystemInfo["AvailableVideomodes"] = []
		SystemInfo["AvailableVideomodes"] = eAVSwitch.getInstance().readAvailableModes().split(" ")
		# print(f"[AVSwitch][readAvailableModes] {SystemInfo['AvailableVideomodes']}")
		if isPluginInstalled("AutoResolution"):
			return SystemInfo["AvailableVideomodes"]

	def readPreferredModes(self):
		self.modes_preferred = eAVSwitch.getInstance().getPreferredModes(1)
		# print("[AVSwitch] reading preferred modes", modes)
		if not self.modes_preferred:
			self.modes_preferred = SystemInfo["AvailableVideomodes"]
			print(f"[AVSwitch][readPreferredModes]none, so using {self.modes_preferred}")
		if self.modes_preferred != self.last_modes_preferred:
			self.last_modes_preferred = self.modes_preferred
			self.on_hotplug("HDMI")  # Must be HDMI.

	# Check if a high-level mode with a given rate is available.
	#
	def isModeAvailable(self, port, mode, rate):
		rateNew = self.rates[mode][rate]
		for modeNew in rateNew.values():
			# print(f"[AVSwitch][isModeAvailable] modeNew:{modeNew} videomodes:{SystemInfo['AvailableVideomodes']}")
			if modeNew not in SystemInfo["AvailableVideomodes"]:
				# print(f"[AVSwitch][isModeAvailable] modeNew:{modeNew} not available")
				return False
		# print(f"[AVSwitch][isModeAvailable] modeNew:{modeNew} available")
		return True

	def isWidescreenMode(self, port, mode):
		return mode in self.widescreen_modes

	def setMode(self, port, mode, rate, force=None):
		print(f"[AVSwitch] setMode - port: {port}, mode: {mode}, rate: {rate}")
		self.current_mode = mode
		self.current_port = port
		modes = self.rates[mode][rate]
		mode_50 = modes.get(50)
		mode_60 = modes.get(60)
		mode_24 = modes.get(24)
		print(f"[AVSwitch] setMode modes - setup_mode: {mode}, available:  mode_50: {mode_50}, mode_60: {mode_60}, mode_24: {mode_24}")
		if mode_50 is None or force == 60:
			mode_50 = mode_60
		if mode_60 is None or force == 50:
			mode_60 = mode_50
		if mode_24 is None or force:
			mode_24 = mode_60
			if force == 50:
				mode_24 = mode_50
		try:
			with open("/proc/stb/video/videomode_50hz", "w") as fd:
				fd.write(mode_50)
				print(f"[AVSwitch][setMode][videomode_50hz] set to {mode_50}")
			with open("/proc/stb/video/videomode_60hz", "w") as fd:
				fd.write(mode_60)
				print(f"[AVSwitch][setMode][videomode_60hz] set to {mode_60}")
		except (IOError, OSError):
			print("[AVSwitch] cannot open /proc/stb/video/videomode_50hz or videomode_60hz")
			try:
				eAVSwitch.getInstance().setVideoMode(mode_50)
				print(f"[AVSwitch][videomode] set to: {mode_50}")  # fallback if no possibility to setup 50/60 hz mode
			except (IOError, OSError):
				print("[AVSwitch] fallback to mode 50 failed.")

		if SystemInfo["Has24hz"]:
			try:
				with open("/proc/stb/video/videomode_24hz", "w") as fd:
					fd.write(mode_24)
					print(f"[AVSwitch][setMode][videomode_24hz] set to {mode_24}")
			except (IOError, OSError):
				print("[AVSwitch] cannot open /proc/stb/video/videomode_24hz")

		if SystemInfo["brand"] in ("gigablue",):
			try:
				# use 50Hz mode (if available) for booting
				with open("/etc/videomode", "w") as fd:
					fd.write(mode_50)
			except (IOError, OSError):
				print("[AVSwitch] GigaBlue writing initial videomode to /etc/videomode failed.")
		map = {"cvbs": 0, "rgb": 1, "svideo": 2, "yuv": 3}
		self.setColorFormat(map[config.av.colorformat.value])

	def saveMode(self, port, mode, rate):
		config.av.videoport.setValue(port)
		config.av.videoport.save()
		if port in config.av.videomode:
			config.av.videomode[port].setValue(mode)
			config.av.videomode[port].save()
		if mode in config.av.videorate:
			config.av.videorate[mode].setValue(rate)
			config.av.videorate[mode].save()

	def isPortUsed(self, port):  # used by VideoWizard
		if port == "HDMI":
			self.readPreferredModes()
			return len(self.modes_preferred) != 0
		else:
			return True

	def getPortList(self):  # used by VideoWizard
		return [port for port in self.modes]

	# Get a list with all modes, with all rates, for a given port.
	def getModeList(self, port):
		res = []
		for mode in self.modes[port]:
			# List all rates which are completely valid.
			rates = [rate for rate in self.rates[mode] if self.isModeAvailable(port, mode, rate)]
			# If at least one rate is ok, add this mode.
			if len(rates):
				res.append((mode, rates))
		return res

	def createConfig(self, *args):
		lst = []
		config.av.videomode = ConfigSubDict()
		config.av.videorate = ConfigSubDict()
		# create list of output ports
		portlist = [port for port in self.modes]
		print(f"[AVSwitch][createConfig] portlist is {portlist}")
		for port in portlist:
			descr = port
			if "HDMI" in port:
				lst.insert(0, (port, descr))
			else:
				lst.append((port, descr))
			modes = self.getModeList(port)
			if len(modes):
				config.av.videomode[port] = ConfigSelection(choices=[mode for (mode, rates) in modes])
			for (mode, rates) in modes:
				ratelist = []
				for rate in rates:
					if rate == "auto":
						if SystemInfo["Has24hz"]:
							ratelist.append((rate, mode == "2160p30" and "auto (25Hz/30Hz/24Hz)" or "auto (50Hz/60Hz/24Hz)"))
					else:
						ratelist.append((rate, rate == "multi" and (mode == "2160p30" and "multi (25Hz/30Hz)" or "multi (50Hz/60Hz)") or rate))
				config.av.videorate[mode] = ConfigSelection(choices=ratelist)
				print(f"[AVSwitch][createConfig] mode:{mode} rates:{ratelist}")
		config.av.videoport = ConfigSelection(choices=lst)

	def setInput(self, input):
		INPUT = {
			"ENCODER": 0,
			"SCART": 1,
			"AUX": 2
		}
		eAVSwitch.getInstance().setInput(INPUT[input])

	def setColorFormat(self, value):
		if not self.current_port:
			self.current_port = config.av.videoport.value
		if self.current_port in ("YPbPr", "Scart-YPbPr"):
			eAVSwitch.getInstance().setColorFormat(3)
		elif self.current_port in ("RCA"):
			eAVSwitch.getInstance().setColorFormat(0)
		else:
			eAVSwitch.getInstance().setColorFormat(value)

	def setConfiguredMode(self):
		port = config.av.videoport.value
		if port not in config.av.videomode:
			print(f"[AVSwitch] current port: {port} not available, not setting videomode:{config.av.videomode}")
			return
		mode = config.av.videomode[port].value
		if mode not in config.av.videorate:
			print(f"[AVSwitch] current mode:{mode} not available in config.av.videorate:{config.av.videorate}")
			return
		rate = config.av.videorate[mode].value
		self.setMode(port, mode, rate)

	def setAspect(self, configElement):
		eAVSwitch.getInstance().setAspect(configElement.value, 1)
		print(f"[AVSwitch] setting aspect:{configElement.value}")

	def setWss(self, configElement):
		if not configElement.value:
			wss = "auto(4:3_off)"
		else:
			wss = "auto"
		print(f"[AVSwitch] setting wss:{wss} configElement.value:{configElement.value}")
		with open("/proc/stb/denc/0/wss", "w") as fd:
			fd.write(wss)

	def setPolicy43(self, configElement):
		print(f"[AVSwitch] setting policy43:{configElement.value}")
		eAVSwitch.getInstance().setPolicy43(configElement.value, 1)

	def setPolicy169(self, configElement):
		print(f"[AVSwitch] setting policy169:{configElement.value}")
		eAVSwitch.getInstance().setPolicy169(configElement.value, 1)

	def getOutputAspect(self):
		ret = (16, 9)
		port = config.av.videoport.value
		if port not in config.av.videomode:
			print(f"[AVSwitch] current port:{port} not available in config.av.videomode:{config.av.videomode} force 16:9")
		else:
			mode = config.av.videomode[port].value
			force_widescreen = self.isWidescreenMode(port, mode)
			is_widescreen = force_widescreen or config.av.aspect.value in ("16:9", "16:10")
			is_auto = config.av.aspect.value == "auto"
			if is_widescreen:
				if force_widescreen:
					pass
				else:
					aspect = {"16:9": "16:9", "16:10": "16:10"}[config.av.aspect.value]
					if aspect == "16:10":
						ret = (16, 10)
			elif is_auto:
				try:
					if "1" in open("/proc/stb/vmpeg/0/aspect", "r").read():  # 4:3
						return (4, 3)
				except (IOError, OSError):
					pass
			else:  # 4:3
				ret = (4, 3)
		return ret

	def getFramebufferScale(self):
		aspect = self.getOutputAspect()
		fb_size = getDesktop(0).size()
		return (aspect[0] * fb_size.height(), aspect[1] * fb_size.width())

	def getAspectRatioSetting(self):
		valstr = config.av.aspectratio.value
		if valstr == "4_3_letterbox":
			val = 0
		elif valstr == "4_3_panscan":
			val = 1
		elif valstr == "16_9":
			val = 2
		elif valstr == "16_9_always":
			val = 3
		elif valstr == "16_10_letterbox":
			val = 4
		elif valstr == "16_10_panscan":
			val = 5
		elif valstr == "16_9_letterbox":
			val = 6
		return val


iAVSwitch = AVSwitch()


def InitAVSwitch():
	config.av.yuvenabled = ConfigBoolean(default=True)
	colorformat_choices = {
		"cvbs": _("CVBS"),
		"rgb": _("RGB"),
		"svideo": _("S-Video")
	}
	# when YUV is not enabled, don't let the user select it
	if config.av.yuvenabled.value:
		colorformat_choices["yuv"] = _("YPbPr")
	config.av.colorformat = ConfigSelection(choices=colorformat_choices, default="rgb")
	config.av.aspectratio = ConfigSelection(choices={
		"4_3_letterbox": _("4:3 Letterbox"),
		"4_3_panscan": _("4:3 PanScan"),
		"16_9": _("16:9"),
		"16_9_always": _("16:9 always"),
		"16_10_letterbox": _("16:10 Letterbox"),
		"16_10_panscan": _("16:10 PanScan"),
		"16_9_letterbox": _("16:9 Letterbox")
	}, default="16_9")
	config.av.aspect = ConfigSelection(choices={
		"4:3": _("4:3"),
		"16:9": _("16:9"),
		"16:10": _("16:10"),
		"auto": _("Automatic")
	}, default="16:9")
	policy2_choices = {
		"letterbox": _("Letterbox"),					# TRANSLATORS: (aspect ratio policy: black bars on top/bottom) in doubt, keep english term.
		"panscan": _("Pan&scan"),					# TRANSLATORS: (aspect ratio policy: cropped content on left/right) in doubt, keep english term
		"scale": _("Just scale")					# TRANSLATORS: (aspect ratio policy: display as fullscreen, even if this breaks the aspect)
	}
	if path.exists("/proc/stb/video/policy2_choices"):
		f = open("/proc/stb/video/policy2_choices")
		if "auto" in f.readline():
			policy2_choices.update({"auto": _("Auto")})		# TRANSLATORS: (aspect ratio policy: always try to display as fullscreen, when there is no content (black bars) on left/right, even if this breaks the aspect.
		f.close()
	config.av.policy_169 = ConfigSelection(choices=policy2_choices, default="letterbox")
	policy_choices = {
		"panscan": _("Pillarbox"),					# TRANSLATORS: (aspect ratio policy: black bars on left/right) in doubt, keep english term.
		"letterbox": _("Pan&scan"),					# TRANSLATORS: (aspect ratio policy: cropped content on left/right) in doubt, keep english term
		# "nonlinear": _("Nonlinear"),					# TRANSLATORS: (aspect ratio policy: display as fullscreen, with stretching the left/right)
		"bestfit": _("Just scale")					# TRANSLATORS: (aspect ratio policy: display as fullscreen, even if this breaks the aspect)
	}
	if path.exists("/proc/stb/video/policy_choices"):
		f = open("/proc/stb/video/policy_choices")
		if "auto" in f.readline():
			policy_choices.update({"auto": _("Auto")})		# TRANSLATORS: (aspect ratio policy: always try to display as fullscreen, when there is no content (black bars) on left/right, even if this breaks the aspect.
		f.close()
	config.av.policy_43 = ConfigSelection(choices=policy_choices, default="panscan")
	config.av.tvsystem = ConfigSelection(choices={
		"pal": _("PAL"),
		"ntsc": _("NTSC"),
		"multinorm": _("multinorm")
	}, default="pal")
	config.av.wss = ConfigEnableDisable(default=True)
	config.av.generalAC3delay = ConfigSelectionNumber(-1000, 1000, 5, default=0)
	config.av.generalPCMdelay = ConfigSelectionNumber(-1000, 1000, 5, default=0)
	config.av.vcrswitch = ConfigEnableDisable(default=False)
	config.av.aspect.setValue("16:9")
	config.av.aspect.addNotifier(iAVSwitch.setAspect)
	config.av.wss.addNotifier(iAVSwitch.setWss)
	config.av.policy_43.addNotifier(iAVSwitch.setPolicy43)
	config.av.policy_169.addNotifier(iAVSwitch.setPolicy169)

	def setColorFormat(configElement):
		if config.av.videoport and config.av.videoport.value in ("YPbPr", "Scart-YPbPr"):
			iAVSwitch.setColorFormat(3)
		elif config.av.videoport and config.av.videoport.value in ("RCA"):
			iAVSwitch.setColorFormat(0)
		else:
			map = {
				"cvbs": 0,
				"rgb": 1,
				"svideo": 2,
				"yuv": 3
			}
			iAVSwitch.setColorFormat(map[configElement.value])
	config.av.colorformat.addNotifier(setColorFormat)

	def setAspectRatio(configElement):
		map = {
			"4_3_letterbox": 0,
			"4_3_panscan": 1,
			"16_9": 2,
			"16_9_always": 3,
			"16_10_letterbox": 4,
			"16_10_panscan": 5,
			"16_9_letterbox": 6
		}
		iAVSwitch.setAspectRatio(map[configElement.value])

	def readChoices(procx, choices, default):
		with open(procx, "r") as myfile:
			procChoices = myfile.read().strip()
		if procChoices:
			choiceslist = procChoices.split(" ")
			choices = [(item, _(item)) for item in choiceslist]
			default = choiceslist[0]
			# print("[AVSwitch][readChoices from Proc] choices=%s, default=%s" % (choices, default))
		return (choices, default)

	iAVSwitch.setInput("ENCODER")  # Init on startup.
	SystemInfo["ScartSwitch"] = eAVSwitch.getInstance().haveScartSwitch()

	if SystemInfo["Canedidchecking"]:
		def setEDIDBypass(configElement):
			open(SystemInfo["Canedidchecking"], "w").write("00000001" if configElement.value else "00000000")
		config.av.bypass_edid_checking = ConfigYesNo(default=False)
		config.av.bypass_edid_checking.addNotifier(setEDIDBypass)
	else:
		config.av.bypass_edid_checking = ConfigNothing()

	if SystemInfo["havecolorspace"]:
		def setHDMIColorspace(configElement):
			open(SystemInfo["havecolorspace"], "w").write(configElement.value)
		if SystemInfo["brand"] == "vuplus" and SystemInfo["HasMMC"]:
			choices = [
				("Edid(Auto)", _("Auto")),
				("Hdmi_Rgb", _("RGB")),
				("444", _("YCbCr444")),
				("422", _("YCbCr422")),
				("420", _("YCbCr420"))
			]
			default = "Edid(Auto)"
		else:
			choices = [("auto", _("Auto")),
						("rgb", _("RGB")),
						("420", _("420")),
						("422", _("422")),
						("444", _("444"))]
			default = "auto"
		if SystemInfo["havecolorspacechoices"] and SystemInfo["CanProc"]:
			f = "/proc/stb/video/hdmi_colorspace_choices"
			(choices, default) = readChoices(f, choices, default)
		config.av.hdmicolorspace = ConfigSelection(choices=choices, default=default)
		config.av.hdmicolorspace.addNotifier(setHDMIColorspace)
	else:
		config.av.hdmicolorspace = ConfigNothing()

	if SystemInfo["havecolorimetry"]:
		def setHDMIColorimetry(configElement):
			open(SystemInfo["havecolorimetry"], "w").write(configElement.value)
		choices = [
			("auto", _("auto")),
			("bt2020ncl", _("BT 2020 NCL")),
			("bt2020cl", _("BT 2020 CL")),
			("bt709", _("BT 709"))
		]
		default = "auto"
		if SystemInfo["havecolorimetrychoices"] and SystemInfo["CanProc"]:
			f = "/proc/stb/video/hdmi_colorimetry_choices"
			(choices, default) = readChoices(f, choices, default)
		config.av.hdmicolorimetry = ConfigSelection(choices=choices, default=default)
		config.av.hdmicolorimetry.addNotifier(setHDMIColorimetry)
	else:
		config.av.hdmicolorimetry = ConfigNothing()

	if SystemInfo["havehdmicolordepth"]:
		def setHdmiColordepth(configElement):
			open(SystemInfo["havehdmicolordepth"], "w").write(configElement.value)
		choices = [("auto", _("Auto")),
					("8bit", _("8bit")),
					("10bit", _("10bit")),
					("12bit", _("12bit"))]
		default = "auto"
		if SystemInfo["havehdmicolordepthchoices"] and SystemInfo["CanProc"]:
			f = "/proc/stb/video/hdmi_colordepth_choices"
			(choices, default) = readChoices(f, choices, default)
		config.av.hdmicolordepth = ConfigSelection(choices=choices, default=default)
		config.av.hdmicolordepth.addNotifier(setHdmiColordepth)
	else:
		config.av.hdmicolordepth = ConfigNothing()

	if SystemInfo["havehdmihdrtype"]:
		def setHdmiHdrType(configElement):
			try:
				with open(SystemInfo["havehdmihdrtype"], "w") as fd:
					fd.write(configElement.value)
			except (IOError, OSError):
				pass
		config.av.hdmihdrtype = ConfigSelection(choices={
			"auto": _("Auto"),
			"dolby": _("dolby"),
			"none": _("sdr"),
			"hdr10": _("hdr10"),
			"hlg": _("hlg")
		}, default="auto")
		config.av.hdmihdrtype.addNotifier(setHdmiHdrType)
	else:
		config.av.hdmihdrtype = ConfigNothing()

	if SystemInfo["HDRSupport"]:
		def setHlgSupport(configElement):
			open("/proc/stb/hdmi/hlg_support", "w").write(configElement.value)

		config.av.hlg_support = ConfigSelection(default="auto(EDID)", choices=[
			("auto(EDID)", _("controlled by HDMI")),
			("yes", _("force enabled")),
			("no", _("force disabled"))
		])
		config.av.hlg_support.addNotifier(setHlgSupport)

		def setHdr10Support(configElement):
			open("/proc/stb/hdmi/hdr10_support", "w").write(configElement.value)

		config.av.hdr10_support = ConfigSelection(default="auto(EDID)", choices=[
			("auto(EDID)", _("controlled by HDMI")),
			("yes", _("force enabled")),
			("no", _("force disabled"))
		])
		config.av.hdr10_support.addNotifier(setHdr10Support)

		def setDisable12Bit(configElement):
			open("/proc/stb/video/disable_12bit", "w").write(configElement.value)

		config.av.allow_12bit = ConfigSelection(default="0", choices=[
			("0", _("yes")),
			("1", _("no"))
		])
		config.av.allow_12bit.addNotifier(setDisable12Bit)

		def setDisable10Bit(configElement):
			open("/proc/stb/video/disable_10bit", "w").write(configElement.value)

		config.av.allow_10bit = ConfigSelection(default="0", choices=[
			("0", _("yes")),
			("1", _("no"))
		])
		config.av.allow_10bit.addNotifier(setDisable10Bit)

	if SystemInfo["Canaudiosource"]:
		def setAudioSource(configElement):
			try:
				with open(SystemInfo["Canaudiosource"], "w") as fd:
					fd.write(configElement.value)
			except (IOError, OSError):
				pass

		config.av.audio_source = ConfigSelection(choices={
			"pcm": _("PCM"),
			"spdif": _("SPDIF")
		}, default="pcm")
		config.av.audio_source.addNotifier(setAudioSource)
	else:
		config.av.audio_source = ConfigNothing()

	if SystemInfo["Can3DSurround"]:
		def set3DSurround(configElement):
			open(SystemInfo["Can3DSurround"], "w").write(configElement.value)
		choices = [
			("none", _("off")),
			("hdmi", _("HDMI")),
			("spdif", _("SPDIF")),
			("dac", _("DAC"))
		]
		default = "none"
		if SystemInfo["CanProc"]:
			f = "/proc/stb/audio/3d_surround_choices"
			(choices, default) = readChoices(f, choices, default)

		config.av.surround_3d = ConfigSelection(choices=choices, default=default)
		config.av.surround_3d.addNotifier(set3DSurround)
	else:
		config.av.surround_3d = ConfigNothing()

	if SystemInfo["Can3DSpeaker"]:
		def set3DPosition(configElement):
			open(SystemInfo["Can3DSpeaker"], "w").write(configElement.value)
		choices = [
			("center", _("center")),
			("wide", _("wide")),
			("extrawide", _("extra wide"))
		]
		default = "center"
		if SystemInfo["CanProc"]:
			f = "/proc/stb/audio/3d_surround_speaker_position_choices"
			(choices, default) = readChoices(f, choices, default)
		config.av.surround_3d_speaker = ConfigSelection(choices=choices, default=default)
		config.av.surround_3d_speaker.addNotifier(set3DPosition)
	else:
		config.av.surround_3d_speaker = ConfigNothing()

	if SystemInfo["CanAutoVolume"]:
		def setAutoVolume(configElement):
			open("/proc/stb/audio/avl", "w").write(configElement.value)
		choices = [
			("none", _("off")),
			("hdmi", _("HDMI")),
			("spdif", _("SPDIF")),
			("dac", _("DAC"))
		]
		default = "none"
		if SystemInfo["CanProc"]:
			f = "/proc/stb/audio/avl_choices"
			(choices, default) = readChoices(f, choices, default)
		config.av.autovolume = ConfigSelection(choices=choices, default=default)
		config.av.autovolume.addNotifier(setAutoVolume)
	else:
		config.av.autovolume = ConfigNothing()
	if SystemInfo["supportPcmMultichannel"]:
		def setPCMMultichannel(configElement):
			open(SystemInfo["supportPcmMultichannel"], "w").write(configElement.value and "enable" or "disable")
		config.av.pcm_multichannel = ConfigYesNo(default=False)
		config.av.pcm_multichannel.addNotifier(setPCMMultichannel)

	if SystemInfo["CanDownmixAC3"]:
		def setAC3Downmix(configElement):
			open("/proc/stb/audio/ac3", "w").write(configElement.value)
			if SystemInfo.get("supportPcmMultichannel", False) and configElement.value == "passthrough":
				SystemInfo["CanPcmMultichannel"] = True
			else:
				SystemInfo["CanPcmMultichannel"] = False
				if SystemInfo["supportPcmMultichannel"]:
					config.av.pcm_multichannel.setValue(False)
		choices = [
			("downmix", _("Downmix")),
			("passthrough", _("Passthrough"))
		]
		default = "downmix"
		if SystemInfo["CanProc"]:
			f = "/proc/stb/audio/ac3_choices"
			(choices, default) = readChoices(f, choices, default)
		config.av.downmix_ac3 = ConfigSelection(choices=choices, default=default)
		config.av.downmix_ac3.addNotifier(setAC3Downmix)

	if SystemInfo["CanAC3Transcode"]:
		def setAC3plusTranscode(configElement):
			open("/proc/stb/audio/ac3plus", "w").write(configElement.value)
		choices = [
			("use_hdmi_caps", _("controlled by HDMI")),
			("force_ac3", _("convert to AC3"))
		]
		default = "force_ac3"
		if SystemInfo["CanProc"]:
			f = "/proc/stb/audio/ac3plus_choices"
			(choices, default) = readChoices(f, choices, default)
		config.av.transcodeac3plus = ConfigSelection(choices=choices, default=default)
		config.av.transcodeac3plus.addNotifier(setAC3plusTranscode)

	if SystemInfo["CanDownmixDTS"]:
		def setDTSDownmix(configElement):
			open("/proc/stb/audio/dts", "w").write(configElement.value)
		choices = [
			("downmix", _("Downmix")),
			("passthrough", _("Passthrough"))
		]
		default = "downmix"
		if SystemInfo["CanProc"]:
			f = "/proc/stb/audio/dts_choices"
			(choices, default) = readChoices(f, choices, default)
		config.av.downmix_dts = ConfigSelection(choices=choices, default=default)
		config.av.downmix_dts.addNotifier(setDTSDownmix)

	if SystemInfo["CanDTSHD"]:
		def setDTSHD(configElement):
			open("/proc/stb/audio/dtshd", "w").write(configElement.value)
		choices = [
			("downmix", _("Downmix")),
			("force_dts", _("convert to DTS")),
			("use_hdmi_caps", _("controlled by HDMI")),
			("multichannel", _("convert to multi-channel PCM")),
			("hdmi_best", _("use best / controlled by HDMI"))
		]
		default = "downmix"
		if SystemInfo["CanProc"]:
			f = "/proc/stb/audio/dtshd_choices"
			(choices, default) = readChoices(f, choices, default)

		config.av.dtshd = ConfigSelection(choices=choices, default=default)
		config.av.dtshd.addNotifier(setDTSHD)

	if SystemInfo["CanDownmixAAC"]:
		def setAACDownmix(configElement):
			open("/proc/stb/audio/aac", "w").write(configElement.value)
		choices = [
			("downmix", _("Downmix")),
			("passthrough", _("Passthrough"))
		]
		default = "downmix"
		if SystemInfo["CanProc"]:
			f = "/proc/stb/audio/aac_choices"
			(choices, default) = readChoices(f, choices, default)

		config.av.downmix_aac = ConfigSelection(choices=choices, default=default)
		config.av.downmix_aac.addNotifier(setAACDownmix)

	if SystemInfo["CanDownmixAACPlus"]:
		def setAACDownmixPlus(configElement):
			open("/proc/stb/audio/aacplus", "w").write(configElement.value)
		choices = [
			("downmix", _("Downmix")),
			("passthrough", _("Passthrough")),
			("multichannel", _("convert to multi-channel PCM")),
			("force_ac3", _("convert to AC3")),
			("force_dts", _("convert to DTS")),
			("use_hdmi_cacenter", _("use_hdmi_cacenter")),
			("wide", _("wide")),
			("extrawide", _("extrawide"))
		]
		default = "downmix"
		if SystemInfo["CanProc"]:
			f = "/proc/stb/audio/aacplus_choices"
			(choices, default) = readChoices(f, choices, default)

		config.av.downmix_aacplus = ConfigSelection(choices=choices, default=default)
		config.av.downmix_aacplus.addNotifier(setAACDownmixPlus)

	if SystemInfo["CanAACTranscode"]:
		def setAACTranscode(configElement):
			open("/proc/stb/audio/aac_transcode", "w").write(configElement.value)
		choices = [
			("off", _("off")),
			("ac3", _("AC3")),
			("dts", _("DTS"))
		]
		default = "off"
		if SystemInfo["CanProc"]:
			f = "/proc/stb/audio/aac_transcode_choices"
			(choices, default) = readChoices(f, choices, default)

		config.av.transcodeaac = ConfigSelection(choices=choices, default=default)
		config.av.transcodeaac.addNotifier(setAACTranscode)
	else:
		config.av.transcodeaac = ConfigNothing()

	if SystemInfo["CanWMAPRO"]:
		def setWMAPRO(configElement):
			open("/proc/stb/audio/wmapro", "w").write(configElement.value)
		choices = [
			("downmix", _("Downmix")),
			("passthrough", _("Passthrough")),
			("multichannel", _("convert to multi-channel PCM")),
			("hdmi_best", _("use best / controlled by HDMI"))
		]
		default = "downmix"
		if SystemInfo["CanProc"]:
			f = "/proc/stb/audio/wmapro_choices"
			(choices, default) = readChoices(f, choices, default)

		config.av.wmapro = ConfigSelection(choices=choices, default=default)
		config.av.wmapro.addNotifier(setWMAPRO)

	if SystemInfo["CanBTAudio"]:
		def setBTAudio(configElement):
			open("/proc/stb/audio/btaudio", "w").write(configElement.value)
		choices = [
			("off", _("Off")),
			("on", _("On"))
		]
		default = "off"

		if SystemInfo["CanProc"]:
			f = "/proc/stb/audio/btaudio_choices"
			(choices, default) = readChoices(f, choices, default)

		config.av.btaudio = ConfigSelection(choices=choices, default="off")
		config.av.btaudio.addNotifier(setBTAudio)
	else:
		config.av.btaudio = ConfigNothing()

	if SystemInfo["CanBTAudioDelay"]:
		def setBTAudioDelay(configElement):
			open(SystemInfo["CanBTAudioDelay"], "w").write(format(configElement.value * 90, "x"))
		config.av.btaudiodelay = ConfigSelectionNumber(-1000, 1000, 5, default=0)
		config.av.btaudiodelay.addNotifier(setBTAudioDelay)
	else:
		config.av.btaudiodelay = ConfigNothing()

	if SystemInfo["haveboxmode"]:
		def setBoxmode(configElement):
			try:
				open(SystemInfo["haveboxmode"], "w").write(configElement.value)
			except (IOError, OSError):
				pass
		config.av.boxmode = ConfigSelection(choices={
			"12": _("PIP enabled, no HDR"),
			"1": _("HDR, 12bit 4:2:0/4:2:2, no PIP")
		}, default="12")
		config.av.boxmode.addNotifier(setBoxmode)
	else:
		config.av.boxmode = ConfigNothing()

	if SystemInfo["HasScaler_sharpness"]:
		def setScaler_sharpness(configElement):
			myval = int(configElement.value)
			try:
				print("[AVSwitch] setting scaler_sharpness to: %0.8X" % myval)
				open("/proc/stb/vmpeg/0/pep_scaler_sharpness", "w").write("%0.8X" % myval)
				open("/proc/stb/vmpeg/0/pep_apply", "w").write("1")
			except (IOError, OSError):
				print("[AVSwitch] couldn't write pep_scaler_sharpness")
		if SystemInfo["boxtype"] in ("gbquad", "gbquadplus"):
			config.av.scaler_sharpness = ConfigSlider(default=5, limits=(0, 26))
		else:
			config.av.scaler_sharpness = ConfigSlider(default=13, limits=(0, 26))
		config.av.scaler_sharpness.addNotifier(setScaler_sharpness)
	else:
		config.av.scaler_sharpness = NoSave(ConfigNothing())
	config.av.edid_override = ConfigYesNo(default=False)
	iAVSwitch.setConfiguredMode()


class VideomodeHotplug:
	def __init__(self):
		pass

	def start(self):
		iAVSwitch.on_hotplug.append(self.hotplug)

	def stop(self):
		iAVSwitch.on_hotplug.remove(self.hotplug)

	def hotplug(self, what):
		print("[AVSwitch][VideomodeHotplug] hotplug detected on port '%s'" % what)
		port = config.av.videoport.value
		mode = config.av.videomode[port].value
		rate = config.av.videorate[mode].value

		if not iAVSwitch.isModeAvailable(port, mode, rate):
			print("[AVSwitch][VideomodeHotplug] mode %s/%s/%s went away!" % (port, mode, rate))
			modelist = iAVSwitch.getModeList(port)
			if not len(modelist):
				print("[AVSwitch][VideomodeHotplug] sorry, no other mode is available (unplug?). Doing nothing.")
				return
			mode = modelist[0][0]
			rate = modelist[0][1]
			print("[AVSwitch][VideomodeHotplug] setting %s/%s/%s" % (port, mode, rate))
			iAVSwitch.setMode(port, mode, rate)


hotplug = None


def startHotplug():
	global hotplug
	hotplug = VideomodeHotplug()
	hotplug.start()


def stopHotplug():
	global hotplug
	hotplug.stop()


def InitiVideomodeHotplug(**kwargs):
	startHotplug()
