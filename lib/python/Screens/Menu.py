from skin import findSkinScreen
from Screens.HelpMenu import HelpableScreen
from Screens.Screen import Screen, ScreenSummary
from Screens.MessageBox import MessageBox
from Screens.ParentalControlSetup import ProtectedScreen
from Components.Sources.List import List
from Components.ActionMap import HelpableNumberActionMap, HelpableActionMap
from Components.Sources.StaticText import StaticText
from Components.PluginComponent import plugins
from Components.config import config, ConfigDictionarySet, configfile, NoSave
from Components.NimManager import nimmanager
from Components.SystemInfo import SystemInfo
from Tools.BoundFunction import boundFunction
from Plugins.Plugin import PluginDescriptor
from Tools.Directories import resolveFilename, SCOPE_SKINS, SCOPE_GUISKIN
from Tools.LoadPixmap import LoadPixmap
from enigma import eTimer

import xml.etree.cElementTree

from Screens.Setup import Setup

# read the menu
file = open(resolveFilename(SCOPE_SKINS, 'menu.xml'), 'r')
mdom = xml.etree.cElementTree.parse(file)
file.close()


def MenuEntryPixmap(entryID, png_cache, parentMenuEntryID):
 	# imported here to avoid circular import
	from skin import parameters
	isMenuIcons = int(parameters.get("MenuIcons", 0)) == 1
	if not isMenuIcons:
		return None
	
	icoSize = int(parameters.get("MenuIconsSize", 192))
	width = icoSize
	height = icoSize
	png = png_cache.get(entryID, None)
	if png is None: # no cached entry
		pngPath = resolveFilename(SCOPE_GUISKIN, "menu/" + entryID + ".svg")
		pos = config.skin.primary_skin.value.rfind('/')
		if pos > -1:
			current_skin = config.skin.primary_skin.value[:pos+1]
		else:
			current_skin = ""
		if ( current_skin in pngPath and current_skin ) or not current_skin:
			png = LoadPixmap(pngPath, cached=True, width=width, height=0 if pngPath.endswith(".svg") else height) #looking for a dedicated icon
		if png is None: # no dedicated icon found
			if parentMenuEntryID is not None: # check do we have parent menu item that can use for icon
				png = png_cache.get(parentMenuEntryID, None)
		png_cache[entryID] = png
	if png is None:
		png = png_cache.get("missing", None)
		if png is None:
			pngPath = resolveFilename(SCOPE_GUISKIN, "menu/missing.svg")
			png = LoadPixmap(pngPath, cached=True, width=width, height=0 if pngPath.endswith(".svg") else height)
			png_cache["missing"] = png
	return png


class MenuUpdater:
	def __init__(self):
		self.updatedMenuItems = {}

	def addMenuItem(self, id, pos, text, module, screen, weight):
		if not self.updatedMenuAvailable(id):
			self.updatedMenuItems[id] = []
		self.updatedMenuItems[id].append([text, pos, module, screen, weight])

	def delMenuItem(self, id, pos, text, module, screen, weight):
		self.updatedMenuItems[id].remove([text, pos, module, screen, weight])

	def updatedMenuAvailable(self, id):
		return id in self.updatedMenuItems

	def getUpdatedMenu(self, id):
		return self.updatedMenuItems[id]


menuupdater = MenuUpdater()


class MenuSummary(ScreenSummary):
	def __init__(self, session, parent):
		ScreenSummary.__init__(self, session, parent=parent)
		self["entry"] = StaticText("")  # DEBUG: Proposed for new summary screens.
		if self.addWatcher not in self.onShow:
			self.onShow.append(self.addWatcher)
		if self.removeWatcher not in self.onHide:
			self.onHide.append(self.removeWatcher)

	def addWatcher(self):
		if self.selectionChanged not in self.parent["menu"].onSelectionChanged:
			self.parent["menu"].onSelectionChanged.append(self.selectionChanged)
		self.selectionChanged()

	def removeWatcher(self):
		if self.selectionChanged in self.parent["menu"].onSelectionChanged:
			self.parent["menu"].onSelectionChanged.remove(self.selectionChanged)

	def selectionChanged(self):
		selection = self.parent["menu"].getCurrent()
		if selection:
			self["entry"].text = selection[0]  # DEBUG: Proposed for new summary screens.


class Menu(Screen, HelpableScreen, ProtectedScreen):
	ALLOW_SUSPEND = True
	png_cache = {}

	def okbuttonClick(self):
		if self.number:
			if self.menuHorizontal:
				self.horzIndex = self.number - 1
			else:
				self["menu"].setIndex(self.number - 1)
		self.resetNumberKey()
		selection = self.list[self.horzIndex] if self.menuHorizontal else self["menu"].getCurrent()
		if selection and selection[1]:
			selection[1]()

	def execText(self, text):
		exec(text)

	def runScreen(self, arg):
		# arg[0] is the module (as string)
		# arg[1] is Screen inside this module
		#        plus possible arguments, as
		#        string (as we want to reference
		#        stuff which is just imported)
		if arg[0] != "":
			exec("from %s import %s" % (arg[0], arg[1].split(",")[0]))
			self.openDialog(*eval(arg[1]))

	def nothing(self): #dummy
		pass

	def openDialog(self, *dialog): # in every layer needed
		self.session.openWithCallback(self.menuClosed, *dialog)

	def openSetup(self, dialog):
		self.session.openWithCallback(self.menuClosed, Setup, dialog)

	def addMenu(self, destList, node, parent=None):
		requires = node.get("requires")
		if requires:
			if requires[0] == '!':
				if SystemInfo.get(requires[1:], False):
					return
			elif not SystemInfo.get(requires, False):
				return
		# print("[Menu][addMenu] Menu text=", node.get("text", "??"))				
		MenuTitle = str(_(node.get("text", "??")))
		entryID = node.get("entryID", "undefined")
		weight = node.get("weight", 50)
		description = node.get("description", "").encode("UTF-8") or None
		description = description and _(description)
		menupng = MenuEntryPixmap(entryID, self.png_cache, parent)
		x = node.get("flushConfigOnClose")
		if x:
			a = boundFunction(self.session.openWithCallback, self.menuClosedWithConfigFlush, Menu, node)
		else:
			a = boundFunction(self.session.openWithCallback, self.menuClosed, Menu, node)
		#TODO add check if !empty(node.childNodes)
		destList.append((MenuTitle, a, entryID, weight, description, menupng))

	def menuClosedWithConfigFlush(self, *res):
		configfile.save()
		self.menuClosed(*res)

	def menuClosed(self, *res):
		if res and res[0]:
			self.close(True)
		elif len(self.list) == 1:
			self.close()
		else:
			self.createMenuList()

	def addItem(self, destList, node, parent=None):
		requires = node.get("requires")
		if requires:
			if requires[0] == '!':
				if SystemInfo.get(requires[1:], False):
					return
			elif not SystemInfo.get(requires, False):
				return
		conditional = node.get("conditional")
		if conditional and not eval(conditional):
			return
		# print("[Menu][addItem] item text=", node.get("text", "* Undefined *"))
		item_text = str(node.get("text", "* Undefined *"))
		
		if item_text:
			item_text = _(item_text)
		entryID = node.get("entryID", "undefined")
		weight = node.get("weight", 50)
		description = node.get("description", "").encode("UTF-8") or None
		description = description and _(description)
		menupng = MenuEntryPixmap(entryID, self.png_cache, parent)
		for x in node:
			if x.tag == 'screen':
				module = x.get("module")
				screen = x.get("screen")

				if screen is None:
					screen = module

				# print module, screen
				if module:
					module = "Screens." + module
				else:
					module = ""

				# check for arguments. they will be appended to the
				# openDialog call
				args = x.text or ""
				screen += ", " + args

				destList.append((item_text, boundFunction(self.runScreen, (module, screen)), entryID, weight, description, menupng))
				return
			elif x.tag == 'plugin':
				extensions = x.get("extensions")
				system = x.get("system")
				screen = x.get("screen")

				if extensions:
					module = extensions
				elif system:
					module = system

				if screen is None:
					screen = module

				if extensions:
					module = "Plugins.Extensions." + extensions + '.plugin'
				elif system:
					module = "Plugins.SystemPlugins." + system + '.plugin'
				else:
					module = ""

				# check for arguments. they will be appended to the
				# openDialog call
				args = x.text or ""
				screen += ", " + args

				destList.append((item_text, boundFunction(self.runScreen, (module, screen)), entryID, weight, description, menupng))
				return
			elif x.tag == 'code':
				destList.append((item_text, boundFunction(self.execText, x.text), entryID, weight, description, menupng))
				return
			elif x.tag == 'setup':
				id = x.get("id")
				destList.append((item_text, boundFunction(self.openSetup, id), entryID, weight, description, menupng))
				return
		destList.append((item_text, self.nothing, entryID, weight, description, menupng))

	def __init__(self, session, parent):
		self.parentmenu = parent
		Screen.__init__(self, session)
		self.menuHorizontalSkinName = "MenuHorizontal"
		self.menuHorizontal = self.__class__.__name__ != "MenuSort" and config.usage.menu_style.value == "horizontal" and findSkinScreen(self.menuHorizontalSkinName)
		self.onHorizontalSelectionChanged = []
		self["key_blue"] = StaticText("")
		HelpableScreen.__init__(self)
		self.menulength = 0
		if not self.menuHorizontal:
			self["menu"] = List([])
			self["menu"].enableWrapAround = True
		self.createMenuList()

		# for the skin: first try a menu_<menuID>, then Menu
		self.skinName = []
		if self.menuHorizontal:
			if self.menuID:
				self.skinName.append(self.menuHorizontalSkinName + "_" + self.menuID)
			self.skinName.append(self.menuHorizontalSkinName)
		elif self.menuID:
			self.skinName.append("menu_" + self.menuID)
		self.skinName.append("Menu")

		ProtectedScreen.__init__(self)

		self["menuActions"] = HelpableActionMap(self, ["OkCancelActions", "MenuActions"],
		{
			"ok": (self.okbuttonClick, self.okbuttontext if hasattr(self, "okbuttontext") else _("Select the current menu item")),
			"cancel": (self.closeNonRecursive, self.exitbuttontext if hasattr(self, "exitbuttontext") else _("Exit menu")),
			"close": (self.closeRecursive, self.exitbuttontext if hasattr(self, "exitbuttontext") else _("Exit all menus")),
			"menu": (self.closeRecursive, _("Exit all menus")),
		}, prio=0, description=_("Common Menu Actions"))

		if self.__class__.__name__ != "MenuSort":
			self["menuActions2"] = HelpableNumberActionMap(self, ["NumberActions", "ColorActions"],
			{
				"0": (self.keyNumberGlobal, _("Direct menu item selection")),
				"1": (self.keyNumberGlobal, _("Direct menu item selection")),
				"2": (self.keyNumberGlobal, _("Direct menu item selection")),
				"3": (self.keyNumberGlobal, _("Direct menu item selection")),
				"4": (self.keyNumberGlobal, _("Direct menu item selection")),
				"5": (self.keyNumberGlobal, _("Direct menu item selection")),
				"6": (self.keyNumberGlobal, _("Direct menu item selection")),
				"7": (self.keyNumberGlobal, _("Direct menu item selection")),
				"8": (self.keyNumberGlobal, _("Direct menu item selection")),
				"9": (self.keyNumberGlobal, _("Direct menu item selection")),
				"blue": (self.keyBlue, _("Sort menu")),
			}, prio=0, description=_("Common Menu Actions"))
		title = parent.get("title", "")
		title = title and _(title) or _(parent.get("text", ""))
		title = self.__class__.__name__ == "MenuSort" and _("Menusort (%s)") % title or title
		self["title"] = StaticText(title)
		self.setTitle(title)

		self.number = 0
		self.nextNumberTimer = eTimer()
		self.nextNumberTimer.callback.append(self.okbuttonClick)
		if len(self.list) == 1:
			self.onExecBegin.append(self.__onExecBegin)
		if self.menuHorizontal:
			self.initMenuHorizontal()

	def __onExecBegin(self):
		self.onExecBegin.remove(self.__onExecBegin)
		self.okbuttonClick()

	def createMenuList(self):
		if self.__class__.__name__ != "MenuSort":
			self["key_blue"].text = _("Edit menu") if config.usage.menu_sort_mode.value == "user" else ""
		self.list = []
		self.menuID = None
		parentEntryID = None
		for x in self.parentmenu: #walk through the actual nodelist
			if not x.tag:
				continue
			parentEntryID = self.parentmenu.get("entryID", None)
			if x.tag == 'item':
				item_level = int(x.get("level", 0))
				if item_level <= config.usage.setup_level.index:
					self.addItem(self.list, x, parentEntryID)
					count += 1
			elif x.tag == 'menu':
				item_level = int(x.get("level", 0))
				if item_level <= config.usage.setup_level.index:
					self.addMenu(self.list, x, parentEntryID)
					count += 1
			elif x.tag == "id":
				self.menuID = x.get("val")
				count = 0

			if self.menuID is not None:
				# menuupdater?
				if menuupdater.updatedMenuAvailable(self.menuID):
					for x in menuupdater.getUpdatedMenu(self.menuID):
						if x[1] == count:
							description = x.get("description", "").encode("UTF-8") or None
							description = description and _(description)
							menupng = MenuEntryPixmap(self.menuID, self.png_cache, parentEntryID)
							self.list.append((x[0], boundFunction(self.runScreen, (x[2], x[3] + ", ")), x[4], description, menupng))
							count += 1

		if self.menuID is not None:
			# plugins
			for l in plugins.getPluginsForMenu(self.menuID):
				# check if a plugin overrides an existing menu
				plugin_menuid = l[2]
				for x in self.list:
					if x[2] == plugin_menuid:
						self.list.remove(x)
						break
				description = l[4] if len(l) == 5 else plugins.getDescriptionForMenuEntryID(self.menuID, plugin_menuid)
				menupng = MenuEntryPixmap(l[2], self.png_cache, parentEntryID)
				if len(l) > 4 and l[4]:
					
					self.list.append((l[0], boundFunction(l[1], self.session, self.close), l[2], l[3] or 50, description, menupng))
				else:
					self.list.append((l[0], boundFunction(l[1], self.session), l[2], l[3] or 50, description, menupng))

		if "user" in config.usage.menu_sort_mode.value and self.menuID == "mainmenu":
			plugin_list = []
			id_list = []
			for l in plugins.getPlugins([PluginDescriptor.WHERE_PLUGINMENU, PluginDescriptor.WHERE_EXTENSIONSMENU, PluginDescriptor.WHERE_EVENTINFO]):
				l.id = (l.name.lower()).replace(' ', '_')
				if l.id not in id_list:
					id_list.append(l.id)
					plugin_list.append((l.name, boundFunction(l.fnc, self.session), l.id, 200))

		if self.menuID is not None and "user" in config.usage.menu_sort_mode.value:
			self.sub_menu_sort = NoSave(ConfigDictionarySet())
			self.sub_menu_sort.value = config.usage.menu_sort_weight.getConfigValue(self.menuID, "submenu") or {}
			idx = 0
			for x in self.list:
				entry = list(self.list.pop(idx))
				m_weight = self.sub_menu_sort.getConfigValue(entry[2], "sort") or entry[3]
				entry.append(m_weight)
				self.list.insert(idx, tuple(entry))
				self.sub_menu_sort.changeConfigValue(entry[2], "sort", m_weight)
				idx += 1
			self.full_list = list(self.list)

		if config.usage.menu_sort_mode.value == "a_z":
			# Sort alphabetical
			self.list.sort(key=lambda x: x[0].lower())
		elif "user" in config.usage.menu_sort_mode.value:
			self.hide_show_entries()
		else:
			# Sort by Weight
			self.list.sort(key=lambda x: int(x[3]))

		if config.usage.menu_show_numbers.value:
			self.list = [(str(x[0] + 1) + " " + x[1][0], x[1][1], x[1][2]) for x in enumerate(self.list)]

		if self.menulength != len(self.list): # updateList must only be used on a list of the same length. If length is different we call setList.
			self.menulength = len(self.list)
			if not self.menuHorizontal:
				self["menu"].setList(self.list)
		if not self.menuHorizontal:
			self["menu"].updateList(self.list)

	def keyNumberGlobal(self, number):
		self.number = self.number * 10 + number
		if self.number and self.number <= self.menulength:
			if number * 10 > self.menulength or self.number >= 10:
				self.okbuttonClick()
			else:
				self.nextNumberTimer.start(1500, True)
		else:
			self.resetNumberKey()

	def resetNumberKey(self):
		self.nextNumberTimer.stop()
		self.number = 0

	def closeNonRecursive(self):
		self.resetNumberKey()
		self.close(False)

	def closeRecursive(self):
		self.resetNumberKey()
		self.close(True)

	def createSummary(self):
		if not self.menuHorizontal:
			return MenuSummary
		else:
			return MenuHorizontalSummary

	def isProtected(self):
		if config.ParentalControl.setuppinactive.value:
			if config.ParentalControl.config_sections.main_menu.value and not(hasattr(self.session, 'infobar') and self.session.infobar is None):
				return self.menuID == "mainmenu"
			elif config.ParentalControl.config_sections.configuration.value and self.menuID == "setup":
				return True
			elif config.ParentalControl.config_sections.standby_menu.value and self.menuID == "shutdown":
				return True

	def keyBlue(self):
		if "user" in config.usage.menu_sort_mode.value:
			self.session.openWithCallback(self.menuSortCallBack, MenuSort, self.parentmenu)
		else:
			return 0

	def menuSortCallBack(self, key=False):
		self.createMenuList()

	def keyCancel(self):
		self.closeNonRecursive()

	def hide_show_entries(self):
		self.list = []
		for entry in self.full_list:
			if not self.sub_menu_sort.getConfigValue(entry[2], "hidden"):
				self.list.append(entry)
		if not self.list:
			self.list.append(('', None, 'dummy', '10', 10))
		self.list.sort(key=lambda listweight: int(listweight[4]))

	# for horizontal menu
	
	def updateMenuHorz(self):
		i = self.horzIndex
		L = self.menulength
		self["label1"].setText(self.list[(i-2)%L][0] if L > 3 else "")
		self["label2"].setText(self.list[(i-1)%L][0] if L > 1 else "")
		self["label3"].setText(self.list[i][0])
		self["label4"].setText(self.list[(i+1)%L][0] if L > 1 else "")
		self["label5"].setText(self.list[(i+2)%L][0] if L > 3 else "")
		
	def keyLeftHorz(self):
		self.horzIndex = (self.horzIndex - 1) % self.menulength
		self.updateMenuHorz()
		self.horizontalSelectionChanged()

	def keyRightHorz(self):
		self.horzIndex = (self.horzIndex + 1) % self.menulength
		self.updateMenuHorz()
		self.horizontalSelectionChanged()

	def horizontalSelectionChanged(self):
		for x in self.onHorizontalSelectionChanged:
			if callable(x):
				x()		

	def initMenuHorizontal(self):
		self["label1"] = StaticText()
		self["label2"] = StaticText()
		self["label3"] = StaticText()
		self["label4"] = StaticText()
		self["label5"] = StaticText()
		self["menuActions3"] = HelpableActionMap(self, ["OkCancelActions", "DirectionActions"],
		{
			"left": (self.keyLeftHorz, _("Scroll menu")),
			"right": (self.keyRightHorz, _("Scroll menu")),
		}, prio=0, description=_("Common Menu Actions"))
		self["menuActions3"].setEnabled(bool(self.menulength))
		if self.menulength:
			self.horzIndex = 0
			self.updateMenuHorz()


class MenuHorizontalSummary(ScreenSummary):
	def __init__(self, session, parent):
		ScreenSummary.__init__(self, session, parent=parent)
		self.skinName =["MenuHorizontalSummary"]
		self["title"] = StaticText(self.parent.title)
		self["entry"] = StaticText()
		if self.addWatcher not in self.onShow:
			self.onShow.append(self.addWatcher)
		if self.removeWatcher not in self.onHide:
			self.onHide.append(self.removeWatcher)

	def addWatcher(self):
		if self.selectionChanged not in self.parent.onHorizontalSelectionChanged:
			self.parent.onHorizontalSelectionChanged.append(self.selectionChanged)
		self.selectionChanged()

	def removeWatcher(self):
		if self.selectionChanged in self.parent.onHorizontalSelectionChanged:
			self.parent.onHorizontalSelectionChanged.remove(self.selectionChanged)

	def selectionChanged(self):
		if self.parent.list:
			self["entry"].text = self.parent.list[self.parent.horzIndex][0]


class MenuSort(Menu):
	def __init__(self, session, parentmenu):
		self.somethingChanged = False
		self.okbuttontext = _("Toggle show/hide of the current selection")
		self.exitbuttontext = _("Exit Menusort")
		Menu.__init__(self, session, parentmenu)
		self.skinName = ["MenuSort", "Menu"]
		self["key_red"] = StaticText(_("Exit"))
		self["key_green"] = StaticText(_("Save changes"))
		self["key_yellow"] = StaticText(_("Toggle show/hide"))
		self["key_blue"] = StaticText(_("Reset order (All)"))
		self["key_previous"] = StaticText(_("PREVIOUS"))
		self["key_next"] = StaticText(_("NEXT"))
		self["menu"].onSelectionChanged.append(self.selectionChanged)

		self["MoveActions"] = HelpableActionMap(self, ["DirectionActions"],
		{
			"shiftUp": (boundFunction(self.moveChoosen, -1), _("Move menu item up")),
			"shiftDown": (boundFunction(self.moveChoosen, +1), _("Move menu item down")),
		}, prio=-1, description=_("Common Menu Actions"))

		self["EditActions"] = HelpableActionMap(self, ["ColorActions"],
		{
			"red": (self.closeMenuSort, self.exitbuttontext),
			"green": (self.keySave, _("Save and exit")),
			"yellow": (self.keyToggleShowHide, self.okbuttontext),
			"blue": (self.resetSortOrder, _("Restore default sort")),
		}, prio=-1, description=_("Common Menu Actions"))

		self.onLayoutFinish.append(self.selectionChanged)

	def isProtected(self):
		return config.ParentalControl.setuppinactive.value and config.ParentalControl.config_sections.menu_sort.value

	def resetSortOrder(self, key=None):
		config.usage.menu_sort_weight.value = config.usage.menu_sort_weight.default
		config.usage.menu_sort_weight.save()
		self.createMenuList()

	def hide_show_entries(self):
		self.list = list(self.full_list)
		if not self.list:
			self.list.append(('', None, 'dummy', '10', 10))
		self.list.sort(key=lambda listweight: int(listweight[4]))

	def selectionChanged(self):
		selection = self["menu"].getCurrent() and len(self["menu"].getCurrent()) > 2 and self["menu"].getCurrent()[2] or ""
		if self.sub_menu_sort.getConfigValue(selection, "hidden"):
			self["key_yellow"].setText(_("Show"))
		else:
			self["key_yellow"].setText(_("Hide"))

	def keySave(self):
		if self.somethingChanged:
			i = 10
			idx = 0
			for x in self.list:
				self.sub_menu_sort.changeConfigValue(x[2], "sort", i)
				if len(x) >= 5:
					entry = list(x)
					entry[4] = i
					entry = tuple(entry)
					self.list.pop(idx)
					self.list.insert(idx, entry)
				i += 10
				idx += 1
			config.usage.menu_sort_weight.changeConfigValue(self.menuID, "submenu", self.sub_menu_sort.value)
			config.usage.menu_sort_weight.save()
		self.close()

	def closeNonRecursive(self):
		self.closeMenuSort()

	def closeRecursive(self):
		self.closeMenuSort()

	def closeMenuSort(self):
		if self.somethingChanged:
			self.session.openWithCallback(self.cancelConfirm, MessageBox, _("Really close without saving settings?"))
		else:
			self.close()

	def cancelConfirm(self, result):
		if result:
			config.usage.menu_sort_weight.cancel()
			self.close()

	def okbuttonClick(self):
		self.keyToggleShowHide()

	def keyToggleShowHide(self):
		self.somethingChanged = True
		selection = self["menu"].getCurrent()[2]
		if self.sub_menu_sort.getConfigValue(selection, "hidden"):
			self.sub_menu_sort.removeConfigValue(selection, "hidden")
			self["key_yellow"].setText(_("Hide"))
		else:
			self.sub_menu_sort.changeConfigValue(selection, "hidden", 1)
			self["key_yellow"].setText(_("Show"))

	def moveChoosen(self, direction):
		self.somethingChanged = True
		currentIndex = self["menu"].getSelectedIndex()
		swapIndex = (currentIndex + direction) % len(self["menu"].list)
		self["menu"].list[currentIndex], self["menu"].list[swapIndex] = self["menu"].list[swapIndex], self["menu"].list[currentIndex]
		self["menu"].updateList(self["menu"].list)
		if direction > 0:
			self["menu"].down()
		else:
			self["menu"].up()


class MainMenu(Menu):
	#add file load functions for the xml-file

	def __init__(self, *x):
		Menu.__init__(self, *x)
