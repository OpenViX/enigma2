from enigma import getDesktop
from os import mkdir, path, rmdir
import tempfile
import struct

from Components.ActionMap import HelpableActionMap
from Components.ChoiceList import ChoiceEntryComponent, ChoiceList
from Components.Console import Console
from Components.Sources.StaticText import StaticText
from Components.SystemInfo import SystemInfo
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Standby import QUIT_REBOOT, TryQuitMainloop
from Tools.BoundFunction import boundFunction
from Tools.Directories import copyfile, pathExists
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
		self["config"] = ChoiceList(list=[ChoiceEntryComponent("", ((_("Retrieving image slots - Please wait...")), "Queued"))])
		self["description"] = StaticText(_("Press GREEN (Reboot) to switch images, YELLOW (Delete) to erase an image or BLUE (Restore) to restore all deleted images."))
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Reboot"))
		self["key_yellow"] = StaticText(_("Delete"))
		self["key_blue"] = StaticText(_("Restore"))
		self["actions"] = HelpableActionMap(self, ["OkCancelActions", "ColorActions", "DirectionActions", "KeyboardInputActions", "MenuActions"], {
			"red": (boundFunction(self.close, None), _("Cancel the image selection and exit")),
			"green": (self.reboot, _("Select the highlighted image and reboot")),
			"yellow": (self.deleteImage, _("Select the highlighted image and delete")),
			"blue": (self.restoreImages, _("Select to restore all deleted images")),
			"ok": (self.reboot, _("Select the highlighted image and reboot")),
			"cancel": (boundFunction(self.close, None), _("Cancel the image selection and exit")),
			"up": (self.keyUp, _("Move up a line")),
			"down": (self.keyDown, _("Move down a line")),
			"left": (self.keyUp, _("Move up a line")),
			"right": (self.keyDown, _("Move down a line")),
			"menu": (boundFunction(self.close, True), _("Cancel the image selection and exit all menus"))
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
