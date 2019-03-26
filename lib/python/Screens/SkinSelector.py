# -*- coding: utf-8 -*-
from Screens.Screen import Screen
from Screens.Standby import TryQuitMainloop
from Screens.MessageBox import MessageBox
from Components.ActionMap import NumberActionMap
from Components.Pixmap import Pixmap
from Components.Sources.StaticText import StaticText
from Components.MenuList import MenuList
from Components.config import config, configfile
from Tools.Directories import resolveFilename, SCOPE_ACTIVE_SKIN
from enigma import eEnv, ePicLoad, eTimer
import os

class SkinSelectorBase:
	def __init__(self, session):
		self.skinlist = []
		self.previewPath = ""

		self["key_red"] = StaticText(_("Close"))
		self["key_green"] = StaticText(_("Save"))
		self["introduction"] = StaticText(_("Please wait... Loading list..."))
		self["SkinList"] = MenuList([])
		self["Preview"] = Pixmap()

		self["actions"] = NumberActionMap(["SetupActions", "DirectionActions", "TimerEditActions", "ColorActions"],
		{
			"ok": self.ok,
			"cancel": self.close,
			"red": self.close,
			"green": self.ok,
			"up": self.up,
			"down": self.down,
			"left": self.left,
			"right": self.right,
			"log": self.info,
		}, -1)

		self.picload = ePicLoad()
		self.picload.PictureData.get().append(self.showPic)

		self.onLayoutFinish.append(self.layoutFinished)
		self.listTimer = eTimer()
		self.listTimer.callback.append(self.refreshList)

	def showPic(self, picInfo=""):
		ptr = self.picload.getData()
		if ptr is not None:
			self["Preview"].instance.setPixmap(ptr.__deref__())
			self["Preview"].show()

	def layoutFinished(self):
		self.picload.setPara((self["Preview"].instance.size().width(), self["Preview"].instance.size().height(), 1.0, 1, 1, 1, "#ff000000"))
		self.show()
		self.listTimer.start(1, True)

	def refreshList(self):
		if self.SKINXML and os.path.exists(os.path.join(self.root, self.SKINXML)):
			self.skinlist.append(self.DEFAULTSKIN)
		if self.PICONSKINXML and os.path.exists(os.path.join(self.root, self.PICONSKINXML)):
			self.skinlist.append(self.PICONDEFAULTSKIN)

		for root, dirs, files in os.walk(self.root, followlinks=True):
			for subdir in dirs:
				dir = os.path.join(root,subdir)
				if os.path.exists(os.path.join(dir,self.SKINXML)):
					self.skinlist.append(subdir)
			dirs = []
		self.skinlist.sort()
		self["SkinList"].l.setList(self.skinlist)
		self["introduction"].setText(_("Press OK to activate the selected skin."))

		tmp = self.config.value.find("/"+self.SKINXML)
		if tmp != -1:
			tmp = self.config.value[:tmp]
			idx = 0
			for skin in self.skinlist:
				if skin == tmp:
					break
				idx += 1
			if idx < len(self.skinlist):
				self["SkinList"].moveToIndex(idx)
		self.loadPreview()

	def ok(self):
		if not self["SkinList"].getCurrent() or not self.SKINXML:
			return
		if self["SkinList"].getCurrent() == self.DEFAULTSKIN:
			self.skinfile = ""
			self.skinfile = os.path.join(self.skinfile, self.SKINXML)
		elif self["SkinList"].getCurrent() == self.PICONDEFAULTSKIN:
			self.skinfile = ""
			self.skinfile = os.path.join(self.skinfile, self.PICONSKINXML)
		else:
			self.skinfile = self["SkinList"].getCurrent()
			self.skinfile = os.path.join(self.skinfile, self.SKINXML)

		print "[SkinSelector] Selected Skin: "+self.root+self.skinfile
		restartbox = self.session.openWithCallback(self.restartGUI,MessageBox,_("GUI needs a restart to apply a new skin\nDo you want to restart the GUI now?"), MessageBox.TYPE_YESNO)
		restartbox.setTitle(_("Restart GUI now?"))

	def up(self):
		self["SkinList"].up()
		self.loadPreview()

	def down(self):
		self["SkinList"].down()
		self.loadPreview()

	def left(self):
		self["SkinList"].pageUp()
		self.loadPreview()

	def right(self):
		self["SkinList"].pageDown()
		self.loadPreview()

	def info(self):
		aboutbox = self.session.open(MessageBox,_("Enigma2 skin selector"), MessageBox.TYPE_INFO)
		aboutbox.setTitle(_("About..."))

	def loadPreview(self):
		self.changedEntry()
		if self["SkinList"].getCurrent() == self.DEFAULTSKIN:
			pngpath = "."
			pngpath = os.path.join(os.path.join(self.root, pngpath), "prev.png")
		elif self["SkinList"].getCurrent() == self.PICONDEFAULTSKIN:
			pngpath = "."
			pngpath = os.path.join(os.path.join(self.root, pngpath), "piconprev.png")
		else:
			pngpath = self["SkinList"].getCurrent()
			if not pngpath :
				pngpath = "."
			pngpath = os.path.join(os.path.join(self.root, pngpath), "prev.png")

		if not os.path.exists(pngpath):
			pngpath = resolveFilename(SCOPE_ACTIVE_SKIN, "noprev.png")

		if self.previewPath != pngpath:
			self.previewPath = pngpath

		self.picload.startDecode(self.previewPath)

	def restartGUI(self, answer):
		if answer is True:
			if isinstance(self, LcdSkinSelector):
				config.skin.display_skin.value = self.skinfile
				config.skin.display_skin.save()
			else:
				config.skin.primary_skin.value = self.skinfile
				config.skin.primary_skin.save()
			self.session.open(TryQuitMainloop, 3)

class SkinSelector(Screen, SkinSelectorBase):
	SKINXML = "skin.xml"
	DEFAULTSKIN = _("< Default >")
	PICONSKINXML = None
	PICONDEFAULTSKIN = None

	skinlist = []
	root = os.path.join(eEnv.resolve("${datadir}"),"enigma2")

	def __init__(self, session, menu_path="", skin_name=None):
		Screen.__init__(self, session)
		SkinSelectorBase.__init__(self, session)
		self.onChangedEntry = []
		self.skinName = ["SkinSelector"]
		if isinstance(skin_name, str):
			self.skinName.insert(0,skin_name)

		screentitle = _("Skin")
		if config.usage.show_menupath.value == 'large':
			menu_path += screentitle
			title = menu_path
			self["menu_path_compressed"] = StaticText("")
		elif config.usage.show_menupath.value == 'small':
			title = screentitle
			self["menu_path_compressed"] = StaticText(menu_path + " >" if not menu_path.endswith(' / ') else menu_path[:-3] + " >" or "")
		else:
			title = screentitle
			self["menu_path_compressed"] = StaticText("")
		Screen.setTitle(self, title)
		self.config = config.skin.primary_skin

	# for summary
	def changedEntry(self):
		for x in self.onChangedEntry:
			x()

	def createSummary(self):
		return SkinSelectorSummary

	def getCurrentName(self):
		current = self["SkinList"].getCurrent()
		return None if current is None else current.replace("_", " ")


class LcdSkinSelector(Screen, SkinSelectorBase):
	SKINXML = "skin_display.xml"
	DEFAULTSKIN = _("< Default >")
	PICONSKINXML = "skin_display_picon.xml"
	PICONDEFAULTSKIN = _("< Default with Picon >")

	skinlist = []
	root = os.path.join(eEnv.resolve("${datadir}"),"enigma2/display/")

	def __init__(self, session, menu_path=""):
		Screen.__init__(self, session)
		SkinSelectorBase.__init__(self, session)
		self.onChangedEntry = []
		screentitle = _("Skin setup")
		if config.usage.show_menupath.value == 'large':
			menu_path += screentitle
			title = menu_path
			self["menu_path_compressed"] = StaticText("")
		elif config.usage.show_menupath.value == 'small':
			title = screentitle
			self["menu_path_compressed"] = StaticText(menu_path + " >" if not menu_path.endswith(' / ') else menu_path[:-3] + " >" or "")
		else:
			title = screentitle
			self["menu_path_compressed"] = StaticText("")
		Screen.setTitle(self, title)
		self.skinName = "SkinSelector"
		self.config = config.skin.display_skin

	# for summary
	def changedEntry(self):
		for x in self.onChangedEntry:
			x()

	def createSummary(self):
		return SkinSelectorSummary

	def getCurrentName(self):
		current = self["SkinList"].getCurrent()
		return None if current is None else current.replace("_", " ")


class SkinSelectorSummary(Screen):
	def __init__(self, session, parent):
		Screen.__init__(self, session, parent = parent)
		self["Name"] = StaticText("")
		if hasattr(self.parent,"onChangedEntry"):
			self.onShow.append(self.addWatcher)
			self.onHide.append(self.removeWatcher)

	def addWatcher(self):
		if hasattr(self.parent,"onChangedEntry"):
			self.parent.onChangedEntry.append(self.selectionChanged)
			self.selectionChanged()

	def removeWatcher(self):
		if hasattr(self.parent,"onChangedEntry"):
			self.parent.onChangedEntry.remove(self.selectionChanged)

	def selectionChanged(self):
		self["Name"].text = self.parent.getCurrentName()
