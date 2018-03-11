from Screens.Screen import Screen
from Components.ActionMap import NumberActionMap, ActionMap
from Components.config import config, ConfigNothing, ConfigYesNo, ConfigSelection, ConfigText, ConfigPassword
from Tools.Directories import resolveFilename, SCOPE_CURRENT_PLUGIN
from Components.SystemInfo import SystemInfo
from Components.ConfigList import ConfigListScreen
from Components.Pixmap import Pixmap
from Components.Sources.StaticText import StaticText
from Components.Label import Label
from Components.Sources.Boolean import Boolean

from enigma import eEnv
from gettext import dgettext
from boxbranding import getMachineBrand, getMachineName

import xml.etree.cElementTree

def setupdom(plugin=None):
	# read the setupmenu
	if plugin:
		# first we search in the current path
		setupfile = file(resolveFilename(SCOPE_CURRENT_PLUGIN, plugin + '/setup.xml'), 'r')
	else:
		# if not found in the current path, we use the global datadir-path
		setupfile = file(eEnv.resolve('${datadir}/enigma2/setup.xml'), 'r')
	setupfiledom = xml.etree.cElementTree.parse(setupfile)
	setupfile.close()
	return setupfiledom

def getConfigMenuItem(configElement):
	for item in setupdom().getroot().findall('./setup/item/.'):
		if item.text == configElement:
			return _(item.attrib["text"]), eval(configElement)
	return "", None


class SetupSummary(Screen):
	def __init__(self, session, parent):
		Screen.__init__(self, session, parent = parent)
		self["SetupTitle"] = StaticText(_(parent.setup_title))
		self["SetupEntry"] = StaticText("")
		self["SetupValue"] = StaticText("")
		if hasattr(self.parent,"onChangedEntry"):
			self.onShow.append(self.addWatcher)
			self.onHide.append(self.removeWatcher)

	def addWatcher(self):
		if hasattr(self.parent,"onChangedEntry"):
			self.parent.onChangedEntry.append(self.selectionChanged)
			self.parent["config"].onSelectionChanged.append(self.selectionChanged)
			self.selectionChanged()

	def removeWatcher(self):
		if hasattr(self.parent,"onChangedEntry"):
			self.parent.onChangedEntry.remove(self.selectionChanged)
			self.parent["config"].onSelectionChanged.remove(self.selectionChanged)

	def selectionChanged(self):
		self["SetupEntry"].text = self.parent.getCurrentEntry()
		self["SetupValue"].text = self.parent.getCurrentValue()
		if hasattr(self.parent,"getCurrentDescription") and "description" in self.parent:
			self.parent["description"].text = self.parent.getCurrentDescription()
		if self.parent.has_key('footnote'):
			if self.parent.getCurrentEntry().endswith('*'):
				self.parent['footnote'].text = (_("* = Restart Required"))
			else:
				self.parent['footnote'].text = ("")

class Setup(ConfigListScreen, Screen):

	ALLOW_SUSPEND = True

	def removeNotifier(self):
		config.usage.setup_level.notifiers.remove(self.levelChanged)

	def levelChanged(self, configElement):
		list = []
		self.refill(list)
		self["config"].setList(list)

	def refill(self, list):
		xmldata = setupdom(self.plugin).getroot()
		for x in xmldata.findall("setup"):
			if x.get("key") != self.setup:
				continue
			self.addItems(list, x)
			if config.usage.show_menupath.value in ('large', 'small') and x.get("titleshort", "").encode("UTF-8") != "":
				self.setup_title = x.get("titleshort", "").encode("UTF-8")
			else:
				self.setup_title = x.get("title", "").encode("UTF-8")
			self.seperation = int(x.get('separation', '0'))

	def __init__(self, session, setup, plugin=None, menu_path=None, PluginLanguageDomain=None):
		Screen.__init__(self, session)
		# for the skin: first try a setup_<setupID>, then Setup
		self.skinName = ["setup_" + setup, "Setup" ]

		self["menu_path_compressed"] = StaticText()
		self['footnote'] = Label()
		self["HelpWindow"] = Pixmap()
		self["HelpWindow"].hide()
		self["VKeyIcon"] = Boolean(False)
		self.onChangedEntry = [ ]
		self.item = None
		self.setup = setup
		self.plugin = plugin
		self.PluginLanguageDomain = PluginLanguageDomain
		self.menu_path = menu_path
		list = []

		self.refill(list)

		ConfigListScreen.__init__(self, list, session = session, on_change = self.changedEntry)
		self.createSetup()

		#check for list.entries > 0 else self.close
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Save"))
		self["description"] = Label("")

		self["actions"] = NumberActionMap(["SetupActions", "MenuActions"],
			{
				"cancel": self.keyCancel,
				"save": self.keySave,
				"menu": self.closeRecursive,
			}, -2)

		if not self.handleInputHelpers in self["config"].onSelectionChanged:
			self["config"].onSelectionChanged.append(self.handleInputHelpers)
		self.changedEntry()
		self.onLayoutFinish.append(self.layoutFinished)

	def createSetup(self):
		list = []
		self.refill(list)
		self["config"].setList(list)
		if config.usage.sort_settings.value:
			self["config"].list.sort()
		self.moveToItem(self.item)

	def getIndexFromItem(self, item):
		if item is not None:
			for x in range(len(self["config"].list)):
				if self["config"].list[x][0] == item[0]:
					return x
		return None

	def moveToItem(self, item):
		newIdx = self.getIndexFromItem(item)
		if newIdx is None:
			newIdx = 0
		self["config"].setCurrentIndex(newIdx)

	def layoutFinished(self):
		if config.usage.show_menupath.value == 'large' and self.menu_path:
			title = self.menu_path + _(self.setup_title)
			self["menu_path_compressed"].setText("")
		elif config.usage.show_menupath.value == 'small' and self.menu_path:
			title = _(self.setup_title)
			self["menu_path_compressed"].setText(self.menu_path + " >" if not self.menu_path.endswith(' / ') else self.menu_path[:-3] + " >" or "")
		else:
			title = _(self.setup_title)
			self["menu_path_compressed"].setText("")
		self.setTitle(title)

	# for summary:
	def changedEntry(self):
		self.item = self["config"].getCurrent()
		try:
			if isinstance(self["config"].getCurrent()[1], ConfigYesNo) or isinstance(self["config"].getCurrent()[1], ConfigSelection):
				self.createSetup()
		except:
			pass

	def addItems(self, list, parentNode):
		for x in parentNode:
			if not x.tag:
				continue
			if x.tag == 'item':
				item_level = int(x.get("level", 0))

				if not self.levelChanged in config.usage.setup_level.notifiers:
					config.usage.setup_level.notifiers.append(self.levelChanged)
					self.onClose.append(self.removeNotifier)

				if item_level > config.usage.setup_level.index:
					continue

				requires = x.get("requires")
				if requires and requires.startswith('config.'):
					item = eval(requires or "")
					if item.value and not item.value == "0":
						SystemInfo[requires] = True
					else:
						SystemInfo[requires] = False

				if requires and not SystemInfo.get(requires, False):
					continue

				if self.PluginLanguageDomain:
					item_text = dgettext(self.PluginLanguageDomain, x.get("text", "??").encode("UTF-8"))
					item_description = dgettext(self.PluginLanguageDomain, x.get("description", " ").encode("UTF-8"))
				else:
					item_text = _(x.get("text", "??").encode("UTF-8"))
					item_description = _(x.get("description", " ").encode("UTF-8"))

				item_text = item_text.replace("%s %s","%s %s" % (getMachineBrand(), getMachineName()))
				item_description = item_description.replace("%s %s","%s %s" % (getMachineBrand(), getMachineName()))
				b = eval(x.text or "")
				if b == "":
					continue
				#add to configlist
				item = b
				# the first b is the item itself, ignored by the configList.
				# the second one is converted to string.
				if not isinstance(item, ConfigNothing):
					list.append((item_text, item, item_description))

def getSetupTitle(id):
	xmldata = setupdom().getroot()
	id = str(id)
	title = ""
	for x in xmldata.findall("setup"):
		if x.get("key") == id:
			title = x.get("titleshort", "").encode("UTF-8")
			if title == "":
				title = x.get("title", "Settings").encode("UTF-8")
	if title == "":
		print "[Setup] Error: Setup ID '%s' not found in setup file!" % id
		title = "** Setup error: '%s' section not found! **" % id
	return _(title)
