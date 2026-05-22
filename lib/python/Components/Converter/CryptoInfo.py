from Components.Converter.Converter import Converter
from Components.Converter.Poll import Poll
from Components.Element import cached
from Components.config import config
from enigma import iServiceInformation
from Tools.GetEcmInfo import GetEcmInfo
from Tools.Directories import pathExists


class CryptoInfo(Converter, Poll):
	def __init__(self, type):
		Converter.__init__(self, type)
		Poll.__init__(self)
		self.type = type
		self.poll_interval = 1000
		self.poll_enabled = True
		self.ecmdata = GetEcmInfo()

	@cached
	def getText(self):
		if not int(config.usage.show_cryptoinfo.value):
			return ""

		service = self.source.service
		info = service and service.info()

		if not info:
			return ""

		is_crypted = bool(info.getInfo(iServiceInformation.sIsCrypted))

		if self.type == "VerboseInfo":
			return self.ecmdata.getEcmData()[0] if is_crypted else ""

		if self.type == "FullInfo":
			return self._getFullInfo(info, is_crypted)

		return self.ecmdata.getInfo(self.type) if is_crypted else ""

	def _getFullInfo(self, info, is_crypted):
		if not is_crypted:
			return "Free-to-air"

		if not (info.getInfoObject(iServiceInformation.sCAIDs) or pathExists("/tmp/ecm.info")):
			return ""

		try:  # what exception is this try expecting?
			ecm = self.ecmdata.getInfoRaw()
			if not ecm:
				return "No parse cannot Emu"

			caid = "%0.4X" % int(ecm.get("caid", ecm.get("CAID", "0")), 16)
			prov = "%0.6X" % int(ecm.get("provid", ecm.get("prov", ecm.get("Provider", "0"))), 16)
			ecm_time = ecm.get("ecm time", "")

			if "msec" not in ecm_time:
				ecm_time = ecm_time.replace(".", "").lstrip("0") + " msec"

			ecm_time = ecm_time.replace("msec", "ms")

			protocol = ecm.get("protocol", "")
			reader = ecm.get("reader", "")
			hops = ecm.get("hops", "")

			server, port = (x.strip() for x in ecm.get("from", "").partition(":")[::2])

			if protocol == "emu":
				source = "emu"
			elif protocol == "constcw":
				source = "constcw"
			elif server == "local":
				source = "sci"
			else:
				source = "net"

			if source in ("emu", "constcw"):
				return f"{source} - {caid} ({caid}:{prov}) - {reader} - {ecm_time}"

			if reader:
				if source == "net":
					host = f"{server}:{port}" if port else server
					return f"{source} - {caid}:{prov} - {reader}, {protocol} ({host}@{hops}) - {ecm_time}"

				return f"{source} - {caid}:{prov} - {reader}, {protocol} (local) - {ecm_time}"

			if protocol:
				if server or port:
					return f"{source} - {caid}:{prov}, {protocol} ({server}:{port}) - {ecm_time}"

				return f"{source} - {caid}:{prov}, {protocol} - {ecm_time}"

			return f"{source} - {caid} - {ecm_time}, Prov: {prov}"

		except Exception as e:
			print("[CryptoInfo][_getFullInfo] exception\n", e)
			return ""

	text = property(getText)
