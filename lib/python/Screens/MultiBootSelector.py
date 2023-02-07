from enigma import getDesktop
from os import mkdir, path, rmdir, system
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
from Screens.Screen import Screen
from Screens.Standby import QUIT_REBOOT, TryQuitMainloop
from Tools.BoundFunction import boundFunction
from Tools.Directories import copyfile, fileExists, pathExists
from Tools.Multiboot import emptySlot, GetImagelist, GetCurrentImageMode, restoreSlots


class MultiBootSelector(Screen, HelpableScreen):
	skin = ["""
	<screen title="MultiBoot Image Selector" position="center,center" size="%d,%d">
		<widget name="config" position="%d,%d" size="%d,%d" font="Regular;%d" itemHeight="%d" scrollbarMode="showOnDemand" />
		<widget source="description" render="Label" position="%d,e-%d" size="%d,%d" font="Regular;%d" />
		<widget source="key_red" render="Label" position="%d,e-%d" size="%d,%d" backgroundColor="key_red" font="Regular;%d" foregroundColor="key_text" halign="center" noWrap="1" valign="center" />
		<widget source="key_green" render="Label" position="%d,e-%d" size="%d,%d" backgroundColor="key_green" font="Regular;%d" foregroundColor="key_text" halign="center" noWrap="1" valign="center" />
		<widget source="key_yellow" render="Label" position="%d,e-%d" size="%d,%d" backgroundColor="key_yellow" font="Regular;%d" foregroundColor="key_text" halign="center" noWrap="1" valign="center" />
		<widget source="key_blue" render="Label" position="%d,e-%d" size="%d,%d" backgroundColor="key_blue" font="Regular;%d" foregroundColor="key_text" halign="center" noWrap="1" valign="center" />
	</screen>""",
		900, 460,
		10, 10, 880, 306, 24, 34,
		10, 125, 880, 60, 22,
		10, 50, 140, 40, 20,
		160, 50, 140, 40, 20,
		310, 50, 140, 40, 20,
		460, 50, 140, 40, 20
	]

	def __init__(self, session, *args):
		Screen.__init__(self, session, mandatoryWidgets=["key_yellow", "key_blue"])
		HelpableScreen.__init__(self)
		Screen.setTitle(self, _("MultiBoot Image Selector"))
		self.skinName = ["MultiBootSelector", "Setup"]
		self.tmp_dir = None
		canAddUsbMultiboot = SystemInfo["HasKexecMultiboot"] and not SystemInfo["HasKexecUSB"]
		self["config"] = ChoiceList(list=[ChoiceEntryComponent("", ((_("Retrieving image slots - Please wait...")), "Queued"))])
		self["description"] = StaticText(_("Press GREEN (Reboot) to switch images, YELLOW (Delete) to erase an image or BLUE (Restore) to restore all deleted images."))
		self["key_red"] = StaticText(_("Add Multiboot USB") if canAddUsbMultiboot else _("Cancel"))  
		self["key_green"] = StaticText(_("Reboot"))
		self["key_yellow"] = StaticText(_("Delete"))
		self["key_blue"] = StaticText(_("Restore"))
		self["actions"] = HelpableActionMap(self, ["OkCancelActions", "ColorActions", "DirectionActions", "KeyboardInputActions", "MenuActions"], {
			"red": (self.KexecMount if canAddUsbMultiboot else self.cancel, _("Create USB Multiboot") if canAddUsbMultiboot else _("Cancel the image selection and exit")),
			"green": (self.reboot, _("Select the highlighted image and reboot")),
			"yellow": (self.deleteImage, _("Select the highlighted image and delete")),
			"blue": (self.restoreImages, _("Select to restore all deleted images")),
			"ok": (self.reboot, _("Select the highlighted image and reboot")),
			"cancel": (self.cancel, _("Cancel the image selection and exit")),
			"up": (self.keyUp, _("Move up a line")),
			"down": (self.keyDown, _("Move down a line")),
			"left": (self.keyUp, _("Move up a line")),
			"right": (self.keyDown, _("Move down a line")),
			"menu": (boundFunction(self.cancel, True), _("Cancel the image selection and exit all menus"))
		}, -1, description=_("MultiBootSelector Actions"))
		self.imagedict = []
		self.tmp_dir = tempfile.mkdtemp(prefix="MultibootSelector")
		Console().ePopen("mount %s %s" % (SystemInfo["MBbootdevice"], self.tmp_dir))
		self.callLater(self.getImagelist)

	def getImagelist(self):
		self.imagedict = GetImagelist()
		list = []
		self.deletedImagesExists = False
		currentimageslot = SystemInfo["MultiBootSlot"]
		mode = GetCurrentImageMode() or 0
		print("[MultiBootSelector] reboot0 slot:", currentimageslot)
		current = "  %s" % _("(Current)")
		slotSingle = _("Slot%s %s: %s%s")
		slotMulti = _("Slot%s %s: %s - %s mode%s")
		if self.imagedict:
			indextot = 0
			for index, x in enumerate(sorted(self.imagedict.keys())):
				if self.imagedict[x]["imagename"] == _("Deleted image"):
					self.deletedImagesExists = True
				if SystemInfo["canMode12"]:
					if self.imagedict[x]["imagename"] == _("Empty slot"):
						list.insert(index, ChoiceEntryComponent("", (slotSingle % (x, SystemInfo["canMultiBoot"][x]["slotname"], self.imagedict[x]["imagename"], current if x == currentimageslot else ""), (x, 1))))					
					else:
						list.insert(index, ChoiceEntryComponent("", (slotMulti % (x, SystemInfo["canMultiBoot"][x]["slotname"], self.imagedict[x]["imagename"], "Kodi", current if x == currentimageslot and mode != 12 else ""), (x, 1))))
						list.append(ChoiceEntryComponent("", (slotMulti % (x, SystemInfo["canMultiBoot"][x]["slotname"], self.imagedict[x]["imagename"], "PiP", current if x == currentimageslot and mode == 12 else ""), (x, 12))))
					indextot = index + 1
				elif self.imagedict[x]["imagename"] != _("Empty slot"):
					list.append(ChoiceEntryComponent("", (slotSingle % (x, SystemInfo["canMultiBoot"][x]["slotname"], self.imagedict[x]["imagename"], current if x == currentimageslot else ""), (x, 1))))
			if SystemInfo["canMode12"]:
				list.insert(indextot, " ")
		else:
			list.append(ChoiceEntryComponent("", ((_("No images found")), "Waiter")))
		self["config"].setList(list)
		print("[MultiBootSelector] list X = %s" % list)

	def reboot(self):
		self.currentSelected = self["config"].l.getCurrentSelection()
		self.slotx = self.slot = self.currentSelected[0][1][0]
		if self.imagedict[self.slotx]["imagename"] == _("Deleted image")  or self.imagedict[self.slotx]["imagename"] == _("Empty slot"):
			self.session.open(MessageBox, _("Cannot reboot to deleted image"), MessageBox.TYPE_ERROR, timeout=3)
			self.getImagelist()
		elif self.currentSelected[0][1] != "Queued":
			slot = self.currentSelected[0][1][0]
			boxmode = self.currentSelected[0][1][1]
			# print("[MultiBootSelector] reboot1 reboot slot = %s, " % slot)
			# print("[MultiBootSelector] reboot2 reboot boxmode = %s, " % boxmode)
			# print("[MultiBootSelector] reboot3 slotinfo = %s" % SystemInfo["canMultiBoot"])
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
		self.currentSelected = self["config"].l.getCurrentSelection()
		self.slot = self.currentSelected[0][1][0]		
		if SystemInfo["MultiBootSlot"] != self.currentSelected[0][1] and self.imagedict[self.slot]["imagename"] != _("Empty slot"):
			self.session.openWithCallback(self.deleteImageCallback, MessageBox, "%s:\n%s" % (_("Are you sure you want to delete image:"), self.currentSelected[0][0]), simple=True)
		else:
			self.session.open(MessageBox, _("Cannot delete current image"), MessageBox.TYPE_ERROR, timeout=3)
			self.getImagelist()

	def deleteImageCallback(self, answer):
		if answer:
			self.currentSelected = self["config"].l.getCurrentSelection()
			self.slot = self.currentSelected[0][1][0]
			print("[MultiBootSelector] delete self.slot = %s" % self.slot)
			emptySlot(self.slot)
		self.getImagelist()

	def restoreImages(self):
		if self.deletedImagesExists:
			restoreSlots()
		self.getImagelist()


	def KexecMount(self):
		hdd = []
		usblist = list(SystemInfo["HasUsbhdd"].keys())
		print("[MultiBootSelector] usblist=", usblist)
		with open("/proc/mounts", "r") as fd:
			xlines = fd.readlines()
#			print("[MultiBootSelector] xlines", xlines)			
			for hddkey in range(len(usblist)):
				for xline in xlines:
					print("[MultiBootSelector] xline, usblist", xline, "   ", usblist[hddkey])			
					if xline.find(usblist[hddkey]) != -1 and "ext4" in xline:
						index = xline.find(usblist[hddkey])
						print("[MultiBootSelector] key, line ", usblist[hddkey], "   ", xline)		
						hdd.append(xline[index:index+4])
					else:
						continue
#						print("[MultiBootSelector] key, not in line ", usblist[hddkey], "   ", xline)											 
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
	

	def KexecMountRet(self, result=None, retval=None, extra_args=None):
		self.device_uuid = "UUID=" + result.split("UUID=")[1].split(" ")[0].replace('"', '')
		usb = result.split(":")[0]
		print("[MultiBootSelector] RESULT, retval", result, "   ", retval)	
		print("[MultiBootSelector] uuidPath ", self.device_uuid)
# 			using UUID	 kernel=/linuxrootfs1/boot/zImage root=UUID="12c2025e-2969-4bd1-9e0c-da08b97d40ce" rootsubdir=linuxrootfs1
#			STARTUP_4 = "kernel=/linuxrootfs4/zImage root=/dev/%s rootsubdir=linuxrootfs4" % hdd[0] 	# /STARTUP_4
#			STARTUP_5 = "kernel=/linuxrootfs5/zImage root=/dev/%s rootsubdir=linuxrootfs5" % hdd[0] 	# /STARTUP_5
#			STARTUP_6 = "kernel=/linuxrootfs6/zImage root=/dev/%s rootsubdir=linuxrootfs6" % hdd[0] 	# /STARTUP_6
#			STARTUP_7 = "kernel=/linuxrootfs7/zImage root=/dev/%s rootsubdir=linuxrootfs7" % hdd[0] 	# /STARTUP_7
		STARTUP_4 = "kernel=/linuxrootfs4/zImage root=%s rootsubdir=linuxrootfs4" % self.device_uuid 	# /STARTUP_4
		STARTUP_5 = "kernel=/linuxrootfs5/zImage root=%s rootsubdir=linuxrootfs5" % self.device_uuid 	# /STARTUP_5
		STARTUP_6 = "kernel=/linuxrootfs6/zImage root=%s rootsubdir=linuxrootfs6" % self.device_uuid 	# /STARTUP_6
		STARTUP_7 = "kernel=/linuxrootfs7/zImage root=%s rootsubdir=linuxrootfs7" % self.device_uuid 	# /STARTUP_7
		print("[MultiBootSelector] STARTUP_4 , self.tmp_dir ", STARTUP_4, "    ", self.tmp_dir)											
		with open("/%s/STARTUP_4" % self.tmp_dir, 'w') as f:
			f.write(STARTUP_4)
		with open("/%s/STARTUP_5" % self.tmp_dir, 'w') as f:
			f.write(STARTUP_5)
		with open("/%s/STARTUP_6" % self.tmp_dir, 'w') as f:
			f.write(STARTUP_6)
		with open("/%s/STARTUP_7" % self.tmp_dir, 'w') as f:
			f.write(STARTUP_7)
		SystemInfo["HasKexecUSB"] = True							
		self.session.open(MessageBox, _("[MultiBootSelector][Vu USB STARTUP] - created STARTUP slots for %s." % usb), MessageBox.TYPE_INFO, timeout=10)												
		self.cancel(QUIT_REBOOT)					
						
	def cancel(self, value=None):
		Console().ePopen("umount %s" % self.tmp_dir)
		if not path.ismount(self.tmp_dir):
			rmdir(self.tmp_dir)
		if value == QUIT_REBOOT:
			self.session.open(TryQuitMainloop, QUIT_REBOOT)
		else:
			self.close(value)

	def keyUp(self):
		self["config"].instance.moveSelection(self["config"].instance.moveUp)

	def keyDown(self):
		self["config"].instance.moveSelection(self["config"].instance.moveDown)
