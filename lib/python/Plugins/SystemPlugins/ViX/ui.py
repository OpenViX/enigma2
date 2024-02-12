from Components.ActionMap import NumberActionMap
from Components.config import config
from Components.Sources.StaticText import StaticText
from Components.Sources.List import List
from Components.SystemInfo import SystemInfo
from Screens.ParentalControlSetup import ProtectedScreen
from Screens.Screen import Screen


class VIXMenu(Screen, ProtectedScreen):
	skin = ["""
		<screen name="VIXMenu" position="center,center" size="%d,%d">
			<panel name="__DynamicColorButtonTemplate__"/>
			<widget source="menu" render="Listbox" position="%d,%d" size="%d,%d" scrollbarMode="showOnDemand">
				<convert type="TemplatedMultiContent">
					{"template": [
							MultiContentEntryText(pos = (%d,%d), size = (%d,%d), flags = RT_HALIGN_LEFT, text = 1), # index 0 is the MenuText,
						],
					"fonts": [gFont("Regular",%d)],
					"itemHeight":%d
					}
				</convert>
			</widget>
			<widget source="menu" render="Listbox" position="%d,%d" size="%d,%d" scrollbarMode="showNever" selectionDisabled="1">
				<convert type="TemplatedMultiContent">
					{"template": [
							MultiContentEntryText(pos = (%d,%d), size = (%d,%d), flags = RT_HALIGN_CENTER|RT_VALIGN_CENTER|RT_WRAP, text = 2), # index 2 is the Description,
						],
					"fonts": [gFont("Regular",%d)],
					"itemHeight":%d
					}
				</convert>
			</widget>
			<widget source="status" render="Label" position="%d,%d" zPosition="10" size="%d,%d" halign="center" valign="center" font="Regular;%d" transparent="1" shadowColor="black" shadowOffset="-1,-1" />
		</screen>""",
			610, 410,  # screen
			15, 60, 330, 286,  # first menu Listbox
			2, 0, 330, 26,  # template one
			22,  # fonts
			26,  # ItemHeight
			360, 50, 240, 300,  # second menu Listbox
			2, 2, 240, 300,  # template two
			22,  # fonts
			300,  # itemHeight
			5, 360, 600, 50, 22,  # status
			]  # noqa: E124

	def __init__(self, session, args=0):
		Screen.__init__(self, session)
		ProtectedScreen.__init__(self)
		self.setTitle(_("ViX"))
		self.menu = args
		self.list = []
		if self.menu == 0:
			self.list.append(("backup-manager", _("Backup manager"), _("Manage settings backup."), None))
			self.list.append(("image-manager", _("Image manager"), _("Backup/Flash/ReBoot system image."), None))
			self.list.append(("ipkg-install", _("Install local extension"), _("Install IPK's from your tmp folder."), None))
			self.list.append(("mount-manager", _("Mount manager"), _("Manage your devices mount points."), None))
			self.list.append(("script-runner", _("Script runner"), _("Run your shell scripts."), None))
			self.list.append(("swap-manager", _("SWAP manager"), _("Create and Manage your SWAP files."), None))
			if SystemInfo["HasH9SD"]:
				self.list.append(("H9SDcard manager", _("H9SDcard Manager"), _("Move Nand root to SD card"), None))
		self["menu"] = List(self.list)
		self["key_red"] = StaticText(_("Close"))

		self["shortcuts"] = NumberActionMap(["ShortcutActions", "WizardActions", "InfobarEPGActions", "MenuActions", "NumberActions"],
			{
				"ok": self.go,
				"back": self.close,
				"red": self.close,
				"menu": self.closeRecursive,
				"1": self.go,
				"2": self.go,
				"3": self.go,
				"4": self.go,
				"5": self.go,
				"6": self.go,
				"7": self.go,
				"8": self.go,
				"9": self.go,
			}, -1)  # noqa: E123
		self.onLayoutFinish.append(self.layoutFinished)
		self.onChangedEntry = []
		self["menu"].onSelectionChanged.append(self.selectionChanged)

	def isProtected(self):
		return config.ParentalControl.setuppinactive.value and config.ParentalControl.config_sections.vixmenu.value

	def createSummary(self):
		from Screens.PluginBrowser import PluginBrowserSummary
		return PluginBrowserSummary

	def selectionChanged(self):
		item = self["menu"].getCurrent()
		if item:
			name = item[1]
			desc = item[2]
		else:
			name = "-"
			desc = ""
		for cb in self.onChangedEntry:
			cb(name, desc)

	def layoutFinished(self):
		idx = 0
		self["menu"].index = idx

	def go(self, num=None):
		if num is not None:
			num -= 1
			if not num < self["menu"].count():
				return
			self["menu"].setIndex(num)
		current = self["menu"].getCurrent()
		if current:
			currentEntry = current[0]
			if self.menu == 0:
				if currentEntry == "backup-manager":
					from .BackupManager import VIXBackupManager
					self.session.open(VIXBackupManager)
				elif currentEntry == "image-manager":
					from .ImageManager import VIXImageManager
					self.session.open(VIXImageManager)
				elif currentEntry == "H9SDcard manager":
					from .H9SDmanager import H9SDmanager
					self.session.open(H9SDmanager)
				elif currentEntry == "ipkg-install":
					from .IPKInstaller import VIXIPKInstaller
					self.session.open(VIXIPKInstaller)
				elif currentEntry == "mount-manager":
					from .MountManager import VIXDevicesPanel
					self.session.open(VIXDevicesPanel)
				elif currentEntry == "script-runner":
					from .ScriptRunner import VIXScriptRunner
					self.session.open(VIXScriptRunner, None)
				elif currentEntry == "swap-manager":
					from .SwapManager import VIXSwap
					self.session.open(VIXSwap)

	def closeRecursive(self):
		self.close(True)
