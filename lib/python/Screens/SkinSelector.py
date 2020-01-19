import re
import xml.etree.cElementTree

from enigma import ePicLoad, getDesktop
from os import listdir
from os.path import dirname, exists, isdir, join as pathjoin

from skin import DEFAULT_SKIN, DEFAULT_DISPLAY_SKIN, EMERGENCY_SKIN, domScreens
from Components.ActionMap import HelpableNumberActionMap
from Components.config import config
from Components.Pixmap import Pixmap
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Standby import TryQuitMainloop, QUIT_RESTART
from Tools.Directories import resolveFilename, SCOPE_CURRENT_SKIN, SCOPE_LCDSKIN, SCOPE_SKIN


class SkinSelector(Screen, HelpableScreen):
	def __init__(self, session, menu_path="", screenTitle=_("GUI Skin")):
		self.hackSkin()  # This is a hack to ensure the SkinConverter screen works with the new code.
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		if config.usage.show_menupath.value == 'large':
			menu_path += screenTitle
			title = menu_path
			self["menu_path_compressed"] = StaticText("")
		elif config.usage.show_menupath.value == 'small':
			title = screenTitle
			self["menu_path_compressed"] = StaticText(menu_path + " >" if not menu_path.endswith(" / ") else menu_path[:-3] + " >" or "")
		else:
			title = screenTitle
			self["menu_path_compressed"] = StaticText("")
		Screen.setTitle(self, title)
		self.skinName = ["SkinSelector"]
		self.rootDir = resolveFilename(SCOPE_SKIN)
		self.config = config.skin.primary_skin
		self.xmlList = ["skin.xml"]
		self.onChangedEntry = []
		self["skins"] = List(enableWrapAround=True)
		self["preview"] = Pixmap()
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Save"))
		self["description"] = StaticText(_("Please wait... Loading list..."))
		self["actions"] = HelpableNumberActionMap(self, ["SetupActions", "DirectionActions", "ColorActions"], {
			"ok": (self.save, _("Activate the currently selected skin")),
			"cancel": (self.cancel, _("Revert to the currently active skin")),
			"red": (self.cancel, _("Revert to the currently active skin")),
			"green": (self.save, _("Activate the currently selected skin")),
			"up": (self.up, _("Move to the previous skin")),
			"down": (self.down, _("Move to the next skin")),
			"left": (self.left, _("Move to the previous page")),
			"right": (self.right, _("Move to the next page"))
		}, -1, description=_("Skin Selection Actions"))
		self.picload = ePicLoad()
		self.picload.PictureData.get().append(self.showPic)
		self.onLayoutFinish.append(self.layoutFinished)

	def hackSkin(self):  # This is a hack to ensure the SkinConverter screen works with the new code.
		rescueSkin = """
	<screen name="SkinSelector" position="center,center" size="%d,%d">
		<widget name="preview" position="center,%d" size="%d,%d" alphatest="blend" />
		<widget source="skins" render="Listbox" position="center,%d" size="%d,%d" enableWrapAround="1" scrollbarMode="showOnDemand" transparent="1">
			<convert type="TemplatedMultiContent">
				{
				"template": [
					MultiContentEntryText(pos = (%d, 0), size = (%d, %d), font = 0, flags = RT_HALIGN_LEFT | RT_VALIGN_CENTER, text = 1),
					MultiContentEntryText(pos = (%d, 0), size = (%d, %d), font = 0, flags = RT_HALIGN_RIGHT | RT_VALIGN_CENTER, text = 2)
				],
				"fonts": [gFont("Regular",%d)],
				"itemHeight": %d
				}
			</convert>
		</widget>
		<widget source="description" render="Label" position="center,%d" size="%d,%d" font="Regular;%d" transparent="1" valign="center" />
		<widget source="key_red" render="Pixmap" pixmap="buttons/key_red_fill.png" position="%d,e-%d" size="%d,%d" alphatest="blend" objectTypes="key_red,StaticText" scale="1">
 			<convert type="ConditionalShowHide" />
 		</widget>
		<widget source="key_red" render="Label" position="%d,e-%d" size="%d,%d" backgroundColor="key_red" font="Regular;%d" foregroundColor="key_text" halign="center" transparent="1" valign="center" zPosition="+1" />
		<widget source="key_green" render="Pixmap" pixmap="buttons/key_green_fill.png" position="%d,e-%d" size="%d,%d" alphatest="blend" objectTypes="key_green,StaticText" scale="1">
 			<convert type="ConditionalShowHide" />
 		</widget>
		<widget source="key_green" render="Label" position="%d,e-%d" size="%d,%d" backgroundColor="key_green" font="Regular;%d" foregroundColor="key_text" halign="center" transparent="1" valign="center" zPosition="+1" />
	</screen>"""
		rescueData = [630, 570, 10, 356, 200, 230, 610, 240, 10, 290, 30, 310, 280, 30, 25, 30, 490, 610, 25, 20, 10, 50, 140, 40, 10, 50, 140, 40, 20, 160, 50, 140, 40, 160, 50, 140, 40, 20]
		replaceSkin = False
		element, path = domScreens.get("SkinSelector", (None, None))
		if element is not None:
			widgets = element.findall("widget")
			if widgets is not None:
				for widget in widgets:
					name = widget.get("name", None)
					if name == "Preview":
						replaceSkin = True
					if name == "SkinList":
						replaceSkin = True
					source = widget.get("source", None)
					if source == "introduction":
						replaceSkin = True
		height = getDesktop(0).size().height()
		if replaceSkin:
			height = 720 if height < 720 else height
			rescueData = [x * height / 720 for x in rescueData]
			element = xml.etree.cElementTree.fromstring(rescueSkin % tuple(rescueData))
			domScreens["SkinSelector"] = (element, path)
		# print "[SkinSelector] DEBUG: Height=%d\n" % getDesktop(0).size().height(), xml.etree.cElementTree.tostring(element)

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
		emergency = _("< Emergency >")
		default = _("< Default >")
		defaultPicon = _("< Default + Picon >")
		current = _("< Current >")
		displayPicon = pathjoin(dirname(DEFAULT_DISPLAY_SKIN), "skin_display_picon.xml")
		skinList = []
		# Find and list the available skins...
		for dir in [dir for dir in listdir(self.rootDir) if isdir(pathjoin(self.rootDir, dir))]:
			previewPath = pathjoin(self.rootDir, dir)
			for skinFile in self.xmlList:
				skin = pathjoin(dir, skinFile)
				skinPath = pathjoin(self.rootDir, skin)
				if exists(skinPath):
					resolution = None
					if skinFile == "skin.xml":
						with open(skinPath) as chan:
							resolution = chan.read(65536)
						try:
							resolution = re.search("\<resolution.*?\syres\s*=\s*\"(\d+)\"", resolution).group(1)
						except Exception:
							resolution = ""
						resolution = resolutions.get(resolution, None)
						msg = "an unknown" if resolution is None else "a %s" % resolution
						print "[SkinSelector] Skin '%s' is %s resolution skin." % (skinPath, msg)
						# Code can be added here to reject unsupported resolutions.
					# The "piconprev.png" image should be "prevpicon.png" to keep it with its partner preview image.
					preview = pathjoin(previewPath, "piconprev.png" if skinFile == "skin_display_picon.xml" else "prev.png")
					if skin == EMERGENCY_SKIN:
						list = [emergency, emergency, dir, skin, resolution, preview]
					elif skin == DEFAULT_SKIN:
						list = [dir, default, dir, skin, resolution, preview]
					elif skin == DEFAULT_DISPLAY_SKIN:
						list = [default, default, dir, skin, resolution, preview]
					elif skin == displayPicon:
						list = [dir, defaultPicon, dir, skin, resolution, preview]
					else:
						list = [dir, "", dir, skin, resolution, preview]
					if skin == self.config.value:
						list[1] = current
					# 0=SortKey, 1=Label, 2=Flag, 3=Directory, 4=Skin, 5=Resolution, 6=Preview
					skinList.append(tuple([list[0].upper()] + list))
		skinList.sort()
		self["skins"].setList(skinList)
		# Set the list pointer to the current skin...
		for index in range(len(skinList)):
			if skinList[index][4] == self.config.value:
				self["skins"].setIndex(index)
				break
		self.loadPreview()

	def loadPreview(self):
		self.changedEntry()
		preview = self["skins"].getCurrent()[6]
		if not exists(preview):
			preview = resolveFilename(SCOPE_CURRENT_SKIN, "noprev.png")
		self.picload.startDecode(preview)
		resolution = self["skins"].getCurrent()[5]
		msg = "" if resolution is None else " %s" % resolution
		if self["skins"].getCurrent()[4] == self.config.value:
			self["description"].setText(_("Press OK to keep the currently selected%s skin.") % msg)
		else:
			self["description"].setText(_("Press OK to activate the selected%s skin.") % msg)

	def cancel(self):
		self.close()

	def save(self):
		skin = self["skins"].getCurrent()[4]
		if self.config.value == skin:
			print "[SkinSelector] Selected skin: '%s' (Unchanged!)" % pathjoin(self.rootDir, skin)
			self.cancel()
		else:
			print "[SkinSelector] Selected skin: '%s'" % pathjoin(self.rootDir, skin)
			restartBox = self.session.openWithCallback(self.restartGUI, MessageBox, _("To save and apply the selected '%s' skin the GUI needs to restart.  Would you like to save the selection and restart the GUI?" % self["skins"].getCurrent()[1]), MessageBox.TYPE_YESNO)
			restartBox.setTitle(_("SkinSelector: Restart GUI"))

	def restartGUI(self, answer):
		if answer is True:
			self.config.value = self["skins"].getCurrent()[4]
			self.config.save()
			self.session.open(TryQuitMainloop, QUIT_RESTART)

	def up(self):
		self["skins"].up()
		self.loadPreview()

	def down(self):
		self["skins"].down()
		self.loadPreview()

	def left(self):
		self["skins"].pageUp()
		self.loadPreview()

	def right(self):
		self["skins"].pageDown()
		self.loadPreview()

	# For summary screen.
	def changedEntry(self):
		for x in self.onChangedEntry:
			x()

	def createSummary(self):
		return SkinSelectorSummary

	def getCurrentName(self):
		current = self["skins"].getCurrent()[1]
		if current:
			current = current.replace("_", " ")
		return current


class LcdSkinSelector(SkinSelector):
	def __init__(self, session, menu_path="", screenTitle=_("Display Skin")):
		SkinSelector.__init__(self, session, menu_path=menu_path, screenTitle=screenTitle)
		self.rootDir = resolveFilename(SCOPE_LCDSKIN)
		self.config = config.skin.display_skin
		self.xmlList = ["skin_display.xml", "skin_display_picon.xml"]


class SkinSelectorSummary(Screen):
	def __init__(self, session, parent):
		Screen.__init__(self, session, parent=parent)
		self["Name"] = StaticText("")
		if hasattr(self.parent, "onChangedEntry"):
			self.onShow.append(self.addWatcher)
			self.onHide.append(self.removeWatcher)

	def addWatcher(self):
		if hasattr(self.parent, "onChangedEntry"):
			self.parent.onChangedEntry.append(self.selectionChanged)
			self.selectionChanged()

	def removeWatcher(self):
		if hasattr(self.parent, "onChangedEntry"):
			self.parent.onChangedEntry.remove(self.selectionChanged)

	def selectionChanged(self):
		self["Name"].text = self.parent.getCurrentName()
