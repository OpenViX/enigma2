from os import path as ospath, fsync, rename, makedirs
from pathlib import Path
from Plugins.Plugin import PluginDescriptor
from Screens.Setup import Setup
from Screens.Standby import TryQuitMainloop
from Screens.MessageBox import MessageBox
from Components.Pixmap import Pixmap
from skin import loadSkin
from Tools.BoundFunction import boundFunction
from Tools.Directories import fileExists, fileReadXML, resolveFilename, SCOPE_GUISKIN
from Tools.LoadPixmap import LoadPixmap
from Components.config import config, ConfigSelection

import threading

write_lock = threading.Lock()

PROGRAM_NAME = _("Skin Configurator")
PROGRAM_DESCRIPTION = _("Current skin configuration plugin.")


file_tree = {}
current_skin_config = {}


def build_xml_tree(directory: Path):
	tree = {}
	if directory.exists() and directory.is_dir():
		for item in directory.iterdir():
			if item.is_dir():
				# Recursively build subtree
				subtree = build_xml_tree(item)
				if subtree:  # Only include non-empty folders
					tree[item.name] = subtree
					print(subtree)
			elif item.is_file() and item.suffix.lower() == ".xml":  # Store XML file with full path
				print(item.resolve())
				tree[item.name] = str(item.resolve())
	return tree


def xml_to_dict(elem):
	result = {}

	# Add attributes (e.g. name="Timer List")
	if elem.attrib:
		result.update(elem.attrib)

	# Add text content (CDATA included)
	text = (elem.text or "").strip()
	if text:
		result["value"] = text

	# Process child elements
	for child in elem:
		child_dict = xml_to_dict(child)

		if child.tag in result:
			# Convert to list if multiple children with same tag
			if not isinstance(result[child.tag], list):
				result[child.tag] = [result[child.tag]]
			result[child.tag].append(child_dict)
		else:
			result[child.tag] = child_dict

	return result


def applyCustomLayouts():
	root = current_skin_config.get("config", {})
	color_scheme = root.get("color_scheme", {}).get("value", None)
	if color_scheme:
		loadSkin(filename=color_scheme, scope=SCOPE_GUISKIN)
	screens = root.get("screens", {})
	if screens:
		for key, value in screens.items():
			if not isinstance(value, list):
				value = [value]
			for val in value:
				loadSkin(filename=val["value"], scope=SCOPE_GUISKIN)


def find_screen_by_name(config, name):
	screens = config.get("screen", {})

	# Normalize to list
	if isinstance(screens, dict) and screens:
		screens = [screens]

	for entry in screens:
		if entry.get("name") == name:
			val = entry.get("value", "off")
			return val

	return "off"


class SkinSetupConfig(Setup):
	def __init__(self, session):
		root = current_skin_config.get("config", {})
		color_scheme = root.get("color_scheme", {})
		colors = file_tree.get("Colors", {})
		color_scheme_choices = [("off", _("off"))]
		for key, value in colors.items():
			color_scheme_choices.append((value.replace(resolveFilename(SCOPE_GUISKIN), ""), key.replace(".xml", "")))
		self.color_scheme = ConfigSelection(default=color_scheme.get("value", "off"), choices=color_scheme_choices)
		screens_configuration = root.get("screens", {})
		screens = file_tree.get("Screens", {})

		for key, value in screens.items():
			val_choices = [("off", _("off"))]
			for name, path in value.items():
				val_fixed = f"{path.replace(resolveFilename(SCOPE_GUISKIN), "")}"
				val_choices.append((val_fixed, name.replace(".xml", "")))
			val = ConfigSelection(default=find_screen_by_name(screens_configuration, key), choices=val_choices)
			val.addNotifier(self.showThumb)
			setattr(self, f"screen_{key.lower().replace(" ", "_")}", val)

		Setup.__init__(self, session, None)
		self["thumb"] = Pixmap()
		self.title = _("Skin Configuration")

	def showThumb(self, configElement):
		if "thumb" not in self or not self["thumb"]:
			return
		selectedVal = configElement.value
		thumb = resolveFilename(SCOPE_GUISKIN, selectedVal + ".png")
		if fileExists(thumb):
			pixmap = LoadPixmap(thumb)
			self["thumb"].setPixmap(pixmap)
		else:
			self["thumb"].setPixmap(None)

	def writeSkinConfig(self):
		xml = []
		xml.append("<config>\n")
		colors = file_tree.get("Colors", {})
		screens = file_tree.get("Screens", {})
		if colors:
			conf_value = self.color_scheme.value
			if conf_value != "off":
				for key, value in colors.items():
					val_fixed = f"{value.replace(resolveFilename(SCOPE_GUISKIN), "")}"
					if val_fixed == conf_value:
						xml.append(f'\t\t<color_scheme name="{key}">{conf_value}</color_scheme>\n')
		if screens:
			xml.append("\t\t<screens>\n")
			for key, value in screens.items():
				screen_conf_val = getattr(self, f"screen_{key.lower().replace(" ", "_")}").value
				if screen_conf_val and screen_conf_val != "off":
					for name, path in value.items():
						val_fixed = f"{path.replace(resolveFilename(SCOPE_GUISKIN), "")}"
						if val_fixed == screen_conf_val:
							xml.append(f'\t\t\t<screen name="{key}">{screen_conf_val}</screen>\n')
			xml.append("\t\t</screens>\n")

		xml.append("</config>\n")
		skinname = ospath.dirname(config.skin.primary_skin.value)
		skin_conf = f"/etc/enigma2/SkinConfig/{skinname}_config.xml"
		makedirs(ospath.dirname(skin_conf), exist_ok=True)  # create config folder recursive if not exists

		with write_lock:
			f = open(skin_conf + ".writing", 'w')
			f.write("".join(xml))
			f.flush()
			fsync(f.fileno())
			f.close()
			rename(skin_conf + ".writing", skin_conf)
		loadConfigToDict()

	def createSetup(self):
		configlist = []
		has_one = False
		colors = file_tree.get("Colors", {})
		if colors:
			configlist.append(("Colors",))
			configlist.append(("     " + _("Color Theme"), self.color_scheme, _("Pick an option. After selection is saved GUI should be restarted to accept the changes.")))
			has_one = True
		screens = file_tree.get("Screens", {})
		if screens:
			if has_one:
				configlist.append(("---",))
			configlist.append(("Screens",))
			for key, value in screens.items():
				configlist.append(("     " + key, getattr(self, f"screen_{key.lower().replace(" ", "_")}"), _("Pick an option. After selection is saved GUI should be restarted to accept the changes.")))
		self["config"].list = configlist

	def keySave(self):
		self.showRestartMessage(_("To save and apply the selected skin configuration the GUI needs to restart. Would you like to save the selection and restart the GUI now?"))

	def showRestartMessage(self, msg):
		restartBox = self.session.openWithCallback(self.restartGUI, MessageBox, msg, MessageBox.TYPE_YESNO)
		restartBox.setTitle(_("Skin Configurator: Restart GUI"))

	def restartGUI(self, answer):
		if answer is True:
			self.writeSkinConfig()
			self.session.open(TryQuitMainloop, 3)
		self.close(True)


def sessionstart(reason, session, **kwargs):
	if not reason:
		applyCustomLayouts()


def loadFileSystemToDict():
	skinfile = Path(config.skin.primary_skin.value)
	if not skinfile.is_absolute():  # Enigma2 default skin directory
		skinfile = Path("/usr/share/enigma2") / skinfile
	layouts_root = skinfile.parent / Path("Layouts")
	global file_tree
	file_tree = build_xml_tree(layouts_root)


def skinHasXmlFiles():
	if file_tree:
		return True
	return False


def startFromSkinMenu(menuid):
	if menuid == "skin_setup" and skinHasXmlFiles():
		return [(_("Skin Configuration"), SkinSetupMenu, "skinconf", 10)]
	return []


def loadConfigToDict():
	global current_skin_config
	skinname = ospath.dirname(config.skin.primary_skin.value)
	skin_conf = f"/etc/enigma2/SkinConfig/{skinname}_config.xml"
	if root := fileReadXML(skin_conf):
		current_skin_config = {root.tag: xml_to_dict(root)}


def MenuCallback(close, answer=None):
	if close and answer:
		close(True)


def SkinSetupMenu(session, close=None, **kwargs):
	session.openWithCallback(boundFunction(MenuCallback, close), SkinSetupConfig)


def Plugins(path, **kwargs):
	plugin = [
		PluginDescriptor(where=PluginDescriptor.WHERE_SESSIONSTART, fnc=sessionstart, needsRestart=False),
		PluginDescriptor(name=PROGRAM_NAME, description=PROGRAM_DESCRIPTION, where=PluginDescriptor.WHERE_MENU, fnc=startFromSkinMenu)
	]

	loadFileSystemToDict()
	loadConfigToDict()

	return plugin
