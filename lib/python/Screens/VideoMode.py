from os import path

from enigma import iPlayableService, iServiceInformation, eTimer, eServiceCenter, eServiceReference, eDVBDB

from Screens.Screen import Screen
from Screens.ChannelSelection import FLAG_IS_DEDICATED_3D
from Components.About import about
from Components.SystemInfo import SystemInfo
from Components.ConfigList import ConfigListScreen
from Components.config import config, configfile, getConfigListEntry
from Components.Label import Label
from Components.Sources.StaticText import StaticText
from Components.Pixmap import Pixmap
from Components.Sources.Boolean import Boolean
from Components.ServiceEventTracker import ServiceEventTracker
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
from Tools.HardwareInfo import HardwareInfo
from Components.AVSwitch import iAVSwitch

resolutionlabel = None

class VideoSetup(Screen, ConfigListScreen):
	def __init__(self, session, menu_path=""):
		Screen.__init__(self, session)
		screentitle = _("Settings")
		if config.usage.show_menupath.value == 'large':
			menu_path += screentitle
			title = menu_path
			self["menu_path_compressed"] = StaticText("")
		elif config.usage.show_menupath.value == 'small':
			title = screentitle
			self["menu_path_compressed"] = StaticText(menu_path + " >" if not menu_path.endswith(' / ') else menu_path[:-3] + " >" or "")
		else:
			title = screentitle
			self["menu_path_compressed"] = StaticText("")
		self.skinName = ["Setup" ]
		self.setup_title = title
		self["HelpWindow"] = Pixmap()
		self["HelpWindow"].hide()
		self["VKeyIcon"] = Boolean(False)
		self['footnote'] = Label()

		self.hw = iAVSwitch
		self.onChangedEntry = [ ]

		# handle hotplug by re-creating setup
		self.onShow.append(self.startHotplug)
		self.onHide.append(self.stopHotplug)

		self.list = [ ]
		ConfigListScreen.__init__(self, self.list, session = session, on_change = self.changedEntry)

		from Components.ActionMap import ActionMap
		self["actions"] = ActionMap(["SetupActions", "MenuActions"],
			{
				"cancel": self.keyCancel,
				"save": self.apply,
				"menu": self.closeRecursive,
			}, -2)

		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("OK"))
		self["description"] = Label("")

		self.createSetup()
		self.grabLastGoodMode()
		self.onLayoutFinish.append(self.layoutFinished)

	def layoutFinished(self):
		self.setTitle(self.setup_title)

	def startHotplug(self):
		self.hw.on_hotplug.append(self.createSetup)

	def stopHotplug(self):
		self.hw.on_hotplug.remove(self.createSetup)

	def createSetup(self):
		level = config.usage.setup_level.index

		self.list = [
			getConfigListEntry(_("Video output"), config.av.videoport, _("Configures which video output connector will be used."))
		]
		if config.av.videoport.value in ('HDMI', 'YPbPr', 'Scart-YPbPr') and not path.exists(resolveFilename(SCOPE_PLUGINS)+'SystemPlugins/AutoResolution'):
			self.list.append(getConfigListEntry(_("Automatic resolution"), config.av.autores,_("If enabled the output resolution of the box will try to match the resolution of the video content")))
			if config.av.autores.value in ('all', 'hd'):
				self.list.append(getConfigListEntry(_("Force de-interlace"), config.av.autores_deinterlace,_("If enabled the video will always be de-interlaced.")))
				self.list.append(getConfigListEntry(_("Automatic resolution label"), config.av.autores_label_timeout,_("Allows you to adjust the amount of time the resolution infomation display on screen.")))
				if config.av.autores.value in ('hd'):
					self.list.append(getConfigListEntry(_("Show SD as"), config.av.autores_sd,_("This option allows you to choose how to display standard defintion video on your TV.")))
				self.list.append(getConfigListEntry(_("Show 480/576p 24fps as"), config.av.autores_480p24,_("This option allows you to choose how to display SD progressive 24Hz on your TV. (as not all TV's support these resolutions)")))
				self.list.append(getConfigListEntry(_("Show 720p 24fps as"), config.av.autores_720p24,_("This option allows you to choose how to display 720p 24Hz on your TV. (as not all TV's support these resolutions)")))
				self.list.append(getConfigListEntry(_("Show 1080p 24fps as"), config.av.autores_1080p24,_("This option allows you to choose how to display 1080p 24Hz on your TV. (as not all TV's support these resolutions)")))
				self.list.append(getConfigListEntry(_("Show 1080p 25fps as"), config.av.autores_1080p25,_("This option allows you to choose how to display 1080p 25Hz on your TV. (as not all TV's support these resolutions)")))
				self.list.append(getConfigListEntry(_("Show 1080p 30fps as"), config.av.autores_1080p30,_("This option allows you to choose how to display 1080p 30Hz on your TV. (as not all TV's support these resolutions)")))
				if '2160p24' in iAVSwitch.readAvailableModes():
					self.list.append(getConfigListEntry(_("Show 2160p 24fps as"), config.av.autores_2160p24,_("This option allows you to choose how to display 2160p 24Hz on your TV. (as not all TV's support these resolutions)")))
					self.list.append(getConfigListEntry(_("Show 2160p 25fps as"), config.av.autores_2160p25,_("This option allows you to choose how to display 2160p 25Hz on your TV. (as not all TV's support these resolutions)")))
					self.list.append(getConfigListEntry(_("Show 2160p 30fps as"), config.av.autores_2160p30,_("This option allows you to choose how to display 2160p 30Hz on your TV. (as not all TV's support these resolutions)")))

		# if we have modes for this port:
		if (config.av.videoport.value in config.av.videomode and config.av.autores.value == 'disabled') or config.av.videoport.value == 'Scart':
			# add mode- and rate-selection:
			self.list.append(getConfigListEntry(pgettext("Video output mode", "Mode"), config.av.videomode[config.av.videoport.value], _("This option configures the video output mode (or resolution).")))
			if config.av.videomode[config.av.videoport.value].value == 'PC':
				self.list.append(getConfigListEntry(_("Resolution"), config.av.videorate[config.av.videomode[config.av.videoport.value].value], _("This option configures the screen resolution in PC output mode.")))
			elif config.av.videoport.value != 'Scart':
				self.list.append(getConfigListEntry(_("Refresh rate"), config.av.videorate[config.av.videomode[config.av.videoport.value].value], _("Configure the refresh rate of the screen. Multi means refresh rate depends on the source 24/50/60Hz")))
		if config.av.autores.value in ('all', 'hd') or config.av.videorate[config.av.videomode[config.av.videoport.value].value].value == 'multi':
			self.list.append(getConfigListEntry(_("Delay time"), config.av.autores_delay,_("Set the time before checking video source for resolution/refresh rate infomation.")))

		port = config.av.videoport.value
		if port not in config.av.videomode:
			mode = None
		else:
			mode = config.av.videomode[port].value

		# some modes (720p, 1080i) are always widescreen. Don't let the user select something here, "auto" is not what he wants.
		force_wide = self.hw.isWidescreenMode(port, mode)

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
			self.list.append(getConfigListEntry(_("HDMI Colorspace"), config.av.hdmicolorspace,_("Change the Colorspace from Auto to RGB")))

		if SystemInfo["havecolorimetry"]:
			self.list.append(getConfigListEntry(_("HDMI Colorimetry"), config.av.hdmicolorimetry,_("Change the Colorimetry for HDR")))

		if SystemInfo["havehdmicolordepth"]:
			self.list.append(getConfigListEntry(_("HDMI Colordepth"), config.av.hdmicolordepth,_("Change the Colordepth for UHD")))

		if SystemInfo["havehdmihdrtype"]:
			self.list.append(getConfigListEntry(_("HDMI HDR Type"), config.av.hdmihdrtype,_("Enable or disable to force HDR Modes for UHD")))

		if SystemInfo["HDRSupport"]:
			self.list.append(getConfigListEntry(_("HLG Support"), config.av.hlg_support,_("Enable or disable to force HLG Modes for UHD")))
			self.list.append(getConfigListEntry(_("HDR10 Support"), config.av.hdr10_support,_("Enable or disable to force HDR10 Modes for UHD")))
			self.list.append(getConfigListEntry(_("Allow 12bit"), config.av.allow_12bit,_("Enable or disable the 12 Bit Color Mode")))
			self.list.append(getConfigListEntry(_("Allow 10bit"), config.av.allow_10bit,_("Enable or disable the 10 Bit Color Mode")))

		if level >= 1:
			if SystemInfo["CanPcmMultichannel"]:
				self.list.append(getConfigListEntry(_("PCM Multichannel"), config.av.pcm_multichannel, _("Choose whether multi channel sound tracks should be output as PCM.")))
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
			self.list.extend((
				getConfigListEntry(_("General AC3 delay"), config.av.generalAC3delay, _("This option configures the general audio delay of Dolby Digital sound tracks.")),
				getConfigListEntry(_("General PCM delay"), config.av.generalPCMdelay, _("This option configures the general audio delay of stereo sound tracks."))
			))

			if SystemInfo["Can3DSurround"]:
				self.list.append(getConfigListEntry(_("3D Surround"), config.av.surround_3d,_("This option allows you to enable 3D Surround Sound for an output.")))

			if SystemInfo["Can3DSpeaker"] and config.av.surround_3d.value != "none":
				self.list.append(getConfigListEntry(_("3D Surround Speaker Position"), config.av.surround_3d_speaker,_("This option allows you to change the virtual loudspeaker position.")))

			if SystemInfo["CanAutoVolume"]:
				self.list.append(getConfigListEntry(_("Auto Volume Level"), config.av.autovolume,_("This option configures output for Auto Volume Level.")))

			if SystemInfo["Canedidchecking"]:
				self.list.append(getConfigListEntry(_("Bypass HDMI EDID Check"), config.av.bypass_edid_checking,_("This option allows you to bypass HDMI EDID check")))

		if SystemInfo["haveboxmode"]:
			self.list.append(getConfigListEntry(_("Video Chip Mode*"), config.av.boxmode,_("Choose between High Dynamic Range (HDR) or Picture in Picture (PIP). Both are not possible at the same time. A FULL REBOOT is required for it to take effect")))

#		if not isinstance(config.av.scaler_sharpness, ConfigNothing):
#			self.list.append(getConfigListEntry(_("Scaler sharpness"), config.av.scaler_sharpness, _("This option configures the picture sharpness.")))

		self["config"].list = self.list
		self["config"].l.setList(self.list)
		if config.usage.sort_settings.value:
			self["config"].list.sort()

	def keyLeft(self):
		ConfigListScreen.keyLeft(self)
		self.createSetup()

	def keyRight(self):
		ConfigListScreen.keyRight(self)
		self.createSetup()

	def confirm(self, confirmed):
		if not confirmed:
			config.av.videoport.setValue(self.last_good[0])
			config.av.videomode[self.last_good[0]].setValue(self.last_good[1])
			config.av.videorate[self.last_good[1]].setValue(self.last_good[2])
			self.hw.setMode(*self.last_good)
		else:
			self.keySave()

	def grabLastGoodMode(self):
		port = config.av.videoport.value
		mode = config.av.videomode[port].value
		rate = config.av.videorate[mode].value
		self.last_good = (port, mode, rate)

	def saveAll(self):
		if config.av.videoport.value == 'Scart':
			config.av.autores.setValue('disabled')
		for x in self["config"].list:
			x[1].save()
		configfile.save()

	def apply(self):
		port = config.av.videoport.value
		mode = config.av.videomode[port].value
		rate = config.av.videorate[mode].value
		if (port, mode, rate) != self.last_good:
			self.hw.setMode(port, mode, rate)
			from Screens.MessageBox import MessageBox
			self.session.openWithCallback(self.confirm, MessageBox, _("Is this video mode ok?"), MessageBox.TYPE_YESNO, timeout = 20, default = False)
		else:
			self.keySave()

	# for summary:
	def changedEntry(self):
		for x in self.onChangedEntry:
			x()

	def getCurrentEntry(self):
		return self["config"].getCurrent()[0]

	def getCurrentValue(self):
		return str(self["config"].getCurrent()[1].getText())

	def getCurrentDescription(self):
		return self["config"].getCurrent() and len(self["config"].getCurrent()) > 2 and self["config"].getCurrent()[2] or ""

	def createSummary(self):
		from Screens.Setup import SetupSummary
		return SetupSummary

class AutoVideoModeLabel(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)

		self["content"] = Label()
		self["restxt"] = Label()

		self.hideTimer = eTimer()
		self.hideTimer.callback.append(self.hide)

		self.onShow.append(self.hide_me)

	def hide_me(self):
		idx = config.av.autores_label_timeout.index
		if idx:
			idx += 4
			self.hideTimer.start(idx*1000, True)

previous = None
isDedicated3D = False

def applySettings(mode=config.osd.threeDmode.value, znorm=int(config.osd.threeDznorm.value)):
	global previous, isDedicated3D
	mode = isDedicated3D and mode == "auto" and "sidebyside" or mode
	mode == "3dmode" in SystemInfo["3DMode"] and mode or mode == 'sidebyside' and 'sbs' or mode == 'topandbottom' and 'tab' or 'off'
	if previous != (mode, znorm):
		try:
			open(SystemInfo["3DMode"], "w").write(mode)
			open(SystemInfo["3DZNorm"], "w").write('%d' % znorm)
			previous = (mode, znorm)
		except:
			return

class AutoVideoMode(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.current3dmode = config.osd.threeDmode.value
		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evStart: self.__evStart,
				iPlayableService.evVideoSizeChanged: self.VideoChanged,
				iPlayableService.evVideoProgressiveChanged: self.VideoChanged,
				iPlayableService.evVideoFramerateChanged: self.VideoChanged,
				iPlayableService.evBuffering: self.BufferInfo,
			})

		self.delay = False
		self.bufferfull = True
		self.detecttimer = eTimer()
		self.detecttimer.callback.append(self.VideoChangeDetect)

	def checkIfDedicated3D(self):
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

	def BufferInfo(self):
		bufferInfo = self.session.nav.getCurrentService().streamed().getBufferCharge()
		if bufferInfo[0] > 98:
			self.bufferfull = True
			self.VideoChanged()
		else:
			self.bufferfull = False

	def VideoChanged(self):
		if self.session.nav.getCurrentlyPlayingServiceReference() and not self.session.nav.getCurrentlyPlayingServiceReference().toString().startswith('4097:'):
			delay = config.av.autores_delay.value
		else:
			delay = config.av.autores_delay.value * 2
		if not self.detecttimer.isActive() and not self.delay:
			self.delay = True
			self.detecttimer.start(delay)
		else:
			self.delay = True
			self.detecttimer.stop()
			self.detecttimer.start(delay)

	def VideoChangeDetect(self):
		global resolutionlabel
		config_port = config.av.videoport.value
		config_mode = str(config.av.videomode[config_port].value).replace('\n','')
		config_res = str(config.av.videomode[config_port].value[:-1]).replace('\n','')
		config_pol = str(config.av.videomode[config_port].value[-1:]).replace('\n','')
		config_rate = str(config.av.videorate[config_mode].value).replace('Hz','').replace('\n','')

		f = open("/proc/stb/video/videomode")
		current_mode = f.read()[:-1].replace('\n','')
		f.close()
		if current_mode.upper() in ('PAL', 'NTSC'):
			current_mode = current_mode.upper()

		current_pol = ''
		if 'i' in current_mode:
			current_pol = 'i'
		elif 'p' in current_mode:
			current_pol = 'p'
		current_res = current_pol and current_mode.split(current_pol)[0].replace('\n','') or ""
		current_rate = current_pol and current_mode.split(current_pol)[0].replace('\n','') and current_mode.split(current_pol)[1].replace('\n','') or ""

		video_height = None
		video_width = None
		video_pol = None
		video_rate = None
		if path.exists("/proc/stb/vmpeg/0/yres"):
			f = open("/proc/stb/vmpeg/0/yres", "r")
			try:
				video_height = int(f.read(),16)
			except:
				pass
			f.close()
		if path.exists("/proc/stb/vmpeg/0/xres"):
			f = open("/proc/stb/vmpeg/0/xres", "r")
			try:
				video_width = int(f.read(),16)
			except:
				pass
			f.close()
		if path.exists("/proc/stb/vmpeg/0/progressive"):
			f = open("/proc/stb/vmpeg/0/progressive", "r")
			try:
				video_pol = "p" if int(f.read(),16) else "i"
			except:
				pass
			f.close()
		if path.exists("/proc/stb/vmpeg/0/framerate"):
			f = open("/proc/stb/vmpeg/0/framerate", "r")
			try:
				video_rate = int(f.read())
			except:
				pass
			f.close()

		if not video_height or not video_width or not video_pol or not video_rate:
			service = self.session.nav.getCurrentService()
			if service is not None:
				info = service.info()
			else:
				info = None

			if info:
				video_height = int(info.getInfo(iServiceInformation.sVideoHeight))
				video_width = int(info.getInfo(iServiceInformation.sVideoWidth))
				video_pol = ("i", "p")[info.getInfo(iServiceInformation.sProgressive)]
				video_rate = int(info.getInfo(iServiceInformation.sFrameRate))

		if video_height and video_width and video_pol and video_rate:
			resolutionlabel["content"].setText(_("Video content: %ix%i%s %iHz") % (video_width, video_height, video_pol, (video_rate + 500) / 1000))
			if (700 < video_width <= 720) and video_height <= 480 and video_rate in (23976, 24000, 29970, 59940):
				new_res = "480"
			elif (700 < video_width <= 720) and video_height <= 576 and video_rate in (25000, 50000):
				new_res = "576"
			elif (video_width == 1280) and video_height <= 720:
				new_res = "720"
			elif (video_width == 1920) and video_height <= 1080:
				new_res = "1080"
			elif (video_width == 3840) and video_height > 1080:
				new_res = "2160"
			else:
				new_res = config_res

			if video_rate != -1:
				if video_rate == 25000 and video_pol == 'i':
					new_rate = 50000
				elif video_rate == 59940 or (video_rate == 29970 and video_pol == 'i') or (video_rate == 29970 and video_pol == 'p' and config.av.autores.value == 'disabled'):
					new_rate = 60000
				elif video_rate == 23976:
					new_rate = 24000
				elif video_rate == 29970:
					new_rate = 30000
				else:
					new_rate = video_rate
				new_rate = str((new_rate + 500) / 1000)
			else:
				new_rate = config_rate

			if video_pol != -1:
				new_pol = str(video_pol)
			else:
				new_pol = config_pol

			write_mode = None
			new_mode = None
			if config_mode in ('PAL', 'NTSC'):
				write_mode = config_mode
			elif config.av.autores.value == 'all' or (config.av.autores.value == 'hd' and int(new_res) >= 720):
				if (config.av.autores_deinterlace.value and HardwareInfo().is_nextgen()) or (config.av.autores_deinterlace.value and not HardwareInfo().is_nextgen() and int(new_res) <= 720):
					new_pol = new_pol.replace('i','p')
				if new_res+new_pol+new_rate in iAVSwitch.readAvailableModes():
					new_mode = new_res+new_pol+new_rate
					if new_mode == '480p24' or new_mode == '576p24':
						new_mode = config.av.autores_480p24.value
					if new_mode == '720p24':
						new_mode = config.av.autores_720p24.value
					if new_mode == '1080p24':
						new_mode = config.av.autores_1080p24.value
					if new_mode == '1080p25':
						new_mode = config.av.autores_1080p25.value
					if new_mode == '1080p30':
						new_mode = config.av.autores_1080p30.value
					if new_mode == '2160p24':
						new_mode = config.av.autores_2160p24.value
					if new_mode == '2160p25' or new_mode == '2160p50':
						new_mode = config.av.autores_2160p25.value
					if new_mode == '2160p30' or new_mode == '2160p60' or new_mode == '2160p':
						new_mode = config.av.autores_2160p30.value
				elif new_res+new_pol in iAVSwitch.readAvailableModes():
					new_mode = new_res+new_pol
					if new_mode == '2160p30' or new_mode == '2160p60' or new_mode == '2160p':
						new_mode = config.av.autores_2160p30.value
				else:
					new_mode = config_mode+new_rate

				write_mode = new_mode
			elif config.av.autores.value == 'hd' and int(new_res) <= 576:
				if (config.av.autores_deinterlace.value and HardwareInfo().is_nextgen()) or (config.av.autores_deinterlace.value and not HardwareInfo().is_nextgen() and not config.av.autores_sd.value == '1080i'):
					new_mode = config.av.autores_sd.value.replace('i','p')+new_rate
				else:
					if new_pol in 'p':
						new_mode = config.av.autores_sd.value.replace('i','p')+new_rate
					else:
						new_mode = config.av.autores_sd.value+new_rate

				if new_mode == '720p24':
					new_mode = config.av.autores_720p24.value
				if new_mode == '1080p24':
					new_mode = config.av.autores_1080p24.value
				if new_mode == '1080p25':
					new_mode = config.av.autores_1080p25.value
				if new_mode == '1080p30':
					new_mode = config.av.autores_1080p30.value
				if new_mode == '2160p24':
					new_mode = config.av.autores_2160p24.value
				if new_mode == '2160p25':
					new_mode = config.av.autores_2160p25.value
				if new_mode == '2160p30':
					new_mode = config.av.autores_2160p30.value

				write_mode = new_mode
			else:
				if path.exists('/proc/stb/video/videomode_%shz' % new_rate) and config_rate == 'multi':
					try:
						f = open("/proc/stb/video/videomode_%shz" % new_rate, "r")
						multi_videomode = f.read().replace('\n','')
						f.close()
						if multi_videomode and (current_mode != multi_videomode):
							write_mode = multi_videomode
						else:
							write_mode = current_mode
					except IOError:
							write_mode = current_mode

			if write_mode and current_mode != write_mode:
				resolutionlabel["restxt"].setText(_("Video mode: %s") % write_mode)
				if config.av.autores.value != "disabled" and config.av.autores_label_timeout.value != '0':
					resolutionlabel.show()
				print "[VideoMode] setMode - port: %s, mode: %s" % (config_port, write_mode)
				f = open("/proc/stb/video/videomode", "w")
				f.write(write_mode)
				f.close()

		iAVSwitch.setAspect(config.av.aspect)
		iAVSwitch.setWss(config.av.wss)
		iAVSwitch.setPolicy43(config.av.policy_43)
		iAVSwitch.setPolicy169(config.av.policy_169)

		self.delay = False
		self.detecttimer.stop()

def autostart(session):
	global resolutionlabel
	if not path.exists(resolveFilename(SCOPE_PLUGINS)+'SystemPlugins/AutoResolution'):
		if resolutionlabel is None:
			resolutionlabel = session.instantiateDialog(AutoVideoModeLabel)
		AutoVideoMode(session)
	else:
		config.av.autores.setValue(False)
		config.av.autores.save()
		configfile.save()
