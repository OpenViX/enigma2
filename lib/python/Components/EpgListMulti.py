from time import localtime, time, strftime

from enigma import eEPGCache, eListboxPythonMultiContent, gFont, eRect, eSize, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, RT_VALIGN_CENTER, RT_VALIGN_TOP, RT_WRAP, BT_SCALE, BT_KEEP_ASPECT_RATIO, BT_ALIGN_CENTER
from skin import parameters, applySkinFactor

from Components.EpgListBase import EPGListBase
from Components.GUIComponent import GUIComponent
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmapAlphaBlend, MultiContentEntryPixmapAlphaTest
from Components.config import config
import NavigationInstance

# Various value are in minutes, while others are in seconds.
# Use this to remind us what is going on...
SECS_IN_MIN = 60


class EPGListMulti(EPGListBase):
	def __init__(self, session, epgConfig, selChangedCB=None):
		EPGListBase.__init__(self, session, selChangedCB)

		self.epgConfig = epgConfig
		self.eventFontName = "Regular"
		self.eventFontSize = applySkinFactor(18)
		self.l.setBuildFunc(self.buildEntry)

	def getCurrentChangeCount(self):
		return self.l.getCurrentSelection()[7] if self.l.getCurrentSelection() is not None else 0

	def setItemsPerPage(self):
		EPGListBase.setItemsPerPage(self, 32)

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
		servScale, timeScale, durScale, wideScale = parameters.get("EPGMultiColumnScales", (config.epgselection.multi.servicewidth.value, 6.0, 4.5, 1.5))
		servW = int(fontSize * servScale)
		timeW = int(fontSize * timeScale)
		durW = int(fontSize * durScale)
		left, servWidth, sepWidth, timeWidth, progHeight, breakWidth, durWidth, gapWidth = parameters.get("EPGMultiColumnSpecs", (0, servW, 10, timeW, height - 12, 10, durW, 10))
		if config.usage.time.wide.value:
			timeWidth = int(timeWidth * wideScale)
		self.serviceRect = eRect(left, 0, servWidth, height)
		left += servWidth + sepWidth
		self.startEndRect = eRect(left, 0, timeWidth, height)
		progTop = int((height - progHeight) / 2)
		self.progressRect = eRect(left, progTop, timeWidth, progHeight)
		left += timeWidth + breakWidth
		self.durationRect = eRect(left, 0, durWidth, height)
		left += durWidth + gapWidth
		self.descrRect = eRect(left, 0, width - left, height)

	def buildEntry(self, service, eventId, beginTime, duration, EventName, nowTime, serviceName, changeCount):
		r1 = self.serviceRect
		r2 = self.startEndRect
		r3 = self.progressRect
		r4 = self.durationRect
		r5 = self.descrRect
		res = [
			None,  # No private data needed.
			(eListboxPythonMultiContent.TYPE_TEXT, r1.left(), r1.top(), r1.width(), r1.height(), 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serviceName)
		]
		if beginTime is not None:
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
				prefix = "" if remaining <= 0 else "+"
				res.append((eListboxPythonMultiContent.TYPE_PROGRESS, r3.left(), r3.top(), r3.width(), r3.height(), percent))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, r4.left(), r4.top(), r4.width(), r4.height(), 0, RT_HALIGN_RIGHT | RT_VALIGN_CENTER, _("%s%d Min") % (prefix, remaining)))
			width = r5.width()
			timer, matchType = self.session.nav.RecordTimer.isInTimer(service, beginTime, duration)
			if timer:
				clockSize = applySkinFactor(17)
				width -= clockSize / 2 if matchType == 0 else clockSize
				timerIcon, autoTimerIcon = self.getPixmapsForTimer(timer, matchType)
				res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, r5.left() + width, (r5.height() - clockSize) / 2, clockSize, clockSize, timerIcon))
				if autoTimerIcon:
					width -= clockSize + 1
					res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, r5.left() + width, (r5.height() - clockSize) / 2, clockSize, clockSize, autoTimerIcon))
				width -= 5
			res.append((eListboxPythonMultiContent.TYPE_TEXT, r5.left(), r5.top(), width, r5.height(), 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, EventName))
		return res

	def fillEPG(self, services, stime=None):
		test = [(service.ref.toString(), 0, stime) for service in services]
		test.insert(0, 'XRIBDTCn0')
		self.list = self.queryEPG(test)
		self.l.setList(self.list)
		self.recalcEntrySize()
		self.snapshotTimers(stime or time())

	def snapshotTimers(self, startTime):
		# take a snapshot of the timers relevant to the span of the grid
		timerList = self.session.nav.RecordTimer.timer_list

		self.filteredTimerList = {}
		for x in timerList:
			if x.end >= startTime:
				service = ":".join(x.service_ref.ref.toString().split(':')[:11])
				l = self.filteredTimerList.get(service)
				if l is None:
					self.filteredTimerList[service] = l = [x]
				else:
					l.append(x)
				if x.begin > startTime + 6 * 3600:
					break

	def updateEPG(self, direction):
		test = [x[2] and (x[0], direction, x[2]) or (x[0], direction, 0) for x in self.list]
		test.insert(0, 'XRIBDTCn')
		epgData = self.queryEPG(test)
		cnt = 0
		for x in epgData:
			changeCount = self.list[cnt][7] + direction
			if changeCount >= 0 and x[2] is not None:
				self.list[cnt] = (x[0], x[1], x[2], x[3], x[4], x[5], x[6], changeCount)
			cnt += 1
		self.l.setList(self.list)
		self.recalcEntrySize()
