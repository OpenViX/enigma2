from MenuList import MenuList
from Tools.Directories import SCOPE_CURRENT_SKIN, resolveFilename
from enigma import RT_HALIGN_LEFT, eListboxPythonMultiContent, gFont
from Tools.LoadPixmap import LoadPixmap
from Tools.Directories import fileExists
from skin import applySkinFactor, fonts, parameters


def row_delta_y():
	font = fonts["ChoiceList"]
	return (int(font[2]) - int(font[1])) / 2


def ChoiceEntryComponent(key=None, text=["--"]):
	res = [text]
	if text[0] == "--":
		x, y, w, h = parameters.get("ChoicelistDash", applySkinFactor(0, 2, 800, 25))
		res.append((eListboxPythonMultiContent.TYPE_TEXT, x, y, w, h, 0, RT_HALIGN_LEFT, "-" * 200))
	else:
		x, y, w, h = parameters.get("ChoicelistName", applySkinFactor(45, 2, 800, 25))
		res.append((eListboxPythonMultiContent.TYPE_TEXT, x, y, w, h, 0, RT_HALIGN_LEFT, text[0]))
		if key:
			if key == "expandable":
				pngfile = resolveFilename(SCOPE_CURRENT_SKIN, "icons/expandable.png")
			elif key == "expanded":
				pngfile = resolveFilename(SCOPE_CURRENT_SKIN, "icons/expanded.png")
			elif key == "verticalline":
				pngfile = resolveFilename(SCOPE_CURRENT_SKIN, "icons/verticalline.png")
			elif key == "bullet":
				pngfile = resolveFilename(SCOPE_CURRENT_SKIN, "icons/bullet.png")
			else:
				pngfile = resolveFilename(SCOPE_CURRENT_SKIN, "buttons/key_%s.png" % key)
			if fileExists(pngfile):
				png = LoadPixmap(pngfile)
				x, y, w, h = parameters.get("ChoicelistIcon", (applySkinFactor(5), applySkinFactor(0), png.size().width(), png.size().height()))
				res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, x, y, w, h, png))
	return res


class ChoiceList(MenuList):
	def __init__(self, list, selection=0, enableWrapAround=False):
		MenuList.__init__(self, list, enableWrapAround, eListboxPythonMultiContent)
		font = fonts.get("ChoiceList", applySkinFactor("Regular", 20, 25))
		self.l.setFont(0, gFont(font[0], font[1]))
		self.l.setItemHeight(font[2])
		self.ItemHeight = font[2]
		self.selection = selection

	def postWidgetCreate(self, instance):
		MenuList.postWidgetCreate(self, instance)
		self.moveToIndex(self.selection)
		self.instance.setWrapAround(True)

	def getItemHeight(self):
		return self.ItemHeight
