from time import localtime, time, strftime

from enigma import eListbox, eListboxPythonMultiContent, eServiceReference, loadPNG, gFont, eRect, eSize, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, RT_VALIGN_CENTER, RT_VALIGN_TOP, RT_WRAP, BT_SCALE, BT_KEEP_ASPECT_RATIO, BT_ALIGN_CENTER

from skin import parseColor, parseFont, parseScale
from Components.EpgListBase import EPGListBase
from Components.GUIComponent import GUIComponent
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmapAlphaBlend, MultiContentEntryPixmapAlphaTest
from Components.Renderer.Picon import getPiconName
from Components.config import config
from RecordTimer import RecordTimer
from Tools.Alternatives import CompareWithAlternatives
from Tools.Directories import resolveFilename, SCOPE_CURRENT_SKIN
from Tools.TextBoundary import getTextBoundarySize

MAX_TIMELINES = 6

# Various value are in minutes, while others are in seconds.
# Use this to remind us what is going on...
SECS_IN_MIN = 60


class EPGListGrid(EPGListBase):
	def __init__(self, session, isInfobar, selChangedCB=None):
		EPGListBase.__init__(self, session, selChangedCB)

		self.isInfobar = isInfobar
		self.epgConfig = config.epgselection.infobar if isInfobar else config.epgselection.grid
		self.timeFocus = time()  # Default to now.
		self.selectedEventIndex = None
		self.selectedService = None
		self.selectionRect = None
		self.eventRect = None
		self.serviceRect = None

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
		self.eventFontSize = self.serviceFontSize = 28 if self.isFullHd else 20

		self.serviceBorderWidth = 1
		self.serviceNamePadding = 3
		self.serviceNumberPadding = 9
		self.eventBorderWidth = 1
		self.eventNamePadding = 3
		self.serviceNumberWidth = 0

		self.l.setBuildFunc(self.buildEntry)
		self.loadConfig()

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

	def applySkin(self, desktop, screen):
		if self.skinAttributes is not None:
			attribs = []
			for (attrib, value) in self.skinAttributes:
				if attrib == ("ServiceFontInfobar" if self.isInfobar else "ServiceFontGraphical"):
					font = parseFont(value, ((1, 1), (1, 1)))
					self.serviceFontName = font.family
					self.serviceFontSize = font.pointSize
				elif attrib == ("EntryFontInfobar" if self.isInfobar else "EntryFontGraphical"):
					font = parseFont(value, ((1, 1), (1, 1)))
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

				elif attrib == "ServiceBorderColor":
					self.borderColorService = parseColor(value).argb()
				elif attrib == "ServiceBorderWidth":
					self.serviceBorderWidth = int(value)
				elif attrib == "ServiceNamePadding":
					self.serviceNamePadding = int(value)
				elif attrib == "ServiceNumberPadding":
					self.serviceNumberPadding = int(value)
				elif attrib == "EntryBorderColor":
					self.borderColor = parseColor(value).argb()
				elif attrib == "EventBorderWidth":
					self.eventBorderWidth = int(value)
				elif attrib == "EventNamePadding":
					self.eventNamePadding = int(value)

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
		return EPGListBase.applySkin(self, desktop, screen)

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
				tmpItemHeight = ((self.listHeight / numberOfRows) / 3)
			elif ((self.listHeight / numberOfRows) / 2) >= 27:
				tmpItemHeight = ((self.listHeight / numberOfRows) / 2)
			else:
				tmpItemHeight = 27
			if tmpItemHeight < self.itemHeight:
				self.itemHeight = tmpItemHeight
			else:
				if ((self.listHeight / numberOfRows) * 3) <= 45:
					self.itemHeight = ((self.listHeight / numberOfRows) * 3)
				elif ((self.listHeight / numberOfRows) * 2) <= 45:
					self.itemHeight = ((self.listHeight / numberOfRows) * 2)
				else:
					self.itemHeight = 45
			self.l.setItemHeight(self.itemHeight)
			self.instance.resize(eSize(self.listWidth, self.listHeight / self.itemHeight * self.itemHeight))
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

	def isSelectable(self, service, serviceName, events, picon, channel):
		return (events and len(events) and True) or False

	def postWidgetCreate(self, instance):
		if config.epgselection.overjump.value:
			self.l.setSelectableFunc(self.isSelectable)
		else:
			self.l.setSelectableFunc(None)
		instance.setWrapAround(True)
		instance.setContent(self.l)
		instance.selectionChanged.get().append(self.serviceChanged)
		self.l.setSelectionClip(eRect(0, 0, 0, 0), False)

	def preWidgetRemove(self, instance):
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
			piconWidth = self.epgConfig.piconwidth.value
			w += piconWidth
			if piconWidth > w - 2 * self.serviceBorderWidth:
				piconWidth = w - 2 * self.serviceBorderWidth
			piconHeight = height - 2 * self.serviceBorderWidth
			self.piconSize = eSize(piconWidth, piconHeight)
		self.serviceRect = eRect(0, 0, w, height)
		self.eventRect = eRect(w, 0, width - w, height)

	def calcEventPosAndWidthHelper(self, stime, duration, start, end, width):
		xpos = (stime - start) * width / (end - start)
		ewidth = (stime + duration - start) * width / (end - start)
		ewidth -= xpos
		if xpos < 0:
			ewidth += xpos
			xpos = 0
		if (xpos + ewidth) > width:
			ewidth = width - xpos
		return xpos, ewidth

	def buildEntry(self, service, serviceName, events, picon, channel):
		r1 = self.serviceRect
		r2 = self.eventRect
		left = r2.left()
		top = r2.top()
		width = r2.width()
		height = r2.height()
		selected = self.selectedService[0] == service
		res = [None]

		borderTopPix = None
		borderLeftPix = None
		borderBottomPix = None
		borderRightPix = None

		# Picon and Service name
		serviceForeColor = self.foreColorService
		serviceBackColor = self.backColorService
		bgpng = self.othServPix
		if CompareWithAlternatives(service, self.session.nav.getCurrentlyPlayingServiceOrGroup()):
			serviceForeColor = self.foreColorServiceNow
			serviceBackColor = self.backColorServiceNow
			bgpng = self.nowServPix

		if bgpng is not None and self.graphic:
			serviceBackColor = None
			res.append(MultiContentEntryPixmapAlphaBlend(
					pos=(r1.left() + self.serviceBorderWidth, r1.top() + self.serviceBorderWidth),
					size=(r1.width() - 2 * self.serviceBorderWidth, r1.height() - 2 * self.serviceBorderWidth),
					png=bgpng,
					flags=BT_SCALE))
		else:
			res.append(MultiContentEntryText(
					pos=(r1.left(), r1.top()),
					size=(r1.width(), r1.height()),
					font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
					text="",
					color=serviceForeColor, color_sel=serviceForeColor,
					backcolor=serviceBackColor, backcolor_sel=serviceBackColor,
					border_width=self.serviceBorderWidth, border_color=self.borderColorService))

		colX = r1.left() + self.serviceBorderWidth
		for titleItem in self.serviceTitleMode:
			if titleItem == "picon":
				if picon is None:
					# Go find picon and cache its location.
					picon = getPiconName(service)
					curIdx = self.l.getCurrentSelectionIndex()
					self.list[curIdx] = (service, serviceName, events, picon, channel)
				piconWidth = self.piconSize.width()
				piconHeight = self.piconSize.height()
				displayPicon = None
				if picon != "":
					displayPicon = loadPNG(picon)
				if displayPicon is not None:
					res.append(MultiContentEntryPixmapAlphaBlend(
						pos=(colX, r1.top() + self.serviceBorderWidth),
						size=(piconWidth, piconHeight),
						png=displayPicon,
						backcolor=None, backcolor_sel=None, flags=BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_ALIGN_CENTER))
				elif not self.showServiceName:
					# No picon so show servicename anyway in picon space.
					namefont = 1
					namefontflag = int(config.epgselection.grid.servicename_alignment.value)
					res.append(MultiContentEntryText(
						pos=(colX, r1.top() + self.serviceBorderWidth),
						size=(piconWidth, r1.height() - 2 * self.serviceBorderWidth),
						font=namefont, flags=namefontflag,
						text=serviceName,
						color=serviceForeColor, color_sel=serviceForeColor,
						backcolor=serviceBackColor, backcolor_sel=serviceBackColor))
				colX += piconWidth

			if titleItem == "servicenumber":
				if not isinstance(channel, int):
					channel = self.getChannelNumber(channel)
				namefont = 0
				namefontflag = int(config.epgselection.grid.servicenumber_alignment.value)
				font = gFont(self.serviceFontName, self.serviceFontSize + self.epgConfig.servfs.value)
				channelWidth = getTextBoundarySize(self.instance, font, self.instance.size(),
					"0000" if channel < 10000 else str(channel)).width()
				if channel:
					res.append(MultiContentEntryText(
						pos=(colX + self.serviceNumberPadding, r1.top() + self.serviceBorderWidth),
						size=(channelWidth, r1.height() - 2 * self.serviceBorderWidth),
						font=namefont, flags=namefontflag,
						text=str(channel),
						color=serviceForeColor, color_sel=serviceForeColor,
						backcolor=serviceBackColor, backcolor_sel=serviceBackColor))
				colX += channelWidth + 2 * self.serviceNumberPadding

			if titleItem == "servicename":
				namefont = 0
				namefontflag = int(config.epgselection.grid.servicename_alignment.value)
				namewidth = r1.width() - colX - 2 * self.serviceNamePadding - self.serviceBorderWidth
				res.append(MultiContentEntryText(
					pos=(colX + self.serviceNamePadding, r1.top() + self.serviceBorderWidth),
					size=(namewidth, r1.height() - 2 * self.serviceBorderWidth),
					font=namefont, flags=namefontflag,
					text=serviceName,
					color=serviceForeColor, color_sel=serviceForeColor,
					backcolor=serviceBackColor, backcolor_sel=serviceBackColor))
				colX += namewidth + 2 * self.serviceNamePadding

		if self.graphic:
			# Service Borders
			if self.borderTopPix is not None:
				res.append(MultiContentEntryPixmapAlphaTest(
						pos=(r1.left(), r1.top()),
						size=(r1.width(), self.serviceBorderWidth),
						png=self.borderTopPix,
						flags=BT_SCALE))
				res.append(MultiContentEntryPixmapAlphaTest(
						pos=(left, top),
						size=(width, self.eventBorderWidth),
						png=self.borderTopPix,
						flags=BT_SCALE))
			if self.borderBottomPix is not None:
				res.append(MultiContentEntryPixmapAlphaTest(
						pos=(r1.left(), r1.height()-self.serviceBorderWidth),
						size=(r1.width(), self.serviceBorderWidth),
						png=self.borderBottomPix,
						flags=BT_SCALE))
				res.append(MultiContentEntryPixmapAlphaTest(
						pos=(left, height-self.eventBorderWidth),
						size=(width, self.eventBorderWidth),
						png=self.borderBottomPix,
						flags=BT_SCALE))
			if self.borderLeftPix is not None:
				res.append(MultiContentEntryPixmapAlphaTest(
						pos=(r1.left(), r1.top()),
						size=(self.serviceBorderWidth, r1.height()),
						png=self.borderLeftPix,
						flags=BT_SCALE))
				res.append(MultiContentEntryPixmapAlphaTest(
						pos=(left, top),
						size=(self.eventBorderWidth, height),
						png=self.borderLeftPix,
						flags=BT_SCALE))
			if self.borderRightPix is not None:
				res.append(MultiContentEntryPixmapAlphaTest(
						pos=(r1.width()-self.serviceBorderWidth, r1.left()),
						size=(self.serviceBorderWidth, r1.height()),
						png=self.borderRightPix,
						flags=BT_SCALE))
				res.append(MultiContentEntryPixmapAlphaTest(
						pos=(left + width-self.eventBorderWidth, top),
						size=(self.eventBorderWidth, height),
						png=self.borderRightPix,
						flags=BT_SCALE))

			# Only draw the selected graphic if there are no events to fill
			# the prevents issues with lingering selection highlights.
			png = (selected and events is None and self.selEvPix) or self.othEvPix
			if png:
				res.append(MultiContentEntryPixmapAlphaTest(
					pos=(left + self.eventBorderWidth, top + self.eventBorderWidth),
					size=(width - 2 * self.eventBorderWidth, height - 2 * self.eventBorderWidth),
					png=png,
					flags=BT_SCALE))
		else:
			res.append(MultiContentEntryText(
				pos=(left, top), size=(width, height),
				font=1, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
				text="", color=None, color_sel=None,
				backcolor=self.backColor, backcolor_sel=self.backColorSelected,
				border_width=self.eventBorderWidth, border_color=self.borderColor))

		# Events for service
		if events:
			start = self.timeBase
			end = start + self.timeEpochSecs

			now = time()
			for ev in events:  # (eventId, eventTitle, beginTime, duration)
				stime = ev[2]
				duration = ev[3]

				xpos, ewidth = self.calcEventPosAndWidthHelper(stime, duration, start, end, width)
				serviceTimers = self.filteredTimerList.get(':'.join(service.split(':')[:11]))
				if serviceTimers is not None:
					timer, matchType = RecordTimer.isInTimerOnService(serviceTimers, stime, duration)
					timerIcon, autoTimerIcon = self.getPixmapsForTimer(timer, matchType, selected)
					if matchType not in (2,3):
						timer = None
				else:
					timer = matchType = timerIcon = None

				isNow = stime <= now < (stime + duration) and config.epgselection.grid.highlight_current_events.value
				# Only highlight timers that span an entire event
				if timer and matchType == 3:
					if timer.justplay == 0 and timer.always_zap == 0:
						foreColor = self.foreColorRecord
						backColor = self.backColorRecord
						foreColorSel = self.foreColorRecordSelected
						backColorSel = self.backColorRecordSelected
					else:
						foreColor = self.foreColorZap
						backColor = self.backColorZap
						foreColorSel = self.foreColorZapSelected
						backColorSel = self.backColorZapSelected
				elif isNow:
					foreColor = self.foreColorNow
					backColor = self.backColorNow
					foreColorSel = self.foreColorNowSelected
					backColorSel = self.backColorNowSelected
				else:
					foreColor = self.foreColor
					backColor = self.backColor
					foreColorSel = self.foreColorSelected
					backColorSel = self.backColorSelected

				if selected and self.selectionRect.left() == xpos + left:
					borderTopPix = self.borderSelectedTopPix
					borderLeftPix = self.borderSelectedLeftPix
					borderBottomPix = self.borderSelectedBottomPix
					borderRightPix = self.borderSelectedRightPix
					infoPix = self.selInfoPix
					bgpng = self.nowSelEvPix if isNow else self.selEvPix
				else:
					borderTopPix = self.borderTopPix
					borderLeftPix = self.borderLeftPix
					borderBottomPix = self.borderBottomPix
					borderRightPix = self.borderRightPix
					infoPix = self.infoPix
					bgpng = self.othEvPix
					if timer:
						bgpng = self.recEvPix if timer.justplay == 0 and timer.always_zap == 0 else self.zapEvPix
					elif isNow:
						bgpng = self.nowEvPix

				# Event box background.
				if bgpng is not None and self.graphic:
					backColor = None
					backColorSel = None
					res.append(MultiContentEntryPixmapAlphaTest(
						pos=(left + xpos + self.eventBorderWidth, top + self.eventBorderWidth),
						size=(ewidth - 2 * self.eventBorderWidth, height - 2 * self.eventBorderWidth),
						png=bgpng,
						flags=BT_SCALE))
				else:
					res.append(MultiContentEntryText(
						pos=(left + xpos, top), size=(ewidth, height),
						font=1, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
						text="", color=None, color_sel=None,
						backcolor=backColor, backcolor_sel=backColorSel,
						border_width=self.eventBorderWidth, border_color=self.borderColor))

				# Event text.
				evX = left + xpos + self.eventBorderWidth + self.eventNamePadding
				evY = top + self.eventBorderWidth
				evW = ewidth - 2 * (self.eventBorderWidth + self.eventNamePadding)
				evH = height - 2 * self.eventBorderWidth
				infowidth = self.epgConfig.infowidth.value
				if infowidth > 0 and evW < infowidth and infoPix is not None:
					res.append(MultiContentEntryPixmapAlphaBlend(
						pos=(left + xpos + self.eventBorderWidth, evY), size=(ewidth - 2 * self.eventBorderWidth, evH),
						png=infoPix, flags=BT_ALIGN_CENTER))
				else:
					res.append(MultiContentEntryText(
						pos=(evX, evY), size=(evW, evH),
						font=1, flags=int(config.epgselection.grid.event_alignment.value),
						text=ev[1],
						color=foreColor, color_sel=foreColorSel,
						backcolor=backColor, backcolor_sel=backColorSel))

				# Event box borders.
				if self.graphic:
					if borderTopPix is not None:
						res.append(MultiContentEntryPixmapAlphaTest(
								pos=(left + xpos, top),
								size=(ewidth, self.eventBorderWidth),
								png=borderTopPix,
								flags=BT_SCALE))
					if borderBottomPix is not None:
						res.append(MultiContentEntryPixmapAlphaTest(
								pos=(left + xpos, height-self.eventBorderWidth),
								size=(ewidth, self.eventBorderWidth),
								png=borderBottomPix,
								flags=BT_SCALE))
					if borderLeftPix is not None:
						res.append(MultiContentEntryPixmapAlphaTest(
								pos=(left + xpos, top),
								size=(self.eventBorderWidth, height),
								png=borderLeftPix,
								flags=BT_SCALE))
					if borderRightPix is not None:
						res.append(MultiContentEntryPixmapAlphaTest(
								pos=(left + xpos + ewidth-self.eventBorderWidth, top),
								size=(self.eventBorderWidth, height),
								png=borderRightPix,
								flags=BT_SCALE))

				# Recording icons.
				if timerIcon is not None and ewidth > 23:
					if config.epgselection.grid.rec_icon_height.value != "hide":
						clockSize = 26 if self.isFullHd else 21
						if config.epgselection.grid.rec_icon_height.value == "middle":
							recIconHeight = top + (height - clockSize) / 2
						elif config.epgselection.grid.rec_icon_height.value == "top":
							recIconHeight = top + 3
						else:
							recIconHeight = top + height - clockSize
						if matchType == 0:
							pos = (left + xpos + ewidth - (15 if self.isFullHd else 13), recIconHeight)
						else:
							pos = (left + xpos + ewidth - clockSize, recIconHeight)
						res.append(MultiContentEntryPixmapAlphaBlend(
							pos=pos, size=(clockSize, clockSize),
							png=timerIcon))
						if autoTimerIcon:
							res.append(MultiContentEntryPixmapAlphaBlend(
								pos=(pos[0]-clockSize,pos[1]), size=(clockSize, clockSize),
								png=autoTimerIcon))
		return res

	def getSelectionPosition(self):
		_, sely = EPGListBase.getSelectionPosition(self)
		return self.selectionRect.left() + self.selectionRect.width(), sely

	def refreshSelection(self):
		events = self.selectedService and self.selectedService[2]  # (service, serviceName, events, picon)
		if events and self.selectedEventIndex is not None and self.selectedEventIndex < len(events):
			event = events[self.selectedEventIndex]  # (eventId, eventTitle, beginTime, duration)
			xpos, width = self.calcEventPosAndWidthHelper(event[2], event[3], 
				self.timeBase, self.timeBase + self.timeEpochSecs, self.eventRect.width())
			self.selectionRect = eRect(xpos + self.eventRect.left(), 0, width, self.eventRect.height())
		else:
			self.selectionRect = eRect(self.eventRect.left(), self.eventRect.top(), self.eventRect.width(), self.eventRect.height())
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

	def fillEPGNoRefresh(self, services=None):
		if not self.graphicsloaded:
			if self.graphic:
				self.nowEvPix = loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "epg/CurrentEvent.png"))
				self.nowSelEvPix = loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "epg/SelectedCurrentEvent.png"))
				self.othEvPix = loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "epg/OtherEvent.png"))
				self.selEvPix = loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "epg/SelectedEvent.png"))
				self.othServPix = loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "epg/OtherService.png"))
				self.nowServPix = loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "epg/CurrentService.png"))
				self.recEvPix = loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "epg/RecordEvent.png"))
				self.recSelEvPix = loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "epg/SelectedRecordEvent.png"))
				self.zapEvPix = loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "epg/ZapEvent.png"))
				self.zapSelEvPix = loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "epg/SelectedZapEvent.png"))
				self.borderTopPix = loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "epg/BorderTop.png"))
				self.borderBottomPix = loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "epg/BorderBottom.png"))
				self.borderLeftPix = loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "epg/BorderLeft.png"))
				self.borderRightPix = loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "epg/BorderRight.png"))
				self.borderSelectedTopPix = loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "epg/SelectedBorderTop.png"))
				self.borderSelectedBottomPix = loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "epg/SelectedBorderBottom.png"))
				self.borderSelectedLeftPix = loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "epg/SelectedBorderLeft.png"))
				self.borderSelectedRightPix = loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "epg/SelectedBorderRight.png"))
			self.infoPix = loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "epg/information.png"))
			self.selInfoPix = loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "epg/SelectedInformation.png"))

			self.graphicsloaded = True

		if services is None:
			test = [(service[0], 0, self.timeBase, self.timeEpoch) for service in self.list]
			serviceList = self.list
			piconIdx = 3
			channelIdx = 4
		else:
			self.selectedEventIndex = None
			self.selectedService = None
			test = [(service.ref.toString(), 0, self.timeBase, self.timeEpoch) for service in services]
			serviceList = services
			piconIdx = 0
			channelIdx = 0

		test.insert(0, "XRnITBD")  # return record, service ref, service name, event id, event title, begin time, duration
		epgData = self.queryEPG(test)
		self.list = []
		eventList = None
		serviceRef = ""
		serviceName = ""
		self.snapshotTimers(self.timeBase, self.timeBase + self.timeEpochSecs)

		def appendService():
			picon = None if piconIdx == 0 else serviceList[serviceIdx][piconIdx]
			# We pass the serviceref if we don't have the channel number yet, so it can be grabbed.
			channel = serviceList[serviceIdx] if channelIdx == 0 else serviceList[serviceIdx][channelIdx]
			self.list.append((serviceRef, serviceName, eventList[0][0] is not None and eventList or None, picon, channel))

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
				l = self.filteredTimerList.get(serviceref)
				if l is None:
					self.filteredTimerList[serviceref] = l = [timer]
				else:
					l.append(timer)

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
		self.l = eListboxPythonMultiContent()
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
					self.borderWidth = int(value)
				elif attrib == "TimelineFont":
					font = parseFont(value, ((1, 1), (1, 1)))
					self.timelineFontName = font.family
					self.timelineFontSize = font.pointSize
				elif attrib == "itemHeight":
					self.itemHeight = parseScale(value)
				else:
					attribs.append((attrib, value))
			self.skinAttributes = attribs
		rc = GUIComponent.applySkin(self, desktop, screen)
		self.listHeight = self.instance.size().height()
		self.listWidth = self.instance.size().width()
		self.setFontsize()
		self.l.setItemHeight(self.itemHeight)
		if self.graphic:
			self.timelineDate = loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "epg/TimeLineDate.png"))
			self.timelineTime = loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "epg/TimeLineTime.png"))
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
			numLines = timeEpoch / timeSteps
# Whereas we need the integer division to get numLines, we
# need real division to find out what the incremental space is
# between successive timelines
# NOTE: that Py3 can/will be different!
#
			fnum = float(timeEpoch)/float(timeSteps)
			incWidth = int(eventRect.width() / fnum)
			timeStepsCalc = timeSteps * SECS_IN_MIN

			nowTime = localtime(time())
			begTime = localtime(timeBase)
			serviceWidth = serviceRect.width()
			if nowTime.tm_year == begTime.tm_year and nowTime.tm_yday == begTime.tm_yday:
				datestr = _("Today")
			else:
				if serviceWidth > (self.timelineFontSize + self.epgConfig.timelinefs.value) * 7.6:
					dateFormat = config.usage.date.daylong.value
				elif serviceWidth > (self.timelineFontSize + self.epgConfig.timelinefs.value) * 4.5:
					dateFormat = config.usage.date.dayshort.value
				elif serviceWidth > (self.timelineFontSize + self.epgConfig.timelinefs.value) * 2.85:
					dateFormat = config.usage.date.daysmall.value
				else:
					dateFormat = "%a"
				datestr = strftime(dateFormat, begTime)

			foreColor = self.foreColor
			backColor = self.backColor
			bgpng = self.timelineDate
			if bgpng is not None and self.graphic:
				backColor = None
				backColorSel = None
				res.append(MultiContentEntryPixmapAlphaTest(
					pos=(0, 0),
					size=(serviceRect.width(), self.listHeight),
					png=bgpng,
					flags=BT_SCALE))
			else:
				res.append(MultiContentEntryText(
					pos=(0, 0),
					size=(serviceRect.width(), self.listHeight),
					color=foreColor,
					backcolor=backColor,
					border_width=self.borderWidth, border_color=self.borderColor))

			res.append(MultiContentEntryText(
				pos=(5, 0),
				size=(serviceRect.width()-15, self.listHeight),
				font=0, flags=int(config.epgselection.grid.timelinedate_alignment.value),
				text=_(datestr),
				color=foreColor,
				backcolor=backColor))

			bgpng = self.timelineTime
			xpos = 0
			if bgpng is not None and self.graphic:
				backColor = None
				backColorSel = None
				res.append(MultiContentEntryPixmapAlphaTest(
					pos=(serviceRect.width(), 0),
					size=(eventRect.width(), self.listHeight),
					png=bgpng,
					flags=BT_SCALE))
			else:
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
					pos=(serviceRect.width() + xpos, 0),
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
			xpos = int((((now - timeBase) * eventRect.width()) / (timeEpoch * SECS_IN_MIN)) - (timelineNow.instance.size().width() / 2))
			oldPos = timelineNow.position
			newPos = (xpos + eventLeft, oldPos[1])
			if oldPos != newPos:
				timelineNow.setPosition(newPos[0], newPos[1])
			timelineNow.visible = True
		else:
			timelineNow.visible = False
