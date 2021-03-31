from Screens.HelpMenu import HelpableScreen
from Screens.Screen import Screen, ScreenSummary
from Screens.ParentalControlSetup import ProtectedScreen
from Components.Sources.List import List
from Components.ActionMap import HelpableNumberActionMap
from Components.Sources.StaticText import StaticText
from Components.config import configfile
from Components.PluginComponent import plugins
from Components.config import config
from Components.NimManager import nimmanager
from Components.SystemInfo import SystemInfo

from Tools.BoundFunction import boundFunction
from Tools.Directories import resolveFilename, SCOPE_SKIN
from enigma import eTimer

import xml.etree.cElementTree

from Screens.Setup import Setup

# read the menu
file = open(resolveFilename(SCOPE_SKIN, 'menu.xml'), 'r')
mdom = xml.etree.cElementTree.parse(file)
file.close()


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

	def okbuttonClick(self):
		if self.number:
			self["menu"].setIndex(self.number - 1)
		self.resetNumberKey()
		selection = self["menu"].getCurrent()
		if selection is not None:
			selection[1]()

	def execText(self, text):
		exec text

	def runScreen(self, arg):
		# arg[0] is the module (as string)
		# arg[1] is Screen inside this module
		#        plus possible arguments, as
		#        string (as we want to reference
		#        stuff which is just imported)
		# FIXME. somehow
		if arg[0] != "":
			exec "from " + arg[0] + " import *"
		self.openDialog(*eval(arg[1]))

	def nothing(self): #dummy
		pass

	def openDialog(self, *dialog): # in every layer needed
		self.session.openWithCallback(self.menuClosed, *dialog)

	def openSetup(self, dialog):
		self.session.openWithCallback(self.menuClosed, Setup, dialog)

	def addMenu(self, destList, node):
		requires = node.get("requires")
		if requires:
			if requires[0] == '!':
				if SystemInfo.get(requires[1:], False):
					return
			elif not SystemInfo.get(requires, False):
				return
		MenuTitle = _(node.get("text", "??").encode("UTF-8"))
		entryID = node.get("entryID", "undefined")
		weight = node.get("weight", 50)
		x = node.get("flushConfigOnClose")
		if x:
			a = boundFunction(self.session.openWithCallback, self.menuClosedWithConfigFlush, Menu, node)
		else:
			a = boundFunction(self.session.openWithCallback, self.menuClosed, Menu, node)
		#TODO add check if !empty(node.childNodes)
		destList.append((MenuTitle, a, entryID, weight))

	def menuClosedWithConfigFlush(self, *res):
		configfile.save()
		self.menuClosed(*res)

	def menuClosed(self, *res):
		if res and res[0]:
			self.close(True)

	def addItem(self, destList, node):
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
		item_text = node.get("text", "* Undefined *").encode("UTF-8")
		if item_text:
			item_text = _(item_text)
		entryID = node.get("entryID", "undefined")
		weight = node.get("weight", 50)
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

				destList.append((item_text, boundFunction(self.runScreen, (module, screen)), entryID, weight))
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

				destList.append((item_text, boundFunction(self.runScreen, (module, screen)), entryID, weight))
				return
			elif x.tag == 'code':
				destList.append((item_text, boundFunction(self.execText, x.text), entryID, weight))
				return
			elif x.tag == 'setup':
				id = x.get("id")
				destList.append((item_text, boundFunction(self.openSetup, id), entryID, weight))
				return
		destList.append((item_text, self.nothing, entryID, weight))


	def __init__(self, session, parent):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		list = []

		menuID = None
		for x in parent: #walk through the actual nodelist
			if not x.tag:
				continue
			if x.tag == 'item':
				item_level = int(x.get("level", 0))
				if item_level <= config.usage.setup_level.index:
					self.addItem(list, x)
					count += 1
			elif x.tag == 'menu':
				self.addMenu(list, x)
				count += 1
			elif x.tag == "id":
				menuID = x.get("val")
				count = 0

			if menuID is not None:
				# menuupdater?
				if menuupdater.updatedMenuAvailable(menuID):
					for x in menuupdater.getUpdatedMenu(menuID):
						if x[1] == count:
							list.append((x[0], boundFunction(self.runScreen, (x[2], x[3] + ", ")), x[4]))
							count += 1

		if menuID is not None:
			# plugins
			for l in plugins.getPluginsForMenu(menuID):
				# check if a plugin overrides an existing menu
				plugin_menuid = l[2]
				for x in list:
					if x[2] == plugin_menuid:
						list.remove(x)
						break
				if len(l) > 4 and l[4]:
					list.append((l[0], boundFunction(l[1], self.session, self.close), l[2], l[3] or 50))
				else:
					list.append((l[0], boundFunction(l[1], self.session), l[2], l[3] or 50))

		# for the skin: first try a menu_<menuID>, then Menu
		self.skinName = [ ]
		if menuID is not None:
			self.skinName.append("menu_" + menuID)
		self.skinName.append("Menu")
		self.menuID = menuID
		ProtectedScreen.__init__(self)

		# Sort by Weight
		if config.usage.sort_menus.value:
			list.sort()
		else:
			list.sort(key=lambda x: int(x[3]))

		if config.usage.menu_show_numbers.value:
			list = [(str(x[0] + 1) + "  " +x[1][0], x[1][1], x[1][2], x[1][3]) for x in enumerate(list)]

		self["menu"] = List(list)

		# self["menuActions"] = HelpableNumberActionMap(self, ["OkCancelActions", "MenuActions", "NumberActions"], {
		self["menuActions"] = HelpableNumberActionMap(self, ["OkCancelActions", "NumberActions"], {
			"ok": (self.okbuttonClick, _("Select the current menu item")),
			"cancel": (self.closeNonRecursive, _("Exit menu")),
			"close": (self.closeRecursive, _("Exit all menus")),
			# "menu": (self.closeRecursive, _("Exit all menus")),
			"1": (self.keyNumberGlobal, _("Direct menu item selection")),
			"2": (self.keyNumberGlobal, _("Direct menu item selection")),
			"3": (self.keyNumberGlobal, _("Direct menu item selection")),
			"4": (self.keyNumberGlobal, _("Direct menu item selection")),
			"5": (self.keyNumberGlobal, _("Direct menu item selection")),
			"6": (self.keyNumberGlobal, _("Direct menu item selection")),
			"7": (self.keyNumberGlobal, _("Direct menu item selection")),
			"8": (self.keyNumberGlobal, _("Direct menu item selection")),
			"9": (self.keyNumberGlobal, _("Direct menu item selection")),
			"0": (self.keyNumberGlobal, _("Direct menu item selection"))
		}, prio=0, description=_("Common Menu Actions"))

		a = parent.get("title", "").encode("UTF-8") or None
		a = a and _(a) or _(parent.get("text", "").encode("UTF-8"))
		self.setTitle(a)

		self.number = 0
		self.nextNumberTimer = eTimer()
		self.nextNumberTimer.callback.append(self.okbuttonClick)

	def keyNumberGlobal(self, number):
		self.number = self.number * 10 + number
		if self.number and self.number <= len(self["menu"].list):
			if number * 10 > len(self["menu"].list) or self.number >= 10:
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
			if config.ParentalControl.config_sections.main_menu.value and not(hasattr(self.session, 'infobar') and self.session.infobar is None):
				return self.menuID == "mainmenu"
			elif config.ParentalControl.config_sections.configuration.value and self.menuID == "setup":
				return True
			elif config.ParentalControl.config_sections.standby_menu.value and self.menuID == "shutdown":
				return True

class MainMenu(Menu):
	#add file load functions for the xml-file

	def __init__(self, *x):
		self.skinName = "Menu"
		Menu.__init__(self, *x)
