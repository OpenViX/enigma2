from os import stat
import time

from Components.config import config

ECM_INFO = "/tmp/ecm.info"
EMPTY_ECM_INFO = "", "0", "0", "0", ""

old_ecm_time = time.time()
info = {}
ecm = ""
data = EMPTY_ECM_INFO


class GetEcmInfo:
	def __init__(self):
		pass

	def createCurrentDevice(self, current_device, isLong):
		if not current_device:
			return ""
		if "/sci0" in current_device.lower():
			return _("Card reader 1") if isLong else "CRD 1"
		elif "/sci1" in current_device.lower():
			return _("Card reader 2") if isLong else "CRD 2"
		elif "/ttyusb0" in current_device.lower():
			return _("USB reader 1") if isLong else "USB 1"
		elif "/ttyusb1" in current_device.lower():
			return _("USB reader 2") if isLong else "USB 2"
		elif "/ttyusb2" in current_device.lower():
			return _("USB reader 3") if isLong else "USB 3"
		elif "/ttyusb3" in current_device.lower():
			return _("USB reader 4") if isLong else "USB 4"
		elif "/ttyusb4" in current_device.lower():
			return _("USB reader 5") if isLong else "USB 5"
		elif "emulator" in current_device.lower():
			return _("Emulator") if isLong else "EMU"
		elif "const" in current_device.lower():
			return _("Constcw") if isLong else "CCW"

	def pollEcmData(self):
		global data
		global old_ecm_time
		global info
		global ecm
		try:
			ecm_time = stat(ECM_INFO).st_mtime
		except:
			ecm_time = old_ecm_time
			data = EMPTY_ECM_INFO
			info = {}
			ecm = ""
		if ecm_time != old_ecm_time:
			oecmi1 = info.get("ecminterval1", "")
			oecmi0 = info.get("ecminterval0", "")
			info = {"ecminterval2": oecmi1, "ecminterval1": oecmi0}
			old_ecm_time = ecm_time
			try:
				ecm = open(ECM_INFO, "r").readlines()
			except:
				ecm = ""
			for line in ecm:
				d = line.split(":", 1)
				if len(d) > 1:
					info[d[0].strip()] = d[1].strip()
			data = self.getText()
			return True
		else:
			info["ecminterval0"] = int(time.time() - ecm_time + 0.5)

	def getEcm(self):
		return (self.pollEcmData(), ecm)

	def getEcmData(self):
		self.pollEcmData()
		return data

	def getInfo(self, member, ifempty=""):
		self.pollEcmData()
		return str(info.get(member, ifempty))

	def getInfoRaw(self):
		self.pollEcmData()
		return info

	def getText(self):
		global ecm
		address = ""
		device = ""
		try:
			using = info.get("using", "")
			protocol = info.get("protocol", "")
			alt = config.usage.show_cryptoinfo.value in ("2", "4")
			if using or protocol:
				if config.usage.show_cryptoinfo.value == "0":
					self.textvalue = ""
				elif using == "fta":
					self.textvalue = _("Free To Air")
				elif config.usage.show_cryptoinfo.value in ("1", "2"):  # "One line" or "One line Alt"
					# CCcam
					if protocol == "emu":
						self.textvalue = (x := info.get("ecm time", "")) and "Emu (%ss)" % x
					elif protocol == "constcw":
						self.textvalue = (x := info.get("ecm time", "")) and "Constcw (%ss)" % x
					else:
						if x := (info.get("reader") if alt else info.get("address")) or info.get("from", None):
							address = x.replace(":0", "").replace("cache", "cache ")
							if "local" in address.lower():
								from_arr = address.split("-")
								address = from_arr[0].strip()
								if len(from_arr) > 1:
									device = from_arr[1].strip()
						hops = (x := info.get("hops", "")) and x != "0" and "@" + x or ""
						ecm = (x := info.get("ecm time", "")) and "(%ss)" % x
						devtext = self.createCurrentDevice(device, False) if device else address
						self.textvalue = "  ".join([x for x in (devtext, hops, ecm) if x])

				elif config.usage.show_cryptoinfo.value in ("3", "4"):  # "Two lines" or "Two lines Alt"
					# CCcam
					if x := (info.get("reader") if alt else info.get("address")) or info.get("from"):
						address = (_("Reader:") if alt else _("Server:")) + " " + x.replace(":0", "").replace("cache", "cache ")
						if "const" in protocol.lower():
							device = "constcw"
						if "const" in address.lower() or "emu" in address.lower():
							address = ""
						if "emu" in protocol.lower():
							device = "emulator"
						if "local" in address.lower():
							from_arr = address.split("-")
							address = from_arr[0].strip().replace("Local", "").replace("local", "")
							if len(from_arr) > 1:
								device = from_arr[1].strip()
					protocol = (x := info.get("protocol", "")) and _("Protocol:") + " " + x.replace("-s2s", "-S2s").replace("ext", "Ext").replace("mcs", "Mcs").replace("Cccam", "CCcam").replace("cccam", "CCcam")
					hops = (x := info.get("hops", "")) and _("Hops:") + " " + x
					ecm = (x := info.get("ecm time", "")) and _("Ecm:") + " " + x
					devtext = self.createCurrentDevice(device, True) if device else ""
					self.textvalue = "  ".join([x for x in (address, devtext) if x]) + "\n" + "  ".join([x for x in (protocol, hops, ecm) if x])

			elif info.get("decode"):
				# gbox (untested)
				if info["decode"] == "Network":
					cardid = "id:" + info.get("prov", "")
					try:
						share = open("/tmp/share.info", "r").readlines()
						for line in share:
							if cardid in line:
								self.textvalue = line.strip()
								break
						else:
							self.textvalue = cardid
					except:
						self.textvalue = info["decode"]
				else:
					self.textvalue = info["decode"]
				if ecm[1].startswith("SysID"):
					info["prov"] = ecm[1].strip()[6:]
				if "response" in info:
					self.textvalue += " (0.%ss)" % info["response"]
					info["caid"] = ecm[0][ecm[0].find("CaID 0x") + 7:ecm[0].find(",")]
					info["pid"] = ecm[0][ecm[0].find("pid 0x") + 6:ecm[0].find(" =")]
					info["provid"] = info.get("prov", "0")[:4]

			elif info.get("source", None):
				# wicardd - type 2 / mgcamd
				caid = info.get("caid", None)
				if caid:
					info["caid"] = info["caid"][2:]
					info["pid"] = info["pid"][2:]
				info["provid"] = info["prov"][2:]
				time = ""
				for line in ecm:
					if "msec" in line:
						line = line.split(" ")
						if line[0]:
							time = " (%ss)" % (float(line[0]) / 1000)
							break
				self.textvalue = info["source"] + time

			elif info.get("reader", ""):
				hops = (x := info.get("hops", "")) and x != "0" and " @" + x or ""
				ecm = (x := info.get("ecm time", "")) and " (%ss)" % x
				self.textvalue = info["reader"] + hops + ecm

			elif response := info.get("response time", None):
				response = response.split(" ")
				self.textvalue = "%s (%ss)" % (response[4], float(response[0]) / 1000)

			else:
				self.textvalue = ""

			decCI = info.get("caid", info.get("CAID", "0"))
			provid = info.get("provid", info.get("prov", info.get("Provider", "0")))
			ecmpid = info.get("pid", info.get("ECM PID", "0"))
		except:
			ecm = ""
			self.textvalue = ""
			device = ""
			decCI = "0"
			provid = "0"
			ecmpid = "0"
		return self.textvalue, decCI, provid, ecmpid, device
