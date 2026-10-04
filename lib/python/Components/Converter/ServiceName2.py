# -*- coding: utf-8 -*-
#
# Extended ServiceName Converter for Enigma2 Dreamboxes (ServiceName2.py)
# Coded by vlamo (c) 2011
#
# Version: 0.4 (03.06.2011 18:40)
# Version: 0.5 (08.09.2012) add Alternative numbering mode support - Dmitry73 & 2boom
# Version: 0.6 (19.10.2012) add stream mapping
# Version: 0.7 (19.09.2013) add iptv info - nikolasi & 2boom
# Version: 0.8 (29.10.2013) add correct output channelnumner - Dmitry73
# Version: 0.9 (18.11.2013) code fix and optimization - Taapat & nikolasi
# Version: 1.0 (04.12.2013) code fix and optimization - Dmitry73
# Version: 1.1 (06-17.12.2013) small cosmetic fix - 2boom
# Version: 1.2 (25.12.2013) small iptv fix - MegAndretH
# Version: 1.3 (27.01.2014) small iptv fix - 2boom
# Version: 1.4 (30.06.2014) fix iptv reference - 2boom
# Version: 1.5 (04.07.2014) fix iptv reference cosmetic - 2boom
# Support: http://dream.altmaster.net/ & http://gisclub.tv
#

from functools import partial

from enigma import iServiceInformation, iPlayableService, iPlayableServicePtr, eServiceReference, eServiceCenter, eTimer, getBestPlayableServiceReference

from Components.config import config
from Components.Converter.Converter import Converter
from Components.Element import cached

import NavigationInstance
try:
	from Components.Renderer.ChannelNumber import ChannelNumberClasses
	correctChannelNumber = True
except:
	correctChannelNumber = False


class ServiceName2(Converter):
	NAME = 0
	NUMBER = 1
	BOUQUET = 2
	PROVIDER = 3
	REFERENCE = 4
	ORBPOS = 5
	TPRDATA = 6
	SATELLITE = 7
	ALLREF = 8
	FORMAT = 9

	# Skin type name -> type. An empty type is the name, anything unknown is a format string.
	KEYWORDS = {
		"Name": NAME,
		"Number": NUMBER,
		"Bouquet": BOUQUET,
		"Provider": PROVIDER,
		"Reference": REFERENCE,
		"OrbitalPos": ORBPOS,
		"TransponderInfo": TPRDATA,
		"Satellite": SATELLITE,
		"AllRef": ALLREF
	}

	# Map each type to the name of the method that produces its text. They all take (info, ref, refstr).
	HANDLERS = {
		NAME: "nameText",
		NUMBER: "numberText",
		BOUQUET: "bouquetText",
		PROVIDER: "providerText",
		REFERENCE: "referenceText",
		ORBPOS: "orbitalPosText",
		TPRDATA: "transponderDataText",
		SATELLITE: "satelliteText",
		ALLREF: "allRefText",
		FORMAT: "formatText"
	}

	# The letters of a format string (after a %) that have a method of their own, and the letters handled by getTransponderInfo.
	FORMAT_HANDLERS = {
		"N": "nameText",
		"n": "numberText",
		"B": "bouquetText",
		"P": "providerText",
		"R": "referenceText",
		"S": "satelliteText",
		"A": "allRefText"
	}
	TRANSPONDER_LETTERS = "TtsFfiOMpYroclhmgbe"

	# Transponder letter -> method that produces its text. They all take the tuner type.
	TRANSPONDER_HANDLERS = {
		"t": "tpTunerType",
		"s": "tpSystem",
		"F": "tpFrequency",
		"f": "tpFec",
		"i": "tpInversion",
		"O": "tpOrbitalPosition",
		"M": "tpModulation",
		"p": "tpPolarization",
		"Y": "tpSymbolRate",
		"r": "tpRolloff",
		"o": "tpPilot",
		"c": "tpConstellation",
		"l": "tpCodeRateLP",
		"h": "tpCodeRateHP",
		"m": "tpTransmissionMode",
		"g": "tpGuardInterval",
		"b": "tpBandwidth",
		"e": "tpHierarchy"
	}

	# What the transponder text shows when no letters are asked for.
	TRANSPONDER_FORMAT_SATELLITE = ("O ", "s ", "M ", "F ", "p ", "Y ", "f")  # orbital_position system modulation frequency polarization symbol_rate fec
	TRANSPONDER_FORMAT_CABLE = ("t ", "F ", "Y ", "i ", "f ", "M")  # type frequency symbol_rate inversion fec modulation
	TRANSPONDER_FORMAT_TERRESTRIAL = ("t ", "F ", "c ", "l ", "h ", "m ", "g ")  # type frequency constellation code_rate_lp code_rate_hp transmission_mode guard_interval
	TRANSPONDER_FORMAT_TERRESTRIAL_REF = ("O ", "F ", "c ", "l ", "h ", "m ", "g ")  # the same, starting with orbital_position

	# The first needle found in a service reference names its IPTV provider. The order matters.
	IPTV_PROVIDERS = (
		(("tvshka",), "SCHURA"),
		(("udp/239.0.1",), "Lanet"),
		(("3a7777",), "IPTVNTV"),
		(("KartinaTV",), "KartinaTV"),
		(("Megaimpuls",), "MEGAIMPULSTV"),
		(("Newrus",), "NEWRUSTV"),
		(("Sovok",), "SOVOKTV"),
		(("Rodnoe",), "RODNOETV"),
		(("238.1.1.89%3a1234",), "TRK UKRAINE"),
		(("238.1.1.181%3a1234",), "VIASAT"),
		(("cdnet",), "NonameTV"),
		(("unicast",), "StarLink"),
		(("udp/239.255.2.",), "Planeta"),
		(("udp/233.7.70.",), "Rostelecom"),
		(("udp/239.1.1.",), "Real"),
		(("udp/238.0.", "udp/233.191."), "Triolan"),
		(("%3a8208",), "MovieStar"),
		(("udp/239.0.0.",), "Trinity"),
		((".cn.ru", "novotelecom"), "Novotelecom"),
		(("www.youtube.com",), "www.youtube.com"),
		((".torrent-tv.ru",), "torrent-tv.ru"),
		(("web.tvbox.md",), "web.tvbox.md"),
		(("live-p12",), "PAC12"),
		(("4097",), "StreamTV"),
		(("%3a1234",), "IPTV1")
	)

	def __init__(self, type):
		Converter.__init__(self, type)
		self.type = self.KEYWORDS.get(type, self.FORMAT) if len(str(type)) else self.NAME
		if self.type == self.FORMAT:
			self.sfmt = type[:]
		# Number and bouquet changes have to wait a moment for the channel list to catch up.
		self.delayedChange = self.type in (self.NUMBER, self.BOUQUET) or (self.type == self.FORMAT and ('%n' in self.sfmt or '%B' in self.sfmt))
		try:
			if (self.type == self.NUMBER or (self.type == self.FORMAT and '%n' in self.sfmt)) and correctChannelNumber:
				ChannelNumberClasses.append(self.forceChanged)
		except:
			pass
		self.refstr = self.isStream = self.ref = self.info = self.what = self.tpdata = None
		if self.delayedChange:
			self.Timer = eTimer()
			self.Timer.callback.append(self.neededChange)
		self.IPTVcontrol, self.AlternativeControl = self.additionalServices()
		# Resolve everything that depends on the type once; getText never has to work it out again.
		self.handler = getattr(self, self.HANDLERS[self.type])
		self.transponderHandlers = {letter: getattr(self, name) for letter, name in self.TRANSPONDER_HANDLERS.items()}
		if self.type == self.FORMAT:
			parts = self.sfmt.split("%")
			self.formatHead = parts[0]
			self.formatParts = tuple(self.formatPart(part) for part in parts[1:])

	def formatPart(self, part):
		# What a "%x" of a format string produces, and the text that follows it.
		letter = part[:1]
		if letter in self.FORMAT_HANDLERS:
			handler = getattr(self, self.FORMAT_HANDLERS[letter])
		elif letter in self.TRANSPONDER_LETTERS:
			handler = partial(self.transponderText, letter)
		else:
			handler = None
		return handler, part[1:]

	def additionalServices(self):
		# Look through the bouquets once for IPTV services and for alternative (group) services.
		serviceHandler = eServiceCenter.getInstance()
		found = [False, False]  # IPTV, alternative

		def searchService(bouquet):
			servicelist = serviceHandler.list(bouquet)
			if servicelist is not None:
				while True:
					s = servicelist.getNext()
					if not s.valid():
						break
					if not (s.flags & (eServiceReference.isMarker | eServiceReference.isDirectory)):
						if not found[0] and "%3a//" in s.toString().lower():
							found[0] = True
						if not found[1] and s.flags & eServiceReference.isGroup:
							found[1] = True
						if found[0] and found[1]:
							return

		if not config.usage.multibouquet.value:
			service_types_tv = '1:7:1:0:0:0:0:0:0:0:(type == 1) || (type == 17) || (type == 22) || (type == 25) || (type == 134) || (type == 195)'
			rootstr = '%s FROM BOUQUET "userbouquet.favourites.tv" ORDER BY bouquet' % (service_types_tv)
			searchService(eServiceReference(rootstr))
		else:
			rootstr = '1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "bouquets.tv" ORDER BY bouquet'
			bouquetlist = serviceHandler.list(eServiceReference(rootstr))
			if bouquetlist is not None:
				while True:
					bouquet = bouquetlist.getNext()
					if not bouquet.valid():
						break
					if bouquet.flags & eServiceReference.isDirectory:
						searchService(bouquet)
						if found[0] and found[1]:
							break
		return found[0], found[1]

	def isAdditionalService(self, type=0):
		return self.additionalServices()[type]

	def getServiceNumber(self, ref):
		def searchHelper(serviceHandler, num, bouquet):
			servicelist = serviceHandler.list(bouquet)
			if servicelist is not None:
				while True:
					s = servicelist.getNext()
					if not s.valid():
						break
					if not (s.flags & (eServiceReference.isMarker | eServiceReference.isDirectory)):
						num += 1
						if s == ref:
							return s, num
			return None, num

		if isinstance(ref, eServiceReference):
			isRadioService = ref.getData(0) in (2, 10)
			lastpath = isRadioService and config.radio.lastroot.value or config.tv.lastroot.value
			if 'FROM BOUQUET' not in lastpath:
				if 'FROM PROVIDERS' in lastpath:
					return 'P', 'Provider'
				if 'FROM SATELLITES' in lastpath:
					return 'S', 'Satellites'
				if ') ORDER BY name' in lastpath:
					return 'A', 'All Services'
				return 0, 'N/A'
			try:
				acount = config.plugins.NumberZapExt.enable.value and config.plugins.NumberZapExt.acount.value or config.usage.alternative_number_mode.value
			except:
				acount = False
			rootstr = ''
			for x in lastpath.split(';'):
				if x != '':
					rootstr = x
			serviceHandler = eServiceCenter.getInstance()
			if acount is True or not config.usage.multibouquet.value:
				bouquet = eServiceReference(rootstr)
				service, number = searchHelper(serviceHandler, 0, bouquet)
			else:
				if isRadioService:
					bqrootstr = '1:7:2:0:0:0:0:0:0:0:FROM BOUQUET "bouquets.radio" ORDER BY bouquet'
				else:
					bqrootstr = '1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "bouquets.tv" ORDER BY bouquet'
				number = 0
				cur = eServiceReference(rootstr)
				bouquet = eServiceReference(bqrootstr)
				bouquetlist = serviceHandler.list(bouquet)
				if bouquetlist is not None:
					while True:
						bouquet = bouquetlist.getNext()
						if not bouquet.valid():
							break
						if bouquet.flags & eServiceReference.isDirectory:
							service, number = searchHelper(serviceHandler, number, bouquet)
							if service is not None and cur == bouquet:
								break
			if service is not None:
				info = serviceHandler.info(bouquet)
				name = info and info.getName(bouquet) or ''
				return number, name
		return 0, ''

	def getProviderName(self, ref):
		if isinstance(ref, eServiceReference):
			from Screens.ChannelSelection import service_types_radio, service_types_tv
			typestr = ref.getData(0) in (2, 10) and service_types_radio or service_types_tv
			pos = typestr.rfind(':')
			rootstr = '%s (channelID == %08x%04x%04x) && %s FROM PROVIDERS ORDER BY name' % (typestr[:pos + 1], ref.getUnsignedData(4), ref.getUnsignedData(2), ref.getUnsignedData(3), typestr[pos + 1:])
			provider_root = eServiceReference(rootstr)
			serviceHandler = eServiceCenter.getInstance()
			providerlist = serviceHandler.list(provider_root)
			if providerlist is not None:
				while True:
					provider = providerlist.getNext()
					if not provider.valid():
						break
					if provider.flags & eServiceReference.isDirectory:
						servicelist = serviceHandler.list(provider)
						if servicelist is not None:
							while True:
								service = servicelist.getNext()
								if not service.valid():
									break
								if service == ref:
									info = serviceHandler.info(provider)
									return info and info.getName(provider) or "Unknown"
		return ""

	def getTransponderInfo(self, info, ref, fmt):
		result = ""
		if self.tpdata is None:
			if ref:
				self.tpdata = info.getInfoObject(ref, iServiceInformation.sTransponderData)
			else:
				self.tpdata = info.getInfoObject(iServiceInformation.sTransponderData)
			if not isinstance(self.tpdata, dict):
				self.tpdata = None
				return result
		if self.isStream:
			type = 'IP-TV'
		else:
			type = self.tpdata.get('tuner_type', '')
		if not fmt or fmt == 'T':
			if type == 'DVB-C':
				fmt = self.TRANSPONDER_FORMAT_CABLE
			elif type == 'DVB-T':
				fmt = self.TRANSPONDER_FORMAT_TERRESTRIAL_REF if ref else self.TRANSPONDER_FORMAT_TERRESTRIAL
			elif type == 'IP-TV':
				return _("Streaming")
			else:
				fmt = self.TRANSPONDER_FORMAT_SATELLITE
		for line in fmt:
			handler = self.transponderHandlers.get(line[:1])
			if handler:
				result += handler(type)
			result += line[1:]
		return result

	def tpTunerType(self, type):  # %t - tuner_type (dvb-s/s2/c/t)
		if type == 'DVB-S':
			return _("Satellite")
		elif type == 'DVB-C':
			return _("Cable")
		elif type == 'DVB-T':
			return _("Terrestrial")
		elif type == 'IP-TV':
			return _('Stream-tv')
		return 'N/A'

	def tpSystem(self, type):  # %s - system (dvb-s/s2/c/t)
		if type == 'DVB-S':
			x = self.tpdata.get('system', 0)
			return x in range(2) and {0: 'DVB-S', 1: 'DVB-S2'}[x] or ''
		return type

	def tpFrequency(self, type):  # %F - frequency (dvb-s/s2/c/t) in KHz
		result = ""
		if type in ('DVB-S') and self.tpdata.get('frequency', 0) > 0:
			result += '%d MHz' % (self.tpdata.get('frequency', 0) / 1000)
		if type in ('DVB-C', 'DVB-T'):
			result += '%.3f MHz' % (((self.tpdata.get('frequency', 0) + 500) / 1000) / 1000.0)
		return result

	def tpFec(self, type):  # %f - fec_inner (dvb-s/s2/c/t)
		if type in ('DVB-S', 'DVB-C'):
			x = self.tpdata.get('fec_inner', 15)
			return x in list(range(10)) + [15] and {0: 'Auto', 1: '1/2', 2: '2/3', 3: '3/4', 4: '5/6', 5: '7/8', 6: '8/9', 7: '3/5', 8: '4/5', 9: '9/10', 15: 'None'}[x] or ''
		elif type == 'DVB-T':
			x = self.tpdata.get('code_rate_lp', 5)
			return x in range(6) and {0: '1/2', 1: '2/3', 2: '3/4', 3: '5/6', 4: '7/8', 5: 'Auto'}[x] or ''
		return ""

	def tpInversion(self, type):  # %i - inversion (dvb-s/s2/c/t)
		if type in ('DVB-S', 'DVB-C', 'DVB-T'):
			x = self.tpdata.get('inversion', 2)
			return x in range(3) and {0: 'On', 1: 'Off', 2: 'Auto'}[x] or ''
		return ""

	def tpOrbitalPosition(self, type):  # %O - orbital_position (dvb-s/s2)
		if type == 'DVB-S':
			x = self.tpdata.get('orbital_position', 0)
			return x > 1800 and "%d.%d°W" % ((3600 - x) / 10, (3600 - x) % 10) or "%d.%d°E" % (x / 10, x % 10)
		elif type == 'DVB-T':
			return 'DVB-T'
		elif type == 'DVB-C':
			return 'DVB-C'
		elif type == 'Iptv':
			return 'Stream'
		return ""

	def tpModulation(self, type):  # %M - modulation (dvb-s/s2/c)
		x = self.tpdata.get('modulation', 1)
		if type == 'DVB-S':
			return x in range(4) and {0: 'Auto', 1: 'QPSK', 2: '8PSK', 3: 'QAM16'}[x] or ''
		elif type == 'DVB-C':
			return x in range(6) and {0: 'Auto', 1: 'QAM16', 2: 'QAM32', 3: 'QAM64', 4: 'QAM128', 5: 'QAM256'}[x] or ''
		return ""

	def tpPolarization(self, type):  # %p - polarization (dvb-s/s2)
		if type == 'DVB-S':
			x = self.tpdata.get('polarization', 0)
			return x in range(4) and {0: 'H', 1: 'V', 2: 'LHC', 3: 'RHC'}[x] or '?'
		return ""

	def tpSymbolRate(self, type):  # %Y - symbol_rate (dvb-s/s2/c)
		if type in ('DVB-S', 'DVB-C'):
			return '%d' % (self.tpdata.get('symbol_rate', 0) / 1000)
		return ""

	def tpRolloff(self, type):  # %r - rolloff (dvb-s2)
		if not self.isStream:
			x = self.tpdata.get('rolloff')
			if x is not None:
				return x in range(3) and {0: '0.35', 1: '0.25', 2: '0.20'}[x] or ''
		return ""

	def tpPilot(self, type):  # %o - pilot (dvb-s2)
		if not self.isStream:
			x = self.tpdata.get('pilot')
			if x is not None:
				return x in range(3) and {0: 'Off', 1: 'On', 2: 'Auto'}[x] or ''
		return ""

	def tpConstellation(self, type):  # %c - constellation (dvb-t)
		if type == 'DVB-T':
			x = self.tpdata.get('constellation', 3)
			return x in range(4) and {0: 'QPSK', 1: 'QAM16', 2: 'QAM64', 3: 'Auto'}[x] or ''
		return ""

	def tpCodeRateLP(self, type):  # %l - code_rate_lp (dvb-t)
		if type == 'DVB-T':
			x = self.tpdata.get('code_rate_lp', 5)
			return x in range(6) and {0: '1/2', 1: '2/3', 2: '3/4', 3: '5/6', 4: '7/8', 5: 'Auto'}[x] or ''
		return ""

	def tpCodeRateHP(self, type):  # %h - code_rate_hp (dvb-t)
		if type == 'DVB-T':
			x = self.tpdata.get('code_rate_hp', 5)
			return x in range(6) and {0: '1/2', 1: '2/3', 2: '3/4', 3: '5/6', 4: '7/8', 5: 'Auto'}[x] or ''
		return ""

	def tpTransmissionMode(self, type):  # %m - transmission_mode (dvb-t)
		if type == 'DVB-T':
			x = self.tpdata.get('transmission_mode', 2)
			return x in range(3) and {0: '2k', 1: '8k', 2: 'Auto'}[x] or ''
		return ""

	def tpGuardInterval(self, type):  # %g - guard_interval (dvb-t)
		if type == 'DVB-T':
			x = self.tpdata.get('guard_interval', 4)
			return x in range(5) and {0: '1/32', 1: '1/16', 2: '1/8', 3: '1/4', 4: 'Auto'}[x] or ''
		return ""

	def tpBandwidth(self, type):  # %b - bandwidth (dvb-t)
		if type == 'DVB-T':
			x = self.tpdata.get('bandwidth', 0)
			if isinstance(x, int):
				return str("%.3f" % (float(x) / 1000000.0)).rstrip('0').rstrip('.') + " MHz" if x else "Auto"
		return ""

	def tpHierarchy(self, type):  # %e - hierarchy_information (dvb-t)
		if type == 'DVB-T':
			x = self.tpdata.get('hierarchy_information', 4)
			return x in range(5) and {0: 'None', 1: '1', 2: '2', 3: '4', 4: 'Auto'}[x] or ''
		return ""

	def getSatelliteName(self, ref):
		if isinstance(ref, eServiceReference):
			orbpos = ref.getUnsignedData(4) >> 16
			if orbpos == 0xFFFF:  # Cable
				return _("Cable")
			elif orbpos == 0xEEEE:  # Terrestrial
				return _("Terrestrial")
			else:  # Satellite
				orbpos = ref.getData(4) >> 16
				if orbpos < 0:
					orbpos += 3600
				try:
					from Components.NimManager import nimmanager
					return str(nimmanager.getSatDescription(orbpos))
				except:
					dir = ref.flags & (eServiceReference.isDirectory | eServiceReference.isMarker)
					if not dir:
						refString = ref.toString().lower()
						if refString.startswith("-1"):
							return ''
						elif refString.startswith("1:134:"):
							return _("Alternative")
						elif refString.startswith("4097:"):
							return _("Internet")
						else:
							return orbpos > 1800 and "%d.%d°W" % ((3600 - orbpos) / 10, (3600 - orbpos) % 10) or "%d.%d°E" % (orbpos / 10, orbpos % 10)
		return ""

	def getIPTVProvider(self, refstr):
		for needles, name in self.IPTV_PROVIDERS:
			for needle in needles:
				if needle in refstr:
					return name
		return ""

	def getPlayingref(self, ref):
		playingref = None
		if NavigationInstance.instance:
			playingref = NavigationInstance.instance.getCurrentlyPlayingServiceReference()
		if not playingref:
			playingref = eServiceReference()
		return playingref

	def resolveAlternate(self, ref):
		nref = getBestPlayableServiceReference(ref, self.getPlayingref(ref))
		if not nref:
			nref = getBestPlayableServiceReference(ref, eServiceReference(), True)
		return nref

	def getReferenceType(self, refstr, ref):
		if ref is None:
			if NavigationInstance.instance:
				playref = NavigationInstance.instance.getCurrentlyPlayingServiceReference()
				if playref:
					refstr = playref.toString() or ''
					prefix = ''
					if refstr.startswith("4097:"):
						prefix += "GStreamer "
					if '%3a//' in refstr:
						sref = ' '.join(refstr.split(':')[10:])
						refstr = prefix + sref
					else:
						sref = ':'.join(refstr.split(':')[:10])
						refstr = prefix + sref
		else:
			if refstr != '':
				prefix = ''
				if refstr.startswith("1:7:"):
					if 'FROM BOUQUET' in refstr:
						prefix += "Bouquet "
					elif '(provider == ' in refstr:
						prefix += "Provider "
					elif '(satellitePosition == ' in refstr:
						prefix += "Satellit "
					elif '(channelID == ' in refstr:
						prefix += "Current tr "
				elif refstr.startswith("1:134:"):
					prefix += "Alter "
				elif refstr.startswith("1:64:"):
					prefix += "Marker "
				elif refstr.startswith("4097:"):
					prefix += "GStreamer "
				if self.isStream:
					if self.refstr:
						if '%3a//' in self.refstr:
							sref = ' '.join(self.refstr.split(':')[10:])
						else:
							sref = ':'.join(self.refstr.split(':')[:10])
					else:
						sref = ' '.join(refstr.split(':')[10:])
					return prefix + sref
				else:
					if self.refstr:
						sref = ':'.join(self.refstr.split(':')[:10])
					else:
						sref = ':'.join(refstr.split(':')[:10])
					return prefix + sref
		return refstr

	@cached
	def getText(self):
		service = self.source.service
		if isinstance(service, iPlayableServicePtr):
			info = service and service.info()
			ref = None
		else:  # reference
			info = service and self.source.info
			ref = service
		if not info:
			return ""
		if ref:
			refstr = ref.toString()
		else:
			refstr = info.getInfoString(iServiceInformation.sServiceref)
		if refstr is None:
			refstr = ''
		if self.AlternativeControl:
			if ref and refstr.startswith("1:134:") and self.ref is None:
				nref = self.resolveAlternate(ref)
				if nref:
					self.ref = nref
					self.info = eServiceCenter.getInstance().info(self.ref)
					self.refstr = self.ref.toString()
					if not self.info:
						return ""
		if self.IPTVcontrol:
			if '%3a//' in refstr or (self.refstr and '%3a//' in self.refstr) or refstr.startswith("4097:"):
				self.isStream = True
		return self.handler(info, ref, refstr)

	text = property(getText)

	# ---- Text ----

	def nameText(self, info, ref, refstr):
		name = ref and (info.getName(ref) or 'N/A') or (info.getName() or 'N/A')
		if self.ref:
			name += " (alter)"
		return name.replace('\xc2\x86', '').replace('\xc2\x87', '')

	def numberText(self, info, ref, refstr):
		try:
			service = self.source.serviceref
			num = service and service.getChannelNum() or None
		except:
			num = None
		if num:
			return str(num)
		num, bouq = self.getServiceNumber(ref or eServiceReference(info.getInfoString(iServiceInformation.sServiceref)))
		return num and str(num) or ''

	def bouquetText(self, info, ref, refstr):
		num, bouq = self.getServiceNumber(ref or eServiceReference(info.getInfoString(iServiceInformation.sServiceref)))
		return bouq

	def providerText(self, info, ref, refstr):
		if self.isStream:
			if self.refstr and '%3a//' in self.refstr:
				return self.getIPTVProvider(self.refstr)
			return self.getIPTVProvider(refstr)
		if self.ref:
			return self.getProviderName(self.ref)
		if ref:
			return self.getProviderName(ref)
		return info.getInfoString(iServiceInformation.sProvider) or ''

	def referenceText(self, info, ref, refstr):
		return self.refstr or refstr

	def orbitalPosText(self, info, ref, refstr):
		if self.isStream:
			return "Stream"
		if self.ref and self.info:
			return self.getTransponderInfo(self.info, self.ref, 'O')
		return self.getTransponderInfo(info, ref, 'O')

	def transponderDataText(self, info, ref, refstr):
		if self.isStream:
			return _("Streaming")
		if self.ref and self.info:
			return self.getTransponderInfo(self.info, self.ref, 'T')
		return self.getTransponderInfo(info, ref, 'T')

	def satelliteText(self, info, ref, refstr):
		if self.isStream:
			return _("Internet")
		if self.ref:
			return self.getSatelliteName(self.ref)
		return self.getSatelliteName(ref or eServiceReference(info.getInfoString(iServiceInformation.sServiceref)))

	def allRefText(self, info, ref, refstr):
		tmpref = self.getReferenceType(refstr, ref)
		if 'Bouquet' in tmpref or 'Satellit' in tmpref or 'Provider' in tmpref:
			return ' '
		elif '%3a' in tmpref:
			return ':'.join(refstr.split(':')[:10])
		return tmpref

	def transponderText(self, letter, info, ref, refstr):
		if self.ref:
			return self.getTransponderInfo(self.info, self.ref, letter)
		return self.getTransponderInfo(info, ref, letter)

	def formatText(self, info, ref, refstr):
		ret = self.formatHead
		for handler, tail in self.formatParts:
			if handler:
				ret += handler(info, ref, refstr)
			ret += tail
		return ret.replace('N/A', '').strip()

	def neededChange(self):
		if self.what:
			Converter.changed(self, self.what)
			self.what = None

	def forceChanged(self, what):
		if what is True:
			self.refstr = self.isStream = self.ref = self.info = self.tpdata = None
			Converter.changed(self, (self.CHANGED_ALL,))
			self.what = None

	def changed(self, what):
		if what[0] != self.CHANGED_SPECIFIC or what[1] in (iPlayableService.evStart,):
			self.refstr = self.isStream = self.ref = self.info = self.tpdata = None
			if self.delayedChange:
				self.what = what
				self.Timer.start(200, True)
			else:
				Converter.changed(self, what)
