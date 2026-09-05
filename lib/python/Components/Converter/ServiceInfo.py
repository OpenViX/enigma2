from enigma import eAVSwitch, iServiceInformation, iPlayableService, eServiceReference
from Components.Converter.Converter import Converter
from Components.Converter.Poll import Poll
from Components.Converter.VAudioInfo import StdAudioDesc
from Components.Element import cached
from Screens.InfoBarGenerics import hasActiveSubservicesForCurrentChannel
from Tools.Transponder import ConvertToHumanReadable

WIDESCREEN = [1, 3, 4, 7, 8, 0xB, 0xC, 0xF, 0x10]


# Skin-facing audio codec booleans.  Values are exact descriptions from
# iAudioTrackInfo after the codec work in eServiceMP3/eServiceDVB.  Legacy
# aliases are accepted so skins also work with older/native service paths.
AUDIO_CODEC_TYPES = {
	"IsDolbyDigital": ("Dolby Digital", "AC3"),
	"IsAudioAC3": ("Dolby Digital", "AC3"),
	"IsDolbyDigitalPlus": ("Dolby Digital +", "Dolby Digital Plus", "EAC3", "AC3+"),
	"IsAudioEAC3": ("Dolby Digital +", "Dolby Digital Plus", "EAC3", "AC3+"),
	"IsDolbyAtmos": ("Dolby Atmos", "Dolby Atmos (TrueHD)"),
	"IsAudioAtmos": ("Dolby Atmos", "Dolby Atmos (TrueHD)"),
	"IsDolbyTrueHD": ("Dolby TrueHD", "TrueHD", "Dolby Atmos (TrueHD)"),
	"IsAudioTrueHD": ("Dolby TrueHD", "TrueHD", "Dolby Atmos (TrueHD)"),
	"IsDolbyAC4": ("Dolby AC-4", "Dolby AC4", "AC-4", "AC4"),

	"IsDTS": ("DTS",),
	"IsDTSHD": ("DTS-HD", "DTSHD"),
	"IsDTSHDMA": ("DTS-HD MA", "DTSHD MA", "DTS-HD Master Audio", "DTSHD Master Audio", "DTS-HD MA + DTS:X", "DTS-HD MA + DTS:X IMAX"),
	"IsDTSHDHRA": ("DTS-HD HRA", "DTSHD HRA", "DTS-HD High Resolution", "DTSHD High Resolution", "DTS-HD High Resolution Audio", "DTSHD High Resolution Audio"),
	"IsDTSX": ("DTS:X", "DTS-HD MA + DTS:X"),
	"IsDTSXIMAX": ("DTS:X IMAX", "DTS-HD MA + DTS:X IMAX"),
	"IsDTSXPro": ("DTS:X Pro",),
	"IsDTSExpress": ("DTS Express",),
	"IsDTSES": ("DTS-ES", "DTS ES"),
	"IsDTS9624": ("DTS 96/24", "DTS 96-24"),

	"IsAAC": ("AAC",),
	"IsAACLC": ("AAC-LC", "AACLC"),
	"IsAACLD": ("AAC-LD", "AACLD"),
	"IsAACELD": ("AAC-ELD", "AACELD"),
	"IsHEAAC": ("HE-AAC", "HEAAC"),
	"IsHEAACV2": ("HE-AAC v2", "HEAAC v2"),
	"IsXHEAAC": ("xHE-AAC", "xHEAAC"),

	"IsFLAC": ("FLAC",),
	"IsALAC": ("ALAC",),
	"IsOpus": ("Opus",),
	"IsVorbis": ("Vorbis",),
	"IsWavPack": ("WavPack",),
	"IsAPE": ("APE",),
	"IsTTA": ("TTA",),
	"IsMLP": ("MLP",),
	"IsRealAudio": ("RealAudio", "RealAudio 14.4", "RealAudio 28.8"),
	"IsRealAudio144": ("RealAudio 14.4",),
	"IsRealAudio288": ("RealAudio 28.8",),
	"IsWMALossless": ("WMA Lossless",),
	"IsWMAPro": ("WMA Pro",),
	"IsWMA": ("WMA",),
	"IsAMRWB": ("AMR-WB", "AMRWB"),
	"IsAMR": ("AMR",),
	"IsSpeex": ("Speex",),
	"IsDSD": ("DSD",),
	"IsMP3": ("MP3",),
	"IsMP2": ("MP2",),
	"IsMPEGLayer1": ("MPEG Layer I",),
	"IsMPEG1LayerII": ("MPEG1 Layer II",),
	"IsALaw": ("A-law", "A law"),
	"IsMuLaw": ("mu-law", "mu law"),
	"IsPCM": ("PCM",),
	"IsLPCM": ("LPCM", "IPCM"),
}

AUDIO_CODEC_DESCRIPTIONS = frozenset(
	description
	for descriptions in AUDIO_CODEC_TYPES.values()
	for description in descriptions
)

# Canonical selected-track codec label and dynamic icon key.  The icon key is
# deliberately path- and extension-free; the skin chooses its own icon path.
# AudioIcon prefers <path>/icon_<key>.svg, then falls back to .png.
AUDIO_CODEC_DISPLAY = (
	(("Dolby Digital", "AC3"), "Dolby Digital", "dolby-digital"),
	(("Dolby Digital +", "Dolby Digital Plus", "EAC3", "AC3+"), "Dolby Digital +", "dolby-digital-plus"),
	(("Dolby Atmos",), "Dolby Atmos", "dolby-atmos"),
	(("Dolby Atmos (TrueHD)",), "Dolby Atmos (TrueHD)", "dolby-atmos"),
	(("Dolby TrueHD", "TrueHD"), "Dolby TrueHD", "dolby-truehd"),
	(("Dolby AC-4", "Dolby AC4", "AC-4", "AC4"), "Dolby AC-4", "dolby-ac4"),

	(("DTS",), "DTS", "dts"),
	(("DTS-HD", "DTSHD"), "DTS-HD", "dts-hd"),
	(("DTS-HD MA", "DTSHD MA", "DTS-HD Master Audio", "DTSHD Master Audio"), "DTS-HD MA", "dts-hd-ma"),
	(("DTS-HD HRA", "DTSHD HRA", "DTS-HD High Resolution", "DTSHD High Resolution", "DTS-HD High Resolution Audio", "DTSHD High Resolution Audio"), "DTS-HD HRA", "dts-hd-hra"),
	(("DTS:X",), "DTS:X", "dts-x"),
	(("DTS-HD MA + DTS:X",), "DTS-HD MA + DTS:X", "dts-x"),
	(("DTS:X IMAX",), "DTS:X IMAX", "dts-x-imax"),
	(("DTS-HD MA + DTS:X IMAX",), "DTS-HD MA + DTS:X IMAX", "dts-x-imax"),
	(("DTS:X Pro",), "DTS:X Pro", "dts-x-pro"),
	(("DTS Express",), "DTS Express", "dts-express"),
	(("DTS-ES", "DTS ES"), "DTS-ES", "dts-es"),
	(("DTS 96/24", "DTS 96-24"), "DTS 96/24", "dts-96-24"),

	(("AAC",), "AAC", "aac"),
	(("AAC-LC", "AACLC"), "AAC-LC", "aac-lc"),
	(("AAC-LD", "AACLD"), "AAC-LD", "aac-ld"),
	(("AAC-ELD", "AACELD"), "AAC-ELD", "aac-eld"),
	(("HE-AAC", "HEAAC"), "HE-AAC", "he-aac"),
	(("HE-AAC v2", "HEAAC v2"), "HE-AAC v2", "he-aac-v2"),
	(("xHE-AAC", "xHEAAC"), "xHE-AAC", "xhe-aac"),

	(("FLAC",), "FLAC", "flac"),
	(("ALAC",), "ALAC", "alac"),
	(("Opus",), "Opus", "opus"),
	(("Vorbis",), "Vorbis", "vorbis"),
	(("WavPack",), "WavPack", "wavpack"),
	(("APE",), "APE", "ape"),
	(("TTA",), "TTA", "tta"),
	(("MLP",), "MLP", "mlp"),
	(("RealAudio",), "RealAudio", "realaudio"),
	(("RealAudio 14.4",), "RealAudio 14.4", "realaudio-14-4"),
	(("RealAudio 28.8",), "RealAudio 28.8", "realaudio-28-8"),
	(("WMA Lossless",), "WMA Lossless", "wma-lossless"),
	(("WMA Pro",), "WMA Pro", "wma-pro"),
	(("WMA",), "WMA", "wma"),
	(("AMR-WB", "AMRWB"), "AMR-WB", "amr-wb"),
	(("AMR",), "AMR", "amr"),
	(("Speex",), "Speex", "speex"),
	(("DSD",), "DSD", "dsd"),
	(("MP3",), "MP3", "mp3"),
	(("MP2",), "MP2", "mp2"),
	(("MPEG Layer I",), "MPEG Layer I", "mpeg-layer-i"),
	(("MPEG1 Layer II",), "MPEG1 Layer II", "mpeg1-layer-ii"),
	(("A-law", "A law"), "A-law", "a-law"),
	(("mu-law", "mu law"), "mu-law", "mu-law"),
	(("PCM",), "PCM", "pcm"),
	(("LPCM", "IPCM"), "LPCM", "lpcm"),
)

AUDIO_CODEC_INFO = {
	description: (label, icon)
	for descriptions, label, icon in AUDIO_CODEC_DISPLAY
	for description in descriptions
}

# Exact selected-track channel-count flags.  These use the negotiated channel
# count exposed by iAudioTrackInfo; they do not infer layout from codec names.
AUDIO_CHANNEL_TYPES = {
	"IsAudioMono": 1,
	"IsAudio10": 1,
	"IsAudioStereo": 2,
	"IsAudio20": 2,
	"IsAudio51": 6,
	"IsAudio71": 8,
}

AUDIO_CHANNEL_LABELS = {
	1: "1.0",
	2: "2.0",
	6: "5.1",
	8: "7.1",
}


def getCurrentAudioChannels(service):
	audio = service and service.audioTracks()
	if not audio:
		return 0
	current = audio.getCurrentTrack()
	if current < 0 or current >= audio.getNumberOfTracks():
		return 0
	track = audio.getTrackInfo(current)
	return track.getChannels() if track else 0


def getCurrentAudioCodec(service):
	audio = service and service.audioTracks()
	if not audio:
		return ""
	current = audio.getCurrentTrack()
	if current < 0 or current >= audio.getNumberOfTracks():
		return ""
	track = audio.getTrackInfo(current)
	if not track:
		return ""
	description = track.getDescription() or ""
	# Preserve exact known codec names before the legacy normalizer.  This is
	# important for names such as ALAC and the refined DTS-HD/DTS:X labels.
	if description not in AUDIO_CODEC_DESCRIPTIONS:
		description = StdAudioDesc(description)
	return description


def getVideoHeight(info):
	val = eAVSwitch.getInstance().getResolutionY(0)
	return val if val else info.getInfo(iServiceInformation.sVideoHeight)


def getVideoHeightStr(info, convert=lambda x: "%d" % x if x > 0 else "?", instance=None):
	val = eAVSwitch.getInstance().getResolutionY(0)
	return convert(val) if val else instance.getServiceInfoString(info, iServiceInformation.sVideoHeight, convert)


def getVideoWidth(info):
	val = eAVSwitch.getInstance().getResolutionX(0)
	return val if val else info.getInfo(iServiceInformation.sVideoWidth)


def getVideoWidthStr(info, convert=lambda x: "%d" % x if x > 0 else "?", instance=None):
	val = eAVSwitch.getInstance().getResolutionX(0)
	return convert(val) if val else instance.getServiceInfoString(info, iServiceInformation.sVideoWidth, convert)


def getFrameRate(info):
	val = eAVSwitch.getInstance().getFrameRate(0)
	return val if val else info.getInfo(iServiceInformation.sFrameRate)


def getFrameRateStr(info, convert=lambda x: "%d" % x if x > 0 else "", instance=None):
	val = eAVSwitch.getInstance().getFrameRate(0)
	return convert(val) if val else instance.getServiceInfoString(info, iServiceInformation.sFrameRate, convert)


def getProgressive(info):
	return eAVSwitch.getInstance().getProgressive()


def getProgressiveStr(info):
	return "p" if eAVSwitch.getInstance().getProgressive() else "i"


class ServiceInfo(Poll, Converter):
	HAS_TELETEXT = 1
	IS_MULTICHANNEL = 2
	IS_STEREO = 3
	IS_CRYPTED = 4
	IS_WIDESCREEN = 5
	IS_NOT_WIDESCREEN = 6
	SUBSERVICES_AVAILABLE = 7
	XRES = 8
	YRES = 9
	APID = 10
	VPID = 11
	PCRPID = 12
	PMTPID = 13
	TXTPID = 14
	TSID = 15
	ONID = 16
	SID = 17
	FRAMERATE = 18
	TRANSFERBPS = 19
	HAS_HBBTV = 20
	AUDIOTRACKS_AVAILABLE = 21
	SUBTITLES_AVAILABLE = 22
	EDITMODE = 23
	IS_STREAM = 24
	IS_SD = 25
	IS_HD = 26
	IS_1080 = 27
	IS_720 = 28
	IS_576 = 29
	IS_480 = 30
	IS_4K = 31
	FREQ_INFO = 32
	PROGRESSIVE = 33
	VIDEO_INFO = 34
	IS_SD_AND_WIDESCREEN = 35
	IS_SD_AND_NOT_WIDESCREEN = 36
	IS_SDR = 37
	IS_HDR = 38
	IS_HDR10 = 39
	IS_HLG = 40
	IS_VIDEO_MPEG2 = 41
	IS_VIDEO_AVC = 42
	IS_VIDEO_HEVC = 43
	IS_SOFTCSA = 44
	IS_STREAM_RELAY = 45
	IS_AUDIO_CODEC = 46
	IS_AUDIO_CHANNEL = 47
	AUDIO_CHANNELS = 48
	AUDIO_CODEC = 49
	AUDIO_CODEC_ICON = 50
	AUDIO_CODEC_CHANNELS = 51

	def __init__(self, type):
		Poll.__init__(self)
		Converter.__init__(self, type)
		self.poll_interval = 5000
		self.poll_enabled = True
		self.audio_codec = AUDIO_CODEC_TYPES.get(type)
		if self.audio_codec is not None:
			self.type = self.IS_AUDIO_CODEC
			self.interesting_events = (iPlayableService.evUpdatedInfo, iPlayableService.evStart)
			return
		self.audio_channel = AUDIO_CHANNEL_TYPES.get(type)
		if self.audio_channel is not None:
			self.type = self.IS_AUDIO_CHANNEL
			self.interesting_events = (iPlayableService.evUpdatedInfo, iPlayableService.evStart)
			return
		if type == "AudioChannels":
			self.type = self.AUDIO_CHANNELS
			self.interesting_events = (iPlayableService.evUpdatedInfo, iPlayableService.evStart)
			return
		if type == "AudioCodec":
			self.type = self.AUDIO_CODEC
			self.interesting_events = (iPlayableService.evUpdatedInfo, iPlayableService.evStart)
			return
		if type == "AudioCodecIcon":
			self.type = self.AUDIO_CODEC_ICON
			self.interesting_events = (iPlayableService.evUpdatedInfo, iPlayableService.evStart)
			return
		if type == "AudioCodecChannels":
			self.type = self.AUDIO_CODEC_CHANNELS
			self.interesting_events = (iPlayableService.evUpdatedInfo, iPlayableService.evStart)
			return
		self.type, self.interesting_events = {
			"HasTelext": (self.HAS_TELETEXT, (iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"IsMultichannel": (self.IS_MULTICHANNEL, (iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"IsStereo": (self.IS_STEREO, (iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"IsCrypted": (self.IS_CRYPTED, (iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"IsSoftCSA": (self.IS_SOFTCSA, (iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"IsStreamRelay": (self.IS_STREAM_RELAY, (iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"IsWidescreen": (self.IS_WIDESCREEN, (iPlayableService.evVideoSizeChanged, iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"IsNotWidescreen": (self.IS_NOT_WIDESCREEN, (iPlayableService.evVideoSizeChanged, iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"SubservicesAvailable": (self.SUBSERVICES_AVAILABLE, (iPlayableService.evStart,)),
			"VideoWidth": (self.XRES, (iPlayableService.evVideoSizeChanged,)),
			"VideoHeight": (self.YRES, (iPlayableService.evVideoSizeChanged,)),
			"AudioPid": (self.APID, (iPlayableService.evUpdatedInfo,)),
			"VideoPid": (self.VPID, (iPlayableService.evUpdatedInfo,)),
			"PcrPid": (self.PCRPID, (iPlayableService.evUpdatedInfo,)),
			"PmtPid": (self.PMTPID, (iPlayableService.evUpdatedInfo,)),
			"TxtPid": (self.TXTPID, (iPlayableService.evUpdatedInfo,)),
			"TsId": (self.TSID, (iPlayableService.evUpdatedInfo,)),
			"OnId": (self.ONID, (iPlayableService.evUpdatedInfo,)),
			"Sid": (self.SID, (iPlayableService.evUpdatedInfo,)),
			"Framerate": (self.FRAMERATE, (iPlayableService.evVideoFramerateChanged, iPlayableService.evUpdatedInfo,)),
			"Progressive": (self.PROGRESSIVE, (iPlayableService.evVideoProgressiveChanged, iPlayableService.evUpdatedInfo,)),
			"VideoInfo": (self.VIDEO_INFO, (iPlayableService.evVideoSizeChanged, iPlayableService.evVideoFramerateChanged, iPlayableService.evVideoProgressiveChanged, iPlayableService.evUpdatedInfo,)),
			"TransferBPS": (self.TRANSFERBPS, (iPlayableService.evUpdatedInfo,)),
			"HasHBBTV": (self.HAS_HBBTV, (iPlayableService.evUpdatedInfo, iPlayableService.evHBBTVInfo, iPlayableService.evStart)),
			"AudioTracksAvailable": (self.AUDIOTRACKS_AVAILABLE, (iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"SubtitlesAvailable": (self.SUBTITLES_AVAILABLE, (iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"Freq_Info": (self.FREQ_INFO, (iPlayableService.evUpdatedInfo,)),
			"Editmode": (self.EDITMODE, (iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"IsStream": (self.IS_STREAM, (iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"IsSD": (self.IS_SD, (iPlayableService.evVideoSizeChanged, iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"IsHD": (self.IS_HD, (iPlayableService.evVideoSizeChanged, iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"IsSDAndWidescreen": (self.IS_SD_AND_WIDESCREEN, (iPlayableService.evVideoSizeChanged, iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"IsSDAndNotWidescreen": (self.IS_SD_AND_NOT_WIDESCREEN, (iPlayableService.evVideoSizeChanged, iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"Is1080": (self.IS_1080, (iPlayableService.evVideoSizeChanged, iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"Is720": (self.IS_720, (iPlayableService.evVideoSizeChanged, iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"Is576": (self.IS_576, (iPlayableService.evVideoSizeChanged, iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"Is480": (self.IS_480, (iPlayableService.evVideoSizeChanged, iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"Is4K": (self.IS_4K, (iPlayableService.evVideoSizeChanged, iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"IsSDR": (self.IS_SDR, (iPlayableService.evVideoGammaChanged, iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"IsHDR": (self.IS_HDR, (iPlayableService.evVideoGammaChanged, iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"IsHDR10": (self.IS_HDR10, (iPlayableService.evVideoGammaChanged, iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"IsHLG": (self.IS_HLG, (iPlayableService.evVideoGammaChanged, iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"IsVideoMPEG2": (self.IS_VIDEO_MPEG2, (iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"IsVideoAVC": (self.IS_VIDEO_AVC, (iPlayableService.evUpdatedInfo, iPlayableService.evStart)),
			"IsVideoHEVC": (self.IS_VIDEO_HEVC, (iPlayableService.evUpdatedInfo, iPlayableService.evVideoSizeChanged)),
		}[type]

	def isVideoService(self, info, service):
		if not service or not isinstance(service, eServiceReference):
			serviceInfo = info.getInfoString(iServiceInformation.sServiceref).split(':')
		else:
			serviceInfo = info.getInfoString(service, iServiceInformation.sServiceref).split(':')

		return len(serviceInfo) < 3 or serviceInfo[2] != '2'

	def getServiceInfoString(self, info, what, convert=lambda x: "%d" % x):
		v = info.getInfo(what)
		if v == -1:
			return _("N/A")
		if v == -2:
			return info.getInfoString(what)
		return convert(v)

	@cached
	def getBoolean(self):
		service = self.source.service
		isRef = isinstance(service, eServiceReference)
		info = service.info() if (service and not isRef) else None
		if not info:
			return False
		video_height = 0
		video_width = 0  # noqa: F841
		video_aspect = None

		video_height = getVideoHeight(info)
		video_width = getVideoWidth(info)  # noqa: F841
		# print(f"[ServiceInfo] video_height:{video_height} video_width:{video_width}")
		if not isRef:
			video_aspect = info.getInfo(iServiceInformation.sAspect)

		if self.type == self.HAS_TELETEXT and not isRef:
			tpid = info.getInfo(iServiceInformation.sTXTPID)
			return tpid > 0
		elif self.type == self.IS_AUDIO_CODEC and not isRef:
			audio = service.audioTracks()
			if not audio:
				return False
			current = audio.getCurrentTrack()
			if current < 0 or current >= audio.getNumberOfTracks():
				return False
			track = audio.getTrackInfo(current)
			description = track.getDescription() or ""
			# Prefer an already-known exact codec description.  Only run the
			# legacy normalizer for descriptions we do not recognize directly.
			# This avoids aliases such as ALAC being rewritten as another codec.
			if description not in AUDIO_CODEC_DESCRIPTIONS:
				description = StdAudioDesc(description)
			return description in self.audio_codec
		elif self.type == self.IS_AUDIO_CHANNEL and not isRef:
			return getCurrentAudioChannels(service) == self.audio_channel
		elif self.type in (self.IS_MULTICHANNEL, self.IS_STEREO) and not isRef:
			# FIXME. but currently iAudioTrackInfo doesn't provide more information.
			audio = service.audioTracks()
			if audio:
				n = audio.getNumberOfTracks()
				idx = 0
				while idx < n:
					i = audio.getTrackInfo(idx)
					description = StdAudioDesc(i.getDescription())
					if description and description.split()[0] in ("AC3+", "AC3", "Dolby", "TrueHD", "DTS-HD", "DTS", "HE-AAC", "AC4", "AAC+", "IPCM", "LPCM", "WMA Pro"):
						if self.type == self.IS_MULTICHANNEL:
							return True
						elif self.type == self.IS_STEREO:
							return False
					idx += 1
				if self.type == self.IS_MULTICHANNEL:
					return False
				elif self.type == self.IS_STEREO:
					return True
			return False
		elif self.type == self.IS_CRYPTED and not isRef:
			return info.getInfo(iServiceInformation.sIsCrypted) == 1 and info.getInfo(iServiceInformation.sIsSoftCSA) != 1
		elif self.type == self.IS_SOFTCSA and not isRef:
			return info.getInfo(iServiceInformation.sIsSoftCSA) == 1
		elif self.type == self.IS_STREAM_RELAY and not isRef:
			refstr = info.getInfoString(iServiceInformation.sServiceref)
			if "9999" in refstr or "17999" in refstr and "127.0.0.1" in refstr or "localhost" in refstr or "0.0.0.0" in refstr and info.getInfo(iServiceInformation.sIsCrypted) == 1:
				return True
		elif self.type == self.SUBSERVICES_AVAILABLE and not isRef:
			return hasActiveSubservicesForCurrentChannel(service)
		elif self.type == self.HAS_HBBTV and not isRef:
			return info.getInfoString(iServiceInformation.sHBBTVUrl) != ""
		elif self.type == self.AUDIOTRACKS_AVAILABLE and not isRef:
			audio = service.audioTracks()
			return bool(audio) and audio.getNumberOfTracks() > 1
		elif self.type == self.SUBTITLES_AVAILABLE and not isRef:
			subtitle = service and service.subtitle()
			subtitlelist = subtitle and subtitle.getSubtitleList()
			if subtitlelist:
				return len(subtitlelist) > 0
			return False
		elif self.type == self.EDITMODE:
			return hasattr(self.source, "editmode") and not not self.source.editmode
		elif self.type == self.IS_STREAM and not isRef:
			refstr = info.getInfoString(iServiceInformation.sServiceref)
			if "4097" in refstr or "5001" in refstr or "5002" in refstr or "9999" in refstr:
				return service.streamed() is not None
			return False
		elif self.isVideoService(info, service):
			if self.type == self.IS_WIDESCREEN:
				return video_aspect in WIDESCREEN
			elif self.type == self.IS_NOT_WIDESCREEN:
				return video_aspect not in WIDESCREEN
			elif self.type == self.IS_HD:
				return video_width > 1025 and video_width <= 1920 and video_height >= 481 and video_height < 1440 or video_width >= 960 and video_height == 720
			elif self.type == self.IS_SD:
				return video_width > 1 and video_width <= 1024 and video_height > 1 and video_height <= 578
			elif self.type == self.IS_SD_AND_WIDESCREEN:
				return video_height < 578 and video_aspect in WIDESCREEN
			elif self.type == self.IS_SD_AND_NOT_WIDESCREEN:
				return video_height < 578 and video_aspect not in WIDESCREEN
			elif self.type == self.IS_1080:
				return video_width >= 1367 and video_width <= 2400 and video_height >= 768 and video_height <= 1440
			elif self.type == self.IS_720:
				return video_width >= 1025 and video_width <= 1366 and video_height >= 481 and video_height <= 768 or video_width >= 960 and video_height == 720
			elif self.type == self.IS_576:
				return video_width > 1 and video_width <= 1024 and video_height > 481 and video_height <= 578
			elif self.type == self.IS_480:
				return video_width > 1 and video_width <= 1024 and video_height > 1 and video_height <= 480
			elif self.type == self.IS_4K:
				return video_width >= 1921 and video_height >= 1440
			elif self.type == self.PROGRESSIVE and not isRef:
				return bool(self._getProgressive(info))
			elif self.type == self.IS_SDR and not isRef:
				return info.getInfo(iServiceInformation.sGamma) == 0
			elif self.type == self.IS_HDR and not isRef:
				hdr = info.getInfo(iServiceInformation.sHDRType)
				return hdr == 3 if hdr > 0 else info.getInfo(iServiceInformation.sGamma) == 1
			elif self.type == self.IS_HDR10 and not isRef:
				hdr = info.getInfo(iServiceInformation.sHDRType)
				return hdr == 1 if hdr > 0 else info.getInfo(iServiceInformation.sGamma) == 2
			elif self.type == self.IS_HLG and not isRef:
				hdr = info.getInfo(iServiceInformation.sHDRType)
				return hdr == 2 if hdr > 0 else info.getInfo(iServiceInformation.sGamma) == 3
			elif self.type == self.IS_VIDEO_MPEG2 and not isRef:
				return info.getInfo(iServiceInformation.sVideoType) == 0
			elif self.type == self.IS_VIDEO_AVC and not isRef:
				return info.getInfo(iServiceInformation.sVideoType) == 1
			elif self.type == self.IS_VIDEO_HEVC and not isRef:
				if info.getInfoString(iServiceInformation.sServiceref).startswith("5002") and info.getInfo(iServiceInformation.sVideoType) == -1:
					return 7
				else:
					return info.getInfo(iServiceInformation.sVideoType) == 7
		return False

	boolean = property(getBoolean)

	@cached
	def getText(self):
		service = self.source.service
		info = service and service.info()
		if not info:
			return ""
		if self.type == self.XRES:
			return getVideoWidthStr(info, instance=self)
		elif self.type == self.YRES:
			return getVideoHeightStr(info, instance=self)
		elif self.type == self.APID:
			return self.getServiceInfoString(info, iServiceInformation.sAudioPID)
		elif self.type == self.VPID:
			return self.getServiceInfoString(info, iServiceInformation.sVideoPID)
		elif self.type == self.PCRPID:
			return self.getServiceInfoString(info, iServiceInformation.sPCRPID)
		elif self.type == self.PMTPID:
			return self.getServiceInfoString(info, iServiceInformation.sPMTPID)
		elif self.type == self.TXTPID:
			return self.getServiceInfoString(info, iServiceInformation.sTXTPID)
		elif self.type == self.TSID:
			return self.getServiceInfoString(info, iServiceInformation.sTSID)
		elif self.type == self.ONID:
			return self.getServiceInfoString(info, iServiceInformation.sONID)
		elif self.type == self.SID:
			return self.getServiceInfoString(info, iServiceInformation.sSID)
		elif self.type == self.FRAMERATE:
			return f"{(getFrameRate(info) + 500) // 1000} fps"
		elif self.type == self.PROGRESSIVE:
			return getProgressiveStr(info, instance=self)
		elif self.type == self.AUDIO_CHANNELS:
			channels = getCurrentAudioChannels(service)
			return AUDIO_CHANNEL_LABELS.get(channels, f"{channels} ch" if channels > 0 else "")
		elif self.type in (self.AUDIO_CODEC, self.AUDIO_CODEC_CHANNELS, self.AUDIO_CODEC_ICON):
			description = getCurrentAudioCodec(service)
			label, icon = AUDIO_CODEC_INFO.get(description, (description, ""))
			if self.type == self.AUDIO_CODEC_ICON:
				return f"icon_{icon}" if icon else ""
			if self.type == self.AUDIO_CODEC_CHANNELS:
				channels = getCurrentAudioChannels(service)
				channel_label = AUDIO_CHANNEL_LABELS.get(channels, f"{channels} ch" if channels > 0 else "")
				return f"{label} {channel_label}".strip()
			return label
		elif self.type == self.TRANSFERBPS:
			return self.getServiceInfoString(info, iServiceInformation.sTransferBPS, lambda x: "%d kB/s" % (x // 1024))
		elif self.type == self.HAS_HBBTV:
			return info.getInfoString(iServiceInformation.sHBBTVUrl)
		elif self.type == self.FREQ_INFO:
			feinfo = service.frontendInfo()
			if feinfo is None:
				return ""
			feraw = feinfo.getAll(False)
			if feraw is None:
				return ""
			fedata = ConvertToHumanReadable(feraw)
			if fedata is None:
				return ""
			frequency = fedata.get("frequency")
			sr_txt = "Sr:"
			polarization = fedata.get("polarization_abbreviation")
			if polarization is None:
				polarization = ""
			symbolrate = str(int(fedata.get("symbol_rate", 0)))
			if symbolrate == "0":
				sr_txt = ""
				symbolrate = ""
			fec = fedata.get("fec_inner")
			if fec is None:
				fec = ""
			out = f"Freq: {frequency} {polarization} {sr_txt} {symbolrate} {fec}"
			return out
		elif self.type == self.VIDEO_INFO:
			return f"{getVideoWidthStr(info, instance=self)}x{getVideoHeightStr(info, instance=self)}{getProgressiveStr(info)}{(getFrameRate(info) + 500) // 1000}"
		return ""

	text = property(getText)

	@cached
	def getValue(self):
		service = self.source.service
		info = service and service.info()
		if not info:
			return -1
		if self.type == self.XRES:
			return str(getVideoWidth(info))
		elif self.type == self.YRES:
			return str(getVideoHeight(info))
		elif self.type == self.FRAMERATE:
			return str(getFrameRate(info))
		return -1

	value = property(getValue)

	def changed(self, what):
		if what[0] != self.CHANGED_SPECIFIC or what[1] in self.interesting_events:
			Converter.changed(self, what)
