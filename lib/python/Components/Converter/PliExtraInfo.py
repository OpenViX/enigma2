# shamelessly copied from pliExpertInfo (Vali, Mirakels, Littlesat)

from enigma import iServiceInformation, iPlayableService
from Components.Converter.Converter import Converter
from Components.Element import cached
from Components.config import config
from Tools.Transponder import ConvertToHumanReadable
from Tools.GetEcmInfo import GetEcmInfo
from Tools.Hex2strColor import Hex2strColor
from Components.Converter.Poll import Poll
from skin import parameters

caid_data = (
	("0x100", "0x1ff", "Seca", "S", True),
	("0x500", "0x5ff", "Via", "V", True),
	("0x600", "0x6ff", "Irdeto", "I", True),
	("0x900", "0x9ff", "NDS", "Nd", True),
	("0xb00", "0xbff", "Conax", "Co", True),
	("0xd00", "0xdff", "CryptoW", "Cw", True),
	("0xe00", "0xeff", "PowerVU", "P", False),
	("0x1000", "0x10FF", "Tandberg", "TB", False),
	("0x1700", "0x17ff", "Beta", "B", True),
	("0x1800", "0x18ff", "Nagra", "N", True),
	("0x2600", "0x2600", "Biss", "Bi", False),
	("0x2700", "0x2710", "Dre3", "D3", False),
	("0x4ae0", "0x4ae1", "Dre", "D", False),
	("0x4aee", "0x4aee", "BulCrypt", "B1", False),
	("0x5581", "0x5581", "BulCrypt", "B2", False)
)

# stream type to codec map
codec_data = {
	-1: "N/A",
	0: "MPEG2 H.262",
	1: "MPEG4 H.264",
	2: "H263",
	3: "VC1",
	4: "MPEG4 VC",
	5: "VC1 SM",
	6: "MPEG1 H.261",
	7: "HEVC H.265",
	8: "VP8",
	9: "VP9",
	10: "XVID",
	11: "N/A 11",
	12: "N/A 12",
	13: "DIVX 3.11",
	14: "DIVX 4",
	15: "DIVX 5",
	16: "AVS",
	17: "N/A 17",
	18: "VP6",
	19: "N/A 19",
	20: "N/A 20",
	21: "SPARK",
	40: "AVS2",
}

# Dynamic range ("gamma") value to text
gamma_data = {
	0: "SDR",
	1: "HDR",
	2: "HDR10",
	3: "HLG",
}


def addspace(text):
	if text:
		text += "  "
	return text


class PliExtraInfo(Poll, Converter, object):

	def __init__(self, type):
		Converter.__init__(self, type)
		Poll.__init__(self)
		self.type = type
		self.poll_interval = 1000
		self.poll_enabled = True
		self.info_fields = {
			# Field combinations accessible from skin
			"All": (
				(  # config.usage.show_cryptoinfo.value <= 0
					"ProviderName",
					"TransponderInfo",
					"TransponderName",
					"NewLine",
					"CryptoBar",
					"CryptoCurrentSource",
					"NewLine",
					"CryptoSpecial",
					"VideoCodec",
					"ResolutionString",
				), (  # config.usage.show_cryptoinfo.value > 0
					"ProviderName",
					"TransponderInfo",
					"TransponderName",
					"NewLine",
					"CryptoBar",
					"CryptoSpecial",
					"NewLine",
					"PIDInfo",
					"VideoCodec",
					"ResolutionString",
				)
			),
			"CryptoInfo": (
				(  # config.usage.show_cryptoinfo.value <= 0
					"CryptoBar",
					"CryptoCurrentSource",
					"CryptoSpecial",
				), (  # config.usage.show_cryptoinfo.value > 0
					"CryptoBar",
					"CryptoSpecial",
				)
			),
			"ServiceInfo": (
				"ProviderName",
				"TunerSystem",
				"TransponderFrequencyMHz",
				"TransponderPolarization",
				"TransponderSymbolRate",
				"TransponderFEC",
				"TransponderModulation",
				"OrbitalPosition",
				"TransponderName",
				"VideoCodec",
				"ResolutionString",
			),
			"TransponderInfo": (
				(  # not feraw
					"StreamURLInfo",
				),
				(  # feraw and "DVB-T" not in feraw.get("tuner_type", "")
					"TunerSystem",
					"TransponderFrequencyMHz",
					"TransponderPolarization",
					"TransponderSymbolRate",
					"TransponderFEC",
					"TransponderModulation",
					"OrbitalPosition",
					"TransponderInfoMisPls",
				),
				(  # feraw and "DVB-T" in feraw.get("tuner_type", "")
					"TunerSystem",
					"TerrestrialChannelNumber",
					"TransponderFrequencyMHz",
					"TransponderPolarization",
					"TransponderSymbolRate",
					"TransponderFEC",
					"TransponderModulation",
					"OrbitalPosition",
				)
			),
			"TransponderInfo2line": (
				"ProviderName",
				"TunerSystem",
				"TransponderName",
				"NewLine",
				"TransponderFrequencyMHz",
				"TransponderPolarization",
				"TransponderSymbolRate",
				"TransponderModulationFEC",
			),
			"User": (),
		}
		self.ca_table = (
			("CryptoCaidSecaAvailable", "S", False),
			("CryptoCaidViaAvailable", "V", False),
			("CryptoCaidIrdetoAvailable", "I", False),
			("CryptoCaidNDSAvailable", "Nd", False),
			("CryptoCaidConaxAvailable", "Co", False),
			("CryptoCaidCryptoWAvailable", "Cw", False),
			("CryptoCaidPowerVUAvailable", "P", False),
			("CryptoCaidBetaAvailable", "B", False),
			("CryptoCaidNagraAvailable", "N", False),
			("CryptoCaidBissAvailable", "Bi", False),
			("CryptoCaidDre3Available", "D3", False),
			("CryptoCaidDreAvailable", "D", False),
			("CryptoCaidBulCrypt1Available", "B1", False),
			("CryptoCaidBulCrypt2Available", "B2", False),
			("CryptoCaidTandbergAvailable", "T", False),
			("CryptoCaidSecaSelected", "S", True),
			("CryptoCaidViaSelected", "V", True),
			("CryptoCaidIrdetoSelected", "I", True),
			("CryptoCaidNDSSelected", "Nd", True),
			("CryptoCaidConaxSelected", "Co", True),
			("CryptoCaidCryptoWSelected", "Cw", True),
			("CryptoCaidPowerVUSelected", "P", True),
			("CryptoCaidBetaSelected", "B", True),
			("CryptoCaidNagraSelected", "N", True),
			("CryptoCaidBissSelected", "Bi", True),
			("CryptoCaidDre3Selected", "D3", True),
			("CryptoCaidDreSelected", "D", True),
			("CryptoCaidBulCrypt1Selected", "B1", True),
			("CryptoCaidBulCrypt2Selected", "B2", True),
			("CryptoCaidTandbergSelected", "T", True)
		)
		self.type = self.type.split(',')
		if self.type[0] == "User":
			self.info_fields[self.type[0]] = tuple(self.type[1:])
		self.type = self.type[0]
		self.ecmdata = GetEcmInfo()
		self.feraw = self.fedata = self.updateFEdata = None
		self.recursionCheck = set()
		self.cryptocolors = parameters.get("PliExtraInfoCryptoColors", (0x004C7D3F, 0x009F9F9F, 0x00EEEE00, 0x00FFFFFF))

	def getCryptoInfo(self, info):
		if info.getInfo(iServiceInformation.sIsCrypted) == 1:
			data = self.ecmdata.getEcmData()
			self.current_source = data[0]
			self.current_caid = data[1]
			self.current_provid = data[2]
			self.current_ecmpid = data[3]
		else:
			self.current_source = ""
			self.current_caid = "0"
			self.current_provid = "0"
			self.current_ecmpid = "0"

	def createCryptoBar(self, info):
		res = ""
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
		colors = parameters.get("PliExtraInfoColors", (0x0000FF00, 0x00FFFF00, 0x007F7F7F, 0x00FFFFFF))  # "found", "not found", "available", "default" colors

		for caid_entry in caid_data:
			if int(caid_entry[0], 16) <= int(self.current_caid, 16) <= int(caid_entry[1], 16):
				color = Hex2strColor(colors[0])  # green
			else:
				color = Hex2strColor(colors[2])  # grey
				try:
					for caid in available_caids:
						if int(caid_entry[0], 16) <= caid <= int(caid_entry[1], 16):
							color = Hex2strColor(colors[1])  # yellow
				except:
					pass

			if color != Hex2strColor(colors[2]) or caid_entry[4]:
				if res:
					res += " "
				res += color + caid_entry[3]

		res += Hex2strColor(colors[3])  # white (this acts like a color "reset" for following strings
		return res

	def createCryptoSeca(self, info):
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
		if int('0x100', 16) <= int(self.current_caid, 16) <= int('0x1ff', 16):
			color = Hex2strColor(self.cryptocolors[0])
		else:
			color = Hex2strColor(self.cryptocolors[1])
			try:
				for caid in available_caids:
					if int('0x100', 16) <= caid <= int('0x1ff', 16):
						color = Hex2strColor(self.cryptocolors[2])
			except:
				pass
		res = color + 'S'
		res += Hex2strColor(self.cryptocolors[3])
		return res

	def createCryptoVia(self, info):
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
		if int('0x500', 16) <= int(self.current_caid, 16) <= int('0x5ff', 16):
			color = Hex2strColor(self.cryptocolors[0])
		else:
			color = Hex2strColor(self.cryptocolors[1])
			try:
				for caid in available_caids:
					if int('0x500', 16) <= caid <= int('0x5ff', 16):
						color = Hex2strColor(self.cryptocolors[2])
			except:
				pass
		res = color + 'V'
		res += Hex2strColor(self.cryptocolors[3])
		return res

	def createCryptoIrdeto(self, info):
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
		if int('0x600', 16) <= int(self.current_caid, 16) <= int('0x6ff', 16):
			color = Hex2strColor(self.cryptocolors[0])
		else:
			color = Hex2strColor(self.cryptocolors[1])
			try:
				for caid in available_caids:
					if int('0x600', 16) <= caid <= int('0x6ff', 16):
						color = Hex2strColor(self.cryptocolors[2])
			except:
				pass
		res = color + 'I'
		res += Hex2strColor(self.cryptocolors[3])
		return res

	def createCryptoNDS(self, info):
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
		if int('0x900', 16) <= int(self.current_caid, 16) <= int('0x9ff', 16):
			color = Hex2strColor(self.cryptocolors[0])
		else:
			color = Hex2strColor(self.cryptocolors[1])
			try:
				for caid in available_caids:
					if int('0x900', 16) <= caid <= int('0x9ff', 16):
						color = Hex2strColor(self.cryptocolors[2])
			except:
				pass
		res = color + 'NDS'
		res += Hex2strColor(self.cryptocolors[3])
		return res

	def createCryptoConax(self, info):
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
		if int('0xb00', 16) <= int(self.current_caid, 16) <= int('0xbff', 16):
			color = Hex2strColor(self.cryptocolors[0])
		else:
			color = Hex2strColor(self.cryptocolors[1])
			try:
				for caid in available_caids:
					if int('0xb00', 16) <= caid <= int('0xbff', 16):
						color = Hex2strColor(self.cryptocolors[2])
			except:
				pass
		res = color + 'CO'
		res += Hex2strColor(self.cryptocolors[3])
		return res

	def createCryptoCryptoW(self, info):
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
		if int('0xd00', 16) <= int(self.current_caid, 16) <= int('0xdff', 16):
			color = Hex2strColor(self.cryptocolors[0])
		else:
			color = Hex2strColor(self.cryptocolors[1])
			try:
				for caid in available_caids:
					if int('0xd00', 16) <= caid <= int('0xdff', 16):
						color = Hex2strColor(self.cryptocolors[2])
			except:
				pass
		res = color + 'CW'
		res += Hex2strColor(self.cryptocolors[3])
		return res

	def createCryptoPowerVU(self, info):
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
		if int('0xe00', 16) <= int(self.current_caid, 16) <= int('0xeff', 16):
			color = Hex2strColor(self.cryptocolors[0])
		else:
			color = Hex2strColor(self.cryptocolors[1])
			try:
				for caid in available_caids:
					if int('0xe00', 16) <= caid <= int('0xeff', 16):
						color = Hex2strColor(self.cryptocolors[2])
			except:
				pass
		res = color + 'P'
		res += Hex2strColor(self.cryptocolors[3])
		return res

	def createCryptoTandberg(self, info):
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
		if int('0x1010', 16) <= int(self.current_caid, 16) <= int('0x1010', 16):
			color = Hex2strColor(self.cryptocolors[0])
		else:
			color = Hex2strColor(self.cryptocolors[1])
			try:
				for caid in available_caids:
					if int('0x1010', 16) <= caid <= int('0x1010', 16):
						color = Hex2strColor(self.cryptocolors[2])
			except:
				pass
		res = color + 'T'
		res += Hex2strColor(self.cryptocolors[3])
		return res

	def createCryptoBeta(self, info):
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
		if int('0x1700', 16) <= int(self.current_caid, 16) <= int('0x17ff', 16):
			color = Hex2strColor(self.cryptocolors[0])
		else:
			color = Hex2strColor(self.cryptocolors[1])
			try:
				for caid in available_caids:
					if int('0x1700', 16) <= caid <= int('0x17ff', 16):
						color = Hex2strColor(self.cryptocolors[2])
			except:
				pass
		res = color + 'B'
		res += Hex2strColor(self.cryptocolors[3])
		return res

	def createCryptoNagra(self, info):
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
		if int('0x1800', 16) <= int(self.current_caid, 16) <= int('0x18ff', 16):
			color = Hex2strColor(self.cryptocolors[0])
		else:
			color = Hex2strColor(self.cryptocolors[1])
			try:
				for caid in available_caids:
					if int('0x1800', 16) <= caid <= int('0x18ff', 16):
						color = Hex2strColor(self.cryptocolors[2])
			except:
				pass
		res = color + 'N'
		res += Hex2strColor(self.cryptocolors[3])
		return res

	def createCryptoBiss(self, info):
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
		if int('0x2600', 16) <= int(self.current_caid, 16) <= int('0x26ff', 16):
			color = Hex2strColor(self.cryptocolors[0])
		else:
			color = Hex2strColor(self.cryptocolors[1])
			try:
				for caid in available_caids:
					if int('0x2600', 16) <= caid <= int('0x26ff', 16):
						color = Hex2strColor(self.cryptocolors[2])
			except:
				pass
		res = color + 'BI'
		res += Hex2strColor(self.cryptocolors[3])
		return res

	def createCryptoDre(self, info):
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
		if int('0x4ae0', 16) <= int(self.current_caid, 16) <= int('0x4ae1', 16):
			color = Hex2strColor(self.cryptocolors[0])
		else:
			color = Hex2strColor(self.cryptocolors[1])
			try:
				for caid in available_caids:
					if int('0x4ae0', 16) <= caid <= int('0x4ae1', 16):
						color = Hex2strColor(self.cryptocolors[2])
			except:
				pass
		res = color + 'DC'
		res += Hex2strColor(self.cryptocolors[3])
		return res

	def createCryptoSpecial(self, info):
		refstr = info.getInfoString(iServiceInformation.sServiceref)
		caid_name = "Free to Air"
		if "%3a//" in refstr.lower() and "127.0.0.1" not in refstr and "0.0.0.0" not in refstr and "localhost" not in refstr or "@" in refstr:
			return "IPTV" + ":%06X:%04X" % (int(self.current_provid, 16), info.getInfo(iServiceInformation.sSID))
		elif int(self.current_caid, 16) == 0:
			return caid_name + ":%06X:%04X" % (int(self.current_provid, 16), info.getInfo(iServiceInformation.sSID))
		try:
			for caid_entry in caid_data:
				if int(caid_entry[0], 16) <= int(self.current_caid, 16) <= int(caid_entry[1], 16):
					caid_name = caid_entry[2]
					break
			return caid_name + ":%04X:%06X:%04X" % (int(self.current_caid, 16), int(self.current_provid, 16), info.getInfo(iServiceInformation.sSID))
		except:
			pass
		return ""

	def createCryptoNameCaid(self, info):
		caid_name = "FTA"
		if int(self.current_caid, 16) == 0:
			return caid_name
		try:
			for caid_entry in self.caid_data:
				if int(caid_entry[0], 16) <= int(self.current_caid, 16) <= int(caid_entry[1], 16):
					caid_name = caid_entry[2]
					break
			return caid_name + ":%04X" % (int(self.current_caid, 16))
		except:
			pass
		return ""

	def createResolution(self, info):
		try:
			yres = int(open("/proc/stb/vmpeg/0/yres", "r").read(), 16)
			if yres > 4096 or yres == 0:
				return ""
		except:
			return ""
		try:
			xres = int(open("/proc/stb/vmpeg/0/xres", "r").read(), 16)
			if xres > 4096 or xres == 0:
				return ""
		except:
			return ""
		mode = ""
		try:
			mode = "p" if int(open("/proc/stb/vmpeg/0/progressive", "r").read(), 16) else "i"
		except:
			pass
		fps = ""
		try:
			fps = str((int(open("/proc/stb/vmpeg/0/framerate", "r").read()) + 500) // 1000)
		except:
			pass

		return "%sx%s%s%s" % (xres, yres, mode, fps)

	def createVideoCodec(self, info):
		return codec_data.get(info.getInfo(iServiceInformation.sVideoType), _("N/A"))

	def createServiceRef(self, info):
		return info.getInfoString(iServiceInformation.sServiceref)

	def createPIDInfo(self, info):
		vpid = info.getInfo(iServiceInformation.sVideoPID)
		apid = info.getInfo(iServiceInformation.sAudioPID)
		pcrpid = info.getInfo(iServiceInformation.sPCRPID)
		sidpid = info.getInfo(iServiceInformation.sSID)
		tsid = info.getInfo(iServiceInformation.sTSID)
		onid = info.getInfo(iServiceInformation.sONID)
		if vpid < 0:
			vpid = 0
		if apid < 0:
			apid = 0
		if pcrpid < 0:
			pcrpid = 0
		if sidpid < 0:
			sidpid = 0
		if tsid < 0:
			tsid = 0
		if onid < 0:
			onid = 0
		return "%d-%d:%05d:%04d:%04d:%04d" % (onid, tsid, sidpid, vpid, apid, pcrpid)

	def createInfoString(self, fieldGroup, fedata, feraw, info):
		if fieldGroup in self.recursionCheck:
			return _("?%s-recursive?") % fieldGroup
		self.recursionCheck.add(fieldGroup)

		fields = self.info_fields[fieldGroup]
		if fields and isinstance(fields[0], (tuple, list)):
			if fieldGroup == "TransponderInfo":
				fields = fields[feraw and int("DVB-T" in feraw.get("tuner_type", "")) + 1 or 0]
			else:
				fields = fields[int(config.usage.show_cryptoinfo.value) > 0]

		ret = ""
		vals = []
		for field in fields:
			val = None
			if field == "CryptoCurrentSource":
				self.getCryptoInfo(info)
				vals.append(self.current_source)
			elif field == "StreamURLInfo":
				val = self.createStreamURLInfo(info)
			elif field == "TransponderModulationFEC":
				val = self.createModulation(fedata) + '-' + self.createFEC(fedata, feraw)
			elif field == "TransponderName":
				val = self.createTransponderName(feraw)
			elif field == "ProviderName":
				val = self.createProviderName(info)
			elif field in ("NewLine", "NL"):
				ret += "  ".join(vals) + "\n"
				vals = []
			else:
				val = self.getTextByType(field)

			if val:
				vals.append(val)

		return ret + "  ".join(vals)

	def createStreamURLInfo(self, info):
		refstr = info.getInfoString(iServiceInformation.sServiceref)
		if "%3a//" in refstr.lower():
			return refstr.replace("%3a", ":").replace("%3A", ":").split("://")[1].split("/")[0].split('@')[-1]
		return ""

	def createFrequency(self, fedata):
		frequency = fedata.get("frequency")
		if frequency:
			return str(frequency)
		return ""

	def createChannelNumber(self, fedata, feraw):
		return "DVB-T" in feraw.get("tuner_type", "") and fedata.get("channel") or ""

	def createSymbolRate(self, fedata, feraw):
		if "DVB-T" in feraw.get("tuner_type", ""):
			bandwidth = fedata.get("bandwidth")
			if bandwidth:
				return bandwidth
		else:
			symbolrate = fedata.get("symbol_rate")
			if symbolrate:
				return str(symbolrate)
		return ""

	def createPolarization(self, fedata):
		return fedata.get("polarization_abbreviation") or ""

	def createFEC(self, fedata, feraw):
		if "DVB-T" in feraw.get("tuner_type", ""):
			code_rate_lp = fedata.get("code_rate_lp")
			code_rate_hp = fedata.get("code_rate_hp")
			guard_interval = fedata.get('guard_interval')
			if code_rate_lp and code_rate_hp and guard_interval:
				return code_rate_lp + "-" + code_rate_hp + "-" + guard_interval
		else:
			fec = fedata.get("fec_inner")
			if fec:
				return fec
		return ""

	def createModulation(self, fedata):
		if fedata.get("tuner_type") == _("Terrestrial"):
			constellation = fedata.get("constellation")
			if constellation:
				return constellation
		else:
			modulation = fedata.get("modulation")
			if modulation:
				return modulation
		return ""

	def createTunerType(self, feraw):
		return feraw.get("tuner_type") or ""

	def createTunerSystem(self, fedata):
		return fedata.get("system") or ""

	def formatOrbPos(self, orbpos):
		if isinstance(orbpos, int) and 0 <= orbpos <= 3600:  # sanity
			if orbpos > 1800:
				return str((float(3600 - orbpos)) / 10.0) + "\xb0" + "W"
			else:
				return str((float(orbpos)) / 10.0) + "\xb0" + "E"
		return ""

	def createOrbPos(self, feraw):
		orbpos = feraw.get("orbital_position")
		return self.formatOrbPos(orbpos)

	def createOrbPosOrTunerSystem(self, fedata, feraw):
		orbpos = self.createOrbPos(feraw)
		if orbpos != "":
			return orbpos
		return self.createTunerSystem(fedata)

	def createTransponderName(self, feraw):
		orbpos = feraw.get("orbital_position")
		if orbpos is None:  # Not satellite
			return ""
		freq = feraw.get("frequency")
		if freq and freq < 10700000:  # C-band
			if orbpos > 1800:
				orbpos += 1
			else:
				orbpos -= 1

		sat_names = {
			30: 'Rascom/Eutelsat 3E',
			48: 'SES 5',
			70: 'Eutelsat 7E',
			90: 'Eutelsat 9E',
			100: 'Eutelsat 10E',
			130: 'Hot Bird',
			160: 'Eutelsat 16E',
			192: 'Astra 1KR/1L/1M/1N',
			200: 'Arabsat 20E',
			216: 'Eutelsat 21.5E',
			235: 'Astra 3',
			255: 'Eutelsat 25.5E',
			260: 'Badr 4/5/6',
			282: 'Astra 2E/2F/2G',
			305: 'Arabsat 30.5E',
			315: 'Astra 5',
			330: 'Eutelsat 33E',
			360: 'Eutelsat 36E',
			380: 'Paksat',
			390: 'Hellas Sat',
			400: 'Express 40E',
			420: 'Turksat',
			450: 'Intelsat 45E',
			480: 'Afghansat',
			490: 'Yamal 49E',
			530: 'Express 53E',
			570: 'NSS 57E',
			600: 'Intelsat 60E',
			620: 'Intelsat 62E',
			685: 'Intelsat 68.5E',
			705: 'Eutelsat 70.5E',
			720: 'Intelsat 72E',
			750: 'ABS',
			765: 'Apstar',
			785: 'ThaiCom',
			800: 'Express 80E',
			830: 'Insat',
			851: 'Intelsat/Horizons',
			880: 'ST2',
			900: 'Yamal 90E',
			915: 'Mesat',
			950: 'NSS/SES 95E',
			1005: 'AsiaSat 100E',
			1030: 'Express 103E',
			1055: 'Asiasat 105E',
			1082: 'NSS/SES 108E',
			1100: 'BSat/NSAT',
			1105: 'ChinaSat',
			1130: 'KoreaSat',
			1222: 'AsiaSat 122E',
			1380: 'Telstar 18',
			1440: 'SuperBird',
			2310: 'Ciel',
			2390: 'Echostar/Galaxy 121W',
			2410: 'Echostar/DirectTV 119W',
			2500: 'Echostar/DirectTV 110W',
			2630: 'Galaxy 97W',
			2690: 'NIMIQ 91W',
			2780: 'NIMIQ 82W',
			2830: 'Echostar/QuetzSat',
			2880: 'AMC 72W',
			2900: 'Star One',
			2985: 'Echostar 61.5W',
			2990: 'Amazonas',
			3020: 'Intelsat 58W',
			3045: 'Intelsat 55.5W',
			3070: 'Intelsat 53W',
			3100: 'Intelsat 50W',
			3150: 'Intelsat 45W',
			3169: 'Intelsat 43.1W',
			3195: 'SES 40.5W',
			3225: 'NSS/Telstar 37W',
			3255: 'Intelsat 34.5W',
			3285: 'Intelsat 31.5W',
			3300: 'Hispasat',
			3325: 'Intelsat 27.5W',
			3355: 'Intelsat 24.5W',
			3380: 'SES 22W',
			3400: 'NSS 20W',
			3420: 'Intelsat 18W',
			3450: 'Telstar 15W',
			3460: 'Express 14W',
			3475: 'Eutelsat 12.5W',
			3490: 'Express 11W',
			3520: 'Eutelsat 8W',
			3530: 'Nilesat/Eutelsat 7W',
			3550: 'Eutelsat 5W',
			3560: 'Amos',
			3592: 'Thor/Intelsat'
		}

		if orbpos in sat_names:
			return sat_names[orbpos]
		else:
			return self.formatOrbPos(orbpos)

	def createProviderName(self, info):
		return info.getInfoString(iServiceInformation.sProvider)

	def createMisPls(self, fedata):
		tmp = ""
		is_id = fedata.get("is_id")
		pls_mode = fedata.get("pls_mode")
		pls_code = fedata.get("pls_code")
		t2mi_plp_id = fedata.get("t2mi_plp_id")
		t2mi_pid = fedata.get("t2mi_pid")
		if is_id is not None and is_id > -1:
			tmp = "MIS %d" % is_id
		if pls_mode is not None and pls_code is not None and pls_code > 0:
			tmp = addspace(tmp) + "%s %d" % (pls_mode, pls_code)
		if t2mi_pid is not None and t2mi_plp_id is not None and t2mi_plp_id > -1:
			tmp = addspace(tmp) + "T2MI %d PID %d" % (t2mi_plp_id, t2mi_pid)
		return tmp

	@cached
	def getText(self):
		self.recursionCheck.clear()
		return self.getTextByType(self.type)

	def getTextByType(self, textType):
		service = self.source.service
		if service is None:
			return ""
		info = service and service.info()

		if not info:
			return ""

		if textType == "CryptoBar":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoBar(info)
			else:
				return ""

		if textType == "CryptoSeca":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoSeca(info)
			else:
				return ""

		if textType == "CryptoVia":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoVia(info)
			else:
				return ""

		if textType == "CryptoIrdeto":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoIrdeto(info)
			else:
				return ""

		if textType == "CryptoNDS":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoNDS(info)
			else:
				return ""

		if textType == "CryptoConax":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoConax(info)
			else:
				return ""

		if textType == "CryptoCryptoW":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoCryptoW(info)
			else:
				return ""

		if textType == "CryptoBeta":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoBeta(info)
			else:
				return ""

		if textType == "CryptoNagra":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoNagra(info)
			else:
				return ""

		if textType == "CryptoBiss":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoBiss(info)
			else:
				return ""

		if textType == "CryptoDre":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoDre(info)
			else:
				return ""

		if textType == "CryptoTandberg":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoTandberg(info)
			else:
				return ""

		if textType == "CryptoSpecial":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoSpecial(info)
			else:
				return ""

		if textType == "CryptoNameCaid":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoNameCaid(info)
			else:
				return ""

		if textType == "ResolutionString":
			return self.createResolution(info)

		if textType == "VideoCodec":
			return self.createVideoCodec(info)

		if self.updateFEdata:
			self.updateFEdata = False
			feinfo = service.frontendInfo()
			if feinfo:
				self.feraw = feinfo.getAll(config.usage.infobar_frontend_source.value == "settings")
				if self.feraw:
					self.fedata = ConvertToHumanReadable(self.feraw)

		feraw = self.feraw
		if not feraw:
			feraw = info.getInfoObject(iServiceInformation.sTransponderData)
			fedata = ConvertToHumanReadable(feraw)
		else:
			fedata = self.fedata

		if textType in self.info_fields:
			return self.createInfoString(textType, fedata, feraw, info)

		if textType == "PIDInfo":
			return self.createPIDInfo(info)

		if textType == "ServiceRef":
			return self.createServiceRef(info)

		if not feraw:
			return ""

		if textType == "TransponderFrequency":
			return self.createFrequency(feraw)

		if textType == "TransponderFrequencyMHz":
			return self.createFrequency(fedata)

		if textType == "TransponderSymbolRate":
			return self.createSymbolRate(fedata, feraw)

		if textType == "TransponderPolarization":
			return self.createPolarization(fedata)

		if textType == "TransponderFEC":
			return self.createFEC(fedata, feraw)

		if textType == "TransponderModulation":
			return self.createModulation(fedata)

		if textType == "OrbitalPosition":
			return self.createOrbPos(feraw)

		if textType == "TunerType":
			return self.createTunerType(feraw)

		if textType == "TunerSystem":
			return self.createTunerSystem(fedata)

		if self.type == "OrbitalPositionOrTunerSystem":
			return self.createOrbPosOrTunerSystem(fedata, feraw)

		if textType == "TerrestrialChannelNumber":
			return self.createChannelNumber(fedata, feraw)

		if textType == "TransponderInfoMisPls":
			return self.createMisPls(fedata)

		return _("?%s?") % textType

	text = property(getText)

	@cached
	def getBool(self):
		service = self.source.service
		info = service and service.info()

		if not info:
			return False

		request_caid = None
		for x in self.ca_table:
			if x[0] == self.type:
				request_caid = x[1]
				request_selected = x[2]
				break

		if request_caid is None:
			return False

		if info.getInfo(iServiceInformation.sIsCrypted) != 1:
			return False

		data = self.ecmdata.getEcmData()

		if data is None:
			return False

		current_caid = data[1]

		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)

		for caid_entry in caid_data:
			if caid_entry[3] == request_caid:
				if request_selected:
					if int(caid_entry[0], 16) <= int(current_caid, 16) <= int(caid_entry[1], 16):
						return True
				else:  # request available
					try:
						for caid in available_caids:
							if int(caid_entry[0], 16) <= caid <= int(caid_entry[1], 16):
								return True
					except:
						pass

		return False

	boolean = property(getBool)

	def changed(self, what):
		if what[0] == self.CHANGED_SPECIFIC:
			self.updateFEdata = False
			if what[1] == iPlayableService.evNewProgramInfo:
				self.updateFEdata = True
			if what[1] == iPlayableService.evEnd:
				self.feraw = self.fedata = None
			Converter.changed(self, what)
		elif what[0] == self.CHANGED_POLL and self.updateFEdata is not None:
			self.updateFEdata = False
			Converter.changed(self, what)
