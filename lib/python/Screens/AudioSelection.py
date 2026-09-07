from enigma import iPlayableService, eTimer, eSize, eDVBDB, eServiceReference, eServiceCenter, iServiceInformation
from Components.ActionMap import NumberActionMap
from Components.config import config, ConfigSubsection, getConfigListEntry, ConfigNothing, ConfigSelection, ConfigOnOff, ConfigYesNo
from Components.ConfigList import ConfigListScreen
from Components.Converter.VAudioInfo import StdAudioDesc
from Components.Label import Label
from Components.PluginComponent import plugins
from Components.ServiceEventTracker import ServiceEventTracker
from Components.Sources.Boolean import Boolean
from Components.Sources.List import List
from Components.SystemInfo import SystemInfo
from Components.UsageConfig import originalAudioTracks, visuallyImpairedCommentary
from Components.VolumeControl import VolumeControl

from Plugins.Plugin import PluginDescriptor

from Screens.InputBox import PinInput
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Setup import getConfigMenuItem, Setup

from Tools.ISO639 import LanguageCodes
from Tools.General import isIPTV
from Tools.Directories import resolveFilename, SCOPE_CURRENT_SKIN
from Tools.LoadPixmap import LoadPixmap
from Tools.BoundFunction import boundFunction

FOCUS_CONFIG, FOCUS_STREAMS = range(2)
[PAGE_AUDIO, PAGE_SUBTITLES] = ["audio", "subtitles"]

selectionpng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "selections/selectioncross.png"))  # for use in the future


class AudioSelection(ConfigListScreen, Screen):
	TYPE_ALL = 0
	TYPE_AUDIO = 1
	TYPE_SUBTITLE = 2
	hooks = []
	audioHooks = []
	subtitleHooks = []
	fillSubtitleExt = None

	def __init__(self, session, infobar=None, page=PAGE_AUDIO):
		Screen.__init__(self, session)
		self["streams"] = List([], enableWrapAround=True)
		self.colors = ("red", "green", "yellow", "blue")
		for color in self.colors:
			self[f"key_{color}"] = Boolean(False)
		self.protectContextMenu = True
		ConfigListScreen.__init__(self, [])
		self.infobar = infobar or self.session.infobar
		if not hasattr(self.infobar, "selected_subtitle"):
			self.infobar.selected_subtitle = None

		self.__event_tracker = ServiceEventTracker(screen=self, eventmap={
			iPlayableService.evUpdatedInfo: self.__updatedInfo
		})
		self.cached_subtitle_checked = False
		self.__selected_subtitle = None
		self["actions"] = NumberActionMap(["ColorActions", "OkCancelActions", "DirectionActions", "MenuActions", "InfobarAudioSelectionActions", "InfobarSubtitleSelectionActions"], {
			"red": boundFunction(self.colorkey, self.colors.index("red")),
			"green": boundFunction(self.colorkey, self.colors.index("green")),
			"yellow": boundFunction(self.colorkey, self.colors.index("yellow")),
			"blue": boundFunction(self.colorkey, self.colors.index("blue")),
			"subtitleSelection": self.keyAudioSubtitle,
			"audioSelection": self.keyAudioSubtitle,
			"ok": self.keyOk,
			"cancel": self.cancel,
			"up": self.keyUp,
			"down": self.keyDown,
			"volumeUp": self.volumeUp,
			"volumeDown": self.volumeDown,
			"volumeMute": self.volumeMute,
			"menu": self.openAutoLanguageSetup,
			"1": self.keyNumberGlobal,
			"2": self.keyNumberGlobal,
			"3": self.keyNumberGlobal,
			"4": self.keyNumberGlobal,
			"5": self.keyNumberGlobal,
			"6": self.keyNumberGlobal,
			"7": self.keyNumberGlobal,
			"8": self.keyNumberGlobal,
			"9": self.keyNumberGlobal,
		}, -2)
		self.settings = ConfigSubsection()
		choicelist = [
			(PAGE_AUDIO, ""),
			(PAGE_SUBTITLES, "")
		]
		self.settings.menupage = ConfigSelection(choices=choicelist, default=page)
		self.onLayoutFinish.append(self.__layoutFinished)

	def runHooks(self, type):
		if type == self.TYPE_ALL:
			for hook in AudioSelection.hooks:
				if callable(hook):
					hook()
		elif type == self.TYPE_AUDIO:
			for hook in AudioSelection.audioHooks:
				if callable(hook):
					hook()
		elif type == self.TYPE_SUBTITLE:
			for hook in AudioSelection.subtitleHooks:
				if callable(hook):
					hook()

	def __layoutFinished(self):
		self.settings.menupage.addNotifier(self.fillList)
		self.settings.menupage.addNotifier(self.moveFocusToStreams)

	def saveAVDict(self):
		eDVBDB.getInstance().saveIptvServicelist()

	def readChoices(self, procx, choices):
		choice_list = choices
		with open(procx, "r") as myfile:
			procChoices = myfile.read().strip()
		if procChoices:
			choiceslist = procChoices.split(" ")
			choice_list = [(item, _(item)) for item in choiceslist]
		return choice_list

	def updateColorButtons(self):
		for color in self.colors:
			self[f"key_{color}"].setBoolean(False)

		visible_rows = self["config"].instance.size().height() // self["config"].l.getItemSize().height()
		if self["config"].getCurrentIndex() < visible_rows:  # display color buttons on the first page only

			for i, color in enumerate(self.colors):
				if i < visible_rows and i < len(self["config"].list) and self["config"].list[i][0]:
					self[f"key_{color}"].setBoolean(True)

	def fillList(self, arg=None):
		streams = []
		conflist = []
		selectedidx = 0
		self.subtitlelist = []

		for color in self.colors:
			self[f"key_{color}"].setBoolean(False)

		self.subtitlelist = self.getSubtitleList()
		print("[AudiSelection][fillList] subtitlelist=%s" % (self.subtitlelist))
		if self.settings.menupage.value == PAGE_AUDIO:
			self.setTitle(_("Select Audio Track"))
			service = self.session.nav.getCurrentService()
			self.audioTracks = audio = service and service.audioTracks()
			n = audio and audio.getNumberOfTracks() or 0
			if self.subtitlelist:
				conflist.append(getConfigListEntry(_("To Subtitle Selection"), self.settings.menupage))
			if SystemInfo["CanDownmixAC3"]:
				choice_list = [
					("downmix", _("Downmix")),
					("passthrough", _("Passthrough"))
				]
				if SystemInfo["CanProc"]:
					choice_list = self.readChoices("/proc/stb/audio/ac3_choices", choice_list)
				self.settings.downmix_ac3 = ConfigSelection(choices=choice_list, default=config.av.downmix_ac3.value)
				self.settings.downmix_ac3.addNotifier(self.changeAC3Downmix, initial_call=False)
				if SystemInfo["model"] not in ("gb7252", "vuduo4klite"):
					conflist.append(getConfigListEntry(_("AC3 / AC3+ Downmix"), self.settings.downmix_ac3, None))
				else:
					conflist.append(getConfigListEntry(_("AC3 Downmix"), self.settings.downmix_ac3, None))

			if SystemInfo["CanDownmixAC3Plus"]:
				choice_list = [
					("downmix", _("Downmix")),
					("passthrough", _("Passthrough"))
				]
				if SystemInfo["CanProc"]:
					choice_list = self.readChoices("/proc/stb/audio/ac3plus_choices", choice_list)
				self.settings.downmix_ac3plus = ConfigSelection(choices=choice_list, default=config.av.downmix_ac3plus.value)
				self.settings.downmix_ac3plus.addNotifier(self.changeAC3DownmixPlus, initial_call=False)
				conflist.append(getConfigListEntry(_("AC3+ Downmix"), self.settings.downmix_ac3plus, None))

			if SystemInfo["CanDownmixAAC"]:
				choice_list = [
					("downmix", _("Downmix")),
					("passthrough", _("Passthrough"))
				]
				if SystemInfo["CanProc"]:
					choice_list = self.readChoices("/proc/stb/audio/aac_choices", choice_list)
				self.settings.downmix_aac = ConfigSelection(choices=choice_list, default=config.av.downmix_aac.value)
				self.settings.downmix_aac.addNotifier(self.changeAACDownmix, initial_call=False)
				if SystemInfo["model"] not in ("gb7252", "vuduo4klite"):
					conflist.append(getConfigListEntry(_("AAC / AAC+ Downmix"), self.settings.downmix_aac, None))
				else:
					conflist.append(getConfigListEntry(_("AAC Downmix"), self.settings.downmix_aac, None))

			if SystemInfo["CanDownmixAACPlus"]:
				choice_list = [
					("downmix", _("Downmix")),
					("passthrough", _("Passthrough")),
					("multichannel", _("Convert to Multi-Channel PCM")),
					("force_ac3", _("Convert to AC3")),
					("force_dts", _("Convert to DTS")),
					("use_hdmi_caps", _("Use Best / Controlled by HDMI"))
				]
				if SystemInfo["CanProc"]:
					choice_list = self.readChoices("/proc/stb/audio/aacplus_choices", choice_list)
				self.settings.downmix_aacplus = ConfigSelection(choices=choice_list, default=config.av.downmix_aacplus.value)
				self.settings.downmix_aacplus.addNotifier(self.changeAACDownmixPlus, initial_call=False)
				conflist.append(getConfigListEntry(_("AAC+ Downmix"), self.settings.downmix_aacplus, None))

			if SystemInfo["CanDownmixDTS"]:
				choice_list = [
					("downmix", _("Downmix")),
					("passthrough", _("Passthrough"))
				]
				if SystemInfo["CanProc"]:
					choice_list = self.readChoices("/proc/stb/audio/dts_choices", choice_list)
				self.settings.downmix_dts = ConfigSelection(choices=choice_list, default=config.av.downmix_dts.value)
				self.settings.downmix_dts.addNotifier(self.changeDTSDownmix, initial_call=False)
				conflist.append(getConfigListEntry(_("DTS Downmix"), self.settings.downmix_dts, None))

			if SystemInfo["CanDTSHD"]:
				choice_list = [
					("downmix", _("Downmix")),
					("force_dts", _("Convert to DTS")),
					("use_hdmi_caps", _("Controlled by HDMI")),
					("multichannel", _("Convert to Multi-Channel PCM")),
					("hdmi_best", _("Passthrough"))
				]
				if SystemInfo["CanProc"]:
					choice_list = self.readChoices("/proc/stb/audio/dtshd_choices", choice_list)
				self.settings.dtshd = ConfigSelection(choices=choice_list, default=config.av.dtshd.value)
				self.settings.dtshd.addNotifier(self.changeDTSHD, initial_call=False)
				conflist.append(getConfigListEntry(_("DTS-HD MA/HR Downmix"), self.settings.dtshd, None))

			if SystemInfo["CanWMAPRO"]:
				choice_list = [
					("downmix", _("Downmix")),
					("passthrough", _("Passthrough")),
					("multichannel", _("Convert to Multi-Channel PCM")),
					("hdmi_best", _("Use Best / Controlled by HDMI"))
				]
				if SystemInfo["CanProc"]:
					choice_list = self.readChoices("/proc/stb/audio/wmapro_choices", choice_list)
				self.settings.wmapro = ConfigSelection(choices=choice_list, default=config.av.wmapro.value)
				self.settings.wmapro.addNotifier(self.changeWMAPro, initial_call=False)
				conflist.append(getConfigListEntry(_("WMA Pro Downmix"), self.settings.wmapro, None))

			conflist.append(getConfigListEntry(_("DTS / DTS-HD Transcoding"), config.av.dts_playback, None))
			conflist.append(getConfigListEntry(_("Dolby TrueHD Transcoding"), config.av.truehd_playback, None))

			if SystemInfo["CanAACTranscode"]:
				choice_list = [
					("off", _("Off")),
					("ac3", _("AC3")),
					("dts", _("DTS"))
				]
				if SystemInfo["CanProc"]:
					choice_list = self.readChoices("/proc/stb/audio/aac_transcode_choices", choice_list)
				self.settings.transcodeaac = ConfigSelection(choices=choice_list, default=config.av.transcodeaac.value)
				self.settings.transcodeaac.addNotifier(self.setAACTranscode, initial_call=False)
				conflist.append(getConfigListEntry(_("AAC Transcoding"), self.settings.transcodeaac, None))

			if SystemInfo["CanPcmMultichannel"]:
				self.settings.pcm_multichannel = ConfigOnOff(default=config.av.pcm_multichannel.value)
				self.settings.pcm_multichannel.addNotifier(self.changePCMMultichannel, initial_call=False)
				conflist.append(getConfigListEntry(_("PCM Multichannel"), self.settings.pcm_multichannel, None))

			if SystemInfo["CanBTAudio"]:
				choice_list = [("off", _("Off")), ("on", _("On"))]
				self.settings.btaudio = ConfigSelection(choices=choice_list, default=config.av.btaudio.value)
				self.settings.btaudio.addNotifier(self.changeBTAudio, initial_call=False)
				conflist.append(getConfigListEntry(_("Enable Bluetooth Audio"), self.settings.btaudio, None))

			if SystemInfo["Can3DSurround"]:
				choice_list = [
					("none", _("Off")),
					("hdmi", _("HDMI")),
					("spdif", _("SPDIF")),
					("dac", _("DAC"))
				]
				if SystemInfo["CanProc"]:
					choice_list = self.readChoices("/proc/stb/audio/3d_surround_choices", choice_list)
				self.settings.surround_3d = ConfigSelection(choices=choice_list, default=config.av.surround_3d.value)
				self.settings.surround_3d.addNotifier(self.change3DSurround, initial_call=False)
				conflist.append(getConfigListEntry(_("3D Surround"), self.settings.surround_3d, None))

			if SystemInfo["Can3DSpeaker"] and config.av.surround_3d.value != "none":
				choice_list = [
					("center", _("Center")),
					("wide", _("Wide")),
					("extrawide", _("Extra Wide"))
				]
				if SystemInfo["CanProc"]:
					choice_list = self.readChoices("/proc/stb/audio/3d_surround_speaker_position_choices", choice_list)
				self.settings.surround_3d_speaker = ConfigSelection(choices=choice_list, default=config.av.surround_3d_speaker.value)
				self.settings.surround_3d_speaker.addNotifier(self.change3DSurroundSpeaker, initial_call=False)
				conflist.append(getConfigListEntry(_("3D Surround Speaker Position"), self.settings.surround_3d_speaker, None))

			if SystemInfo["CanAutoVolume"]:
				choice_list = [
					("none", _("Off")),
					("hdmi", _("HDMI")),
					("spdif", _("SPDIF")),
					("dac", _("DAC"))
				]
				if SystemInfo["CanProc"]:
					choice_list = self.readChoices("/proc/stb/audio/avl_choices", choice_list)
				self.settings.autovolume = ConfigSelection(choices=choice_list, default=config.av.autovolume.value)
				self.settings.autovolume.addNotifier(self.changeAutoVolume, initial_call=False)
				conflist.append(getConfigListEntry(_("Auto Volume Level"), self.settings.autovolume, None))

			if n > 0:
				self.audioChannel = service.audioChannel()
				if self.audioChannel:
					choicelist = [
						("0", _("Left")),
						("1", _("Stereo")),
						("2", _("Right"))
					]
					self.settings.channelmode = ConfigSelection(choices=choicelist, default=str(self.audioChannel.getCurrentChannel()))
					self.settings.channelmode.addNotifier(self.changeMode, initial_call=False)
					conflist.append(getConfigListEntry(_("Audio Channel"), self.settings.channelmode, None))
				selectedAudio = self.audioTracks.getCurrentTrack()
				for x in range(n):
					number = str(x + 1)
					i = audio.getTrackInfo(x)
					languages = i.getLanguage().split('/')
					description = StdAudioDesc(i.getDescription())
					selected = ""
					language = ""
					if selectedAudio == x:
						selected = "X"
						selectedidx = x
					cnt = 0
					for lang in languages:
						if cnt:
							language += " / "
						if lang == "":
							language += _("Not Defined")
						elif lang in originalAudioTracks:
							language += _("Original Language")
						elif lang in LanguageCodes:
							language += _(LanguageCodes[lang][0])
						elif lang in visuallyImpairedCommentary:
							language += _("Narration")
						else:
							language += lang
						cnt += 1
					streams.append((x, "", number, description, language, selected, selectionpng if selected == "X" else None))
			else:
				conflist.append(("",))
			if SystemInfo["Canedidchecking"]:
				self.settings.bypass_edid_checking = ConfigYesNo(default=config.av.bypass_edid_checking.value)
				self.settings.bypass_edid_checking.addNotifier(self.changeEDIDChecking, initial_call=False)
				conflist.append(getConfigListEntry(_("Bypass HDMI EDID Check"), self.settings.bypass_edid_checking, None))
			if hasattr(self.infobar, "runPlugin"):
				class PluginCaller:
					def __init__(self, fnc, *args):
						self.fnc = fnc
						self.args = args

					def __call__(self, *args, **kwargs):
						self.fnc(*self.args)

				Plugins = [(p.name, PluginCaller(self.infobar.runPlugin, p)) for p in plugins.getPlugins(where=PluginDescriptor.WHERE_AUDIOMENU)]
				if len(Plugins):
					for x in Plugins:
						if x[0] != "AudioEffect":  # Always make AudioEffect Blue button.
							conflist.append(getConfigListEntry(x[0], ConfigNothing(), x[1]))

		elif self.settings.menupage.value == PAGE_SUBTITLES:
			self.setTitle(_("Subtitle Selection"))
			idx = 0
			if self.subtitlelist is not None:
				for x in self.subtitlelist:
					number = str(x[1])
					description = "?"
					language = ""
					selected = ""
					if self.selectedSubtitle and x[:4] == self.selectedSubtitle[:4]:
						selected = "X"
						selectedidx = idx
					try:
						if x[4] != "und":
							if x[4] in LanguageCodes:
								language = _(LanguageCodes[x[4]][0])
							else:
								language = x[4]
					except Exception:
						language = ""
					if x[0] == 0:
						description = "DVB"
						number = "%x" % (x[1])
					elif x[0] == 1:
						description = "teletext"
						number = "%x%02x" % (x[3] and x[3] or 8, x[2])
					elif x[0] == 2:
						types = (_("unknown"), _("embedded"), "SSA", "ASS", "SRT", "VOB", "PGS")
						try:
							description = types[x[2]]
						except Exception:
							description = _("unknown") + ": %s" % x[2]
					streams.append((x, "", number, description, language, selected, selectionpng if selected == "X" else None))
					idx += 1
			conflist.append(getConfigListEntry(_("To Audio Selection"), self.settings.menupage))

			if self.infobar.selected_subtitle and self.infobar.selected_subtitle != (0, 0, 0, 0) and ".DVDPlayer'>" not in repr(self.infobar):
				conflist.append(getConfigListEntry(_("Subtitle Quickmenu"), ConfigNothing(), None))

		self["config"].list = conflist
		self.updateColorButtons()
		self["streams"].list = streams
		self["streams"].setIndex(selectedidx)

	def __updatedInfo(self):
		self.fillList()

	def getSubtitleList(self):
		service = self.session.nav.getCurrentService()
		subtitle = service and service.subtitle()
		subtitlelist = subtitle and subtitle.getSubtitleList()
		self.selectedSubtitle = None
		if callable(AudioSelection.fillSubtitleExt):
			AudioSelection.fillSubtitleExt(subtitlelist)
		if self.subtitlesEnabled():
			self.selectedSubtitle = self.infobar.selected_subtitle
			if self.selectedSubtitle and self.selectedSubtitle[:4] == (0, 0, 0, 0):
				self.selectedSubtitle = None
			elif subtitlelist is not None and self.selectedSubtitle and not self.selectedSubtitle[:4] in (x[:4] for x in subtitlelist):
				subtitlelist.append(self.selectedSubtitle)
		return subtitlelist

	def subtitlesEnabled(self):
		try:
			return self.infobar.subtitle_window.shown or self.infobar.subtitle_window.externalSubtitleStarted
		except Exception:
			return False

	def enableSubtitle(self, subtitle):
		if self.infobar.selected_subtitle != subtitle:
			self.infobar.enableSubtitle(subtitle)

	def change3DSurround(self, surround_3d):
		config.av.surround_3d.value = surround_3d.value
		config.av.surround_3d.save()
		self.fillList()

	def change3DSurroundSpeaker(self, surround_3d_speaker):
		config.av.surround_3d_speaker.value = surround_3d_speaker.value
		config.av.surround_3d_speaker.save()

	def changeAutoVolume(self, autovolume):
		config.av.autovolume.value = autovolume.value
		config.av.autovolume.save()

	def changePCMMultichannel(self, multichan):
		if multichan.value:
			config.av.pcm_multichannel.setValue(multichan.value)
		else:
			config.av.pcm_multichannel.setValue(False)
		config.av.pcm_multichannel.save()
		self.fillList()

	def changeAC3Downmix(self, downmix):
		config.av.downmix_ac3.setValue(downmix.value)
		if SystemInfo["supportPcmMultichannel"]:
			config.av.pcm_multichannel.setValue(False)
		config.av.downmix_ac3.save()
		if SystemInfo["supportPcmMultichannel"]:
			config.av.pcm_multichannel.save()
		self.fillList()

	def changeAC3DownmixPlus(self, downmix):
		config.av.downmix_ac3plus.setValue(downmix.value)
		config.av.downmix_ac3plus.save()

	def changeDTSDownmix(self, downmix):
		config.av.downmix_dts.setValue(downmix.value)
		config.av.downmix_dts.save()

	def changeDTSHD(self, downmix):
		config.av.dtshd.setValue(downmix.value)
		config.av.dtshd.save()

	def changeAACDownmix(self, downmix):
		config.av.downmix_aac.setValue(downmix.value)
		config.av.downmix_aac.save()

	def changeAACDownmixPlus(self, downmix):
		config.av.downmix_aacplus.setValue(downmix.value)
		config.av.downmix_aacplus.save()

	def changeWMAPro(self, downmix):
		config.av.wmapro.setValue(downmix.value)
		config.av.wmapro.save()

	def setAACTranscode(self, transcode):
		config.av.transcodeaac.setValue(transcode.value)
		config.av.transcodeaac.save()

	def changeBTAudio(self, btaudio):
		config.av.btaudio.value = btaudio.value
		config.av.btaudio.save()

	def changeEDIDChecking(self, edidchecking):
		config.av.bypass_edid_checking.value = edidchecking.value
		config.av.bypass_edid_checking.save()

	def changeMode(self, mode):
		if mode is not None and self.audioChannel:
			self.audioChannel.selectChannel(int(mode.value))

	def changeAudio(self, audio):
		track = int(audio)
		if isinstance(track, int):
			service = self.session.nav.getCurrentService()
			ref = self.session.nav.getCurrentServiceReferenceOriginal()
			ref = ref and eServiceReference(ref)
			if service.audioTracks().getNumberOfTracks() > track:
				self.audioTracks.selectTrack(track)
				if isIPTV(ref):
					self.saveAVDict()

	def keyLeft(self):
		if self.focus == FOCUS_CONFIG:
			ConfigListScreen.keyLeft(self)
		elif self.focus == FOCUS_STREAMS:
			self["streams"].setIndex(0)

	def keyRight(self):
		if self.focus == FOCUS_CONFIG:
			index = self["config"].getCurrentIndex()
			if self.settings.menupage.value == PAGE_AUDIO:
				if self.subtitlelist and index == 0:  # Subtitle selection screen
					self.keyAudioSubtitle()
					self.__updatedInfo()
				elif self["config"].getCurrent()[2]:
					self["config"].getCurrent()[2]()
				else:
					ConfigListScreen.keyRight(self)
			elif self.settings.menupage.value == PAGE_SUBTITLES and self.infobar.selected_subtitle and self.infobar.selected_subtitle != (0, 0, 0, 0):
				if index == 0:  # Audio selection screen
					self.keyAudioSubtitle()
					self.__updatedInfo()
				else:
					self.session.open(QuickSubtitlesConfigMenu, self.infobar)  # sub title config screen
			else:
				ConfigListScreen.keyRight(self)
		if self.focus == FOCUS_STREAMS and self["streams"].count():
			self["streams"].setIndex(self["streams"].count() - 1)

	def keyAudioSubtitle(self):
		if self.settings.menupage.value == PAGE_AUDIO:
			self.settings.menupage.setValue("subtitles")
		else:
			self.settings.menupage.setValue("audio")

	def colorkey(self, idx):
		if idx < len(self["config"].list) and self["config"].list[idx][0]:
			self.moveFocusToConfig()
			self["config"].setCurrentIndex(idx)
			self.keyRight()

	def keyUp(self):
		if self.focus == FOCUS_CONFIG:
			self["config"].instance.moveSelection(self["config"].instance.moveUp)
		elif self.focus == FOCUS_STREAMS:
			if self["streams"].getIndex() == 0:
				self.moveFocusToConfig()
				self["config"].setCurrentIndex(len(self["config"].getList()) - 1)
			else:
				self["streams"].selectPrevious()
		self.updateColorButtons()

	def keyDown(self):
		if self.focus == FOCUS_CONFIG:
			if self["config"].getCurrentIndex() < len(self["config"].getList()) - 1:
				self["config"].instance.moveSelection(self["config"].instance.moveDown)
			else:
				self.moveFocusToStreams()
		elif self.focus == FOCUS_STREAMS:
			self["streams"].selectNext()
		self.updateColorButtons()

	def moveFocusToStreams(self, configElement=None):
		self["config"].instance.setSelectionEnable(False)
		self["streams"].style = "default"
		self.focus = FOCUS_STREAMS

	def moveFocusToConfig(self, configElement=None):
		self["config"].instance.setSelectionEnable(True)
		self["streams"].style = "notselected"
		self.focus = FOCUS_CONFIG

	def volumeUp(self):
		VolumeControl.instance and VolumeControl.instance.volUp()

	def volumeDown(self):
		VolumeControl.instance and VolumeControl.instance.volDown()

	def volumeMute(self):
		VolumeControl.instance and VolumeControl.instance.volMute()

	def keyNumberGlobal(self, number):
		if number <= len(self["streams"].list):
			self["streams"].setIndex(number - 1)
			self.keyOk()

	def keyOk(self):
		if self.focus == FOCUS_STREAMS and self["streams"].list:
			cur = self["streams"].getCurrent()
			ref = self.session.nav.getCurrentServiceReferenceOriginal()
			ref = ref and eServiceReference(ref)
			if self.settings.menupage.value == PAGE_AUDIO and cur[0] is not None:
				self.changeAudio(cur[0])
				self.__updatedInfo()
				self.runHooks(self.TYPE_AUDIO)
			if self.settings.menupage.value == PAGE_SUBTITLES and cur[0] is not None:
				if self.infobar.selected_subtitle and self.infobar.selected_subtitle[:4] == cur[0][:4]:
					if len(cur[0]) > 5 and callable(cur[0][5]):
						cur[0][5](None)
					else:
						self.enableSubtitle(None)
					selectedidx = self["streams"].getIndex()
					self.__updatedInfo()
					self["streams"].setIndex(selectedidx)
					self.runHooks(self.TYPE_SUBTITLE)
				else:
					if len(cur[0]) > 5 and callable(cur[0][5]):
						cur[0][5](cur[0])
					else:
						if self.infobar.selected_subtitle and len(self.infobar.selected_subtitle) > 5:
							self.infobar.selected_subtitle[5](None)
						self.enableSubtitle(cur[0][:5])
					self.__updatedInfo()
				if isIPTV(ref):
					self.saveAVDict()
			self.runHooks(self.TYPE_ALL)
			self.close(0)
		elif self.focus == FOCUS_CONFIG:
			self.keyRight()

	def openAutoLanguageSetup(self):
		if self.protectContextMenu and config.ParentalControl.setuppinactive.value and config.ParentalControl.config_sections.context_menus.value:
			self.session.openWithCallback(self.protectResult, PinInput, pinList=[x.value for x in config.ParentalControl.servicepin], triesEntry=config.ParentalControl.retries.servicepin, title=_("Please enter the correct pin code"), windowTitle=_("Enter pin code"))
		else:
			self.protectResult(True)

	def protectResult(self, answer):
		if answer:
			self.session.open(Setup, "autolanguagesetup")
			self.protectContextMenu = False
		elif answer is not None:
			self.session.openWithCallback(self.close, MessageBox, _("The pin code you entered is wrong."), MessageBox.TYPE_ERROR)

	def cancel(self):
		self.close(0)


class SubtitleSelection(AudioSelection):
	def __init__(self, session, infobar=None):
		AudioSelection.__init__(self, session, infobar, page=PAGE_SUBTITLES)
		self.skinName = ["AudioSelection"]


class QuickSubtitlesConfigMenu(ConfigListScreen, Screen):
	FLAG_CENTER_DVB_SUBS = 2048

	def __init__(self, session, infobar):
		Screen.__init__(self, session)
		self.infobar = infobar or self.session.infobar
		self.wait = eTimer()
		self.wait.timeout.get().append(self.resyncSubtitles)
		self.service = self.session.nav.getCurrentlyPlayingServiceReference()
		servicepath = self.service and self.service.getPath()
		if servicepath and servicepath.startswith("/") and self.service.toString().startswith("1:"):
			info = eServiceCenter.getInstance().info(self.service)
			self.service_string = info and info.getInfoString(self.service, iServiceInformation.sServiceref)
		else:
			self.service_string = self.service.toString()
		self.center_dvb_subs = ConfigYesNo(default=(eDVBDB.getInstance().getFlag(eServiceReference(self.service_string)) & self.FLAG_CENTER_DVB_SUBS) and True)
		self.center_dvb_subs.addNotifier(self.setCenterDvbSubs, initial_call=False)
		self["videofps"] = Label("")
		sub = self.infobar.selected_subtitle
		if sub[0] == 0:  # dvb
			menu = [
				getConfigMenuItem("config.subtitles.dvb_subtitles_color"),
				getConfigMenuItem("config.subtitles.dvb_subtitles_backtrans"),
				getConfigMenuItem("config.subtitles.dvb_subtitles_original_position"),
				(_("Center DVB subtitles"), self.center_dvb_subs),
				getConfigMenuItem("config.subtitles.subtitle_position"),
				getConfigMenuItem("config.subtitles.subtitle_bad_timing_delay"),
				getConfigMenuItem("config.subtitles.subtitle_noPTSrecordingdelay"),
			]
		elif sub[0] == 1:  # teletext
			menu = [
				getConfigMenuItem("config.subtitles.ttx_subtitle_colors"),
				getConfigMenuItem("config.subtitles.ttx_subtitle_original_position"),
				getConfigMenuItem("config.subtitles.subtitle_fontsize"),
				getConfigMenuItem("config.subtitles.subtitle_position"),
				getConfigMenuItem("config.subtitles.subtitle_rewrap"),
				getConfigMenuItem("config.subtitles.subtitle_borderwidth"),
				getConfigMenuItem("config.subtitles.showbackground"),
				getConfigMenuItem("config.subtitles.subtitle_alignment"),
				getConfigMenuItem("config.subtitles.subtitle_bad_timing_delay"),
				getConfigMenuItem("config.subtitles.subtitle_noPTSrecordingdelay"),
			]
		else: 		# pango
			menu = [
				getConfigMenuItem("config.subtitles.pango_subtitles_delay"),
				getConfigMenuItem("config.subtitles.pango_subtitle_colors"),
				getConfigMenuItem("config.subtitles.pango_subtitle_fontswitch"),
				getConfigMenuItem("config.subtitles.colourise_dialogs"),
				getConfigMenuItem("config.subtitles.subtitle_fontsize"),
				getConfigMenuItem("config.subtitles.subtitle_position"),
				getConfigMenuItem("config.subtitles.subtitle_alignment"),
				getConfigMenuItem("config.subtitles.subtitle_rewrap"),
				getConfigMenuItem("config.subtitles.subtitle_borderwidth"),
				getConfigMenuItem("config.subtitles.showbackground"),
				getConfigMenuItem("config.subtitles.pango_subtitle_removehi"),
				getConfigMenuItem("config.subtitles.pango_subtitles_fps"),
			]
			self["videofps"].setText(_("Video: %s fps") % (self.getFps().rstrip(".000")))
		ConfigListScreen.__init__(self, menu, self.session, on_change=self.changedEntry)
		self["actions"] = NumberActionMap(["SetupActions"], {
			"cancel": self.cancel,
			"ok": self.ok,
		}, -2)
		self.onLayoutFinish.append(self.layoutFinished)

	def setCenterDvbSubs(self, configElement):
		if configElement.value:
			eDVBDB.getInstance().addFlag(eServiceReference(self.service_string), self.FLAG_CENTER_DVB_SUBS)
			config.subtitles.dvb_subtitles_centered.value = True
		else:
			eDVBDB.getInstance().removeFlag(eServiceReference(self.service_string), self.FLAG_CENTER_DVB_SUBS)
			config.subtitles.dvb_subtitles_centered.value = False

	def layoutFinished(self):
		if not self["videofps"].text:
			self.instance.resize(eSize(self.instance.size().width(), self["config"].l.getItemSize().height() * len(self["config"].getList()) + 10))

	def changedEntry(self):
		if self["config"].getCurrent() in [getConfigMenuItem("config.subtitles.pango_subtitles_delay"), getConfigMenuItem("config.subtitles.pango_subtitles_fps")]:
			self.wait.start(500, True)

	def resyncSubtitles(self):
		self.infobar.setSeekState(self.infobar.SEEK_STATE_PAUSE)
		self.infobar.setSeekState(self.infobar.SEEK_STATE_PLAY)

	def getFps(self):
		service = self.session.nav.getCurrentService()
		info = service and service.info()
		if not info:
			return ""
		fps = info.getInfo(iServiceInformation.sFrameRate)
		if fps > 0:
			return "%6.3f" % (fps / 1000.0)
		return ""

	def cancel(self):
		self.center_dvb_subs.removeNotifier(self.setCenterDvbSubs)
		self.close()

	def ok(self):
		config.subtitles.save()
		self.close()
