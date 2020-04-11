import skin
from time import localtime, time, strftime

from enigma import eEPGCache, eListbox, eListboxPythonMultiContent, loadPNG, gFont, getDesktop, eRect, eSize, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, RT_VALIGN_CENTER, RT_VALIGN_TOP, RT_WRAP, BT_SCALE, BT_KEEP_ASPECT_RATIO, BT_ALIGN_CENTER
from skin import parseColor, parseFont

from Components.GUIComponent import GUIComponent
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmapAlphaBlend, MultiContentEntryPixmapAlphaTest
from Components.config import config
from EpgListBase import EPGListBase

# Various value are in minutes, while others are in seconds.
# Use this to remind us what is going on...
SECS_IN_MIN = 60

class EPGListMulti(EPGListBase):
	def __init__(self, selChangedCB = None, timer = None):
		EPGListBase.__init__(self, selChangedCB, timer)

		self.eventFontName = "Regular"
		if self.screenwidth == 1920:
			self.eventFontSize = 28
		else:
			self.eventFontSize = 20

		self.l.setBuildFunc(self.buildEntry)

	def applySkin(self, desktop, screen):
		rc = EPGListBase.applySkin(self, desktop, screen)
		self.setItemsPerPage()
		return rc

	def getCurrentChangeCount(self):
		return self.l.getCurrentSelection()[7] if self.l.getCurrentSelection() is not None else 0

	def setItemsPerPage(self):
		if self.numberOfRows:
			config.epgselection.multi.itemsperpage.default = self.numberOfRows
		if self.listHeight > 0:
			itemHeight = self.listHeight / config.epgselection.multi.itemsperpage.value
		else:
			itemHeight = 32
		if itemHeight < 20:
			itemHeight = 20
		self.l.setItemHeight(itemHeight)
		self.instance.resize(eSize(self.listWidth, self.listHeight / itemHeight * itemHeight))
		self.listHeight = self.instance.size().height()
		self.listWidth = self.instance.size().width()
		self.itemHeight = itemHeight

	def setFontsize(self):
		self.l.setFont(0, gFont(self.eventFontName, self.eventFontSize + config.epgselection.multi.eventfs.value))
		self.l.setFont(1, gFont(self.eventFontName, self.eventFontSize - 4 + config.epgselection.multi.eventfs.value))

	def postWidgetCreate(self, instance):
		instance.setWrapAround(False)
		instance.selectionChanged.get().append(self.selectionChanged)
		instance.setContent(self.l)

	def preWidgetRemove(self, instance):
		instance.selectionChanged.get().remove(self.selectionChanged)
		instance.setContent(None)

	def recalcEntrySize(self):
		esize = self.l.getItemSize()
		width = esize.width()
		height = esize.height()
		fontSize = self.eventFontSize + config.epgselection.multi.eventfs.value
		servScale, timeScale, durScale, wideScale = skin.parameters.get("EPGMultiColumnScales", (6.5, 6.0, 4.5, 1.5))
		servW = int(fontSize * servScale)
		timeW = int(fontSize * timeScale)
		durW = int(fontSize * durScale)
		left, servWidth, sepWidth, timeWidth, progHeight, breakWidth, durWidth, gapWidth = skin.parameters.get("EPGMultiColumnSpecs", (0, servW, 10, timeW, height - 12, 10, durW, 10))
		if config.usage.time.wide.value:
			timeWidth = int(timeWidth * wideScale)
		self.service_rect = eRect(left, 0, servWidth, height)
		left += servWidth + sepWidth
		self.start_end_rect = eRect(left, 0, timeWidth, height)
		progTop = int((height - progHeight) / 2)
		self.progress_rect = eRect(left, progTop, timeWidth, progHeight)
		left += timeWidth + breakWidth
		self.duration_rect = eRect(left, 0, durWidth, height)
		left += durWidth + gapWidth
		self.descr_rect = eRect(left, 0, width - left, height)

	def buildEntry(self, service, eventId, beginTime, duration, EventName, nowTime, service_name, changecount):
		r1 = self.service_rect
		r2 = self.start_end_rect
		r3 = self.progress_rect
		r4 = self.duration_rect
		r5 = self.descr_rect
		res = [
			None,  # no private data needed
			(eListboxPythonMultiContent.TYPE_TEXT, r1.left(), r1.top(), r1.width(), r1.height(), 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, service_name)
		]
		if beginTime is not None:
			fontSize = self.eventFontSize + config.epgselection.multi.eventfs.value
			if nowTime < beginTime:
				begin = localtime(beginTime)
				end = localtime(beginTime + duration)
				split = int(r2.width() * 0.55)
				res.extend((
					(eListboxPythonMultiContent.TYPE_TEXT, r2.left(), r2.top(), split, r2.height(), 0, RT_HALIGN_RIGHT | RT_VALIGN_CENTER, strftime(config.usage.time.short.value + " - ", begin)),
					(eListboxPythonMultiContent.TYPE_TEXT, r2.left() + split, r2.top(), r2.width() - split, r2.height(), 0, RT_HALIGN_RIGHT | RT_VALIGN_CENTER, strftime(config.usage.time.short.value, end))
				))
				remaining = duration / SECS_IN_MIN
				prefix = ""
			else:
				percent = (nowTime - beginTime) * 100 / duration
				remaining = ((beginTime + duration) - int(time())) / SECS_IN_MIN
				if remaining <= 0:
					prefix = ""
				else:
					prefix = "+"
				res.append((eListboxPythonMultiContent.TYPE_PROGRESS, r3.left(), r3.top(), r3.width(), r3.height(), percent))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, r4.left(), r4.top(), r4.width(), r4.height(), 0, RT_HALIGN_RIGHT | RT_VALIGN_CENTER, _("%s%d Min") % (prefix, remaining)))
			width = r5.width()
			clock_types = self.getPixmapForEntry(service, eventId, beginTime, duration)
			if clock_types:
				clk_sz = 25 if self.screenwidth == 1920 else 21
				width -= clk_sz / 2 if clock_types in (1, 6, 11) else clk_sz
				res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, r5.left() + width, (r5.height() - clk_sz) / 2, clk_sz, clk_sz, self.clocks[clock_types]))
				if self.wasEntryAutoTimer and clock_types in (2, 7, 12):
					width -= clk_sz + 1
					res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, r5.left() + width, (r5.height() - clk_sz) / 2, clk_sz, clk_sz, self.autotimericon))
				width -= 5
			res.append((eListboxPythonMultiContent.TYPE_TEXT, r5.left(), r5.top(), width, r5.height(), 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, EventName))
		return res

	def getSelectionPosition(self):
		# Adjust absolute indx to indx in displayed view
		indx = self.l.getCurrentSelectionIndex() % config.epgselection.multi.itemsperpage.value
		sely = self.instance.position().y() + self.itemHeight * indx
		if sely >= self.instance.position().y() + self.listHeight:
			sely -= self.listHeight
		return self.listWidth, sely

	def fillEPG(self, services, stime=None):
		test = [ (service.ref.toString(), 0, stime) for service in services ]
		test.insert(0, 'XRIBDTCn0')
		self.list = self.queryEPG(test)
		self.l.setList(self.list)
		self.recalcEntrySize()

	def updateEPG(self, direction):
		test = [ x[2] and (x[0], direction, x[2]) or (x[0], direction, 0) for x in self.list ]
		test.insert(0, 'XRIBDTCn')
		epg_data = self.queryEPG(test)
		cnt = 0
		for x in epg_data:
			changecount = self.list[cnt][7] + direction
			if changecount >= 0:
				if x[2] is not None:
					self.list[cnt] = (x[0], x[1], x[2], x[3], x[4], x[5], x[6], changecount)
			cnt+=1
		self.l.setList(self.list)
		self.recalcEntrySize()

	def getSelectedEventId(self):
		x = self.l.getCurrentSelection()
		return x and x[0]

	def moveToEventId(self, eventId):
		if not eventId:
			return
		index = 0
		for x in self.list:
			if x[0] == eventId:
				self.instance.moveSelectionTo(index)
				break
			index += 1
