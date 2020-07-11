import xml.etree.cElementTree

from boxbranding import getMachineBrand, getMachineName
from gettext import dgettext
from os.path import getmtime, join as pathJoin

from Components.ActionMap import NumberActionMap
from Components.config import ConfigBoolean, ConfigNothing, ConfigSelection, config
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.SystemInfo import SystemInfo
from Components.Sources.Boolean import Boolean
from Components.Sources.StaticText import StaticText
from Screens.Screen import Screen
from Tools.Directories import SCOPE_PLUGINS, SCOPE_SKIN, resolveFilename

domSetups = {}
setupModTimes = {}
setupTitles = {}


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
		xmldata = setupDom(setup, self.plugin).getroot()
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
def setupDom(setup=None, plugin=None):
	if plugin:
		setupFile = resolveFilename(SCOPE_PLUGINS, pathJoin(plugin, "setup.xml"))
		msg = " from plugin '%s'" % plugin
	else:
		setupFile = resolveFilename(SCOPE_SKIN, "setup.xml")
		msg = ""
	try:
		modTime = getmtime(setupFile)
	except (IOError, OSError) as err:
		print("[Setup] Error: Unable to get '%s' modified time - Error (%d): %s!" % (setupFile, err.errno, err.strerror))
		return xml.etree.cElementTree.fromstring("<setupxml></setupxml>")
	cached = setupFile in domSetups and setupFile in setupModTimes and setupModTimes[setupFile] == modTime
	print("[Setup] XML%s source file '%s'." % (" cached" if cached else "", setupFile))
	if setup is not None:
		print("[Setup] XML Setup menu '%s'%s." % (setup, msg))
	if cached:
		return domSetups[setupFile]
	gotFile = False
	try:
		with open(setupFile, "r") as fd:  # This open gets around a possible file handle leak in Python's XML parser.
			try:
				setupfiledom = xml.etree.cElementTree.parse(fd).getroot()
				gotFile = True
			except xml.etree.cElementTree.ParseError as err:
				fd.seek(0)
				content = fd.readlines()
				line, column = err.position
				print("[Setup] XML Parse Error: '%s' in '%s'!" % (err, setupFile))
				data = content[line - 1].replace("\t", " ").rstrip()
				print("[Setup] XML Parse Error: '%s'" % data)
				print("[Setup] XML Parse Error: '%s^%s'" % ("-" * column, " " * (len(data) - column - 1)))
			except Exception as err:
				print("[Setup] Error: Unable to parse setup data in '%s' - '%s'!" % (setupFile, err))
	except (IOError, OSError) as err:
		if err.errno == errno.ENOENT:  # No such file or directory
			print("[Skin] Warning: Setup file '%s' does not exist!" % setupFile)
		else:
			print("[Skin] Error %d: Opening setup file '%s'! (%s)" % (err.errno, setupFile, err.strerror))
	except Exception as err:
		print("[Setup] Error %d: Unexpected error opening setup file '%s'! (%s)" % (err.errno, setupFile, err.strerror))
	if gotFile:
		domSetups[setupFile] = setupfiledom
		setupModTimes[setupFile] = modTime
		xmldata = setupfiledom
		for setup in xmldata.findall("setup"):
			key = setup.get("key", "")
			if key in setupTitles:
				print("[Setup] Warning: Setup key '%s' has been redefined!" % key)
			title = setup.get("menuTitle", "").encode("UTF-8")
			if title == "":
				title = setup.get("title", "").encode("UTF-8")
				if title == "":
					print("[Setup] Error: Setup key '%s' title is missing or blank!" % key)
					setupTitles[key] = _("** Setup error: '%s' title is missing or blank!") % key
				else:
					setupTitles[key] = _(title)
			else:
				setupTitles[key] = _(title)
			# print("[Setup] DEBUG XML Setup menu load: key='%s', title='%s', menuTitle='%s', translated title='%s'" % (key, setup.get("title", "").encode("UTF-8"), setup.get("menuTitle", "").encode("UTF-8"), setupTitles[key]))
	else:
		setupfiledom = xml.etree.cElementTree.fromstring("<setupxml></setupxml>")
	return setupfiledom

# Temporary legacy interface.
#
def setupdom(plugin=None):
	if plugin:
		setupfile = file(resolveFilename(SCOPE_PLUGINS, pathJoin(plugin, "setup.xml")), "r")
	else:
		setupfile = file(resolveFilename(SCOPE_SKIN, "setup.xml"), "r")
	setupfiledom = xml.etree.cElementTree.parse(setupfile)
	setupfile.close()
	return setupfiledom

# Only used in AudioSelection screen...
#
def getConfigMenuItem(configElement):
	for item in setupDom().findall("./setup/item/."):
		if item.text == configElement:
			return _(item.attrib["text"]), eval(configElement)
	return "", None

# Only used in Menu screen...
#
def getSetupTitle(key):
	setupDom()  # Load or check for an updated setup.xml file.
	key = str(key)
	title = setupTitles.get(key, None)
	if title is None:
		print("[Setup] Error: Setup key '%s' not found in setup file!" % key)
		title = _("** Setup error: '%s' section not found! **") % key
	return title
