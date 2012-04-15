# for localized messages
from . import _

from Screens.Screen import Screen
from Components.ActionMap import NumberActionMap
from Components.Sources.StaticText import StaticText
from Components.Sources.List import List
from Components.MultiContent import MultiContentEntryText
from enigma import RT_HALIGN_LEFT, RT_VALIGN_CENTER, gFont

class VIXMenu(Screen):
	skin = """
		<screen name="VIXMenu" position="center,center" size="610,410" >
			<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on" />
			<widget source="key_red" render="Label" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
			<ePixmap pixmap="skin_default/border_menu_350.png" position="5,50" zPosition="1" size="350,300" transparent="1" alphatest="on" />
			<widget source="menu" render="Listbox" position="15,60" size="330,290" scrollbarMode="showOnDemand">
				<convert type="TemplatedMultiContent">
					{"template": [
							MultiContentEntryText(pos = (2, 2), size = (330, 24), flags = RT_HALIGN_LEFT, text = 1), # index 0 is the MenuText,
						],
					"fonts": [gFont("Regular", 22)],
					"itemHeight": 25
					}
				</convert>
			</widget>
			<widget source="menu" render="Listbox" position="360,50" size="240,300" scrollbarMode="showNever" selectionDisabled="1">
				<convert type="TemplatedMultiContent">
					{"template": [
							MultiContentEntryText(pos = (2, 2), size = (240, 300), flags = RT_HALIGN_CENTER|RT_VALIGN_CENTER|RT_WRAP, text = 2), # index 2 is the Description,
						],
					"fonts": [gFont("Regular", 22)],
					"itemHeight": 300
					}
				</convert>
			</widget>
			<widget source="status" render="Label" position="5,360" zPosition="10" size="600,50" halign="center" valign="center" font="Regular;22" transparent="1" shadowColor="black" shadowOffset="-1,-1" />
		</screen>"""

	def __init__(self, session, args = 0):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("ViX"))
		self.menu = args
		self.list = []
		if self.menu == 0:
			self.list.append(("backup-manager", _("Backup Manager"), _("Manage your backups of your settings." ), None))
			self.list.append(("cron-manager", _("Cron Manager"), _("Manage your cron jobs." ), None))
			self.list.append(("image-manager", _("Image Manager"), _("Create and Restore complete images of the system." ), None))
			self.list.append(("ipkg-install", _("Install local extension"),  _("Install IPK's from your tmp folder." ), None))
			self.list.append(("install-extensions", _("Manage Extensions"), _("Manage extensions or plugins for your STB_BOX" ), None))
			self.list.append(("mount-manager",_("Mount Manager"), _("Manage you devices mountpoints." ), None))
			self.list.append(("ipkg-manager", _("Packet Manager"),  _("View, install and remove available or installed packages." ), None))
			self.list.append(("power-manager",_("Power Manager"), _("Create schedules for Standby, Restart GUI, DeepStandby and Reboot."), None))
			self.list.append(("script-runner",_("Script Runner"), _("Run your shell scripts." ), None))
			self.list.append(("software-update", _("Software Update"), _("Online update of your STB_BOX software." ), None))
			self.list.append(("swap-manager",_("Swap Manager"), _("Create and Manage your swapfiles." ), None))
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
		}, -1)
		self.onLayoutFinish.append(self.layoutFinished)
		self.onChangedEntry = []
		self["menu"].onSelectionChanged.append(self.selectionChanged)

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

	def setWindowTitle(self):
		self.setTitle(_("ViX"))

	def go(self, num = None):
		if num is not None:
			num -= 1
			if not num < self["menu"].count():
				return
			self["menu"].setIndex(num)
		current = self["menu"].getCurrent()
		if current:
			currentEntry = current[0]
			if self.menu == 0:
				if (currentEntry == "backup-manager"):
					from BackupManager import VIXBackupManager
					self.session.open(VIXBackupManager)
				elif (currentEntry == "cron-manager"):
					from CronManager import VIXCronManager
					self.session.open(VIXCronManager)
				elif (currentEntry == "image-manager"):
					from ImageManager import VIXImageManager
					self.session.open(VIXImageManager)
				elif (currentEntry == "install-extensions"):
					from SoftwareManager import PluginManager
					self.session.open(PluginManager)
				elif (currentEntry == "ipkg-install"):
					from IPKInstaller import VIXIPKInstaller
					self.session.open(VIXIPKInstaller)
				elif (currentEntry == "ipkg-manager"):
					from SoftwareManager import PacketManager
					self.session.open(PacketManager)
				elif (currentEntry == "mount-manager"):
					from MountManager import VIXDevicesPanel
					self.session.open(VIXDevicesPanel)
				elif (currentEntry == "power-manager"):
					from PowerManager import VIXPowerManager
					self.session.open(VIXPowerManager)
				elif (currentEntry == "script-runner"):
					from ScriptRunner import VIXScriptRunner
					self.session.open(VIXScriptRunner)
				elif (currentEntry == "software-update"):
					from SoftwareManager import UpdatePlugin
					self.session.open(UpdatePlugin)
				elif (currentEntry == "swap-manager"):
					from SwapManager import VIXSwap
					self.session.open(VIXSwap)

	def closeRecursive(self):
		self.close(True)
