from Screens.Setup import Setup
from Components.ActionMap import HelpableActionMap
from Components.config import config
from Components.Sources.StaticText import StaticText

import Components.HdmiCec


class HdmiCECSetupScreen(Setup):
	def __init__(self, session):
		self["key_yellow"] = StaticText(_("Set fixed"))
		self["key_blue"] = StaticText(_("Clear fixed"))
		Setup.__init__(self, session=session, setup="hdmicec", plugin="SystemPlugins/HdmiCEC")
		self["actions"] = HelpableActionMap(self, ["ColorActions"],
		{
			"yellow": (self.setFixedAddress, _("Set HDMI-CEC fixed address")),
			"blue": (self.clearFixedAddress, _("Clear HDMI-CEC fixed address")),
		}, prio=-2, description=_("HDMI-CEC address editing actions"))

		self.updateAddress()

	def selectionChanged(self): # This is needed because the description is not standard. i.e. a concatenation.
		self.updateDescription()

	def updateDescription(self): # Called by selectionChanged() or updateAddress()
		self["description"].setText("%s\n%s\n\n%s" % (self.current_address, self.fixed_address, self.getCurrentDescription()))

	def keySelect(self):
		if self.getCurrentItem() == config.hdmicec.log_path:
			self.set_path()
		else:
			Setup.keySelect(self)

	def setFixedAddress(self):
		import Components.HdmiCec
		Components.HdmiCec.hdmi_cec.setFixedPhysicalAddress(Components.HdmiCec.hdmi_cec.getPhysicalAddress())
		self.updateAddress()

	def clearFixedAddress(self):
		import Components.HdmiCec
		Components.HdmiCec.hdmi_cec.setFixedPhysicalAddress("0.0.0.0")
		self.updateAddress()

	def updateAddress(self):
		import Components.HdmiCec
		self.current_address = _("Current CEC address") + ": " + Components.HdmiCec.hdmi_cec.getPhysicalAddress()
		if config.hdmicec.fixed_physical_address.value == "0.0.0.0":
			self.fixed_address = ""
		else:
			self.fixed_address = _("Using fixed address") + ": " + config.hdmicec.fixed_physical_address.value
		self.updateDescription()

	def logPath(self, res):
		if res is not None:
			config.hdmicec.log_path.value = res

	def set_path(self):
		inhibitDirs = ["/autofs", "/bin", "/boot", "/dev", "/etc", "/lib", "/proc", "/sbin", "/sys", "/tmp", "/usr"]
		from Screens.LocationBox import LocationBox
		txt = _("Select directory for logfile")
		self.session.openWithCallback(self.logPath, LocationBox, text=txt, currDir=config.hdmicec.log_path.value,
				bookmarks=config.hdmicec.bookmarks, autoAdd=False, editDir=True,
				inhibitDirs=inhibitDirs, minFree=1
				)


def Plugins(**kwargs):
	# imported directly by menu.xml based on SystemInfo["HDMICEC"]
	return []
