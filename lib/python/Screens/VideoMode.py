from os import path
from enigma import iPlayableService, iServiceInformation, eTimer, eServiceCenter, eServiceReference, eDVBDB, eAVSwitch

from Components.AVSwitch import iAVSwitch as iAV
from Components.config import config, getConfigListEntry
from Components.Label import Label
from Components.ServiceEventTracker import ServiceEventTracker
from Components.SystemInfo import SystemInfo
from Screens.ChannelSelection import FLAG_IS_DEDICATED_3D
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Setup import Setup
from Tools.Directories import isPluginInstalled
from Tools.HardwareInfo import HardwareInfo

resolutionlabel = None
previous = None
isDedicated3D = False
videomode = "/proc/stb/video/videomode"


def getConfig_videomode(getmode, getrate):
	port = config.av.videoport.value
	mode = getmode[port].value
	res = mode.replace("p30", "p")[:-1]
	pol = mode.replace("p30", "p")[-1:]
	rate = getrate[mode].value.replace("Hz", "")
	return port, mode, res, pol, rate


class VideoSetup(Setup):
	def __init__(self, session):
		Setup.__init__(self, session, None)
		self.title = _("Video & Audio Settings")
		self.onShow.append(self.startHotplug)
		self.onHide.append(self.stopHotplug)
		self.createSetup()
		self.grabLastGoodMode()

	def startHotplug(self):
		iAV.on_hotplug.append(self.createSetup)

	def stopHotplug(self):
		iAV.on_hotplug.remove(self.createSetup)

	def createSetup(self):
		level = config.usage.setup_level.index
		self.list = [
			getConfigListEntry(_("Video output"), config.av.videoport, _("Configures which video output connector will be used."))
		]
		if config.av.videoport.value == "Scart":
			config.av.fixres.value = "disabled"
		# if we have modes for this port:
		if config.av.videoport.value in config.av.videomode or config.av.videoport.value == "Scart":
			# add mode- and rate-selection:
			self.list.append(getConfigListEntry(pgettext("Video output mode", "Mode"), config.av.videomode[config.av.videoport.value], _("This option configures the video output mode (or resolution).")))
			if config.av.videomode[config.av.videoport.value].value == "PC":
				self.list.append(getConfigListEntry(_("Resolution"), config.av.videorate[config.av.videomode[config.av.videoport.value].value], _("This option configures the screen resolution in PC output mode.")))
			elif config.av.videoport.value != "Scart":
				self.list.append(getConfigListEntry(_("Refresh rate"), config.av.videorate[config.av.videomode[config.av.videoport.value].value], _("Configure screen refresh rate. Multi & Auto rates depend on the source 24/50/60Hz")))
		port = config.av.videoport.value
		mode = config.av.videomode[port].value if port in config.av.videomode else None
		# some modes (720p, 1080i) are always widescreen. Don't let the user select something here, "auto" is not what he wants.
		force_wide = iAV.isWidescreenMode(port, mode)
		# if not force_wide:
		# 	self.list.append(getConfigListEntry(_("Aspect ratio"), config.av.aspect, _("Configure the aspect ratio of the screen.")))
		if force_wide or config.av.aspect.value in ("16:9", "16:10"):
			self.list.extend((
				getConfigListEntry(_("Display 4:3 content as"), config.av.policy_43, _("When the content has an aspect ratio of 4:3, choose whether to scale/stretch the picture.")),
				getConfigListEntry(_("Display >16:9 content as"), config.av.policy_169, _("When the content has an aspect ratio of 16:9, choose whether to scale/stretch the picture."))
			))
		elif config.av.aspect.value == "4:3":
			self.list.append(getConfigListEntry(_("Display 16:9 content as"), config.av.policy_169, _("When the content has an aspect ratio of 16:9, choose whether to scale/stretch the picture.")))

		if config.av.videoport.value == "Scart":
			self.list.append(getConfigListEntry(_("Color format"), config.av.colorformat, _("Configure which color format should be used on the SCART output.")))
			if level >= 1:
				self.list.append(getConfigListEntry(_("WSS on 4:3"), config.av.wss, _("When enabled, content with an aspect ratio of 4:3 will be stretched to fit the screen.")))
				if SystemInfo["ScartSwitch"]:
					self.list.append(getConfigListEntry(_("Auto scart switching"), config.av.vcrswitch, _("When enabled, your receiver will detect activity on the VCR SCART input.")))
		if SystemInfo["havecolorspace"]:
			self.list.append(getConfigListEntry(_("HDMI Colorspace"), config.av.hdmicolorspace, _("Change Colorspace setting - this may cause unexpected results or black screen")))
		if SystemInfo["havecolorimetry"]:
			self.list.append(getConfigListEntry(_("HDMI Colorimetry"), config.av.hdmicolorimetry, _("Change the Colorimetry for HDR - this may cause unexpected results or black screen")))
		if SystemInfo["havehdmicolordepth"]:
			self.list.append(getConfigListEntry(_("HDMI Color depth"), config.av.hdmicolordepth, _("Change the Colordepth for UHD - this may cause unexpected results or black screen")))
		if SystemInfo["havehdmihdrtype"]:
			self.list.append(getConfigListEntry(_("HDMI HDR Type"), config.av.hdmihdrtype, _("Enable or disable to force HDR Modes for UHD")))
		if SystemInfo["HDRSupport"]:
			self.list.append(getConfigListEntry(_("HLG Support"), config.av.hlg_support, _("Enable or disable to force HLG Modes for UHD")))
			self.list.append(getConfigListEntry(_("HDR10 Support"), config.av.hdr10_support, _("Enable or disable to force HDR10 Modes for UHD")))
			self.list.append(getConfigListEntry(_("Allow 12bit"), config.av.allow_12bit, _("Enable or disable the 12 Bit Color Mode")))
			self.list.append(getConfigListEntry(_("Allow 10bit"), config.av.allow_10bit, _("Enable or disable the 10 Bit Color Mode")))
		if config.av.videoport.value in ("HDMI", "YPbPr", "Scart-YPbPr") and not isPluginInstalled("AutoResolution"):
			self.list.append(getConfigListEntry(_("Force resolution override*"), config.av.fixres, _("Only use if you must force the output resolution - otherwise select 'Refresh Rate = auto'")))
			if config.av.fixres.value in ("all", "hd"):
				self.list.append(getConfigListEntry(_("Force de-interlace"), config.av.fixres_deinterlace, _("If enabled the video will always be de-interlaced.")))
				self.list.append(getConfigListEntry(_("Show resolution label"), config.av.fixres_label_timeout, _("Allows you to adjust the amount of time the resolution infomation display on screen.")))
				if config.av.fixres.value in ("hd"):
					self.list.append(getConfigListEntry(_("Show SD as"), config.av.fixres_sd, _("This option allows you to choose how to display standard defintion video on your TV.")))
				self.list.append(getConfigListEntry(_("Show 480/576p 24fps as"), config.av.fixres_480p24, _("This option allows you to choose how to display SD progressive 24Hz on your TV. (as not all TV's support these resolutions)")))
				self.list.append(getConfigListEntry(_("Show 720p 24fps as"), config.av.fixres_720p24, _("This option allows you to choose how to display 720p 24Hz on your TV. (as not all TVs support these resolutions)")))
				self.list.append(getConfigListEntry(_("Show 1080p 24fps as"), config.av.fixres_1080p24, _("This option allows you to choose how to display 1080p 24Hz on your TV. (as not all TVs support these resolutions)")))
				self.list.append(getConfigListEntry(_("Show 1080p 25fps as"), config.av.fixres_1080p25, _("This option allows you to choose how to display 1080p 25Hz on your TV. (as not all TVs support these resolutions)")))
				self.list.append(getConfigListEntry(_("Show 1080p 30fps as"), config.av.fixres_1080p30, _("This option allows you to choose how to display 1080p 30Hz on your TV. (as not all TVs support these resolutions)")))
				if "2160p24" in SystemInfo["AvailableVideomodes"]:
					self.list.append(getConfigListEntry(_("Show 2160p 24fps as"), config.av.fixres_2160p24, _("This option allows you to choose how to display 2160p 24Hz on your TV. (as not all TVs support these resolutions)")))
					self.list.append(getConfigListEntry(_("Show 2160p 25fps as"), config.av.fixres_2160p25, _("This option allows you to choose how to display 2160p 25Hz on your TV. (as not all TVs support these resolutions)")))
					self.list.append(getConfigListEntry(_("Show 2160p 30fps as"), config.av.fixres_2160p30, _("This option allows you to choose how to display 2160p 30Hz on your TV. (as not all TVs support these resolutions)")))
		if config.av.fixres.value in ("all", "hd") and config.av.videorate[config.av.videomode[config.av.videoport.value].value].value == "multi":
			self.list.append(getConfigListEntry(_("Delay time"), config.av.fixres_delay, _("Set the time before checking video source for resolution/refresh rate infomation.")))
		if level >= 1:
			if SystemInfo["CanDownmixAC3"]:
				self.list.append(getConfigListEntry(_("AC3 downmix"), config.av.downmix_ac3, _("Choose whether multi channel ac3 sound tracks should be downmixed to stereo.")))
			if SystemInfo["CanDownmixDTS"]:
				self.list.append(getConfigListEntry(_("DTS downmix"), config.av.downmix_dts, _("Choose whether multi channel dts sound tracks should be downmixed to stereo.")))
			if SystemInfo["CanDownmixAACPlus"]:
				self.list.append(getConfigListEntry(_("AAC+ downmix"), config.av.downmix_aacplus, _("Choose whether multi channel aac+ sound tracks should be downmixed to stereo.")))
			elif SystemInfo["CanDownmixAAC"]:
				self.list.append(getConfigListEntry(_("AAC downmix"), config.av.downmix_aac, _("Choose whether multi channel aac sound tracks should be downmixed to stereo.")))
			if SystemInfo["CanAC3Transcode"]:
				self.list.append(getConfigListEntry(_("AC3 transcoding"), config.av.transcodeac3plus, None))
			if SystemInfo["CanAACTranscode"]:
				self.list.append(getConfigListEntry(_("AAC transcoding"), config.av.transcodeaac, _("Choose whether AAC sound tracks should be transcoded.")))
			if SystemInfo["CanDTSHD"]:
				self.list.append(getConfigListEntry(_("DTS-HD HR/DTS-HD MA/DTS"), config.av.dtshd, ("Choose whether multi channel DTSHD sound tracks should be downmixed or transcoded..")))
			if SystemInfo["CanWMAPRO"]:
				self.list.append(getConfigListEntry(_("WMA Pro downmix"), config.av.wmapro, _("Choose whether WMA Pro sound tracks should be downmixed.")))
			if SystemInfo["CanPcmMultichannel"]:
				self.list.append(getConfigListEntry(_("PCM Multichannel"), config.av.pcm_multichannel, _("Choose whether multi channel sound tracks should be output as PCM.")))
			self.list.extend((
				getConfigListEntry(_("General AC3 delay"), config.av.generalAC3delay, _("This option configures the general audio delay of Dolby Digital sound tracks.")),
				getConfigListEntry(_("General PCM delay"), config.av.generalPCMdelay, _("This option configures the general audio delay of stereo sound tracks."))
			))
			if SystemInfo["CanBTAudio"]:
				self.list.append(getConfigListEntry(_("Enable Bluetooth Audio"), config.av.btaudio, _("This option allows you to switch audio to bluetooth speakers.")))
			if SystemInfo["CanBTAudioDelay"]:
				self.list.append(getConfigListEntry(_("General Bluetooth Audio delay"), config.av.btaudiodelay, _("This option configures the general audio delay for bluetooth speakers.")))
			if SystemInfo["Can3DSurround"]:
				self.list.append(getConfigListEntry(_("3D Surround"), config.av.surround_3d, _("This option allows you to enable 3D Surround Sound for an output.")))
			if SystemInfo["Can3DSpeaker"] and config.av.surround_3d.value != "none":
				self.list.append(getConfigListEntry(_("3D Surround Speaker Position"), config.av.surround_3d_speaker, _("This option allows you to change the virtual loudspeaker position.")))
			if SystemInfo["CanAutoVolume"]:
				self.list.append(getConfigListEntry(_("Auto Volume Level"), config.av.autovolume, _("This option configures output for Auto Volume Level.")))
			if SystemInfo["Canedidchecking"]:
				self.list.append(getConfigListEntry(_("Bypass HDMI EDID Check"), config.av.bypass_edid_checking, _("This option allows you to bypass HDMI EDID check")))
		if SystemInfo["haveboxmode"]:
			self.list.append(getConfigListEntry(_("Video Chip Mode*"), config.av.boxmode, _("Choose between High Dynamic Range (HDR) or Picture in Picture (PIP). Both are not possible at the same time. A FULL REBOOT is required for it to take effect")))
		# if not isinstance(config.av.scaler_sharpness, ConfigNothing):
		# 	self.list.append(getConfigListEntry(_("Scaler sharpness"), config.av.scaler_sharpness, _("This option configures the picture sharpness.")))
		self["config"].list = self.list
		if config.usage.sort_settings.value:
			self["config"].list.sort(key=lambda x: x[0])

	def confirm(self, confirmed):
		if not confirmed:
			config.av.videoport.setValue(self.last_good[0])
			config.av.videomode[self.last_good[0]].setValue(self.last_good[1])
			config.av.videorate[self.last_good[1]].setValue(self.last_good[2])
			iAV.setMode(*self.last_good)
		else:
			Setup.keySave(self)

	def grabLastGoodMode(self):
		port = config.av.videoport.value
		mode = config.av.videomode[port].value
		rate = config.av.videorate[mode].value
		self.last_good = (port, mode, rate)

	def keySave(self):
		port = config.av.videoport.value
		mode = config.av.videomode[port].value
		rate = config.av.videorate[mode].value
		if (port, mode, rate) != self.last_good:
			iAV.setMode(port, mode, rate)
			self.session.openWithCallback(self.confirm, MessageBox, _("Is this video mode ok?"), MessageBox.TYPE_YESNO, timeout=20, default=False)
		else:
			Setup.keySave(self)


class forceVideoModeLabel(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self["content"] = Label()
		self["restxt"] = Label()
		self.hideTimer = eTimer()
		self.hideTimer.callback.append(self.hide)
		self.onShow.append(self.hide_me)

	def hide_me(self):
		idx = config.av.fixres_label_timeout.index
		if idx:
			idx += 4
			self.hideTimer.start(idx * 1000, True)


def applySettings(mode=config.osd.threeDmode.value, znorm=int(config.osd.threeDznorm.value)):
	global previous, isDedicated3D
	mode = isDedicated3D and mode == "auto" and "sidebyside" or mode
	mode == "3dmode" in SystemInfo["3DMode"] and mode or mode == "sidebyside" and "sbs" or mode == "topandbottom" and "tab" or "off"
	if previous != (mode, znorm):
		try:
			open(SystemInfo["3DMode"], "w").write(mode)
			open(SystemInfo["3DZNorm"], "w").write("%d" % znorm)
			previous = (mode, znorm)
		except Exception:
			return


class forceVideoMode(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		print("[VideoMode][forceVideoMode] Entered")
		self.current3dmode = config.osd.threeDmode.value
		self.__event_tracker = ServiceEventTracker(screen=self, eventmap={
			iPlayableService.evStart: self.__evStart,
			iPlayableService.evVideoSizeChanged: self.VideoChanged,
			iPlayableService.evVideoProgressiveChanged: self.VideoChanged,
			iPlayableService.evVideoFramerateChanged: self.VideoChanged,
			# iPlayableService.evBuffering: self.evBuffering,
			# iPlayableService.evEnd: self.VideoChanged,
			# iPlayableService.evSeekableStatusChanged: self.VideoChanged,
			# iPlayableService.evCuesheetChanged: self.VideoChanged,
			# iPlayableService.evUpdatedInfo: self.VideoChanged,
			# iPlayableService.evUpdatedEventInfo: self.evUpdatedEventInfo,
			# iPlayableService.evEOF: self.evEOF,
			# iPlayableService.evSOF: self.evSOF,
			# iPlayableService.evGstreamerPlayStarted: self.evGstreamerPlayStarted,

		})

		self.firstrun = True
		self.delay = False
		self.bufferfull = True
		self.detecttimer = eTimer()
		self.detecttimer.callback.append(self.VideoChangeDetect)

	def checkIfDedicated3D(self):
		print("[VideoMode][checkIfDedicated3D] Entered")
		service = self.session.nav.getCurrentlyPlayingServiceReference()
		servicepath = service and service.getPath()
		if servicepath and servicepath.startswith("/"):
			if service.toString().startswith("1:"):
				info = eServiceCenter.getInstance().info(service)
				service = info and info.getInfoString(service, iServiceInformation.sServiceref)
				return service and eDVBDB.getInstance().getFlag(eServiceReference(service)) & FLAG_IS_DEDICATED_3D == FLAG_IS_DEDICATED_3D and "sidebyside"
			else:
				return ".3d." in servicepath.lower() and "sidebyside" or ".tab." in servicepath.lower() and "topandbottom"
		service = self.session.nav.getCurrentService()
		info = service and service.info()
		return info and info.getInfo(iServiceInformation.sIsDedicated3D) == 1 and "sidebyside"

	def __evStart(self):
		if config.osd.threeDmode.value == "auto":
			global isDedicated3D
			isDedicated3D = self.checkIfDedicated3D()
			if isDedicated3D:
				applySettings(isDedicated3D)
			else:
				applySettings()
		self.VideoChanged()

	def BufferInfo(self):
		bufferInfo = self.session.nav.getCurrentService().streamed().getBufferCharge()
		if bufferInfo[0] > 98:
			self.bufferfull = True
			self.VideoChanged()
		else:
			self.bufferfull = False

	def BufferInfoStop(self):
		self.bufferfull = True

	def VideoChanged(self):
		if config.av.fixres.value == "disabled":
			print("[VideoMode] autoresolution is disabled - resolution not changed !")
			return
		else:
			print("[VideoMode][VideoChanged] Entered")
			if self.session.nav.getCurrentlyPlayingServiceReference() and not self.session.nav.getCurrentlyPlayingServiceReference().toString().startswith("4097:"):
				delay = config.av.fixres_delay.value
			else:
				delay = config.av.fixres_delay.value * 2
			if not self.detecttimer.isActive() and not self.delay:
				self.delay = True
			else:
				self.delay = True
				self.detecttimer.stop()

			self.detecttimer.start(delay)

	def VideoChangeDetect(self):
		print("[VideoMode][VideoChangeDetect] Entered")
		global resolutionlabel
		avSwitch = eAVSwitch.getInstance()
		config_port, config_mode, config_res, config_pol, config_rate = getConfig_videomode(config.av.videomode, config.av.videorate)
		current_mode = avSwitch.getVideoMode("")
		if current_mode.upper() in ("PAL", "NTSC"):
			current_mode = current_mode.upper()
		print(f"[VideoMode][VideoChangeDetect]2 current_mode:{current_mode} config_port:{config_port}, config_mode:{config_mode}, config_res:{config_res}, config_pol:{config_pol}, config_rate:{config_rate}")

		video_height = avSwitch.getResolutionY(0)
		video_width = avSwitch.getResolutionX(0)
		video_pol = "p" if avSwitch.getProgressive() else "i"
		video_rate = avSwitch.getFrameRate(0)
		print(f"[VideoMode][VideoChangeDetect]1 video_height:{video_height}, video_width:{video_width}, video_pol:{video_pol}, video_rate:{video_rate}")
		if not video_height or not video_width or not video_pol or not video_rate:
			info = None if self.session.nav.getCurrentService() is None else self.session.nav.getCurrentService().info()
			if info:
				video_height = int(info.getInfo(iServiceInformation.sVideoHeight))
				video_width = int(info.getInfo(iServiceInformation.sVideoWidth))
				video_pol = ("i", "p")[info.getInfo(iServiceInformation.sProgressive)]
				video_rate = int(info.getInfo(iServiceInformation.sFrameRate))
				print(f"[VideoMode][VideoChangeDetect]2 have info - video_height:{video_height}, video_width:{video_width}, video_pol:{video_pol}, video_rate:{video_rate}")
		if video_height and video_width and video_pol and video_rate:
			resolutionlabel["content"].setText(_("Video content: %ix%i%s %iHz") % (video_width, video_height, video_pol, (video_rate + 500) // 1000))
			if (1 < video_width <= 1024) and video_height <= 480 and video_rate in (23976, 24000, 25000, 29970, 50000, 59940):
				new_res = "480"
			elif (1 < video_width <= 1024) and video_height <= 576 and video_rate in (23976, 24000, 25000, 50000):
				new_res = "576"
			elif (video_width == 1280) and video_height <= 720:
				new_res = "720"
			elif (video_width == 1920) and video_height <= 1080:
				new_res = "1080"
			elif (video_width == 3840) and video_height > 1080:
				new_res = "2160"
			else:
				print(f"[VideoMode][VideoChangeDetect]new_res = config_res:{config_res}")
				new_res = config_res
			print(f"[VideoMode][VideoChangeDetect]new_res:{new_res}, video_width:{video_width}, video_height:{video_height}, video_pol:{video_pol}, video_rate:{video_rate}")
			if video_rate != -1:
				print(f"[VideoMode][VideoChangeDetect]video_rate:{video_rate}")
				if video_rate == 25000:
					new_rate = 50000
				elif video_rate == 59940 or (video_rate == 29970 and video_pol == "i") or (video_rate == 29970 and video_pol == "p" and config.av.fixres.value == "disabled"):
					new_rate = 60000
				elif video_rate == 23976:
					new_rate = 24000
				elif video_rate == 29970:
					new_rate = 30000
				else:
					new_rate = video_rate
				print(f"[VideoMode][VideoChangeDetect]new_rate:{new_rate} = video_rate:{video_rate}")
				new_rate = str((new_rate + 500) // 1000)
			else:
				print(f"[VideoMode][VideoChangeDetect]new_rate = config_rate:{config_rate}")
				new_rate = config_rate
			new_pol = str(video_pol) if video_pol != -1 else config_pol
			write_mode = new_mode = None
			print(f"[VideoMode][VideoChangeDetect] new_pol:{new_pol} video_pol:{video_pol} config_pol:{config_pol} config_mode:{config_mode} config.av.fixres.value:{config.av.fixres.value}")
			if config_mode in ("PAL", "NTSC"):
				write_mode = config_mode

			elif config.av.fixres.value == "all" or (config.av.fixres.value == "hd" and int(new_res) >= 720):
				print(f"[VideoMode][VideoChangeDetect] config.av.fixres.value = all or HD:{config.av.fixres.value}")
				if (config.av.fixres_deinterlace.value and HardwareInfo().is_nextgen()) or (config.av.fixres_deinterlace.value and not HardwareInfo().is_nextgen() and int(new_res) <= 720):
					new_pol = new_pol.replace("i", "p")
				print(f"[VideoMode][VideoChangeDetect] new_res + new_pol + new_rate: {new_res + new_pol + new_rate}")
				if new_res + new_pol + new_rate in SystemInfo["AvailableVideomodes"]:
					new_mode = new_res + new_pol + new_rate
					print(f"[VideoMode][VideoChangeDetect]1 new_mode:{new_mode}")
					if new_mode == "480p24" or new_mode == "576p24":
						new_mode = config.av.fixres_480p24.value
					if new_mode == "720p24":
						new_mode = config.av.fixres_720p24.value
					if new_mode == "1080p24":
						new_mode = config.av.fixres_1080p24.value
					if new_mode == "1080p25":
						new_mode = config.av.fixres_1080p25.value
					if new_mode == "1080p30":
						new_mode = config.av.fixres_1080p30.value
					if new_mode == "2160p24":
						new_mode = config.av.fixres_2160p24.value
					if new_mode == "2160p25" or new_mode == "2160p50":
						new_mode = config.av.fixres_2160p25.value
					if new_mode == "2160p30" or new_mode == "2160p60" or new_mode == "2160p":
						new_mode = config.av.fixres_2160p30.value
				elif new_res + new_pol in SystemInfo["AvailableVideomodes"]:
					new_mode = new_res + new_pol
					print(f"[VideoMode][VideoChangeDetect]2 new_mode:{new_mode}")
					if new_mode == "2160p30" or new_mode == "2160p60" or new_mode == "2160p":
						new_mode = config.av.fixres_2160p30.value
				else:
					new_mode = config_mode + new_rate
					print(f"[VideoMode][VideoChangeDetect]3 new_mode:{new_mode}")
				write_mode = new_mode
				print(f"[VideoMode][VideoChangeDetect]4 write_mode:{write_mode}, new_mode:{new_mode}")
			elif config.av.fixres.value == "hd" and int(new_res) <= 576:
				print("f[VideoMode][VideoChangeDetect] config.av.fixres.value = HD and less than 720:{config.av.fixres.value}")
				if (config.av.fixres_deinterlace.value and HardwareInfo().is_nextgen()) or (config.av.fixres_deinterlace.value and not HardwareInfo().is_nextgen() and not config.av.fixres_sd.value == "1080i"):
					new_mode = config.av.fixres_sd.value.replace("i", "p") + new_rate
				else:
					if new_pol in "p":
						new_mode = config.av.fixres_sd.value.replace("i", "p") + new_rate
					else:
						new_mode = config.av.fixres_sd.value + new_rate
				if new_mode == "720p24":
					new_mode = config.av.fixres_720p24.value
				if new_mode == "1080p24":
					new_mode = config.av.fixres_1080p24.value
				if new_mode == "1080p25":
					new_mode = config.av.fixres_1080p25.value
				if new_mode == "1080p30":
					new_mode = config.av.fixres_1080p30.value
				if new_mode == "2160p24":
					new_mode = config.av.fixres_2160p24.value
				if new_mode == "2160p25":
					new_mode = config.av.fixres_2160p25.value
				if new_mode == "2160p30":
					new_mode = config.av.fixres_2160p30.value
				write_mode = new_mode
			else:
				if video_rate == 25000:  # videomode_25hz is not in proc and will be reset 2nd pass thru , so do it now.
					new_rate = 50
				print(f"[VideoMode][VideoChangeDetect] else:  video_rate:{video_rate}, new_rate:{new_rate}")
				if path.exists(f"{videomode}_{new_rate}hz") and config_rate in ("multi", "auto"):
					print(f"[VideoMode][VideoChangeDetect] path exists in proc:  video_rate:{video_rate}, new_rate:{new_rate}, config_rate:{config_rate}")
					with open(f"{videomode}_{new_rate}hz", "r") as fd:
						multi_videomode = fd.read().replace("\n", "")
					print(f"[VideoMode][VideoChangeDetect]1 multi_videomode:{multi_videomode}, current_mode:{current_mode}")
					if multi_videomode and (current_mode != multi_videomode):
						write_mode = multi_videomode
						print(f"[VideoMode][VideoChangeDetect]2 write_mode:{write_mode}, multi_videomode:{multi_videomode}")
					else:
						write_mode = current_mode
						print(f"[VideoMode][VideoChangeDetect]3 write_mode:{write_mode}, current_mode:{current_mode}")
			print(f"[VideoMode][VideoChangeDetect]5 write_mode: {write_mode} current_mode: {current_mode}")
			if write_mode and current_mode != write_mode or self.firstrun:
				resolutionlabel["restxt"].setText(_(f"Video mode: {write_mode}"))
				if config.av.fixres_label_timeout.value != "0":
					resolutionlabel.show()
				print(f"[VideoMode] setMode - port: {config.av.videoport.value}, mode: {write_mode}")
				avSwitch.setVideoMode(write_mode)
				read_mode = avSwitch.getVideoMode("")
				print(f"[VideoMode]3 fd.write_mode:{write_mode}, read_mode:{read_mode}")
			else:
				print(f"[VideoMode][VideoChangeDetect]6 VideoMode not changed write_mode: {write_mode} current_mode: {current_mode}")
				resolutionlabel["restxt"].setText(_("Video mode: %s not available") % write_mode)
		self.delay = False
		self.detecttimer.stop()
		self.firstrun = False
		iAV.setAspect(config.av.aspect)
		iAV.setWss(config.av.wss)
		iAV.setPolicy43(config.av.policy_43)
		iAV.setPolicy169(config.av.policy_169)


def autostart(session):
	global resolutionlabel
	print("[VideoMode][autostart] forceVideoMode entered")
	if resolutionlabel is None:
		resolutionlabel = session.instantiateDialog(forceVideoModeLabel)
	forceVideoMode(session)
