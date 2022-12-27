from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.Console import Console
from Components.ScrollLabel import ScrollLabel
from Components.Sources.StaticText import StaticText
from Screens.Screen import Screen, ScreenSummary

class AboutUserInstalledPlugins(Screen):
	def __init__(self, session):
		self.Console = Console()
		Screen.__init__(self, session)
		self.setTitle(_("User installed plugins"))
		self.skinName = "AboutOE"

		self["key_red"] = Button(_("Close"))
		self["actions"] = ActionMap(["SetupActions", "NavigationActions"],
		{
			"cancel": self.close,
			"up": self.pageUp,
			"down": self.pageDown,
			"left": self.pageUp,
			"right": self.pageDown,
			"pageUp": self.pageUp,
			"pageDown": self.pageDown,
		}, -2)

		
		self["AboutScrollLabel"] = ScrollLabel()
		self.onLayoutFinish.append(self.checkOPKG)

	def checkOPKG(self):
		self.Console.ePopen("opkg status", self.readOPKG)

	def readOPKG(self, result, retval, extra_args):
		if result:
			plugins_out = []
			opkg_status_list = result.split("\n\n")
			for opkg_status in opkg_status_list:
				plugin = ""
				opkg_status_split = opkg_status.split("\n")
				for line in opkg_status_split:
					if line.startswith("Package"):
						parts = line.strip().split()
						if len(parts) > 1 and parts[1] not in ("opkg", "openvix-base"):
							plugin = parts[1]
							continue
					if plugin and line.startswith("Status") and "user installed" in line:
						plugins_out.append(plugin)
						break
#			print("[AboutUserInstalledPlugins]\n" + ("\n".join(sorted(plugins_out))) + "\n")
			self["AboutScrollLabel"].setText("\n".join(sorted(plugins_out)))
		else:
			self["AboutScrollLabel"].setText(_("No user installed plugins found"))

	def pageUp(self):
		self["AboutScrollLabel"].pageUp()

	def pageDown(self):
		self["AboutScrollLabel"].pageDown()

	def createSummary(self):
		return AboutUserInstalledPluginsSummary


class AboutUserInstalledPluginsSummary(ScreenSummary):
	def __init__(self, session, parent):
		ScreenSummary.__init__(self, session, parent=parent)
		self.skinName = "AboutSummary"
		self["AboutText"] = StaticText(_("User installed plugins"))
