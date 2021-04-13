from __future__ import print_function
from __future__ import absolute_import

from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.config import config, configfile, ConfigSubsection, getConfigListEntry, ConfigSelectionNumber, ConfigSelection, ConfigSlider, ConfigYesNo, NoSave, ConfigNumber, ConfigText
from Components.ConfigList import ConfigListScreen
from Components.SystemInfo import SystemInfo
from Components.Sources.StaticText import StaticText
from Components.Pixmap import Pixmap
from Components.Console import Console
from Tools.Directories import fileCheck, fileExists
from enigma import getDesktop
from os import access, R_OK

from boxbranding import getBoxType


def getFilePath(setting):
	return "/proc/stb/fb/dst_%s" % (setting)


def setPositionParameter(parameter, configElement):
	f = open(getFilePath(parameter), "w")
	f.write('%08X\n' % configElement.value)
	f.close()
	if fileExists(getFilePath("apply")):
		f = open(getFilePath("apply"), "w")
		f.write('1')
		f.close()


def InitOsd():
	SystemInfo["CanChange3DOsd"] = (access('/proc/stb/fb/3dmode', R_OK) or access('/proc/stb/fb/primary/3d', R_OK)) and True or False

	config.osd.dst_left = ConfigSelectionNumber(default=0, stepwidth=1, min=0, max=720, wraparound=False)
	config.osd.dst_width = ConfigSelectionNumber(default=720, stepwidth=1, min=0, max=720, wraparound=False)
	config.osd.dst_top = ConfigSelectionNumber(default=0, stepwidth=1, min=0, max=576, wraparound=False)
	config.osd.dst_height = ConfigSelectionNumber(default=576, stepwidth=1, min=0, max=576, wraparound=False)
	config.osd.alpha = ConfigSelectionNumber(default=255, stepwidth=1, min=0, max=255, wraparound=False)
	config.av.osd_alpha = NoSave(ConfigNumber(default=255))
	config.osd.threeDmode = ConfigSelection([("off", _("Off")), ("auto", _("Auto")), ("sidebyside", _("Side by Side")), ("topandbottom", _("Top and Bottom"))], "auto")
	config.osd.threeDznorm = ConfigSlider(default=50, increment=1, limits=(0, 100))
	config.osd.show3dextensions = ConfigYesNo(default=False)

	def set3DMode(configElement):
		if SystemInfo["CanChange3DOsd"] and getBoxType() not in ('spycat'):
			print('[UserInterfacePositioner] Setting 3D mode:', configElement.value)
			file3d = fileCheck('/proc/stb/fb/3dmode') or fileCheck('/proc/stb/fb/primary/3d')
			f = open(file3d, "w")
			f.write(configElement.value)
			f.close()
	config.osd.threeDmode.addNotifier(set3DMode)

	def set3DZnorm(configElement):
		if SystemInfo["CanChange3DOsd"] and getBoxType() not in ('spycat'):
			print('[UserInterfacePositioner] Setting 3D depth:', configElement.value)
			f = open("/proc/stb/fb/znorm", "w")
			f.write('%d' % int(configElement.value))
			f.close()
	config.osd.threeDznorm.addNotifier(set3DZnorm)


def InitOsdPosition():
	SystemInfo["CanChangeOsdAlpha"] = access('/proc/stb/video/alpha', R_OK) and True or False
	SystemInfo["CanChangeOsdPosition"] = access('/proc/stb/fb/dst_left', R_OK) and True or False
	SystemInfo["OsdSetup"] = SystemInfo["CanChangeOsdPosition"]

	if SystemInfo["CanChangeOsdAlpha"] == True or SystemInfo["CanChangeOsdPosition"] == True:
		SystemInfo["OsdMenu"] = True
	else:
		SystemInfo["OsdMenu"] = False

	def setOSDLeft(configElement):
		if SystemInfo["CanChangeOsdPosition"]:
			setPositionParameter("left", configElement)
	config.osd.dst_left.addNotifier(setOSDLeft)

	def setOSDWidth(configElement):
		if SystemInfo["CanChangeOsdPosition"]:
			setPositionParameter("width", configElement)
	config.osd.dst_width.addNotifier(setOSDWidth)

	def setOSDTop(configElement):
		if SystemInfo["CanChangeOsdPosition"]:
			setPositionParameter("top", configElement)
	config.osd.dst_top.addNotifier(setOSDTop)

	def setOSDHeight(configElement):
		if SystemInfo["CanChangeOsdPosition"]:
			setPositionParameter("height", configElement)
	config.osd.dst_height.addNotifier(setOSDHeight)
	print('[UserInterfacePositioner] Setting OSD position: %s %s %s %s' % (config.osd.dst_left.value, config.osd.dst_width.value, config.osd.dst_top.value, config.osd.dst_height.value))

	def setOSDAlpha(configElement):
		if SystemInfo["CanChangeOsdAlpha"]:
			print('[UserInterfacePositioner] Setting OSD alpha:', str(configElement.value))
			config.av.osd_alpha.setValue(configElement.value)
			f = open("/proc/stb/video/alpha", "w")
			f.write(str(configElement.value))
			f.close()
	config.osd.alpha.addNotifier(setOSDAlpha)


class UserInterfacePositioner(ConfigListScreen, Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle(_("OSD position"))
		self.Console = Console()
		self["status"] = StaticText()
		self["key_yellow"] = StaticText(_("Defaults"))

		self["actions"] = ActionMap(["ColorActions"],
			{
				"yellow": self.keyDefault,
			}, -2)

		self.onChangedEntry = []
		self.list = []
		ConfigListScreen.__init__(self, self.list, session=self.session, on_change=self.changedEntry, fullUI=True)
		if SystemInfo["CanChangeOsdAlpha"]:
			self.list.append(getConfigListEntry(_("User interface visibility"), config.osd.alpha, _("This option lets you adjust the transparency of the user interface")))
		if SystemInfo["CanChangeOsdPosition"]:
			self.list.append(getConfigListEntry(_("Move Left/Right"), config.osd.dst_left, _("Use the LEFT/RIGHT buttons on your remote to move the user interface left/right.")))
			self.list.append(getConfigListEntry(_("Width"), config.osd.dst_width, _("Use the LEFT/RIGHT buttons on your remote to adjust the width of the user interface. LEFT button decreases the size, RIGHT increases the size.")))
			self.list.append(getConfigListEntry(_("Move Up/Down"), config.osd.dst_top, _("Use the LEFT/RIGHT buttons on your remote to move the user interface up/down.")))
			self.list.append(getConfigListEntry(_("Height"), config.osd.dst_height, _("Use the LEFT/RIGHT buttons on your remote to adjust the height of the user interface. LEFT button decreases the size, RIGHT increases the size.")))
		self["config"].list = self.list
		self["config"].l.setList(self.list)

		self.serviceRef = None
		if self.welcomeWarning not in self.onShow:
			self.onShow.append(self.welcomeWarning)
		if self.selectionChanged not in self["config"].onSelectionChanged:
			self["config"].onSelectionChanged.append(self.selectionChanged)
		self.selectionChanged()

	def selectionChanged(self):
		self["status"].setText(self["config"].getCurrent()[2])

	def welcomeWarning(self):
		if self.welcomeWarning in self.onShow:
			self.onShow.remove(self.welcomeWarning)
		popup = self.session.openWithCallback(self.welcomeAction, MessageBox, _("NOTE: This feature is intended for people who cannot disable overscan "
			"on their television / display.  Please first try to disable overscan before using this feature.\n\n"
			"USAGE: Adjust the screen size and position settings so that the shaded user interface layer *just* "
			"covers the test pattern in the background.\n\n"
			"Select Yes to continue or No to exit."), type=MessageBox.TYPE_YESNO, timeout=-1, default=False)
		popup.setTitle(_("OSD position"))

	def welcomeAction(self, answer):
		if answer:
			self.serviceRef = self.session.nav.getCurrentlyPlayingServiceReference()
			self.session.nav.stopService()
			if self.restoreService not in self.onClose:
				self.onClose.append(self.restoreService)
			self.Console.ePopen('/usr/bin/showiframe /usr/share/enigma2/hd-testcard.mvi')
		else:
			self.close()

	def restoreService(self):
		try:
			self.session.nav.playService(self.serviceRef)
		except:
			pass

	def keyLeft(self):
		ConfigListScreen.keyLeft(self)
		self.setPreviewPosition()

	def keyRight(self):
		ConfigListScreen.keyRight(self)
		self.setPreviewPosition()

	def keyDefault(self):
		config.osd.alpha.setValue(255)
		config.osd.dst_left.setValue(0)
		config.osd.dst_width.setValue(720)
		config.osd.dst_top.setValue(0)
		config.osd.dst_height.setValue(576)
		for item in self["config"].list:
			self["config"].invalidate(item)
		print('[UserInterfacePositioner] Setting default OSD position: %s %s %s %s' % (config.osd.dst_left.value, config.osd.dst_width.value, config.osd.dst_top.value, config.osd.dst_height.value))

	def setPreviewPosition(self):
		size_w = getDesktop(0).size().width()
		size_h = getDesktop(0).size().height()
		dsk_w = int(float(size_w)) / float(720)
		dsk_h = int(float(size_h)) / float(576)
		dst_left = int(config.osd.dst_left.value)
		dst_width = int(config.osd.dst_width.value)
		dst_top = int(config.osd.dst_top.value)
		dst_height = int(config.osd.dst_height.value)
		while dst_width + (dst_left / float(dsk_w)) >= 720.5 or dst_width + dst_left > 720:
			dst_width = int(dst_width) - 1
		while dst_height + (dst_top / float(dsk_h)) >= 576.5 or dst_height + dst_top > 576:
			dst_height = int(dst_height) - 1
		config.osd.dst_left.setValue(dst_left)
		config.osd.dst_width.setValue(dst_width)
		config.osd.dst_top.setValue(dst_top)
		config.osd.dst_height.setValue(dst_height)
		for item in self["config"].list:
			self["config"].invalidate(item)
		print('[UserInterfacePositioner] Setting OSD position: %s %s %s %s' % (config.osd.dst_left.value, config.osd.dst_width.value, config.osd.dst_top.value, config.osd.dst_height.value))

# This is called by the Wizard...

	def run(self):
		config.osd.dst_left.save()
		config.osd.dst_width.save()
		config.osd.dst_top.save()
		config.osd.dst_height.save()
		configfile.save()
		self.close()


class OSD3DSetupScreen(ConfigListScreen, Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.skinName = "Setup"
		self.setTitle(_("3D"))
		self["description"] = StaticText()

		self.onChangedEntry = []
		self.list = []
		ConfigListScreen.__init__(self, self.list, session=self.session, on_change=self.changedEntry, fullUI=True)
		self.list.append(getConfigListEntry(_("3D Mode"), config.osd.threeDmode, _("This option lets you choose the 3D mode")))
		self.list.append(getConfigListEntry(_("Depth"), config.osd.threeDznorm, _("This option lets you adjust the 3D depth")))
		self.list.append(getConfigListEntry(_("Show in extensions list ?"), config.osd.show3dextensions, _("This option lets you show the option in the extension screen")))
		self["config"].list = self.list
		self["config"].l.setList(self.list)

		if not self.selectionChanged in self["config"].onSelectionChanged:
			self["config"].onSelectionChanged.append(self.selectionChanged)
		self.selectionChanged()

	def selectionChanged(self):
		self["description"].setText(self["config"].getCurrent()[2])
