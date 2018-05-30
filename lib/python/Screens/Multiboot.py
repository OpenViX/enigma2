from Screens.Screen import Screen
from Screens.Standby import TryQuitMainloop
from Screens.MessageBox import MessageBox
from boxbranding import getMachineBuild
from Components.Sources.StaticText import StaticText
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.SystemInfo import SystemInfo
from Tools.Multiboot import GetImagelist, GetCurrentImage, WriteStartup

class MultiBoot(Screen):

	skin = """
	<screen name="MultiBoot" position="center,center" size="700,400"  flags="wfNoBorder" title="ReBootGB" backgroundColor="transparent">
		<eLabel name="b" position="0,0" size="700,200" backgroundColor="#00ffffff" zPosition="-2" />
		<eLabel name="a" position="1,1" size="698,198" backgroundColor="#00000000" zPosition="-1" />
		<widget source="Title" render="Label" position="10,10" foregroundColor="#00ffffff" size="480,50" halign="center" font="Regular; 28" backgroundColor="#00000000" />
		<eLabel name="line" position="1,60" size="698,1" backgroundColor="#00ffffff" zPosition="1" />
		<widget source="config" render="Label" position="2,70" size="680,60" halign="center" font="Regular; 22" backgroundColor="#00000000" foregroundColor="#00ffffff" />
		<widget source="key_red" render="Label" position="35,162" size="75,30" noWrap="1" zPosition="1" valign="center" font="Regular; 20" halign="left" backgroundColor="#00000000" foregroundColor="#00ffffff" />
		<widget source="key_green" render="Label" position="150,162" size="75,30" noWrap="1" zPosition="1" valign="center" font="Regular; 20" halign="left" backgroundColor="#00000000" foregroundColor="#00ffffff" />
		<widget source="key_yellow" render="Label" position="250,162" size="150,30" noWrap="1" zPosition="1" valign="center" font="Regular; 20" halign="left" backgroundColor="#00000000" foregroundColor="#00ffffff" />
		<eLabel position="25,159" size="6,40" backgroundColor="#00e61700" />
		<eLabel position="125,159" size="6,40" backgroundColor="#0061e500" />
		<eLabel position="225,159" size="6,40" backgroundColor="#00e5b243" />
	</screen>
	"""

	def __init__(self, session, *args):
		Screen.__init__(self, session)
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("ReBoot"))
		self["config"] = StaticText(_("Select Image: STARTUP_1"))
		self.STARTUPslot = 0
		self.images = []
		self.mode = 0
		self.boxmode = 1
		self.STARTUPslot = GetCurrentImage()
		self.getImageList = None
		self.selection = 0
		self.slotno = SystemInfo["canMultiBoot"][1]
		self.startit()

		if not SystemInfo["canMode12"]:
			self["actions"] = ActionMap(["WizardActions", "SetupActions", "ColorActions"],
			{
				"left": self.left,
				"right": self.right,
				"red": self.cancel,
				"green": self.reboot,
				"cancel": self.cancel,
				"ok": self.reboot,
			}, -2)
		else:
			self["key_yellow"] = StaticText(_("ReBoot_mode12"))
			self["actions"] = ActionMap(["WizardActions", "SetupActions", "ColorActions"],
			{
				"left": self.left,
				"right": self.right,
				"red": self.cancel,
				"green": self.reboot,
				"yellow": self.reboot12,
				"cancel": self.cancel,
				"ok": self.reboot,
			}, -2)
		self.onLayoutFinish.append(self.layoutFinished)

	def layoutFinished(self):
		self.setTitle(self.title)

	def startit(self):
		self.getImageList = GetImagelist(self.startup0)

	def startup0(self, imagedict):
		self.images = imagedict
		self.title = "Current Image: STARTUP_" + str(GetCurrentImage())
		self.startup()

	def startup(self):
		self.slot = self.selection + 1
#		print "Multiboot OldImage %s NewFlash %s FlashType %s" % (self.STARTUPslot, self.selection, x)
		if self.images[self.slot]['imagename'] != _("Empty slot"):
			self["config"].setText(_("Reboot Image: STARTUP_%s: %s\n Use < > keys to select Image and Reboot.") %(self.slot, self.images[self.slot]['imagename']))
		else:
			self.right()


	def cancel(self):
		self.close()

	def left(self):
		self.selection = self.selection - 1
		if self.selection == -1:
			self.selection = self.slotno - 1
		self.startup()

	def right(self):
		self.selection = self.selection + 1
		if self.selection == self.slotno:
			self.selection = 0
		self.startup()

	def reboot(self):
		import shutil
		shutil.copyfile("/boot/STARTUP_%s" % self.slot, "/boot/STARTUP")
		self.session.open(TryQuitMainloop, 2)

	def reboot12(self):
		slot = self.slot
		model = getMachineBuild()
		self.mode = 1
		self.boxmode = 12
		startupFileContents = "boot emmcflash0.kernel%s 'brcm_cma=%s root=/dev/mmcblk0p%s rw rootwait %s_4.boxmode=%s'\n" % (slot, SystemInfo["canMode12"][self.mode], slot * 2 + SystemInfo["canMultiBoot"][0], model, self.boxmode)
		WriteStartup(startupFileContents, self.ReExit)

	def ReExit(self):
		self.session.open(TryQuitMainloop, 2)
