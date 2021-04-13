import mmap
import re

from enigma import ePicLoad
from os import listdir
from os.path import dirname, exists, isdir, join as pathjoin

from skin import DEFAULT_SKIN, DEFAULT_DISPLAY_SKIN, EMERGENCY_NAME, EMERGENCY_SKIN
from Components.ActionMap import HelpableActionMap
from Components.config import config
from Components.Pixmap import Pixmap
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen, ScreenSummary
from Screens.Standby import TryQuitMainloop, QUIT_RESTART
from Tools.Directories import resolveFilename, SCOPE_CURRENT_SKIN, SCOPE_LCDSKIN, SCOPE_SKIN


class SkinSelector(Screen, HelpableScreen):

	def __init__(self, session, screenTitle=_("GUI Skin"), skin_name=None, reboot=True):
		Screen.__init__(self, session, mandatoryWidgets=["skins", "preview"])
		HelpableScreen.__init__(self)
		self.setTitle(screenTitle)
		self.reboot = reboot
		self.skinName = ["SkinSelector", "__SkinSelector__"]
		if isinstance(skin_name, str):
			self.skinName = [skin_name] + self.skinName
		self.rootDir = resolveFilename(SCOPE_SKIN)
		self.config = config.skin.primary_skin
		from skin import currentPrimarySkin # value types are imported by value at import time
		self.currentSkin = currentPrimarySkin
		self.xmlList = ["skin.xml"]
		self.onChangedEntry = []
		self["skins"] = List(enableWrapAround=True)
		self["preview"] = Pixmap()
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Save"))
		self["description"] = StaticText(_("Please wait... Loading list..."))
		self["skinActions"] = HelpableActionMap(self, ["CancelSaveActions", "OkActions", "NavigationActions"], {
			"cancel": (self.keyCancel, _("Cancel any changes to the currently active skin")),
			"close": (self.closeRecursive, _("Cancel any changes to the currently active skin and exit all menus")),
			"save": (self.keySave, _("Save and activate the currently selected skin")),
			"ok": (self.keySave, _("Save and activate the currently selected skin")),
			"top": (self.keyPageUp, _("Move up a screen")),
			"pageUp": (self.keyPageUp, _("Move up a screen")),
			"up": (self.keyUp, _("Move up a line")),
			"first": (self.keyPageUp, _("Move up a screen")),
			"left": (self.keyPageUp, _("Move up a screen")),
			"right": (self.keyPageDown, _("Move down a screen")),
			"last": (self.keyPageDown, _("Move down a screen")),
			"down": (self.keyDown, _("Move down a line")),
			"pageDown": (self.keyPageDown, _("Move down a screen")),
			"bottom": (self.keyPageDown, _("Move down a screen"))
		}, prio=-1, description=_("Skin Selection Actions"))
		self.picload = ePicLoad()
		self.picload.PictureData.get().append(self.showPic)
		self.onLayoutFinish.append(self.layoutFinished)

	def showPic(self, picInfo=""):
		ptr = self.picload.getData()
		if ptr is not None:
			self["preview"].instance.setPixmap(ptr.__deref__())

	def layoutFinished(self):
		self.picload.setPara((self["preview"].instance.size().width(), self["preview"].instance.size().height(), 1.0, 1, 1, 1, "#ff000000"))
		self.refreshList()

	def refreshList(self):
		resolutions = {
			"480": _("NTSC"),
			"576": _("PAL"),
			"720": _("HD"),
			"1080": _("FHD"),
			"2160": _("4K"),
			"4320": _("8K"),
			"8640": _("16K")
		}
		emergency = _("<Emergency>")
		default = _("<Default>")
		defaultPicon = _("<Default+Picon>")
		current = _("<Current>")
		pending = _("<Pending restart>")
		displayPicon = pathjoin(dirname(DEFAULT_DISPLAY_SKIN), "skin_display_picon.xml")
		skinList = []
		# Find and list the available skins...
		for dir in [dir for dir in listdir(self.rootDir) if isdir(pathjoin(self.rootDir, dir))]:
			previewPath = pathjoin(self.rootDir, dir)
			for skinFile in self.xmlList:
				skin = pathjoin(dir, skinFile)
				skinPath = pathjoin(self.rootDir, skin)
				if exists(skinPath):
					skinSize = None
					resolution = None
					if skinFile == "skin.xml":
						try:
							with open(skinPath, "r") as fd:
								mm = mmap.mmap(fd.fileno(), 0, prot=mmap.PROT_READ)
								skinWidth = re.search(r"<?resolution.*?\sxres\s*=\s*\"(\d+)\"", mm)
								skinHeight = re.search(r"<?resolution.*?\syres\s*=\s*\"(\d+)\"", mm)
								if skinWidth and skinHeight:
									skinSize = "%sx%s" % (skinWidth.group(1), skinHeight.group(1))
								resolution = skinHeight and resolutions.get(skinHeight.group(1), None)
								mm.close()
						except:
							pass
						print("[SkinSelector] Resolution of skin '%s': '%s' (%s)." % (skinPath, "Unknown" if resolution is None else resolution, skinSize))
						# Code can be added here to reject unsupported resolutions.
					# The "piconprev.png" image should be "prevpicon.png" to keep it with its partner preview image.
					label = dir.replace("_", " ")
					preview = pathjoin(previewPath, "piconprev.png" if skinFile == "skin_display_picon.xml" else "prev.png")
					if skin == EMERGENCY_SKIN:
						skinEntry = [EMERGENCY_NAME, emergency, dir, skin, resolution, skinSize, preview]
					elif skin == DEFAULT_SKIN:
						skinEntry = [label, default, dir, skin, resolution, skinSize, preview]
					elif skin == DEFAULT_DISPLAY_SKIN:
						skinEntry = [default, default, dir, skin, resolution, skinSize, preview]
					elif skin == displayPicon:
						skinEntry = [label, defaultPicon, dir, skin, resolution, skinSize, preview]
					else:
						skinEntry = [label, "", dir, skin, resolution, skinSize, preview]
					if skin == self.currentSkin:
						skinEntry[1] = current
					elif skin == self.config.value:
						skinEntry[1] = pending
					skinEntry.append("%s  %s" % (skinEntry[0], skinEntry[1]))
					# 0=SortKey, 1=Label, 2=Flag, 3=Directory, 4=Skin, 5=Resolution, 6=SkinSize, 7=Preview, 8=Label + Flag
					skinList.append(tuple([skinEntry[0].upper()] + skinEntry))
		skinList.sort()
		self["skins"].setList(skinList)
		# Set the list pointer to the current skin...
		for index in range(len(skinList)):
			if skinList[index][4] == self.config.value:
				self["skins"].setIndex(index)
				break
		self.loadPreview()

	def loadPreview(self):
		self.currentEntry = self["skins"].getCurrent()
		self.changedEntry()
		preview = self.currentEntry[7]
		if not exists(preview):
			preview = resolveFilename(SCOPE_CURRENT_SKIN, "noprev.png")
		self.picload.startDecode(preview)
		resolution = self.currentEntry[5]
		msg = "" if resolution is None else " %s" % resolution
		if self.currentEntry[4] == self.config.value:  # Is the current entry the current skin?
			self["description"].setText(_("Press OK to keep the currently selected%s skin.") % msg)
		else:
			self["description"].setText(_("Press OK to activate the selected%s skin.") % msg)

	def keyCancel(self):
		self.close()

	def closeRecursive(self):
		self.close(True)

	def keySave(self):
		label = self.currentEntry[1]
		skin = self.currentEntry[4]
		if skin == self.config.value:
			if skin == self.currentSkin:
				print("[SkinSelector] Selected skin: '%s' (Unchanged!)" % pathjoin(self.rootDir, skin))
				self.close()
			else:
				print("[SkinSelector] Selected skin: '%s' (Trying to restart again!)" % pathjoin(self.rootDir, skin))
				restartBox = self.session.openWithCallback(self.restartGUI, MessageBox, _("To apply the selected '%s' skin the GUI needs to restart. Would you like to restart the GUI now?") % label, MessageBox.TYPE_YESNO)
				restartBox.setTitle(_("SkinSelector: Restart GUI"))
		elif skin == self.currentSkin:
			print("[SkinSelector] Selected skin: '%s' (Pending skin '%s' cancelled!)" % (pathjoin(self.rootDir, skin), pathjoin(self.rootDir, self.config.value)))
			self.config.value = skin
			self.config.save()
			self.close()
		else:
			print("[SkinSelector] Selected skin: '%s'" % pathjoin(self.rootDir, skin))
			if config.usage.fast_skin_reload.value or not self.reboot:
				self.saveConfig()
				self.session.reloadSkin()
			else:
				restartBox = self.session.openWithCallback(self.restartGUI, MessageBox, _("To save and apply the selected '%s' skin the GUI needs to restart. Would you like to save the selection and restart the GUI now?") % label, MessageBox.TYPE_YESNO)
				restartBox.setTitle(_("SkinSelector: Restart GUI"))

	def restartGUI(self, answer):
		if answer is True:
			self.saveConfig()
			self.session.open(TryQuitMainloop, QUIT_RESTART)
		self.refreshList()

	def saveConfig(self):
		self.config.value = self.currentEntry[4]
		self.config.save()

	def keyTop(self):
		self["skins"].moveTop()
		self.loadPreview()

	def keyPageUp(self):
		self["skins"].pageUp()
		self.loadPreview()

	def keyUp(self):
		self["skins"].up()
		self.loadPreview()

	def keyDown(self):
		self["skins"].down()
		self.loadPreview()

	def keyPageDown(self):
		self["skins"].pageDown()
		self.loadPreview()

	def keyBottom(self):
		self["skins"].moveEnd()
		self.loadPreview()

	def changedEntry(self):
		for x in self.onChangedEntry:
			x()

	def createSummary(self):
		return SkinSelectorSummary


class LcdSkinSelector(SkinSelector):
	def __init__(self, session, screenTitle=_("Display Skin")):
		SkinSelector.__init__(self, session, screenTitle=screenTitle)
		self.skinName = ["LcdSkinSelector"] + self.skinName
		self.rootDir = resolveFilename(SCOPE_LCDSKIN)
		self.config = config.skin.display_skin
		from skin import currentDisplaySkin # value types are imported by value at import time
		self.currentSkin = currentDisplaySkin
		self.xmlList = ["skin_display.xml", "skin_display_picon.xml"]


class SkinSelectorSummary(ScreenSummary):
	def __init__(self, session, parent):
		ScreenSummary.__init__(self, session, parent=parent)
		self["entry"] = StaticText("")
		self["value"] = StaticText("")
		self["Name"] = StaticText("")
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
		currentEntry = self.parent["skins"].getCurrent()  # Label
		self["entry"].setText(currentEntry[1])
		self["value"].setText("%s   %s" % (currentEntry[5], currentEntry[2]) if currentEntry[5] and currentEntry[2] else currentEntry[5] or currentEntry[2])  # Resolution and/or Flag.
		self["Name"].setText(self["entry"].getText())
