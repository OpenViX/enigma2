from Components.AVSwitch import iAVSwitch as iAV
from Components.config import config, getConfigListEntry
from Components.SystemInfo import SystemInfo
from Screens.MessageBox import MessageBox
from Screens.Setup import Setup


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
		self.list = [
			getConfigListEntry(_("Video Output"), config.av.videoport, _("Configures which video output connector will be used."))
		]
		# if we have modes for this port:
		if config.av.videoport.value in config.av.videomode or config.av.videoport.value == "Scart":
			# add mode- and rate-selection:
			self.list.append(getConfigListEntry(pgettext("Video Output Mode", "Mode"), config.av.videomode[config.av.videoport.value], _("This option configures the video output mode (or resolution).")))
			if config.av.videomode[config.av.videoport.value].value == "PC":
				self.list.append(getConfigListEntry(_("Resolution"), config.av.videorate[config.av.videomode[config.av.videoport.value].value], _("This option configures the screen resolution in PC output mode.")))
			elif config.av.videoport.value != "Scart":
				self.list.append(getConfigListEntry(_("Refresh Rate"), config.av.videorate[config.av.videomode[config.av.videoport.value].value], _("Configure screen refresh rate. Multi & Auto rates depend on the source 24/50/60Hz")))
		port = config.av.videoport.value
		mode = config.av.videomode[port].value if port in config.av.videomode else None
		# some modes (720p, 1080i) are always widescreen. Don't let the user select something here, "auto" is not what he wants.
		force_wide = iAV.isWidescreenMode(port, mode)
		# if not force_wide:
		# 	self.list.append(getConfigListEntry(_("Aspect ratio"), config.av.aspect, _("Configure the aspect ratio of the screen.")))
		if force_wide or config.av.aspect.value in ("16:9", "16:10"):
			self.list.extend((
				getConfigListEntry(_("Display 4:3 Content as"), config.av.policy_43, _("When the content has an aspect ratio of 4:3, choose whether to scale/stretch the picture.")),
				getConfigListEntry(_("Display >16:9 Content as"), config.av.policy_169, _("When the content has an aspect ratio of 16:9, choose whether to scale/stretch the picture."))
			))
		elif config.av.aspect.value == "4:3":
			self.list.append(getConfigListEntry(_("Display 16:9 Content as"), config.av.policy_169, _("When the content has an aspect ratio of 16:9, choose whether to scale/stretch the picture.")))

		if config.av.videoport.value == "Scart":
			self.list.append(getConfigListEntry(_("Color Format"), config.av.colorformat, _("Configure which color format should be used on the SCART output.")))
			if config.usage.setup_level.index >= 1:
				self.list.append(getConfigListEntry(_("WSS on 4:3"), config.av.wss, _("When enabled, content with an aspect ratio of 4:3 will be stretched to fit the screen.")))
				if SystemInfo["ScartSwitch"]:
					self.list.append(getConfigListEntry(_("Auto Scart Switching"), config.av.vcrswitch, _("When enabled, your receiver will detect activity on the VCR SCART input.")))
		if SystemInfo["havecolorspace"]:
			self.list.append(getConfigListEntry(_("HDMI Colorspace"), config.av.hdmicolorspace, _("Change Colorspace setting - this may cause unexpected results or black screen")))
		if SystemInfo["havecolorimetry"]:
			self.list.append(getConfigListEntry(_("HDMI Colorimetry"), config.av.hdmicolorimetry, _("Change the Colorimetry for HDR - this may cause unexpected results or black screen")))
		if SystemInfo["havehdmicolordepth"]:
			if not SystemInfo["needsVideoJudderDriverFix"]:
				self.list.append(getConfigListEntry(_("HDMI Color Depth"), config.av.hdmicolordepth, _("Change the Colordepth for UHD - this may cause unexpected results or black screen")))
		if SystemInfo["havehdmihdrtype"]:
			self.list.append(getConfigListEntry(_("HDMI HDR Type"), config.av.hdmihdrtype, _("Enable or disable to force HDR Modes for UHD")))
		if SystemInfo["havehdmihdrosd"]:
			self.list.append(getConfigListEntry(_("HDR OSD adjustment"), config.av.hdmihdrosd, _("This option adjusts SDR graphics and OSD colors while the HDMI output is in HDR mode.")))
		if SystemInfo["HDRSupport"]:
			self.list.append(getConfigListEntry(_("HLG Support"), config.av.hlg_support, _("Enable or Disable to Force HLG Modes for UHD")))
			self.list.append(getConfigListEntry(_("HDR10 Support"), config.av.hdr10_support, _("Enable or Disable to Force HDR10 Modes for UHD")))
			self.list.append(getConfigListEntry(_("Allow 12bit"), config.av.allow_12bit, _("Enable or Disable the 12 Bit Color Mode")))
			self.list.append(getConfigListEntry(_("Allow 10bit"), config.av.allow_10bit, _("Enable or Disable the 10 Bit Color Mode")))
		if config.usage.setup_level.index >= 1:
			if SystemInfo["CanDownmixAC3"]:
				if SystemInfo["Vu_EAC3_fix"]:
					self.list.append(getConfigListEntry(_("AC3 / AC3+ Downmix"), config.av.downmix_ac3, _("Choose whether multi channel AC3 / AC3+ sound tracks should be downmixed to stereo.")))
				else:
					self.list.append(getConfigListEntry(_("AC3 Downmix"), config.av.downmix_ac3, _("Choose whether multi channel AC3 sound tracks should be downmixed to stereo.")))
			if SystemInfo["CanDownmixAC3Plus"]:
				self.list.append(getConfigListEntry(_("AC3+ Downmix"), config.av.downmix_ac3plus, _("Choose whether multi channel AC3+ sound tracks should be downmixed to stereo.")))
			if SystemInfo["CanDownmixAAC"]:
				if SystemInfo["Vu_EAC3_fix"]:
					self.list.append(getConfigListEntry(_("AAC / AAC+ Downmix"), config.av.downmix_aac, _("Choose whether multi channel AAC / AAC+ sound tracks should be downmixed to stereo.")))
				else:
					self.list.append(getConfigListEntry(_("AAC Downmix"), config.av.downmix_aac, _("Choose whether multi channel AAC sound tracks should be downmixed to stereo.")))
			if SystemInfo["CanDownmixAACPlus"]:
				self.list.append(getConfigListEntry(_("AAC+ Downmix"), config.av.downmix_aacplus, _("Choose whether multi channel AAC+ sound tracks should be downmixed to stereo.")))
			if SystemInfo["CanDownmixDTS"]:
				self.list.append(getConfigListEntry(_("DTS Downmix"), config.av.downmix_dts, _("Choose whether multi channel DTS sound tracks should be downmixed to stereo.")))
			if SystemInfo["CanDTSHD"]:
				self.list.append(getConfigListEntry(_("DTS-HD MA/HR Downmix"), config.av.dtshd, _("Choose whether multi channel DTS-HD sound tracks should be downmixed or transcoded.")))
			if SystemInfo["CanWMAPRO"]:
				self.list.append(getConfigListEntry(_("WMA Pro Downmix"), config.av.wmapro, _("Choose whether WMA Pro sound tracks should be downmixed.")))

			self.list.append(getConfigListEntry(_("DTS / DTS-HD Transcoding"), config.av.dts_playback, _("Choose whether DTS / DTS-HD sound tracks should be transcoded to Dolby Digital.")))
			self.list.append(getConfigListEntry(_("Dolby TrueHD Transcoding"), config.av.truehd_playback, _("Choose whether Dolby TrueHD sound tracks should be transcoded to Dolby Digital.")))

			if SystemInfo["CanAACTranscode"]:
				self.list.append(getConfigListEntry(_("AAC Transcoding"), config.av.transcodeaac, _("Choose whether AAC sound tracks should be transcoded.")))
			if SystemInfo["CanPcmMultichannel"]:
				self.list.append(getConfigListEntry(_("PCM Multichannel"), config.av.pcm_multichannel, _("Choose whether multi channel sound tracks should be output as PCM.")))
			self.list.extend((
				getConfigListEntry(_("General AC3 Delay"), config.av.generalAC3delay, _("This option configures the general audio delay of Dolby Digital sound tracks.")),
				getConfigListEntry(_("General PCM Delay"), config.av.generalPCMdelay, _("This option configures the general audio delay of stereo sound tracks."))
			))
			if SystemInfo["CanBTAudio"]:
				self.list.append(getConfigListEntry(_("Enable Bluetooth Audio"), config.av.btaudio, _("This option allows you to switch audio to bluetooth speakers.")))
			if SystemInfo["CanBTAudioDelay"]:
				self.list.append(getConfigListEntry(_("General Bluetooth Audio Delay"), config.av.btaudiodelay, _("This option configures the general audio delay for bluetooth speakers.")))
			if SystemInfo["Can3DSurround"]:
				self.list.append(getConfigListEntry(_("3D Surround"), config.av.surround_3d, _("This option allows you to enable 3D Surround Sound for an output.")))
			if SystemInfo["Can3DSpeaker"] and config.av.surround_3d.value != "none":
				self.list.append(getConfigListEntry(_("3D Surround Speaker Position"), config.av.surround_3d_speaker, _("This option allows you to change the virtual loudspeaker position.")))
			self.list.append((_("Audio Volume Step Size"), config.av.volume_stepsize, _("Configure the general audio volume step size (limit 1-10).")))
			self.list.append((_("Hide Mute Icon"), config.av.volume_hide_mute, _("If volume muted, hide mute icon or mute information after few seconds.")))
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
			self.session.openWithCallback(self.confirm, MessageBox, _("Is this Video Mode Ok?"), MessageBox.TYPE_YESNO, timeout=20, default=False)
		else:
			Setup.keySave(self)
