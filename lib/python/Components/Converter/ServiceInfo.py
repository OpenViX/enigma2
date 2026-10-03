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


# Canonical video codec label and dynamic icon key, keyed by the raw
# iServiceInformation.sVideoType stream-type value.  The icon key is
# deliberately path- and extension-free; the skin chooses its own icon path.
VIDEO_CODEC_DISPLAY = (
	(0, "MPEG-2", "mpeg2"),
	(1, "H.264", "avc"),
	(2, "H.263", "h263"),
	(3, "VC-1", "vc1"),
	(4, "MPEG-4", "mpeg4"),
	(5, "VC-1 SM", "vc1-sm"),
	(6, "MPEG-1", "mpeg1"),
	(7, "H.265", "hevc"),
	(8, "VP8", "vp8"),
	(9, "VP9", "vp9"),
	(10, "XVID", "xvid"),
	(13, "DIVX 3.11", "divx"),
	(14, "DIVX 4", "divx"),
	(15, "DIVX 5", "divx"),
	(16, "AVS", "avs"),
	(18, "VP6", "vp6"),
	(21, "SPARK", "spark"),
	(40, "AVS2", "avs2"),
)

VIDEO_CODEC_INFO = {videoType: (label, icon) for videoType, label, icon in VIDEO_CODEC_DISPLAY}


def getCurrentVideoCodec(info):
	videoType = info.getInfo(iServiceInformation.sVideoType)
	# Some stream-relay paths never report a video type; assume HEVC as that is
	# the only codec such relays are used for.
	if videoType == -1 and info.getInfoString(iServiceInformation.sServiceref).startswith("5002"):
		return 7
	return videoType


def getVideoHeight(info):
	val = eAVSwitch.getInstance().getResolutionY(0)
	return val if val else info.getInfo(iServiceInformation.sVideoHeight)


def getVideoWidth(info):
	val = eAVSwitch.getInstance().getResolutionX(0)
	return val if val else info.getInfo(iServiceInformation.sVideoWidth)


# Event sets shared by many types.
EVENTS_INFO = (iPlayableService.evUpdatedInfo, iPlayableService.evStart)
EVENTS_SIZE_INFO = (iPlayableService.evVideoSizeChanged, iPlayableService.evUpdatedInfo, iPlayableService.evStart)
EVENTS_GAMMA_INFO = (iPlayableService.evVideoGammaChanged, iPlayableService.evUpdatedInfo, iPlayableService.evStart)

# First words of audio descriptions that mean "more than stereo".
MULTICHANNEL_CODECS = frozenset(("AC3+", "AC3", "Dolby", "TrueHD", "DTS-HD", "DTS", "HE-AAC", "AC4", "AAC+", "IPCM", "LPCM", "WMA Pro"))


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

	# Skin type name -> (type, events that make the converter update).
	# The IS_AUDIO_CODEC and IS_AUDIO_CHANNEL types are looked up through AUDIO_CODEC_TYPES and AUDIO_CHANNEL_TYPES instead.
	TYPES = {
		"HasTelext": (HAS_TELETEXT, EVENTS_INFO),
		"IsMultichannel": (IS_MULTICHANNEL, EVENTS_INFO),
		"IsStereo": (IS_STEREO, EVENTS_INFO),
		"IsCrypted": (IS_CRYPTED, EVENTS_INFO),
		"IsSoftCSA": (IS_SOFTCSA, EVENTS_INFO),
		"IsStreamRelay": (IS_STREAM_RELAY, EVENTS_INFO),
		"IsWidescreen": (IS_WIDESCREEN, EVENTS_SIZE_INFO),
		"IsNotWidescreen": (IS_NOT_WIDESCREEN, EVENTS_SIZE_INFO),
		"SubservicesAvailable": (SUBSERVICES_AVAILABLE, (iPlayableService.evStart,)),
		"VideoWidth": (XRES, (iPlayableService.evVideoSizeChanged,)),
		"VideoHeight": (YRES, (iPlayableService.evVideoSizeChanged,)),
		"AudioPid": (APID, (iPlayableService.evUpdatedInfo,)),
		"VideoPid": (VPID, (iPlayableService.evUpdatedInfo,)),
		"PcrPid": (PCRPID, (iPlayableService.evUpdatedInfo,)),
		"PmtPid": (PMTPID, (iPlayableService.evUpdatedInfo,)),
		"TxtPid": (TXTPID, (iPlayableService.evUpdatedInfo,)),
		"TsId": (TSID, (iPlayableService.evUpdatedInfo,)),
		"OnId": (ONID, (iPlayableService.evUpdatedInfo,)),
		"Sid": (SID, (iPlayableService.evUpdatedInfo,)),
		"Framerate": (FRAMERATE, (iPlayableService.evVideoFramerateChanged, iPlayableService.evUpdatedInfo)),
		"Progressive": (PROGRESSIVE, (iPlayableService.evVideoProgressiveChanged, iPlayableService.evUpdatedInfo)),
		"VideoInfo": (VIDEO_INFO, (iPlayableService.evVideoSizeChanged, iPlayableService.evVideoFramerateChanged, iPlayableService.evVideoProgressiveChanged, iPlayableService.evUpdatedInfo)),
		"TransferBPS": (TRANSFERBPS, (iPlayableService.evUpdatedInfo,)),
		"HasHBBTV": (HAS_HBBTV, (iPlayableService.evUpdatedInfo, iPlayableService.evHBBTVInfo, iPlayableService.evStart)),
		"AudioTracksAvailable": (AUDIOTRACKS_AVAILABLE, EVENTS_INFO),
		"SubtitlesAvailable": (SUBTITLES_AVAILABLE, EVENTS_INFO),
		"Freq_Info": (FREQ_INFO, (iPlayableService.evUpdatedInfo,)),
		"Editmode": (EDITMODE, EVENTS_INFO),
		"IsStream": (IS_STREAM, EVENTS_INFO),
		"IsSD": (IS_SD, EVENTS_SIZE_INFO),
		"IsHD": (IS_HD, EVENTS_SIZE_INFO),
		"IsSDAndWidescreen": (IS_SD_AND_WIDESCREEN, EVENTS_SIZE_INFO),
		"IsSDAndNotWidescreen": (IS_SD_AND_NOT_WIDESCREEN, EVENTS_SIZE_INFO),
		"Is1080": (IS_1080, EVENTS_SIZE_INFO),
		"Is720": (IS_720, EVENTS_SIZE_INFO),
		"Is576": (IS_576, EVENTS_SIZE_INFO),
		"Is480": (IS_480, EVENTS_SIZE_INFO),
		"Is4K": (IS_4K, EVENTS_SIZE_INFO),
		"IsSDR": (IS_SDR, EVENTS_GAMMA_INFO),
		"IsHDR": (IS_HDR, EVENTS_GAMMA_INFO),
		"IsHDR10": (IS_HDR10, EVENTS_GAMMA_INFO),
		"IsHLG": (IS_HLG, EVENTS_GAMMA_INFO),
		"IsVideoMPEG2": (IS_VIDEO_MPEG2, EVENTS_INFO),
		"IsVideoAVC": (IS_VIDEO_AVC, EVENTS_INFO),
		"IsVideoHEVC": (IS_VIDEO_HEVC, (iPlayableService.evUpdatedInfo, iPlayableService.evVideoSizeChanged)),
		"AudioChannels": (AUDIO_CHANNELS, EVENTS_INFO),
		"AudioCodec": (AUDIO_CODEC, EVENTS_INFO),
		"AudioCodecIcon": (AUDIO_CODEC_ICON, EVENTS_INFO),
		"AudioCodecChannels": (AUDIO_CODEC_CHANNELS, EVENTS_INFO)
	}

	# Map each type to the name of the method that produces its boolean, text or value output.
	# A type missing from a table has no such output: False, "" or -1.
	# The handlers all take (service, info), both already checked to exist.
	BOOL_HANDLERS = {
		HAS_TELETEXT: "boolTeletext",
		IS_AUDIO_CODEC: "boolAudioCodec",
		IS_AUDIO_CHANNEL: "boolAudioChannel",
		IS_MULTICHANNEL: "boolMultichannel",
		IS_STEREO: "boolStereo",
		IS_CRYPTED: "boolCrypted",
		IS_SOFTCSA: "boolSoftCSA",
		IS_STREAM_RELAY: "boolStreamRelay",
		SUBSERVICES_AVAILABLE: "boolSubservices",
		HAS_HBBTV: "boolHBBTV",
		AUDIOTRACKS_AVAILABLE: "boolAudioTracks",
		SUBTITLES_AVAILABLE: "boolSubtitles",
		EDITMODE: "boolEditmode",
		IS_STREAM: "boolStream",
		IS_WIDESCREEN: "boolWidescreen",
		IS_NOT_WIDESCREEN: "boolNotWidescreen",
		IS_HD: "boolHD",
		IS_SD: "boolSD",
		IS_SD_AND_WIDESCREEN: "boolSDAndWidescreen",
		IS_SD_AND_NOT_WIDESCREEN: "boolSDAndNotWidescreen",
		IS_1080: "bool1080",
		IS_720: "bool720",
		IS_576: "bool576",
		IS_480: "bool480",
		IS_4K: "bool4K",
		PROGRESSIVE: "boolProgressive",
		IS_SDR: "boolSDR",
		IS_HDR: "boolHDR",
		IS_HDR10: "boolHDR10",
		IS_HLG: "boolHLG",
		IS_VIDEO_MPEG2: "boolVideoMPEG2",
		IS_VIDEO_AVC: "boolVideoAVC",
		IS_VIDEO_HEVC: "boolVideoHEVC"
	}

	# These only apply to services that carry video; for radio services they are always False.
	VIDEO_SERVICE_TYPES = frozenset((
		IS_WIDESCREEN, IS_NOT_WIDESCREEN, IS_HD, IS_SD, IS_SD_AND_WIDESCREEN, IS_SD_AND_NOT_WIDESCREEN, IS_1080, IS_720, IS_576, IS_480, IS_4K,
		PROGRESSIVE, IS_SDR, IS_HDR, IS_HDR10, IS_HLG, IS_VIDEO_MPEG2, IS_VIDEO_AVC, IS_VIDEO_HEVC
	))

	TEXT_HANDLERS = {
		XRES: "textWidth",
		YRES: "textHeight",
		APID: "textServiceInfo",
		VPID: "textServiceInfo",
		PCRPID: "textServiceInfo",
		PMTPID: "textServiceInfo",
		TXTPID: "textServiceInfo",
		TSID: "textServiceInfo",
		ONID: "textServiceInfo",
		SID: "textServiceInfo",
		FRAMERATE: "textFramerate",
		PROGRESSIVE: "textProgressive",
		AUDIO_CHANNELS: "textAudioChannels",
		AUDIO_CODEC: "textAudioCodec",
		AUDIO_CODEC_ICON: "textAudioCodecIcon",
		AUDIO_CODEC_CHANNELS: "textAudioCodecChannels",
		TRANSFERBPS: "textTransferBPS",
		HAS_HBBTV: "textHBBTV",
		FREQ_INFO: "textFreqInfo",
		VIDEO_INFO: "textVideoInfo"
	}

	# Which service information field the "textServiceInfo" handler shows.
	TEXT_INFO_FIELDS = {
		APID: iServiceInformation.sAudioPID,
		VPID: iServiceInformation.sVideoPID,
		PCRPID: iServiceInformation.sPCRPID,
		PMTPID: iServiceInformation.sPMTPID,
		TXTPID: iServiceInformation.sTXTPID,
		TSID: iServiceInformation.sTSID,
		ONID: iServiceInformation.sONID,
		SID: iServiceInformation.sSID
	}

	VALUE_HANDLERS = {
		XRES: "valueWidth",
		YRES: "valueHeight",
		FRAMERATE: "valueFramerate"
	}

	def __init__(self, type):
		Poll.__init__(self)
		Converter.__init__(self, type)
		self.poll_interval = 5000
		self.poll_enabled = True
		self.audio_codec = AUDIO_CODEC_TYPES.get(type)
		self.audio_channel = AUDIO_CHANNEL_TYPES.get(type)
		self.codecIconPrefix = "icon_"  # forced prefix used for video and audio codc icons
		if self.audio_codec is not None:
			self.type, self.interesting_events = self.IS_AUDIO_CODEC, EVENTS_INFO
		elif self.audio_channel is not None:
			self.type, self.interesting_events = self.IS_AUDIO_CHANNEL, EVENTS_INFO
		else:
			self.type, self.interesting_events = self.TYPES[type]
		# Resolve everything that depends on the type once; the getters never have to work it out again.
		self.boolHandler = getattr(self, self.BOOL_HANDLERS.get(self.type, "boolFalse"))
		self.textHandler = getattr(self, self.TEXT_HANDLERS.get(self.type, "textEmpty"))
		self.valueHandler = getattr(self, self.VALUE_HANDLERS.get(self.type, "valueUnavailable"))
		self.videoServiceOnly = self.type in self.VIDEO_SERVICE_TYPES
		self.infoField = self.TEXT_INFO_FIELDS.get(self.type)

	def isVideoService(self, info, service):
		if not service or not isinstance(service, eServiceReference):
			serviceInfo = info.getInfoString(iServiceInformation.sServiceref).split(':')
		else:
			serviceInfo = info.getInfoString(service, iServiceInformation.sServiceref).split(':')

		return len(serviceInfo) < 3 or serviceInfo[2] != '2'

	def formatSize(self, value):
		return "%d" % value if value > 0 else "?"

	def formatKBps(self, value):
		return "%d kB/s" % (value // 1024)

	def audioChannelLabel(self, channels):
		return AUDIO_CHANNEL_LABELS.get(channels, f"{channels} ch" if channels > 0 else "")

	def getServiceInfoString(self, info, what, convert=lambda x: "%d" % x):
		v = info.getInfo(what)
		if v == -1:
			return _("N/A")
		if v == -2:
			return info.getInfoString(what)
		return convert(v)

	def getFrameRate(self, info):
		val = eAVSwitch.getInstance().getFrameRate(0)
		return val if val else info.getInfo(iServiceInformation.sFrameRate)

	def getProgressive(self):
		return eAVSwitch.getInstance().getProgressive()

	def getProgressiveStr(self):
		return "p" if self.getProgressive() else "i"

	def getVideoWidthStr(self, info):
		val = eAVSwitch.getInstance().getResolutionX(0)
		return self.formatSize(val) if val else self.getServiceInfoString(info, iServiceInformation.sVideoWidth, self.formatSize)

	def getVideoHeightStr(self, info):
		val = eAVSwitch.getInstance().getResolutionY(0)
		return self.formatSize(val) if val else self.getServiceInfoString(info, iServiceInformation.sVideoHeight, self.formatSize)

	@cached
	def getBoolean(self):
		service = self.source.service
		if not service or isinstance(service, eServiceReference):
			return False
		info = service.info()
		if not info:
			return False
		if self.videoServiceOnly and not self.isVideoService(info, service):
			return False
		return self.boolHandler(service, info)

	boolean = property(getBoolean)

	@cached
	def getText(self):
		service = self.source.service
		info = service and service.info()
		if not info:
			return ""
		return self.textHandler(service, info)

	text = property(getText)

	@cached
	def getValue(self):
		service = self.source.service
		info = service and service.info()
		if not info:
			return -1
		return self.valueHandler(service, info)

	value = property(getValue)

	def changed(self, what):
		if what[0] != self.CHANGED_SPECIFIC or what[1] in self.interesting_events:
			Converter.changed(self, what)

	# ---- Boolean ----

	def boolFalse(self, service, info):
		return False

	def boolTeletext(self, service, info):
		return info.getInfo(iServiceInformation.sTXTPID) > 0

	def boolAudioCodec(self, service, info):
		return getCurrentAudioCodec(service) in self.audio_codec

	def boolAudioChannel(self, service, info):
		return getCurrentAudioChannels(service) == self.audio_channel

	def hasMultichannelTrack(self, audio):
		# FIXME. but currently iAudioTrackInfo doesn't provide more information.
		for idx in range(audio.getNumberOfTracks()):
			description = StdAudioDesc(audio.getTrackInfo(idx).getDescription())
			if description and description.split()[0] in MULTICHANNEL_CODECS:
				return True
		return False

	def boolMultichannel(self, service, info):
		audio = service.audioTracks()
		return bool(audio) and self.hasMultichannelTrack(audio)

	def boolStereo(self, service, info):
		audio = service.audioTracks()
		return bool(audio) and not self.hasMultichannelTrack(audio)

	def boolCrypted(self, service, info):
		return info.getInfo(iServiceInformation.sIsCrypted) == 1 and info.getInfo(iServiceInformation.sIsSoftCSA) != 1

	def boolSoftCSA(self, service, info):
		return info.getInfo(iServiceInformation.sIsSoftCSA) == 1

	def boolStreamRelay(self, service, info):
		refstr = info.getInfoString(iServiceInformation.sServiceref)
		return "9999" in refstr or "17999" in refstr and "127.0.0.1" in refstr or "localhost" in refstr or "0.0.0.0" in refstr and info.getInfo(iServiceInformation.sIsCrypted) == 1

	def boolSubservices(self, service, info):
		return hasActiveSubservicesForCurrentChannel(service)

	def boolHBBTV(self, service, info):
		return info.getInfoString(iServiceInformation.sHBBTVUrl) != ""

	def boolAudioTracks(self, service, info):
		audio = service.audioTracks()
		return bool(audio) and audio.getNumberOfTracks() > 1

	def boolSubtitles(self, service, info):
		subtitle = service.subtitle()
		subtitlelist = subtitle and subtitle.getSubtitleList()
		return bool(subtitlelist)

	def boolEditmode(self, service, info):
		return hasattr(self.source, "editmode") and bool(self.source.editmode)

	def boolStream(self, service, info):
		refstr = info.getInfoString(iServiceInformation.sServiceref)
		if "4097" in refstr or "5001" in refstr or "5002" in refstr or "9999" in refstr:
			return service.streamed() is not None
		return False

	# The video types below are only reached for services that carry video.

	def boolWidescreen(self, service, info):
		return info.getInfo(iServiceInformation.sAspect) in WIDESCREEN

	def boolNotWidescreen(self, service, info):
		return info.getInfo(iServiceInformation.sAspect) not in WIDESCREEN

	def boolHD(self, service, info):
		video_width = getVideoWidth(info)
		video_height = getVideoHeight(info)
		return video_width > 1025 and video_width <= 1920 and video_height >= 481 and video_height < 1440 or video_width >= 960 and video_height == 720

	def boolSD(self, service, info):
		video_width = getVideoWidth(info)
		video_height = getVideoHeight(info)
		return video_width > 1 and video_width <= 1024 and video_height > 1 and video_height <= 578

	def boolSDAndWidescreen(self, service, info):
		return getVideoHeight(info) < 578 and info.getInfo(iServiceInformation.sAspect) in WIDESCREEN

	def boolSDAndNotWidescreen(self, service, info):
		return getVideoHeight(info) < 578 and info.getInfo(iServiceInformation.sAspect) not in WIDESCREEN

	def bool1080(self, service, info):
		video_width = getVideoWidth(info)
		video_height = getVideoHeight(info)
		return video_width >= 1367 and video_width <= 2400 and video_height >= 768 and video_height <= 1440

	def bool720(self, service, info):
		video_width = getVideoWidth(info)
		video_height = getVideoHeight(info)
		return video_width >= 1025 and video_width <= 1366 and video_height >= 481 and video_height <= 768 or video_width >= 960 and video_height == 720

	def bool576(self, service, info):
		video_width = getVideoWidth(info)
		video_height = getVideoHeight(info)
		return video_width > 1 and video_width <= 1024 and video_height > 481 and video_height <= 578

	def bool480(self, service, info):
		video_width = getVideoWidth(info)
		video_height = getVideoHeight(info)
		return video_width > 1 and video_width <= 1024 and video_height > 1 and video_height <= 480

	def bool4K(self, service, info):
		return getVideoWidth(info) >= 1921 and getVideoHeight(info) >= 1440

	def boolProgressive(self, service, info):
		return bool(self.getProgressive())

	def boolSDR(self, service, info):
		return info.getInfo(iServiceInformation.sGamma) == 0

	def boolHDR(self, service, info):
		hdr = info.getInfo(iServiceInformation.sHDRType)
		return hdr == 3 if hdr > 0 else info.getInfo(iServiceInformation.sGamma) == 1

	def boolHDR10(self, service, info):
		hdr = info.getInfo(iServiceInformation.sHDRType)
		return hdr == 1 if hdr > 0 else info.getInfo(iServiceInformation.sGamma) == 2

	def boolHLG(self, service, info):
		hdr = info.getInfo(iServiceInformation.sHDRType)
		return hdr == 2 if hdr > 0 else info.getInfo(iServiceInformation.sGamma) == 3

	def boolVideoMPEG2(self, service, info):
		return info.getInfo(iServiceInformation.sVideoType) == 0

	def boolVideoAVC(self, service, info):
		return info.getInfo(iServiceInformation.sVideoType) == 1

	def boolVideoHEVC(self, service, info):
		return getCurrentVideoCodec(info) == 7

	# ---- Text ----

	def textEmpty(self, service, info):
		return ""

	def textWidth(self, service, info):
		return self.getVideoWidthStr(info)

	def textHeight(self, service, info):
		return self.getVideoHeightStr(info)

	def textServiceInfo(self, service, info):
		return self.getServiceInfoString(info, self.infoField)

	def textFramerate(self, service, info):
		return f"{(self.getFrameRate(info) + 500) // 1000} fps"

	def textProgressive(self, service, info):
		return self.getProgressiveStr()

	def textAudioChannels(self, service, info):
		return self.audioChannelLabel(getCurrentAudioChannels(service))

	def audioCodecLabelIcon(self, service):
		description = getCurrentAudioCodec(service)
		return AUDIO_CODEC_INFO.get(description, (description, ""))

	def textAudioCodec(self, service, info):
		return self.audioCodecLabelIcon(service)[0]

	def textAudioCodecIcon(self, service, info):
		icon = self.audioCodecLabelIcon(service)[1]
		return f"{self.codecIconPrefix}{icon}" if icon else ""

	def textAudioCodecChannels(self, service, info):
		label = self.audioCodecLabelIcon(service)[0]
		return f"{label} {self.audioChannelLabel(getCurrentAudioChannels(service))}".strip()

	def textTransferBPS(self, service, info):
		return self.getServiceInfoString(info, iServiceInformation.sTransferBPS, self.formatKBps)

	def textHBBTV(self, service, info):
		return info.getInfoString(iServiceInformation.sHBBTVUrl)

	def textFreqInfo(self, service, info):
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
		return f"Freq: {frequency} {polarization} {sr_txt} {symbolrate} {fec}"

	def textVideoInfo(self, service, info):
		return f"{self.getVideoWidthStr(info)}x{self.getVideoHeightStr(info)}{self.getProgressiveStr()}{(self.getFrameRate(info) + 500) // 1000}"

	# ---- Value ----

	def valueUnavailable(self, service, info):
		return -1

	def valueWidth(self, service, info):
		return str(getVideoWidth(info))

	def valueHeight(self, service, info):
		return str(getVideoHeight(info))

	def valueFramerate(self, service, info):
		return str(self.getFrameRate(info))
