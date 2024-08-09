from enigma import eDVBDB
from Components.config import config, ConfigSubsection, ConfigYesNo, ConfigSelection
from Plugins.Plugin import PluginDescriptor
from Screens.MessageBox import MessageBox
from Screens.ChannelSelection import MODE_TV, MODE_RADIO
from Screens.Setup import Setup
from Tools.BoundFunction import boundFunction
from ServiceReference import ServiceReference
from .providers import providers

choices = [(k, providers[k].get("name", _("Other"))) for k in providers.keys()]
config.plugins.terrestrialbouquet = ConfigSubsection()
config.plugins.terrestrialbouquet.enabled = ConfigYesNo()
config.plugins.terrestrialbouquet.providers = ConfigSelection(default=choices[0][0], choices=choices)
config.plugins.terrestrialbouquet.makeradiobouquet = ConfigYesNo()
config.plugins.terrestrialbouquet.skipduplicates = ConfigYesNo(True)


class TerrestrialBouquet:
	def __init__(self):
		self.config = config.plugins.terrestrialbouquet
		self.path = "/etc/enigma2"
		self.bouquetsIndexFilename = "bouquets.tv"
		self.bouquetFilename = "userbouquet.TerrestrialBouquet.tv"
		self.bouquetName = _('Terrestrial')
		self.services = {}
		self.VIDEO_ALLOWED_TYPES = [1, 17, 22, 25, 31, 32] + [4, 5, 24, 27]  # tv (live and NVOD)
		self.AUDIO_ALLOWED_TYPES = [2, 10]

	def getTerrestrials(self, mode):
		terrestrials = {}
		query = "1:7:%s:0:0:0:0:0:0:0:%s ORDER BY name" % (1 if mode == MODE_TV else 2, " || ".join(["(type == %s)" % i for i in self.getAllowedTypes(mode)]))
		if (servicelist := ServiceReference.list(ServiceReference(query))) is not None:
			while (service := servicelist.getNext()) and service.valid():
				if service.getUnsignedData(4) >> 16 == 0xeeee:  # filter (only terrestrial)
					stype, sid, tsid, onid, ns = [int(x, 16) for x in service.toString().split(":", 7)[2:7]]
					name = ServiceReference.getServiceName(service)
					terrestrials["%08x:%04x:%04x:%04x" % (ns, onid, tsid, sid)] = {"name": name, "namespace": ns, "onid": onid, "tsid": tsid, "sid": sid, "type": stype}
		return terrestrials

	def getAllowedTypes(self, mode):
		return self.VIDEO_ALLOWED_TYPES if mode == MODE_TV else self.AUDIO_ALLOWED_TYPES  # tv (live and NVOD) and radio allowed service types

	def readLcnDb(self):
		LCNs = {}
		if LCNData := eDVBDB.getInstance().getLcnDBData():
			for service in LCNData:
				ns, onid, tsid, sid, lcn, signal = service
				if ns >> 16 == 0xeeee:  # filter (only terrestrial)
					LCNs["%08x:%04x:%04x:%04x" % (ns, onid, tsid, sid)] = {"lcn": lcn, "signal": signal}
			LCNs = {k: v for k, v in sorted(list(LCNs.items()), key=lambda x: (x[1]["lcn"], abs(x[1]["signal"] - 65535)))} if LCNs else LCNs
		return LCNs

	def rebuild(self):
		if not self.config.enabled.value:
			return _("Terrestrial Bouquet plugin is not enabled.")
		msg = _("Try running a manual scan of terrestrial frequencies. If this fails maybe there is no lcn data available in your area.")
		self.services.clear()
		if not (LCNs := self.readLcnDb()):
			return (_("There is currently no LCN data stored.")) + " " + msg
		for mode in (MODE_TV, MODE_RADIO):
			terrestrials = self.getTerrestrials(mode)
			for k in terrestrials:
				if k in LCNs:
					terrestrials[k] |= LCNs[k]
			self.services |= terrestrials
		self.services = {k: v for k, v in sorted(list(self.services.items()), key=lambda x: ("lcn" in x[1] and x[1]["lcn"] or 65535, "signal" in x[1] and abs(x[1]["signal"] - 65536) or 65535))}
		LCNsUsed = []  # duplicates (we are already ordered by highest signal strength)
		for k in list(self.services.keys()):  # use list to avoid RuntimeError: dictionary changed size during iteration
			if "lcn" not in self.services[k] or self.services[k]["lcn"] in LCNsUsed:
				if self.config.skipduplicates.value:
					del self.services[k]
				else:
					self.services[k]["duplicate"] = True
			else:
				LCNsUsed.append(self.services[k]["lcn"])
		if not self.services:
			return _("No corresponding terrestrial services found.") + " " + msg
		self.createBouquet()

	def readBouquetIndex(self, mode):
		try:  # may not exist
			return open(self.path + "/%s%s" % (self.bouquetsIndexFilename[:-2], "tv" if mode == MODE_TV else "radio"), "r").read()
		except Exception as e:  # noqa: F841
			return ""

	def writeBouquetIndex(self, bouquetIndexContent, mode):
		bouquets_index_list = []
		bouquets_index_list.append("#NAME Bouquets (%s)\n" % ("TV" if mode == MODE_TV else "Radio"))
		bouquets_index_list.append("#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET \"%s%s\" ORDER BY bouquet\n" % (self.bouquetFilename[:-2], "tv" if mode == MODE_TV else "radio"))
		if bouquetIndexContent:
			lines = bouquetIndexContent.split("\n", 1)
			if lines[0][:6] != "#NAME ":
				bouquets_index_list.append("%s\n" % lines[0])
			if len(lines) > 1:
				bouquets_index_list.append("%s" % lines[1])
		bouquets_index = open(self.path + "/" + self.bouquetsIndexFilename[:-2] + ("tv" if mode == MODE_TV else "radio"), "w")
		bouquets_index.write(''.join(bouquets_index_list))
		bouquets_index.close()

	def writeBouquet(self, mode):
		allowed_service_types = not self.config.makeradiobouquet.value and self.VIDEO_ALLOWED_TYPES + self.AUDIO_ALLOWED_TYPES or self.getAllowedTypes(mode)
		lcnindex = {v["lcn"]: k for k, v in self.services.items() if not v.get("duplicate") and v.get("lcn") and v.get("type") in allowed_service_types}
		highestLCN = max(list(lcnindex.keys()))
		sections = providers[self.config.providers.value].get("sections", {})
		active_sections = [max((x for x in list(sections.keys()) if int(x) <= key)) for key in list(lcnindex.keys())] if sections else []
		if not self.config.skipduplicates.value and (duplicates := sorted([(k, v) for k, v in self.services.items() if v.get("duplicate") and v.get("type") in allowed_service_types], key=lambda x: x[1]["name"].lower())):
			duplicate_range = {"lower": highestLCN + 1, "upper": 65535} | providers[self.config.providers.value].get("duplicates", {})
			for i in range(duplicate_range["lower"], duplicate_range["upper"] + 1):
				if i not in lcnindex:
					duplicate = duplicates.pop(0)
					lcnindex[i] = duplicate[0]
					if not len(duplicates):
						break
			sections[duplicate_range["lower"]] = _("Duplicates")
			active_sections.append(duplicate_range["lower"])
			highestLCN = max(list(lcnindex.keys()))
		bouquet_list = []
		bouquet_list.append("#NAME %s\n" % providers[self.config.providers.value].get("bouquetname", self.bouquetName))
		for number in range(1, (highestLCN) // 1000 * 1000 + 1001):   # ceil bouquet length to nearest 1000, range needs + 1
			if mode == MODE_TV and number in active_sections:
				bouquet_list.append(self.bouquetMarker(sections[number]))
			if number in lcnindex:
				bouquet_list.append(self.bouquetServiceLine(self.services[lcnindex[number]]))
			else:
				bouquet_list.append("#SERVICE 1:320:0:0:0:0:0:0:0:0:\n")  # bouquet spacer
		bouquetFile = open(self.path + "/" + self.bouquetFilename[:-2] + ("tv" if mode == MODE_TV else "radio"), "w")
		bouquetFile.write(''.join(bouquet_list))
		bouquetFile.close()

	def bouquetServiceLine(self, service):
		return "#SERVICE 1:0:%x:%x:%x:%x:%x:0:0:0:\n" % (service["type"], service["sid"], service["tsid"], service["onid"], service["namespace"])

	def bouquetMarker(self, text):
		return "#SERVICE 1:64:0:0:0:0:0:0:0:0:\n#DESCRIPTION %s\n" % text

	def createBouquet(self):
		radio_services = [x for x in self.services.values() if x["type"] in self.AUDIO_ALLOWED_TYPES and "lcn" in x]
		for mode in (MODE_TV, MODE_RADIO):
			if mode == MODE_RADIO and (not radio_services or not self.config.makeradiobouquet.value):
				break
			bouquetIndexContent = self.readBouquetIndex(mode)
			if '"' + self.bouquetFilename[:-2] + ("tv" if mode == MODE_TV else "radio") + '"' not in bouquetIndexContent:  # only edit the index if bouquet file is not present
				self.writeBouquetIndex(bouquetIndexContent, mode)
			self.writeBouquet(mode)
		eDVBDB.getInstance().reloadBouquets()


class PluginSetup(Setup, TerrestrialBouquet):
	def __init__(self, session):
		TerrestrialBouquet.__init__(self)
		Setup.__init__(self, session, blue_button={'function': self.startrebuild, 'helptext': _("Build/rebuild terrestrial bouquet now based on the last scan.")})
		self.title = _("Terrestrial Bouquet setup")
		self.updatebluetext()

	def createSetup(self):
		configlist = []
		indent = "- "
		configlist.append((_("Enable terrestrial bouquet"), self.config.enabled, _("Enable creating a terrestrial bouquet based on LCN (logocal channel number) data.") + " " + _("This plugin depends on LCN data being broadcast by your local tansmitter.") + " " + _("Once configured the bouquet will be updated automatically when doing a manual scan.")))
		if self.config.enabled.value:
			configlist.append((indent + _("Region"), self.config.providers, _("Select your region.")))
			configlist.append((indent + _("Create separate radio bouquet"), self.config.makeradiobouquet, _("Put radio services in a separate bouquet, not the main tv bouquet. This is required when the provider duplicates channel numbers for tv and radio.")))
			configlist.append((indent + _("Skip duplicates"), self.config.skipduplicates, _("Do not add duplicated or non indexed channels to the bouquet.")))
		self["config"].list = configlist

	def changedEntry(self):
		Setup.changedEntry(self)
		self.updatebluetext()

	def updatebluetext(self):
		self["key_blue"].text = _("Rebuild bouquet") if self.config.enabled.value else ""

	def startrebuild(self):
		if self.config.enabled.value:
			self.saveAll()
			if msg := self.rebuild():
				mb = self.session.open(MessageBox, msg, MessageBox.TYPE_ERROR)
				mb.setTitle(_("Terrestrial Bouquet Error"))
			else:
				mb = self.session.open(MessageBox, _("Terrestrial bouquet successfully rebuilt."), MessageBox.TYPE_INFO)
				mb.setTitle(_("Terrestrial Bouquet"))
				self.closeRecursive()


def PluginCallback(close, answer=None):
	if close and answer:
		close(True)


def PluginMain(session, close=None, **kwargs):
	session.openWithCallback(boundFunction(PluginCallback, close), PluginSetup)


def PluginStart(menuid, **kwargs):
	return menuid == "scan" and [(_("Terrestrial Bouquet"), PluginMain, "PluginMain", None)] or []


def Plugins(**kwargs):
	from Components.NimManager import nimmanager
	if nimmanager.hasNimType("DVB-T"):
		from Screens.ServiceScan import ServiceScan
		__origfunc = ServiceScan.ok

		def __newfunc(self, *args, **kwargs):
			if self["scan"].isDone() and "Terrestrial" in str(self.scanList):
				from Plugins.SystemPlugins.TerrestrialBouquet.plugin import TerrestrialBouquet
				print("[TerrestrialBouquet] rebuilding terrestrial bouquet -", TerrestrialBouquet().rebuild() or "was successful")
			__origfunc(self, *args, **kwargs)  # now run ServiceScan.ok
		ServiceScan.ok = __newfunc
		return [PluginDescriptor(name=_("Terrestrial Bouquet"), description=_("Create an ordered bouquet of terrestrial services based on LCN data from your local transmitter."), where=PluginDescriptor.WHERE_MENU, needsRestart=False, fnc=PluginStart)]
	return []
