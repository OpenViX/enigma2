from os import mkdir, path
from shutil import copyfile
from boxbranding import getMachineBuild, getMachineMtdRoot
from Components.ActionMap import ActionMap
from Components.ChoiceList import ChoiceList, ChoiceEntryComponent
from Components.Console import Console
from Components.Label import Label
from Components.Sources.StaticText import StaticText
from Components.SystemInfo import SystemInfo
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Standby import TryQuitMainloop
from Tools.BoundFunction import boundFunction
from Tools.Directories import fileExists, fileCheck, pathExists, fileHas
from Tools.Multiboot import GetImagelist, GetCurrentImage, GetCurrentImageMode

class MultiBoot(Screen):

	skin = """
	<screen name="Multiboot Image Selector" position="center,center" size="750,900" flags="wfNoBorder" backgroundColor="transparent">
		<eLabel name="b" position="0,0" size="750,700" backgroundColor="#00ffffff" zPosition="-2" />
		<eLabel name="a" position="1,1" size="748,698" backgroundColor="#00000000" zPosition="-1" />
		<widget source="Title" render="Label" position="60,10" foregroundColor="#00ffffff" size="480,50" halign="left" font="Regular; 28" backgroundColor="#00000000" />
		<eLabel name="line" position="1,60" size="748,1" backgroundColor="#00ffffff" zPosition="1" />
		<eLabel name="line2" position="1,250" size="748,4" backgroundColor="#00ffffff" zPosition="1" />
		<widget name="config" position="2,280" size="730,380" halign="center" font="Regular; 22" backgroundColor="#00000000" foregroundColor="#00e5b243" />
		<widget source="description" render="Label" position="2,80" size="730,30" halign="center" font="Regular; 22" backgroundColor="#00000000" foregroundColor="#00ffffff" />
		<widget source="options" render="Label" position="2,130" size="730,60" halign="center" font="Regular; 22" backgroundColor="#00000000" foregroundColor="#00ffffff" />
		<widget source="key_red" render="Label" position="30,200" size="150,30" noWrap="1" zPosition="1" valign="center" font="Regular; 20" halign="left" backgroundColor="#00000000" foregroundColor="#00ffffff" />
		<widget source="key_green" render="Label" position="200,200" size="150,30" noWrap="1" zPosition="1" valign="center" font="Regular; 20" halign="left" backgroundColor="#00000000" foregroundColor="#00ffffff" />
		<eLabel position="20,200" size="6,40" backgroundColor="#00e61700" /> <!-- Should be a pixmap -->
		<eLabel position="190,200" size="6,40" backgroundColor="#0061e500" /> <!-- Should be a pixmap -->
	</screen>
	"""

	def __init__(self, session, *args):
		Screen.__init__(self, session)
		screentitle = _("Multiboot Image Selector")
		self["key_red"] = StaticText(_("Cancel"))
		if not SystemInfo["HasHiSi"] or SystemInfo["HasHiSi"] and pathExists('/dev/sda4'):
			self["description"] = StaticText(_("Use the cursor keys to select an installed image and then Reboot button."))
		else:
			self["description"] = StaticText(_("SDcard is not initialised for multiboot - Exit and use ViX MultiBoot Manager to initialise"))			
		self["options"] = StaticText(_(" "))
		self["key_green"] = StaticText(_("Reboot"))
		if SystemInfo["canMode12"]:
			self["options"] = StaticText(_("Mode 1 suppports Kodi, PiP may not work.\nMode 12 supports PiP, Kodi may not work."))
		self["config"] = ChoiceList(list=[ChoiceEntryComponent('',((_("Retrieving image slots - Please wait...")), "Queued"))])
		imagedict = []
		self.getImageList = None
		self.title = screentitle
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
		self.callLater(self.getBootOptions)

	def cancel(self, value=None):
		self.container = Console()
		self.container.ePopen('umount /tmp/startupmount', boundFunction(self.unmountCallback, value))

	def unmountCallback(self, value, data=None, retval=None, extra_args=None):
		self.container.killAll()
		if not path.ismount('/tmp/startupmount'):
			rmdir('/tmp/startupmount')
		self.close(value)

	def getBootOptions(self, value=None):
		self.container = Console()
		if path.isdir('/tmp/startupmount'):
			self.getImagesList()
		else:
			mkdir('/tmp/startupmount')
			self.container.ePopen('mount %s /tmp/startupmount' % SystemInfo["MBbootdevice"], self.getImagesList)
	def getImagesList(self, data=None, retval=None, extra_args=None):
		self.container.killAll()
		self.getImageList = GetImagelist(self.getImagelistCallback)

	def getImagelistCallback(self, imagedict):
		list = []
		mode = GetCurrentImageMode() or 0
		currentimageslot = GetCurrentImage()
		print "[MultiBoot Restart] reboot1 slot:\n", currentimageslot 
		if imagedict:
			for index, x in enumerate(sorted(imagedict.keys())):
				if imagedict[x]["imagename"] != _("Empty slot"):
					if not SystemInfo["canMode12"]:
						list.append(ChoiceEntryComponent('',((_("slot%s -%s (current image)") if x == currentimageslot else _("slot%s -%s")) % (x, imagedict[x]['imagename']), x)))
					else:
						list.insert(index, ChoiceEntryComponent('',((_("slot%s - %s mode 1 (current image)") if x == currentimageslot and mode != 12 else _("slot%s - %s mode 1")) % (x, imagedict[x]['imagename']), x)))
						list.append("                                 ")
						list.append("                                 ")
						list.append(ChoiceEntryComponent('',((_("slot%s - %s mode 12 (current image)") if x == currentimageslot and mode == 12 else _("slot%s - %s mode 12")) % (x, imagedict[x]['imagename']), x + 12)))
		else:
			list.append(ChoiceEntryComponent('',((_("No images found")), "Waiter")))
		self["config"].setList(list)

	def reboot(self):
		self.currentSelected = self["config"].l.getCurrentSelection()
		self.slot = self.currentSelected[0][1]
		if self.currentSelected[0][1] != "Queued":
			if self.slot == "Recovery":
				copyfile("/tmp/startupmount/STARTUP_RECOVERY", "/tmp/startupmount/STARTUP")
			elif self.slot == "Android":
				copyfile("/tmp/startupmount/STARTUP_ANDROID", "/tmp/startupmount/STARTUP")
			else:
				if self.slot < 12:
					startupfile = "/tmp/startupmount/%s" % SystemInfo["canMultiBoot"][self.slot]['startupfile'].replace("boxmode=12'", "boxmode=1'")
					copyfile(startupfile, "/tmp/startupmount/STARTUP")
				else:
					self.slot -=12
					startupfile = "/tmp/startupmount/%s" % SystemInfo["canMultiBoot"][self.slot]['startupfile']
					if "BOXMODE" not in startupfile:
						f = open('%s' %startupfile, 'r').read().replace("boxmode=1'", "boxmode=12'").replace("%s" %SystemInfo["canMode12"][0], "%s" %SystemInfo["canMode12"][1])
						open('/tmp/startupmount/STARTUP', 'w').write(f)
						self.session.open(TryQuitMainloop, 2)
					else:
						copyfile(startupfile, "/tmp/startupmount/STARTUP")
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
