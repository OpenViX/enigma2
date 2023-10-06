from enigma import RT_HALIGN_LEFT, RT_VALIGN_CENTER, eListboxPythonMultiContent, gFont
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryText
from Tools.Directories import fileExists, SCOPE_CURRENT_SKIN, resolveFilename
from Tools.LoadPixmap import LoadPixmap
from skin import applySkinFactor, fonts, parameters


def row_delta_y():
	font = fonts["ChoiceList"]
	return (int(font[2]) - int(font[1])) / 2


def ChoiceEntryComponent(key=None, text=None):
	if text is None:
		text = ["--"]
	res = [text]
	if text[0] == "--":
		# Do we want graphical separator (solid line with color) or dashed line
		isUseGraphicalSeparator = parameters.get("ChoicelistUseGraphicalSeparator", 0)
		x, y, w, h = parameters.get("ChoicelistDash", applySkinFactor(0, 2, 800, 25))
		if isUseGraphicalSeparator:
			bk_color = parameters.get("ChoicelistSeparatorColor", "0x00555556")
			res.append(
				MultiContentEntryText(
					pos=(x, y + 20),
					size=(w, 2),
					font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
					text="",
					color=None, color_sel=None,
					backcolor=bk_color, backcolor_sel=bk_color))
		else:
			res.append((eListboxPythonMultiContent.TYPE_TEXT, x, y, w, h, 0, RT_HALIGN_LEFT, "-" * 200))
	else:
		if key:
			x, y, w, h = parameters.get("ChoicelistName", applySkinFactor(45, 2, 800, 25))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, x, y, w, h, 0, RT_HALIGN_LEFT, text[0]))
			# separate the sizes definition for keybutton is=cons and the rest so there to be possibility to use different size images for different type icons
			iconKeyConfigName = "ChoicelistIcon"
			if key == "expandable":
				pngfile = resolveFilename(SCOPE_CURRENT_SKIN, "icons/expandable.png")
			elif key == "expanded":
				pngfile = resolveFilename(SCOPE_CURRENT_SKIN, "icons/expanded.png")
			elif key == "verticalline":
				pngfile = resolveFilename(SCOPE_CURRENT_SKIN, "icons/verticalline.png")
			elif key == "bullet":
				pngfile = resolveFilename(SCOPE_CURRENT_SKIN, "icons/bullet.png")
			else:
				iconKeyConfigName = "ChoicelistButtonIcon"
				pngfile = resolveFilename(SCOPE_CURRENT_SKIN, "buttons/key_%s.png" % key)
			if fileExists(pngfile):
				png = LoadPixmap(pngfile)
				x, y, w, h = parameters.get(iconKeyConfigName, (applySkinFactor(5), applySkinFactor(0), png.size().width(), png.size().height()))
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
