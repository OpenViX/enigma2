from os import rmdir
from os.path import exists, ismount, join
from math import ceil
import tempfile
import struct

from Components.ActionMap import HelpableActionMap
from Components.ChoiceList import ChoiceEntryComponent, ChoiceList
from Components.config import ConfigSelection
from Components.Console import Console
from Components.Harddisk import Harddisk, harddiskmanager
from Components.Label import Label
from Components.Sources.StaticText import StaticText
from Components.SystemInfo import SystemInfo, getBoxDisplayName, BOXTYPE, KERNEL, MACHINEBUILD, MTDKERNEL, MTDROOTFS, UBIMB
from Screens.Console import Console as ConsoleScreen
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen, ScreenSummary
from Screens.Standby import QUIT_REBOOT, QUIT_RESTART, TryQuitMainloop
from Screens.Setup import Setup
from Tools.BoundFunction import boundFunction
from Tools.Directories import copyfile, fileReadLine, fileReadLines, fileWriteLine
from Tools.Multiboot import emptySlot, GetImagelist, GetCurrentImageMode, restoreSlots

ACTION_SELECT = 0
ACTION_CREATE = 1


class MultiBootSelector(Screen, HelpableScreen):
	def __init__(self, session, *args):
		Screen.__init__(self, session, mandatoryWidgets=["key_yellow", "key_blue"])
		HelpableScreen.__init__(self)
		self.title = _("MultiBoot Image Selector")
		self.skinName = ["MultiBootSelector", "Setup"]
		self.onChangedEntry = []
		self.tmp_dir = None
		self.fromInit = True
		usbIn = (SystemInfo["HasUsbhdd"].keys() and SystemInfo["HasKexecMultiboot"]) or UBIMB
		# print("[MultiBootSelector] usbIn, SystemInfo['HasUsbhdd'], SystemInfo['HasKexecMultiboot'], SystemInfo['HasKexecUSB']", usbIn, "   ", SystemInfo["HasUsbhdd"], "   ", SystemInfo["HasKexecMultiboot"], "   ", SystemInfo["HasKexecUSB"])
		self["config"] = ChoiceList(list=[ChoiceEntryComponent(text=((_("Retrieving image slots - Please wait...")), "Queued"))])
		self["description"] = StaticText(_("Press GREEN (Reboot) to switch images, YELLOW (Delete) to erase an image or BLUE (Restore) to restore all deleted images."))
		self["key_red"] = StaticText(_("Add Extra USB slots") if usbIn else _("Cancel"))
		self["key_green"] = StaticText()
		self["key_yellow"] = StaticText()
		self["key_blue"] = StaticText()
		self["defaultActions"] = HelpableActionMap(self, ["OkCancelActions", "DirectionActions", "ColorActions", "MenuActions"], {
			"cancel": (self.cancel, _("Cancel the image selection and exit")),
			"red": (self.cancel, _("Cancel")) if not usbIn else (self.KexecMount, _("Add Extra USB slots")),
			"menu": (boundFunction(self.cancel, True), _("Cancel the image selection and exit all menus")),
			"up": (self.keyUp, _("Move up a line")),
			"down": (self.keyDown, _("Move down a line")),
			"left": (self.keyUp, _("Move up a line")),
			"right": (self.keyDown, _("Move down a line")),
			"blue": (self.restoreImages, _("Select to restore all deleted images")),
		}, -1, description=_("MultiBootSelector Actions"))
		self["rebootActions"] = HelpableActionMap(self, ["OkCancelActions", "ColorActions", "KeyboardInputActions"], {
			"green": (self.reboot, _("Select the highlighted image and reboot")),
			"ok": (self.reboot, _("Select the highlighted image and reboot")),
		}, -1, description=_("MultiBootSelector Actions"))
		self["rebootActions"].setEnabled(False)
		self["deleteActions"] = HelpableActionMap(self, ["OkCancelActions", "ColorActions", "KeyboardInputActions"], {
			"yellow": (self.deleteImage, _("Select the highlighted image and delete")),
		}, -1, description=_("MultiBootSelector Actions"))
		self["deleteActions"].setEnabled(False)
		self.imagedict = []
		self.tmp_dir = tempfile.mkdtemp(prefix="MultibootSelector")
		Console().ePopen("mount %s %s" % (SystemInfo["MBbootdevice"], self.tmp_dir))
		self.callLater(self.getImagelist)

	def getImagelist(self):
		self.imagedict = GetImagelist(Recovery=SystemInfo["RecoveryMode"])
		imageList = []
		imageList12 = []
		self.deletedImagesExists = False
		self["key_blue"].text = ""
		currentimageslot = SystemInfo["MultiBootSlot"]
		mode = GetCurrentImageMode() or 0
		print("[MultiBootSelector] reboot0 slot:", currentimageslot)
		current = "  %s" % _("(Current)")
		slotRecov = _("%s%s - Select to access recovery options")
		slotSingle = _("Slot%s %s %s: %s%s")
		slotMulti = _("Slot%s %s %s: %s - %s mode%s")
		if self.imagedict:
			for x in sorted(self.imagedict.keys()):
				if self.imagedict[x]["imagename"] == _("Deleted image"):
					self.deletedImagesExists = True
					self["key_blue"].text = _("Restore")
				elif self.imagedict[x]["imagename"] != _("Empty slot"):
					if SystemInfo["canMode12"]:
						imageList.append(ChoiceEntryComponent(text=(slotMulti % (x, SystemInfo["canMultiBoot"][x]["slotType"], SystemInfo["canMultiBoot"][x]["slotname"], self.imagedict[x]["imagename"], "Kodi", current if x == currentimageslot and mode != 12 else ""), (x, 1))))
						imageList12.append(ChoiceEntryComponent(text=(slotMulti % (x, SystemInfo["canMultiBoot"][x]["slotType"], SystemInfo["canMultiBoot"][x]["slotname"], self.imagedict[x]["imagename"], "PiP", current if x == currentimageslot and mode == 12 else ""), (x, 12))))
					else:
						if self.imagedict[x]["imagename"] == _("Recovery Mode"):
							imageList.append(ChoiceEntryComponent(text=(slotRecov % (self.imagedict[x]["imagename"], current if x == currentimageslot else ""), (x, 1))))
						else:
							imageList.append(ChoiceEntryComponent(text=(slotSingle % (x, SystemInfo["canMultiBoot"][x]["slotType"], SystemInfo["canMultiBoot"][x]["slotname"], self.imagedict[x]["imagename"], current if x == currentimageslot else ""), (x, 1))))
			if imageList12:
				imageList += [" "] + imageList12
		else:
			imageList.append(ChoiceEntryComponent(text=((_("No images found")), "Waiter")))
		self["config"].setList(imageList)
		print("[MultiBootSelector] imageList X = %s" % imageList)
		if self.fromInit:
			self["config"].moveToIndex(next(iter([i for i, x in enumerate(imageList) if current in x[0][0]]), 0))
			self.fromInit = False
		self.updateKeys()

	def reboot(self):
		currentSelected = self["config"].getCurrent()
		slot = currentSelected[0][1][0]
		boxmode = currentSelected[0][1][1]
		if SystemInfo["canMode12"]:
			if "BOXMODE" in SystemInfo["canMultiBoot"][slot]['startupfile']:
				startupfile = join(self.tmp_dir, "%s_%s" % (SystemInfo["canMultiBoot"][slot]['startupfile'].rsplit('_', 1)[0], boxmode))
				copyfile(startupfile, join(self.tmp_dir, "STARTUP"))
			else:
				f = open(join(self.tmp_dir, SystemInfo["canMultiBoot"][slot]['startupfile']), "r").read()
				if boxmode == 12:
					f = f.replace("boxmode=1'", "boxmode=12'").replace("%s" % SystemInfo["canMode12"][0], "%s" % SystemInfo["canMode12"][1])
				open(join(self.tmp_dir, "STARTUP"), "w").write(f)
		else:
			copyfile(join(self.tmp_dir, SystemInfo["canMultiBoot"][slot]["startupfile"]), join(self.tmp_dir, "STARTUP"))
		if SystemInfo["HasMultibootMTD"]:
			with open('/dev/block/by-name/flag', 'wb') as f:
				f.write(struct.pack("B", int(slot)))
		self.cancel(QUIT_REBOOT)

	def deleteImage(self):
		currentSelected = self["config"].getCurrent()
		self.session.openWithCallback(self.deleteImageCallback, MessageBox, "%s:\n%s" % (_("Are you sure you want to delete image:"), currentSelected[0][0]), simple=True)

	def deleteImageCallback(self, answer):
		if answer:
			currentSelected = self["config"].getCurrent()
			slot = currentSelected[0][1][0]
			# print("[MultiBootSelector] delete slot = %s" % slot)
			if SystemInfo["HasKexecMultiboot"] and int(slot) < 4:
				# print("[MultiBootSelector] rm -rf delete slot = %s" % slot)
				Console().ePopen("rm -rf /boot/linuxrootfs%s" % slot)
			else:
				emptySlot(slot)
			self.getImagelist()

	def restoreImages(self):
		if self.deletedImagesExists:
			restoreSlots()
			self.getImagelist()

	def KexecMount(self):
		hdd = []
		usblist = list(SystemInfo["HasUsbhdd"].keys())
		print("[MultiBootSelector] usblist=", usblist)
		if not SystemInfo["VuUUIDSlot"]:
			with open("/proc/mounts", "r") as fd:
				xlines = fd.readlines()
				# print("[MultiBootSelector] xlines", xlines)
				for hddkey in range(len(usblist)):
					for xline in xlines:
						print("[MultiBootSelector] xline, usblist", xline, "   ", usblist[hddkey])
						if xline.find(usblist[hddkey]) != -1 and "ext4" in xline:
							index = xline.find(usblist[hddkey])
							print("[MultiBootSelector] key, line ", usblist[hddkey], "   ", xline)
							hdd.append(xline[index:index + 4])
						else:
							continue
							# print("[MultiBootSelector] key, not in line ", usblist[hddkey], "   ", xline)
			print("[MultiBootSelector] hdd available ", hdd)
			if not hdd:
				self.session.open(MessageBox, _("[MultiBootSelector][add USB STARTUP slots] - No EXT4 USB attached."), MessageBox.TYPE_INFO, timeout=10)
				self.cancel()
			else:
				usb = hdd[0][0:3]
				free = Harddisk(usb).Totalfree()
				print("[MultiBootSelector] USB free space", free)
				if free < 1024:
					des = str(round((float(free)), 2)) + _("MB")
					print("[MultiBootSelector][add USB STARTUP slot] limited free space", des)
					self.session.open(MessageBox, _("[MultiBootSelector][add USB STARTUP slots] - The USB (%s) only has %s free. At least 1024MB is required.") % (usb, des), MessageBox.TYPE_INFO, timeout=30)
					self.cancel()
					return
				Console().ePopen("/sbin/blkid | grep " + "/dev/" + hdd[0], self.KexecMountRet)

		else:
			hiKey = sorted(SystemInfo["canMultiBoot"].keys(), reverse=True)[0]
			self.session.openWithCallback(self.addSTARTUPs, MessageBox, _("Add 4 more Multiboot USB slots after slot %s ?") % hiKey, MessageBox.TYPE_YESNO, timeout=30)

	def addSTARTUPs(self, answer):
		hiKey = sorted(SystemInfo["canMultiBoot"].keys(), reverse=True)[0]
		UUIDkey = SystemInfo["VuUUIDSlot"][0]
		print(f"[MultiBootSelector]1 answer:{answer} hiKey:{hiKey} UUIDkey:{UUIDkey}")
		if answer is False:
			self.close()
		elif UBIMB:
			UUIDValue = SystemInfo["VuUUIDSlot"][2]
			for usbslot in range(hiKey + 1, hiKey + 5):
				STARTUP_usbslot = f"kernel=/dev/{MTDKERNEL} root={UUIDValue} rootsubdir=linuxrootfs{usbslot} rootfstype=ext4\n"
				# print(f"[MultiBootSelector]1 STARTUP_usbslot:{STARTUP_usbslot} UUIDkey:{UUIDkey} UUIDValue:{UUIDValue}")
				with open("/%s/STARTUP_%d" % (self.tmp_dir, usbslot), 'w') as f:
					f.write(STARTUP_usbslot)
			self.session.open(TryQuitMainloop, QUIT_RESTART)
		else:
			boxmodel = BOXTYPE[2:]
			for usbslot in range(hiKey + 1, hiKey + 5):
				STARTUP_usbslot = "kernel=%s/linuxrootfs%d/zImage root=%s rootsubdir=%s/linuxrootfs%d" % (boxmodel, usbslot, SystemInfo["VuUUIDSlot"][0], boxmodel, usbslot)  # /STARTUP_<n>
				if boxmodel in ("duo4k"):
					STARTUP_usbslot += " rootwait=40"
				elif boxmodel in ("duo4kse"):
					STARTUP_usbslot += " rootwait=35"
				with open("/%s/STARTUP_%d" % (self.tmp_dir, usbslot), 'w') as f:
					f.write(STARTUP_usbslot)
				print("[MultiBootSelector] STARTUP_%d --> %s, self.tmp_dir: %s" % (usbslot, STARTUP_usbslot, self.tmp_dir))
			self.session.open(TryQuitMainloop, QUIT_RESTART)

	def KexecMountRet(self, result=None, retval=None, extra_args=None):
		self.device_uuid = "UUID=" + result.split("UUID=")[1].split(" ")[0].replace('"', '')
		boxmodel = BOXTYPE[2:]
		# using UUID	 kernel=/linuxrootfs1/boot/zImage root=UUID="12c2025e-2969-4bd1-9e0c-da08b97d40ce" rootsubdir=linuxrootfs1
		# using dev = "kernel=/linuxrootfs4/zImage root=/dev/%s rootsubdir=linuxrootfs4" % hdd[0] 	# /STARTUP_4

		for usbslot in range(4, 8):
			STARTUP_usbslot = "kernel=%s/linuxrootfs%d/zImage root=%s rootsubdir=%s/linuxrootfs%d" % (boxmodel, usbslot, self.device_uuid, boxmodel, usbslot)  # /STARTUP_<n>
			if boxmodel in ("duo4k"):
				STARTUP_usbslot += " rootwait=40"
			elif boxmodel in ("duo4kse"):
				STARTUP_usbslot += " rootwait=35"
			print("[MultiBootSelector] STARTUP_%d --> %s, self.tmp_dir: %s" % (usbslot, STARTUP_usbslot, self.tmp_dir))
			with open("/%s/STARTUP_%d" % (self.tmp_dir, usbslot), 'w') as f:
				f.write(STARTUP_usbslot)
		SystemInfo["HasKexecUSB"] = True
		Console().ePopen("umount %s" % self.tmp_dir)
		if not ismount(self.tmp_dir):
			rmdir(self.tmp_dir)
		self.session.open(TryQuitMainloop, QUIT_RESTART)

	def cancel(self, value=None):
		Console().ePopen("umount %s" % self.tmp_dir)
		if not ismount(self.tmp_dir):
			rmdir(self.tmp_dir)
		if value == QUIT_REBOOT:
			self.session.open(TryQuitMainloop, QUIT_REBOOT)
		self.close()

	def keyUp(self):
		self["config"].instance.moveSelection(self["config"].instance.moveUp)
		self.updateKeys()

	def keyDown(self):
		self["config"].instance.moveSelection(self["config"].instance.moveDown)
		self.updateKeys()

	def updateKeys(self):
		if UBIMB and SystemInfo["MultiBootSlot"] == 0:
			return
		currentSelected = self["config"].getCurrent()
		if currentSelected[0][1] == "Queued":  # list not loaded yet so abort
			return
		slot = currentSelected[0][1][0]

		# green key
		if self.imagedict[slot]["imagename"] in (_("Deleted image"), _("Empty slot")):
			self["key_green"].text = ""
			self["rebootActions"].setEnabled(False)
		else:
			self["key_green"].text = _("Reboot")
			self["rebootActions"].setEnabled(True)

		# yellow key
		if SystemInfo["MultiBootSlot"] == slot or self.imagedict[slot]["imagename"] in (_("Empty slot"), _("Recovery Mode")):  # must not delete the current image or the recovery image and can't boot an empty slot
			self["key_yellow"].text = ""
			self["deleteActions"].setEnabled(False)
		else:
			self["key_yellow"].text = _("Delete")
			self["deleteActions"].setEnabled(True)
		for x in self.onChangedEntry:
			if callable(x):
				x()

	def createSummary(self):
		return MultiBootSelectorSummary


class ChkrootInit(Screen):
	skin = """
	<screen name="ChkrootInit" title="Chkroot MultiBoot Manager" position="center,center" size="900,600" resolution="1280,720">
		<widget name="description" position="0,0" size="e,e-50" font="Regular;20" />
		<widget source="key_red" render="Label" position="0,e-40" size="180,40" backgroundColor="key_red" conditional="key_red" font="Regular;20" foregroundColor="key_text" halign="center" valign="center">
			<convert type="ConditionalShowHide" />
		</widget>
		<widget source="key_green" render="Label" position="190,e-40" size="180,40" backgroundColor="key_green" conditional="key_green" font="Regular;20" foregroundColor="key_text" halign="center" valign="center">
			<convert type="ConditionalShowHide" />
		</widget>
		<widget source="key_help" render="Label" position="e-80,e-40" size="80,40" backgroundColor="key_back" conditional="key_help" font="Regular;20" foregroundColor="key_text" halign="center" valign="center">
			<convert type="ConditionalShowHide" />
		</widget>
	</screen>"""

	def __init__(self, session, *args):
		Screen.__init__(self, session)
		self.skinName = "ChkrootInit"
		self.setTitle(_("Chkroot MultiBoot Manager"))
		self["key_red"] = StaticText()
		self["key_green"] = StaticText()
		self["description"] = Label()
		greenAction = (self.UBIMBInit, _("Start the UBI Multiboot initialization")) if UBIMB else (self.rootInit, _("Start the Chkroot initialization"))
		self["actions"] = HelpableActionMap(self, ["OkCancelActions", "ColorActions"], {
			"ok": (self.close, _("Close the Chkroot MultiBoot Manager")),
			"cancel": (self.close, _("Close the Chkroot MultiBoot Manager")),
			"red": (self.disableChkroot, _("Disable the MultiBoot option")),
			"green": greenAction
		}, prio=-1, description=_("Chkroot Manager Actions"))
		self["key_red"].setText(_("Disable Chkroot"))
		self["key_green"].setText(_("Initialize"))
		self.descriptionSuffix = _("The %s %s will reboot after enabling.") % getBoxDisplayName()
		self["description"].setText("%s\n\n%s" % (_("Press GREEN to enable MultiBoot process"), self.descriptionSuffix))

	def rootInit(self):
		def rootInitCallback(*args, **kwargs):
			self.session.open(TryQuitMainloop, QUIT_REBOOT)

		self["description"].setText("%s\n\n%s" % (_("Chkroot MultiBoot Initialization in progress!"), self.descriptionSuffix))
		device = "/dev/block/by-name/others"
		mountpoint = "/boot"
		if BOXTYPE in ("dm900", "dm920"):  # mmcblk0p1 = 63488 mmcblk0p2 = 2031616 mmcblk0p3 = 13172703
			with open("/sys/block/mmcblk0/mmcblk0p1/size", "r") as fd:
				sectors = int(fd.read().strip())
			rootMap = [
				("mmcblk0p2", "linuxrootfs1"),
				("mmcblk0p2", "linuxrootfs1")
			]
			rootMap.append(("mmcblk0p3" if sectors < 2097152 else "mmcblk0p2", "linuxrootfs2"))
			rootMap.extend([
				("mmcblk0p3", "linuxrootfs3"),
				("mmcblk0p3", "linuxrootfs4"),
				("mmcblk0p3", "linuxrootfs5"),
				("mmcblk0p3", "linuxrootfs6")
			])
		else:
			rootMap = [
				(MTDROOTFS, "linuxrootfs1"),
				(MTDROOTFS, "linuxrootfs1"),
				(MTDROOTFS, "linuxrootfs2"),
				(MTDROOTFS, "linuxrootfs3"),
				(MTDROOTFS, "linuxrootfs4")
			]

		cmdList = [
			f"mkfs.vfat -F 32 -n CHKROOT {device}",
			f"mkdir -p {mountpoint}",
			f"mount {device} {mountpoint}",
		]

		for idx, (rootdev, subdir) in enumerate(rootMap):
			suffix = "" if idx == 0 else f"_{idx}"
			cmdList.append(f"echo 'kernel=/dev/{KERNEL} root=/dev/{rootdev} rootsubdir={subdir}' > {mountpoint}/STARTUP{suffix}")

		cmdList.append(f"umount {mountpoint}")
		print(f"[MultiBootSelector][ChkrootInit] cmdlist:{cmdList}")
		Console().eBatch(cmdList, rootInitCallback, debug=True)

	def disableChkroot(self):
		def disableChkrootCallback(answer):
			if answer:
				fileWriteLine("/etc/.disableChkroot", "disabled\n")
				self.close()

		self.session.openWithCallback(disableChkrootCallback, MessageBox, _("Permanently disable the MultiBoot option?"), simple=True)

	def UBIMBInit(self):
		print(f"[MultiBootSelector][UBIMBInit]")
		self.session.open(UBISlotManager)


class UBISlotManager(Setup):
	def __init__(self, session):
		def getGreenHelpText():
			return {
				ACTION_SELECT: _("Select Device for FORMAT!! & Creation of multiboot slots"),
				ACTION_CREATE: _("Create slots for the selected device")
			}.get(self.green, _("Help text uninitialized"))

		self.UBISlotManagerLocation = ConfigSelection(default=None, choices=[(_("Select Green to start slot creation"), _("Select Green to action"))])
		self.UBISlotManagerDevice = None
		Setup.__init__(self, session=session, setup="UBISlotManager")
		self.setTitle(_("Slot Manager"))
		self["fullUIActions"] = HelpableActionMap(self, ["CancelSaveActions"], {
			"cancel": (self.keyCancel, _("Cancel any changed settings and exit")),
			"close": (self.closeRecursive, _("Cancel any changed settings and exit all menus"))
		}, prio=0, description=_("Common Setup Actions"))  # Override the ConfigList "fullUIActions" action map so that we can control the GREEN button here.
		self["actions"] = HelpableActionMap(self, ["ColorActions"], {
			"green": (self.keyGreen, getGreenHelpText)
		}, prio=-1, description=_("Slot Manager Actions"))
		self.console = Console()
		self.deviceData = {}
		self.green = ACTION_SELECT

	def layoutFinished(self):
		Setup.layoutFinished(self)
		self.readDevices()

	def selectionChanged(self):
		Setup.selectionChanged(self)
		self.updateStatus()

	def changedEntry(self):
		Setup.changedEntry(self)
		self.updateStatus()

	def keySelect(self):
		if self.getCurrentItem() == self.UBISlotManagerLocation:
			self.showDeviceSelection()
		else:
			Setup.keySelect(self)

	def keyGreen(self):
		if self.UBISlotManagerDevice:
			self.createSlots()
		else:
			self.showDeviceSelection()

	def createSlots(self):
		print("[UBISlotManager] createSlots DEBUG")
		if not self.UBISlotManagerDevice:
			self.showDeviceSelection()
			return

		TARGET = self.deviceData[self.UBISlotManagerDevice][0].split("/")[-1]
		TARGET_DEVICE = f"/dev/{TARGET}"
		PART_SUFFIX = "p" if "mmcblk" in TARGET else ""
		PART = lambda n: f"{TARGET_DEVICE}{PART_SUFFIX}{n}"
		MOUNTPOINT = "/tmp/boot"
		print(f"[UBISlotManager] createSlots TARGET:{TARGET} TARGET_DEVICE:{TARGET_DEVICE} Mountpoint:{MOUNTPOINT}")
		if exists(TARGET_DEVICE):
			cmdlist = []
			cmdlist.append(f"for n in {TARGET_DEVICE}* ; do umount -lf $n > /dev/null 2>&1 ; done")
			cmdlist.append(f"/usr/sbin/sgdisk -z {TARGET_DEVICE}")
			cmdlist.append(f"/bin/touch /dev/nomount.{TARGET} > /dev/null 2>&1")
			cmdlist.append(f"/bin/touch /dev/nomount.{TARGET}1 > /dev/null 2>&1")
			cmdlist.append(f"/usr/sbin/parted --script {TARGET_DEVICE} mklabel gpt")
			cmdlist.append(f"/usr/sbin/partprobe {TARGET_DEVICE}")
			cmdlist.append(f"/usr/sbin/parted --script {TARGET_DEVICE} mkpart startup fat32 8192s 5MB")
			cmdlist.append(f"/usr/sbin/parted --script {TARGET_DEVICE} unit MiB mkpart rootfs ext4 5MiB -- -256MiB")
			cmdlist.append(f"/usr/sbin/parted --script {TARGET_DEVICE} unit MiB mkpart swap linux-swap -- -256MiB 100%")
			cmdlist.append(f"/usr/sbin/partprobe {TARGET_DEVICE}")
			cmdlist.append(f"/usr/sbin/mkfs.vfat -F 32 -n STARTUP {PART(1)}")
			# cmdlist.append(f"/sbin/mkfs.ext4 -O ^64bit,^extent,^flex_bg,^huge_file,^dir_nlink,^extra_isize,^metadata_csum -F -L rootfs {PART(2)}")
			cmdlist.append(f"/sbin/mkfs.ext4 -F -L rootfs {PART(2)}")
			cmdlist.append(f"/sbin/mkswap -L swap {PART(3)}")
			cmdlist.append(f"/bin/mkdir -p {MOUNTPOINT}")
			cmdlist.append(f"/bin/umount {MOUNTPOINT} > /dev/null 2>&1")
			cmdlist.append(f"/bin/mount {PART(1)} {MOUNTPOINT}")
			self.session.openWithCallback(self.formatDeviceCallback, ConsoleScreen, title=self.getTitle(), cmdlist=cmdlist)

	def formatDeviceCallback(self):
		def closeStartUpCallback(answer):
			if answer:
				self.session.open(TryQuitMainloop, QUIT_REBOOT)
		print("[UBISlotManager] formatDeviceCallback ")
		MOUNTPOINT = "/tmp/boot"
		mtdRootFs = MTDROOTFS
		mtdKernel = MTDKERNEL
		device = self.UBISlotManagerDevice
		PART_SUFFIX = "p" if "mmcblk" in device else ""
		uuidRootFS = fileReadLine(f"/dev/uuid/{device}{PART_SUFFIX}2", default=None)
		diskSize = self.partitionSizeGB(f"/dev/{device}")

		rootfsName = "rootfs"
		startupContent = f"kernel=/dev/{mtdKernel} ubi.mtd=rootfs root=ubi0:{rootfsName} flash=1 rootfstype=ubifs\n"

		with open(f"{MOUNTPOINT}/STARTUP", "w") as fd:
			fd.write(startupContent)
		with open(f"{MOUNTPOINT}/STARTUP_FLASH", "w") as fd:
			fd.write(startupContent)
		count = min(diskSize, 4)
		for i in range(1, count + 1):
			startupContent = f"kernel=/dev/{mtdKernel} root=UUID={uuidRootFS} rootsubdir=linuxrootfs{i} rootfstype=ext4\n"
			with open(f"{MOUNTPOINT}/STARTUP_{i}", "w") as fd:
				fd.write(startupContent)
		Console().ePopen(["/bin/sync"])
		Console().ePopen(["/bin/umount", "/bin/umount", f"{MOUNTPOINT}"])
		self.session.openWithCallback(closeStartUpCallback, MessageBox, _("%d slots have been created on the device.\n") % count, type=MessageBox.TYPE_INFO, close_on_any_key=True, timeout=10)

	def showDeviceSelection(self):
		def readDevicesCallback():
			choiceList = [(_("Cancel"), None)]
			for device_id, (path, name) in self.deviceData.items():
				choiceList.append(("%s (%s)" % (name, path), device_id))
			self.session.openWithCallback(self.deviceSelectionCallback, MessageBox, text=_("Select device and then Slot Creation"), list=choiceList, title=self.getTitle())
		self.readDevices(readDevicesCallback)

	def deviceSelectionCallback(self, selection):
		# print(f"[UBISlotManager] deviceSelectionCallback: entered selection:{selection}")
		if not selection:
			return

		print(f"[UBISlotManager] deviceSelectionCallback: selected device ID = {selection}")
		self.UBISlotManagerDevice = selection
		path = self.deviceData[selection][0]
		name = self.deviceData[selection][1]
		locations = self.UBISlotManagerLocation.getChoices()
		print(f"[UBISlotManager] deviceSelectionCallback1: locations:{locations} path:{path} name:{name}")
		if (path, path) not in locations:
			locations.append((path, path))
			# print(f"[UBISlotManager] deviceSelectionCallback: locations:{locations}")
			self.UBISlotManagerLocation.setChoices(default=None, choices=locations)
			self.UBISlotManagerLocation.value = path
		self.updateStatus("Selected device: %s" % self.deviceData[selection][1])

	def partitionSizeGB(self, dev):
		try:
			base = dev.replace("/dev/", "")
			path = f"/sys/class/block/{base}/size"
			path = path if exists(path) else f"/sys/block/{base}/size"
			with open(path) as fd:
				blocks = int(fd.read().strip())
				return ceil((blocks * 512) / (1024 * 1024 * 1024))
		except Exception as e:
			return 0

	def readDevices(self, callback=None):
		def readDevicesCallback(output=None, retVal=None, extraArgs=None):
			print("[UBISlotManager] readDevicesCallback DEBUG: retVal=%s, output='%s'." % (retVal, output))
			self.deviceData = {}
			for (name, hdd) in harddiskmanager.HDDList():
				MTDBLACK = SystemInfo["MTDBLACK"]
				MTDBLACK = "mmcblk0" if MTDBLACK.startswith("mmcblk0") else MTDBLACK
				print(f"[UBISlotManager] readDevices: MTDBLACK:{MTDBLACK} hddevpath:{hdd.dev_path} hddevpathnodev:{hdd.dev_path.replace("/dev/", "")[0:3]}")
				if MTDBLACK[0:3] == hdd.dev_path.replace("/dev/", "")[0:3] or hdd.dev_path.startswith("/dev/romblock"):
					continue
				deviceID = hdd.dev_path.split("/")[-1]
				self.deviceData[deviceID] = (hdd.dev_path, name)
				print("[UBISlotManager] readDevices: deviceID=%s, hdd.dev_path='%s' name = %s ." % (deviceID, hdd.dev_path, name))
			self.updateStatus()
			if callback and callable(callback):
				callback()

		self.console.ePopen(["/sbin/blkid", "/sbin/blkid"], callback=readDevicesCallback)

	def updateStatus(self, footnote=None):
		self.green = ACTION_CREATE if self.UBISlotManagerDevice else ACTION_SELECT
		self["key_green"].setText({
			ACTION_SELECT: _("Select Device"),
			ACTION_CREATE: _("Create Slots")
		}.get(self.green, _("Invalid")))


class MultiBootSelectorSummary(ScreenSummary):
	def __init__(self, session, parent):
		ScreenSummary.__init__(self, session, parent=parent)
		self.skinName = ["SetupSummary"]
		self["SetupTitle"] = StaticText(parent.title)
		self["SetupEntry"] = StaticText("")
		self["SetupValue"] = StaticText("")
		if self.addWatcher not in self.onShow:
			self.onShow.append(self.addWatcher)
		if self.removeWatcher not in self.onHide:
			self.onHide.append(self.removeWatcher)

	def addWatcher(self):
		if self.selectionChanged not in self.parent.onChangedEntry:
			self.parent.onChangedEntry.append(self.selectionChanged)
		self.selectionChanged()

	def removeWatcher(self):
		if self.selectionChanged in self.parent.onChangedEntry:
			self.parent.onChangedEntry.remove(self.selectionChanged)

	def selectionChanged(self):
		currentSelected = self.parent["config"].getCurrent()
		self["SetupEntry"].text = currentSelected[0][0]
		self["SetupValue"].text = ""  # not yet used
