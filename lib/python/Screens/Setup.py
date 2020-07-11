import xml.etree.cElementTree

from boxbranding import getMachineBrand, getMachineName
from enigma import eEnv
from gettext import dgettext

from Components.ActionMap import NumberActionMap
from Components.config import ConfigBoolean, ConfigNothing, ConfigSelection, config
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.SystemInfo import SystemInfo
from Components.Sources.Boolean import Boolean
from Components.Sources.StaticText import StaticText
from Screens.Screen import Screen
from Tools.Directories import SCOPE_CURRENT_PLUGIN, resolveFilename


class SetupError(Exception):
	def __init__(self, message):
		self.msg = message

	def __str__(self):
		return self.msg


class Setup(ConfigListScreen, Screen):
	ALLOW_SUSPEND = True

	def __init__(self, session, setup, plugin=None, PluginLanguageDomain=None):
		Screen.__init__(self, session)
		# for the skin: first try a setup_<setupID>, then Setup
		self.skinName = ["setup_" + setup, "Setup"]
		self["footnote"] = Label()
		self["HelpWindow"] = Pixmap()
		self["HelpWindow"].hide()
		self["VKeyIcon"] = Boolean(False)
		self.onChangedEntry = []
		self.item = None
		self.list = []
		self.force_update_list = False
		self.plugin = plugin
		self.PluginLanguageDomain = PluginLanguageDomain
		self.setup = {}
		xmldata = setupdom(self.plugin).getroot()
		for x in xmldata.findall("setup"):
			if x.get("key") == setup:
				self.setup = x
				break
		if config.usage.show_menupath.value in ("large", "small") and x.get("titleshort", "").encode("UTF-8") != "":
			title = x.get("titleshort", "").encode("UTF-8")
		else:
			title = x.get("title", "").encode("UTF-8")
		title = _("Setup" if title == "" else title)
		self.setTitle(title)
		self.seperation = int(self.setup.get("separation", "0"))
		ConfigListScreen.__init__(self, self.list, session=session, on_change=self.changedEntry)
		self.createSetupList()
		self["config"].onSelectionChanged.append(self.__onSelectionChanged)
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Save"))
		self["description"] = Label("")
		self["actions"] = NumberActionMap(["SetupActions", "MenuActions"], {
			"cancel": self.keyCancel,
			"save": self.keySave,
			"menu": self.closeRecursive,
		}, -2)
		if self.handleInputHelpers not in self["config"].onSelectionChanged:
			self["config"].onSelectionChanged.append(self.handleInputHelpers)
		self.changedEntry()

	def createSetupList(self):
		currentItem = self["config"].getCurrent()
		self.list = []
		for x in self.setup:
			if not x.tag:
				continue
			if x.tag == "item":
				item_level = int(x.get("level", 0))
				if item_level > config.usage.setup_level.index:
					continue
				requires = x.get("requires")
				if requires and not requires.startswith("config."):
					if requires.startswith("!"):
						if SystemInfo.get(requires[1:], False):
							continue
					elif not SystemInfo.get(requires, False):
						continue
				conditional = x.get("conditional")
				if conditional and not eval(conditional):
					continue
				# this block is just for backwards compatibility
				if requires and requires.startswith("config."):
					item = eval(requires)
					if not (item.value and not item.value == "0"):
						continue
				if self.PluginLanguageDomain:
					item_text = dgettext(self.PluginLanguageDomain, x.get("text", "??").encode("UTF-8"))
					item_description = dgettext(self.PluginLanguageDomain, x.get("description", " ").encode("UTF-8"))
				else:
					item_text = _(x.get("text", "??").encode("UTF-8"))
					item_description = _(x.get("description", " ").encode("UTF-8"))
				item_text = item_text.replace("%s %s", "%s %s" % (getMachineBrand(), getMachineName()))
				item_description = item_description.replace("%s %s", "%s %s" % (getMachineBrand(), getMachineName()))
				b = eval(x.text or "")
				if b == "":
					continue
				# add to configlist
				item = b
				# the first b is the item itself, ignored by the configList.
				# the second one is converted to string.
				if not isinstance(item, ConfigNothing):
					self.list.append((item_text, item, item_description))
		self["config"].setList(self.list)
		if config.usage.sort_settings.value:
			self["config"].list.sort()
		self.moveToItem(currentItem)

	def moveToItem(self, item):
		if item != self["config"].getCurrent():
			self["config"].setCurrentIndex(self.getIndexFromItem(item))

	def getIndexFromItem(self, item):
		return self["config"].list.index(item) if item in self["config"].list else 0

	def changedEntry(self):
		if self["config"].getCurrent() and (isinstance(self["config"].getCurrent()[1], ConfigBoolean) or isinstance(self["config"].getCurrent()[1], ConfigSelection)):
			self.createSetupList()

	def __onSelectionChanged(self):
		if self.force_update_list:
			self["config"].onSelectionChanged.remove(self.__onSelectionChanged)
			self.createSetupList()
			self["config"].onSelectionChanged.append(self.__onSelectionChanged)
			self.force_update_list = False
		if not (isinstance(self["config"].getCurrent()[1], ConfigBoolean) or isinstance(self["config"].getCurrent()[1], ConfigSelection)):
			self.force_update_list = True

	def run(self):
		self.keySave()


class SetupSummary(Screen):
	def __init__(self, session, parent):
		Screen.__init__(self, session, parent=parent)
		self["SetupTitle"] = StaticText(parent.getTitle())
		self["SetupEntry"] = StaticText("")
		self["SetupValue"] = StaticText("")
		if hasattr(self.parent, "onChangedEntry"):
			self.onShow.append(self.addWatcher)
			self.onHide.append(self.removeWatcher)

	def addWatcher(self):
		if hasattr(self.parent, "onChangedEntry"):
			self.parent.onChangedEntry.append(self.selectionChanged)
			self.parent["config"].onSelectionChanged.append(self.selectionChanged)
			self.selectionChanged()

	def removeWatcher(self):
		if hasattr(self.parent, "onChangedEntry"):
			self.parent.onChangedEntry.remove(self.selectionChanged)
			self.parent["config"].onSelectionChanged.remove(self.selectionChanged)

	def selectionChanged(self):
		self["SetupEntry"].text = self.parent.getCurrentEntry()
		self["SetupValue"].text = self.parent.getCurrentValue()
		if hasattr(self.parent, "getCurrentDescription") and "description" in self.parent:
			self.parent["description"].text = self.parent.getCurrentDescription()
		if "footnote" in self.parent:
			if self.parent.getCurrentEntry().endswith("*"):
				self.parent["footnote"].text = (_("* = Restart Required"))
			else:
				self.parent["footnote"].text = ("")


# Read the setup menu XML file.
#
def setupdom(plugin=None):
	# read the setupmenu
	if plugin:
		# first we search in the current path
		setupfile = file(resolveFilename(SCOPE_CURRENT_PLUGIN, plugin + "/setup.xml"), "r")
	else:
		# if not found in the current path, we use the global datadir-path
		setupfile = file(eEnv.resolve("${datadir}/enigma2/setup.xml"), "r")
	setupfiledom = xml.etree.cElementTree.parse(setupfile)
	setupfile.close()
	return setupfiledom

# Only used in AudioSelection screen...
#
def getConfigMenuItem(configElement):
	for item in setupdom().getroot().findall("./setup/item/."):
		if item.text == configElement:
			return _(item.attrib["text"]), eval(configElement)
	return "", None

# Only used in Menu screen...
#
def getSetupTitle(id):
	xmldata = setupdom().getroot()
	for x in xmldata.findall("setup"):
		if x.get("key") == id:
			if x.get("titleshort", "").encode("UTF-8") != "":
				return _(x.get("titleshort", "").encode("UTF-8"))
			else:
				return _(x.get("title", "").encode("UTF-8"))
	raise SetupError("unknown setup id '%s'!" % repr(id))
