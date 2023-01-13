from Components.Console import Console
from Screens.TextBox import TextBox

class AboutUserInstalledPlugins(TextBox):
	def __init__(self, session):
		self.Console = Console()
		TextBox.__init__(self, session, label="AboutScrollLabel")
		self.setTitle(_("User installed plugins"))
		self.skinName = "AboutOE"
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
			self["AboutScrollLabel"].setText("\n".join(sorted(plugins_out)))
		else:
			self["AboutScrollLabel"].setText(_("No user installed plugins found"))
