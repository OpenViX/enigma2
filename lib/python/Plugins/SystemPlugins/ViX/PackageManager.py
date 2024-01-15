import os
import time
import pickle

from enigma import eRCInput, getPrevAsciiCode

from Components.Console import Console
from Components.Ipkg import IpkgComponent
from Components.Sources.List import List
from Components.ActionMap import NumberActionMap
from Components.PluginComponent import plugins
from Components.Sources.StaticText import StaticText

from Screens.Ipkg import Ipkg
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Standby import TryQuitMainloop

from Tools.Directories import resolveFilename, SCOPE_PLUGINS, SCOPE_CURRENT_PLUGIN, SCOPE_CURRENT_SKIN
from Tools.LoadPixmap import LoadPixmap
from Tools.NumericalTextInput import NumericalTextInput


def write_cache(cache_file, cache_data):
	try:
		path = os.path.dirname(cache_file)
		if not os.path.isdir(path):
			os.mkdir(path)
		pickle.dump(cache_data, open(cache_file, "wb"), -1)
	except Exception as ex:
		print("Failed to write cache data to %s:" % cache_file, ex)


def valid_cache(cache_file, cache_ttl):
	try:
		mtime = os.stat(cache_file)[os.stat.ST_MTIME]
	except:
		return 0
	curr_time = time.time()
	if (curr_time - mtime) > cache_ttl:
		return 0
	else:
		return 1


def load_cache(cache_file):
	return pickle.load(open(cache_file, "rb"))


class PackageManager(Screen, NumericalTextInput):
	skin = ["""
		<screen name="PackageManager" position="center,center" size="%d,%d" title="Packet manager" >
			<ePixmap pixmap="skin_default/buttons/red.png" position="%d,%d" size="%d,%d" alphatest="blend" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="%d,%d" size="%d,%d" alphatest="blend" />
			<widget source="key_red" render="Label" position="%d,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
			<widget source="key_green" render="Label" position="%d,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" />
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
			530, 420,  # Screen
			0, 0, 140, 40,  # colours
			140, 0, 140, 40,
			0, 0, 140, 40, 20,
			140, 0, 140, 40, 20,
			5, 50, 520, 365,  # list
			5, 1, 440, 28,  # template
			5, 26, 440, 20,
			445, 2, 48, 48,
			5, 50, 510, 2,
			22, 14,  # font
			52,  # itemHeight
			]

	def __init__(self, session):
		Screen.__init__(self, session)
		NumericalTextInput.__init__(self)
		self.setTitle(_("Package manager"))

		self.setUseableChars("1234567890abcdefghijklmnopqrstuvwxyz")

		self["shortcuts"] = NumberActionMap(["SetupActions", "InputAsciiActions"],
		{
			"ok": self.go,
			"cancel": self.exit,
			"save": self.reload,
			"gotAsciiCode": self.keyGotAscii,
			"1": self.keyNumberGlobal,
			"2": self.keyNumberGlobal,
			"3": self.keyNumberGlobal,
			"4": self.keyNumberGlobal,
			"5": self.keyNumberGlobal,
			"6": self.keyNumberGlobal,
			"7": self.keyNumberGlobal,
			"8": self.keyNumberGlobal,
			"9": self.keyNumberGlobal,
			"0": self.keyNumberGlobal
		}, -1)

		self.list = []
		self.statuslist = []
		self["list"] = List(self.list)
		self["key_red"] = StaticText(_("Close"))
		self["key_green"] = StaticText(_("Refresh list"))

		self.imagePath = "%s/images/" % os.path.dirname(os.path.realpath(__file__))
		self.list_updating = True
		self.packetlist = []
		self.installed_packetlist = {}
		self.upgradeable_packages = {}
		self.Console = Console()
		self.cmdList = []
		self.cachelist = []
		self.cache_ttl = 86400  #600 is default, 0 disables, Seconds cache is considered valid (24h should be ok for caching opkgs)
		self.cache_file = "/etc/enigma2/packetmanager.cache"  # Path to cache directory
		self.oktext = _("\nAfter pressing OK, please wait!")
		self.unwanted_extensions = ("-dbg", "-dev", "-doc", "-staticdev", "-src", "busybox")

		self.ipkg = IpkgComponent()
		self.ipkg.addCallback(self.ipkgCallback)
		self.onLayoutFinish.append(self.rebuildList)

		rcinput = eRCInput.getInstance()
		rcinput.setKeyboardMode(rcinput.kmAscii)

	def keyNumberGlobal(self, val):
		key = self.getKey(val)
		if key is not None:
			keyvalue = key.encode("utf-8")
			if len(keyvalue) == 1:
				self.setNextIdx(keyvalue[0])

	def keyGotAscii(self):
		keyvalue = chr(getPrevAsciiCode()).encode("utf-8")
		if len(keyvalue) == 1:
			self.setNextIdx(keyvalue[0])

	def setNextIdx(self, char):
		if char in ("0", "1", "a"):
			self["list"].setIndex(0)
		else:
			idx = self.getNextIdx(char)
			if idx and idx <= self["list"].count:
				self["list"].setIndex(idx)

	def getNextIdx(self, char):
		for idx, i in enumerate(self["list"].list):
			if i[0] and (i[0][0] == char):
				return idx

	def exit(self):
		self.ipkg.stop()
		if self.Console is not None:
			self.Console.killAll()
		rcinput = eRCInput.getInstance()
		rcinput.setKeyboardMode(rcinput.kmNone)
		self.close()

	def reload(self):
		if os.path.exists(self.cache_file):
			os.unlink(self.cache_file)
			self.list_updating = True
			self.rebuildList()

	def setStatus(self, status=None):
		if status:
			self.statuslist = []
			divpng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "div-h.png"))
			if status == "update":
				statuspng = LoadPixmap(cached=True, path=self.imagePath + "upgrade.png")
				self.statuslist.append((_("Package list update"), "", _("Downloading a new packet list. Please wait..."), "", statuspng, divpng))
				self["list"].setList(self.statuslist)
			elif status == "error":
				statuspng = LoadPixmap(cached=True, path=self.imagePath + "remove.png")
				self.statuslist.append((_("Error"), "", _("An error occurred while downloading the packetlist. Please try again."), "", statuspng, divpng))
				self["list"].setList(self.statuslist)

	def rebuildList(self):
		self.setStatus("update")
		self.inv_cache = 0
		self.vc = valid_cache(self.cache_file, self.cache_ttl)
		if self.cache_ttl > 0 and self.vc != 0:
			try:
				self.buildPacketList()
			except:
				self.inv_cache = 1
		if self.cache_ttl == 0 or self.inv_cache == 1 or self.vc == 0:
			self.run = 0
			self.ipkg.startCmd(IpkgComponent.CMD_UPDATE)

	def go(self, returnValue=None):
		cur = self["list"].getCurrent()
		if cur:
			status = cur[3]
			package = cur[0]
			self.cmdList = []
			if status == "installed":
				self.cmdList.append((IpkgComponent.CMD_REMOVE, {"package": package}))
				if len(self.cmdList):
					self.session.openWithCallback(self.runRemove, MessageBox, _("Do you want to remove the package:\n") + package + "\n" + self.oktext)
			elif status == "upgradeable":
				self.cmdList.append((IpkgComponent.CMD_INSTALL, {"package": package}))
				if len(self.cmdList):
					self.session.openWithCallback(self.runUpgrade, MessageBox, _("Do you want to update the package:\n") + package + "\n" + self.oktext)
			elif status == "installable":
				self.cmdList.append((IpkgComponent.CMD_INSTALL, {"package": package}))
				if len(self.cmdList):
					self.session.openWithCallback(self.runUpgrade, MessageBox, _("Do you want to install the package:\n") + package + "\n" + self.oktext)

	def runRemove(self, result):
		if result:
			self.session.openWithCallback(self.runRemoveFinished, Ipkg, cmdList=self.cmdList)

	def runRemoveFinished(self):
		self.session.openWithCallback(self.RemoveReboot, MessageBox, _("Removal has completed.") + "\n" + _("Do you want to reboot your receiver?"), MessageBox.TYPE_YESNO)

	def RemoveReboot(self, result):
		if result is None:
			return
		if not result:
			cur = self["list"].getCurrent()
			if cur:
				item = self["list"].getIndex()
				self.list[item] = self.buildEntryComponent(cur[0], cur[1], cur[2], "installable")
				self.cachelist[item] = [cur[0], cur[1], cur[2], "installable"]
				self["list"].setList(self.list)
				write_cache(self.cache_file, self.cachelist)
				self.reloadPluginlist()
		if result:
			self.session.open(TryQuitMainloop, retvalue=3)

	def runUpgrade(self, result):
		if result:
			self.session.openWithCallback(self.runUpgradeFinished, Ipkg, cmdList=self.cmdList)

	def runUpgradeFinished(self):
		self.session.openWithCallback(self.UpgradeReboot, MessageBox, _("Update has completed.") + "\n" + _("Do you want to reboot your receiver?"), MessageBox.TYPE_YESNO)

	def UpgradeReboot(self, result):
		if result is None:
			return
		if not result:
			cur = self["list"].getCurrent()
			if cur:
				item = self["list"].getIndex()
				self.list[item] = self.buildEntryComponent(cur[0], cur[1], cur[2], "installed")
				self.cachelist[item] = [cur[0], cur[1], cur[2], "installed"]
				self["list"].setList(self.list)
				write_cache(self.cache_file, self.cachelist)
				self.reloadPluginlist()
		if result:
			self.session.open(TryQuitMainloop, retvalue=3)

	def ipkgCallback(self, event, param):
		if event == IpkgComponent.EVENT_ERROR:
			self.list_updating = False
			self.setStatus("error")
		elif event == IpkgComponent.EVENT_DONE:
			if self.list_updating:
				self.list_updating = False
				if not self.Console:
					self.Console = Console()
				cmd = self.ipkg.ipkg + " list"
				self.Console.ePopen(cmd, self.OpkgList_Finished)
		pass

	def OpkgList_Finished(self, result, retval, extra_args=None):
		if result:
			self.packetlist = []
			last_name = ""
			for x in result.splitlines():
				if " - " in x:
					tokens = x.split(" - ")
					name = tokens[0].strip()
					if name and not any(name.endswith(x) for x in self.unwanted_extensions):
						l = len(tokens)
						version = l > 1 and tokens[1].strip() or ""
						descr = l > 2 and tokens[2].strip() or ""
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

		if not self.Console:
			self.Console = Console()
		cmd = self.ipkg.ipkg + " list_installed"
		self.Console.ePopen(cmd, self.OpkgListInstalled_Finished)

	def OpkgListInstalled_Finished(self, result, retval, extra_args=None):
		if result:
			self.installed_packetlist = {}
			for x in result.splitlines():
				tokens = x.split(" - ")
				name = tokens[0].strip()
				if not any(name.endswith(x) for x in self.unwanted_extensions):
					l = len(tokens)
					version = l > 1 and tokens[1].strip() or ""
					self.installed_packetlist[name] = version
		if not self.Console:
			self.Console = Console()
		cmd = "opkg list-upgradable"
		self.Console.ePopen(cmd, self.OpkgListUpgradeable_Finished)

	def OpkgListUpgradeable_Finished(self, result, retval, extra_args=None):
		if result:
			self.upgradeable_packages = {}
			for x in result.splitlines():
				tokens = x.split(" - ")
				name = tokens[0].strip()
				if not any(name.endswith(x) for x in self.unwanted_extensions):
					l = len(tokens)
					version = l > 2 and tokens[2].strip() or ""
					self.upgradeable_packages[name] = version
		self.buildPacketList()

	def buildEntryComponent(self, name, version, description, state):
		divpng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "div-h.png"))
		if not description:
			description = "No description available."
		if state == "installed":
			installedpng = LoadPixmap(cached=True, path=self.imagePath + "installed.png")
			return ((name, version, _(description), state, installedpng, divpng))
		elif state == "upgradeable":
			upgradeablepng = LoadPixmap(cached=True, path=self.imagePath + "upgradeable.png")
			return ((name, version, _(description), state, upgradeablepng, divpng))
		else:
			installablepng = LoadPixmap(cached=True, path=self.imagePath + "installable.png")
			return ((name, version, _(description), state, installablepng, divpng))

	def buildPacketList(self):
		self.list = []
		self.cachelist = []
		if self.cache_ttl > 0 and self.vc != 0:
			print("Loading packagelist cache from ", self.cache_file)
			try:
				self.cachelist = load_cache(self.cache_file)
				if len(self.cachelist) > 0:
					for x in self.cachelist:
						self.list.append(self.buildEntryComponent(x[0], x[1], x[2], x[3]))
					self["list"].setList(self.list)
			except:
				self.inv_cache = 1

		if self.cache_ttl == 0 or self.inv_cache == 1 or self.vc == 0:
			print("rebuilding fresh package list")
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
				self.cachelist.append([x[0], x[1], x[2], status])
			write_cache(self.cache_file, self.cachelist)
			self["list"].setList(self.list)

	def reloadPluginlist(self):
		plugins.readPluginList(resolveFilename(SCOPE_PLUGINS))
