from Components.Addons.GUIAddon import GUIAddon

from enigma import eLabel, eListbox, eListboxPythonMultiContent, BT_ALIGN_CENTER, BT_VALIGN_CENTER, RT_VALIGN_CENTER, RT_HALIGN_LEFT, eSize, getDesktop, gFont

from skin import parseScale, parseColor, parseFont, applySkinFactor

from Components.MultiContent import MultiContentEntryPixmapAlphaBlend
from Components.Label import Label

from Tools.Directories import resolveFilename, SCOPE_GUISKIN
from Tools.LoadPixmap import LoadPixmap


class ColorButtonsSequence(GUIAddon):
	def __init__(self):
		GUIAddon.__init__(self)
		self.foreColor = 0xffffff
		self.font = gFont("Regular", 18)
		self.l = eListboxPythonMultiContent()  # noqa: E741
		self.l.setBuildFunc(self.buildEntry)
		self.l.setItemHeight(35)
		self.l.setItemWidth(35)
		self.spacingButtons = applySkinFactor(40)
		self.spacingPixmapText = applySkinFactor(10)
		self.layoutStyle = "fixed"
		self.colorIndicatorStyle = "pixmap"
		self.orientations = {"orHorizontal": eListbox.orHorizontal, "orVertical": eListbox.orVertical}
		self.orientation = eListbox.orHorizontal
		self.alignment = "left"
		self.pixmaps = {}
		self.colors = {}
		self.textRenderer = Label("")

	def onContainerShown(self):
		for x, val in self.sources.items():
			if self.constructButtonSequence not in val.onChanged:
				val.onChanged.append(self.constructButtonSequence)
		if self.layoutStyle == "fluid":
			self.textRenderer.GUIcreate(self.relatedScreen.instance)
		self.constructButtonSequence()

	GUI_WIDGET = eListbox

	def updateAddon(self, sequence):
		l_list = []
		l_list.append((sequence,))
		self.l.setList(l_list)

	def buildEntry(self, sequence):
		width = self.instance.size().width()
		height = self.instance.size().height()
		xPos = width if self.alignment == "right" else 0
		yPos = 0
		sectorWidth = width // len(sequence)

		res = [None]

		for x, val in sequence.items():
			if x in self.pixmaps:
				pic = LoadPixmap(resolveFilename(SCOPE_GUISKIN, self.pixmaps[x]))
				if pic:
					pixd_size = pic.size()
					pixd_width = pixd_size.width()
					pixd_height = pixd_size.height()
					pic_x_pos = (xPos - pixd_width) if self.alignment == "right" else xPos
					res.append(MultiContentEntryPixmapAlphaBlend(
						pos=(pic_x_pos, yPos),
						size=(pixd_width, height),
						png=pic,
						backcolor=None, backcolor_sel=None, flags=BT_ALIGN_CENTER))
					if self.alignment == "right":
						xPos -= pixd_width + self.spacingPixmapText
					else:
						xPos += pixd_width + self.spacingPixmapText
				buttonText = val.text
				if self.layoutStyle == "fluid":
					textWidth = self._calcTextWidth(buttonText, font=self.font, size=eSize(self.getDesktopWith() // 3, 0))
				else:
					textWidth = sectorWidth - self.spacingButtons - self.spacingPixmapText - pixd_width
				res.append((eListboxPythonMultiContent.TYPE_TEXT, xPos, yPos, textWidth, height - 2, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, buttonText))
				xPos += textWidth + self.spacingButtons

		return res

	def postWidgetCreate(self, instance):
		instance.setSelectionEnable(False)
		instance.setContent(self.l)
		instance.allowNativeKeys(False)

	def constructButtonSequence(self):
		sequence = {}
		for x, val in self.sources.items():
			if val.text:
				sequence[x] = val

		self.updateAddon(sequence)

	def applySkin(self, desktop, parent):
		attribs = []
		for (attrib, value) in self.skinAttributes[:]:
			if attrib == "pixmaps":
				self.pixmaps = dict(item.split(':') for item in value.split(','))
			elif attrib == "itemHeight":
				self.l.setItemHeight(parseScale(value))
			elif attrib == "itemWidth":
				self.l.setItemWidth(parseScale(value))
			elif attrib == "spacingButtons":
				self.spacingButtons = parseScale(value)
			elif attrib == "spacingPixmapText":
				self.spacingPixmapText = parseScale(value)
			elif attrib == "layoutStyle":
				self.layoutStyle = value
			elif attrib == "alignment":
				self.alignment = value
			elif attrib == "orientation":
				self.orientation = self.orientations.get(value, self.orientations["orHorizontal"])
				if self.orientation == eListbox.orHorizontal:
					self.instance.setOrientation(eListbox.orVertical)
					self.l.setOrientation(eListbox.orVertical)
				else:
					self.instance.setOrientation(eListbox.orHorizontal)
					self.l.setOrientation(eListbox.orHorizontal)
			elif attrib == "font":
				self.font = parseFont(value, ((1, 1), (1, 1)))
			elif attrib == "foregroundColor":
				self.foreColor = parseColor(value).argb()
			else:
				attribs.append((attrib, value))
		self.skinAttributes = attribs
		self.l.setFont(0, self.font)
		return GUIAddon.applySkin(self, desktop, parent)
	
	def _calcTextWidth(self, text, font=None, size=None):
		if size:
			self.textRenderer.instance.resize(size)
		if font:
			self.textRenderer.instance.setFont(font)
		self.textRenderer.text = text
		return self.textRenderer.instance.calculateSize().width()
	
	def getDesktopWith(self):
		return getDesktop(0).size().width()
