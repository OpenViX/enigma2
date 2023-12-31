from os import path, rmdir
import tempfile
import struct

from Components.ActionMap import HelpableActionMap
from Components.ChoiceList import ChoiceEntryComponent, ChoiceList
from Components.Console import Console
from Components.Harddisk import Harddisk
from Components.Sources.StaticText import StaticText
from Components.SystemInfo import SystemInfo
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen, ScreenSummary
from Screens.Standby import QUIT_REBOOT, QUIT_RESTART, TryQuitMainloop
from Tools.BoundFunction import boundFunction
from Tools.Directories import copyfile
from Tools.Multiboot import emptySlot, GetImagelist, GetCurrentImageMode, restoreSlots


class MultiBootSelector(Screen, HelpableScreen):
	def __init__(self, session, *args):
		Screen.__init__(self, session, mandatoryWidgets=["key_yellow", "key_blue"])
		HelpableScreen.__init__(self)
		self.title = _("MultiBoot Image Selector")
		self.skinName = ["MultiBootSelector", "Setup"]
		self.onChangedEntry = []
		self.tmp_dir = None
		self.fromInit = True
		usbIn = SystemInfo["HasUsbhdd"].keys() and SystemInfo["HasKexecMultiboot"]
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
				startupfile = path.join(self.tmp_dir, "%s_%s" % (SystemInfo["canMultiBoot"][slot]['startupfile'].rsplit('_', 1)[0], boxmode))
				copyfile(startupfile, path.join(self.tmp_dir, "STARTUP"))
			else:
				f = open(path.join(self.tmp_dir, SystemInfo["canMultiBoot"][slot]['startupfile']), "r").read()
				if boxmode == 12:
					f = f.replace("boxmode=1'", "boxmode=12'").replace("%s" % SystemInfo["canMode12"][0], "%s" % SystemInfo["canMode12"][1])
				open(path.join(self.tmp_dir, "STARTUP"), "w").write(f)
		else:
			copyfile(path.join(self.tmp_dir, SystemInfo["canMultiBoot"][slot]["startupfile"]), path.join(self.tmp_dir, "STARTUP"))
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
			self.session.openWithCallback(self.addSTARTUPs, MessageBox, _("Add 4 more Vu+ Multiboot USB slots after slot %s ?") % hiKey, MessageBox.TYPE_YESNO, timeout=30)

	def addSTARTUPs(self, answer):
		hiKey = sorted(SystemInfo["canMultiBoot"].keys(), reverse=True)[0]
		hiUUIDkey = SystemInfo["VuUUIDSlot"][1]
		print("[MultiBootSelector]1 answer, hiKey,  hiUUIDkey", answer, "   ", hiKey, "   ", hiUUIDkey)
		if answer is False:
			self.close()
		else:
			boxmodel = SystemInfo["boxtype"][2:]
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
		boxmodel = SystemInfo["boxtype"][2:]
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
		self.session.open(TryQuitMainloop, QUIT_RESTART)

	def cancel(self, value=None):
		Console().ePopen("umount %s" % self.tmp_dir)
		if not path.ismount(self.tmp_dir):
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
