from Screens.Screen import Screen
from Components.Label import Label
from Components.ActionMap import ActionMap
from Components.Pixmap import Pixmap
from Components.Sources.Boolean import Boolean
from Components.Sources.StaticText import StaticText
from Components.config import config, configfile, ConfigText, ConfigSubsection, ConfigSelection, ConfigIP, ConfigYesNo, ConfigInteger, getConfigListEntry
from Components.ConfigList import ConfigListScreen
from Screens.MessageBox import MessageBox
from Screens.HelpMenu import HelpableScreen

from enigma import getPeerStreamingBoxes

import re

class FallbackTunerSetup(ConfigListScreen, Screen):
	def __init__(self, session, menu_path=""):
		Screen.__init__(self, session)
		self.setup_title = screentitle = _("Fallback tuner setup")
		if config.usage.show_menupath.value == 'large':
			menu_path += screentitle
			title = menu_path
			self["menu_path_compressed"] = StaticText("")
		elif config.usage.show_menupath.value == 'small':
			title = screentitle
			self["menu_path_compressed"] = StaticText(menu_path + " >" if not menu_path.endswith(' / ') else menu_path[:-3] + " >" or "")
		else:
			title = screentitle
			self["menu_path_compressed"] = StaticText("")
		Screen.setTitle(self, title)
		self.skinName = ["FallbackTunerSetup", "Setup"]
		self.onChangedEntry = []
		self.session = session
		ConfigListScreen.__init__(self, [], session = session, on_change = self.changedEntry)

		self["actions2"] = ActionMap(["SetupActions"],
		{
			"ok": self.keyGo,
			"menu": self.keyCancel,
			"cancel": self.keyCancel,
			"save": self.keyGo,
		}, -2)

		self["key_red"] = StaticText(_("Exit"))
		self["key_green"] = StaticText(_("Save"))

		self["description"] = Label("")
		self["VKeyIcon"] = Boolean(False)
		self["HelpWindow"] = Pixmap()
		self["HelpWindow"].hide()

		self.createConfig()
		self.createSetup()

		if not self.selectionChanged in self["config"].onSelectionChanged:
			self["config"].onSelectionChanged.append(self.selectionChanged)
		self.selectionChanged()

	def createConfig(self):
		self.enabled = ConfigYesNo(default = config.usage.remote_fallback_enabled.value)
		self.domain = ConfigText(default = config.usage.remote_fallback.value, fixed_size = False)
		peerStreamingBoxes = getPeerStreamingBoxes()
		self.peerExist = len(peerStreamingBoxes) != 0
		peerDefault = None
		self.peer = None
		if self.peerExist:
			if config.usage.remote_fallback.value in peerStreamingBoxes:
				peerDefault = config.usage.remote_fallback.value
			self.peer = ConfigSelection(default = peerDefault, choices = [(x,x) for x in peerStreamingBoxes])

		ipDefault = [0,0,0,0]
		self.portDefault = portDefault = 8001
		if config.usage.remote_fallback.value:
			result = re.search("(\d+)[.](\d+)[.](\d+)[.](\d+)", config.usage.remote_fallback.value)
			if result is not None:
				ipDefault = [int(result.group(1)),int(result.group(2)),int(result.group(3)),int(result.group(4))]
			result = re.search("[:](\d+)$", config.usage.remote_fallback.value)
			if result is not None:
				portDefault = int(result.group(1))
		self.ip = ConfigIP( default = ipDefault, auto_jump=True)

		self.port = ConfigInteger(default = portDefault, limits=(1,65535))

		fallbackAddressChoices = [("ip", _("IP")), ("domain", _("URL"))]
		if self.peerExist:
			fallbackAddressChoices.append(("peer", _("Network peer")))
		fallbackAddressTypeDefault = "domain"
		if peerDefault or self.peerExist and self.domain.value == "":
			fallbackAddressTypeDefault = "peer"
		if ipDefault != [0,0,0,0]:
			fallbackAddressTypeDefault = "ip"
		self.fallbackAddressType = ConfigSelection(default = fallbackAddressTypeDefault, choices = fallbackAddressChoices)

		self.enabledEntry = getConfigListEntry(_("Enable fallback remote receiver"), self.enabled,_('Enable usage of tuners from another Enigma2 receiver on the local network. Remote tuners will be used when tuners are not available on this receiver. (No free tuner or service type is not available.)'))
		self.addressTypeEntry = getConfigListEntry(_("Fallback address type"), self.fallbackAddressType,_("'Network peer' automatically detects other Enigma2 receivers on the local network. You can also manually enter the URL or IP address."))
		self.peerEntry = self.peer and getConfigListEntry(_("Network peers"), self.peer,_("Select a receiver to use for fallback tuners. If the host receiver is not listed, manually enter the URL or IP address"))
		self.ipEntry = getConfigListEntry(_("Fallback receiver IP address"), self.ip,_("Enter the IP address of the receiver to use for fallback tuners."))
		self.domainEntry = getConfigListEntry(_("Fallback remote receiver URL"), self.domain,_("Enter the URL/IP of the fallback remote receiver, e.g. '192.168.0.1'. The other details such as 'http://' and port number will be filled in automatically when you select save."))
		self.portEntry = getConfigListEntry(_("Fallback receiver streaming port"), self.port,_("Default port is '%d'. Change if required.") % self.portDefault)

	def createSetup(self):
		self.list = [self.enabledEntry]
		if self.enabled.value:
			self.list.append(self.addressTypeEntry)
			if self.fallbackAddressType.value == "peer":
				self.list.append(self.peerEntry)
			elif self.fallbackAddressType.value == "ip":
				self.list.append(self.ipEntry)
				self.list.append(self.portEntry)
			else:
				self.list.append(self.domainEntry)

		self["config"].list = self.list
		self["config"].l.setList(self.list)

	def selectionChanged(self):
		self["description"].setText(self.getCurrentDescription())

	def changedEntry(self):
		if self["config"].getCurrent() in (self.enabledEntry, self.addressTypeEntry): # only do screen refresh if current entry requires this
			self.createSetup()
		for x in self.onChangedEntry:
			x()

	def keyGo(self):
		config.usage.remote_fallback_enabled.value = self.enabled.value
		if self.fallbackAddressType.value == "domain":
			config.usage.remote_fallback.value = self.check_URL_format(self.domain.value)
		elif self.fallbackAddressType.value == "ip":
			config.usage.remote_fallback.value = "http://%d.%d.%d.%d:%d" % (self.ip.value[0], self.ip.value[1], self.ip.value[2], self.ip.value[3], self.port.value)
		elif self.fallbackAddressType.value == "peer":
			config.usage.remote_fallback.value = self.peer.value
		config.usage.remote_fallback_enabled.save()
		config.usage.remote_fallback.save()
		configfile.save()
		self.close(False)

	def check_URL_format(self, fallbackURL):
		if fallbackURL:
			fallbackURL = "%s%s" % (not fallbackURL.startswith("http://") and "http://" or "", fallbackURL)
			fallbackURL = "%s%s" % (fallbackURL, fallbackURL.count(":") == 1 and ":%s" % self.portDefault or "")
		return fallbackURL
