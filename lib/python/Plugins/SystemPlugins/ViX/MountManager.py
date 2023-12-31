import errno
from os import mkdir, path, rename, statvfs, system
import re

from enigma import eTimer

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.ConfigList import ConfigListScreen
from Components.config import getConfigListEntry, ConfigSelection, NoSave
from Components.Console import Console
from Components.Sources.List import List
from Components.SystemInfo import SystemInfo
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Standby import QUIT_REBOOT, TryQuitMainloop
from Tools.LoadPixmap import LoadPixmap
from Tools.Directories import SCOPE_CURRENT_SKIN, resolveFilename

blacklistedDisks = [
	1,  	# RAM disk (/dev/ram0=0, /dev/initrd=250 [250=Initial RAM disk for old systems, new systems use 0])
	7,  	# Loopback devices (/dev/loop0=0)
	31,  	# ROM/flash memory card (/dev/rom0=0, /dev/rrom0=8, /dev/flash0=16, /dev/rflash0=24 [r=Read Only])
	240,  	# ROM/flash memory card (/dev/rom0=0, /dev/rrom0=8, /dev/flash0=16, /dev/rflash0=24 [r=Read Only])
	253,  	# LOCAL/EXPERIMENTAL USE
	254,  	# LOCAL/EXPERIMENTAL USE
	259  	# MMC block devices (/dev/mmcblk0=0, /dev/mmcblk0p1=1, /dev/mmcblk1=8)
]


def readFile(filename):
	try:
		with open(filename, "r") as fd:
			data = fd.read().strip()
	except (IOError, OSError) as err:
		if err.errno != errno.ENOENT:  # No such file or directory.
			print("[MountManager] Error: Failed to read file! ", err)
		data = None
	return data


def getProcPartitions(partitionList):
	partitions = []
	with open("/proc/partitions", "r") as fd:
		for line in fd.readlines():
			line = line.strip()
			if line == "":  # Skip empty lines.
				continue
			(devmajor, devminor, blocks, device) = line.split()
			if devmajor == "major":  # Skip label line.
				continue
			# print("[MountManager] device='%s', devmajor='%s', devminor='%s'." % (device, devmajor, devminor))
			devMajor = int(devmajor)
			if devMajor in blacklistedDisks:  # Ignore all blacklisted devices.
				continue
			if devMajor == 179:
				if not SystemInfo["HasSDnomount"]:  # Only interested in h9/i55/h9combo(+dups) mmc partitions.  h9combo(+dups) uses mmcblk1p[0-3].
					continue
				if SystemInfo["HasH9SD"]:
					if not re.search("mmcblk0p1", device):  # h9/i55 only mmcblk0p1 mmc partition
						continue
					if SystemInfo["HasMMC"]:  # With h9/i55 reject mmcblk0p1 mmc partition if root device.
						continue
				if SystemInfo["HasSDnomount"][0] and not re.search("mmcblk1p[0-3]", device):  # h9combo(+dups) uses mmcblk1p[0-3] include
					continue
			if devMajor == 8:
				if not re.search("sd[a-z][1-9]", device):  # If storage use partitions only.
					continue
				if SystemInfo["HasHiSi"] and path.exists("/dev/sda4") and re.search("sd[a][1-4]", device):  # Sf8008 using SDcard for slots ---> exclude
					continue
			if device in partitions:  # If device is already in partition list ignore it.
				continue
			buildPartitionInfo(device, partitionList)
			partitions.append(device)


def buildPartitionInfo(partition, partitionList):
	if re.search("mmcblk[0-1]p[0-3]", partition):
		device = re.sub("p[0-9]", "", partition)
	else:
		device = re.sub("[0-9]", "", partition)
	physicalDevice = path.realpath(path.join("/sys/block", device, "device"))

	# print("[MountManager] MachineBuild: %s" % getMachineBuild())
	# print("[MountManager] partition: %s" % partition)
	# print("[MountManager] device: %s" % device)
	# print("[MountManager] physicalDevice: %s" % physicalDevice)
	# print("[MountManager] Type: %s" % SystemInfo["MountManager"])

	description = readFile(path.join(physicalDevice, "model"))
	if description is None:
		description = readFile(path.join(physicalDevice, "name"))
	if description is None:
		description = _("Device %s") % partition
	description = str(description).replace("\n", "")

	hotplugBuses = ("usb", "mmc", "ata")
	busTranslate = ("usb", "sd", "hdd")
	count = -1
	for bus in hotplugBuses:
		count += 1
		if "/%s" % bus in physicalDevice:
			break
	# print("[MountManager1]bus: %s count : %s" % (bus, count))
	pngType = busTranslate[count]
	name = _("%s: " % pngType.upper())
	name += description

	if path.exists(resolveFilename(SCOPE_CURRENT_SKIN, "vixcore/dev_%s.png" % pngType)):
		mypixmap = resolveFilename(SCOPE_CURRENT_SKIN, "vixcore/dev_%s.png" % pngType)
	else:
		mypixmap = "/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/images/dev_%s.png" % pngType

	description = ""
	mediamount = _("None")
	_format = _("unavailable")
	rw = _("None")

	with open("/proc/mounts", "r") as f:
		for line in f.readlines():
			if line.find(partition) != -1:
				parts = line.strip().split()
				mediamount = parts[1]		# media mount e.g. /media/xxxxx
				_format = parts[2]		# _format e.g. ext4
# Also, map any fuseblk fstype to the real file-system behind it...
# Use blkid to get the info we need....
#
				if _format == 'fuseblk':
					import subprocess
					res = subprocess.run(['blkid', '-sTYPE', '-ovalue', parts[0]], capture_output=True)
					if res.returncode == 0:
						_format = res.stdout.decode().strip()
				rw = parts[3]			# read/write
				break
	print("[MountManager1][buildPartitionInfo] mediamount", mediamount)
	if mediamount == "/" and SystemInfo["HasKexecMultiboot"]:
		return
	if mediamount == _("None") or mediamount is None:
		description = _("Size: ") + _("unavailable")
	else:
		stat = statvfs(mediamount)
		# print("[MountManager1]mediamount: %s" % mediamount)
		size = (stat.f_blocks * stat.f_bsize) / (1000 * 1000)  # get size in MB
		if size < 1:  # is condition ever fulfilled?
			description = _("Size: unavailable")
		if size < 1000:
			description = _("Size: %sMB") % str(int(size))
		elif size < 1000 * 1000:
			description = _("Size: %sGB") % format(size / 1000, '.2f')
		else:
			description = _("Size: %sTB") % format(size / (1000 * 1000), '.2f')

	if SystemInfo["MountManager"]:  # called by VIXDevicesPanel else DeviceMountSetup
		if rw.startswith("rw"):
			rw = " R/W"
		elif rw.startswith("ro"):
			rw = " R/O"
		else:
			rw = ""
		description += "\t" + _("Mount: ") + mediamount + "\n" + _("Device: ") + "/dev/" + partition + "\t" + _("Type: ") + _format + rw
		png = LoadPixmap(mypixmap)
		partitionInfo = (name, description, png)
	else:
		Gmedia = [
			("/media/" + device, "/media/" + device),
			("/media/hdd", "/media/hdd"),
			("/media/hdd2", "/media/hdd2"),
			("/media/hdd3", "/media/hdd3"),
			("/media/usb", "/media/usb"),
			("/media/usb2", "/media/usb2"),
			("/media/usb3", "/media/usb3"),
			("/media/sdcard", "/media/sdcard")
		]
		item = NoSave(ConfigSelection(default="/media/%s" % partition, choices=Gmedia))
		if _format == "Linux":
			_format = "ext4"
		else:
			_format = "auto"
		item.value = mediamount.strip()
		text = name + " " + description + " /dev/" + partition
		partitionInfo = getConfigListEntry(text, item, partition, _format)
	partitionList.append(partitionInfo)


class VIXDevicesPanel(Screen):
	skin = ["""
	<screen position="center,center" size="%d,%d">
		<widget source="list" render="Listbox" position="%d,%d" size="%d,%d" scrollbarMode="showOnDemand">
			<convert type="TemplatedMultiContent">
				{
				"template":
					[
					MultiContentEntryText(pos = (%d, %d), size = (%d, %d), font = 0, flags = RT_HALIGN_LEFT | RT_VALIGN_CENTER, text = 0),
					MultiContentEntryText(pos = (%d, %d), size = (%d, %d), font = 1, flags = RT_HALIGN_LEFT | RT_VALIGN_TOP, text = 1),
					MultiContentEntryPixmapAlphaBlend(pos = (%d, %d), size = (%d, %d), flags = BT_SCALE, png = 2),
					],
				"fonts": [gFont("Regular",%d), gFont("Regular",%d)],
				"itemHeight": %d
				}
			</convert>
		</widget>
		<widget name="lab1" position="%d,%d" size="%d,%d" font="Regular;%d" halign="center" transparent="1" valign="center" zPosition="+1" />
		<ePixmap pixmap="skin_default/buttons/red.png" position="%d,%d" size="%d,%d" alphatest="blend" scale="1"/>
		<ePixmap pixmap="skin_default/buttons/green.png" position="%d,%d" size="%d,%d" alphatest="blend" scale="1"/>
		<ePixmap pixmap="skin_default/buttons/yellow.png" position="%d,%d" size="%d,%d" alphatest="blend" scale="1"/>
		<ePixmap pixmap="skin_default/buttons/blue.png" position="%d,%d" size="%d,%d" alphatest="blend" scale="1"/>
		<widget name="key_red" position="%d,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#9f1313" transparent="1"/>
		<widget name="key_green" position="%d,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#1f771f" transparent="1"/>
		<widget name="key_yellow" position="%d,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#a08500" transparent="1"/>
		<widget name="key_blue" position="%d,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#18188b" transparent="1"/>
	</screen>""",
		560, 495,  # screen
		10, 50, 540, 400,  # Listbox
		100, 0, 520, 30,
		120, 30, 500, 50,
		10, 0, 80, 80,
		24, 20,  # fonts
		80,
		10, 10, 540, 425, 25,
		0, 0, 140, 40,  # colors
		140, 0, 140, 40,
		280, 0, 140, 40,
		420, 0, 140, 40,
		0, 0, 140, 40, 20,
		140, 0, 140, 40, 20,
		280, 0, 140, 40, 20,
		420, 0, 140, 40, 20,
			]  # noqa: E124

	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle(_("Mount manager"))
		self["key_red"] = Label("")
		self["key_green"] = Label(_("Setup mounts"))
		self["key_yellow"] = Label(_("Un-mount"))
		self["key_blue"] = Label(_("Mount"))
		self["lab1"] = Label(_("Please wait while scanning for devices..."))
		self.onChangedEntry = []
		self.partitionlist = []
		self["list"] = List(self.partitionlist)
		self["list"].onSelectionChanged.append(self.selectionChanged)
		self["actions"] = ActionMap(["WizardActions", "ColorActions", "MenuActions"], {
			"back": self.close,
			"green": self.setupMounts,
			"red": self.saveMounts,
			"yellow": self.unmount,
			"blue": self.mount,
			"menu": self.close
		})
		self.Console = Console()
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.findPartitions)
		self.setTimer()

	def selectionChanged(self):
		# print("[MountManager][selectionChanged] self.partitionList=%s" % self.partitionList)
		if len(self.partitionList) == 0:
			return
		sel = self["list"].getCurrent()  # partitionInfo = (name, description, png)
		# print("[MountManager][selectionChanged] sel1=%s sel2=%s" % (sel[0], sel[1]))
		line = sel[1]
		# print("[MountManager1][selectionChanged] line=%s" % line)
		if line.find("Mount") >= 0:
			if line.find("/media/hdd") < 0:
				self["key_red"].setText(_("Use as HDD"))
		else:
			self["key_red"].setText("")
		name = description = ""
		if sel:
			try:
				name = str(sel[0])
				description = str(sel[1].replace("\t", "  "))
			except Exception:
				pass
		for cb in self.onChangedEntry:
			cb(name, description)

	def setTimer(self, result=None, retval=None, extra_args=None):
		self["lab1"].show()
		self.activityTimer.start(10)

	def findPartitions(self):
		self.activityTimer.stop()
		self.partitionList = []
		SystemInfo["MountManager"] = True
		getProcPartitions(self.partitionList)
		self["list"].list = self.partitionList
		self["lab1"].hide()

	def setupMounts(self):
		self.session.openWithCallback(self.setTimer, DeviceMountSetup)  # print("[MountManager][setupMounts")

	def unmount(self):
		sel = self["list"].getCurrent()
		# print("[MountManager][unmount] sel1=%s sel2=%s" % (sel[0], sel[1]))
		if sel:
			des = sel[1]
			des = des.replace("\n", "\t")
			parts = des.strip().split("\t")
			mountp = parts[1].replace(_("Mount: "), "")
			device = parts[2].replace(_("Device: "), "")
			# print("[MountManager][unmount] mountp=%s device=%s" % (mountp, device))
			exitStatus = system("umount %s" % mountp)
			if exitStatus == 0:
				self.session.open(MessageBox, _("Partition: %s  Mount: %s unmounted successfully; if all partitions now unmounted you can remove device.") % (device, mountp), MessageBox.TYPE_INFO)
				self.setTimer()
			else:
				self.session.open(MessageBox, _("Cannot unmount partition '%s'.  Make sure this partition is not in use.  (SWAP, record/timeshift, etc.)") % mountp, MessageBox.TYPE_INFO)
				return -1

	def mount(self):
		sel = self["list"].getCurrent()
		# print("[MountManager][mount] sel1=%s sel2=%s" % (sel[0], sel[1]))
		if sel:
			des = sel[1]
			des = des.replace("\n", "\t")
			parts = des.strip().split("\t")
			# mountp = parts[1].replace(_("Mount: "), "")
			device = parts[2].replace(_("Device: "), "")
			# print("[MountManager][mount] mountp=%s device=%s" % (mountp, device))
			exitStatus = system("mount %s" % device)
			if exitStatus != 0:
				self.session.open(MessageBox, _("Mount failed for '%s', error code = '%s'.") % (sel, exitStatus), MessageBox.TYPE_INFO, timeout=10)
			self.setTimer()

	def saveMounts(self):
		sel = self["list"].getCurrent()
		# print("[MountManager][saveMounts] selection=%s" % sel)
		if sel:
			parts = sel[1].split()
			self.device = parts[5]
			self.mountp = parts[3]
			# print("[MountManager1]saveMounts: device = %s, mountp = %s" %(self.device, self.mountp))
			self.Console.ePopen("umount " + self.device)
			if self.mountp.find("/media/hdd") < 0:
				self.Console.ePopen("umount /media/hdd")
				self.Console.ePopen("/sbin/blkid | grep " + self.device, self.addFstab, [self.device, self.mountp])
			else:
				self.session.open(MessageBox, _("This device is already mounted as HDD."), MessageBox.TYPE_INFO, timeout=10, close_on_any_key=True)

	def addFstab(self, result=None, retval=None, extra_args=None):
		# print("[MountManager] RESULT:", result)
		if result:
			self.device = extra_args[0]
			self.mountp = extra_args[1]
			self.device_uuid = "UUID=" + result.split("UUID=")[1].split(" ")[0].replace('"', '')
			# print("[MountManager1][addFstab1]: device = %s, mountp=%s, UUID=%s" %(self.device, self.mountp, self.device_uuid))
			if not path.exists(self.mountp):
				mkdir(self.mountp, 0o755)
			open("/etc/fstab.tmp", "w").writelines([x for x in open("/etc/fstab").readlines() if "/media/hdd" not in x])
			rename("/etc/fstab.tmp", "/etc/fstab")
			open("/etc/fstab.tmp", "w").writelines([x for x in open("/etc/fstab").readlines() if self.device not in x])
			rename("/etc/fstab.tmp", "/etc/fstab")
			open("/etc/fstab.tmp", "w").writelines([x for x in open("/etc/fstab").readlines() if self.device_uuid not in x])
			rename("/etc/fstab.tmp", "/etc/fstab")
			with open("/etc/fstab", "a") as fd:
				line = self.device_uuid + "\t/media/hdd\tauto\tdefaults\t0 0\n"
				fd.write(line)
			self.Console.ePopen("mount -a", self.setTimer)


class DeviceMountSetup(Screen, ConfigListScreen):
	skin = ["""
	<screen position="center,center" size="%d,%d">
		<ePixmap pixmap="skin_default/buttons/red.png" position="%d,%d" size="%d,%d" alphatest="blend" scale="1"/>
		<ePixmap pixmap="skin_default/buttons/green.png" position="%d,%d" size="%d,%d" alphatest="blend" scale="1"/>
		<widget name="key_red" position="%d,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#9f1313" transparent="1"/>
		<widget name="key_green" position="%d,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#1f771f" transparent="1"/>
		<widget name="config" position="%d,%d" size="%d,%d" itemHeight="%d" font="Regular;%d" scrollbarMode="showOnDemand"/>
		<widget name="lab1" position="%d,%d" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#9f1313"/>
	</screen>""",
		560, 450,  # screen
		0, 0, 140, 40,  # colors
		140, 0, 140, 40,
		0, 0, 140, 40, 20,
		140, 0, 140, 40, 20,
		0, 50, 560, 275, 26, 20,  # config
		0, 365, 560, 20, 18,
			]  # noqa: E124

	def __init__(self, session):
		Screen.__init__(self, session)
		self.partitionList = []
		ConfigListScreen.__init__(self, self.partitionList)
		self.setTitle(_("Choose where to mount your devices to:"))
		self["key_green"] = Label(_("Save"))
		self["key_red"] = Label(_("Cancel"))
		self["lab1"] = Label()
		self["actions"] = ActionMap(["WizardActions", "ColorActions"], {
			"red": self.close,
			"green": self.saveconfMounts,
			"back": self.close
		})
		self.Console = Console()
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.findconfPartitions)
		self.setconfTimer()

	def setconfTimer(self, result=None, retval=None, extra_args=None):
		scanning = _("Please wait while scanning your %s %s devices...") % (SystemInfo["MachineBrand"], SystemInfo["MachineName"])
		self["lab1"].setText(scanning)
		self.activityTimer.start(10)

	def findconfPartitions(self):
		self.activityTimer.stop()
		self.partitionList = []
		SystemInfo["MountManager"] = False
		getProcPartitions(self.partitionList)
		self["config"].list = self.partitionList
		self["config"].l.setList(self.partitionList)
		self["lab1"].hide()

	def saveconfMounts(self):
		for x in self["config"].list:  # partitionInfo = getConfigListEntry(text, item, partition, _format)
			self.device = x[2]
			self.mountp = x[1].value
			self.type = x[3]
			# print("[MountManager][saveconfMount] mountp=%s device=%s type=%s" % (self.mountp, self.device, self.type))
			self.Console.ePopen("umount %s" % self.device)
			self.Console.ePopen("/sbin/blkid | grep " + self.device + " && opkg list-installed ntfs-3g", self.addconfFstab, [self.device, self.mountp])
		message = _("Updating mount locations...")
		ybox = self.session.openWithCallback(self.delay, MessageBox, message, type=MessageBox.TYPE_INFO, timeout=5, enable_input=False)
		ybox.setTitle(_("Please wait."))

	def delay(self, val):
		message = _("The changes need a system restart to take effect.\nRestart your %s %s now?") % (SystemInfo["MachineBrand"], SystemInfo["MachineName"])
		ybox = self.session.openWithCallback(self.restartBox, MessageBox, message, MessageBox.TYPE_YESNO)
		ybox.setTitle(_("Restart %s %s.") % (SystemInfo["MachineBrand"], SystemInfo["MachineName"]))

	def addconfFstab(self, result=None, retval=None, extra_args=None):
		# print("[MountManager] RESULT:", result)
		if result:
			self.device = extra_args[0]
			self.mountp = extra_args[1]
			uuid = re.search('UUID=\"([^\"]+)\"', result)
			type = re.search('TYPE=\"([^\"]+)\"', result)
			if uuid and type:
				self.device_uuid = "UUID=" + uuid.group(1)
				self.device_type = type.group(1)
				# print("[MountManager][addFstab2] device_uuid:%s device_type:%s" % (self.device_uuid, self.device_type))
				if self.device_type.startswith("ext"):
					self.device_type = "auto"
				elif self.device_type.startswith("ntfs") and result.find("ntfs-3g") != -1:
					self.device_type = "ntfs-3g"
				elif self.device_type.startswith("ntfs") and result.find("ntfs-3g") == -1:
					self.device_type = "ntfs"
				if not path.exists(self.mountp):
					mkdir(self.mountp, 0o755)
				open("/etc/fstab.tmp", "w").writelines([x for x in open("/etc/fstab").readlines() if self.device not in x])
				rename("/etc/fstab.tmp", "/etc/fstab")
				open("/etc/fstab.tmp", "w").writelines([x for x in open("/etc/fstab").readlines() if self.device_uuid not in x])
				rename("/etc/fstab.tmp", "/etc/fstab")
				with open("/etc/fstab", "a") as fd:
					line = self.device_uuid + "\t" + self.mountp + "\t" + self.device_type + "\tdefaults\t0 0\n"
					fd.write(line)

	def restartBox(self, answer):
		if answer is True:
			self.session.open(TryQuitMainloop, QUIT_REBOOT)
		else:
			self.close()
