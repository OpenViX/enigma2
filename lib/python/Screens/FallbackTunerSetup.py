from Components.config import config, configfile, ConfigText, ConfigSelection, ConfigIP, ConfigYesNo, ConfigInteger
from Screens.Setup import Setup
from enigma import getPeerStreamingBoxes
import re


class FallbackTunerSetup(Setup):
	def __init__(self, session):
		self.createConfig()
		Setup.__init__(self, session=session, setup=None)
		self.title = _("Fallback Tuner Setup")

	def createConfig(self):
		self.enabled = ConfigYesNo(default=config.usage.remote_fallback_enabled.value)
		self.domain = ConfigText(default=config.usage.remote_fallback.value, fixed_size=False)
		peerStreamingBoxes = getPeerStreamingBoxes()
		self.peerExist = len(peerStreamingBoxes) != 0
		peerDefault = None
		self.peer = None
		if self.peerExist:
			if config.usage.remote_fallback.value in peerStreamingBoxes:
				peerDefault = config.usage.remote_fallback.value
			self.peer = ConfigSelection(default=peerDefault, choices=[(x, x) for x in peerStreamingBoxes])

		ipDefault = [0, 0, 0, 0]
		self.portDefault = portDefault = 8001
		if config.usage.remote_fallback.value:
			result = re.search("(\d+)[.](\d+)[.](\d+)[.](\d+)", config.usage.remote_fallback.value)
			if result is not None:
				ipDefault = [int(result.group(1)), int(result.group(2)), int(result.group(3)), int(result.group(4))]
			result = re.search("[:](\d+)$", config.usage.remote_fallback.value)
			if result is not None:
				portDefault = int(result.group(1))
		self.ip = ConfigIP(default=ipDefault, auto_jump=True)

		self.port = ConfigInteger(default=portDefault, limits=(1, 65535))

		fallbackAddressChoices = [("ip", _("IP")), ("domain", _("URL"))]
		if self.peerExist:
			fallbackAddressChoices.append(("peer", _("Network peer")))
		fallbackAddressTypeDefault = "domain"
		if peerDefault or self.peerExist and self.domain.value == "":
			fallbackAddressTypeDefault = "peer"
		if ipDefault != [0, 0, 0, 0]:
			fallbackAddressTypeDefault = "ip"
		self.fallbackAddressType = ConfigSelection(default=fallbackAddressTypeDefault, choices=fallbackAddressChoices)

	def createSetup(self):
		self.list = [(_("Enable fallback remote receiver"), self.enabled, _('Enable usage of tuners from another Enigma2 receiver on the local network. Remote tuners will be used when tuners are not available on this receiver. (No free tuner or service type is not available.)'))]
		if self.enabled.value:
			self.list.append((_("Fallback address type"), self.fallbackAddressType, _("'Network peer' automatically detects other Enigma2 receivers on the local network. You can also manually enter the URL or IP address.")))
			if self.fallbackAddressType.value == "peer":
				self.list.append((_("Network peers"), self.peer, _("Select a receiver to use for fallback tuners. If the host receiver is not listed, manually enter the URL or IP address")))
			elif self.fallbackAddressType.value == "ip":
				self.list.append((_("Fallback receiver IP address"), self.ip, _("Enter the IP address of the receiver to use for fallback tuners.")))
				self.list.append((_("Fallback receiver streaming port"), self.port, _("Default port is '%d'. Change if required.") % self.portDefault))
			else:
				self.list.append((_("Fallback remote receiver URL"), self.domain, _("Enter the URL/IP of the fallback remote receiver, e.g. '192.168.0.1'. The other details such as 'http://' and port number will be filled in automatically when you select save.")))

		currentItem = self["config"].getCurrent()
		self["config"].setList(self.list)
		self.moveToItem(currentItem)

	def keySave(self):
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
