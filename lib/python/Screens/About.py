from os import listdir, path, popen
from re import search
from enigma import eTimer, getEnigmaVersionString, getDesktop
from boxbranding import getMachineBrand, getMachineBuild, getMachineName, getImageVersion, getImageType, getImageBuild, getDriverDate, getImageDevBuild
from Components.About import about
from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.config import config
from Components.Console import Console
from Components.Harddisk import harddiskmanager
from Components.Network import iNetwork
from Components.NimManager import nimmanager
from Components.Pixmap import MultiPixmap
from Components.ScrollLabel import ScrollLabel
from Components.Sources.StaticText import StaticText
from Components.SystemInfo import SystemInfo, BoxInfo
from Screens.GitCommitInfo import CommitInfo
from Screens.Screen import Screen, ScreenSummary
from Screens.SoftwareUpdate import UpdatePlugin
from Tools.Directories import fileExists, fileCheck, pathExists, isPluginInstalled
from Tools.Multiboot import GetCurrentImageMode
from Tools.StbHardware import getFPVersion

class About(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle(_("About"))
		self.skinName = "AboutOE"
		self.populate()

		self["key_red"] = Button(_("Close"))
		self["key_green"] = Button(_("Translations"))
		self["key_yellow"] = Button(_("Software update"))
		self["key_blue"] = Button(_("Release notes"))
		self["actions"] = ActionMap(["SetupActions", "ColorActions", "DirectionActions"],
									{
										"cancel": self.close,
										"ok": self.close,
										"up": self["AboutScrollLabel"].pageUp,
										"down": self["AboutScrollLabel"].pageDown,
										"green": self.showTranslationInfo,
										"yellow": self.showUpdatePlugin,
										"blue": self.showAboutReleaseNotes,
									})

	def populate(self):
		self["lab1"] = StaticText(_("Virtuosso Image Xtreme"))
		self["lab2"] = StaticText(_("By Team ViX"))
		model = None
		AboutText = ""
		self["lab3"] = StaticText(_("Support at") + " www.world-of-satellite.com")

		AboutText += _("Model:\t%s %s\n") % (getMachineBrand(), getMachineName())
		
		if about.getChipSetString() != _("unavailable"):
			if SystemInfo["HasHiSi"]:
				AboutText += _("Chipset:\tHiSilicon %s\n") % about.getChipSetString().upper()
			elif about.getIsBroadcom():
				AboutText += _("Chipset:\tBroadcom %s\n") % about.getChipSetString().upper()
			else:
				AboutText += _("Chipset:\t%s\n") % about.getChipSetString().upper()

		AboutText += _("CPU:\t%s %s %s\n") % (about.getCPUArch(), about.getCPUSpeedString(), about.getCpuCoresString())

		AboutText += _("SoC:\t%s\n") % BoxInfo.getItem("socfamily").upper()

		tempinfo = ""
		if path.exists("/proc/stb/sensors/temp0/value"):
			with open("/proc/stb/sensors/temp0/value", "r") as f:
				tempinfo = f.read()
		elif path.exists("/proc/stb/fp/temp_sensor"):
			with open("/proc/stb/fp/temp_sensor", "r") as f:
				tempinfo = f.read()
		elif path.exists("/proc/stb/sensors/temp/value"):
			with open("/proc/stb/sensors/temp/value", "r") as f:
				tempinfo = f.read()
		if tempinfo and int(tempinfo.replace("\n", "")) > 0:
			AboutText += _("System temp:\t%s") % tempinfo.replace("\n", "").replace(" ", "") + "\xb0" + "C\n"

		tempinfo = ""
		if path.exists("/proc/stb/fp/temp_sensor_avs"):
			with open("/proc/stb/fp/temp_sensor_avs", "r") as f:
				tempinfo = f.read()
		elif path.exists("/sys/devices/virtual/thermal/thermal_zone0/temp"):
			try:
				with open("/sys/devices/virtual/thermal/thermal_zone0/temp", "r") as f:
					tempinfo = f.read()
					tempinfo = tempinfo[:-4]
			except:
				tempinfo = ""
		elif path.exists("/proc/hisi/msp/pm_cpu"):
			try:
				tempinfo = search("temperature = (\d+) degree", open("/proc/hisi/msp/pm_cpu").read()).group(1)
			except:
				tempinfo = ""
		if tempinfo and int(tempinfo) > 0:
			AboutText += _("Processor temp:\t%s") % tempinfo.replace("\n", "").replace(" ", "") + "\xb0" + "C\n"

		imageSubBuild = ""
		if getImageType() != "release":
			imageSubBuild = ".%s" % getImageDevBuild()
		AboutText += _("Image:\t%s.%s%s (%s)\n") % (getImageVersion(), getImageBuild(), imageSubBuild, getImageType().title())

		if BoxInfo.getItem("mtdbootfs") != "" and " " not in BoxInfo.getItem("mtdbootfs"):
			AboutText += _("Boot Device:\t%s\n") % BoxInfo.getItem("mtdbootfs")

		if SystemInfo["HasH9SD"]:
			if "rootfstype=ext4" in open("/sys/firmware/devicetree/base/chosen/bootargs", "r").read():
				part = "        - SD card in use for Image root \n"
			else:
				part = "        - eMMC slot in use for Image root \n"
			AboutText += _("%s") % part

		if SystemInfo["canMultiBoot"]:
			slot = image = SystemInfo["MultiBootSlot"]
			part = "eMMC slot %s" % slot
			bootmode = ""
			if SystemInfo["canMode12"]:
				bootmode = "bootmode = %s" % GetCurrentImageMode()
			print("[About] HasHiSi = %s, slot = %s" % (SystemInfo["HasHiSi"], slot))
			if SystemInfo["HasHiSi"] and "sda" in SystemInfo["canMultiBoot"][slot]["root"]:
				if slot > 4:
					image -= 4
				else:
					image -= 1
				part = "SDcard slot %s (%s) " % (image, SystemInfo["canMultiBoot"][slot]["root"])
			AboutText += _("Image Slot:\t%s") % "Startup " + str(slot) + " - " + part + " " + bootmode + "\n"

		if getMachineName() in ("ET8500") and path.exists("/proc/mtd"):
			self.dualboot = self.dualBoot()
			if self.dualboot:
				AboutText += _("ET8500 Multiboot: Installed\n")

		skinWidth = getDesktop(0).size().width()
		skinHeight = getDesktop(0).size().height()

		string = getDriverDate()
		year = string[0:4]
		month = string[4:6]
		day = string[6:8]
		driversdate = "-".join((day, month, year))

		AboutText += _("Drivers:\t%s\n") % driversdate
		AboutText += _("Kernel:\t%s\n") % about.getKernelVersionString()
		AboutText += _("GStreamer:\t%s\n") % about.getGStreamerVersionString().replace("GStreamer ", "")
		if isPluginInstalled("ServiceApp") and config.plugins.serviceapp.servicemp3.replace.value == True:
			AboutText += _("4097 iptv player:\t%s\n") % config.plugins.serviceapp.servicemp3.player.value
		else:
			AboutText += _("4097 iptv player:\tDefault player\n")	
		AboutText += _("Python:\t%s\n") % about.getPythonVersionString()
		flashDate = about.getFlashDateString()[8:]  + about.getFlashDateString()[4:8] + about.getFlashDateString()[0:4] 
		AboutText += _("Installed:\t%s\n") % flashDate
		lastUpdate = getEnigmaVersionString()[8:]  + getEnigmaVersionString()[4:8] + getEnigmaVersionString()[0:4] 
		AboutText += _("Last update:\t%s\n") % lastUpdate
		AboutText += _("E2 (re)starts:\t%s\n") % config.misc.startCounter.value
		uptime = about.getBoxUptime()
		if uptime:
			AboutText += _("Uptime:\t%s\n") % uptime
		e2uptime = about.getEnigmaUptime()
		if e2uptime:
			AboutText += _("Enigma2 uptime:\t%s\n") % e2uptime
		AboutText += _("Skin:\t%s") % config.skin.primary_skin.value[0:-9] + _("  (%s x %s)") % (skinWidth, skinHeight) + "\n"

		fp_version = getFPVersion()
		if fp_version is None:
			fp_version = ""
		elif fp_version != 0:
			fp_version = _("FP version:\t%s") % fp_version
			AboutText += fp_version + "\n"

		bootloader = ""
		if path.exists('/sys/firmware/devicetree/base/bolt/tag'):
				f = open('/sys/firmware/devicetree/base/bolt/tag', 'r')
				bootloader = f.readline().replace('\x00', '').replace('\n', '')
				f.close()
				AboutText += _("Bootloader:\t%s\n") % (bootloader)

		self["AboutScrollLabel"] = ScrollLabel(AboutText)

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

	def createSummary(self):
		return AboutSummary


class Devices(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle(_("Devices"))
		self["TunerHeader"] = StaticText(_("Detected tuners:"))
		self["HDDHeader"] = StaticText(_("Detected devices:"))
		self["MountsHeader"] = StaticText(_("Network servers:"))
		self["nims"] = StaticText()
		for count in range(4):
			self["Tuner" + str(count)] = StaticText("")
		self["hdd"] = StaticText()
		self["mounts"] = StaticText()
		self.list = []
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.populate2)
		self["key_red"] = Button(_("Close"))
		self["actions"] = ActionMap(["SetupActions"],
									{
										"cancel": self.close,
										"ok": self.close,
									})
		self.onLayoutFinish.append(self.populate)

	def populate(self):
		self.mountinfo = ""
		self["actions"].setEnabled(False)
		scanning = _("Please wait while scanning for devices...")
		self["nims"].setText(scanning)
		for count in range(4):
			self["Tuner" + str(count)].setText(scanning)
		self["hdd"].setText(scanning)
		self["mounts"].setText(scanning)
		self.activityTimer.start(1)

	def populate2(self):
		self.activityTimer.stop()
		self.Console = Console()
		niminfo = ""
		nims = nimmanager.nimListCompressed()
		for count in range(len(nims)):
			if niminfo:
				niminfo += "\n"
			niminfo += nims[count]
		self["nims"].setText(niminfo)

		nims = nimmanager.nimList()
		if len(nims) <= 4:
			for count in range(4):
				if count < len(nims):
					self["Tuner" + str(count)].setText(nims[count])
				else:
					self["Tuner" + str(count)].setText("")
		else:
			desc_list = []
			cur_idx = -1
			for count in range(len(nims)):
				data = nims[count].split(":")
				idx = data[0].strip(_("Tuner")).strip()
				desc = data[1].strip()
				if desc_list and desc_list[cur_idx]["desc"] == desc:
					desc_list[cur_idx]["end"] = idx
				else:
					desc_list.append({"desc": desc, "start": idx, "end": idx})
					cur_idx += 1

			for count in range(4):
				if count < len(desc_list):
					if desc_list[count]["start"] == desc_list[count]["end"]:
						text = "%s %s: %s" % (_("Tuner"), desc_list[count]["start"], desc_list[count]["desc"])
					else:
						text = "%s %s-%s: %s" % (_("Tuner"), desc_list[count]["start"], desc_list[count]["end"], desc_list[count]["desc"])
				else:
					text = ""

				self["Tuner" + str(count)].setText(text)

		self.hddlist = harddiskmanager.HDDList()
		self.list = []
		if self.hddlist:
			print("[About] hddlist = %s" % (self.hddlist))
			for count in range(len(self.hddlist)):
				hdd = self.hddlist[count][1]
				hddp = self.hddlist[count][0]
				if "ATA" in hddp:
					hddp = hddp.replace("ATA", "")
					hddp = hddp.replace("Internal", "ATA Bus ")
				free = hdd.Totalfree()
				if (free / 1000 / 1000) >= 1:
					freeline = _("Free: ") + str(round((free / 1000 / 1000), 2)) + _("TB")
				elif (free / 1000) >= 1:
					freeline = _("Free: ") + str(round((free / 1000), 2)) + _("GB")
				elif free >= 1:
					freeline = _("Free: ") + str(round(free, 2)) + _("MB")
				elif "Generic(STORAGE" in hddp:				# This is the SDA boot volume for SF8008 if "full" #
					continue
				else:
					freeline = _("Free: ") + _("full")
				line = "%s      %s" % (hddp, freeline)
				self.list.append(line)
		self.list = "\n".join(self.list)
		self["hdd"].setText(self.list)

		self.Console.ePopen("df -mh | grep -v '^Filesystem'", self.Stage1Complete)

	def Stage1Complete(self, result, retval, extra_args=None):
		result = result.replace("\n                        ", " ").split("\n")
		self.mountinfo = ""
		for line in result:
			self.parts = line.split()
			if line and self.parts[0] and (self.parts[0].startswith("192") or self.parts[0].startswith("//192")):
				line = line.split()
				ipaddress = line[0]
				mounttotal = line[1]
				mountfree = line[3]
				if self.mountinfo:
					self.mountinfo += "\n"
				self.mountinfo += "%s (%sB, %sB %s)" % (ipaddress, mounttotal, mountfree, _("free"))
		if pathExists("/media/autofs"):
			for entry in sorted(listdir("/media/autofs")):
				mountEntry = path.join("/media/autofs", entry)
				self.mountinfo += _("\n %s is also enabled for autofs network mount") % (mountEntry)
		if self.mountinfo:
			self["mounts"].setText(self.mountinfo)
		else:
			self["mounts"].setText(_("none"))
		self["actions"].setEnabled(True)

	def createSummary(self):
		return AboutSummary


class SystemMemoryInfo(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle(_("Memory"))
		self.skinName = ["SystemMemoryInfo", "About"]
		self["lab1"] = StaticText(_("Virtuosso Image Xtreme"))
		self["lab2"] = StaticText(_("By Team ViX"))
		self["lab3"] = StaticText(_("Support at %s") % "www.world-of-satellite.com")
		self["AboutScrollLabel"] = ScrollLabel()

		self["key_red"] = Button(_("Close"))
		self["actions"] = ActionMap(["SetupActions"],
									{
										"cancel": self.close,
										"ok": self.close,
									})

		out_lines = open("/proc/meminfo").readlines()
		self.AboutText = _("RAM") + "\n\n"
		RamTotal = "-"
		RamFree = "-"
		for lidx in range(len(out_lines) - 1):
			tstLine = out_lines[lidx].split()
			if "MemTotal:" in tstLine:
				MemTotal = out_lines[lidx].split()
				self.AboutText += _("Total memory:") + "\t" + MemTotal[1] + "\n"
			if "MemFree:" in tstLine:
				MemFree = out_lines[lidx].split()
				self.AboutText += _("Free memory:") + "\t" + MemFree[1] + "\n"
			if "Buffers:" in tstLine:
				Buffers = out_lines[lidx].split()
				self.AboutText += _("Buffers:") + "\t" + Buffers[1] + "\n"
			if "Cached:" in tstLine:
				Cached = out_lines[lidx].split()
				self.AboutText += _("Cached:") + "\t" + Cached[1] + "\n"
			if "SwapTotal:" in tstLine:
				SwapTotal = out_lines[lidx].split()
				self.AboutText += _("Total swap:") + "\t" + SwapTotal[1] + "\n"
			if "SwapFree:" in tstLine:
				SwapFree = out_lines[lidx].split()
				self.AboutText += _("Free swap:") + "\t" + SwapFree[1] + "\n\n"

		self["actions"].setEnabled(False)
		self.Console = Console()
		self.Console.ePopen("df -mh / | grep -v '^Filesystem'", self.Stage1Complete)

	def Stage1Complete(self, result, retval, extra_args=None):
		flash = str(result).replace("\n", "")
		flash = flash.split()
		RamTotal = flash[1]
		RamFree = flash[3]

		self.AboutText += _("FLASH") + "\n\n"
		self.AboutText += _("Total:") + "\t" + RamTotal + "\n"
		self.AboutText += _("Free:") + "\t" + RamFree + "\n\n"

		self["AboutScrollLabel"].setText(self.AboutText)
		self["actions"].setEnabled(True)

	def createSummary(self):
		return AboutSummary


class SystemNetworkInfo(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
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

		self["AboutScrollLabel"] = ScrollLabel()

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

		self["key_red"] = StaticText(_("Close"))

		self["actions"] = ActionMap(["SetupActions", "DirectionActions"],
									{
										"cancel": self.close,
										"ok": self.close,
										"up": self["AboutScrollLabel"].pageUp,
										"down": self["AboutScrollLabel"].pageDown
									})
		self.onLayoutFinish.append(self.updateStatusbar)

	def createscreen(self):
		self.AboutText = ""
		self.iface = "eth0"
		eth0 = about.getIfConfig("eth0")
		if "addr" in eth0:
			self.AboutText += _("IP:") + "\t" + eth0["addr"] + "\n"
			if "netmask" in eth0:
				self.AboutText += _("Netmask:") + "\t" + eth0["netmask"] + "\n"
			if "hwaddr" in eth0:
				self.AboutText += _("MAC:") + "\t" + eth0["hwaddr"] + "\n"
			self.iface = "eth0"

		eth1 = about.getIfConfig("eth1")
		if "addr" in eth1:
			self.AboutText += _("IP:") + "\t" + eth1["addr"] + "\n"
			if "netmask" in eth1:
				self.AboutText += _("Netmask:") + "\t" + eth1["netmask"] + "\n"
			if "hwaddr" in eth1:
				self.AboutText += _("MAC:") + "\t" + eth1["hwaddr"] + "\n"
			self.iface = "eth1"

		ra0 = about.getIfConfig("ra0")
		if "addr" in ra0:
			self.AboutText += _("IP:") + "\t" + ra0["addr"] + "\n"
			if "netmask" in ra0:
				self.AboutText += _("Netmask:") + "\t" + ra0["netmask"] + "\n"
			if "hwaddr" in ra0:
				self.AboutText += _("MAC:") + "\t" + ra0["hwaddr"] + "\n"
			self.iface = "ra0"

		wlan0 = about.getIfConfig("wlan0")
		if "addr" in wlan0:
			self.AboutText += _("IP:") + "\t" + wlan0["addr"] + "\n"
			if "netmask" in wlan0:
				self.AboutText += _("Netmask:") + "\t" + wlan0["netmask"] + "\n"
			if "hwaddr" in wlan0:
				self.AboutText += _("MAC:") + "\t" + wlan0["hwaddr"] + "\n"
			self.iface = "wlan0"

		wlan3 = about.getIfConfig("wlan3")
		if "addr" in wlan3:
			self.AboutText += _("IP:") + "\t" + wlan3["addr"] + "\n"
			if "netmask" in wlan3:
				self.AboutText += _("Netmask:") + "\t" + wlan3["netmask"] + "\n"
			if "hwaddr" in wlan3:
				self.AboutText += _("MAC:") + "\t" + wlan3["hwaddr"] + "\n"
			self.iface = "wlan3"

		rx_bytes, tx_bytes = about.getIfTransferredData(self.iface)
		self.AboutText += "\n" + _("Bytes received:") + "\t" + rx_bytes + "\n"
		self.AboutText += _("Bytes sent:") + "\t" + tx_bytes + "\n"
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

					if ((status[self.iface]["essid"] and status[self.iface]["essid"] == "off") or
					    not status[self.iface]["accesspoint"] or
					    status[self.iface]["accesspoint"] == "Not-Associated"):
						self.LinkState = False
						self["statuspic"].setPixmapNum(1)
						self["statuspic"].show()
					else:
						self.LinkState = True
						iNetwork.checkNetworkState(self.checkNetworkCB)
					self["AboutScrollLabel"].setText(self.AboutText)

	def exit(self):
		self.close(True)

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

	def createSummary(self):
		return AboutSummary


class AboutSummary(ScreenSummary):
	def __init__(self, session, parent):
		ScreenSummary.__init__(self, session, parent=parent)
		self.skinName = "AboutSummary"
		self.aboutText = []
		self["AboutText"] = StaticText()
		self.aboutText.append(_("OpenViX: %s") % getImageVersion() + "." + getImageBuild() + "\n")
		self.aboutText.append(_("Model: %s %s\n") % (getMachineBrand(), getMachineName()))
		self.aboutText.append(_("Updated: %s") % getEnigmaVersionString() + "\n")
		tempinfo = ""
		if path.exists("/proc/stb/sensors/temp0/value"):
			with open("/proc/stb/sensors/temp0/value", "r") as f:
				tempinfo = f.read()
		elif path.exists("/proc/stb/fp/temp_sensor"):
			with open("/proc/stb/fp/temp_sensor", "r") as f:
				tempinfo = f.read()
		elif path.exists("/proc/stb/sensors/temp/value"):
			with open("/proc/stb/sensors/temp/value", "r") as f:
				tempinfo = f.read()
		if tempinfo and int(tempinfo.replace("\n", "")) > 0:
			self.aboutText.append(_("System temperature: %s") % tempinfo.replace("\n", "") + "\xb0" + "C\n")
		if path.exists("/proc/stb/info/chipset"):
			chipset = open("/proc/stb/info/chipset", "r").read()
			self.aboutText.append(_("Chipset: %s") % chipset.replace("\n", "") + "\n")
		self.aboutText.append(_("Kernel: %s") % about.getKernelVersionString() + "\n")
		string = getDriverDate()
		year = string[0:4]
		month = string[4:6]
		day = string[6:8]
		driversdate = "-".join((year, month, day))
		self.aboutText.append(_("Drivers: %s") % driversdate + "\n")
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
		infomap = {x.split(":")[0].strip() : x.split(":")[1].strip() for x in _("").split("\n") if len(x.split(":")) == 2}
		self["TranslatorName"] = StaticText(infomap.get("Language-Team") or infomap.get("Last-Translator", ""))

		# TRANSLATORS: Add here whatever should be shown in the "translator" about screen, up to 6 lines (use \n for newline)
		self["TranslationInfo"] = StaticText(_("TRANSLATOR_INFO") if "TRANSLATOR_INFO" != _("TRANSLATOR_INFO") else "")

		

