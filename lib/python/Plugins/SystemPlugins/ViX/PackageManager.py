from Components.Console import Console
from Components.Ipkg import IpkgComponent
from Components.Sources.List import List
from Components.ActionMap import ActionMap
from Components.PluginComponent import plugins
from Components.Sources.StaticText import StaticText

from Screens.Ipkg import Ipkg
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen, ScreenSummary
from Screens.Standby import TryQuitMainloop

from Tools.Directories import resolveFilename, SCOPE_PLUGINS, SCOPE_CURRENT_SKIN
from Tools.LoadPixmap import LoadPixmap


class PackageManagerSummary(ScreenSummary):
	def __init__(self, session, parent):
		ScreenSummary.__init__(self, session, parent=parent)


class PackageManager(Screen):
	skin = ["""
		<screen name="PackageManager" position="center,center" size="%d,%d" title="Packet manager" >
			<panel name="__DynamicColorButtonTemplate__"/>
			<widget source="list" render="Listbox" position="%d,%d" size="%d,%d" scrollbarMode="showOnDemand">
				<convert type="TemplatedMultiContent">
					{"template": [
							MultiContentEntryText(pos = (%d, %d), size = (%d, %d), font=0, flags = RT_HALIGN_LEFT, text = 0), # index 0 is the name
							MultiContentEntryText(pos = (%d, %d), size = (%d, %d), font=1, flags = RT_HALIGN_LEFT, text = 2), # index 2 is the description
							MultiContentEntryPixmapAlphaBlend(pos = (%d, %d), size = (%d, %d), png = 4, flags=BT_SCALE), # index 4 is the status pixmap
							MultiContentEntryPixmapAlphaBlend(pos = (%d, %d), size = (%d, %d), png = 5), # index 4 is the div pixmap
						],
					"fonts": [gFont("Regular", %d),gFont("Regular", %d)],
					"itemHeight": %d
					}
				</convert>
			</widget>
		</screen>""",
			560, 420,  # Screen
			5, 50, 550, 365,  # list
			5, 1, 470, 28,  # template
			5, 26, 470, 20,
			475, 2, 48, 48,
			5, 50, 540, 2,
			22, 14,  # font
			52,  # itemHeight
		]  # noqa: E124

	def __init__(self, session):
		Screen.__init__(self, session)
		self.title = _("Package manager")

		self["actions"] = ActionMap(["SetupActions"],
		{
			"ok": self.go,
			"save": self.rebuildList,
			"cancel": self.cancel,
		}, -1)

		self["filterActions"] = ActionMap(["SetupActions"],
		{
			"deleteBackward": self.filterPrev,
			"deleteForward": self.filterNext,
		}, -1)
		self["filterActions"].setEnabled(False)

		self.list = []
		self["list"] = List(self.list)
		self["key_red"] = StaticText(_("Close"))
		self["key_green"] = StaticText(_("opkg update"))
		self["key_previous"] = StaticText()
		self["key_next"] = StaticText()

		self.list_updating = False  # because IpkgComponent sends multiple responses and we only want to react to one of them
		self.packetlist = []
		self.installed_packetlist = {}
		self.upgradeable_packages = {}
		self.Console = Console()
		self.unwanted_extensions = ("-dbg", "-dev", "-doc", "-staticdev", "-src", "busybox")
		self.filters = {"all": _("All"), "installed": _("Installed"), "upgradeable": _("Upgradeable"), "installable": _("Installable")}

		self.installedpng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "icons/installed.png"))
		self.upgradeablepng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "icons/upgradeable.png"))
		self.installablepng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "icons/installable.png"))
		self.divpng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "div-h.png"))
		self.upgradepng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "icons/upgrade.png"))
		self.removepng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "icons/remove.png"))

		self.ipkg = IpkgComponent()
		self.ipkg.addCallback(self.ipkgCallback)
		self.onLayoutFinish.append(self.buildList)

	def cancel(self):
		self.ipkg.stop()
		self.Console.killAll()
		self.close()

	def setStatus(self, status):
		if status == "updating":
			self["list"].setList([(_("Running opkg update"), "", _("Downloading the latest package list. Please wait..."), "", self.upgradepng, self.divpng)])
		elif status == "loading":
			self["list"].setList([(_("Package list loading"), "", _("Loading the package list. Please wait..."), "", self.upgradepng, self.divpng)])
		elif status == "error":
			self["list"].setList([(_("Error"), "", _("An error occurred while downloading the packetlist. Please try again."), "", self.removepng, self.divpng)])

	def rebuildList(self):
		if not self.list_updating:
			self.list_updating = True
			self.setStatus("updating")
			self.ipkg.startCmd(IpkgComponent.CMD_UPDATE)  # sync opkg with the feeds

	def go(self, returnValue=None):
		if cur := self["list"].getCurrent():
			status = cur[3]
			package = cur[0]
			self.wasRemove = False
			if status == "installed":
				self.wasRemove = True
				self.cmd = (IpkgComponent.CMD_REMOVE, {"package": package})
				self.session.openWithCallback(self.runCommand, MessageBox, _("Do you want to remove the package:\n") + package)
			elif status == "upgradeable":
				self.cmd = (IpkgComponent.CMD_INSTALL, {"package": package})
				self.session.openWithCallback(self.runCommand, MessageBox, _("Do you want to update the package:\n") + package)
			elif status == "installable":
				self.cmd = (IpkgComponent.CMD_INSTALL, {"package": package})
				self.session.openWithCallback(self.runCommand, MessageBox, _("Do you want to install the package:\n") + package)

	def runCommand(self, result):
		if result:
			self.session.openWithCallback(self.runCommandFinished, Ipkg, cmdList=[self.cmd])

	def runCommandFinished(self):
		msg = _("Removal has completed.") if self.wasRemove else _("Update has completed.")
		self.session.openWithCallback(self.Reboot, MessageBox, msg + "\n" + _("Do you want to reboot your receiver?"), MessageBox.TYPE_YESNO)

	def Reboot(self, result):
		if result:
			self.session.open(TryQuitMainloop, retvalue=3)
		elif cur := self["list"].getCurrent():
			self.list[self.list.index(cur)] = self.buildEntryComponent(cur[0], cur[1], cur[2], "installable" if self.wasRemove else "installed")
			self.filterList()
			self.reloadPluginlist()

	def ipkgCallback(self, event, param):
		if event == IpkgComponent.EVENT_ERROR:
			self.list_updating = False
			self.setStatus("error")
		elif event == IpkgComponent.EVENT_DONE:
			if self.list_updating:
				self.list_updating = False
				self.buildList()

	def buildList(self):
		self.setStatus("loading")
		cmd = self.ipkg.ipkg + " list"
		self.Console.ePopen(cmd, self.OpkgList_Finished)

	def OpkgList_Finished(self, result, retval, extra_args=None):
		if result:
			self.packetlist = []
			last_name = ""
			for x in result.splitlines():
				if " - " in x:
					tokens = x.split(" - ")
					name = tokens[0].strip()
					if name and not any(name.endswith(x) for x in self.unwanted_extensions):
						tokenLength = len(tokens)
						version = tokenLength > 1 and tokens[1].strip() or ""
						descr = tokenLength > 2 and tokens[2].strip() or ""
						if name == last_name:
							continue
						last_name = name
						self.packetlist.append([name, version, descr])
				elif len(self.packetlist) > 0:
					# no " - " in the text, assume that this is the description
					# therefore add this text to the last packet description
					last_packet = self.packetlist[-1]
					last_packet[2] = last_packet[2] + x
					self.packetlist[:-1] + last_packet
		cmd = self.ipkg.ipkg + " list_installed"
		self.Console.ePopen(cmd, self.OpkgListInstalled_Finished)

	def OpkgListInstalled_Finished(self, result, retval, extra_args=None):
		if result:
			self.installed_packetlist = self.parseResult(result)
		cmd = self.ipkg.ipkg + " list-upgradable"
		self.Console.ePopen(cmd, self.OpkgListUpgradeable_Finished)

	def OpkgListUpgradeable_Finished(self, result, retval, extra_args=None):
		if result:
			self.upgradeable_packages = self.parseResult(result)
		self.buildPacketList()

	def parseResult(self, result):
		packages = {}
		for x in result.splitlines():
			tokens = x.split(" - ")
			name = tokens[0].strip()
			if not any(name.endswith(x) for x in self.unwanted_extensions):
				tokenLength = len(tokens)
				version = tokenLength > 1 and tokens[-1].strip() or ""
				packages[name] = version
		return packages

	def buildEntryComponent(self, name, version, description, state):
		description = _(description) if description else _("No description available.")
		png = state == "installed" and self.installedpng or state == "upgradeable" and self.upgradeablepng or self.installablepng
		return ((name, version, description, state, png, self.divpng))

	def buildPacketList(self):
		self.list = []
		self.i = 0
		for x in self.packetlist:
			status = ""
			if x[0] in self.installed_packetlist:
				if x[0] in self.upgradeable_packages:
					status = "upgradeable"
				else:
					status = "installed"
			else:
				status = "installable"
			self.list.append(self.buildEntryComponent(x[0], x[1], x[2], status))
		self["list"].setList(self.list)
		self.updateTexts()

	def filterPrev(self):
		self.i -= 1
		self.filterList()

	def filterNext(self):
		self.i += 1
		self.filterList()

	def filterList(self):
		if self.list:
			self["list"].setList(self.list if (filter := self.getCurrentFilter()) == "all" else [x for x in self.list if x[3] == filter])
			self.updateTexts()

	def getCurrentFilter(self):
		return list(self.filters.keys())[self.i % len(self.filters)]

	def updateTexts(self):
		if self.list:
			self["filterActions"].setEnabled(True)
			self.title = _("Package manager") + " - " + self.filters[self.getCurrentFilter()]
			self["key_previous"].text = _("PREVIOUS")
			self["key_next"].text = _("NEXT")

	def reloadPluginlist(self):
		plugins.readPluginList(resolveFilename(SCOPE_PLUGINS))

	def createSummary(self):
		return PackageManagerSummary
