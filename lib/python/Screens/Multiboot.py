from Screens.Screen import Screen
from Screens.Standby import TryQuitMainloop
from Screens.MessageBox import MessageBox
from boxbranding import getMachineBuild
from Components.Sources.StaticText import StaticText
from Components.ActionMap import ActionMap
from Components.ChoiceList import ChoiceList, ChoiceEntryComponent
from Components.Label import Label
from Components.SystemInfo import SystemInfo
from Tools.BoundFunction import boundFunction
from Tools.Multiboot import GetImagelist, GetCurrentImage

class MultiBoot(Screen):

	skin = """
	<screen name="MultiBoot" position="center,center" size="750,900" flags="wfNoBorder" backgroundColor="transparent">
		<eLabel name="b" position="0,0" size="750,500" backgroundColor="#00ffffff" zPosition="-2" />
		<eLabel name="a" position="1,1" size="748,498" backgroundColor="#00000000" zPosition="-1" />
		<widget source="Title" render="Label" position="60,10" foregroundColor="#00ffffff" size="480,50" halign="left" font="Regular; 28" backgroundColor="#00000000" />
		<eLabel name="line" position="1,60" size="748,1" backgroundColor="#00ffffff" zPosition="1" />
		<eLabel name="line2" position="1,250" size="748,4" backgroundColor="#00ffffff" zPosition="1" />
		<widget name="config" position="2,280" size="730,190" halign="center" font="Regular; 22" backgroundColor="#00000000" foregroundColor="#00e5b243" />
		<widget source="labe14" render="Label" position="2,80" size="730,30" halign="center" font="Regular; 22" backgroundColor="#00000000" foregroundColor="#00ffffff" />
		<widget source="labe15" render="Label" position="2,130" size="730,60" halign="center" font="Regular; 22" backgroundColor="#00000000" foregroundColor="#00ffffff" />
		<widget source="key_red" render="Label" position="30,200" size="150,30" noWrap="1" zPosition="1" valign="center" font="Regular; 20" halign="left" backgroundColor="#00000000" foregroundColor="#00ffffff" />
		<widget source="key_green" render="Label" position="200,200" size="150,30" noWrap="1" zPosition="1" valign="center" font="Regular; 20" halign="left" backgroundColor="#00000000" foregroundColor="#00ffffff" />
		<widget source="key_yellow" render="Label" position="370,200" size="150,30" noWrap="1" zPosition="1" valign="center" font="Regular; 20" halign="left" backgroundColor="#00000000" foregroundColor="#00ffffff" />
		<eLabel position="20,200" size="6,40" backgroundColor="#00e61700" /> <!-- Should be a pixmap -->
		<eLabel position="190,200" size="6,40" backgroundColor="#0061e500" /> <!-- Should be a pixmap -->
		<eLabel position="360,200" size="6,40" backgroundColor="#00e5b243" /> <!-- Should be a pixmap -->
	</screen>
	"""

	def __init__(self, session, *args):
		Screen.__init__(self, session)
		self.skinName = "MultiBoot"
		screentitle = _("Multiboot Image Restart")
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Reboot mode 1"))
		self["labe14"] = StaticText(_("Use the cursor keys to select an installed image and then Reboot button."))
		self["labe15"] = StaticText(_("Mode 1 suppports Kodi, PiP may not work.\nMode 12 supports PiP, Kodi may not work."))
		self["config"] = ChoiceList(list=[ChoiceEntryComponent('',((_("Retrieving image slots - Please wait...")), "Queued"))])
		imagedict = []
		self.getImageList = None
		self.title = screentitle
		self.startit()

		if not SystemInfo["canMode12"]:
			self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions", "KeyboardInputActions", "MenuActions"],
			{
				"red": boundFunction(self.close, None),
				"green": self.reboot,
				"ok": self.reboot,
				"cancel": boundFunction(self.close, None),
				"up": self.keyUp,
				"down": self.keyDown,
				"left": self.keyLeft,
				"right": self.keyRight,
				"upRepeated": self.keyUp,
				"downRepeated": self.keyDown,
				"leftRepeated": self.keyLeft,
				"rightRepeated": self.keyRight,
				"menu": boundFunction(self.close, True),
			}, -1)
		else:
			self["key_yellow"] = StaticText(_("Reboot mode 12"))
			self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions", "KeyboardInputActions", "MenuActions"],
			{
				"red": boundFunction(self.close, None),
				"green": self.reboot,
				"yellow": self.reboot12,
				"ok": self.reboot,
				"cancel": boundFunction(self.close, None),
				"up": self.keyUp,
				"down": self.keyDown,
				"left": self.keyLeft,
				"right": self.keyRight,
				"upRepeated": self.keyUp,
				"downRepeated": self.keyDown,
				"leftRepeated": self.keyLeft,
				"rightRepeated": self.keyRight,
				"menu": boundFunction(self.close, True),
			}, -1)
		self.onLayoutFinish.append(self.layoutFinished)

	def layoutFinished(self):
		self.setTitle(self.title)

	def startit(self):
		self.getImageList = GetImagelist(self.ImageList)

	def ImageList(self, imagedict):
		list = []
		currentimageslot = GetCurrentImage()
		for x in sorted(imagedict.keys()):
			if imagedict[x]["imagename"] != _("Empty slot"):
				list.append(ChoiceEntryComponent('',((_("slot%s - %s (current image)") if x == currentimageslot else _("slot%s - %s ")) % (x, imagedict[x]['imagename']), x)))
		self["config"].setList(list)

	def reboot(self):
		self.currentSelected = self["config"].l.getCurrentSelection()
		if self.currentSelected[0][1] != "Queued":
			slot = self.currentSelected[0][1]
			import shutil
			shutil.copyfile("/boot/STARTUP_%s" % slot, "/boot/STARTUP")
			self.session.open(TryQuitMainloop, 2)

	def reboot12(self):
		self.currentSelected = self["config"].l.getCurrentSelection()
		if self.currentSelected[0][1] != "Queued":
			slot = self.currentSelected[0][1]
			model = getMachineBuild()
			startupFileContents = "boot emmcflash0.kernel%s 'brcm_cma=%s root=/dev/mmcblk0p%s rw rootwait %s_4.boxmode=12'\n" % (slot, SystemInfo["canMode12"][1], slot * 2 + SystemInfo["canMultiBoot"][0], model)
			open('/boot/STARTUP', 'w').write(startupFileContents)
			self.session.open(TryQuitMainloop, 2)

	def selectionChanged(self):
		currentSelected = self["config"].l.getCurrentSelection()

	def keyLeft(self):
		self["config"].instance.moveSelection(self["config"].instance.moveUp)
		self.selectionChanged()

	def keyRight(self):
		self["config"].instance.moveSelection(self["config"].instance.moveDown)
		self.selectionChanged()

	def keyUp(self):
		self["config"].instance.moveSelection(self["config"].instance.moveUp)
		self.selectionChanged()

	def keyDown(self):
		self["config"].instance.moveSelection(self["config"].instance.moveDown)
		self.selectionChanged()
