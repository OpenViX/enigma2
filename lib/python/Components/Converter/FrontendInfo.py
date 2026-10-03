from Components.Converter.Converter import Converter

from Components.config import config
from Components.Element import cached
from Components.NimManager import nimmanager
from Tools.Hex2strColor import ColorizeText


class FrontendInfo(Converter, ColorizeText):
	BER = 0
	SNR = 1
	AGC = 2
	LOCK = 3
	SNRdB = 4
	SLOT_NUMBER = 5
	TUNER_TYPE = 6
	STRING = 7
	USE_TUNERS_STRING = 8

	# Indexes into the "FrontendInfoColors" skin parameter.
	COLOR_ACTIVE = 0
	COLOR_BUSY = 1
	COLOR_AVAILABLE = 2
	DEFAULT_COLORS = (0x0000FF00, 0x00FFFF00, 0x007F7F7F)  # tuner active, busy, available colors

	# Map each type to the name of the method that produces its text, boolean or value output.
	# A type missing from a table is not supported for that output and raises when it is used.
	# "outputNone" is for types that are allowed but have nothing to show.
	TEXT_HANDLERS = {
		BER: "textBER",
		SNR: "textSNR",
		SNRdB: "textSNRdB",
		AGC: "textAGC",
		TUNER_TYPE: "textTunerType",
		STRING: "textTunerString",
		USE_TUNERS_STRING: "textUsedTuners"
	}

	BOOL_HANDLERS = {
		LOCK: "boolLock",
		BER: "boolBER",
		SNR: "boolSNR",
		SNRdB: "boolSNRdB",
		AGC: "boolAGC",
		STRING: "boolText",
		USE_TUNERS_STRING: "boolText"
	}

	VALUE_HANDLERS = {
		BER: "valueBER",
		SNR: "valueSNR",
		SNRdB: "outputNone",
		AGC: "valueAGC",
		SLOT_NUMBER: "valueSlotNumber",
		TUNER_TYPE: "valueTunerType",
		STRING: "outputNone",
		USE_TUNERS_STRING: "outputNone"
	}

	FRONTEND_TYPE_VALUES = {
		"DVB-S": 0,
		"DVB-C": 1,
		"DVB-T": 2,
		"ATSC": 3
	}

	def __init__(self, type):
		Converter.__init__(self, type)
		ColorizeText.__init__(self, "FrontendInfoColors", self.DEFAULT_COLORS)
		if type == "BER":
			self.type = self.BER
		elif type == "SNR":
			self.type = self.SNR
		elif type == "SNRdB":
			self.type = self.SNRdB
		elif type == "AGC":
			self.type = self.AGC
		elif type == "NUMBER":
			self.type = self.SLOT_NUMBER
		elif type == "TYPE":
			self.type = self.TUNER_TYPE
		elif type.startswith("STRING"):
			self.type = self.STRING
			type = type.split(",")
			self.space_for_tuners = len(type) > 1 and int(type[1]) or 10
			self.space_for_tuners_with_spaces = len(type) > 2 and int(type[2]) or 6
			self.show_all_non_link_tuners = True if len(type) <= 3 else type[3] == "True"
		elif type == "USE_TUNERS_STRING":
			self.type = self.USE_TUNERS_STRING
		else:
			self.type = self.LOCK
		# Resolve the handlers once; the getters never have to work out the type again.
		self.textHandler = getattr(self, self.TEXT_HANDLERS.get(self.type, "textUnsupported"))
		self.boolHandler = getattr(self, self.BOOL_HANDLERS.get(self.type, "boolUnsupported"))
		self.valueHandler = getattr(self, self.VALUE_HANDLERS.get(self.type, "valueUnsupported"))

	@cached
	def getText(self):
		return self.textHandler()

	@cached
	def getBool(self):
		return self.boolHandler()

	text = property(getText)

	boolean = property(getBool)

	@cached
	def getValue(self):
		return self.valueHandler()

	range = 65535  # name inherited from old code
	value = property(getValue)

	# ---- Shared ----

	def outputNone(self):  # not for text, where "" would be required
		return None

	def textUnsupported(self):
		raise AssertionError("the text output of FrontendInfo cannot be used for lock info")

	def boolUnsupported(self):
		raise AssertionError("the boolean output of FrontendInfo can only be used for lock, BER, SNR, SNRdB, AGC, STRING, or USE_TUNERS_STRING")

	def valueUnsupported(self):
		raise AssertionError("the value/range output of FrontendInfo can not be used for lock info")

	def percentText(self, percent):
		if percent is None:
			return _("N/A")
		return "%d %%" % (percent * 100 / 65535)

	# ---- Text ----

	def textBER(self):  # As count.
		count = self.source.ber
		return str(count) if count is not None else _("N/A")

	def textAGC(self):
		return self.percentText(self.source.agc)

	def textSNR(self):
		return self.snrText(not config.usage.swap_snr_on_osd.value)

	def textSNRdB(self):
		return self.snrText(bool(config.usage.swap_snr_on_osd.value))

	def snrText(self, asPercent):
		if asPercent:
			return self.percentText(self.source.snr)
		snr_db = self.source.snr_db
		if snr_db is not None:
			return _("%3.01f dB") % (snr_db / 100.0)
		return self.percentText(self.source.snr)  # Fall back to the normal SNR.

	def textTunerType(self):
		return self.source.frontend_type or _("Unknown")

	def textTunerString(self):
		slots = nimmanager.nim_slots
		slotCount = len(slots)
		slot_number = self.source.slot_number
		tuner_mask = self.source.tuner_mask
		string = ""
		for n in slots:
			if n.enabled:
				if n.slot == slot_number:
					colorIndex = self.COLOR_ACTIVE
				elif tuner_mask & 1 << n.slot:
					colorIndex = self.COLOR_BUSY
				elif slotCount <= self.space_for_tuners or n.isFBCRoot() or self.show_all_non_link_tuners and not (n.isFBCLink() or n.config_mode == "loopthrough"):
					colorIndex = self.COLOR_AVAILABLE
				else:
					continue
				if string and slotCount <= self.space_for_tuners_with_spaces:
					string += " "
				string += self.addColor(chr(ord("A") + n.slot), colorIndex)
		return string

	def textUsedTuners(self):
		slot_number = self.source.slot_number
		tuner_mask = self.source.tuner_mask
		string = ""
		for n in nimmanager.nim_slots:
			if n.enabled:
				if n.slot == slot_number:
					colorIndex = self.COLOR_ACTIVE
				elif tuner_mask & 1 << n.slot:
					colorIndex = self.COLOR_BUSY
				else:
					continue
				if string:
					string += " "
				string += self.addColor(chr(ord("A") + n.slot), colorIndex)
		return string

	# ---- Boolean ----

	def boolLock(self):
		lock = self.source.lock
		if lock is None:
			lock = False
		return lock

	def boolBER(self):
		return self.source.ber is not None

	def boolSNR(self):
		return self.snrAvailable(not config.usage.swap_snr_on_osd.value)

	def boolSNRdB(self):
		return self.snrAvailable(bool(config.usage.swap_snr_on_osd.value))

	def snrAvailable(self, asPercent):
		if asPercent:
			return self.source.snr is not None
		return self.source.snr_db is not None or self.source.snr is not None

	def boolAGC(self):
		return self.source.agc is not None

	def boolText(self):
		return bool(self.getText())

	# ---- Value ----

	def valueAGC(self):
		return self.source.agc or 0

	def valueSNR(self):
		return self.source.snr or 0

	def valueBER(self):
		ber = self.source.ber or 0
		return ber if ber < self.range else self.range

	def valueTunerType(self):
		return self.FRONTEND_TYPE_VALUES.get(self.source.frontend_type, -1)

	def valueSlotNumber(self):
		num = self.source.slot_number
		return -1 if num is None else num
