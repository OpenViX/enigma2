from MenuList import MenuList

from Tools.Directories import resolveFilename, SCOPE_ACTIVE_SKIN
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmapAlphaBlend

from enigma import eListboxPythonMultiContent, gFont, BT_SCALE, BT_KEEP_ASPECT_RATIO, BT_HALIGN_CENTER, BT_VALIGN_CENTER
from Tools.LoadPixmap import LoadPixmap
import skin


def PluginEntryComponent(plugin, width=440):
	if plugin.icon is None:
		png = LoadPixmap(resolveFilename(SCOPE_ACTIVE_SKIN, "icons/plugin.png"))
	else:
		png = plugin.icon
	nx, ny, nh = skin.parameters.get("PluginBrowserName", (skin.applySkinFactor(120), skin.applySkinFactor(5), skin.applySkinFactor(25)))
	dx, dy, dh = skin.parameters.get("PluginBrowserDescr", (skin.applySkinFactor(120), skin.applySkinFactor(26), skin.applySkinFactor(17)))
	ix, iy, iw, ih = skin.parameters.get("PluginBrowserIcon", (skin.applySkinFactor(10), skin.applySkinFactor(5), skin.applySkinFactor(100), skin.applySkinFactor(40)))
	return [
		plugin,
		MultiContentEntryText(pos=(nx, ny), size=(width - nx, nh), font=0, text=plugin.name),
		MultiContentEntryText(pos=(nx, dy), size=(width - dx, dh), font=1, text=plugin.description),
		MultiContentEntryPixmapAlphaBlend(pos=(ix, iy), size=(iw, ih), png=png, flags=BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_CENTER | BT_VALIGN_CENTER)
	]


def PluginCategoryComponent(name, png, width=440):
	x, y, h = skin.parameters.get("PluginBrowserDownloadName", (skin.applySkinFactor(80), skin.applySkinFactor(5), skin.applySkinFactor(25)))
	ix, iy, iw, ih = skin.parameters.get("PluginBrowserDownloadIcon", (skin.applySkinFactor(10), skin.applySkinFactor(0), skin.applySkinFactor(60), skin.applySkinFactor(50)))
	return [
		name,
		MultiContentEntryText(pos=(x, y), size=(width - x, h), font=0, text=name),
		MultiContentEntryPixmapAlphaBlend(pos=(ix, iy), size=(iw, ih), png=png)
	]


def PluginDownloadComponent(plugin, name, version=None, width=440):
	if plugin.icon is None:
		png = LoadPixmap(resolveFilename(SCOPE_ACTIVE_SKIN, "icons/plugin.png"))
	else:
		png = plugin.icon
	if version:
		if "+git" in version:
			# remove git "hash"
			version = "+".join(version.split("+")[:2])
		elif version.startswith('experimental-'):
			version = version[13:]
		name += "  (" + version + ")"
	x, y, h = skin.parameters.get("PluginBrowserDownloadName", (skin.applySkinFactor(80), skin.applySkinFactor(5), skin.applySkinFactor(25)))
	dx, dy, dh = skin.parameters.get("PluginBrowserDownloadDescr", (skin.applySkinFactor(80), skin.applySkinFactor(26), skin.applySkinFactor(17)))
	ix, iy, iw, ih = skin.parameters.get("PluginBrowserDownloadIcon", (skin.applySkinFactor(10), skin.applySkinFactor(0), skin.applySkinFactor(60), skin.applySkinFactor(50)))
	return [
		plugin,
		MultiContentEntryText(pos=(x, y), size=(width - x, h), font=0, text=name),
		MultiContentEntryText(pos=(dx, dy), size=(width - dx, dh), font=1, text=plugin.description),
		MultiContentEntryPixmapAlphaBlend(pos=(ix, iy), size=(iw, ih), png=png)
	]


class PluginList(MenuList):
	def __init__(self, list, enableWrapAround=True):
		MenuList.__init__(self, list, enableWrapAround, eListboxPythonMultiContent)
		font = skin.fonts.get("PluginBrowser0", ("Regular", skin.applySkinFactor(20), skin.applySkinFactor(50)))
		self.l.setFont(0, gFont(font[0], font[1]))
		self.l.setItemHeight(font[2])
		font = skin.fonts.get("PluginBrowser1", ("Regular", skin.applySkinFactor(16)))
		self.l.setFont(1, gFont(font[0], font[1]))
