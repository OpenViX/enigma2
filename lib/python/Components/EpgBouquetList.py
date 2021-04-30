from time import localtime, time, strftime

from enigma import eEPGCache, eListbox, eListboxPythonMultiContent, gFont, eRect, eSize, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, RT_VALIGN_CENTER, RT_VALIGN_TOP, RT_WRAP, BT_SCALE, BT_KEEP_ASPECT_RATIO, BT_ALIGN_CENTER

from skin import parseColor, parseFont, parseScale
from Components.GUIComponent import GUIComponent
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmapAlphaBlend, MultiContentEntryPixmapAlphaTest
from Tools.Alternatives import CompareWithAlternatives
from Tools.Directories import SCOPE_CURRENT_SKIN, resolveFilename
from Tools.LoadPixmap import LoadPixmap


class EPGBouquetList(GUIComponent):
	def __init__(self, graphic=False):
		GUIComponent.__init__(self)
		self.graphic = graphic
		self.l = eListboxPythonMultiContent()
		self.l.setBuildFunc(self.buildEntry)
		self.onSelChanged = []

		self.foreColor = 0xffffff
		self.foreColorSelected = 0xffffff
		self.backColor = 0x2D455E
		self.backColorSelected = 0xd69600

		self.borderColor = 0xC0C0C0
		self.borderWidth = 1

		self.othPix = None
		self.selPix = None
		self.graphicsloaded = False

		self.bouquetFontName = "Regular"
		self.bouquetFontSize = 20

		self.itemHeight = 31
		self.listHeight = None
		self.listWidth = None

		self.bouquetNamePadding = 3
		self.bouquetNameAlign = "left"
		self.bouquetNameWrap = "no"

	def applySkin(self, desktop, screen):
		if self.skinAttributes is not None:
			attribs = []
			for (attrib, value) in self.skinAttributes:
				if attrib == "font":
					font = parseFont(value, ((1, 1), (1, 1)))
					self.bouquetFontName = font.family
					self.bouquetFontSize = font.pointSize
				elif attrib == "foregroundColor":
					self.foreColor = parseColor(value).argb()
				elif attrib == "backgroundColor":
					self.backColor = parseColor(value).argb()
				elif attrib == "foregroundColorSelected":
					self.foreColorSelected = parseColor(value).argb()
				elif attrib == "backgroundColorSelected":
					self.backColorSelected = parseColor(value).argb()
				elif attrib == "borderColor":
					self.borderColor = parseColor(value).argb()
				elif attrib == "borderWidth":
					self.borderWidth = parseScale(value)
				elif attrib == "itemHeight":
					self.itemHeight = parseScale(value)
				else:
					attribs.append((attrib, value))
			self.skinAttributes = attribs
		rc = GUIComponent.applySkin(self, desktop, screen)
		self.setFontsize()
		self.listHeight = self.instance.size().height()
		self.listWidth = self.instance.size().width()
		self.l.setItemHeight(self.itemHeight)
		return rc

	GUI_WIDGET = eListbox

	def getCurrentBouquet(self):
		return self.l.getCurrentSelection()[0]

	def getCurrentBouquetService(self):
		return self.l.getCurrentSelection()[1]

	def selectionChanged(self):
		for x in self.onSelChanged:
			if x is not None:
				x()

	def setCurrentIndex(self, index):
		if self.instance is not None:
			self.instance.moveSelectionTo(index)
			self.currentBouquetService = self.getCurrentBouquetService()

	def moveTo(self, dir):
		if self.instance is not None:
			self.instance.moveSelection(dir)
			self.currentBouquetService = self.getCurrentBouquetService()

	def setFontsize(self):
		self.l.setFont(0, gFont(self.bouquetFontName, self.bouquetFontSize))

	def postWidgetCreate(self, instance):
		self.l.setSelectableFunc(True)
		instance.setWrapAround(True)
		instance.selectionChanged.get().append(self.selectionChanged)
		instance.setContent(self.l)

	def preWidgetRemove(self, instance):
		instance.selectionChanged.get().append(self.selectionChanged)
		instance.setContent(None)

	def selectionEnabled(self, enabled):
		if self.instance is not None:
			self.instance.setSelectionEnable(enabled)

	def recalcEntrySize(self):
		esize = self.l.getItemSize()
		width = esize.width()
		height = esize.height()
		self.bouquetRect = eRect(0, 0, width, height)

	def getBouquetRect(self):
		rc = self.bouquetRect
		return eRect(rc.left() + (self.instance and self.instance.position().x() or 0), rc.top(), rc.width(), rc.height())

	def buildEntry(self, name, service):
		r1 = self.bouquetRect
		left = r1.left()
		top = r1.top()
		width = r1.width()
		height = r1.height()
		selected = self.currentBouquetService == service

		alignment = RT_VALIGN_CENTER | RT_HALIGN_LEFT if self.bouquetNameAlign == "left" else RT_HALIGN_CENTER
		if self.bouquetNameWrap == "yes":
			alignment |= RT_WRAP

		res = [None]

		foreColor = self.foreColor
		backColor = self.backColor
		foreColorSel = self.foreColorSelected
		backColorSel = self.backColorSelected
		if self.graphic:
			if selected:
				borderTopPix = self.borderSelectedTopPix
				borderLeftPix = self.borderSelectedLeftPix
				borderBottomPix = self.borderSelectedBottomPix
				borderRightPix = self.borderSelectedRightPix
				bgpng = self.selPix
			else:
				borderTopPix = self.borderTopPix
				borderLeftPix = self.borderLeftPix
				borderBottomPix = self.borderBottomPix
				borderRightPix = self.borderRightPix
				bgpng = self.othPix

			if bgpng is not None:
				backColor = None
				backColorSel = None

		# box background
		if self.graphic and bgpng is not None:
			res.append(MultiContentEntryPixmapAlphaTest(
				pos=(left + self.borderWidth, top + self.borderWidth),
				size=(width - 2 * self.borderWidth, height - 2 * self.borderWidth),
				png=bgpng,
				flags=BT_SCALE))
		else:
			res.append(MultiContentEntryText(
				pos=(left, top), size=(width, height),
				font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
				text="", color=None, color_sel=None,
				backcolor=backColor, backcolor_sel=backColorSel,
				border_width=self.borderWidth, border_color=self.borderColor))

		evX = left + self.borderWidth + self.bouquetNamePadding
		evY = top + self.borderWidth
		evW = width - 2 * (self.borderWidth + self.bouquetNamePadding)
		evH = height - 2 * self.borderWidth

		res.append(MultiContentEntryText(
			pos=(evX, evY), size=(evW, evH),
			font=0, flags=alignment,
			text=name,
			color=foreColor, color_sel=foreColorSel,
			backcolor=backColor, backcolor_sel=backColorSel))

		# Borders
		if self.graphic:
			if borderTopPix is not None:
				res.append(MultiContentEntryPixmapAlphaTest(
						pos=(left, r1.top()),
						size=(r1.width(), self.borderWidth),
						png=borderTopPix,
						flags=BT_SCALE))
			if borderBottomPix is not None:
				res.append(MultiContentEntryPixmapAlphaTest(
						pos =(left, r1.height() - self.borderWidth),
						size=(r1.width(), self.borderWidth),
						png=borderBottomPix,
						flags=BT_SCALE))
			if borderLeftPix is not None:
				res.append(MultiContentEntryPixmapAlphaTest(
						pos=(left, r1.top()),
						size=(self.borderWidth, r1.height()),
						png=borderLeftPix,
						flags=BT_SCALE))
			if borderRightPix is not None:
				res.append(MultiContentEntryPixmapAlphaTest(
						pos =(r1.width() - self.borderWidth, left),
						size=(self.borderWidth, r1.height()),
						png=borderRightPix,
						flags=BT_SCALE))

		return res

	def fillBouquetList(self, bouquets):
		if self.graphic and not self.graphicsloaded:
			self.othPix = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "epg/OtherEvent.png"))
			self.selPix = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "epg/SelectedCurrentEvent.png"))
			self.borderTopPix = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "epg/BorderTop.png"))
			self.borderBottomPix = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "epg/BorderLeft.png"))
			self.borderLeftPix = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "epg/BorderBottom.png"))
			self.borderRightPix = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "epg/BorderRight.png"))
			self.borderSelectedTopPix = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "epg/SelectedBorderTop.png"))
			self.borderSelectedLeftPix = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "epg/SelectedBorderLeft.png"))
			self.borderSelectedBottomPix = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "epg/SelectedBorderBottom.png"))
			self.borderSelectedRightPix = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "epg/SelectedBorderRight.png"))
			self.graphicsloaded = True
		self.bouquetslist = bouquets
		self.l.setList(self.bouquetslist)
		self.recalcEntrySize()
		self.selectionChanged()
		self.currentBouquetService = self.getCurrentBouquetService()
