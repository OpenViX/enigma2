from os import system, stat as mystat, path, remove
from glob import glob
import stat

from enigma import eTimer

from Components.config import config, configfile, ConfigSubsection, ConfigYesNo
from Components.ActionMap import ActionMap
from Components.Console import Console
from Components.Harddisk import harddiskmanager, getProcMounts
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.Sources.StaticText import StaticText
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen

config.swapmanager = ConfigSubsection()
config.swapmanager.swapautostart = ConfigYesNo(default=False)

# start: temp code - used due to config variable change
config.vixsettings.swapautostart = ConfigYesNo(default=False)
if config.vixsettings.swapautostart.value:
	config.swapmanager.swapautostart.value = True
	# switch off so doesn't happen on any subsuquent run
	config.vixsettings.swapautostart.value = False
	config.vixsettings.swapautostart.save()
# end: temp code
startswap = None


def SwapAutostart(reason, session=None, **kwargs):
	global startswap
	if reason == 0:
		print("[SwapManager] autostart", config.swapmanager.swapautostart.value)
		if config.swapmanager.swapautostart.value:
			print("[SwapManager] autostart")
			startswap = StartSwap()
			startswap.start()


class StartSwap:
	def __init__(self):
		self.Console = Console()

	def start(self):
		self.Console.ePopen("parted -l /dev/sd? | grep swap", self.startSwap2)

	def startSwap2(self, result=None, retval=None, extra_args=None):		# lets find swap partitions(normally receiver specific and part of image build or user swap files
		swap_Pname = ""
		swap_Fname = ""
		# print("[SwapManager][StartSwap] Found a SWAP partition:", result)
		if result and result.find("swap") > 0:		# so much garbage from parted command with eMMC partitions need further exclude.
			for line in result.split("\n"):
				# print("[SwapManager][StartSwap] grep lines in result", line)
				if "swap" not in line:
					continue
				swap_Pname = line.strip().rsplit(" ", 1)[-1]
				print("[SwapManager][StartSwap] Found a SWAP partition:", swap_Pname)
		devicelist = []
		for p in harddiskmanager.getMountedPartitions():
			d = path.normpath(p.mountpoint)
			if (path.exists(p.mountpoint) and p.mountpoint != "/" and not p.mountpoint.startswith(("/media/net/", "/media/autofs/"))):
				devicelist.append((p.description, d))
		if len(devicelist):
			for device in devicelist:
				for filename in glob(device[1] + "/swap*"):
					if path.exists(filename):
						swap_Fname = filename
						print("[SwapManager][StartSwap] Found a SWAP file on ", swap_Fname)
# basically a swap file if created, is now given higher priority than system swap partition if built in image.
# swapmanager can now set a user swap file to be active, or deleted and if present system swap partition will be used.
# if both are present, then swap file is used ahead of swap partition (based on priority) in /proc/swaps.
		f = open("/proc/swaps")
		swapfile = f.read()
		f.close()
		print("[SwapManager][StartSwap] partition/filename", swap_Fname, "   ", swap_Pname)
		if swap_Fname and swapfile.find(swap_Fname) == -1:
			system("swapon -p 10 " + swap_Fname)
			print("[SwapManager][StartSwap] SWAP file active on ", swap_Fname)
		if swap_Pname and not swap_Fname:
			print("[SwapManager][StartSwap] SWAP partition active on ", swap_Pname)
		if swap_Pname and swap_Fname:
			print("[SwapManager][StartSwap] SWAP file %s chosen before swap partition on %s by priority" % (swap_Fname, swap_Pname))


class VIXSwap(Screen):
	skin = ["""
	<screen name="VIXSwap" position="center,center" size="%d,%d">
		<ePixmap pixmap="skin_default/buttons/red.png" position="%d,%d" size="%d,%d" alphatest="blend" scale="1"/>
		<ePixmap pixmap="skin_default/buttons/green.png" position="%d,%d" size="%d,%d" alphatest="blend" scale="1"/>
		<ePixmap pixmap="skin_default/buttons/yellow.png" position="%d,%d" size="%d,%d" alphatest="blend" scale="1"/>
		<ePixmap pixmap="skin_default/buttons/blue.png" position="%d,%d" size="%d,%d" alphatest="blend" scale="1"/>
		<widget name="key_red" position="%d,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#9f1313" transparent="1"/>
		<widget name="key_green" position="%d,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#1f771f" transparent="1"/>
		<widget name="key_yellow" position="%d,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#a08500" transparent="1"/>
		<widget name="key_blue" position="%d,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#18188b" transparent="1"/>
		<widget name="autostart_off" position="%d,%d" zPosition="1" pixmap="skin_default/icons/lock_off.png" size="%d,%d" alphatest="blend" scale="1"/>
		<widget name="autostart_on" position="%d,%d" zPosition="2" pixmap="skin_default/icons/lock_on.png" size="%d,%d" alphatest="blend" scale="1"/>
		<widget name="lab1" position="%d,%d" size="%d,%d" font="Regular;%d" valign="center" transparent="1"/>
		<widget name="lab2" position="%d,%d" size="%d,%d" font="Regular;%d" valign="center" transparent="1"/>
		<widget name="lab3" position="%d,%d" size="%d,%d" font="Regular;%d" valign="center" transparent="1"/>
		<widget name="lab4" position="%d,%d" size="%d,%d" font="Regular;%d" valign="center" transparent="1" />
		<widget name="labplace" position="%d,%d" size="%d,%d" font="Regular;%d" valign="center" backgroundColor="#4D5375"/>
		<widget name="labsize" position="%d,%d" size="%d,%d" font="Regular;%d" valign="center" backgroundColor="#4D5375"/>
		<widget name="inactive" position="%d,%d" size="%d,%d" font="Regular;%d" valign="center" halign="center" backgroundColor="red"/>
		<widget name="active" position="%d,%d" size="%d,%d" font="Regular;%d" valign="center" halign="center" backgroundColor="green"/>
	</screen>""",
		560, 250,  # screen
		0, 0, 140, 40,  # colors
		140, 0, 140, 40,
		280, 0, 140, 40,
		420, 0, 140, 40,
		0, 0, 140, 40, 20,
		140, 0, 140, 40, 20,
		280, 0, 140, 40, 20,
		420, 0, 140, 40, 20,
		10, 50, 32, 32,  # lock off
		10, 50, 32, 32,  # lock on
		50, 50, 360, 30, 20,
		10, 100, 150, 30, 20,
		10, 150, 150, 30, 20,
		10, 200, 150, 30, 20,
		160, 100, 220, 30, 20,
		160, 150, 220, 30, 20,
		160, 200, 100, 30, 20,
		160, 200, 100, 30, 20,
				]  # noqa: E124

	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle(_("SWAP manager"))

		self["lab1"] = Label()
		self["autostart_on"] = Pixmap()
		self["autostart_off"] = Pixmap()
		self["lab2"] = Label(_("SWAP name:"))
		self["labplace"] = Label()
		self["lab3"] = Label(_("SWAP size:"))
		self["labsize"] = Label()
		self["lab4"] = Label(_("Status:"))
		self["inactive"] = Label(_("Inactive"))
		self["active"] = Label(_("Active"))
		self["key_red"] = Label(_("Close"))
		self["key_green"] = Label(_("Activate"))
		self["key_yellow"] = Label(_("Enable Autostart"))
		self["key_blue"] = Label(_("Create"))
		self["swapname_summary"] = StaticText()
		self["swapactive_summary"] = StaticText()
		self.Console = Console()
		self.swap_name = ""
		self.new_name = ""
		self.creatingswap = False
		self.swap_active = False
		self["actions"] = ActionMap(["WizardActions", "ColorActions", "MenuActions"],
		{
			"back": self.close,
			"red": self.close,
			"green": self.actDeact,
			"yellow": self.autoSsWap,
			"blue": self.createDel,
			"menu": self.close,
		})
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.getSwapDevice)
		self.updateSwap()

	def updateSwap(self, result=None, retval=None, extra_args=None):
		self["actions"].setEnabled(False)
		self.swap_active = False
		self.swap_name = None
		self["autostart_on"].hide()
		self["autostart_off"].show()
		self["active"].hide()
		self["inactive"].show()
		self["labplace"].hide()
		self["labsize"].hide()
		self["swapactive_summary"].setText(_("Current status:"))
		scanning = _("Wait please while scanning...")
		self["lab1"].setText(scanning)
		self.activityTimer.start(10)

	def getSwapDevice(self):
		self.activityTimer.stop()
		if path.exists("/etc/rcS.d/S98SwapManager"):
			remove("/etc/rcS.d/S98SwapManager")
			config.swapmanager.swapautostart.value = True
			config.swapmanager.swapautostart.save()
		if path.exists("/tmp/swapdevices.tmp"):
			remove("/tmp/swapdevices.tmp")
		self.Console.ePopen("parted -l /dev/sd? | grep swap", self.updateSwap2)

	def updateSwap2(self, result=None, retval=None, extra_args=None):
		self.swap_active = False
		self.swap_Pname = ""
		self.Pswapsize = 0
		self.swap_Pactive = False
		self.swap_Fname = ""
		self.Fswapsize = 0
		self.swap_Factive = False
		self.MMCdevice = False
		self.swapdevice = 0
		self.swapcount = 0
		self.swapsize = 0
		if result.find("swap") > 0:					# lets find swap partition
			for line in result.split("\n"):
				if "swap" not in line:				# so much garbage from parted command with eMMC partitions need further exclude.
					continue
				parts = line.strip().split()
				# print("[SwapManager][updateSwap2] parts = ", parts, "   ", parts[3])
				self.swap_Pname = line.strip().split(" ", 1)[-1]
				self.Pswapsize = parts[3]
				if self.swap_Pname == "sfdisk:":
					self.swap_Pname = ""
				f = open("/proc/swaps", "r")
				for line2 in f.readlines():
					parts = line2.strip().split()
					if line2.find("partition") != -1:
						if "mmc" in parts[0]:
							self.MMCdevice = True
							self.swap_Pname = parts[0]
							# self["key_blue"].setText("")
							self.swap_name = _("manufacturer defined swap")
						self.swap_Pactive = True
				f.close()
		self["key_blue"].setText(_("Create"))
		devicelist = []						# lets find swap file
		for p in harddiskmanager.getMountedPartitions():
			d = path.normpath(p.mountpoint)
			if path.exists(p.mountpoint) and p.mountpoint != "/" and not p.mountpoint.startswith("/media/net"):
				devicelist.append((p.description, d))
		if len(devicelist):
			print("[SwapManager][{updateSwap2] devicelist = ", devicelist)
			for device in devicelist:
				print("[SwapManager][{updateSwap2] device = ", device, device[1])
				for filename in glob(device[1] + "/swap*"):
					self.swap_name = self.swap_Fname = filename
					self["key_blue"].setText(_("Delete"))
					info = mystat(self.swap_name)
					self.Fswapsize = info[stat.ST_SIZE]

		if self.swap_Fname:						# if swap file
			self["labplace"].setText(self.swap_Fname)
			self["autostart_on"].hide()
			self["autostart_off"].show()
		elif self.swap_Pname:						# if only swap partition
			self["labplace"].setText(self.swap_name)
		else:
			self["labplace"].setText("")
		self["labplace"].show()

		f = open("/proc/swaps", "r")
		for line in f.readlines():
			parts = line.strip().split()
			if line.find("file") != -1:					# if swap file - takes precedence over swap parition
				self["autostart_on"].show()
				self["autostart_off"].hide()
				self.swap_active = self.swap_Factive = True
				continue
			elif line.find("partition") != -1 and not self.swap_Fname:  # only swap partition
				self.swap_active = self.swap_Pactive = True
				continue

		f.close()
		if self.swap_Fname:
			self.swapsize = int(self.Fswapsize)
			if self.swapsize > 0:
				if self.swapsize >= 1024:
					self.swapsize = self.swapsize // 1000
					if self.swapsize >= 1024:
						self.swapsize = self.swapsize // 1000
					self.swapsize = str(self.swapsize) + " " + "MB"
				else:
					self.swapsize = str(self.swapsize) + " " + "KB"
			else:
				self.swapsize = ""
		elif self.swap_Pname:
			self.swapsize = self.Pswapsize					# picked up from parted command
		self["labsize"].setText(self.swapsize)
		self["labsize"].show()

		if self.swap_active:
			self["inactive"].hide()
			self["active"].show()
			self["key_green"].setText(_("Deactivate"))
			self["swapactive_summary"].setText(_("Current status:") + " " + _("Active"))
		else:
			self["inactive"].show()
			self["active"].hide()
			self["key_green"].setText(_("Activate"))
			self["swapactive_summary"].setText(_("Current status:") + " " + _("Inactive"))
		if self.swap_name == _("manufacturer defined swap"):
			self["key_green"].setText("")
			scanning = _("manufacturer defined swap enabled at startup")
		else:
			scanning = _("Enable SWAP at startup")

		if config.swapmanager.swapautostart.value or self.swap_name == _("manufacturer defined swap"):
			self["autostart_off"].hide()
			self["autostart_on"].show()
			self["key_yellow"].setText(_("Disable Autostart"))
		else:
			config.swapmanager.swapautostart.setValue(False)
			config.swapmanager.swapautostart.save()
			configfile.save()
			self["autostart_on"].hide()
			self["autostart_off"].show()
			self["key_yellow"].setText(_("Enable Autostart"))
		self["lab1"].setText(scanning)
		self["lab1"].show()
		self["actions"].setEnabled(True)

		name = self["labplace"].text
		self["swapname_summary"].setText(name)

	def actDeact(self):
		if self.swap_Factive:
			self.Console.ePopen("swapoff " + self.swap_Fname, self.updateSwap)
			self.swap_Factive = False
		else:
			if self.swap_Fname:
				self.Console.ePopen("swapon -p 10 " + self.swap_Fname, self.updateSwap)
				self.swap_Factive = True
				config.swapmanager.swapautostart.setValue(True)
				config.swapmanager.swapautostart.save()
				configfile.save()
			else:
				mybox = self.session.open(MessageBox, _("SWAP file not found. You have to create the file before you try to activate it."), MessageBox.TYPE_INFO)
				mybox.setTitle(_("Info"))
		self.updateSwap()

	def createDel(self):
		if self.swap_Fname:
			if self.swap_Factive:
				self.Console.ePopen("swapoff " + self.swap_Fname, self.createDel2)
			else:
				self.createDel2(None, 0)
		else:
			self.doCreateSwap()

	def createDel2(self, result, retval, extra_args=None):
		if self.swap_name == _("manufacturer defined swap"):
			self.updateSwap()
		if retval == 0:
			# print("[SwapManager][createDel2] delete swap = ", self.swap_Fname)
			self.Console.ePopen("rm " + self.swap_Fname, self.createDel3)

	def createDel3(self, result, retval, extra_args=None):
		print("[SwapManager][createDel3] delete swap, retval, result", retval, "   ", result)
		if config.swapmanager.swapautostart.value:
			config.swapmanager.swapautostart.setValue(False)
			config.swapmanager.swapautostart.save()
			configfile.save()
		self.updateSwap()

	def doCreateSwap(self):
		supported_filesystems = frozenset(("ext4", "ext3"))
		candidates = []
		mounts = getProcMounts()
		for partition in harddiskmanager.getMountedPartitions(False, mounts):
			if partition.filesystem(mounts) in supported_filesystems:
				candidates.append((partition.description, partition.mountpoint))
		if len(candidates):
			self.session.openWithCallback(self.doCSname, ChoiceBox, title=_("Please select device to use as SWAP file location."), list=candidates)
		else:
			self.session.open(MessageBox, _("Sorry, no physical devices that supports SWAP attached. Can't create SWAP file on network or fat32 file-systems."), MessageBox.TYPE_INFO, timeout=10)

	def doCSname(self, name):
		if name:
			self.new_name = name[1]
			myoptions = [[_("8 Mb"), "8192"], [_("16 Mb"), "16384"], [_("32 Mb"), "32768"], [_("64 Mb"), "65536"], [_("96 Mb"), "98304"], [_("128 Mb"), "131072"], [_("256 Mb"), "262144"], [_("512 Mb"), "524288"], [_("756 Mb"), "774144"], [_("1024 Mb"), "1048576"]]
			self.session.openWithCallback(self.doCSsize, ChoiceBox, title=_("Select the SWAP file size:"), list=myoptions)

	def doCSsize(self, swapsize):
		if swapsize:
			self["actions"].setEnabled(False)
			scanning = _("Wait please while creating SWAP file...")
			self["lab1"].setText(scanning)
			self["lab1"].show()
			swapsize = swapsize[1]
			myfile = self.new_name + "swapfile"
			self.commands = []
			self.commands.append("dd if=/dev/zero of=" + myfile + " bs=1024 count=" + swapsize + " 2>/dev/null")
			self.commands.append("mkswap " + myfile)
			self.Console.eBatch(self.commands, self.updateSwap, debug=True)

	def autoSsWap(self):
		if self.swap_name:
			if config.swapmanager.swapautostart.value:
				config.swapmanager.swapautostart.setValue(False)
				config.swapmanager.swapautostart.save()
			else:
				config.swapmanager.swapautostart.setValue(True)
				config.swapmanager.swapautostart.save()
			configfile.save()
		else:
			mybox = self.session.open(MessageBox, _("You have to create a SWAP file before trying to activate the autostart."), MessageBox.TYPE_INFO)
			mybox.setTitle(_("Info"))
		self.updateSwap()
