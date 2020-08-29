import xml.etree.cElementTree

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
		self.createSetup()
		if self.layoutFinished not in self.onLayoutFinish:
			self.onLayoutFinish.append(self.layoutFinished)
		if self.selectionChanged not in self["config"].onSelectionChanged:
			self["config"].onSelectionChanged.append(self.selectionChanged)

	def changedEntry(self):
		if isinstance(self["config"].getCurrent()[1], (ConfigBoolean, ConfigSelection)):
			self.createSetup()

	def createSetup(self):
		oldList = self.list
		self.switch = False
		self.list = []
		title = ""
		xmldata = setupDom(self.setup, self.plugin)
		for setup in xmldata.findall("setup"):
			if setup.get("key") == self.setup:
				self.addItems(setup)
				skin = setup.get("skin", "")
				if skin != "":
					self.skinName.insert(0, skin)
				if config.usage.showScreenPath.value in ("large", "small") and "menuTitle" in setup:
					title = setup.get("menuTitle", "").encode("UTF-8")
				else:
					title = setup.get("title", "").encode("UTF-8")
				# If this break is executed then there can only be one setup tag with this key.
				# This may not be appropriate if conditional setup blocks become available.
				break
		title = _("Setup") if title == "" else _(title)
		self.setTitle(title)
		if self.list != oldList or self.switch:
			print("[Setup] DEBUG: Config list has changed!")
			currentItem = self["config"].getCurrent()
			self["config"].setList(self.list)
			if config.usage.sort_settings.value:
				self["config"].list.sort()
			self.moveToItem(currentItem)
		else:
			print("[Setup] DEBUG: Config list is unchanged!")

	def addItems(self, parentNode):
		for element in parentNode:
			if element.tag and element.tag == "item":
				itemLevel = int(element.get("level", 0))
				if itemLevel > config.usage.setup_level.index:  # The item is higher than the current setup level.
					continue
				requires = element.get("requires")
				if requires:
					negate = requires.startswith("!")
					if negate:
						requires = requires[1:]
					if requires.startswith("config."):
						item = eval(requires)
						SystemInfo[requires] = True if item.value and item.value not in ("0", "False", "false") else False
						clean = True
					else:
						clean = False
					result = bool(SystemInfo.get(requires, False))
					if clean:
						SystemInfo.pop(requires, None)
					if requires and negate == result:  # The item requirements are not met.
						continue
				conditional = element.get("conditional")
				if conditional and not eval(conditional):  # The item conditions are not met.
					continue
				if self.PluginLanguageDomain:
					itemText = dgettext(self.PluginLanguageDomain, element.get("text", "??").encode("UTF-8"))
					itemDescription = dgettext(self.PluginLanguageDomain, element.get("description", " ").encode("UTF-8"))
				else:
					itemText = _(element.get("text", "??").encode("UTF-8"))
					itemDescription = _(element.get("description", " ").encode("UTF-8"))
				itemText = itemText.replace("%s %s", "%s %s" % (SystemInfo["MachineBrand"], SystemInfo["MachineName"]))
				itemDescription = itemDescription.replace("%s %s", "%s %s" % (SystemInfo["MachineBrand"], SystemInfo["MachineName"]))
				item = eval(element.text or "")
				if item != "" and not isinstance(item, ConfigNothing):
					itemDefault = "(Default: %s)" % item.toDisplayString(item.default)
					itemDescription = "%s  %s" % (itemDescription, itemDefault) if itemDescription and itemDescription != " " else itemDefault
					self.list.append((itemText, item, itemDescription))  # Add the item to the config list.
				if item is config.usage.boolean_graphic:
					self.switch = True

	def layoutFinished(self):
		if self.menuimage:
			self["menuimage"].instance.setPixmap(self.menuimage)
		if not self["config"]:
			print("[Setup] No menu items available!")

	def selectionChanged(self):
		if self["config"]:
			self.setFootnote(None)
			self["description"].text = self.getCurrentDescription()
		else:
			self["description"].text = _("There are no items currently available for this menu.")

	def setFootnote(self, footnote):
		if footnote is None:
			if self.getCurrentEntry().endswith("*"):
				self["footnote"].text = _("* = Restart Required")
				self["footnote"].show()
			else:
				self["footnote"].text = ""
				self["footnote"].hide()
		else:
			self["footnote"].text = footnote
			self["footnote"].show()

	def getFootnote(self):
		return self["footnote"].text

	def moveToItem(self, item):
		if item != self["config"].getCurrent():
			self["config"].setCurrentIndex(self.getIndexFromItem(item))

	def getIndexFromItem(self, item):
		return self["config"].list.index(item) if item in self["config"].list else 0


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
