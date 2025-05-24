from os import listdir, path as ospath, popen, statvfs
from re import search
from requests import get
from sys import version_info
from enigma import eTimer, getDesktop, getEnigmaLastCommitDate, getEnigmaLastCommitHash
from skin import parameters
from Components.About import getBoxUptime, getCPUArch, getEnigmaUptime, getIfConfig, getIfTransferredData
from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.config import config
from Components.Harddisk import harddiskmanager, bytesToHumanReadable
from Components.Network import iNetwork
from Components.NimManager import nimmanager
from Components.Pixmap import MultiPixmap
from Components.Sources.StaticText import StaticText
from Components.SystemInfo import SystemInfo, CHIPSET, KERNEL, MODEL, SOC_BRAND
from Screens.GitCommitInfo import CommitInfo
from Screens.Screen import Screen, ScreenSummary
from Screens.SoftwareUpdate import UpdatePlugin
from Screens.TextBox import TextBox
from Tools.Directories import fileHas, fileReadLines, isPluginInstalled
from Tools.Hex2strColor import Hex2strColor
from Tools.Multiboot import GetCurrentImageMode
from Tools.StbHardware import getFPVersion


def getFlashDateString():
	if ospath.isfile('/etc/install'):
		with open("/etc/install", "r") as f:
			return _formatDate(f.read())
	else:
		return _("unknown")


def driversDate():
	return _formatDate(SystemInfo["driversdate"])


def getLastCommitDate():
	return _formatDate(getEnigmaLastCommitDate().replace("-", ""))


def getLastCommitHash():
	return getEnigmaLastCommitHash()[:7]


def _formatDate(Date):
	# expected input = "YYYYMMDD"
	if len(Date) != 8 or not Date.isnumeric():
		return _("unknown")
	return config.usage.date.dateFormatAbout.value % {"year": Date[0:4], "month": Date[4:6], "day": Date[6:8]}


def getFFmpegVersionString():
	lines = fileReadLines("/var/lib/opkg/info/ffmpeg.control")
	if lines:
		for line in lines:
			if line[0:8] == "Version:":
				return line[9:].split("+")[0]
	return _("Not Installed")


def getGStreamerVersionString():
	try:
		from glob import glob
		gst = [x.split("Version: ") for x in open(glob("/var/lib/opkg/info/gstreamer[0-9].[0-9].control")[0], "r") if x.startswith("Version:")][0]
		return gst[1].split("+")[0].split("-")[0].replace("\n", "")
	except:
		return _("unknown")


def getsystemTemperature():
	tempinfo = ""
	if ospath.exists("/proc/stb/sensors/temp0/value"):
		with open("/proc/stb/sensors/temp0/value", "r") as f:
			tempinfo = f.read()
	elif ospath.exists("/proc/stb/fp/temp_sensor"):
		with open("/proc/stb/fp/temp_sensor", "r") as f:
			tempinfo = f.read()
	elif ospath.exists("/proc/stb/sensors/temp/value"):
		with open("/proc/stb/sensors/temp/value", "r") as f:
			tempinfo = f.read()
	return tempinfo


def getprocessorTemperature():
	tempinfo = ""
	if ospath.exists("/proc/stb/fp/temp_sensor_avs"):
		with open("/proc/stb/fp/temp_sensor_avs", "r") as f:
			tempinfo = f.read()
	elif ospath.exists("/sys/devices/virtual/thermal/thermal_zone0/temp"):
		try:
			with open("/sys/devices/virtual/thermal/thermal_zone0/temp", "r") as f:
				tempinfo = f.read()
				tempinfo = tempinfo[:-4]
		except:
			tempinfo = ""
	elif ospath.exists("/proc/hisi/msp/pm_cpu"):
		try:
			tempinfo = search(r"temperature = (\d+) degree", open("/proc/hisi/msp/pm_cpu").read()).group(1)  # noqa: W605
		except:
			tempinfo = ""
	return tempinfo


def df_h(find=None, binary=False):

	# Ubuntu base10/base2 units policy (since 2010): https://wiki.ubuntu.com/UnitsPolicy

	# Format of /proc/mounts
	# The 1st column specifies the device that is mounted.
	# The 2nd column reveals the mount point.
	# The 3rd column tells the file-system type.
	# The 4th column tells you if it is mounted read-only (ro) or read-write (rw).
	# The 5th and 6th columns are dummy values designed to match the format used in /etc/mtab.

	# Format of os.statvfs
	# f_bsize;    /* Filesystem block size */
	# f_frsize;   /* Fragment size */
	# f_blocks;   /* Size of fs in f_frsize units */
	# f_bfree;    /* Number of free blocks */
	# f_bavail;   /* Number of free blocks for unprivileged users */
	# f_files;    /* Number of inodes */
	# f_ffree;    /* Number of free inodes */
	# f_favail;   /* Number of free inodes for unprivileged users */
	# f_fsid;     /* Filesystem ID */
	# f_flag;     /* Mount flags */
	# f_namemax;  /* Maximum filename length */

	out = []
	for mount in open("/proc/mounts").readlines():
		fs_spec, fs_file, fs_vfstype, fs_mntops, fs_freq, fs_passno = mount.split()
		if True:  # fs_spec.startswith('/'):  # possible filtering here if necessary
			r = statvfs(fs_file)
			if find is None or find == fs_file:
				total = r.f_bsize * r.f_blocks
				free = r.f_bsize * r.f_bfree
				used = total - free
				usedpercent = "%d%%" % (100 * used // total if total else 100)  # sanity against ZeroDivisionError if total is 0
				out.append((fs_spec, bytesToHumanReadable(int(total), binary=binary), bytesToHumanReadable(int(used), binary=binary), bytesToHumanReadable(int(free), binary=binary), usedpercent, fs_file))
	return out


class AboutBase(TextBox):
	def __init__(self, session, labels=None):
		TextBox.__init__(self, session, label="AboutScrollLabel")
		self.colors = parameters.get("AboutColors", [])  # First item must be default text colour. If parameter is missing adding colours will be skipped.
		if labels:
			self["lab1"] = StaticText(_("Virtuosso Image Xtreme"))
			self["lab2"] = StaticText(_("By Team ViX"))
			self["lab3"] = StaticText(_("Support at") + " www.world-of-satellite.com")

	def addColor(self, text, i=1):
		if i < len(self.colors):
			text = Hex2strColor(self.colors[i]) + text + Hex2strColor(self.colors[0])
		return text

	def createSummary(self):
		return AboutSummary


class About(AboutBase):
	def __init__(self, session):
		AboutBase.__init__(self, session, labels=True)
		self.setTitle(_("About"))
		self.skinName = "AboutOE"
		self.populate()

		self["key_green"] = Button(_("Translations"))
		self["key_yellow"] = Button(_("Software update"))
		self["key_blue"] = Button(_("Release notes"))
		self["key_menu"] = StaticText(_("MENU"))
		self["actions"] = ActionMap(["ColorActions", "MenuActions"],
		{
			"green": self.showTranslationInfo,
			"yellow": self.showUpdatePlugin,
			"blue": self.showAboutReleaseNotes,
			"menu": self.setup,
		})

	def populate(self):
		Brands = {"meson": "MESON", "bcm": "Broadcom", "hisi": "Hisilicon"}
		AboutText = ""
		AboutText += _("Model:\t%s %s\n") % (SystemInfo["MachineBrand"], SystemInfo["MachineName"])
		AboutText += _("Chipset:\t%s %s\n") % (Brands.get(SOC_BRAND, SOC_BRAND), CHIPSET.replace("hi", "HI").replace("cv", "CV").replace("mv", "MV"))
		CPUArch = getCPUArch(MODEL)
		AboutText += _("CPU:\t%s %s %s\n") % (CPUArch[0], CPUArch[1], CPUArch[2])
		# AboutText += _("SoC:\t%s\n") % SystemInfo["socfamily"].upper()
		if ospath.exists('/sys/firmware/devicetree/base/bolt/tag'):
			with open("/sys/firmware/devicetree/base/bolt/tag") as f:
				bootLoader = f.read().replace('\x00', '').replace('\n', '')
				if SystemInfo["boxtype"] in ("gbquad4k", "gbue4k", "gbquad4kpro"):
					AboutText += _("Bolt:\t%s\n") % bootLoader
				else:
					AboutText += _("Bootloader:\t%s\n") % bootLoader
		AboutText += _("Remote:\t%s\n") % SystemInfo["RCName"]

		SystemTemperature = getsystemTemperature()
		if SystemTemperature and int(SystemTemperature.replace("\n", "")) > 0:
			AboutText += _("System temperature:\t%s") % SystemTemperature.replace("\n", "").replace(" ", "") + "\xb0" + "C\n"

		ProcessorTemperature = getprocessorTemperature()
		if ProcessorTemperature and int(ProcessorTemperature) > 0:
			AboutText += _("Processor temperature:\t%s") % ProcessorTemperature.replace("\n", "").replace(" ", "") + "\xb0" + "C\n"

		imageSubBuild = ""
		if SystemInfo["imagetype"] != "release":
			imageSubBuild = ".%s" % SystemInfo["imagedevbuild"]
		AboutText += _("Image:\t%s.%s%s (%s)\n") % (SystemInfo["imageversion"], SystemInfo["imagebuild"], imageSubBuild, SystemInfo["imagetype"].title())

		AboutText += _("Installed:\t%s\n") % getFlashDateString()

		VuPlustxt = _("Vu+ Multiboot") + " - " if SystemInfo["HasKexecMultiboot"] else ""
		if fileHas("/proc/cmdline", "rootsubdir=linuxrootfs0"):
			AboutText += _("Boot Device: \tRecovery Slot\n")
		elif "BootDevice" in SystemInfo and SystemInfo["BootDevice"]:
			AboutText += _("Boot Device:\t%s%s\n") % (VuPlustxt, SystemInfo["BootDevice"])

		if SystemInfo["HasH9SD"]:
			if "rootfstype=ext4" in open("/sys/firmware/devicetree/base/chosen/bootargs", "r").read():
				part = "        - SD card in use for Image root \n"
			else:
				part = "        - eMMC slot in use for Image root \n"
			AboutText += _("%s") % part

		if SystemInfo["canMultiBoot"]:
			slot = image = SystemInfo["MultiBootSlot"]
			if SystemInfo["HasHiSi"] and "sda" in SystemInfo["canMultiBoot"][slot]["root"]:
				if slot > 4:
					image -= 4
				else:
					image -= 1
			slotType = {"eMMC": _("eMMC"), "SDCARD": _("SDCARD"), "USB": _("USB")}.get(SystemInfo["canMultiBoot"][slot]["slotType"].replace(" ", ""), SystemInfo["canMultiBoot"][slot]["slotType"].replace(" ", ""))
			part = _("slot %s  (%s)") % (slot, slotType)
			bootmode = _("bootmode = %s") % GetCurrentImageMode() if SystemInfo["canMode12"] else ""
			AboutText += (_("Image Slot:\t %s %s") % (part, bootmode)) + "\n"

		if SystemInfo["MachineName"] in ("ET8500") and ospath.exists("/proc/mtd"):
			self.dualboot = self.dualBoot()
			if self.dualboot:
				AboutText += _("ET8500 Multiboot: Installed\n")

		skinWidth = getDesktop(0).size().width()
		skinHeight = getDesktop(0).size().height()

		AboutText += _("Drivers:\t%s\n") % driversDate()
		AboutText += _("Kernel:\t%s\n") % KERNEL
		AboutText += _("GStreamer:\t%s\n") % getGStreamerVersionString().replace("GStreamer ", "")
		AboutText += _("FFmpeg version:\t%s\n") % getFFmpegVersionString()
		if isPluginInstalled("ServiceApp") and config.plugins.serviceapp.servicemp3.replace.value:
			AboutText += _("4097 iptv player:\t%s\n") % config.plugins.serviceapp.servicemp3.player.value
		else:
			AboutText += _("4097 iptv player:\tDefault player\n")
		AboutText += _("Python:\t%s.%s.%s\n") % (version_info.major, version_info.minor, version_info.micro)
		AboutText += _("Last E2 update:\t%s (%s)\n") % (getLastCommitHash(), getLastCommitDate())
		AboutText += _("E2 (re)starts:\t%s\n") % config.misc.startCounter.value
		uptime = getBoxUptime()
		if uptime:
			AboutText += _("Uptime:\t%s\n") % uptime
		e2uptime = getEnigmaUptime()
		if e2uptime:
			AboutText += _("Enigma2 uptime:\t%s\n") % e2uptime
		AboutText += _("Skin:\t%s") % config.skin.primary_skin.value[0:-9] + _("  (%s x %s)") % (skinWidth, skinHeight) + "\n"

		fp_version = getFPVersion()
		if fp_version is None:
			fp_version = ""
		elif fp_version != 0:
			fp_version = _("FP version:\t%s") % fp_version
			AboutText += fp_version + "\n"

		self["AboutScrollLabel"].setText(AboutText)

	def dualBoot(self):
		rootfs2 = False
		kernel2 = False
		with open("/proc/mtd") as f:
			self.dualbootL = f.readlines()
			for x in self.dualbootL:
				if "rootfs2" in x:
					rootfs2 = True
				if "kernel2" in x:
					kernel2 = True
			if rootfs2 and kernel2:
				return True
			else:
				return False

	def showTranslationInfo(self):
		self.session.open(TranslationInfo)

	def showUpdatePlugin(self):
		self.session.open(UpdatePlugin)

	def showAboutReleaseNotes(self):
		self.session.open(CommitInfo)

	def setup(self):
		from Screens.Setup import Setup
		self.session.openWithCallback(self.populate, Setup, "about")


class Devices(AboutBase):
	def __init__(self, session):
		AboutBase.__init__(self, session, labels=True)
		self.skinName = "AboutOE"
		self.setTitle(_("Devices"))
		self.onLayoutFinish.append(self.populate)

	def populate(self):
		nims = nimmanager.nimList()
		if len(nims) > 4:
			desc_list = []
			for nim in nims:
				data = nim.split(":")
				idx = data[0].strip(_("Tuner")).strip()
				desc = data[1].strip()
				if desc_list and desc_list[-1]["desc"] == desc:
					desc_list[-1]["end"] = idx
				else:
					desc_list.append({"desc": desc, "start": idx, "end": idx})

			nims = []
			for nim in desc_list:
				nims.append(f'%s {nim["start"]}{"-%s" % nim["end"] if nim["start"] != nim["end"] else ""}: {nim["desc"]}' % _("Tuner"))

		hddlist = harddiskmanager.HDDList()
		devicelist = []
		mountdict = {m[0]: m for m in df_h()}  # tuples of (device, size, used, free, use %, mount)
		print(f"[About] mountdict\n{mountdict}\n")
		if hddlist:
			print("[About] hddlist = %s" % (hddlist))
			for i in range(len(hddlist)):
				hdd = hddlist[i][0].replace("/dev/mmcblk0", "/dev/mmcblk0p3")  # dm9x0:mmcblk0p3 multiboot root & storage
				hddsplit = hdd.split("/", 1)  # hddsplit[0]:description hddsplit[1]:device and space
				hddDescription = hddsplit[0]  # device description
				if "ATA" in hddDescription:
					hddDescription = hddDescription.replace("ATA", "", 2).replace("SATA ", "SATA Internal Bus ").replace("(", "").replace(")", "").replace("   ", " ").replace("  ", " ").replace("/dev", " /dev")
				if "USB" in hddDescription or "SD" in hddDescription:
					hddDescription = hddDescription.replace("(", "").replace(")", "").replace("   ", " ").replace("  ", " ").replace("/dev", " /dev")
				hddDescription = hddDescription.split()  # split out fields without spaces
				hddDescLen = len(hddDescription)
				hddKey1 = ("/" + hddsplit[1].split(" ", 1)[0])  # device key e.g. /dev/sda /dev/sdb /dev/mmcblk0p1

				if mountdict:
					for device in mountdict:
						if hddKey1 in device:
							break  # use break here to excape the loop and NOT run its else clause
					else:  # device not mounted
						devicelist.append("%s" % hdd)
						continue  # continues the outer loop so code below is skipped
					# device is mounted so add device partition(s) attributes
					keyRange = 5 if "dev/sd" in hddKey1 else 2  # assumes no more than 4 partitions on device
					for count in range(1, keyRange):
						hddKey = "%s" % hddKey1 + "%s" % str(count) if "dev/sd" in hddKey1 else hddKey1
						if hddKey in mountdict.keys():
							freeline = _("%s ") % hddKey + _("%s   ") % mountdict[hddKey][1] + "\n  " + _("Mount: %s  ") % mountdict[hddKey][5] + _("Used: %s  ") % mountdict[hddKey][2] + _("Free: %s ") % mountdict[hddKey][3]
							line = ""
							for count in range(0, hddDescLen):
								line += "%s " % hddDescription[count]
							line += "%s " % freeline
							devicelist.append(line)
				else:  # device not mounted
					devicelist.append("%s" % hdd)

		networkmountinfo = []
		for device in mountdict:
			if device.startswith(("192", "//192")):  # LAN IP starting 192.xxx.xxx.xxx (Is this a good check? Will all LAN IPs start 192? No!)
				ipaddress = mountdict[device][0]
				mounttotal = mountdict[device][1]
				mountfree = mountdict[device][3]
				networkmountinfo.append("%s (%s, %s %s)  " % ("Mount: " + ipaddress, mounttotal, _("Free:"), mountfree))
		if ospath.exists("/media/autofs"):
			for entry in sorted(listdir("/media/autofs")):
				mountEntry = ospath.join("/media/autofs", entry)
				networkmountinfo.append(_("%s is also enabled for autofs network") % (mountEntry))

		self["AboutScrollLabel"].split = False  # don't split
		self["AboutScrollLabel"].setText("\n".join(
			[self.addColor(_("Detected tuners").upper())] + (nims or [_("none")]) + [""] +
			[self.addColor(_("Detected devices").upper())] + (devicelist or [_("none")]) + [""] +
			[self.addColor(_("Network servers").upper())] + (networkmountinfo or [_("none")]) + [""]))

	def createSummary(self):
		return AboutSummary


class SystemMemoryInfo(AboutBase):
	def __init__(self, session):
		AboutBase.__init__(self, session, labels=True)
		self.setTitle(_("Memory"))
		self.skinName = ["SystemMemoryInfo", "About"]
		out_lines = open("/proc/meminfo").readlines()  # output is in kiB so multiply by 1024
		self.AboutText = self.addColor(_("RAM")) + "\n"
		for lidx in range(len(out_lines) - 1):
			tstLine = out_lines[lidx].split()
			if "MemTotal:" in tstLine:
				MemTotal = out_lines[lidx].split()
				self.AboutText += _("Total memory:") + "\t" + bytesToHumanReadable(int(MemTotal[1]) * 1024, binary=True) + "\n"
			if "MemFree:" in tstLine:
				MemFree = out_lines[lidx].split()
				self.AboutText += _("Free memory:") + "\t" + bytesToHumanReadable(int(MemFree[1]) * 1024, binary=True) + "\n"
			if "Buffers:" in tstLine:
				Buffers = out_lines[lidx].split()
				self.AboutText += _("Buffers:") + "\t" + bytesToHumanReadable(int(Buffers[1]) * 1024, binary=True) + "\n"
			if "Cached:" in tstLine:
				Cached = out_lines[lidx].split()
				self.AboutText += _("Cached:") + "\t" + bytesToHumanReadable(int(Cached[1]) * 1024, binary=True) + "\n"
			if "SwapTotal:" in tstLine:
				SwapTotal = out_lines[lidx].split()
				self.AboutText += _("Total swap:") + "\t" + bytesToHumanReadable(int(SwapTotal[1]) * 1024, binary=True) + "\n"
			if "SwapFree:" in tstLine:
				SwapFree = out_lines[lidx].split()
				self.AboutText += _("Free swap:") + "\t" + bytesToHumanReadable(int(SwapFree[1]) * 1024, binary=True) + "\n\n"

		flash = df_h(find="/")[0]

		self.AboutText += self.addColor(_("FLASH")) + "\n"
		self.AboutText += _("Total:") + "\t" + flash[1] + "\n"
		self.AboutText += _("Free:") + "\t" + flash[3] + "\n\n"

		self["AboutScrollLabel"].setText(self.AboutText)


class SystemNetworkInfo(AboutBase):
	def __init__(self, session):
		AboutBase.__init__(self, session)
		self.setTitle(_("Network"))
		self.skinName = ["SystemNetworkInfo", "WlanStatus"]
		self["LabelBSSID"] = StaticText()
		self["LabelESSID"] = StaticText()
		self["LabelQuality"] = StaticText()
		self["LabelSignal"] = StaticText()
		self["LabelBitrate"] = StaticText()
		self["LabelEnc"] = StaticText()
		self["BSSID"] = StaticText()
		self["ESSID"] = StaticText()
		self["quality"] = StaticText()
		self["signal"] = StaticText()
		self["bitrate"] = StaticText()
		self["enc"] = StaticText()

		self["IFtext"] = StaticText()
		self["IF"] = StaticText()
		self["Statustext"] = StaticText()
		self["statuspic"] = MultiPixmap()
		self["statuspic"].setPixmapNum(1)
		self["statuspic"].show()
		self["devicepic"] = MultiPixmap()

		self.iface = None
		self.createscreen()
		self.iStatus = None

		if iNetwork.isWirelessInterface(self.iface):
			try:
				from Plugins.SystemPlugins.WirelessLan.Wlan import iStatus

				self.iStatus = iStatus
			except:
				pass
			self.resetList()
			self.onClose.append(self.cleanup)
		self.onLayoutFinish.append(self.updateStatusbar)
		self.timer = eTimer()
		self.timer.callback.append(self.getWanIP)

	def createscreen(self):
		self.AboutText = ""
		self.iface = "eth0"
		eth0 = getIfConfig("eth0")
		if "addr" in eth0:
			self.AboutText += _("IP:") + "\t" + eth0["addr"] + "\n"
			if "netmask" in eth0:
				self.AboutText += _("Netmask:") + "\t" + eth0["netmask"] + "\n"
			if "hwaddr" in eth0:
				self.AboutText += _("MAC:") + "\t" + eth0["hwaddr"] + "\n"
			self.iface = "eth0"

		eth1 = getIfConfig("eth1")
		if "addr" in eth1:
			self.AboutText += _("IP:") + "\t" + eth1["addr"] + "\n"
			if "netmask" in eth1:
				self.AboutText += _("Netmask:") + "\t" + eth1["netmask"] + "\n"
			if "hwaddr" in eth1:
				self.AboutText += _("MAC:") + "\t" + eth1["hwaddr"] + "\n"
			self.iface = "eth1"

		ra0 = getIfConfig("ra0")
		if "addr" in ra0:
			self.AboutText += _("IP:") + "\t" + ra0["addr"] + "\n"
			if "netmask" in ra0:
				self.AboutText += _("Netmask:") + "\t" + ra0["netmask"] + "\n"
			if "hwaddr" in ra0:
				self.AboutText += _("MAC:") + "\t" + ra0["hwaddr"] + "\n"
			self.iface = "ra0"

		wlan0 = getIfConfig("wlan0")
		if "addr" in wlan0:
			self.AboutText += _("IP:") + "\t" + wlan0["addr"] + "\n"
			if "netmask" in wlan0:
				self.AboutText += _("Netmask:") + "\t" + wlan0["netmask"] + "\n"
			if "hwaddr" in wlan0:
				self.AboutText += _("MAC:") + "\t" + wlan0["hwaddr"] + "\n"
			self.iface = "wlan0"

		wlan3 = getIfConfig("wlan3")
		if "addr" in wlan3:
			self.AboutText += _("IP:") + "\t" + wlan3["addr"] + "\n"
			if "netmask" in wlan3:
				self.AboutText += _("Netmask:") + "\t" + wlan3["netmask"] + "\n"
			if "hwaddr" in wlan3:
				self.AboutText += _("MAC:") + "\t" + wlan3["hwaddr"] + "\n"
			self.iface = "wlan3"

		rx_bytes, tx_bytes = getIfTransferredData(self.iface)
		self.AboutText += "\n" + _("Bytes received:") + "\t" + bytesToHumanReadable(int(rx_bytes)) + "\n"
		self.AboutText += _("Bytes sent:") + "\t" + bytesToHumanReadable(int(tx_bytes)) + "\n"
		for line in popen("ethtool %s |grep Speed" % self.iface, "r"):
			line = line.strip().split(":")
			line = line[1].replace(" ", "")
			if "Speed:" in line:
				self.AboutText += _("Speed:") + "\t" + line + _("Mb/s")
		hostname = open("/proc/sys/kernel/hostname").read()
		self.AboutText += "\n" + _("Hostname:") + "\t" + hostname + "\n"
		self["AboutScrollLabel"].setText(self.AboutText)

	def cleanup(self):
		if self.iStatus:
			self.iStatus.stopWlanConsole()

	def resetList(self):
		if self.iStatus:
			self.iStatus.getDataForInterface(self.iface, self.getInfoCB)

	def getInfoCB(self, data, status):
		self.LinkState = None
		if data is not None and data:
			if status is not None:
				# getDataForInterface()->iwconfigFinished() in
				# Plugins/SystemPlugins/WirelessLan/Wlan.py sets fields to boolean False
				# if there is no info for them, so we need to check that possibility
				# for each status[self.iface] field...
				#
				if self.iface == "wlan0" or self.iface == "wlan3" or self.iface == "ra0":
					# accesspoint is used in the "enc" code too, so we get it regardless
					#
					if not status[self.iface]["accesspoint"]:
						accesspoint = _("Unknown")
					else:
						if status[self.iface]["accesspoint"] == "Not-Associated":
							accesspoint = _("Not-Associated")
							essid = _("No connection")
						else:
							accesspoint = status[self.iface]["accesspoint"]
					if "BSSID" in self:
						self.AboutText += _("Accesspoint:") + "\t" + accesspoint + "\n"

					if "ESSID" in self:
						if not status[self.iface]["essid"]:
							essid = _("Unknown")
						else:
							if status[self.iface]["essid"] == "off":
								essid = _("No connection")
							else:
								essid = status[self.iface]["essid"]
						self.AboutText += _("SSID:") + "\t" + essid + "\n"

					if "quality" in self:
						if not status[self.iface]["quality"]:
							quality = _("Unknown")
						else:
							quality = status[self.iface]["quality"]
						self.AboutText += _("Link quality:") + "\t" + quality + "\n"

					if "bitrate" in self:
						if not status[self.iface]["bitrate"]:
							bitrate = _("Unknown")
						else:
							if status[self.iface]["bitrate"] == "0":
								bitrate = _("Unsupported")
							else:
								bitrate = str(status[self.iface]["bitrate"]) + " Mb/s"
						self.AboutText += _("Bitrate:") + "\t" + bitrate + "\n"

					if "signal" in self:
						if not status[self.iface]["signal"]:
							signal = _("Unknown")
						else:
							signal = str(status[self.iface]["signal"])
						self.AboutText += _("Signal strength:") + "\t" + signal + "\n"

					if "enc" in self:
						if not status[self.iface]["encryption"]:
							encryption = _("Unknown")
						else:
							if status[self.iface]["encryption"] == "off":
								if accesspoint == "Not-Associated":
									encryption = _("Disabled")
								else:
									encryption = _("Unsupported")
							else:
								encryption = _("Enabled")
						self.AboutText += _("Encryption:") + "\t" + encryption + "\n"

					if ((status[self.iface]["essid"] and status[self.iface]["essid"] == "off") or not status[self.iface]["accesspoint"] or status[self.iface]["accesspoint"] == "Not-Associated"):
						self.LinkState = False
						self["statuspic"].setPixmapNum(1)
						self["statuspic"].show()
					else:
						self.LinkState = True
						iNetwork.checkNetworkState(self.checkNetworkCB)
					self["AboutScrollLabel"].setText(self.AboutText)

	def updateStatusbar(self):
		self["IFtext"].setText(_("Network:"))
		self["IF"].setText(iNetwork.getFriendlyAdapterName(self.iface))
		self["Statustext"].setText(_("Link:"))
		if iNetwork.isWirelessInterface(self.iface):
			self["devicepic"].setPixmapNum(1)
			try:
				self.iStatus.getDataForInterface(self.iface, self.getInfoCB)
			except:
				self["statuspic"].setPixmapNum(1)
				self["statuspic"].show()
		else:
			iNetwork.getLinkState(self.iface, self.dataAvail)
			self["devicepic"].setPixmapNum(0)
		self["devicepic"].show()
		self.timer.start(10, 1)

	def getWanIP(self):
		try:
			r = get("http://ipecho.net/plain", timeout=1)
			r.raise_for_status()
			self.AboutText += _("Wan IP:") + "\t" + r.content.decode() + "\n"
			self["AboutScrollLabel"].setText(self.AboutText)
		except Exception as err:
			print("[SystemNetworkInfo][getWanIP] error fetching Wan IP:\n", err, "\n")

	def dataAvail(self, data):
		self.LinkState = None
		for line in data.splitlines():
			line = line.strip()
			if "Link detected:" in line:
				if "yes" in line:
					self.LinkState = True
				else:
					self.LinkState = False
		if self.LinkState:
			iNetwork.checkNetworkState(self.checkNetworkCB)
		else:
			self["statuspic"].setPixmapNum(1)
			self["statuspic"].show()

	def checkNetworkCB(self, data):
		try:
			if iNetwork.getAdapterAttribute(self.iface, "up") is True:
				if self.LinkState is True:
					if data <= 2:
						self["statuspic"].setPixmapNum(0)
					else:
						self["statuspic"].setPixmapNum(1)
				else:
					self["statuspic"].setPixmapNum(1)
			else:
				self["statuspic"].setPixmapNum(1)
			self["statuspic"].show()
		except:
			pass


class AboutSummary(ScreenSummary):
	def __init__(self, session, parent):
		ScreenSummary.__init__(self, session, parent=parent)
		self.skinName = "AboutSummary"
		self.aboutText = []
		self["AboutText"] = StaticText()
		self.aboutText.append(_("OpenViX: %s") % SystemInfo["imageversion"] + "." + SystemInfo["imagebuild"] + "\n")
		self.aboutText.append(_("Model: %s %s\n") % (SystemInfo["MachineBrand"], SystemInfo["MachineName"]))
		self.aboutText.append(_("Updated: %s") % getLastCommitDate() + "\n")
		SystemTemperature = getsystemTemperature()
		if SystemTemperature and int(SystemTemperature.replace("\n", "")) > 0:
			self.aboutText.append(_("System temperature: %s") % SystemTemperature.replace("\n", "") + "\xb0" + "C\n")
		self.aboutText.append(_("Chipset: %s") % CHIPSET.replace("\n", "").upper() + "\n")
		self.aboutText.append(_("Kernel: %s") % KERNEL + "\n")
		self.aboutText.append(_("Drivers: %s") % driversDate() + "\n")
		self["AboutText"].text = "".join(self.aboutText)
		self.timer = eTimer()
		self.timer.callback.append(self.update)
		self.timer.start(3000, 1)

	def update(self):
		self.timer.stop()
		if self.aboutText:
			self.aboutText.append(self.aboutText.pop(0))
			self["AboutText"].text = "".join(self.aboutText)
			self.timer.start(2000, 1)


class TranslationInfo(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle(_("Translations"))

		self["key_red"] = Button(_("Close"))
		self["actions"] = ActionMap(["SetupActions"],
		{
			"cancel": self.close,
			"ok": self.close,
		})

		# _("") fetches the translator info from the *.po.
		infomap = {x.split(":")[0].strip(): x.split(":")[1].strip() for x in _("").split("\n") if len(x.split(":")) == 2}
		self["TranslatorName"] = StaticText(infomap.get("Language-Team") or infomap.get("Last-Translator", ""))

		# TRANSLATORS: Add here whatever should be shown in the "translator" about screen, up to 6 lines (use \n for newline)
		self["TranslationInfo"] = StaticText(_("TRANSLATOR_INFO") if "TRANSLATOR_INFO" != _("TRANSLATOR_INFO") else "")
