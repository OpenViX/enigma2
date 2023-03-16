from time import sleep
from boxbranding import getBoxType, getMachineMtdKernel, getMachineMtdRoot
from Components.Console import Console
from Components.Label import Label
from Components.Sources.StaticText import StaticText
from Screens.Screen import Screen
from Tools.Directories import fileExists, pathExists

STARTUP = "kernel=/zImage root=/dev/%s rootsubdir=linuxrootfs0" % getMachineMtdRoot()					# /STARTUP
STARTUP_RECOVERY = "kernel=/zImage root=/dev/%s rootsubdir=linuxrootfs0" % getMachineMtdRoot() 			# /STARTUP_RECOVERY
STARTUP_1 = "kernel=/linuxrootfs1/zImage root=/dev/%s rootsubdir=linuxrootfs1" % getMachineMtdRoot() 	# /STARTUP_1
STARTUP_2 = "kernel=/linuxrootfs2/zImage root=/dev/%s rootsubdir=linuxrootfs2" % getMachineMtdRoot() 	# /STARTUP_2
STARTUP_3 = "kernel=/linuxrootfs3/zImage root=/dev/%s rootsubdir=linuxrootfs3" % getMachineMtdRoot() 	# /STARTUP_3

class VuWizard(Screen):

	skin = """
	<screen name="VuWizard" position="center,center" size="750,700" flags="wfNoBorder" backgroundColor="transparent">
		<eLabel name="b" position="0,0" size="750,700" backgroundColor="#00ffffff" zPosition="-2" />
		<eLabel name="a" position="1,1" size="748,698" backgroundColor="#00000000" zPosition="-1" />
		<widget source="Title" render="Label" position="center,14" foregroundColor="#00ffffff" size="e-10%,35" halign="left" valign="center" font="Regular; 28" backgroundColor="#00000000" />
		<eLabel name="line" position="1,60" size="748,1" backgroundColor="#00ffffff" zPosition="1" />
		<widget source="description" render="Label" position="2,80" size="730,300" halign="center" font="Regular; 22" backgroundColor="#00000000" foregroundColor="#00ffffff" />
		<widget source="action" render="Label" position="200,300" size="400,150" noWrap="1" zPosition="1" valign="center" font="Regular; 24" halign="left" backgroundColor="#00000000" foregroundColor="#00ffffff" />
	</screen>
	"""

	def __init__(self, session):
		self.session = session
		Screen.__init__(self, session)
		self.title = _("Vu+ MultiBoot Initialisation")
		self["description"] = Label(_("Enabling MultiBoot.\nNote:- restoring eMMC slots takes upto 5 minutes per slot.\n Receiver will then reboot to setup Wizard.\n In Wizard finalise Recovery image, or exit and \n - select restored eMMC image with MultiBootSelector.   \n or \n - flash new image into multiboot slot via ImageManager."))
		self["action"] = StaticText("Enabling MultiBoot")
					
		if fileExists("/STARTUP_RECOVERY") or fileExists("/boot/STARTUP_RECOVERY"):
			self.close	
		else:
			self.Console = Console()
			with open("/STARTUP", 'w') as f:
				f.write(STARTUP)
			with open("/STARTUP_RECOVERY", 'w') as f:
				f.write(STARTUP_RECOVERY)
			with open("/STARTUP_1", 'w') as f:
				f.write(STARTUP_1)
			with open("/STARTUP_2", 'w') as f:
				f.write(STARTUP_2)
			with open("/STARTUP_3", 'w') as f:
				f.write(STARTUP_3)
			cmdlist = []
			cmdlist.append("dd if=/dev/%s of=/zImage" % getMachineMtdKernel())					# backup old kernel
			cmdlist.append("dd if=/usr/bin/kernel_auto.bin of=/dev/%s" % getMachineMtdKernel())	# create new kernel
			cmdlist.append("mv /usr/bin/STARTUP.cpio.gz /STARTUP.cpio.gz")						# copy userroot routine
			self.Console.eBatch(cmdlist, self.RootInitEnd, debug=False)

	def RootInitEnd(self, *args, **kwargs):
		cmdlist = []
		slotlist = []	
		for eMMCslot in range(1,4):		
			if pathExists("/media/hdd/%s/linuxrootfs%s" % (getBoxType(), eMMCslot)):
				slotlist.append(eMMCslot)		
				self["action"].setText(_("Restoring MultiBoot Slots %s." % slotlist))
				cmdlist.append("cp -R /media/hdd/%s/linuxrootfs%s . /" % (getBoxType(), eMMCslot))
		if cmdlist:
			self.Console.eBatch(cmdlist, self.reBoot, debug=False)
		else:
			sleep(5)
			self.reBoot()					

	def reBoot(self, *args, **kwargs):
		self.Console.ePopen("killall -9 enigma2 && init 6")

