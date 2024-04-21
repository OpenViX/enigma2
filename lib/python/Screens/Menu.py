from skin import findSkinScreen, parameters, menus, menuicons

from Components.ActionMap import HelpableNumberActionMap, HelpableActionMap
from Components.config import config, ConfigDictionarySet, configfile, NoSave
from Components.NimManager import nimmanager  # noqa: F401  # used in menu.xml conditionals
from Components.Pixmap import Pixmap
from Components.PluginComponent import plugins
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Components.SystemInfo import SystemInfo

from Plugins.Plugin import PluginDescriptor

from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Screens.ParentalControlSetup import ProtectedScreen
from Screens.Screen import Screen, ScreenSummary

from Tools.BoundFunction import boundFunction
from Tools.Directories import resolveFilename, SCOPE_SKINS, SCOPE_CURRENT_SKIN
from Tools.LoadPixmap import LoadPixmap

from enigma import eTimer

import xml.etree.cElementTree

from Screens.Setup import Setup

# read the menu... recovery.xml is an abreviated version of menu.xml used for slot 0 (recovery image).
file = open(resolveFilename(SCOPE_SKINS, 'menu.xml' if SystemInfo["MultiBootSlot"] != 0 else 'recovery.xml'), 'r')
mdom = xml.etree.cElementTree.parse(file)
file.close()


def MenuEntryPixmap(key, png_cache):
	if not menuicons:
		return None
	w, h = parameters.get("MenuIconSize", (50, 50))
	png = png_cache.get(key)
	if png is None:  # no cached entry
		pngPath = menuicons.get(key, menuicons.get("default", ""))
		if pngPath:
			png = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, pngPath), cached=True, width=w, height=0 if pngPath.endswith(".svg") else h)
	return png


class MenuSummary(ScreenSummary):
	def __init__(self, session, parent):
		ScreenSummary.__init__(self, session, parent=parent)


class Menu(Screen, HelpableScreen, ProtectedScreen):
	ALLOW_SUSPEND = True
	png_cache = {}

	def okbuttonClick(self):
		if self.number:
			self["menu"].setIndex(self.number - 1)
		self.resetNumberKey()
		selection = self["menu"].getCurrent()
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

	def nothing(self):  # dummy
		pass

	def openDialog(self, *dialog):  # in every layer needed
		self.session.openWithCallback(self.menuClosed, *dialog)

	def openSetup(self, dialog):
		self.session.openWithCallback(self.menuClosed, Setup, dialog)

	def addMenu(self, destList, node):
		if not (key := node.get("key")):
			return
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
		menu_text = _(x) if (x := node.get("text")) else "* fix me *"
		weight = node.get("weight", 50)
		description = _(x) if (x := node.get("description", "")) else None
		menupng = MenuEntryPixmap(key, self.png_cache)
		x = node.get("flushConfigOnClose")
		if x:
			a = boundFunction(self.session.openWithCallback, self.menuClosedWithConfigFlush, Menu, node)
		else:
			a = boundFunction(self.session.openWithCallback, self.menuClosed, Menu, node)
		# TODO add check if !empty(node.childNodes)
		destList.append((menu_text, a, key, weight, description, menupng))

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

	def addItem(self, destList, node):
		if not (key := node.get("key")):
			return
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
		item_text = _(x) if (x := node.get("text")) else "* fix me *"
		weight = node.get("weight", 50)
		description = _(x) if (x := node.get("description", "")) else None
		menupng = MenuEntryPixmap(key, self.png_cache)
		for x in node:
			if x.tag == 'screen':
				module = x.get("module")
				screen = x.get("screen")

				if screen is None:
					screen = module

				if module:
					module = "Screens." + module
				else:
					module = ""

				# check for arguments. they will be appended to the
				# openDialog call
				args = x.text or ""
				screen += ", " + args

				destList.append((item_text, boundFunction(self.runScreen, (module, screen)), key, weight, description, menupng))
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

				destList.append((item_text, boundFunction(self.runScreen, (module, screen)), key, weight, description, menupng))
				return
			elif x.tag == 'code':
				destList.append((item_text, boundFunction(self.execText, x.text), key, weight, description, menupng))
				return
			elif x.tag == 'setup':
				id = x.get("id")
				destList.append((item_text, boundFunction(self.openSetup, id), key, weight, description, menupng))
				return
		destList.append((item_text, self.nothing, key, weight, description, menupng))

	def __init__(self, session, parent):
		self.parentmenu = parent
		Screen.__init__(self, session)
		self.menuHorizontalSkinName = "MenuHorizontal"
		self.menuHorizontal = self.__class__.__name__ != "MenuSort" and config.usage.menu_style.value == "horizontal" and findSkinScreen(self.menuHorizontalSkinName)
		self.onHorizontalSelectionChanged = []
		self["key_blue"] = StaticText("")
		HelpableScreen.__init__(self)
		self.menulength = 0
		self["menu"] = List([])
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
		self.loadMenuImage()

		self.number = 0
		self.nextNumberTimer = eTimer()
		self.nextNumberTimer.callback.append(self.okbuttonClick)
		if len(self.list) == 1:
			self.onExecBegin.append(self.__onExecBegin)
		if self.layoutFinished not in self.onLayoutFinish:
			self.onLayoutFinish.append(self.layoutFinished)

	def __onExecBegin(self):
		self.onExecBegin.remove(self.__onExecBegin)
		self.okbuttonClick()

	def layoutFinished(self):
		self.screenContentChanged()
		if self.menuImage and "menuimage" in self:
			self["menuimage"].instance.setPixmap(self.menuImage)

	def loadMenuImage(self):
		self.menuImage = None
		if menus and self.menuID:
			menuImage = menus.get(self.menuID, menus.get("default", ""))
			if menuImage:
				self.menuImage = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, menuImage))
				if self.menuImage:
					self["menuimage"] = Pixmap()

	def createMenuList(self):
		if self.__class__.__name__ != "MenuSort":
			self["key_blue"].text = _("Edit menu") if config.usage.menu_sort_mode.value == "user" else ""

		self.menuID = self.parentmenu.get("key")
		self.list = []
		for x in self.parentmenu:  # walk through the actual nodelist
			if not x.tag:
				continue
			if x.tag == 'item':
				if int(x.get("level", 0)) <= config.usage.setup_level.index:
					self.addItem(self.list, x)
			elif x.tag == 'menu':
				if int(x.get("level", 0)) <= config.usage.setup_level.index:
					self.addMenu(self.list, x)

		if self.menuID is not None:
			# plugins
			for plugin, description in plugins.getPluginsForMenuWithDescription(self.menuID):
				# check if a plugin overrides an existing menu
				plugin_menuid = plugin[2]
				for x in self.list:
					if x[2] == plugin_menuid:
						self.list.remove(x)
						break
				menupng = MenuEntryPixmap(plugin[2], self.png_cache)
				self.list.append((plugin[0], boundFunction(plugin[1], self.session, close=self.close), plugin[2], plugin[3] or 50, description, menupng))

		if "user" in config.usage.menu_sort_mode.value and self.menuID == "mainmenu":
			plugin_list = []
			id_list = []
			for plugin in plugins.getPlugins([PluginDescriptor.WHERE_PLUGINMENU, PluginDescriptor.WHERE_EXTENSIONSMENU, PluginDescriptor.WHERE_EVENTINFO]):
				plugin.id = (plugin.name.lower()).replace(' ', '_')
				if plugin.id not in id_list:
					id_list.append(plugin.id)
					plugin_list.append((plugin.name, boundFunction(plugin.fnc, self.session), plugin.id, 200))

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

		if self.menulength != len(self.list):  # updateList must only be used on a list of the same length. If length is different we call setList.
			self.menulength = len(self.list)
			self["menu"].setList(self.list)
		self["menu"].updateList(self.list)
		self.screenContentChanged()

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
		return MenuSummary

	def isProtected(self):
		if config.ParentalControl.setuppinactive.value:
			if config.ParentalControl.config_sections.main_menu.value and not (hasattr(self.session, 'infobar') and self.session.infobar is None):
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
			self.list.append(('', None, 'dummy', '10', None, None, 10))
		self.list.sort(key=lambda listweight: int(listweight[-1]))


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
			self.list.append(('', None, 'dummy', '10', None, None, 10))
		self.list.sort(key=lambda listweight: int(listweight[-1]))

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
	# add file load functions for the xml-file

	def __init__(self, *x):
		Menu.__init__(self, *x)
