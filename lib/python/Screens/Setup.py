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
from Screens.Screen import Screen, ScreenSummary
from Tools.Directories import SCOPE_CURRENT_SKIN, SCOPE_PLUGINS, SCOPE_SKIN, resolveFilename
from Tools.LoadPixmap import LoadPixmap

domSetups = {}
setupModTimes = {}
setupTitles = {}


class Setup(ConfigListScreen, Screen, HelpableScreen):
	def __init__(self, session, setup, plugin=None, PluginLanguageDomain=None):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.setup = setup
		self.plugin = plugin
		self.pluginLanguageDomain = PluginLanguageDomain
		if hasattr(self, "skinName"):
			if not isinstance(self.skinName, list):
				self.skinName = [self.skinName]
		else:
			self.skinName = []
		if setup:
			self.skinName.append("Setup%s" % setup)  # DEBUG: Proposed for new setup screens.
			self.skinName.append("setup_%s" % setup)
		self.skinName.append("Setup")
		self.onChangedEntry = []
		self.list = []
		ConfigListScreen.__init__(self, self.list, session=session, on_change=self.changedEntry, fullUI=True)
		self["footnote"] = Label()
		self["footnote"].hide()
		self["description"] = Label()
		self.createSetup()
		defaultSetupImage = setups.get("default", "")
		setupImage = setups.get(setup, defaultSetupImage)
		if setupImage:
			print("[Setup] %s image '%s'." % ("Default" if setupImage is defaultSetupImage else "Setup", setupImage))
			setupImage = resolveFilename(SCOPE_CURRENT_SKIN, setupImage)
			self.setupImage = LoadPixmap(setupImage)
			if self.setupImage:
				self["setupimage"] = Pixmap()
			else:
				print("[Setup] Error: Unable to load menu image '%s'!" % setupImage)
		else:
			self.setupImage = None
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
		title = None
		xmlData = setupDom(self.setup, self.plugin)
		for setup in xmlData.findall("setup"):
			if setup.get("key") == self.setup:
				self.addItems(setup)
				skin = setup.get("skin", None)
				if skin and skin != "":
					self.skinName.insert(0, skin)
				if config.usage.showScreenPath.value in ("large", "small") and "menuTitle" in setup:
					title = setup.get("menuTitle", None).encode("UTF-8", errors="ignore")
				else:
					title = setup.get("title", None).encode("UTF-8", errors="ignore")
				# If this break is executed then there can only be one setup tag with this key.
				# This may not be appropriate if conditional setup blocks become available.
				break
		self.setTitle(_(title) if title and title != "" else _("Setup"))
		if self.list != oldList or self.switch:
			print("[Setup] DEBUG: Config list has changed!")
			currentItem = self["config"].getCurrent()
			self["config"].setList(self.list)
			if config.usage.sort_settings.value:
				self["config"].list.sort()
			self.moveToItem(currentItem)
		else:
			print("[Setup] DEBUG: Config list is unchanged!")

	def addItems(self, parentNode, including=True):
		for element in parentNode:
			if not element.tag:
				continue
			if element.tag in ("elif", "else") and including:
				break  # End of succesful if/elif branch - short-circuit rest of children.
			include = self.includeElement(element)
			if element.tag == "item":
				if including and include:
					self.addItem(element)
			elif element.tag == "if":
				if including:
					self.addItems(element, including=include)
			elif element.tag == "elif":
				including = include
			elif element.tag == "else":
				including = True

	def addItem(self, element):
		if self.pluginLanguageDomain:
			itemText = dgettext(self.pluginLanguageDomain, element.get("text", "??").encode("UTF-8", errors="ignore"))
			itemDescription = dgettext(self.pluginLanguageDomain, element.get("description", " ").encode("UTF-8", errors="ignore"))
		else:
			itemText = _(element.get("text", "??").encode("UTF-8", errors="ignore"))
			itemDescription = _(element.get("description", " ").encode("UTF-8", errors="ignore"))
		itemText = itemText.replace("%s %s", "%s %s" % (SystemInfo["MachineBrand"], SystemInfo["MachineName"]))
		itemDescription = itemDescription.replace("%s %s", "%s %s" % (SystemInfo["MachineBrand"], SystemInfo["MachineName"]))
		item = eval(element.text or "")
		if item != "" and not isinstance(item, ConfigNothing):
			itemDefault = item.toDisplayString(item.default)
			itemDescription = _("%s  (Default: %s)") % (itemDescription, itemDefault) if itemDescription and itemDescription != " " else _("Default: '%s'.") % itemDefault
			self.list.append((itemText, item, itemDescription))  # Add the item to the config list.
		if item is config.usage.boolean_graphic:
			self.switch = True

	def includeElement(self, element):
		itemLevel = int(element.get("level", 0))
		if itemLevel > config.usage.setup_level.index:  # The item is higher than the current setup level.
			return False
		requires = element.get("requires")
		if requires:
			negate = requires.startswith("!")
			if negate:
				requires = requires[1:]
			if requires.startswith("config."):
				item = eval(requires)
				result = bool(item.value and item.value not in ("0", "False", "false"))
			else:
				result = bool(SystemInfo.get(requires, False))
			if requires and negate == result:  # The item requirements are not met.
				return False
		conditional = element.get("conditional")
		return not conditional or eval(conditional)

	def layoutFinished(self):
		if self.setupImage:
			self["setupimage"].instance.setPixmap(self.setupImage)
		if not self["config"]:
			print("[Setup] No setup items available!")

	def selectionChanged(self):
		if self["config"]:
			self.setFootnote(None)
			self["description"].text = self.getCurrentDescription()
		else:
			self["description"].text = _("There are no items currently available for this screen.")

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

	def createSummary(self):
		return SetupSummary


class SetupSummary(ScreenSummary):
	def __init__(self, session, parent):
		ScreenSummary.__init__(self, session, parent=parent)
		self["entry"] = StaticText("")  # DEBUG: Proposed for new summary screens.
		self["value"] = StaticText("")  # DEBUG: Proposed for new summary screens.
		self["SetupTitle"] = StaticText(parent.getTitle())
		self["SetupEntry"] = StaticText("")
		self["SetupValue"] = StaticText("")
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
		self["entry"].text = self.parent.getCurrentEntry()  # DEBUG: Proposed for new summary screens.
		self["value"].text = self.parent.getCurrentValue()  # DEBUG: Proposed for new summary screens.
		self["SetupEntry"].text = self.parent.getCurrentEntry()
		self["SetupValue"].text = self.parent.getCurrentValue()


# Read the setup XML file.
#
def setupDom(setup=None, plugin=None):
	# Constants for checkItems()
	ROOT_ALLOWED = ("setup", )  # Tags allowed in top level of setupxml entry.
	ELEMENT_ALLOWED = ("item", "if")  # Tags allowed in top level of setup entry.
	IF_ALLOWED = ("item", "if", "elif", "else")  # Tags allowed inside <if />.
	AFTER_ELSE_ALLOWED = ("item", "if")  # Tags allowed after <elif /> or <else />.
	CHILDREN_ALLOWED = ("setup", "if", )  # Tags that may have children.
	TEXT_ALLOWED = ("item", )  # Tags that may have non-whitespace text (or tail).
	KEY_ATTRIBUTES = {  # Tags that have a reference key mandatory attribute.
		"setup": "key",
		"item": "text"
	}
	MANDATORY_ATTRIBUTES = {  # Tags that have a list of mandatory attributes.
		"setup": ("key", "title"),
		"item": ("text", )
	}

	def checkItems(parentNode, key, allowed=ROOT_ALLOWED, mandatory=MANDATORY_ATTRIBUTES, reference=KEY_ATTRIBUTES):
		keyText = " in '%s'" % key if key else ""
		for element in parentNode:
			if element.tag not in allowed:
				print("[Setup] Error: Tag '%s' not permitted%s!  (Permitted: '%s')" % (element.tag, keyText, ", ".join(allowed)))
				continue
			if mandatory and element.tag in mandatory:
				valid = True
				for attrib in mandatory[element.tag]:
					if element.get(attrib) is None:
						print("[Setup] Error: Tag '%s'%s does not contain the mandatory '%s' attribute!" % (element.tag, keyText, attrib))
						valid = False
				if not valid:
					continue
			if element.tag not in TEXT_ALLOWED:
				if element.text and not element.text.isspace():
					print("[Setup] Tag '%s'%s contains text '%s'." % (element.tag, keyText, element.text.strip()))
				if element.tail and not element.tail.isspace():
					print("[Setup] Tag '%s'%s has trailing text '%s'." % (element.tag, keyText, element.text.strip()))
			if element.tag not in CHILDREN_ALLOWED and len(element):
				itemKey = ""
				if element.tag in reference:
					itemKey = " (%s)" % element.get(reference[element.tag])
				print("[Setup] Tag '%s'%s%s contains children where none expected." % (element.tag, itemKey, keyText))
			if element.tag in CHILDREN_ALLOWED:
				if element.tag in reference:
					key = element.get(reference[element.tag])
				checkItems(element, key, allowed=IF_ALLOWED)
			elif element.tag == "else":
				allowed = AFTER_ELSE_ALLOWED  # else and elif not permitted after else
			elif element.tag == "elif":
				pass

	setupFileDom = xml.etree.cElementTree.fromstring("<setupxml></setupxml>")
	setupFile = resolveFilename(SCOPE_PLUGINS, pathJoin(plugin, "setup.xml")) if plugin else resolveFilename(SCOPE_SKIN, "setup.xml")
	global setupTitles
	try:
		modTime = getmtime(setupFile)
	except (IOError, OSError) as err:
		print("[Setup] Error: Unable to get '%s' modified time - Error (%d): %s!" % (setupFile, err.errno, err.strerror))
		if setupFile in domSetups:
			del domSetups[setupFile]
		if setupFile in setupModTimes:
			del setupModTimes[setupFile]
		setupTitles = {}
		return setupFileDom
	cached = setupFile in domSetups and setupFile in setupModTimes and setupModTimes[setupFile] == modTime
	print("[Setup] XML%s setup file '%s', using element '%s'%s." % (" cached" if cached else "", setupFile, setup, " from plugin '%s'" % plugin if plugin else ""))
	if cached:
		return domSetups[setupFile]
	try:
		if setupFile in domSetups:
			del domSetups[setupFile]
		if setupFile in setupModTimes:
			del setupModTimes[setupFile]
		setupTitles = {}
		with open(setupFile, "r") as fd:  # This open gets around a possible file handle leak in Python's XML parser.
			try:
				fileDom = xml.etree.cElementTree.parse(fd).getroot()
				checkItems(fileDom, None)
				setupFileDom = fileDom
				domSetups[setupFile] = setupFileDom
				setupModTimes[setupFile] = modTime
				for setup in setupFileDom.findall("setup"):
					key = setup.get("key")
					if key:  # If there is no key then this element is useless and can be skipped!
						if key in setupTitles:
							print("[Setup] Warning: Setup key '%s' has been redefined!" % key)
						title = setup.get("menuTitle", "").encode("UTF-8", errors="ignore")
						if title == "":
							title = setup.get("title", "").encode("UTF-8", errors="ignore")
							if title == "":
								print("[Setup] Error: Setup key '%s' title is missing or blank!" % key)
								title = "** Setup error: '%s' title is missing or blank!" % key
						setupTitles[key] = _(title)
						# print("[Setup] DEBUG: XML setup load: key='%s', title='%s', menuTitle='%s', translated title='%s'" % (key, setup.get("title", "").encode("UTF-8", errors="ignore"), setup.get("menuTitle", "").encode("UTF-8", errors="ignore"), setupTitles[key]))
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
			print("[Setup] Warning: Setup file '%s' does not exist!" % setupFile)
		else:
			print("[Setup] Error %d: Opening setup file '%s'! (%s)" % (err.errno, setupFile, err.strerror))
	except Exception as err:
		print("[Setup] Error %d: Unexpected error opening setup file '%s'! (%s)" % (err.errno, setupFile, err.strerror))
	return setupFileDom

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
	if not isinstance(key, str):
		key = str(key)
	title = setupTitles.get(key, None)
	if title is None:
		print("[Setup] Error: Setup key '%s' not found in setup file!" % key)
		title = _("** Setup error: '%s' section not found! **") % key
	return title
