from __future__ import print_function, absolute_import

from boxbranding import getMachineBuild
from Components.ActionMap import ActionMap
from Components.ChoiceList import ChoiceList, ChoiceEntryComponent
from Components.config import config
from Components.Label import Label
from Components.Sources.StaticText import StaticText
from Components.SystemInfo import SystemInfo
from Screens.Console import Console
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.Standby import TryQuitMainloop
from Tools.BoundFunction import boundFunction

class H9SDmanager(Screen):

	skin = """
	<screen name="H9SDmanager" position="center,center" size="750,700" flags="wfNoBorder" backgroundColor="transparent">
		<eLabel name="b" position="0,0" size="750,700" backgroundColor="#00ffffff" zPosition="-2" />
		<eLabel name="a" position="1,1" size="748,698" backgroundColor="#00000000" zPosition="-1" />
		<widget source="Title" render="Label" position="60,10" foregroundColor="#00ffffff" size="480,50" halign="left" font="Regular; 28" backgroundColor="#00000000" />
		<eLabel name="line" position="1,60" size="748,1" backgroundColor="#00ffffff" zPosition="1" />
		<eLabel name="line2" position="1,250" size="748,4" backgroundColor="#00ffffff" zPosition="1" />
		<widget source="labe14" render="Label" position="2,80" size="730,30" halign="center" font="Regular; 22" backgroundColor="#00000000" foregroundColor="#00ffffff" />
		<widget source="key_red" render="Label" position="30,200" size="150,30" noWrap="1" zPosition="1" valign="center" font="Regular; 20" halign="left" backgroundColor="#00000000" foregroundColor="#00ffffff" />
		<widget source="key_green" render="Label" position="200,200" size="150,30" noWrap="1" zPosition="1" valign="center" font="Regular; 20" halign="left" backgroundColor="#00000000" foregroundColor="#00ffffff" />
		<widget source="key_yellow" render="Label" position="370,200" size="150,30" noWrap="1" zPosition="1" valign="center" font="Regular; 20" halign="left" backgroundColor="#00000000" foregroundColor="#00ffffff" />
		<ePixmap pixmap="skin_default/buttons/red.png" position="30,200" size="40,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/green.png" position="200,200" size="40,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/yellow.png" position="370,200" size="40,40" alphatest="on" />
	</screen>
	"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self.skinName = "H9SDmanager"
		self.setTitle(_("H9 SDcard manager"))
		self["labe14"] = StaticText(_("Press appropiate Init to move Nand root to SDcard or USB."))
		self["key_red"] = StaticText(_("Reboot"))
		self["key_green"] = StaticText(_("Init SDcard"))
		self["key_yellow"] = StaticText(_("Init USB/SDA1"))
		self["actions"] = ActionMap(["OkCancelActions", "ColorActions"],
		{
			"red": self.reboot,
			"green": self.SDInit,
			"yellow": self.USBInit,
			"ok": boundFunction(self.close, None),
			"cancel": boundFunction(self.close, None),
		}, -1)
		self.onLayoutFinish.append(self.layoutFinished)

	def layoutFinished(self):
		self.setTitle(_("H9 SDcard manager"))

	def SDInit(self):
		if SystemInfo["HasH9SD"]:
			self.TITLE = _("Init Zgemma H9 SDCARD - please reboot after use.")
			cmdlist = []
			cmdlist.append("opkg update")
			cmdlist.append("opkg install rsync")
			cmdlist.append("umount /dev/mmcblk0p1")
			cmdlist.append("dd if=/dev/zero of=/dev/mmcblk0p1 bs=1M count=150")
			cmdlist.append("mkfs.ext4 -L 'H9-ROOTFS' /dev/mmcblk0p1")
#			cmdlist.append("parted -s /dev/mmcblk0 rm 1")
#			cmdlist.append("parted -s /dev/mmcblk0 mklabel gpt")
#			cmdlist.append("parted -s /dev/mmcblk0 mkpart rootfs2 ext4 0% 100%")
			cmdlist.append("mkdir /tmp/mmc")
			cmdlist.append("mount /dev/mmcblk0p1 /tmp/mmc")
			cmdlist.append("mkdir /tmp/root")
			cmdlist.append("mount --bind / /tmp/root")
			cmdlist.append("rsync -aAX /tmp/root/ /tmp/mmc/")
			cmdlist.append("umount /tmp/root")
			cmdlist.append("umount /tmp/mmc")
			cmdlist.append("rmdir /tmp/root")
			cmdlist.append("rmdir /tmp/mmc")
			self.session.open(Console, title = self.TITLE, cmdlist = cmdlist, closeOnSuccess = True)
		else:
			self.close()

	def reboot(self):
		self.session.open(TryQuitMainloop, 2)

	def USBInit(self):
			self.TITLE = _("Init Zgemma H9 USB/SDA1 - please reboot after use.")
			cmdlist = []
			cmdlist.append("opkg update")
			cmdlist.append("opkg install rsync")
			cmdlist.append("umount /dev/mmcblk0p1")
			cmdlist.append("dd if=/dev/zero of=/dev/sda1 bs=1M count=150")
			cmdlist.append("mkfs.ext4 -L 'H9-ROOTFS' /dev/sda1")
#			cmdlist.append("mkfs.ext4 -L 'rootfs2' /dev/sda1")
			cmdlist.append("mkdir /tmp/mmc")
			cmdlist.append("mount /dev/mmcblk0p1 /tmp/mmc")
			cmdlist.append("mkdir /tmp/root")
			cmdlist.append("mount --bind / /tmp/root")
			cmdlist.append("rsync -aAX /tmp/root/ /tmp/mmc/")
			cmdlist.append("umount /tmp/root")
			cmdlist.append("umount /tmp/mmc")
			cmdlist.append("rmdir /tmp/root")
			cmdlist.append("rmdir /tmp/mmc")
			self.session.open(Console, title = self.TITLE, cmdlist = cmdlist, closeOnSuccess = True)
