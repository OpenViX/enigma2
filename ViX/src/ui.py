# for localized messages
from os import listdir, path, mkdir

from . import _
from Screens.Screen import Screen
from Components.ActionMap import NumberActionMap
from Components.Sources.StaticText import StaticText
from Components.Sources.List import List
from Screens.ParentalControlSetup import ProtectedScreen
from Components.config import config


class VIXMenu(Screen, ProtectedScreen):
	def __init__(self, session, args=0):
		Screen.__init__(self, session)
		ProtectedScreen.__init__(self)
		Screen.setTitle(self, _("ViX"))
		self.menu = args
		self.list = []
		if self.menu == 0:
			self.list.append(("backup-manager", _("Backup Manager"), _("Manage the backups of your settings."), None))
			self.list.append(("image-manager", _("Image Manager"), _("Create and Restore complete images of your system."), None))
			self.list.append(("ipkg-install", _("Install local extension"), _("Install IPK's from your tmp folder."), None))
			self.list.append(("mount-manager", _("Mount Manager"), _("Manage your devices mount points."), None))
			self.list.append(("script-runner", _("Script Runner"), _("Run your shell scripts."), None))
			self.list.append(("swap-manager", _("Swap Manager"), _("Create and Manage your swap files."), None))
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

	def setWindowTitle(self):
		self.setTitle(_("ViX"))

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
					from BackupManager import VIXBackupManager

					self.session.open(VIXBackupManager)
				elif currentEntry == "image-manager":
					from ImageManager import VIXImageManager

					self.session.open(VIXImageManager)
				elif currentEntry == "ipkg-install":
					from IPKInstaller import VIXIPKInstaller

					self.session.open(VIXIPKInstaller)
				elif currentEntry == "mount-manager":
					from MountManager import VIXDevicesPanel

					self.session.open(VIXDevicesPanel)
				elif currentEntry == "script-runner":
					list = []
					if not path.exists('/usr/script'):
						mkdir('/usr/script', 0755)
					f = listdir('/usr/script')
					for line in f:
						parts = line.split()
						pkg = parts[0]
						if pkg.find('.sh') >= 0:
							list.append(pkg)

					from ScriptRunner import VIXScriptRunner

					self.session.open(VIXScriptRunner, list)
				elif currentEntry == "swap-manager":
					from SwapManager import VIXSwap

					self.session.open(VIXSwap)

	def closeRecursive(self):
		self.close(True)
