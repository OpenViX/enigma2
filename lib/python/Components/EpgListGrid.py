from time import localtime, time, strftime

from enigma import eListbox, eListboxPythonMultiContent, eListboxEpgGridContent, eServiceReference, gFont, eRect, eSize, RT_HALIGN_LEFT, RT_VALIGN_CENTER, BT_SCALE

from skin import parseColor, parseFont, parseScale, applySkinFactor
from Components.EpgListBase import EPGListBase
from Components.GUIComponent import GUIComponent
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmapAlphaBlend
from Components.Renderer.Picon import getPiconName
from Components.config import config
from RecordTimer import RecordTimer, isPlaylist
from Tools.Alternatives import CompareWithAlternatives
from Tools.Directories import resolveFilename, SCOPE_CURRENT_SKIN
from Tools.LoadPixmap import LoadPixmap
from Tools.TextBoundary import getTextBoundarySize

MAX_TIMELINES = 6

# Various value are in minutes, while others are in seconds.
# Use this to remind us what is going on...
SECS_IN_MIN = 60

NO_DECOR = (-1, 0, 0, 0)  # (clockIcon, autoIcon, timerKind, fullMatch), see eListboxEpgGridContent


class EPGListGrid(EPGListBase):
	# Rows are drawn natively by eListboxEpgGridContent. Functions appended here are still honoured:
	# they are called as f(res, listInstance, service, serviceName, events, picon, channel) for every
	# painted row and the multi content entries they append to res (a list starting with None) are drawn
	# on top of the native row. picon is always None (the native renderer resolves picons itself).
	# While the list is empty there is no per-row Python call at all.
	buildEntryExtensionFunctions = []

	# Each row of self.list is the tuple the native renderer paints:
	#   (serviceRef, serviceName, events, channelNumber, decor, playing)
	# events: [(eventId, eventTitle, beginTime, duration), ...] or None
	# decor:  None or a list parallel to events, see NO_DECOR.
	def __init__(self, session, isInfobar, selChangedCB=None):
		EPGListBase.__init__(self, session, selChangedCB)
		self.l = eListboxEpgGridContent()  # noqa: E741 (replaces the multi content list of the base class)
		self.l.setGetPiconNameFunc(getPiconName)

		self.isInfobar = isInfobar
		self.epgConfig = config.epgselection.infobar if isInfobar else config.epgselection.grid
		self.timeFocus = time()  # Default to now.
		self.selectedEventIndex = None
		self.selectedService = None
		self.selectionRect = None
		self.eventRect = None
		self.serviceRect = None
		self.list = []
		self.filteredTimerList = {}
		self.timeBase = 0

		self.nowEvPix = None
		self.nowSelEvPix = None
		self.othEvPix = None
		self.selEvPix = None
		self.othServPix = None
		self.nowServPix = None
		self.recEvPix = None
		self.recSelEvPix = None
		self.zapEvPix = None
		self.zapSelEvPix = None

		self.borderTopPix = None
		self.borderBottomPix = None
		self.borderLeftPix = None
		self.borderRightPix = None
		self.borderSelectedTopPix = None
		self.borderSelectedLeftPix = None
		self.borderSelectedBottomPix = None
		self.borderSelectedRightPix = None
		self.infoPix = None
		self.selInfoPix = None

		self.borderColor = 0xC0C0C0
		self.borderColorService = 0xC0C0C0

		self.foreColor = 0xffffff
		self.foreColorSelected = 0xffffff
		self.backColor = 0x2D455E
		self.backColorSelected = 0xd69600
		self.foreColorService = 0xffffff
		self.backColorService = 0x2D455E
		self.foreColorNow = 0xffffff
		self.foreColorNowSelected = 0xffffff
		self.backColorNow = 0x00825F
		self.backColorNowSelected = 0xd69600
		self.foreColorServiceNow = 0xffffff
		self.backColorServiceNow = 0x00825F

		self.foreColorRecord = 0xffffff
		self.backColorRecord = 0xd13333
		self.foreColorRecordSelected = 0xffffff
		self.backColorRecordSelected = 0x9e2626
		self.foreColorZap = 0xffffff
		self.backColorZap = 0x669466
		self.foreColorZapSelected = 0xffffff
		self.backColorZapSelected = 0x436143

		self.serviceFontName = "Regular"
		self.eventFontName = "Regular"
		self.eventFontSize = self.serviceFontSize = applySkinFactor(19)

		self.serviceBorderWidth = 1
		self.serviceNamePadding = 3
		self.serviceNumberPadding = 9
		self.eventBorderWidth = 1
		self.eventNamePadding = 3
		self.serviceNumberWidth = 0
		self.eventTextSidesMargin = 0

		self._pushStaticPixmaps()
		self.loadConfig()

	def _pushStaticPixmaps(self):
		# icons shared with the other EPG lists, loaded by EPGListBase
		E = eListboxEpgGridContent
		for i in range(6):
			if self.clocks[i] is not None:
				self.l.setPixmap(E.pixClock0 + i, self.clocks[i])
			if self.selclocks[i] is not None:
				self.l.setPixmap(E.pixSelClock0 + i, self.selclocks[i])
		for idx, pix in ((E.pixAutoTimer, self.autotimericon), (E.pixIceTV, self.icetvicon), (E.pixCatchup, self.catchUpIcon)):
			if pix is not None:
				self.l.setPixmap(idx, pix)

	def loadConfig(self):
		self.graphic = self.epgConfig.type_mode.value == "graphics"
		self.graphicsloaded = False
		self.epgHistorySecs = int(config.epg.histminutes.value) * SECS_IN_MIN
		self.roundBySecs = int(self.epgConfig.roundto.value) * SECS_IN_MIN
		self.timeEpoch = int(self.epgConfig.prevtimeperiod.value)
		self.timeEpochSecs = self.timeEpoch * SECS_IN_MIN
		self.serviceTitleMode = self.epgConfig.servicetitle_mode.value.split("+")
		self.showServiceNumber = "servicenumber" in self.serviceTitleMode
		self.showServiceName = "servicename" in self.serviceTitleMode
		self.showPicon = "picon" in self.serviceTitleMode
		self.pushConfig()

	def buildExtensionEntry(self, service, serviceName, events, channel, decor, playing):
		res = [None]
		for f in EPGListGrid.buildEntryExtensionFunctions:
			f(res, self, service, serviceName, events, None, channel)
		return res

	def updateExtensions(self):
		self.l.setExtensionFunc(self.buildExtensionEntry if EPGListGrid.buildEntryExtensionFunctions else None)

	def pushConfig(self):
		# Everything the native renderer needs besides the rows. Cheap, so it is simply re-sent whenever
		# anything it depends on may have changed.
		recIconHeight = config.epgselection.grid.rec_icon_height.value
		self.l.setConfig({
			"graphic": self.graphic,
			"highlightNow": config.epgselection.grid.highlight_current_events.value,
			"titleOrder": self.serviceTitleMode,
			"timeBase": int(getattr(self, "timeBase", 0)),
			"timeEpochSecs": self.timeEpochSecs,
			"serviceWidth": self.serviceRect.width() if self.serviceRect else 0,
			"serviceBorderWidth": self.serviceBorderWidth,
			"serviceNamePadding": self.serviceNamePadding,
			"serviceNumberPadding": self.serviceNumberPadding,
			"eventBorderWidth": self.eventBorderWidth,
			"eventNamePadding": self.eventNamePadding,
			"eventTextSidesMargin": self.eventTextSidesMargin,
			"serviceNumberWidth": self.serviceNumberWidth,
			"piconWidth": self.epgConfig.piconwidth.value if self.showPicon else 0,
			"infoWidth": self.epgConfig.infowidth.value,
			"serviceNameAlign": int(config.epgselection.grid.servicename_alignment.value),
			"serviceNumberAlign": int(config.epgselection.grid.servicenumber_alignment.value),
			"eventAlign": int(config.epgselection.grid.event_alignment.value),
			"recIconPos": 0 if recIconHeight == "hide" else 1 if recIconHeight == "middle" else 2 if recIconHeight == "top" else 3
		})

	def pushColors(self):
		E = eListboxEpgGridContent
		for idx, value in (
			(E.colFore, self.foreColor), (E.colForeSel, self.foreColorSelected), (E.colBack, self.backColor), (E.colBackSel, self.backColorSelected),
			(E.colForeNow, self.foreColorNow), (E.colForeNowSel, self.foreColorNowSelected), (E.colBackNow, self.backColorNow), (E.colBackNowSel, self.backColorNowSelected),
			(E.colForeRec, self.foreColorRecord), (E.colForeRecSel, self.foreColorRecordSelected), (E.colBackRec, self.backColorRecord), (E.colBackRecSel, self.backColorRecordSelected),
			(E.colForeZap, self.foreColorZap), (E.colForeZapSel, self.foreColorZapSelected), (E.colBackZap, self.backColorZap), (E.colBackZapSel, self.backColorZapSelected),
			(E.colBorder, self.borderColor),
			(E.colServiceFore, self.foreColorService), (E.colServiceBack, self.backColorService),
			(E.colServiceForeNow, self.foreColorServiceNow), (E.colServiceBackNow, self.backColorServiceNow),
			(E.colServiceBorder, self.borderColorService)
		):
			self.l.setColor(idx, value & 0xffffffff)

	def applySkin(self, desktop, screen):
		if self.skinAttributes is not None:
			attribs = []
			for (attrib, value) in self.skinAttributes:
				if attrib == ("ServiceFontInfobar" if self.isInfobar else "ServiceFontGraphical"):
					font = parseFont(value, screen.scale)
					self.serviceFontName = font.family
					self.serviceFontSize = font.pointSize
				elif attrib == ("EntryFontInfobar" if self.isInfobar else "EntryFontGraphical"):
					font = parseFont(value, screen.scale)
					self.eventFontName = font.family
					self.eventFontSize = font.pointSize

				elif attrib == "ServiceForegroundColor":
					self.foreColorService = parseColor(value).argb()
				elif attrib == "ServiceForegroundColorNow":
					self.foreColorServiceNow = parseColor(value).argb()
				elif attrib == "ServiceBackgroundColor":
					self.backColorService = parseColor(value).argb()
				elif attrib == "ServiceBackgroundColorNow":
					self.backColorServiceNow = parseColor(value).argb()

				elif attrib == "EntryForegroundColor":
					self.foreColor = parseColor(value).argb()
				elif attrib == "EntryForegroundColorSelected":
					self.foreColorSelected = parseColor(value).argb()
				elif attrib == "EntryBackgroundColor":
					self.backColor = parseColor(value).argb()
				elif attrib == "EntryBackgroundColorSelected":
					self.backColorSelected = parseColor(value).argb()
				elif attrib == "EntryBackgroundColorNow":
					self.backColorNow = parseColor(value).argb()
				elif attrib == "EntryBackgroundColorNowSelected":
					self.backColorNowSelected = parseColor(value).argb()
				elif attrib == "EntryForegroundColorNow":
					self.foreColorNow = parseColor(value).argb()
				elif attrib == "EntryForegroundColorNowSelected":
					self.foreColorNowSelected = parseColor(value).argb()

				elif attrib == "EventTextSidesMargin":
					self.eventTextSidesMargin = parseScale(value)

				elif attrib == "ServiceBorderColor":
					self.borderColorService = parseColor(value).argb()
				elif attrib == "ServiceBorderWidth":
					self.serviceBorderWidth = parseScale(value)
				elif attrib == "ServiceNamePadding":
					self.serviceNamePadding = parseScale(value)
				elif attrib == "ServiceNumberPadding":
					self.serviceNumberPadding = parseScale(value)
				elif attrib == "EntryBorderColor":
					self.borderColor = parseColor(value).argb()
				elif attrib == "EventBorderWidth":
					self.eventBorderWidth = parseScale(value)
				elif attrib == "EventNamePadding":
					self.eventNamePadding = parseScale(value)

				elif attrib == "RecordForegroundColor":
					self.foreColorRecord = parseColor(value).argb()
				elif attrib == "RecordForegroundColorSelected":
					self.foreColorRecordSelected = parseColor(value).argb()
				elif attrib == "RecordBackgroundColor":
					self.backColorRecord = parseColor(value).argb()
				elif attrib == "RecordBackgroundColorSelected":
					self.backColorRecordSelected = parseColor(value).argb()
				elif attrib == "ZapForegroundColor":
					self.foreColorZap = parseColor(value).argb()
				elif attrib == "ZapBackgroundColor":
					self.backColorZap = parseColor(value).argb()
				elif attrib == "ZapForegroundColorSelected":
					self.foreColorZapSelected = parseColor(value).argb()
				elif attrib == "ZapBackgroundColorSelected":
					self.backColorZapSelected = parseColor(value).argb()
				else:
					attribs.append((attrib, value))
			self.skinAttributes = attribs
		rc = EPGListBase.applySkin(self, desktop, screen)
		self.pushColors()
		self.pushConfig()
		return rc

	def setTimeFocus(self, timeFocus):
		# prefer time being aligned in the middle of the EPG, but clip to the maximum EPG data history
		self.timeBase = int(timeFocus) - self.timeEpochSecs // 2
		abs0 = int(time()) - self.epgHistorySecs
		if self.timeBase < abs0:
			# we're viewing close to the start of EPG data
			# round down so that the if the timeline is being shown, it"s not right next to the left hand edge of the grid
			self.timeBase = abs0 - abs0 % self.roundBySecs
		else:
			# otherwise we're trying to place the desired time in the centre of the EPG
			# round up, so that slightly more of the future things are shown
			self.timeBase += -self.timeBase % self.roundBySecs
		self.timeFocus = timeFocus

	def setTimeEpoch(self, epoch):
		self.timeEpoch = epoch
		self.timeEpochSecs = epoch * SECS_IN_MIN
		self.fillEPG()

	def getTimeEpoch(self):
		return self.timeEpoch

	def getIndexFromService(self, serviceref):
		if serviceref is not None:
			for x in range(len(self.list)):
				if CompareWithAlternatives(self.list[x][0], serviceref):
					return x
				if CompareWithAlternatives(self.list[x][1], serviceref):
					return x
		return None

	def getCurrent(self):
		if self.selectedService is None:
			return None, None
		events = self.selectedService[2]
		refstr = self.selectedService[0]
		if self.selectedEventIndex is None or not events or (self.selectedEventIndex and events and self.selectedEventIndex > len(events) - 1):
			return None, eServiceReference(refstr)
		event = events[self.selectedEventIndex]  # (eventId, eventTitle, beginTime, duration)
		eventId = event[0]
		service = eServiceReference(refstr)
		event = self.getEventFromId(service, eventId)  # Get full event info.
		return event, service

	def setTimeFocusFromEvent(self, selectedEventIndex):
		if self.selectedService:
			events = self.selectedService[2]
			if events and len(events):
				self.selectedEventIndex = max(min(len(events) - 1, selectedEventIndex), 0)
				event = events[self.selectedEventIndex]

				# clip the selected event times to the current screen
				evTime = max(self.timeBase, event[2])
				evEndTime = min(event[2] + event[3], self.timeBase + self.timeEpochSecs)
				if evTime <= time() < evEndTime:
					# selected event contains the current time, user is interested in current things
					self.timeFocus = time()
				else:
					# user is looking at things roughly around the middle of the selected event
					self.timeFocus = evTime + (evEndTime - evTime) // 2
		else:
			self.selectedEventIndex = None

	GUI_WIDGET = eListbox

	def setItemsPerPage(self):
		EPGListBase.setItemsPerPage(self, 54)
		if not self.isInfobar and config.epgselection.grid.heightswitch.value:
			numberOfRows = (self.listHeight // self.itemHeight) or 8
			if ((self.listHeight / numberOfRows) / 3) >= 27:
				tmpItemHeight = int((self.listHeight / numberOfRows) / 3)
			elif ((self.listHeight / numberOfRows) / 2) >= 27:
				tmpItemHeight = int((self.listHeight / numberOfRows) / 2)
			else:
				tmpItemHeight = 27
			if tmpItemHeight < self.itemHeight:
				self.itemHeight = tmpItemHeight
			else:
				if ((self.listHeight / numberOfRows) * 3) <= 45:
					self.itemHeight = int((self.listHeight / numberOfRows) * 3)
				elif ((self.listHeight / numberOfRows) * 2) <= 45:
					self.itemHeight = int((self.listHeight / numberOfRows) * 2)
				else:
					self.itemHeight = 45
			self.l.setItemHeight(self.itemHeight)
			self.instance.resize(eSize(self.listWidth, self.listHeight // self.itemHeight * self.itemHeight))
			self.listHeight = self.instance.size().height()
	def setFontsize(self):
		self.l.setFont(0, gFont(self.serviceFontName, self.serviceFontSize + self.epgConfig.servfs.value))
		self.l.setFont(1, gFont(self.eventFontName, self.eventFontSize + self.epgConfig.eventfs.value))
		# Cache service number width.
		if self.showServiceNumber:
			fontConf = self.epgConfig.servfs.value
			if fontConf is not None:
				font = gFont(self.serviceFontName, self.serviceFontSize + fontConf)
				self.serviceNumberWidth = getTextBoundarySize(self.instance, font, self.instance.size(), "0000").width()
		self.pushConfig()

	def postWidgetCreate(self, instance):
		self.l.setOverjump(bool(config.epgselection.overjump.value))
		instance.setWrapAround(True)
		instance.setContent(self.l)
		instance.selectionChanged.get().append(self.serviceChanged)
		self.l.setSelectionClip(eRect(0, 0, 0, 0), False)

	def preWidgetRemove(self, instance):
		# release the rows now instead of leaving a big object graph for the garbage collector
		self.l.clearPiconCache()
		instance.selectionChanged.get().remove(self.serviceChanged)
		instance.setContent(None)

	def serviceChanged(self):
		self.selectEventFromTime()
		self.refreshSelection()

	def selectEventFromTime(self):
		self.selectedService = self.l.getCurrentSelection()
		if self.selectedService:
			self.selectedEventIndex = None
			events = self.selectedService[2]
			if events and len(events):
				self.selectedEventIndex = 0
				if self.timeFocus >= events[0][2]:
					for event in events:  # Iterate all events.
						evTime = event[2]
						evEndTime = evTime + event[3]
						self.selectedEventIndex += 1
						if evTime <= self.timeFocus < evEndTime:
							break
					self.selectedEventIndex -= 1

	def recalcEventSize(self):
		esize = self.l.getItemSize()
		width = esize.width()
		height = esize.height()

		w = 0
		if self.showServiceName:
			w += self.epgConfig.servicewidth.value + 2 * self.serviceNamePadding
		if self.showServiceNumber:
			w += self.serviceNumberWidth + 2 * self.serviceNumberPadding
		if self.showPicon:
			w += self.epgConfig.piconwidth.value
		self.serviceRect = eRect(0, 0, w, height)
		self.eventRect = eRect(w, 0, width - w, height)
		self.pushConfig()

	def calcEventPosAndWidthHelper(self, stime, duration, start, end, width):
		xpos = (stime - start) * width // (end - start)
		ewidth = (stime + duration - start) * width // (end - start)
		ewidth -= xpos
		if xpos < 0:
			ewidth += xpos
			xpos = 0
		if (xpos + ewidth) > width:
			ewidth = width - xpos
		return xpos, ewidth


	def getSelectionPosition(self):
		_, sely = EPGListBase.getSelectionPosition(self)
		return self.selectionRect.left() + self.selectionRect.width() + self.instance.position().x(), sely

	def refreshSelection(self):
		events = self.selectedService and self.selectedService[2]  # (service, serviceName, events, channel, decor, playing)
		if events and self.selectedEventIndex is not None and self.selectedEventIndex < len(events):
			event = events[self.selectedEventIndex]  # (eventId, eventTitle, beginTime, duration)
			xpos, width = self.calcEventPosAndWidthHelper(event[2], event[3],
				self.timeBase, self.timeBase + self.timeEpochSecs, self.eventRect.width())
			self.selectionRect = eRect(xpos + self.eventRect.left(), 0, width, self.eventRect.height())
			self.l.setSelectedEvent(self.selectedEventIndex)
			self.l.setSelectionClip(eRect(self.selectionRect.left(), self.selectionRect.top(), self.selectionRect.width(), self.selectionRect.height()), False)
		else:
			self.selectionRect = eRect(self.eventRect.left(), self.eventRect.top(), self.eventRect.width(), self.eventRect.height())
			self.l.setSelectedEvent(-1)
			# Have to copy construct the parameter for this native function or odd selection behaviour results.
			self.l.setSelectionClip(eRect(self.selectionRect.left(), self.selectionRect.top(), self.selectionRect.width(), self.selectionRect.height()), False)
		self.selectionChanged()

	def selEvent(self, dir, visible=True):
		if not self.selectedService:
			return False

		validEvent = self.selectedEventIndex is not None
		focusEvent = None
		timeBase = self.timeBase
		timeFocus = self.timeFocus
		if dir == +1:  # Next event.
			events = self.selectedService[2]  # (service, serviceName, events, picon)
			if validEvent and self.selectedEventIndex + 1 < len(events):
				self.setTimeFocusFromEvent(self.selectedEventIndex + 1)
				self.refreshSelection()
				self.l.invalidateEntry(self.l.getCurrentSelectionIndex())
				return False  # Same page.
			# Next event is the first item on the next page.
			timeBase += self.timeEpochSecs
			focusEvent = 0
		elif dir == -1:  # Prev event.
			if validEvent and self.selectedEventIndex > 0:
				self.setTimeFocusFromEvent(self.selectedEventIndex - 1)
				self.refreshSelection()
				self.l.invalidateEntry(self.l.getCurrentSelectionIndex())
				return False  # Same page.
			# Prev event is the last item on the previous page.
			timeBase -= self.timeEpochSecs
			focusEvent = 65535
		elif dir == +2:  # Next page.
			timeBase += self.timeEpochSecs
			timeFocus += self.timeEpochSecs
		elif dir == +24:  # Next day.
			timeBase += 86400
			timeFocus += 86400
		elif dir == -2:
			timeBase -= self.timeEpochSecs
			timeFocus -= self.timeEpochSecs
		elif dir == -24:  # Prevous day.
			timeBase -= 86400
			timeFocus -= 86400

		if timeBase < self.timeBase:
			# Keep the time base within the bounds of EPG data, rounded to a whole page.
			abs0 = int(time()) - self.epgHistorySecs
			abs0 -= abs0 % self.roundBySecs
			timeBase = max(abs0, timeBase)
			timeFocus = max(abs0, timeFocus)

		if self.timeBase == timeBase:
			return False

		# If we are still here and moving - do the move now and return True to indicate we've changed pages.
		self.timeBase = timeBase
		self.timeFocus = timeFocus
		self.fillEPGNoRefresh()
		if focusEvent is not None:
			self.setTimeFocusFromEvent(focusEvent)
		self.refreshSelection()
		return True


	def fillEPG(self, services=None):
		self.fillEPGNoRefresh(services)
		self.refreshSelection()

	def loadGraphics(self):
		E = eListboxEpgGridContent

		def load(idx, name):
			pix = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "epg/" + name))
			if pix is not None:
				self.l.setPixmap(idx, pix)
			return pix

		if self.graphic:
			self.nowEvPix = load(E.pixNowEvent, "CurrentEvent.png")
			self.nowSelEvPix = load(E.pixNowSelEvent, "SelectedCurrentEvent.png")
			self.othEvPix = load(E.pixOtherEvent, "OtherEvent.png")
			self.selEvPix = load(E.pixSelEvent, "SelectedEvent.png")
			self.othServPix = load(E.pixOtherService, "OtherService.png")
			self.nowServPix = load(E.pixNowService, "CurrentService.png")
			self.recEvPix = load(E.pixRecEvent, "RecordEvent.png")
			self.recSelEvPix = load(E.pixRecSelEvent, "SelectedRecordEvent.png")
			self.zapEvPix = load(E.pixZapEvent, "ZapEvent.png")
			self.zapSelEvPix = load(E.pixZapSelEvent, "SelectedZapEvent.png")
			self.borderTopPix = load(E.pixBorderTop, "BorderTop.png")
			self.borderBottomPix = load(E.pixBorderBottom, "BorderBottom.png")
			self.borderLeftPix = load(E.pixBorderLeft, "BorderLeft.png")
			self.borderRightPix = load(E.pixBorderRight, "BorderRight.png")
			self.borderSelectedTopPix = load(E.pixBorderSelTop, "SelectedBorderTop.png")
			self.borderSelectedBottomPix = load(E.pixBorderSelBottom, "SelectedBorderBottom.png")
			self.borderSelectedLeftPix = load(E.pixBorderSelLeft, "SelectedBorderLeft.png")
			self.borderSelectedRightPix = load(E.pixBorderSelRight, "SelectedBorderRight.png")
		self.infoPix = load(E.pixInfo, "information.png")
		self.selInfoPix = load(E.pixSelInfo, "SelectedInformation.png")
		self.graphicsloaded = True

	def buildDecor(self, serviceRef, events):
		# Timer information for each event of a service; only needs to be computed for services that actually have timers.
		serviceref = "1" + serviceRef[4:] if serviceRef[:4] in config.recording.setstreamto1.value and not isPlaylist(serviceRef) else serviceRef  # converts 4097, 5001, 5002 to 1
		serviceTimers = self.filteredTimerList.get(':'.join(serviceref.split(':')[:11]))
		if serviceTimers is None:
			return None
		# When recording-start-margin is zero allow recordings that start up to 20 seconds
		# after the program boundary to still produce matchType in (2, 3). This allows
		# correct display of "epg/RecordEvent.png" when multiple recodings are programmed to
		# start at the same instant.
		margin = 20 if config.recording.margin_before.value == 0 else 0
		decor = []
		hasTimer = False
		for ev in events:  # (eventId, eventTitle, beginTime, duration)
			timer, matchType = RecordTimer.isInTimerOnService(serviceTimers, ev[2] + margin, ev[3])
			if timer is None:
				decor.append(NO_DECOR)
				continue
			hasTimer = True
			clockIcon = matchType
			autoIcon = 0
			full = matchType == 3
			if full:
				# recording the whole event, add the timer type onto the icon lookup index
				clockIcon += 2 if timer.always_zap else 1 if timer.justplay else 0
				if hasattr(timer, "ice_timer_id") and timer.ice_timer_id:
					autoIcon = 2 if self.icetvicon else 0
				elif timer.isAutoTimer:
					autoIcon = 1 if self.autotimericon else 0
			kind = 0
			if matchType in (2, 3):
				kind = 1 if timer.justplay == 0 and timer.always_zap == 0 else 2
			decor.append((clockIcon, autoIcon, kind, 1 if full else 0))
		return decor if hasTimer else None

	def isPlayingService(self, serviceRef, playing=None):
		if playing is None:
			playing = self.session.nav.getCurrentlyPlayingServiceOrGroup()
		return 1 if CompareWithAlternatives(serviceRef, playing) else 0

	def refreshPlaying(self):
		# The playing service can change while the list is open; only touch rows whose state differs.
		playing = self.session.nav.getCurrentlyPlayingServiceOrGroup()
		changed = False
		for idx, row in enumerate(self.list):
			state = self.isPlayingService(row[0], playing)
			if row[5] != state:
				self.list[idx] = row[:5] + (state,)
				changed = True
		if changed:
			self.l.invalidate()

	def fillEPGNoRefresh(self, services=None):
		self.updateExtensions()
		if not self.graphicsloaded:
			self.loadGraphics()
			self.pushColors()

		if services is None:
			test = [(service[0], 0, self.timeBase, self.timeEpoch) for service in self.list]
			serviceList = self.list
			channelIdx = 3
		else:
			self.selectedEventIndex = None
			self.selectedService = None
			test = [(service.ref.toString(), 0, self.timeBase, self.timeEpoch) for service in services]
			serviceList = services
			channelIdx = None

		test.insert(0, "XRnITBD")  # return record, service ref, service name, event id, event title, begin time, duration
		epgData = self.queryEPG(test)
		self.list = []
		eventList = None
		serviceRef = ""
		serviceName = ""
		self.snapshotTimers(self.timeBase, self.timeBase + self.timeEpochSecs)
		playing = self.session.nav.getCurrentlyPlayingServiceOrGroup()

		def appendService():
			events = eventList if eventList[0][0] is not None else None
			channel = serviceList[serviceIdx][channelIdx] if channelIdx is not None else (self.getChannelNumber(serviceList[serviceIdx]) if self.showServiceNumber else None)
			self.list.append((serviceRef, serviceName, events, channel or 0, self.buildDecor(serviceRef, events) if events else None, self.isPlayingService(serviceRef, playing)))

		serviceIdx = 0
		for x in epgData:
			if serviceRef != x[0]:
				if eventList:
					appendService()
					serviceIdx += 1
				serviceRef = x[0]
				serviceName = x[1]
				eventList = []
			eventList.append((x[2], x[3], x[4], x[5]))  # (eventId, eventTitle, beginTime, duration)
		if eventList and len(eventList) > 0:
			appendService()

		self.l.setList(self.list)
		self.recalcEventSize()

	def snapshotTimers(self, startTime, endTime):
		# take a snapshot of the timers relevant to the span of the grid and index them by service
		# We scan the entire timerlist as pending timers and in progress timers are sorted differently
		self.filteredTimerList = {}
		for timer in self.session.nav.RecordTimer.timer_list:
			# repeat timers represent all their future repetitions, so always include them
			if (startTime <= timer.end or timer.repeated) and timer.begin < endTime:
				serviceref = timer.service_ref.ref.toCompareString()
				serviceref = "1" + serviceref[4:] if serviceref[:4] in config.recording.setstreamto1.value else serviceref  # converts 4097, 5001, 5002 to 1
				srefl = self.filteredTimerList.get(serviceref)
				if srefl is None:
					self.filteredTimerList[serviceref] = srefl = [timer]
				else:
					srefl.append(timer)

	def getChannelNumber(self, service):
		if service.ref and "0:0:0:0:0:0:0:0:0" not in service.ref.toString():
			return service.ref.getChannelNum() or None
		return None

	def getEventRect(self):
		return eRect(self.eventRect.left() + (self.instance and self.instance.position().x() or 0), self.eventRect.top(), self.eventRect.width(), self.eventRect.height())

	def getServiceRect(self):
		return eRect(self.serviceRect.left() + (self.instance and self.instance.position().x() or 0), self.serviceRect.top(), self.serviceRect.width(), self.serviceRect.height())

	def getTimeBase(self):
		return self.timeBase


class TimelineText(GUIComponent):
	def __init__(self, epgConfig, graphic):
		GUIComponent.__init__(self)
		self.epgConfig = epgConfig
		self.graphic = graphic
		self.l = eListboxPythonMultiContent()  # noqa: E741
		self.l.setSelectionClip(eRect(0, 0, 0, 0))
		self.itemHeight = 30
		self.timelineDate = None
		self.timelineTime = None
		self.foreColor = 0xffc000
		self.borderColor = 0x000000
		self.backColor = 0x000000
		self.borderWidth = 1
		self.timeBase = 0
		self.timeEpoch = 0
		self.timelineFontName = "Regular"
		self.timelineFontSize = 20
		self.datefmt = ""
		self.fullBorder = True

	GUI_WIDGET = eListbox

	def applySkin(self, desktop, screen):
		if self.skinAttributes is not None:
			attribs = []
			for (attrib, value) in self.skinAttributes:
				if attrib == "foregroundColor":
					self.foreColor = parseColor(value).argb()
				elif attrib == "borderColor":
					self.borderColor = parseColor(value).argb()
				elif attrib == "backgroundColor":
					self.backColor = parseColor(value).argb()
				elif attrib == "borderWidth":
					self.borderWidth = parseScale(value)
				elif attrib == "TimelineFont":
					font = parseFont(value, screen.scale)
					self.timelineFontName = font.family
					self.timelineFontSize = font.pointSize
				elif attrib == "itemHeight":
					self.itemHeight = parseScale(value)
				elif attrib == "fullBorder":
					self.fullBorder = value == "1"
				else:
					attribs.append((attrib, value))
			self.skinAttributes = attribs
		rc = GUIComponent.applySkin(self, desktop, screen)
		self.listHeight = self.instance.size().height()
		self.listWidth = self.instance.size().width()
		self.setFontsize()
		# print("[EpgListGrid1] itemHeight %s" % (self.itemHeight))
		self.l.setItemHeight(self.itemHeight)
		if self.graphic:
			self.timelineDate = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "epg/TimeLineDate.png"))
			self.timelineTime = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "epg/TimeLineTime.png"))
		return rc

	def setFontsize(self):
		fontConf = self.epgConfig.timelinefs.value
		if fontConf is not None:
			self.l.setFont(0, gFont(self.timelineFontName, self.timelineFontSize + fontConf))

	def postWidgetCreate(self, instance):
		instance.setContent(self.l)

	def setEntries(self, list, timelineNow, timeLines, force):
		eventRect = list.getEventRect()
		timeEpoch = list.getTimeEpoch()
		timeBase = list.getTimeBase()
		if eventRect is None or timeEpoch is None or timeBase is None:
			return

		eventLeft = eventRect.left()

		res = [None]

		# Note: eventRect and serviceRect are relative to the timeline text position
		# while the time lines are relative to the GraphEPG screen position!
		if self.timeBase != timeBase or self.timeEpoch != timeEpoch or force:
			serviceRect = list.getServiceRect()
			timeSteps = 60 if timeEpoch > 180 else 30
			numLines = timeEpoch // timeSteps
# Whereas we need the integer division to get numLines, we
# need real division to find out what the incremental space is
# between successive timelines
# NOTE: that Py3 can/will be different! ... kept float for compat with py2 and int
#
			fnum = timeEpoch / timeSteps
			incWidth = int(eventRect.width() / fnum)
			timeStepsCalc = timeSteps * SECS_IN_MIN

			nowTime = localtime(time())
			begTime = localtime(timeBase)
			serviceWidth = serviceRect.width()
			if nowTime.tm_year == begTime.tm_year and nowTime.tm_yday == begTime.tm_yday:
				datestr = _("Today")
			else:
				if serviceWidth > (self.timelineFontSize + self.epgConfig.timelinefs.value) * 8.1:
					dateFormat = config.usage.date.daylong.value
				elif serviceWidth > (self.timelineFontSize + self.epgConfig.timelinefs.value) * 5.8:
					dateFormat = config.usage.date.dayshort.value
				elif serviceWidth > (self.timelineFontSize + self.epgConfig.timelinefs.value) * 3.95:
					dateFormat = config.usage.date.daysmall.value
				else:
					dateFormat = "%a"
				datestr = strftime(dateFormat, begTime)

			foreColor = self.foreColor
			backColor = self.backColor
			bgpng = self.timelineDate
			if bgpng is not None and self.graphic:
				backColor = None
				# backColorSel = None
				res.append(MultiContentEntryPixmapAlphaBlend(
					pos=(0, 0),
					size=(serviceRect.width(), self.listHeight),
					png=bgpng,
					flags=BT_SCALE))
			else:
				if self.fullBorder:
					res.append(MultiContentEntryText(
						pos=(0, 0),
						size=(serviceRect.width(), self.listHeight),
						color=foreColor,
						backcolor=backColor,
						border_width=self.borderWidth, border_color=self.borderColor))

			res.append(MultiContentEntryText(
				pos=(5, 0),
				size=(serviceRect.width() - 15, self.listHeight),
				font=0, flags=int(config.epgselection.grid.timelinedate_alignment.value),
				text=_(datestr),
				color=foreColor,
				backcolor=backColor))

			if not self.fullBorder:
				res.append(MultiContentEntryText(
					pos=(serviceRect.width() - self.borderWidth * 2, 0),
					size=(self.borderWidth, self.listHeight + self.borderWidth * 2),
					text=" ",
					color=foreColor,
					backcolor=self.borderColor,
					border_width=self.borderWidth, border_color=self.borderColor))

			bgpng = self.timelineTime
			xpos = 0
			if bgpng is not None and self.graphic:
				backColor = None
				# backColorSel = None
				res.append(MultiContentEntryPixmapAlphaBlend(
					pos=(serviceRect.width(), 0),
					size=(eventRect.width(), self.listHeight),
					png=bgpng,
					flags=BT_SCALE))
			else:
				if self.fullBorder:
					res.append(MultiContentEntryText(
						pos=(serviceRect.width(), 0),
						size=(eventRect.width(), self.listHeight),
						color=foreColor,
						backcolor=backColor,
						border_width=self.borderWidth, border_color=self.borderColor))

			for x in range(0, numLines):
				ttime = localtime(timeBase + (x * timeStepsCalc))
				if config.usage.time.enabled.value:
					timetext = strftime(config.usage.time.short.value, ttime)
				else:
					if self.epgConfig.timeline24h.value:
						timetext = strftime("%H:%M", ttime)
					else:
						if int(strftime("%H", ttime)) > 12:
							timetext = strftime("%-I:%M", ttime) + _("pm")
						else:
							timetext = strftime("%-I:%M", ttime) + _("am")
				res.append(MultiContentEntryText(
					pos=(serviceRect.width() + xpos + 5, 0),
					size=(incWidth, self.listHeight),
					font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
					text=timetext,
					color=foreColor,
					backcolor=backColor))
				line = timeLines[x]
				oldPos = line.position
				line.setPosition(xpos + eventLeft, oldPos[1])
				line.visible = True
				xpos += incWidth
			for x in range(numLines, MAX_TIMELINES):
				timeLines[x].visible = False
			self.l.setList([res])
			self.timeBase = timeBase
			self.timeEpoch = timeEpoch

		now = time()
		if timeBase <= now < (timeBase + timeEpoch * SECS_IN_MIN):
			xpos = int((((now - timeBase) * eventRect.width()) // (timeEpoch * SECS_IN_MIN)) - (timelineNow.instance.size().width() // 2))
			oldPos = timelineNow.position
			newPos = (xpos + eventLeft, oldPos[1])
			if oldPos != newPos:
				timelineNow.setPosition(newPos[0], newPos[1])
			timelineNow.visible = True
		else:
			timelineNow.visible = False
