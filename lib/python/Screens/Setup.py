import xml.etree.cElementTree

from boxbranding import getMachineBrand, getMachineName
from gettext import dgettext
from os.path import getmtime, join as pathJoin
from skin import setups

from Components.config import ConfigBoolean, ConfigNothing, ConfigSelection, config
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.SystemInfo import SystemInfo
from Components.Sources.StaticText import StaticText
from Screens.HelpMenu import HelpableScreen
from Screens.Screen import Screen
from Tools.Directories import SCOPE_CURRENT_SKIN, SCOPE_PLUGINS, SCOPE_SKIN, resolveFilename
from Tools.LoadPixmap import LoadPixmap

domSetups = {}
setupModTimes = {}
setupTitles = {}


class Setup(ConfigListScreen, Screen, HelpableScreen):
	ALLOW_SUSPEND = True

	def __init__(self, session, setup, plugin=None, PluginLanguageDomain=None):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.setup = setup
		self.plugin = plugin
		self.PluginLanguageDomain = PluginLanguageDomain
		self.onChangedEntry = []
		if hasattr(self, "skinName"):
			if not isinstance(self.skinName, list):
				self.skinName = [self.skinName]
		else:
			self.skinName = []
		if setup:
			self.skinName.append("Setup_%s" % setup)
		self.skinName.append("Setup")
		if config.usage.show_menupath.value in ("large", "small") and x.get("titleshort", "").encode("UTF-8") != "":
			title = x.get("titleshort", "").encode("UTF-8")
		else:
			title = x.get("title", "").encode("UTF-8")
		title = _("Setup" if title == "" else title)
		self.setTitle(title)
		self.footnote = ""
		self.list = []
		ConfigListScreen.__init__(self, self.list, session=session, on_change=self.changedEntry)
		self["footnote"] = Label()
		self["footnote"].hide()
		self["description"] = Label()
		defaultmenuimage = setups.get("default", "")
		menuimage = setups.get(setup, defaultmenuimage)
		if menuimage:
			print("[Setup] %s image '%s'." % ("Default" if menuimage is defaultmenuimage else "Menu", menuimage))
			menuimage = resolveFilename(SCOPE_CURRENT_SKIN, menuimage)
			self.menuimage = LoadPixmap(menuimage)
			if self.menuimage:
				self["menuimage"] = Pixmap()
			else:
				print("[Setup] Error: Unable to load menu image '%s'!" % menuimage)
		else:
			self.menuimage = None
		self.createSetupList()
		if self.layoutFinished not in self.onLayoutFinish:
			self.onLayoutFinish.append(self.layoutFinished)
		self["config"].onSelectionChanged.append(self.__onSelectionChanged)
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

	def layoutFinished(self):
		if self.menuimage:
			self["menuimage"].instance.setPixmap(self.menuimage)

	def selectionChanged(self):
		if self["config"]:
			self.updateFootnote()
			self["description"].text = self.getCurrentDescription()
		else:
			self["description"].text = _("There are no items currently available for this menu.")

	def updateFootnote(self):
		if self.footnote:
			self["footnote"].text = _(self.footnote)
			self["footnote"].show()
		else:
			if self.getCurrentEntry().endswith("*"):
				self["footnote"].text = _("* = Restart Required")
				self["footnote"].show()
			else:
				self["footnote"].text = ""
				self["footnote"].hide()

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
			if self.addWatcher not in self.onShow:
				self.onShow.append(self.addWatcher)
			if self.removeWatcher not in self.onHide:
				self.onHide.append(self.removeWatcher)

	def addWatcher(self):
		if self.selectionChanged not in self.parent.onChangedEntry:
			self.parent.onChangedEntry.append(self.selectionChanged)
		if self.selectionChanged not in self.parent["config"].onSelectionChanged:
			self.parent["config"].onSelectionChanged.append(self.selectionChanged)
		self.selectionChanged()

	def removeWatcher(self):
		if self.selectionChanged in self.parent.onChangedEntry:
			self.parent.onChangedEntry.remove(self.selectionChanged)
		if self.selectionChanged in self.parent["config"].onSelectionChanged:
			self.parent["config"].onSelectionChanged.remove(self.selectionChanged)

	def selectionChanged(self):
		self["SetupEntry"].text = self.parent.getCurrentEntry()
		self["SetupValue"].text = self.parent.getCurrentValue()


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
