from time import localtime, time, strftime

from enigma import eEPGCache, eListboxPythonMultiContent, gFont, eRect, eSize, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, RT_VALIGN_CENTER, RT_VALIGN_TOP, RT_WRAP, BT_SCALE, BT_KEEP_ASPECT_RATIO, BT_ALIGN_CENTER
from skin import parameters, parseFont, applySkinFactor

from Components.config import config
from Components.EpgListBase import EPGListBase
import NavigationInstance

# Various value are in minutes, while others are in seconds.
# Use this to remind us what is going on...
SECS_IN_MIN = 60


class EPGListSingle(EPGListBase):
	def __init__(self, session, epgConfig, selChangedCB=None):
		EPGListBase.__init__(self, session, selChangedCB)

		self.epgConfig = epgConfig
		self.eventFontName = "Regular"
		self.eventFontSize = applySkinFactor(19)
		self.l.setBuildFunc(self.buildEntry)

	def applySkin(self, desktop, screen):
		if self.skinAttributes is not None:
			attribs = []
			for (attrib, value) in self.skinAttributes:
				if attrib in ('EventFontSingle', 'EventFontMulti', 'EventFont'):
					font = parseFont(value, ((1, 1), (1, 1)))
					self.eventFontName = font.family
					self.eventFontSize = font.pointSize
				else:
					attribs.append((attrib, value))
			self.skinAttributes = attribs
		return EPGListBase.applySkin(self, desktop, screen)

	def setItemsPerPage(self):
		EPGListBase.setItemsPerPage(self, 32)

	def setFontsize(self):
		self.l.setFont(0, gFont(self.eventFontName, self.eventFontSize + self.epgConfig.eventfs.value))

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
		fontSize = self.eventFontSize + self.epgConfig.eventfs.value
		dateScale, timesScale, wideScale = parameters.get("EPGSingleColumnScales", (5.7, 6.0, 1.5))
		dateW = int(fontSize * dateScale)
		timesW = int(fontSize * timesScale)
		left, dateWidth, sepWidth, timesWidth, breakWidth = parameters.get("EPGSingleColumnSpecs", (0, dateW, 5, timesW, 20))
		if config.usage.time.wide.value:
			timesWidth = int(timesWidth * wideScale)
		self._weekdayRect = eRect(left, 0, dateWidth, height)
		left += dateWidth + sepWidth
		self._datetimeRect = eRect(left, 0, timesWidth, height)
		left += timesWidth + breakWidth
		self._descrRect = eRect(left, 0, width - left, height)
		self.showend = True  # This is not an unused variable. It is a flag used by EPGSearch plugin

	def buildEntry(self, service, eventId, beginTime, duration, eventName):
		timer, matchType = self.session.nav.RecordTimer.isInTimer(service, beginTime, duration)
		timerIcon, autoTimerIcon = self.getPixmapsForTimer(timer, matchType)
		r1 = self._weekdayRect
		r2 = self._datetimeRect
		r3 = self._descrRect
		split = int(r2.width() * 0.55)
		t = localtime(beginTime)
		et = localtime(beginTime + duration)
		res = [
			None,  # No private data needed.
			(eListboxPythonMultiContent.TYPE_TEXT, r1.left(), r1.top(), r1.width(), r1.height(), 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, strftime(config.usage.date.dayshort.value, t)),
			(eListboxPythonMultiContent.TYPE_TEXT, r2.left(), r2.top(), split, r2.height(), 0, RT_HALIGN_RIGHT | RT_VALIGN_CENTER, strftime(config.usage.time.short.value + " -", t)),
			(eListboxPythonMultiContent.TYPE_TEXT, r2.left() + split, r2.top(), r2.width() - split, r2.height(), 0, RT_HALIGN_RIGHT | RT_VALIGN_CENTER, strftime(config.usage.time.short.value, et))
		]
		eventW = r3.width()
		if timerIcon:
			clockSize = applySkinFactor(17)
			eventW -= clockSize
			res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, r3.left() + r3.width() - clockSize, (r3.height() - clockSize) / 2, clockSize, clockSize, timerIcon))
			if autoTimerIcon:
				eventW -= clockSize
				res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, r3.left() + r3.width() - clockSize * 2, (r3.height() - clockSize) / 2, clockSize, clockSize, autoTimerIcon))
		res.append((eListboxPythonMultiContent.TYPE_TEXT, r3.left(), r3.top(), eventW, r3.height(), 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, eventName))
		return res

	def fillSimilarList(self, refstr, eventId):
		# Search similar broadcastings.
		if eventId is None:
			return
		self.list = self.epgcache.search(('RIBDN', 1024, eEPGCache.SIMILAR_BROADCASTINGS_SEARCH, refstr, eventId))
		if self.list and len(self.list):
			self.list.sort(key=lambda x: x[2])
		self.l.setList(self.list)
		self.recalcEntrySize()
		self.selectionChanged()

	def fillEPG(self, service):
		now = time()
		epgTime = now - config.epg.histminutes.value * SECS_IN_MIN
		test = ['RIBDT', (service.toString(), 0, epgTime, -1)]
		self.list = self.queryEPG(test)

		odds = chr(0xc2) + chr(0x86)
		odde = chr(0xc2) + chr(0x87)
		# Assume that events *might* have leading 0xC2+0x86 chars and
		# trailing 0xC2+0x87 ones, which need to be removed...(probably from
		# now and next?).
		# Just step through the list until we don't modify one whose start
		# time is after "now".
		# NOTE: that the list is a list of tuples, so we can't modify just the
		#       Title, but have to replace it with a modified tuple.
		for i in range(0, len(self.list)):
			if self.list[i][4][:2] == odds and self.list[i][4][-2:] == odde:
				tlist = list(self.list[i])
				tlist[4] = tlist[4][2:-2]
				self.list[i] = tuple(tlist)
			else:
				if self.list[i][2] > now:
					break
		# Add explicit gaps if data isn't available.
		for i in range(len(self.list) - 1, 0, -1):
			thisBeg = self.list[i][2]
			prevEnd = self.list[i - 1][2] + self.list[i - 1][3]
			if prevEnd + 5 * SECS_IN_MIN < thisBeg:
				self.list.insert(i, (self.list[i][0], None, prevEnd, thisBeg - prevEnd, None))
		self.__sortList()
		self.l.setList(self.list)
		self.recalcEntrySize()

	def __sortList(self):
		sortType = int(config.epgselection.sort.value)
		if sortType == 1:
			self.list.sort(key=lambda x: (x[4] and x[4].lower(), x[2]))
		else:
			assert(sortType == 0)
			self.list.sort(key=lambda x: x[2])

	def sortEPG(self):
		if self.list:
			eventId = self.getSelectedEventId()
			self.__sortList()
			self.l.invalidate()
			self.moveToEventId(eventId)

	def getSelectedEventStartTime(self):
		x = self.l.getCurrentSelection()
		return x and x[2]

	def getSelectedEventId(self):
		x = self.l.getCurrentSelection()
		return x and x[1]

	def moveToEventId(self, eventId):
		if not eventId:
			return
		index = 0
		for x in self.list:
			if x[1] == eventId:
				self.instance.moveSelectionTo(index)
				break
			index += 1

	def selectEventAtTime(self, selectTime):
		index = 0
		for x in self.list:
			if x[2] <= selectTime < x[2] + x[3]:
				self.instance.moveSelectionTo(index)
				break
			index += 1
