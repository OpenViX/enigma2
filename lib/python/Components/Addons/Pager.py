from Components.Addons.GUIAddon import GUIAddon
import math

from enigma import eListbox, eListboxPythonMultiContent, BT_ALIGN_CENTER
from Tools.LoadPixmap import LoadPixmap

from Tools.Directories import resolveFilename, SCOPE_GUISKIN
from Components.MultiContent import MultiContentEntryPixmapAlphaBlend


class Pager(GUIAddon):
	def __init__(self):
		GUIAddon.__init__(self)
		self.itemHeight = 25
		self.sourceHeight = 25
		self.current_index = 0
		self.l_list = []
		self.l = eListboxPythonMultiContent()
		self.l.setBuildFunc(self.buildEntry)
		self.l.setItemHeight(self.itemHeight)
		self.picDotPage = LoadPixmap(resolveFilename(SCOPE_GUISKIN, "icons/dot.png"))
		self.picDotCurPage = LoadPixmap(resolveFilename(SCOPE_GUISKIN, "icons/dotfull.png"))

	def onContainerShown(self):
		# disable listboxes default scrollbars
		if self.source.instance:
			self.source.instance.setScrollbarMode(2)

		if self.initPager not in self.source.onSelectionChanged:
			self.source.onSelectionChanged.append(self.initPager)
		self.initPager()

	GUI_WIDGET = eListbox

	def buildEntry(self, currentPage, pageCount):
		width = self.l.getItemSize().width()
		xPos = width

		if self.picDotPage:
			pixd_size = self.picDotPage.size()
			pixd_width = pixd_size.width()
			pixd_height = pixd_size.height()
			width_dots = pixd_width + (pixd_width + 5)*pageCount
			xPos = (width - width_dots)/2 - pixd_width/2
		res = [ None ]
		if pageCount > 0:
			for x in range(pageCount + 1):
				if self.picDotPage and self.picDotCurPage:
					res.append(MultiContentEntryPixmapAlphaBlend(
								pos=(xPos, 0),
								size=(pixd_width, pixd_height),
								png=self.picDotCurPage if x == currentPage else self.picDotPage,
								backcolor=None, backcolor_sel=None, flags=BT_ALIGN_CENTER))
					xPos += pixd_width + 5
		return res

	def selChange(self, currentPage, pagesCount):
		self.l_list = []
		self.l_list.append((currentPage, pagesCount))
		self.l.setList(self.l_list)

	def postWidgetCreate(self, instance):
		instance.setSelectionEnable(False)
		instance.setContent(self.l)
		instance.allowNativeKeys(False)

	def getCurrentIndex(self):
		if hasattr(self.source, "index"):
			return self.source.index
		return self.source.l.getCurrentSelectionIndex()

	def getSourceHeight(self):
		return self.source.instance.size().height()

	def getListCount(self):
		if hasattr(self.source, 'listCount'):
			return self.source.listCount
		elif hasattr(self.source, 'list'):
			return len(self.source.list)
		else:
			return len(self.source.list)

	def getListItemHeight(self):
		if hasattr(self.source, 'content'):
			return self.source.content.getItemSize().height()
		return self.source.l.getItemSize().height()
	
	def initPager(self):
		listH = self.getSourceHeight()
		if listH > 0:
			current_index = self.getCurrentIndex()
			listCount = self.getListCount()
			itemHeight = self.getListItemHeight()
			items_per_page = listH//itemHeight
			if items_per_page > 0:
				currentPageIndex = math.floor(current_index/items_per_page)
				pagesCount = math.ceil(listCount/items_per_page) - 1
				self.selChange(currentPageIndex,pagesCount)

	def applySkin(self, desktop, parent):
		attribs = [ ]
		for (attrib, value) in self.skinAttributes:
			if attrib == "picPage":
				pic = LoadPixmap(resolveFilename(SCOPE_GUISKIN, value))
				if pic:
					self.picDotPage = pic
			elif attrib == "picPageCurrent":
				pic = LoadPixmap(resolveFilename(SCOPE_GUISKIN, value))
				if pic:
					self.picDotCurPage = pic
			else:
				attribs.append((attrib, value))
		self.skinAttributes = attribs
		return GUIAddon.applySkin(self, desktop, parent)