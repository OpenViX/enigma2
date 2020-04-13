import skin
from time import localtime, time, strftime

from enigma import eEPGCache, eListbox, eListboxPythonMultiContent, loadPNG, gFont, getDesktop, eRect, eSize, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, RT_VALIGN_CENTER, RT_VALIGN_TOP, RT_WRAP, BT_SCALE, BT_KEEP_ASPECT_RATIO, BT_ALIGN_CENTER
from skin import parseColor, parseFont

from Components.GUIComponent import GUIComponent
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmapAlphaBlend, MultiContentEntryPixmapAlphaTest
from Components.Renderer.Picon import getPiconName
from Tools.Alternatives import CompareWithAlternatives
from Components.config import config
from ServiceReference import ServiceReference
from Tools.Directories import resolveFilename, SCOPE_ACTIVE_SKIN
from Tools.TextBoundary import getTextBoundarySize
from EpgListBase import EPGListBase

MAX_TIMELINES = 6

# Various value are in minutes, while others are in seconds.
# Use this to remind us what is going on...
SECS_IN_MIN = 60

class EPGListGrid(EPGListBase):
	def __init__(self, isInfobar, session, selChangedCB = None, timer = None, graphic=True):
		EPGListBase.__init__(self, selChangedCB, timer)

		self.isInfobar = isInfobar
		self.epgConfig = config.epgselection.infobar if isInfobar else config.epgselection.grid
		self.session = session
		self.time_focus = time() # default to now
		self.selectedEventIndex = None
		self.selectedService = None
		self.selection_rect = None
		self.event_rect = None
		self.service_rect = None
		self.showPicon = False
		self.showServiceName = True
		self.showServiceNumber = False
		self.graphic = graphic

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
		self.InfoPix = None
		self.selInfoPix = None
		self.graphicsloaded = False

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

		self.serviceBorderWidth = 1
		self.serviceNamePadding = 3
		self.serviceNumberPadding = 9
		self.eventBorderWidth = 1
		self.eventNamePadding = 3
		self.serviceNumberWidth = 0

		if self.screenwidth == 1920:
			self.serviceFontSize = 28
			self.eventFontSize = 28
		else:
			self.serviceFontSize = 20
			self.eventFontSize = 20

		self.l.setBuildFunc(self.buildEntry)
		self.round_by_secs = int(self.epgConfig.roundto.value) * SECS_IN_MIN
		self.time_epoch = int(self.epgConfig.prevtimeperiod.value)
		self.time_epoch_secs = self.time_epoch * SECS_IN_MIN
		self.serviceTitleMode = self.epgConfig.servicetitle_mode.value.split("+")
		self.showServiceNumber = "servicenumber" in self.serviceTitleMode
		self.showServiceName = "servicename" in self.serviceTitleMode
		self.showPicon = "picon" in self.serviceTitleMode

	def applySkin(self, desktop, screen):
		if self.skinAttributes is not None:
			attribs = [ ]
			for (attrib, value) in self.skinAttributes:
				if attrib == ("ServiceFontInfobar" if self.isInfobar else "ServiceFontGraphical"):
					font = parseFont(value, ((1,1),(1,1)))
					self.serviceFontName = font.family
					self.serviceFontSize = font.pointSize
				elif attrib == ("EntryFontInfobar" if self.isInfobar else "EntryFontGraphical"):
					font = parseFont(value, ((1,1),(1,1)))
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
					attribs.append((attrib,value))
			self.skinAttributes = attribs
		rc = EPGListBase.applySkin(self, desktop, screen)
		self.setItemsPerPage()

		# cache service number width
		if self.showServiceNumber:
			font_conf = self.epgConfig.servfs.value
			if font_conf != None:
				font = gFont(self.serviceFontName, self.serviceFontSize + font_conf)
				self.serviceNumberWidth = getTextBoundarySize(self.instance, font, self.instance.size(), "0000").width()
		return rc

	def __setTimeBase(self, time_center):
		# prefer time being aligned in the middle of the EPG, but clip to the maximum EPG data history
		self.time_base = int(max(time_center - self.time_epoch_secs // 2, 
			time() - (int(config.epg.histminutes.value) + self.time_epoch_secs // 4) * SECS_IN_MIN))
		# round up so that we favour a bit more info to the right of the timeline
		self.time_base += -self.time_base % self.round_by_secs

	def setTimeFocus(self, time_focus):
		self.__setTimeBase(time_focus)
		self.time_focus = time_focus

	def setTimeEpoch(self, epoch):
		center = epoch * SECS_IN_MIN * (self.time_focus - self.time_base) // self.time_epoch_secs
		self.time_epoch = epoch
		self.time_epoch_secs = epoch * SECS_IN_MIN
		self.__setTimeBase(center)
		self.fillEPG()

	def getTimeEpoch(self):
		return self.time_epoch

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
		if self.selectedEventIndex is None or not events or (self.selectedEventIndex and events and self.selectedEventIndex > len(events)-1):
			return None, ServiceReference(refstr)
		event = events[self.selectedEventIndex] #(event_id, event_title, begin_time, duration)
		eventid = event[0]
		service = ServiceReference(refstr)
		event = self.getEventFromId(service, eventid) # get full event info
		return event, service

	def setTimeFocusFromEvent(self, selectedEventIndex):
		if self.selectedService:
			events = self.selectedService[2]
			if events and len(events):
				self.selectedEventIndex = max(min(len(events) - 1, selectedEventIndex), 0)
				event = events[self.selectedEventIndex]

				# clip the selected event times to the current screen
				ev_time = max(self.time_base, event[2])
				ev_end_time = min(event[2] + event[3], self.time_base + self.time_epoch_secs)
				if ev_time <= time() < ev_end_time:
					# selected event contains the current time, user is interested in current things
					self.time_focus = time()
				else:
					# user is looking at things roughly around the middle of the selected event
					self.time_focus = ev_time + (ev_end_time - ev_time) // 2
		else:
			self.selectedEventIndex = None

	GUI_WIDGET = eListbox

	def setItemsPerPage(self):
		if self.numberOfRows:
			self.epgConfig.itemsperpage.default = self.numberOfRows
		if self.listHeight > 0:
			itemHeight = self.listHeight / self.epgConfig.itemsperpage.value
		else:
			itemHeight = 54 # some default (270/5)

		if not self.isInfobar and config.epgselection.grid.heightswitch.value:
			if ((self.listHeight / config.epgselection.grid.itemsperpage.value) / 3) >= 27:
				tmp_itemHeight = ((self.listHeight / config.epgselection.grid.itemsperpage.value) / 3)
			elif ((self.listHeight / config.epgselection.grid.itemsperpage.value) / 2) >= 27:
				tmp_itemHeight = ((self.listHeight / config.epgselection.grid.itemsperpage.value) / 2)
			else:
				tmp_itemHeight = 27
			if tmp_itemHeight < itemHeight:
				itemHeight = tmp_itemHeight
			else:
				if ((self.listHeight / config.epgselection.grid.itemsperpage.value) * 3) <= 45:
					itemHeight = ((self.listHeight / config.epgselection.grid.itemsperpage.value) * 3)
				elif ((self.listHeight / config.epgselection.grid.itemsperpage.value) * 2) <= 45:
					itemHeight = ((self.listHeight / config.epgselection.grid.itemsperpage.value) * 2)
				else:
					itemHeight = 45

		self.l.setItemHeight(itemHeight)
		self.instance.resize(eSize(self.listWidth, self.listHeight / itemHeight * itemHeight))
		self.listHeight = self.instance.size().height()
		self.listWidth = self.instance.size().width()
		self.itemHeight = itemHeight

	def setFontsize(self):
		self.l.setFont(0, gFont(self.serviceFontName, self.serviceFontSize + self.epgConfig.servfs.value))
		self.l.setFont(1, gFont(self.eventFontName, self.eventFontSize + self.epgConfig.eventfs.value))

	def isSelectable(self, service, service_name, events, picon, channel):
		return (events and len(events) and True) or False

	def postWidgetCreate(self, instance):
		if config.epgselection.overjump.value:
			self.l.setSelectableFunc(self.isSelectable)
		else:
			self.l.setSelectableFunc(None)
		instance.setWrapAround(True)
		instance.setContent(self.l)
		instance.selectionChanged.get().append(self.serviceChanged)
		self.l.setSelectionClip(eRect(0,0,0,0), False)

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
				if self.time_focus >= events[0][2]:
					for event in events: #iterate all events
						ev_time = event[2]
						ev_end_time = ev_time + event[3]
						self.selectedEventIndex += 1
						if ev_time <= self.time_focus < ev_end_time:
							break
					self.selectedEventIndex -= 1

	def recalcEventSize(self):
		esize = self.l.getItemSize()
		width = esize.width()
		height = esize.height()

		w = 0
		if self.showServiceName:
			w += self.epgConfig.servicewidth.value + 2*self.serviceNamePadding
		if self.showServiceNumber:
			w += self.serviceNumberWidth + 2*self.serviceNumberPadding 
		if self.showPicon:
			piconWidth = self.epgConfig.piconwidth.value
			w += piconWidth
			if piconWidth > w - 2 * self.serviceBorderWidth:
				piconWidth = w - 2 * self.serviceBorderWidth
			piconHeight = height - 2 * self.serviceBorderWidth
			self.picon_size = eSize(piconWidth, piconHeight)
		self.service_rect = eRect(0, 0, w, height)
		self.event_rect = eRect(w, 0, width - w, height)

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

	def buildEntry(self, service, service_name, events, picon, channel):
		r1 = self.service_rect
		r2 = self.event_rect
		left = r2.left()
		top = r2.top()
		width = r2.width()
		height = r2.height()
		selected = self.selectedService[0] == service
		res = [ None ]

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
					pos = (r1.left() + self.serviceBorderWidth, r1.top() + self.serviceBorderWidth),
					size = (r1.width() - 2 * self.serviceBorderWidth, r1.height() - 2 * self.serviceBorderWidth),
					png = bgpng,
					flags = BT_SCALE))
		else:
			res.append(MultiContentEntryText(
					pos  = (r1.left(), r1.top()),
					size = (r1.width(), r1.height()),
					font = 0, flags = RT_HALIGN_LEFT | RT_VALIGN_CENTER,
					text = "",
					color = serviceForeColor, color_sel = serviceForeColor,
					backcolor = serviceBackColor, backcolor_sel = serviceBackColor,
					border_width = self.serviceBorderWidth, border_color = self.borderColorService))

		colX = r1.left() + self.serviceBorderWidth
		for titleItem in self.serviceTitleMode:
			if titleItem == 'picon':
				if picon is None: # go find picon and cache its location
					picon = getPiconName(service)
					curIdx = self.l.getCurrentSelectionIndex()
					self.list[curIdx] = (service, service_name, events, picon, channel)
				piconWidth = self.picon_size.width()
				piconHeight = self.picon_size.height()
				displayPicon = None
				if picon != "":
					displayPicon = loadPNG(picon)
				if displayPicon is not None:
					res.append(MultiContentEntryPixmapAlphaBlend(
						pos = (colX, r1.top() + self.serviceBorderWidth),
						size = (piconWidth, piconHeight),
						png = displayPicon,
						backcolor = None, backcolor_sel = None, flags = BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_ALIGN_CENTER))
				elif not self.showServiceName:
					# no picon so show servicename anyway in picon space
					namefont = 1
					namefontflag = int(config.epgselection.grid.servicename_alignment.value)
					res.append(MultiContentEntryText(
						pos = (colX, r1.top() + self.serviceBorderWidth),
						size = (piconWidth, r1.height() - 2 * self.serviceBorderWidth),
						font = namefont, flags = namefontflag,
						text = service_name,
						color = serviceForeColor, color_sel = serviceForeColor,
						backcolor = serviceBackColor, backcolor_sel = serviceBackColor))
				colX += piconWidth

			if titleItem == 'servicenumber':
				if not isinstance(channel, int):
					channel = self.getChannelNumber(channel)
				namefont = 0
				namefontflag = int(config.epgselection.grid.servicenumber_alignment.value)
				font = gFont(self.serviceFontName, self.serviceFontSize + self.epgConfig.servfs.value)
				channelWidth = getTextBoundarySize(self.instance, font, self.instance.size(), 
					"0000" if channel < 10000 else str(channel)).width()
				if channel:
					res.append(MultiContentEntryText(
						pos = (colX + self.serviceNumberPadding, r1.top() + self.serviceBorderWidth),
						size = (channelWidth, r1.height() - 2 * self.serviceBorderWidth),
						font = namefont, flags = namefontflag,
						text = str(channel),
						color = serviceForeColor, color_sel = serviceForeColor,
						backcolor = serviceBackColor, backcolor_sel = serviceBackColor))
				colX += channelWidth + 2 * self.serviceNumberPadding

			if titleItem == 'servicename':
				namefont = 0
				namefontflag = int(config.epgselection.grid.servicename_alignment.value)
				namewidth = r1.width() - colX - 2 * self.serviceNamePadding - self.serviceBorderWidth
				res.append(MultiContentEntryText(
					pos = (colX + self.serviceNamePadding, r1.top() + self.serviceBorderWidth),
					size = (namewidth, r1.height() - 2 * self.serviceBorderWidth),
					font = namefont, flags = namefontflag,
					text = service_name,
					color = serviceForeColor, color_sel = serviceForeColor,
					backcolor = serviceBackColor, backcolor_sel = serviceBackColor))
				colX += namewidth + 2 * self.serviceNamePadding

		if self.graphic:
			# Service Borders
			if self.borderTopPix is not None:
				res.append(MultiContentEntryPixmapAlphaTest(
						pos = (r1.left(), r1.top()),
						size = (r1.width(), self.serviceBorderWidth),
						png = self.borderTopPix,
						flags = BT_SCALE))
				res.append(MultiContentEntryPixmapAlphaTest(
						pos = (left, top),
						size = (width, self.eventBorderWidth),
						png = self.borderTopPix,
						flags = BT_SCALE))
			if self.borderBottomPix is not None:
				res.append(MultiContentEntryPixmapAlphaTest(
						pos = (r1.left(), r1.height()-self.serviceBorderWidth),
						size = (r1.width(), self.serviceBorderWidth),
						png = self.borderBottomPix,
						flags = BT_SCALE))
				res.append(MultiContentEntryPixmapAlphaTest(
						pos = (left, height-self.eventBorderWidth),
						size = (width, self.eventBorderWidth),
						png = self.borderBottomPix,
						flags = BT_SCALE))
			if self.borderLeftPix is not None:
				res.append(MultiContentEntryPixmapAlphaTest(
						pos = (r1.left(), r1.top()),
						size = (self.serviceBorderWidth, r1.height()),
						png = self.borderLeftPix,
						flags = BT_SCALE))
				res.append(MultiContentEntryPixmapAlphaTest(
						pos = (left, top),
						size = (self.eventBorderWidth, height),
						png = self.borderLeftPix,
						flags = BT_SCALE))
			if self.borderRightPix is not None:
				res.append(MultiContentEntryPixmapAlphaTest(
						pos = (r1.width()-self.serviceBorderWidth, r1.left()),
						size = (self.serviceBorderWidth, r1.height()),
						png = self.borderRightPix,
						flags = BT_SCALE))
				res.append(MultiContentEntryPixmapAlphaTest(
						pos = (left + width-self.eventBorderWidth, top),
						size = (self.eventBorderWidth, height),
						png = self.borderRightPix,
						flags = BT_SCALE))

			# only draw the selected graphic if there are no events to fill
			# the prevents issues with lingering selection highlights
			png = (selected and events is None and self.selEvPix) or self.othEvPix
			if png:
				res.append(MultiContentEntryPixmapAlphaTest(
					pos = (left + self.eventBorderWidth, top + self.eventBorderWidth),
					size = (width - 2 * self.eventBorderWidth, height - 2 * self.eventBorderWidth),
					png = png,
					flags = BT_SCALE))
		else:
			res.append(MultiContentEntryText(
				pos = (left, top), size = (width, height),
				font = 1, flags = RT_HALIGN_LEFT | RT_VALIGN_CENTER,
				text = "", color = None, color_sel = None,
				backcolor = self.backColor, backcolor_sel = self.backColorSelected,
				border_width = self.eventBorderWidth, border_color = self.borderColor))

		# Events for service
		if events:
			start = self.time_base
			end = start + self.time_epoch_secs

			now = time()
			for ev in events:  #(event_id, event_title, begin_time, duration)
				stime = ev[2]
				duration = ev[3]

				xpos, ewidth = self.calcEventPosAndWidthHelper(stime, duration, start, end, width)
				clock_types = self.getPixmapForEntry(service, ev[0], stime, duration)

				foreColor = self.foreColor
				backColor = self.backColor
				foreColorSel = self.foreColorSelected
				backColorSel = self.backColorSelected
				if clock_types is not None and clock_types == 2:
					foreColor = self.foreColorRecord
					backColor = self.backColorRecord
					foreColorSel = self.foreColorRecordSelected
					backColorSel = self.backColorRecordSelected
				elif clock_types is not None and clock_types == 7:
					foreColor = self.foreColorZap
					backColor = self.backColorZap
					foreColorSel = self.foreColorZapSelected
					backColorSel = self.backColorZapSelected
				elif stime <= now < (stime + duration) and config.epgselection.grid.highlight_current_events.value:
					foreColor = self.foreColorNow
					backColor = self.backColorNow
					foreColorSel = self.foreColorNowSelected
					backColorSel = self.backColorNowSelected

				if selected and self.selection_rect.left() == xpos + left:
					if clock_types is not None:
						clocks = self.selclocks[clock_types]
					borderTopPix = self.borderSelectedTopPix
					borderLeftPix = self.borderSelectedLeftPix
					borderBottomPix = self.borderSelectedBottomPix
					borderRightPix = self.borderSelectedRightPix
					infoPix = self.selInfoPix
					if stime <= now < (stime + duration) and config.epgselection.grid.highlight_current_events.value:
						bgpng = self.nowSelEvPix
					else:
						bgpng = self.selEvPix
				else:
					if clock_types is not None:
						clocks = self.clocks[clock_types]
					borderTopPix = self.borderTopPix
					borderLeftPix = self.borderLeftPix
					borderBottomPix = self.borderBottomPix
					borderRightPix = self.borderRightPix
					infoPix = self.InfoPix
					bgpng = self.othEvPix
					if clock_types is not None and clock_types == 2:
						bgpng = self.recEvPix
					elif clock_types is not None and clock_types == 7:
						bgpng = self.zapEvPix
					elif stime <= now < (stime + duration) and config.epgselection.grid.highlight_current_events.value:
						bgpng = self.nowEvPix

				# event box background
				if bgpng is not None and self.graphic:
					backColor = None
					backColorSel = None
					res.append(MultiContentEntryPixmapAlphaTest(
						pos = (left + xpos + self.eventBorderWidth, top + self.eventBorderWidth),
						size = (ewidth - 2 * self.eventBorderWidth, height - 2 * self.eventBorderWidth),
						png = bgpng,
						flags = BT_SCALE))
				else:
					res.append(MultiContentEntryText(
						pos = (left + xpos, top), size = (ewidth, height),
						font = 1, flags = RT_HALIGN_LEFT | RT_VALIGN_CENTER,
						text = "", color = None, color_sel = None,
						backcolor = backColor, backcolor_sel = backColorSel,
						border_width = self.eventBorderWidth, border_color = self.borderColor))

				# event text
				evX = left + xpos + self.eventBorderWidth + self.eventNamePadding
				evY = top + self.eventBorderWidth
				evW = ewidth - 2 * (self.eventBorderWidth + self.eventNamePadding)
				evH = height - 2 * self.eventBorderWidth
				infowidth = self.epgConfig.infowidth.value
				if evW < infowidth and infoPix is not None:
					res.append(MultiContentEntryPixmapAlphaBlend(
						pos = (left + xpos + self.eventBorderWidth, evY), size = (ewidth - 2 * self.eventBorderWidth, evH),
						png = infoPix, flags = BT_ALIGN_CENTER))
				else:
					res.append(MultiContentEntryText(
						pos = (evX, evY), size = (evW, evH),
						font = 1, flags = int(config.epgselection.grid.event_alignment.value),
						text = ev[1],
						color = foreColor, color_sel = foreColorSel,
						backcolor = backColor, backcolor_sel = backColorSel))

				# event box borders
				if self.graphic:
					if borderTopPix is not None:
						res.append(MultiContentEntryPixmapAlphaTest(
								pos = (left + xpos, top),
								size = (ewidth, self.eventBorderWidth),
								png = borderTopPix,
								flags = BT_SCALE))
					if borderBottomPix is not None:
						res.append(MultiContentEntryPixmapAlphaTest(
								pos = (left + xpos, height-self.eventBorderWidth),
								size = (ewidth, self.eventBorderWidth),
								png = borderBottomPix,
								flags = BT_SCALE))
					if borderLeftPix is not None:
						res.append(MultiContentEntryPixmapAlphaTest(
								pos = (left + xpos, top),
								size = (self.eventBorderWidth, height),
								png = borderLeftPix,
								flags = BT_SCALE))
					if borderRightPix is not None:
						res.append(MultiContentEntryPixmapAlphaTest(
								pos = (left + xpos + ewidth-self.eventBorderWidth, top),
								size = (self.eventBorderWidth, height),
								png = borderRightPix,
								flags = BT_SCALE))

				# recording icons
				if clock_types is not None and ewidth > 23:
					if config.epgselection.grid.rec_icon_height.value != "hide":
						if config.epgselection.grid.rec_icon_height.value == "middle":
							RecIconHDheight = top+(height/2)-11
							RecIconFHDheight = top+(height/2)-13
						elif config.epgselection.grid.rec_icon_height.value == "top":
							RecIconHDheight = top+3
							RecIconFHDheight = top+3
						else:
							RecIconHDheight = top+height-22
							RecIconFHDheight = top+height-26
						if clock_types in (1,6,11):
							if self.screenwidth == 1920:
								pos = (left+xpos+ewidth-15, RecIconFHDheight)
							else:
								pos = (left+xpos+ewidth-13, RecIconHDheight)
						elif clock_types in (5,10,15):
							if self.screenwidth == 1920:
								pos = (left+xpos-26, RecIconFHDheight)
							else:
								pos = (left+xpos-22, RecIconHDheight)
						else:
							if self.screenwidth == 1920:
								pos = (left+xpos+ewidth-26, RecIconFHDheight)
							else:
								pos = (left+xpos+ewidth-22, RecIconHDheight)
						if self.screenwidth == 1920:
							res.append(MultiContentEntryPixmapAlphaBlend(
								pos = pos, size = (25, 25),
								png = clocks))
						else:
							res.append(MultiContentEntryPixmapAlphaBlend(
								pos = pos, size = (21, 21),
								png = clocks))
						if self.wasEntryAutoTimer and clock_types in (2,7,12):
							if self.screenwidth == 1920:
								res.append(MultiContentEntryPixmapAlphaBlend(
									pos = (pos[0]-25,pos[1]), size = (25, 25),
									png = self.autotimericon))
							else:
								res.append(MultiContentEntryPixmapAlphaBlend(
									pos = (pos[0]-21,pos[1]), size = (21, 21),
									png = self.autotimericon))
		return res

	def getSelectionPosition(self):
		# Adjust absolute indx to indx in displayed view
		indx = self.l.getCurrentSelectionIndex() % self.epgConfig.itemsperpage.value
		sely = self.instance.position().y() + self.itemHeight * indx
		if sely >= self.instance.position().y() + self.listHeight:
			sely -= self.listHeight
		return self.listWidth, sely

	def refreshSelection(self):
		events = self.selectedService and self.selectedService[2] #(service, service_name, events, picon)
		if events and self.selectedEventIndex is not None and self.selectedEventIndex < len(events):
			event = events[self.selectedEventIndex] #(event_id, event_title, begin_time, duration)
			xpos, width = self.calcEventPosAndWidthHelper(event[2], event[3], 
				self.time_base, self.time_base + self.time_epoch_secs, self.event_rect.width())
			self.selection_rect = eRect(xpos + self.event_rect.left(), 0, width, self.event_rect.height())
		else:
			self.selection_rect = eRect(self.event_rect.left(), self.event_rect.top(), self.event_rect.width(), self.event_rect.height())
		# have to copy construct the parameter for this native function or odd selection behaviour results
		self.l.setSelectionClip(eRect(self.selection_rect.left(), self.selection_rect.top(), self.selection_rect.width(), self.selection_rect.height()), False)
		self.selectionChanged()

	def selEvent(self, dir, visible = True):
		if not self.selectedService:
			return False

		valid_event = self.selectedEventIndex is not None
		focus_event = None
		time_base = self.time_base
		time_focus = self.time_focus
		if dir == +1:   # Next event
			events = self.selectedService[2] #(service, service_name, events, picon)
			if valid_event and self.selectedEventIndex + 1 < len(events):
				self.setTimeFocusFromEvent(self.selectedEventIndex + 1)
				self.refreshSelection()
				self.l.invalidateEntry(self.l.getCurrentSelectionIndex())
				return False    # Same page
			# Next event is the first item on the next page
			time_base += self.time_epoch_secs
			focus_event = 0
		elif dir == -1:   # Prev event
			if valid_event and self.selectedEventIndex > 0:
				self.setTimeFocusFromEvent(self.selectedEventIndex - 1)
				self.refreshSelection()
				self.l.invalidateEntry(self.l.getCurrentSelectionIndex())
				return False    # Same page
			# Prev event is the last item on the previous page
			time_base -= self.time_epoch_secs
			focus_event = 65535
		elif dir == +2: # Next page
			time_base += self.time_epoch_secs
			time_focus += self.time_epoch_secs
		elif dir == +24: # Next day
			time_base += 86400
			time_focus += 86400
		elif dir == -2:
			time_base -= self.time_epoch_secs
			time_focus -= self.time_epoch_secs
		elif dir == -24: # Prevous day
			# keep the time base within the bounds of EPG data, rounded to a whole page
			abs0 = int(time() - (int(config.epg.histminutes.value) + self.time_epoch_secs // 4) * SECS_IN_MIN)
			abs0 += -abs0 % self.round_by_secs
			time_base = max(abs0, time_base - 86400)
			time_focus = max(abs0, time_focus - 86400)

		if time_base < self.time_base:
			# Prevent scrolling if it'll go past the EPG history limit
			# Work out the earliest we can go back to
			abs0 = int(time() - int(config.epg.histminutes.value) * SECS_IN_MIN)
			if time_base < abs0 - 3 * self.time_epoch_secs // 4:
				return False

		# If we are still here and moving - do the move now and return True to
		# indicate we've changed pages
		self.time_base = time_base
		self.time_focus = time_focus
		self.fillEPGNoRefresh()
		if focus_event is not None:
			self.setTimeFocusFromEvent(focus_event)
		self.refreshSelection()
		return True

	def fillEPG(self, services = None):
		self.fillEPGNoRefresh(services)
		self.refreshSelection()

	def fillEPGNoRefresh(self, services = None):
		if not self.graphicsloaded:
			if self.graphic:
				self.nowEvPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/CurrentEvent.png'))
				self.nowSelEvPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/SelectedCurrentEvent.png'))
				self.othEvPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/OtherEvent.png'))
				self.selEvPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/SelectedEvent.png'))
				self.othServPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/OtherService.png'))
				self.nowServPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/CurrentService.png'))
				self.recEvPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/RecordEvent.png'))
				self.recSelEvPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/SelectedRecordEvent.png'))
				self.zapEvPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/ZapEvent.png'))
				self.zapSelEvPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/SelectedZapEvent.png'))

				self.borderTopPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/BorderTop.png'))
				self.borderBottomPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/BorderBottom.png'))
				self.borderLeftPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/BorderLeft.png'))
				self.borderRightPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/BorderRight.png'))
				self.borderSelectedTopPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/SelectedBorderTop.png'))
				self.borderSelectedBottomPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/SelectedBorderBottom.png'))
				self.borderSelectedLeftPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/SelectedBorderLeft.png'))
				self.borderSelectedRightPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/SelectedBorderRight.png'))

			self.InfoPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/information.png'))
			self.selInfoPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/SelectedInformation.png'))

			self.graphicsloaded = True

		if services is None:
			test = [ (service[0], 0, self.time_base, self.time_epoch) for service in self.list ]
			serviceList = self.list
			piconIdx = 3
			channelIdx = 4
		else:
			self.selectedEventIndex = None
			self.selectedService = None
			test = [ (service.ref.toString(), 0, self.time_base, self.time_epoch) for service in services ]
			serviceList = services
			piconIdx = 0
			channelIdx = 0

		test.insert(0, 'XRnITBD') #return record, service ref, service name, event id, event title, begin time, duration
		epg_data = self.queryEPG(test)
		self.list = [ ]
		event_list = None
		serviceRef = ""
		serviceName = ""

		def appendService():
			picon = None if piconIdx == 0 else serviceList[serviceIdx][piconIdx]
			# We pass the serviceref if we don't have the channel number yet, so it can be grabbed
			channel = serviceList[serviceIdx] if channelIdx == 0 else serviceList[serviceIdx][channelIdx]
			self.list.append((serviceRef, serviceName, event_list[0][0] is not None and event_list or None, picon, channel))

		serviceIdx = 0
		for x in epg_data:
			if serviceRef != x[0]:
				if event_list:
					appendService()
					serviceIdx += 1
				serviceRef = x[0]
				serviceName = x[1]
				event_list = [ ]
			event_list.append((x[2], x[3], x[4], x[5])) #(event_id, event_title, begin_time, duration)
		if event_list and len(event_list) > 0:
			appendService()

		self.l.setList(self.list)
		self.recalcEventSize()

	def getChannelNumber(self,service):
		if hasattr(service, "ref") and service.ref and '0:0:0:0:0:0:0:0:0' not in service.ref.toString():
			numservice = service.ref
			num = numservice and numservice.getChannelNum() or None
			if num is not None:
				return num
		return None

	def getEventRect(self):
		rc = self.event_rect
		return eRect(rc.left() + (self.instance and self.instance.position().x() or 0), rc.top(), rc.width(), rc.height())

	def getServiceRect(self):
		rc = self.service_rect
		return eRect(rc.left() + (self.instance and self.instance.position().x() or 0), rc.top(), rc.width(), rc.height())

	def getTimeBase(self):
		return self.time_base


class TimelineText(GUIComponent):
	def __init__(self, epgConfig, graphic):
		GUIComponent.__init__(self)
		self.epgConfig = epgConfig
		self.graphic = graphic
		self.l = eListboxPythonMultiContent()
		self.l.setSelectionClip(eRect(0,0,0,0))
		self.itemHeight = 30
		self.TlDate = None
		self.TlTime = None
		self.foreColor = 0xffc000
		self.borderColor = 0x000000
		self.backColor = 0x000000
		self.borderWidth = 1
		self.time_base = 0
		self.time_epoch = 0
		self.timelineFontName = "Regular"
		self.timelineFontSize = 20
		self.datefmt = ""

	GUI_WIDGET = eListbox

	def applySkin(self, desktop, screen):
		if self.skinAttributes is not None:
			attribs = [ ]
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
					font = parseFont(value, ((1,1),(1,1)) )
					self.timelineFontName = font.family
					self.timelineFontSize = font.pointSize
				elif attrib == "itemHeight":
					self.itemHeight = int(value)
				else:
					attribs.append((attrib,value))
			self.skinAttributes = attribs
		rc = GUIComponent.applySkin(self, desktop, screen)
		self.listHeight = self.instance.size().height()
		self.listWidth = self.instance.size().width()
		self.setTimeLineFontsize()
		self.l.setItemHeight(self.itemHeight)
		if self.graphic:
			self.TlDate = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/TimeLineDate.png'))
			self.TlTime = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/TimeLineTime.png'))
		return rc

	def setTimeLineFontsize(self):
		font_conf = self.epgConfig.timelinefs.value
		if font_conf != None:
			self.l.setFont(0, gFont(self.timelineFontName, self.timelineFontSize + font_conf))

	def postWidgetCreate(self, instance):
		self.setTimeLineFontsize()
		instance.setContent(self.l)

	def setEntries(self, l, timeline_now, time_lines, force):
		event_rect = l.getEventRect()
		time_epoch = l.getTimeEpoch()
		time_base = l.getTimeBase()

		if event_rect is None or time_epoch is None or time_base is None:
			return

		eventLeft = event_rect.left()

		res = [ None ]

		# Note: event_rect and service_rect are relative to the timeline_text position
		# while the time lines are relative to the GraphEPG screen position!
		if self.time_base != time_base or self.time_epoch != time_epoch or force:
			service_rect = l.getServiceRect()
			time_steps = 60 if time_epoch > 180 else 30
			num_lines = time_epoch / time_steps
			incWidth = event_rect.width() / num_lines
			timeStepsCalc = time_steps * SECS_IN_MIN

			nowTime = localtime(time())
			begTime = localtime(time_base)
			serviceWidth = service_rect.width()
			if nowTime.tm_year == begTime.tm_year and nowTime.tm_yday == begTime.tm_yday:
				datestr = _("Today")
			else:
				if serviceWidth > 179:
					date_fmt = config.usage.date.daylong.value
				elif serviceWidth > 129:
					date_fmt = config.usage.date.dayshort.value
				elif serviceWidth > 79:
					date_fmt = config.usage.date.daysmall.value
				else:
					date_fmt = "%a"
				datestr = strftime(date_fmt, begTime)

			foreColor = self.foreColor
			backColor = self.backColor
			bgpng = self.TlDate
			if bgpng is not None and self.graphic:
				backColor = None
				backColorSel = None
				res.append(MultiContentEntryPixmapAlphaTest(
					pos = (0, 0),
					size = (service_rect.width(), self.listHeight),
					png = bgpng,
					flags = BT_SCALE))
			else:
				res.append( MultiContentEntryText(
					pos = (0, 0),
					size = (service_rect.width(), self.listHeight),
					color = foreColor,
					backcolor = backColor,
					border_width = self.borderWidth, border_color = self.borderColor))

			res.append(MultiContentEntryText(
				pos = (5, 0),
				size = (service_rect.width()-15, self.listHeight),
				font = 0, flags = int(config.epgselection.grid.timelinedate_alignment.value),
				text = _(datestr),
				color = foreColor,
				backcolor = backColor))

			bgpng = self.TlTime
			xpos = 0 # eventLeft
			if bgpng is not None and self.graphic:
				backColor = None
				backColorSel = None
				res.append(MultiContentEntryPixmapAlphaTest(
					pos = (service_rect.width(), 0),
					size = (event_rect.width(), self.listHeight),
					png = bgpng,
					flags = BT_SCALE))
			else:
				res.append( MultiContentEntryText(
					pos = (service_rect.width(), 0),
					size = (event_rect.width(), self.listHeight),
					color = foreColor,
					backcolor = backColor,
					border_width = self.borderWidth, border_color = self.borderColor))

			for x in range(0, num_lines):
				ttime = localtime(time_base + (x * timeStepsCalc))
				if config.usage.time.enabled.value:
					timetext = strftime(config.usage.time.short.value, ttime)
				else:
					if self.epgConfig.timeline24h.value:
						timetext = strftime("%H:%M", ttime)
					else:
						if int(strftime("%H", ttime)) > 12:
							timetext = strftime("%-I:%M", ttime) + _('pm')
						else:
							timetext = strftime("%-I:%M", ttime) + _('am')
				res.append(MultiContentEntryText(
					pos = (service_rect.width() + xpos, 0),
					size = (incWidth, self.listHeight),
					font = 0, flags = RT_HALIGN_LEFT | RT_VALIGN_CENTER,
					text = timetext,
					color = foreColor,
					backcolor = backColor))
				line = time_lines[x]
				old_pos = line.position
				line.setPosition(xpos + eventLeft, old_pos[1])
				line.visible = True
				xpos += incWidth
			for x in range(num_lines, MAX_TIMELINES):
				time_lines[x].visible = False
			self.l.setList([res])
			self.time_base = time_base
			self.time_epoch = time_epoch

		now = time()
		if time_base <= now < (time_base + time_epoch * SECS_IN_MIN):
			xpos = int((((now - time_base) * event_rect.width()) / (time_epoch * SECS_IN_MIN)) - (timeline_now.instance.size().width() / 2))
			old_pos = timeline_now.position
			new_pos = (xpos + eventLeft, old_pos[1])
			if old_pos != new_pos:
				timeline_now.setPosition(new_pos[0], new_pos[1])
			timeline_now.visible = True
		else:
			timeline_now.visible = False
