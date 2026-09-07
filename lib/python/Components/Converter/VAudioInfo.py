from enigma import iPlayableService, iPlayableServicePtr

from Components.Converter.Converter import Converter
from Components.Converter.Poll import Poll
from Components.Element import cached

# Common function to standardize the display of Audio Codecs
# _acedits is a list of text conversions (from, to) that are done in the
# order given.
#
_acedits = (
	("MPEG-4 AAC audio", "AAC"),
	("MPEG-4 AAC", "AAC"),
	("MPEG-2 AAC audio", "AAC"),
	("MPEG-2 AAC", "AAC"),
	("DVD LPCM", "AAC"),
	("MPEG/L3", "MP2"),
	("Free Lossless Audio Codec (FLAC)", "FLAC"),
	("-", ""),
	("A_", ""),
	("(ATSC A/52)", ""),
	("(ATSC A/52B)", ""),
	("EAC3", "AC3+"),
	("IPCM", "AC3+"),
	("LPCM", "AC3+"),
	("AAC_PLUS", "HE-AAC"),
	("AAC_LATM", "HE-AAC"),
	("HEAAC", "HE-AAC"),
	("AACHE", "HE-AAC"),
	("ADTS", "HE-AAC"),
	("ALAC", "HE-AAC"),
	("private1-lpcm", "HE-AAC"),
	("WMA/PRO", "WMA Pro"),
	("audio/x", ""),
	(" audio", ""),
	("raw", "Dolby TrueHD"),
	("MPEG1", ""),
	(" Layer 2 (MP2)", "MP2"),
	(" Layer 3 (MP3)", "MP3"),
	("MPEG", "MPEG1 Layer II"),
)


_accanonical = (
	("DTSHD Master Audio", "DTS-HD MA"),
	("DTS-HD Master Audio", "DTS-HD MA"),
	("DTSHD High Resolution Audio", "DTS-HD HRA"),
	("DTS-HD High Resolution Audio", "DTS-HD HRA"),
	("DTSHD High Resolution", "DTS-HD HRA"),
	("DTS-HD High Resolution", "DTS-HD HRA"),
	("DTSHD MA + DTS:X IMAX", "DTS-HD MA + DTS:X IMAX"),
	("DTSHD MA + DTS:X", "DTS-HD MA + DTS:X"),
	("DTSHD MA", "DTS-HD MA"),
	("DTSHD HRA", "DTS-HD HRA"),
	("DTSHD", "DTS-HD"),
	("DTSES", "DTS-ES"),
	("xHEAAC", "xHE-AAC"),
	("HEAAC v2", "HE-AAC v2"),
	("HEAAC", "HE-AAC"),
	("AACELD", "AAC-ELD"),
	("AACLD", "AAC-LD"),
	("AACLC", "AAC-LC"),
	("Dolby AC4", "Dolby AC-4"),
	("AMRWB", "AMR-WB"),
)


def StdAudioDesc(description):
	for orig, repl in _acedits:
		description = description.replace(orig, repl)
	for orig, repl in _accanonical:
		if description == orig:
			return repl
	return description


class VAudioInfo(Poll, Converter, object):
	GET_AUDIO_ICON = 0
	GET_AUDIO_CODEC = 1

	def __init__(self, type):
		Converter.__init__(self, type)
		Poll.__init__(self)
		self.type = type
		self.poll_interval = 1000
		self.poll_enabled = True
		self.lang_strings = ("english", "englisch", "eng")
		self.codecs = {
			"01_dolbydigitalplus": ("ac3+", "digital+", "digitalplus", "dolby.digital.plus",),
			"02_dolbydigital": ("ac3", "dolbydigital", "dolby.digital",),
			"03_mp3": ("mp3",),
			"04_wma": ("wma",),
			"05_flac": ("flac",),
			"06_mpeg": ("mpeg",),
			"07_lpcm": ("lpcm",),
			"08_dts-hd": ("dts-hd",),
			"09_dts": ("dts",),
			"10_pcm": ("pcm",),
			"11_aac": ("aac",),
			"12_aac-he": ("he-aac",),
			"13_dolbytruehd": ("truehd",),
			"14_aacplus": ("he-aac",),
			"15_ipcm": ("ipcm",),
			"16_wma-pro": ("wma pro",),
			"17_vorbis": ("vorbis",),
			"18_opus": ("opus",),
			"19_amr": ("amr",),
			"20_mp2": ("mp2",),
		}
		self.codec_info = {
			"dolbydigitalplus": ("51", "20", "71",),
			"dolbydigital": ("51", "20", "71",),
			"dolbytruehd": ("51", "20", "71",),
			"wma": ("8", "9",),
		}
		self.type, self.interesting_events = {
			"AudioIcon": (self.GET_AUDIO_ICON, (iPlayableService.evUpdatedInfo,)),
			"AudioCodec": (self.GET_AUDIO_CODEC, (iPlayableService.evUpdatedInfo,)),
		}[type]

	def getAudio(self):
		service = self.source.service
		audio = isinstance(service, iPlayableServicePtr) and service.audioTracks()
		if audio:
			self.current_track = audio.getCurrentTrack()
			self.number_of_tracks = audio.getNumberOfTracks()
			if self.number_of_tracks > 0 and self.current_track > -1:
				self.audio_info = audio.getTrackInfo(self.current_track)
				return True
		return False

	def getLanguage(self):
		languages = self.audio_info.getLanguage()
		for lang in self.lang_strings:
			if lang in languages:
				languages = "English"
				break
		languages = languages.replace("und", "")
		return languages

	def getAudioCodec(self, info):
		description_str = _(" ")
		if self.getAudio():
			languages = self.getLanguage()
			description = StdAudioDesc(self.audio_info.getDescription()) or ""
			description_str = description.split(" ")
			if description.lower() in languages.lower():
				languages = ""
			description_str = description
		return description_str

	def getAudioIcon(self, info):
		description_str = self.get_short(self.getAudioCodec(info).translate(str.maketrans('  ', ' .')).lower())
		return description_str

	def get_short(self, audioName):
		for return_codec, codecs in sorted(self.codecs.items()):
			for codec in codecs:
				if codec in audioName:
					codec = return_codec.split('_')[1]
					if codec in self.codec_info:
						for ex_codec in self.codec_info[codec]:
							if ex_codec in audioName:
								codec += ex_codec
								break
					return codec
		return audioName

	@cached
	def getText(self):
		service = self.source.service
		if service:
			info = service and service.info()
			if info:
				if self.type == self.GET_AUDIO_CODEC:
					return self.getAudioCodec(info)
				if self.type == self.GET_AUDIO_ICON:
					return self.getAudioIcon(info)
		return _(" ")

	text = property(getText)

	def changed(self, what):
		if what[0] != self.CHANGED_SPECIFIC or what[1] in self.interesting_events:
			Converter.changed(self, what)
