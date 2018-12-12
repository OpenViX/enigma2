import skin
from time import localtime, time, strftime

from enigma import eEPGCache, eListbox, eListboxPythonMultiContent, loadPNG, gFont, getDesktop, eRect, eSize, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, RT_VALIGN_CENTER, RT_VALIGN_TOP, RT_WRAP, BT_SCALE, BT_KEEP_ASPECT_RATIO

from GUIComponent import GUIComponent
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmapAlphaBlend, MultiContentEntryPixmapAlphaTest
from Components.Renderer.Picon import getPiconName
from skin import parseColor, parseFont
from Tools.Alternatives import CompareWithAlternatives
from Tools.LoadPixmap import LoadPixmap
from Components.config import config
from ServiceReference import ServiceReference
from Tools.Directories import resolveFilename, SCOPE_ACTIVE_SKIN
from Tools.TextBoundary import getTextBoundarySize

EPG_TYPE_SINGLE = 0
EPG_TYPE_MULTI = 1
EPG_TYPE_SIMILAR = 2
EPG_TYPE_ENHANCED = 3
EPG_TYPE_INFOBAR = 4
EPG_TYPE_GRAPH = 5
EPG_TYPE_INFOBARGRAPH = 7

MAX_TIMELINES = 6

class Rect:
	def __init__(self, x, y, width, height):
		self.x = x
		self.y = y
		self.w = width
		self.h = height

	# silly, but backward compatible
	def left(self):
		return self.x

	def top(self):
		return self.y

	def height(self):
		return self.h

	def width(self):
		return self.w

# Various value are in minutes, while others are in seconds.
# Use this to remind us what is going on...
#
SECS_IN_MIN = 60

class EPGList(GUIComponent):
	def __init__(self, type = EPG_TYPE_SINGLE, selChangedCB = None, timer = None, time_epoch = 120, overjump_empty = False, graphic=False):
		self.cur_event = None
		self.cur_service = None
		self.time_focus = time() # default to now
		self.time_base = None
		self.time_epoch = time_epoch
		self.select_rect = None
		self.event_rect = None
		self.service_rect = None
		self.currentlyPlaying = None
		self.showPicon = False
		self.showServiceTitle = True
		self.showServiceNumber = False
		self.screenwidth = getDesktop(0).size().width()
		self.overjump_empty = overjump_empty
		self.timer = timer
		self.onSelChanged = [ ]
		if selChangedCB is not None:
			self.onSelChanged.append(selChangedCB)
		GUIComponent.__init__(self)
		self.type = type
		self.graphic = graphic
		self.l = eListboxPythonMultiContent()

		if type == EPG_TYPE_SINGLE or type == EPG_TYPE_ENHANCED or type == EPG_TYPE_INFOBAR:
			self.l.setBuildFunc(self.buildSingleEntry)
		elif type == EPG_TYPE_MULTI:
			self.l.setBuildFunc(self.buildMultiEntry)
		elif type == EPG_TYPE_GRAPH or type == EPG_TYPE_INFOBARGRAPH:
			self.l.setBuildFunc(self.buildGraphEntry)
			if self.type == EPG_TYPE_GRAPH:
				value = config.epgselection.graph_servicetitle_mode.value
				round_by = int(config.epgselection.graph_roundto.value)
			elif self.type == EPG_TYPE_INFOBARGRAPH:
				value = config.epgselection.infobar_servicetitle_mode.value
				round_by = int(config.epgselection.infobar_roundto.value)
			self.round_by_secs = round_by * SECS_IN_MIN
			self.time_epoch_secs = time_epoch * SECS_IN_MIN
			self.showServiceNumber = "servicenumber" in value
			self.showServiceTitle = "servicename" in value
			self.showPicon = "picon" in value
		else:
			assert(type == EPG_TYPE_SIMILAR)
			self.l.setBuildFunc(self.buildSimilarEntry)
		self.epgcache = eEPGCache.getInstance()

		self.clocks = [ LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_add.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_pre.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_prepost.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_post.png')),

				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_add.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_pre.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_zap.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_prepost.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_post.png')),

				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_add.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_pre.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_zaprec.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_prepost.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_post.png')),

				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_add.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_pre.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_prepost.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_post.png'))]

		self.selclocks = [ LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_add.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_selpre.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_selprepost.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_selpost.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_add.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_selpre.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_zap.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_selprepost.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_selpost.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_add.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_selpre.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_zaprec.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_selprepost.png')),
				LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_selpost.png'))]

		self.autotimericon = LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_autotimer.png'))

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

		self.serviceFontNameGraph = "Regular"
		self.eventFontNameGraph = "Regular"
		self.eventFontNameSingle = "Regular"
		self.eventFontNameMulti = "Regular"
		self.serviceFontNameInfobar = "Regular"
		self.eventFontNameInfobar = "Regular"

		if self.screenwidth and self.screenwidth == 1920:
			self.serviceFontSizeGraph = 28
			self.eventFontSizeGraph = 28
			self.eventFontSizeSingle = 28
			self.eventFontSizeMulti = 28
			self.serviceFontSizeInfobar = 28
			self.eventFontSizeInfobar = 28
		else:
			self.serviceFontSizeGraph = 20
			self.eventFontSizeGraph = 20
			self.eventFontSizeSingle = 20
			self.eventFontSizeMulti = 20
			self.serviceFontSizeInfobar = 20
			self.eventFontSizeInfobar = 20

		self.listHeight = None
		self.listWidth = None
		self.serviceBorderWidth = 1
		self.serviceNamePadding = 3
		self.serviceNumberPadding = 9
		self.eventBorderWidth = 1
		self.eventNamePadding = 3
		self.NumberOfRows = None
		self.serviceNumberWidth = 0

	def applySkin(self, desktop, screen):
		if self.skinAttributes is not None:
			attribs = [ ]
			for (attrib, value) in self.skinAttributes:
				if attrib == "ServiceFontGraphical":
					font = parseFont(value, ((1,1),(1,1)) )
					self.serviceFontNameGraph = font.family
					self.serviceFontSizeGraph = font.pointSize
				elif attrib == "EntryFontGraphical":
					font = parseFont(value, ((1,1),(1,1)) )
					self.eventFontNameGraph = font.family
					self.eventFontSizeGraph = font.pointSize
				elif attrib == "ServiceFontInfobar":
					font = parseFont(value, ((1,1),(1,1)) )
					self.serviceFontNameInfobar = font.family
					self.serviceFontSizeInfobar = font.pointSize
				elif attrib == "EventFontInfobar":
					font = parseFont(value, ((1,1),(1,1)) )
					self.eventFontNameInfobar = font.family
					self.eventFontSizeInfobar = font.pointSize
				elif attrib == "EventFontSingle":
					font = parseFont(value, ((1,1),(1,1)) )
					self.eventFontNameSingle = font.family
					self.eventFontSizeSingle = font.pointSize

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
				elif attrib == "NumberOfRows":
					self.NumberOfRows = int(value)
				else:
					attribs.append((attrib,value))
			self.skinAttributes = attribs
		rc = GUIComponent.applySkin(self, desktop, screen)
		self.listHeight = self.instance.size().height()
		self.listWidth = self.instance.size().width()
		self.setItemsPerPage()
		self.setFontsize()

		# cache service number width
		if self.showServiceNumber:
			if self.type == EPG_TYPE_GRAPH:
				font_conf = config.epgselection.graph_servfs.value
			elif self.type == EPG_TYPE_INFOBARGRAPH:
				font_conf = config.epgselection.infobar_servfs.value
			font = gFont(self.serviceFontNameGraph, self.serviceFontSizeGraph + font_conf)
			self.serviceNumberWidth = getTextBoundarySize(self.instance, font, self.instance.size(), "0000" ).width()

		return rc

	def getCurrentChangeCount(self):
		if self.type == EPG_TYPE_MULTI and self.l.getCurrentSelection() is not None:
			return self.l.getCurrentSelection()[0]
		return 0

	def isSelectable(self, service, service_name, events, picon, channel):
		return (events and len(events) and True) or False

	def setTimeFocus(self, time_focus):
		self.time_focus = time_focus

	def setOverjump_Empty(self, overjump_empty):
		if overjump_empty:
			self.l.setSelectableFunc(self.isSelectable)
		else:
			self.l.setSelectableFunc(None)

	def setTimeEpoch(self, epoch):
		self.time_epoch = epoch
		self.time_epoch_secs = epoch * SECS_IN_MIN
		self.fillGraphEPG(None)

	def getTimeEpoch(self):
		return self.time_epoch

	def setCurrentlyPlaying(self, serviceref):
		self.currentlyPlaying = serviceref

	def getEventFromId(self, service, eventid):
		event = None
		if self.epgcache is not None and eventid is not None:
			event = self.epgcache.lookupEventId(service.ref, eventid)
		return event

	def getIndexFromService(self, serviceref):
		if serviceref is not None:
			for x in range(len(self.list)):
				if CompareWithAlternatives(self.list[x][0], serviceref.toString()):
					return x
				if CompareWithAlternatives(self.list[x][1], serviceref.toString()):
					return x
		return None

	def getCurrentIndex(self):
		return self.instance.getCurrentIndex()

	def moveToService(self, serviceref):
		if not serviceref:
			return
		newIdx = self.getIndexFromService(serviceref)
		if newIdx is None:
			newIdx = 0
		self.setCurrentIndex(newIdx)

	def setCurrentIndex(self, index):
		if self.instance is not None:
			self.instance.moveSelectionTo(index)

	def moveTo(self, dir):
		if self.instance is not None:
			self.instance.moveSelection(dir)

	def getCurrent(self):
		if self.type == EPG_TYPE_GRAPH or self.type == EPG_TYPE_INFOBARGRAPH:
			if self.cur_service is None:
				return None, None
			events = self.cur_service[2]
			refstr = self.cur_service[0]
			if self.cur_event is None or not events or (self.cur_event and events and self.cur_event > len(events)-1):
				return None, ServiceReference(refstr)
			event = events[self.cur_event] #(event_id, event_title, begin_time, duration)
			eventid = event[0]
			service = ServiceReference(refstr)
			event = self.getEventFromId(service, eventid) # get full event info
			return event, service
		else:
			idx = 0
			if self.type == EPG_TYPE_MULTI:
				idx += 1
			tmp = self.l.getCurrentSelection()
			if tmp is None:
				return None, None
			eventid = tmp[idx+1]
			service = ServiceReference(tmp[idx])
			event = self.getEventFromId(service, eventid)
			return event, service

	def connectSelectionChanged(func):
		if not self.onSelChanged.count(func):
			self.onSelChanged.append(func)

	def disconnectSelectionChanged(func):
		self.onSelChanged.remove(func)

	def serviceChanged(self):
		cur_sel = self.l.getCurrentSelection()
		if cur_sel:
			self.selectEventFromTime()
			self.selEntry(0)

	def selectEventFromTime(self):
		cur_service = self.cur_service = self.l.getCurrentSelection()
		if cur_service:
			self.cur_event = None
			events = cur_service[2]
			if events and len(events):
				self.cur_event = 0
				if self.time_focus >= events[0][2]:
					for event in events: #iterate all events
						ev_time = event[2]
						ev_end_time = ev_time + event[3]
						self.cur_event += 1
						if ev_time <= self.time_focus < ev_end_time:
							break
					self.cur_event -= 1

	def setTimeFocusFromEvent(self, cur_event):
		cur_service = self.l.getCurrentSelection()
		if cur_service:
			events = cur_service[2]
			if events and len(events):
				self.cur_event = max(min(len(events) - 1, cur_event), 0)
				event = events[self.cur_event]

				# clip the selected event times to the current screen
				time_base = self.getTimeBase()
				ev_time = max(time_base, event[2])
				ev_end_time = min(event[2] + event[3], time_base + self.time_epoch_secs)
				if ev_time <= time() < ev_end_time:
					# selected event contains the current time, user is interested in current things
					self.time_focus = time()
				else:
					# user is looking at things roughly around the middle of the selected event
					self.time_focus = ev_time + (ev_end_time - ev_time) / 2
		else:
			self.cur_event = None
		self.selEntry(0)

	def selectionChanged(self):
		for x in self.onSelChanged:
			if x is not None:
				x()

	GUI_WIDGET = eListbox

	def setItemsPerPage(self):
		if self.type == EPG_TYPE_GRAPH or self.type == EPG_TYPE_INFOBARGRAPH:
			if self.type == EPG_TYPE_GRAPH:
				if self.listHeight > 0:
					itemHeight = self.listHeight / config.epgselection.graph_itemsperpage.value
				else:
					itemHeight = 54 # some default (270/5)
				if config.epgselection.graph_heightswitch.value:
					if ((self.listHeight / config.epgselection.graph_itemsperpage.value) / 3) >= 27:
						tmp_itemHeight = ((self.listHeight / config.epgselection.graph_itemsperpage.value) / 3)
					elif ((self.listHeight / config.epgselection.graph_itemsperpage.value) / 2) >= 27:
						tmp_itemHeight = ((self.listHeight / config.epgselection.graph_itemsperpage.value) / 2)
					else:
						tmp_itemHeight = 27
					if tmp_itemHeight < itemHeight:
						itemHeight = tmp_itemHeight
					else:
						if ((self.listHeight / config.epgselection.graph_itemsperpage.value) * 3) <= 45:
							itemHeight = ((self.listHeight / config.epgselection.graph_itemsperpage.value) * 3)
						elif ((self.listHeight / config.epgselection.graph_itemsperpage.value) * 2) <= 45:
							itemHeight = ((self.listHeight / config.epgselection.graph_itemsperpage.value) * 2)
						else:
							itemHeight = 45
				if self.NumberOfRows:
					config.epgselection.graph_itemsperpage.default = self.NumberOfRows
			elif self.type == EPG_TYPE_INFOBARGRAPH:
				if self.NumberOfRows:
					config.epgselection.infobar_itemsperpage.default = self.NumberOfRows
				if self.listHeight > 0:
					itemHeight = self.listHeight / config.epgselection.infobar_itemsperpage.value
				else:
					itemHeight = 54 # some default (270/5)
			self.l.setItemHeight(itemHeight)
			self.instance.resize(eSize(self.listWidth, self.listHeight / itemHeight * itemHeight))
			self.listHeight = self.instance.size().height()
			self.listWidth = self.instance.size().width()
			self.itemHeight = itemHeight

		elif self.type == EPG_TYPE_ENHANCED or self.type == EPG_TYPE_SINGLE or self.type == EPG_TYPE_SIMILAR:
			if self.NumberOfRows:
				config.epgselection.enhanced_itemsperpage.default = self.NumberOfRows
			if self.listHeight > 0:
				itemHeight = self.listHeight / config.epgselection.enhanced_itemsperpage.value
			else:
				itemHeight = 32
			if itemHeight < 20:
				itemHeight = 20
			self.l.setItemHeight(itemHeight)
			self.instance.resize(eSize(self.listWidth, self.listHeight / itemHeight * itemHeight))
			self.listHeight = self.instance.size().height()
			self.listWidth = self.instance.size().width()
			self.itemHeight = itemHeight
		elif self.type == EPG_TYPE_MULTI:
			if self.NumberOfRows:
				config.epgselection.multi_itemsperpage.default = self.NumberOfRows
			if self.listHeight > 0:
				itemHeight = self.listHeight / config.epgselection.multi_itemsperpage.value
			else:
				itemHeight = 32
			if itemHeight < 20:
				itemHeight = 20
			self.l.setItemHeight(itemHeight)
			self.instance.resize(eSize(self.listWidth, self.listHeight / itemHeight * itemHeight))
			self.listHeight = self.instance.size().height()
			self.listWidth = self.instance.size().width()
			self.itemHeight = itemHeight
		elif self.type == EPG_TYPE_INFOBAR:
			if self.NumberOfRows:
				config.epgselection.infobar_itemsperpage.default = self.NumberOfRows
			if self.listHeight > 0:
				itemHeight = self.listHeight / config.epgselection.infobar_itemsperpage.value
			else:
				itemHeight = 32
			if itemHeight < 20:
				itemHeight = 20
			self.l.setItemHeight(int(itemHeight))
			self.instance.resize(eSize(self.listWidth, self.listHeight / itemHeight * itemHeight))
			self.listHeight = self.instance.size().height()
			self.listWidth = self.instance.size().width()
			self.itemHeight = itemHeight

	def setFontsize(self):
		if self.type == EPG_TYPE_GRAPH:
			self.l.setFont(0, gFont(self.serviceFontNameGraph, self.serviceFontSizeGraph + config.epgselection.graph_servfs.value))
			self.l.setFont(1, gFont(self.eventFontNameGraph, self.eventFontSizeGraph + config.epgselection.graph_eventfs.value))
		elif self.type == EPG_TYPE_ENHANCED or self.type == EPG_TYPE_SINGLE or self.type == EPG_TYPE_SIMILAR:
			self.l.setFont(0, gFont(self.eventFontNameSingle, self.eventFontSizeSingle + config.epgselection.enhanced_eventfs.value))
		elif self.type == EPG_TYPE_MULTI:
			self.l.setFont(0, gFont(self.eventFontNameMulti, self.eventFontSizeMulti + config.epgselection.multi_eventfs.value))
			self.l.setFont(1, gFont(self.eventFontNameMulti, self.eventFontSizeMulti - 4 + config.epgselection.multi_eventfs.value))
		elif self.type == EPG_TYPE_INFOBAR:
			self.l.setFont(0, gFont(self.eventFontNameInfobar, self.eventFontSizeInfobar + config.epgselection.infobar_eventfs.value))
		elif self.type == EPG_TYPE_INFOBARGRAPH:
			self.l.setFont(0, gFont(self.serviceFontNameInfobar, self.serviceFontSizeInfobar + config.epgselection.infobar_servfs.value))
			self.l.setFont(1, gFont(self.eventFontNameInfobar, self.eventFontSizeInfobar + config.epgselection.infobar_eventfs.value))

	def postWidgetCreate(self, instance):
		if self.type == EPG_TYPE_GRAPH or self.type == EPG_TYPE_INFOBARGRAPH:
			self.setOverjump_Empty(self.overjump_empty)
			instance.setWrapAround(True)
			instance.selectionChanged.get().append(self.serviceChanged)
			instance.setContent(self.l)
			self.l.setSelectionClip(eRect(0,0,0,0), False)
		else:
			instance.setWrapAround(False)
			instance.selectionChanged.get().append(self.selectionChanged)
			instance.setContent(self.l)

	def preWidgetRemove(self, instance):
		if self.type == EPG_TYPE_GRAPH or self.type == EPG_TYPE_INFOBARGRAPH:
			instance.selectionChanged.get().remove(self.serviceChanged)
			instance.setContent(None)
		else:
			instance.selectionChanged.get().remove(self.selectionChanged)
			instance.setContent(None)

	def selectionEnabled(self, enabled):
		if self.instance is not None:
			self.instance.setSelectionEnable(enabled)

	def recalcEntrySize(self):
		esize = self.l.getItemSize()
		width = esize.width()
		height = esize.height()
		if self.type == EPG_TYPE_MULTI:
			fontSize = self.eventFontSizeMulti + config.epgselection.multi_eventfs.value
			servScale, timeScale, durScale, wideScale = skin.parameters.get("EPGMultiColumnScales", (6.5, 6.0, 4.5, 1.5))
			# servW = int((fontSize + 4) * servScale)  # Service font is 4 px larger
			servW = int(fontSize * servScale)
			timeW = int(fontSize * timeScale)
			durW = int(fontSize * durScale)
			left, servWidth, sepWidth, timeWidth, progHeight, breakWidth, durWidth, gapWidth = skin.parameters.get("EPGMultiColumnSpecs", (0, servW, 10, timeW, height - 12, 10, durW, 10))
			if config.usage.time.wide.value:
				timeWidth = int(timeWidth * wideScale)
			self.service_rect = Rect(left, 0, servWidth, height)
			left += servWidth + sepWidth
			self.start_end_rect = Rect(left, 0, timeWidth, height)
			progTop = int((height - progHeight) / 2)
			self.progress_rect = Rect(left, progTop, timeWidth, progHeight)
			left += timeWidth + breakWidth
			self.duration_rect = Rect(left, 0, durWidth, height)
			left += durWidth + gapWidth
			self.descr_rect = Rect(left, 0, width - left, height)
		elif self.type == EPG_TYPE_GRAPH or self.type == EPG_TYPE_INFOBARGRAPH:
			servicew = 0
			piconw = 0
			channelw = 0
			if self.type == EPG_TYPE_GRAPH:
				if self.showServiceTitle:
					servicew = config.epgselection.graph_servicewidth.value
				if self.showPicon:
					piconw = config.epgselection.graph_piconwidth.value
				if self.showServiceNumber:
					channelw = self.serviceNumberWidth
			elif self.type == EPG_TYPE_INFOBARGRAPH:
				if self.showServiceTitle:
					servicew = config.epgselection.infobar_servicewidth.value
				if self.showPicon:
					piconw = config.epgselection.infobar_piconwidth.value
				if self.showServiceNumber:
					channelw = self.serviceNumberWidth
			w = (channelw + piconw + servicew)
			self.service_rect = Rect(0, 0, w, height)
			self.event_rect = Rect(w, 0, width - w, height)
			piconHeight = height - 2 * self.serviceBorderWidth
			piconWidth = piconw
			if piconWidth > w - 2 * self.serviceBorderWidth:
				piconWidth = w - 2 * self.serviceBorderWidth
			self.picon_size = eSize(piconWidth, piconHeight)
		else:
			fontSize = self.eventFontSizeSingle + config.epgselection.enhanced_eventfs.value
			dateScale, timesScale, wideScale = skin.parameters.get("EPGSingleColumnScales", (5.7, 6.0, 1.5))
			dateW = int(fontSize * dateScale)
			timesW = int(fontSize * timesScale)
			left, dateWidth, sepWidth, timesWidth, breakWidth = skin.parameters.get("EPGSingleColumnSpecs", (0, dateW, 5, timesW, 20))
			if config.usage.time.wide.value:
				timesWidth = int(timesWidth * wideScale)
			self.weekday_rect = Rect(left, 0, dateWidth, height)
			left += dateWidth + sepWidth
			self.datetime_rect = Rect(left, 0, timesWidth, height)
			left += timesWidth + breakWidth
			self.descr_rect = Rect(left, 0, width - left, height)
			self.showend = True  # This is not an unused variable. It is a flag used by EPGSearch plugin

	def calcEntryPosAndWidthHelper(self, stime, duration, start, end, width):
		xpos = (stime - start) * width / (end - start)
		ewidth = (stime + duration - start) * width / (end - start)
		ewidth -= xpos
		if xpos < 0:
			ewidth += xpos
			xpos = 0
		if (xpos + ewidth) > width:
			ewidth = width - xpos
		return xpos, ewidth

	def calcEntryPosAndWidth(self, event_rect, time_base, time_epoch_secs, ev_start, ev_duration):
		xpos, width = self.calcEntryPosAndWidthHelper(ev_start, ev_duration, time_base, time_base + time_epoch_secs, event_rect.width())
		return xpos + event_rect.left(), width

	def getPixmapForEntry(self, service, eventId, beginTime, duration):
		if not beginTime:
			return None
		rec = self.timer.isInTimer(eventId, beginTime, duration, service)
		if rec is not None:
			self.wasEntryAutoTimer = rec[2]
			return rec[1]
		else:
			self.wasEntryAutoTimer = False
			return None

	def buildSingleEntry(self, service, eventId, beginTime, duration, EventName):
		clock_types = self.getPixmapForEntry(service, eventId, beginTime, duration)
		r1 = self.weekday_rect
		r2 = self.datetime_rect
		r3 = self.descr_rect
		split = int(r2.w * 0.55)
		t = localtime(beginTime)
		et = localtime(beginTime + duration)
		res = [
			None, # no private data needed
			(eListboxPythonMultiContent.TYPE_TEXT, r1.x, r1.y, r1.w, r1.h, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, strftime(config.usage.date.dayshort.value, t)),
			(eListboxPythonMultiContent.TYPE_TEXT, r2.x, r2.y, split, r2.h, 0, RT_HALIGN_RIGHT | RT_VALIGN_CENTER, strftime(config.usage.time.short.value + " -", t)),
			(eListboxPythonMultiContent.TYPE_TEXT, r2.x + split, r2.y, r2.w - split, r2.h, 0, RT_HALIGN_RIGHT | RT_VALIGN_CENTER, strftime(config.usage.time.short.value, et))
		]
		if clock_types:
			if self.wasEntryAutoTimer and clock_types in (2,7,12):
				if self.screenwidth and self.screenwidth == 1920:
					res.extend((
						(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, r3.x+r3.w-25, (r3.h/2-13), 25, 25, self.clocks[clock_types]),
						(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, r3.x+r3.w-52, (r3.h/2-13), 25, 25, self.autotimericon),
						(eListboxPythonMultiContent.TYPE_TEXT, r3.x, r3.y, r3.w-52, r3.h, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, EventName)
						))
				else:
					res.extend((
						(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, r3.x+r3.w-21, (r3.h/2-11), 21, 21, self.clocks[clock_types]),
						(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, r3.x+r3.w-42, (r3.h/2-11), 21, 21, self.autotimericon),
						(eListboxPythonMultiContent.TYPE_TEXT, r3.x, r3.y, r3.w-42, r3.h, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, EventName)
						))
			else:
				if self.screenwidth and self.screenwidth == 1920:
					res.extend((
						(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, r3.x+r3.w-25, (r3.h/2-13), 25, 25, self.clocks[clock_types]),
						(eListboxPythonMultiContent.TYPE_TEXT, r3.x, r3.y, r3.w-25, r3.h, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, EventName)
						))
				else:
					res.extend((
						(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, r3.x+r3.w-21, (r3.h/2-11), 21, 21, self.clocks[clock_types]),
						(eListboxPythonMultiContent.TYPE_TEXT, r3.x, r3.y, r3.w-21, r3.h, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, EventName)
						))
		else:
			res.append((eListboxPythonMultiContent.TYPE_TEXT, r3.x, r3.y, r3.w, r3.h, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, EventName))
		return res

	def buildSimilarEntry(self, service, eventId, beginTime, service_name, duration):
		clock_types = self.getPixmapForEntry(service, eventId, beginTime, duration)
		r1 = self.weekday_rect
		r2 = self.datetime_rect
		r3 = self.descr_rect
		split = int(r2.w * 0.55)
		t = localtime(beginTime)
		et = localtime(beginTime + duration)
		res = [
			None,  # no private data needed
			(eListboxPythonMultiContent.TYPE_TEXT, r1.x, r1.y, r1.w, r1.h, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, strftime(config.usage.date.dayshort.value, t)),
			(eListboxPythonMultiContent.TYPE_TEXT, r2.x, r2.y, split, r2.h, 0, RT_HALIGN_RIGHT | RT_VALIGN_CENTER, strftime(config.usage.time.short.value + " -", t)),
			(eListboxPythonMultiContent.TYPE_TEXT, r2.x + split, r2.y, r2.w - split, r2.h, 0, RT_HALIGN_RIGHT | RT_VALIGN_CENTER, strftime(config.usage.time.short.value, et))
		]
		if clock_types:
			if self.wasEntryAutoTimer and clock_types in (2,7,12):
				if self.screenwidth and self.screenwidth == 1920:
					res.extend((
						(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, r3.x+r3.w-25, (r3.h/2-13), 25, 25, self.clocks[clock_types]),
						(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, r3.x+r3.w-52, (r3.h/2-13), 25, 25, self.autotimericon),
						(eListboxPythonMultiContent.TYPE_TEXT, r3.x, r3.y, r3.w-52, r3.h, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, service_name)
					))
				else:
					res.extend((
						(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, r3.x+r3.w-21, (r3.h/2-11), 21, 21, self.clocks[clock_types]),
						(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, r3.x+r3.w-42, (r3.h/2-11), 21, 21, self.autotimericon),
						(eListboxPythonMultiContent.TYPE_TEXT, r3.x, r3.y, r3.w-42, r3.h, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, service_name)
					))
			else:
				if self.screenwidth and self.screenwidth == 1920:
					res.extend((
						(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, r3.x+r3.w-25, (r3.h/2-13), 25, 25, self.clocks[clock_types]),
						(eListboxPythonMultiContent.TYPE_TEXT, r3.x, r3.y, r3.w-25, r3.h, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, service_name)
					))
				else:
					res.extend((
						(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, r3.x+r3.w-21, (r3.h/2-11), 21, 21, self.clocks[clock_types]),
						(eListboxPythonMultiContent.TYPE_TEXT, r3.x, r3.y, r3.w-21, r3.h, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, service_name)
					))
		else:
			res.append((eListboxPythonMultiContent.TYPE_TEXT, r3.x, r3.y, r3.w, r3.h, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, service_name))
		return res

	def buildMultiEntry(self, changecount, service, eventId, beginTime, duration, EventName, nowTime, service_name):
		r1 = self.service_rect
		r2 = self.start_end_rect
		r3 = self.progress_rect
		r4 = self.duration_rect
		r5 = self.descr_rect
		res = [
			None,  # no private data needed
			(eListboxPythonMultiContent.TYPE_TEXT, r1.x, r1.y, r1.w, r1.h, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, service_name)
		]
		if beginTime is not None:
			fontSize = self.eventFontSizeMulti + config.epgselection.multi_eventfs.value
			if nowTime < beginTime:
				begin = localtime(beginTime)
				end = localtime(beginTime + duration)
				split = int(r2.w * 0.55)
				res.extend((
					(eListboxPythonMultiContent.TYPE_TEXT, r2.x, r2.y, split, r2.h, 0, RT_HALIGN_RIGHT | RT_VALIGN_CENTER, strftime(config.usage.time.short.value + " - ", begin)),
					(eListboxPythonMultiContent.TYPE_TEXT, r2.x + split, r2.y, r2.w - split, r2.h, 0, RT_HALIGN_RIGHT | RT_VALIGN_CENTER, strftime(config.usage.time.short.value, end))
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
				res.append((eListboxPythonMultiContent.TYPE_PROGRESS, r3.x, r3.y, r3.w, r3.h, percent))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, r4.x, r4.y, r4.w, r4.h, 0, RT_HALIGN_RIGHT | RT_VALIGN_CENTER, _("%s%d Min") % (prefix, remaining)))
			width = r5.w
			clock_types = self.getPixmapForEntry(service, eventId, beginTime, duration)
			if clock_types:
				clk_sz = 25 if self.screenwidth and self.screenwidth == 1920 else 21
				width -= clk_sz / 2 if clock_types in (1, 6, 11) else clk_sz
				res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, r5.x + width, (r5.h - clk_sz) / 2, clk_sz, clk_sz, self.clocks[clock_types]))
				if self.wasEntryAutoTimer and clock_types in (2, 7, 12):
					width -= clk_sz + 1
					res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, r5.x + width, (r5.h - clk_sz) / 2, clk_sz, clk_sz, self.autotimericon))
				width -= 5
			res.append((eListboxPythonMultiContent.TYPE_TEXT, r5.x, r5.y, width, r5.h, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, EventName))
		return res

	def buildGraphEntry(self, service, service_name, events, picon, channel):
		r1 = self.service_rect
		r2 = self.event_rect
		left = r2.x
		top = r2.y
		width = r2.w
		height = r2.h
		selected = self.cur_service[0] == service
		res = [ None ]

		borderTopPix = None
		borderLeftPix = None
		borderBottomPix = None
		borderRightPix = None

		# Picon and Service name
		serviceForeColor = self.foreColorService
		serviceBackColor = self.backColorService
		bgpng = self.othServPix
		if CompareWithAlternatives(service, self.currentlyPlaying and self.currentlyPlaying.toString()):
			serviceForeColor = self.foreColorServiceNow
			serviceBackColor = self.backColorServiceNow
			bgpng = self.nowServPix

		if bgpng is not None and self.graphic:
			serviceBackColor = None
			res.append(MultiContentEntryPixmapAlphaBlend(
					pos = (r1.x + self.serviceBorderWidth, r1.y + self.serviceBorderWidth),
					size = (r1.w - 2 * self.serviceBorderWidth, r1.h - 2 * self.serviceBorderWidth),
					png = bgpng,
					flags = BT_SCALE))
		else:
			res.append(MultiContentEntryText(
					pos  = (r1.x, r1.y),
					size = (r1.w, r1.h),
					font = 0, flags = RT_HALIGN_LEFT | RT_VALIGN_CENTER,
					text = "",
					color = serviceForeColor, color_sel = serviceForeColor,
					backcolor = serviceBackColor, backcolor_sel = serviceBackColor,
					border_width = self.serviceBorderWidth, border_color = self.borderColorService))

		displayPicon = None
		if self.showPicon:
			if picon is None: # go find picon and cache its location
				picon = getPiconName(service)
				curIdx = self.l.getCurrentSelectionIndex()
				self.list[curIdx] = (service, service_name, events, picon, channel)
			piconWidth = self.picon_size.width()
			piconHeight = self.picon_size.height()
			if picon != "":
				displayPicon = loadPNG(picon)
			if displayPicon is not None:
				res.append(MultiContentEntryPixmapAlphaBlend(
					pos = (r1.x + self.serviceBorderWidth, r1.y + self.serviceBorderWidth),
					size = (piconWidth, piconHeight),
					png = displayPicon,
					backcolor = None, backcolor_sel = None, flags = BT_SCALE | BT_KEEP_ASPECT_RATIO))
			elif not self.showServiceTitle:
				# no picon so show servicename anyway in picon space
				namefont = 1
				namefontflag = int(config.epgselection.graph_servicename_alignment.value)
				namewidth = piconWidth
			else:
				piconWidth = 0
		else:
			piconWidth = 0

		channelWidth = 0
		if self.showServiceNumber:
			if not isinstance(channel, int):
				channel = self.getChannelNumber(channel)

			if channel:
				namefont = 0
				namefontflag = int(config.epgselection.graph_servicenumber_alignment.value)
				font = gFont(self.serviceFontNameGraph, self.serviceFontSizeGraph + config.epgselection.graph_servfs.value)
				channelWidth = getTextBoundarySize(self.instance, font, self.instance.size(), (channel < 10000)  and "0000" or str(channel) ).width()
				res.append(MultiContentEntryText(
					pos = (r1.x + self.serviceNamePadding + piconWidth + self.serviceNamePadding, r1.y + self.serviceBorderWidth),
					size = (channelWidth, r1.h - 2 * self.serviceBorderWidth),
					font = namefont, flags = namefontflag,
					text = str(channel),
					color = serviceForeColor, color_sel = serviceForeColor,
					backcolor = serviceBackColor, backcolor_sel = serviceBackColor))

		if self.showServiceTitle: # we have more space so reset parms
			namefont = 0
			namefontflag = int(config.epgselection.graph_servicename_alignment.value)
			namewidth = r1.w - channelWidth - piconWidth

		if self.showServiceTitle or displayPicon is None:
			res.append(MultiContentEntryText(
				pos = (r1.x + self.serviceNamePadding + piconWidth + self.serviceNamePadding + channelWidth + self.serviceNumberPadding,
					r1.y + self.serviceBorderWidth),
				size = (namewidth - 3 * (self.serviceBorderWidth + self.serviceNamePadding),
					r1.h - 2 * self.serviceBorderWidth),
				font = namefont, flags = namefontflag,
				text = service_name,
				color = serviceForeColor, color_sel = serviceForeColor,
				backcolor = serviceBackColor, backcolor_sel = serviceBackColor))

		# Service Borders
		if self.borderTopPix is not None and self.graphic:
			res.append(MultiContentEntryPixmapAlphaTest(
					pos = (r1.x, r1.y),
					size = (r1.w, self.serviceBorderWidth),
					png = self.borderTopPix,
					flags = BT_SCALE))
			res.append(MultiContentEntryPixmapAlphaTest(
					pos = (r2.x, r2.y),
					size = (r2.w, self.eventBorderWidth),
					png = self.borderTopPix,
					flags = BT_SCALE))
		if self.borderBottomPix is not None and self.graphic:
			res.append(MultiContentEntryPixmapAlphaTest(
					pos = (r1.x, r1.h-self.serviceBorderWidth),
					size = (r1.w, self.serviceBorderWidth),
					png = self.borderBottomPix,
					flags = BT_SCALE))
			res.append(MultiContentEntryPixmapAlphaTest(
					pos = (r2.x, r2.h-self.eventBorderWidth),
					size = (r2.w, self.eventBorderWidth),
					png = self.borderBottomPix,
					flags = BT_SCALE))
		if self.borderLeftPix is not None and self.graphic:
			res.append(MultiContentEntryPixmapAlphaTest(
					pos = (r1.x, r1.y),
					size = (self.serviceBorderWidth, r1.h),
					png = self.borderLeftPix,
					flags = BT_SCALE))
			res.append(MultiContentEntryPixmapAlphaTest(
					pos = (r2.x, r2.y),
					size = (self.eventBorderWidth, r2.h),
					png = self.borderLeftPix,
					flags = BT_SCALE))
		if self.borderRightPix is not None and self.graphic:
			res.append(MultiContentEntryPixmapAlphaTest(
					pos = (r1.w-self.serviceBorderWidth, r1.x),
					size = (self.serviceBorderWidth, r1.h),
					png = self.borderRightPix,
					flags = BT_SCALE))
			res.append(MultiContentEntryPixmapAlphaTest(
					pos = (r2.x + r2.w-self.eventBorderWidth, r2.y),
					size = (self.eventBorderWidth, r2.h),
					png = self.borderRightPix,
					flags = BT_SCALE))

		if self.graphic:
			if not selected and self.othEvPix:
				res.append(MultiContentEntryPixmapAlphaTest(
					pos = (r2.x + self.eventBorderWidth, r2.y + self.eventBorderWidth),
					size = (r2.w - 2 * self.eventBorderWidth, r2.h - 2 * self.eventBorderWidth),
					png = self.othEvPix,
					flags = BT_SCALE))
			elif selected and self.selEvPix:
				res.append(MultiContentEntryPixmapAlphaTest(
					pos = (r2.x + self.eventBorderWidth, r2.y + self.eventBorderWidth),
					size = (r2.w - 2 * self.eventBorderWidth, r2.h - 2 * self.eventBorderWidth),
					png = self.selEvPix,
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
				xpos, ewidth = self.calcEntryPosAndWidthHelper(stime, duration, start, end, width)
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
				elif stime <= now < (stime + duration) and config.epgselection.graph_highlight_current_events.value:
					foreColor = self.foreColorNow
					backColor = self.backColorNow
					foreColorSel = self.foreColorNowSelected
					backColorSel = self.backColorNowSelected

				if selected and self.select_rect.x == xpos + left:
					if clock_types is not None:
						clocks = self.selclocks[clock_types]
					borderTopPix = self.borderSelectedTopPix
					borderLeftPix = self.borderSelectedLeftPix
					borderBottomPix = self.borderSelectedBottomPix
					borderRightPix = self.borderSelectedRightPix
					infoPix = self.selInfoPix
					if stime <= now < (stime + duration) and config.epgselection.graph_highlight_current_events.value:
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
					elif stime <= now < (stime + duration) and config.epgselection.graph_highlight_current_events.value:
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
				if self.type == EPG_TYPE_GRAPH:
					infowidth = config.epgselection.graph_infowidth.value
				elif self.type == EPG_TYPE_INFOBARGRAPH:
					infowidth = config.epgselection.infobar_infowidth.value
				if evW < infowidth and infoPix is not None:
					res.append(MultiContentEntryPixmapAlphaBlend(
						pos = (evX, evY), size = (evW, evH),
						png = infoPix))
				else:
					res.append(MultiContentEntryText(
						pos = (evX, evY), size = (evW, evH),
						font = 1, flags = int(config.epgselection.graph_event_alignment.value),
						text = ev[1],
						color = foreColor, color_sel = foreColorSel,
						backcolor = backColor, backcolor_sel = backColorSel))

				# event box borders
				if borderTopPix is not None and self.graphic:
					res.append(MultiContentEntryPixmapAlphaTest(
							pos = (left + xpos, top),
							size = (ewidth, self.eventBorderWidth),
							png = borderTopPix,
							flags = BT_SCALE))
				if borderBottomPix is not None and self.graphic:
					res.append(MultiContentEntryPixmapAlphaTest(
							pos = (left + xpos, height-self.eventBorderWidth),
							size = (ewidth, self.eventBorderWidth),
							png = borderBottomPix,
							flags = BT_SCALE))
				if borderLeftPix is not None and self.graphic:
					res.append(MultiContentEntryPixmapAlphaTest(
							pos = (left + xpos, top),
							size = (self.eventBorderWidth, height),
							png = borderLeftPix,
							flags = BT_SCALE))
				if borderRightPix is not None and self.graphic:
					res.append(MultiContentEntryPixmapAlphaTest(
							pos = (left + xpos + ewidth-self.eventBorderWidth, top),
							size = (self.eventBorderWidth, height),
							png = borderRightPix,
							flags = BT_SCALE))

				# recording icons
				if clock_types is not None and ewidth > 23:
					if config.epgselection.graph_rec_icon_height.value != "hide":
						if config.epgselection.graph_rec_icon_height.value == "middle":
							RecIconHDheight = top+(height/2)-11
							RecIconFHDheight = top+(height/2)-13
						elif config.epgselection.graph_rec_icon_height.value == "top":
							RecIconHDheight = top+3
							RecIconFHDheight = top+3
						else:
							RecIconHDheight = top+height-22
							RecIconFHDheight = top+height-26
						if clock_types in (1,6,11):
							if self.screenwidth and self.screenwidth == 1920:
								pos = (left+xpos+ewidth-15, RecIconFHDheight)
							else:
								pos = (left+xpos+ewidth-13, RecIconHDheight)
						elif clock_types in (5,10,15):
							if self.screenwidth and self.screenwidth == 1920:
								pos = (left+xpos-26, RecIconFHDheight)
							else:
								pos = (left+xpos-22, RecIconHDheight)
						else:
							if self.screenwidth and self.screenwidth == 1920:
								pos = (left+xpos+ewidth-26, RecIconFHDheight)
							else:
								pos = (left+xpos+ewidth-22, RecIconHDheight)
						if self.screenwidth and self.screenwidth == 1920:
							res.append(MultiContentEntryPixmapAlphaBlend(
								pos = pos, size = (25, 25),
								png = clocks))
						else:
							res.append(MultiContentEntryPixmapAlphaBlend(
								pos = pos, size = (21, 21),
								png = clocks))
						if self.wasEntryAutoTimer and clock_types in (2,7,12):
							if self.screenwidth and self.screenwidth == 1920:
								res.append(MultiContentEntryPixmapAlphaBlend(
									pos = (pos[0]-25,pos[1]), size = (25, 25),
									png = self.autotimericon))
							else:
								res.append(MultiContentEntryPixmapAlphaBlend(
									pos = (pos[0]-21,pos[1]), size = (21, 21),
									png = self.autotimericon))
		return res

	def getSelectionPosition(self,serviceref):

		if self.type == EPG_TYPE_GRAPH:
			selx = self.select_rect.x+self.select_rect.w
			itemsperpage = config.epgselection.graph_itemsperpage.value
		elif self.type == EPG_TYPE_INFOBARGRAPH:
			selx = self.select_rect.x+self.select_rect.w
			itemsperpage = config.epgselection.infobar_itemsperpage.value
		elif self.type == EPG_TYPE_ENHANCED or self.type == EPG_TYPE_SINGLE or self.type == EPG_TYPE_SIMILAR:
			selx = self.listWidth
			itemsperpage = config.epgselection.enhanced_itemsperpage.value
		elif self.type == EPG_TYPE_MULTI:
			selx = self.listWidth
			itemsperpage = config.epgselection.multi_itemsperpage.value
		elif self.type == EPG_TYPE_INFOBAR:
			selx = self.listWidth
			itemsperpage = config.epgselection.infobar_itemsperpage.value

# Adjust absolute indx to indx in displayed view
#
		indx = int(self.l.getCurrentSelectionIndex())
		while indx+1 > itemsperpage:
			indx = indx - itemsperpage
		pos = self.instance.position().y()
		sely = int(pos)+(int(self.itemHeight)*int(indx))
		temp = int(self.instance.position().y())+int(self.listHeight)
		if int(sely) >= temp:
			sely = int(sely) - int(self.listHeight)
		return int(selx), int(sely)

# This method function is a little odd...
# When it is called with a non-zero dir it runs through the code in the
# dir != 0 part (at the top).  If this results in it moving screen-page
# that code calls fillGraphEPG()/fillGraphEPGNoRefresh(), which makes a
# call back here with dir=0, so the rest of the code gets run.
#
	def selEntry(self, dir, visible = True):
		cur_service = self.cur_service    #(service, service_name, events, picon)
		self.recalcEntrySize()
		valid_event = self.cur_event is not None
		if cur_service:
			update = True
			entries = cur_service[2]

			abs_time_focus = None
			if dir == 0: #current
				update = False

			elif (dir > 0): # Move forward
				if dir == +1:   # Next event
					if valid_event and self.cur_event + 1 < len(entries):
						self.setTimeFocusFromEvent(self.cur_event + 1)
						self.l.invalidateEntry(self.l.getCurrentSelectionIndex())
						return False    # Same page
# Next event is on next page, so we need to move to it
					incr = self.time_epoch_secs
					fevent = 0
					norefresh = True
				elif dir == +2: # Next page
					incr = self.time_epoch_secs
					fevent = None
					norefresh = False
				elif dir == +24: # Next day
					incr = 86400
					fevent = None
					norefresh = False
			else:           # Move back (dir < 0)
				if dir == -1:   # Prev event
					if valid_event and self.cur_event - 1 >= 0:
						self.setTimeFocusFromEvent(self.cur_event - 1)
						self.l.invalidateEntry(self.l.getCurrentSelectionIndex())
						return False    # Same page
# Prev event is on prev page, so move to it iff it exists
# It won't exists if time_base is less than time()
					if time() > self.time_base:
						return False    # Nothing to do
					incr = -self.time_epoch_secs
					fevent = 65535
					norefresh = True
				else:           # Prev page or Prev day
					fevent = None
					norefresh = False
					if dir == -2: # Prev page
						target = self.time_base - self.time_epoch_secs
					else:         # Prev day
						target = self.time_base - 86400
# Work out the earliest we can go back to
					abs0 = int(time() - int(config.epg.histminutes.value) * SECS_IN_MIN)
					abs0 = abs0 - abs0 % self.round_by_secs
					if target >= abs0:
						incr = target - self.time_base
					else:
						incr = abs0 - self.time_base
# If we go back to square one with prev page/day then set the focus on
# now, rather than start of page
						abs_time_focus = time()
# If we are still here and moving - do the move now and return True to
# indicate we've changed pages
#
			if dir != 0:
				self.time_base += incr
				if abs_time_focus:
					self.time_focus = abs_time_focus
				else:
					self.time_focus += incr
				if norefresh:
					self.fillGraphEPGNoRefresh()
				else:
					self.fillGraphEPG(None)
				if fevent != None:
					self.setTimeFocusFromEvent(fevent)
				return True

		if cur_service and valid_event and (self.cur_event+1 <= len(entries)):
			entry = entries[self.cur_event] #(event_id, event_title, begin_time, duration)
			xpos, width = self.calcEntryPosAndWidth(self.event_rect, self.time_base, self.time_epoch_secs, entry[2], entry[3])
			self.select_rect = Rect(xpos ,0, width, self.event_rect.height)
			self.l.setSelectionClip(eRect(xpos, 0, width, self.event_rect.h), visible and update)
		else:
			self.select_rect = self.event_rect
			self.l.setSelectionClip(eRect(self.event_rect.x, self.event_rect.y, self.event_rect.w, self.event_rect.h), False)
		self.selectionChanged()
		return False

	def queryEPG(self, list, buildFunc=None):
		if self.epgcache is not None:
			if buildFunc is not None:
				return self.epgcache.lookupEvent(list, buildFunc)
			else:
				return self.epgcache.lookupEvent(list)
		return [ ]

	def fillSimilarList(self, refstr, event_id):
		# search similar broadcastings
		t = time()
		if event_id is None:
			return
		self.list = self.epgcache.search(('RIBND', 1024, eEPGCache.SIMILAR_BROADCASTINGS_SEARCH, refstr, event_id))
		if self.list and len(self.list):
			self.list.sort(key=lambda x: x[2])
		self.l.setList(self.list)
		self.recalcEntrySize()
		self.selectionChanged()

	def fillSingleEPG(self, service):
		t = time()
		epg_time = t - config.epg.histminutes.value*SECS_IN_MIN
		test = [ 'RIBDT', (service.ref.toString(), 0, epg_time, -1) ]
		self.list = self.queryEPG(test)
		# Add explicit gaps if data isn't available.
		for i in range(len(self.list) - 1, 0, -1):
			this_beg = self.list[i][2]
			prev_end = self.list[i-1][2] + self.list[i-1][3]
			if prev_end + 5 * SECS_IN_MIN < this_beg:
				self.list.insert(i, (self.list[i][0], None, prev_end, this_beg - prev_end, None))
		self.l.setList(self.list)
		self.recalcEntrySize()
		if t != epg_time:
			idx = 0
			for x in self.list:
				idx += 1
				if t < x[2]+x[3]:
					break
			self.instance.moveSelectionTo(idx-1)
		self.selectionChanged()

	def fillMultiEPG(self, services, stime=None):
		test = [ (service.ref.toString(), 0, stime) for service in services ]
		test.insert(0, 'X0RIBDTCn')
		self.list = self.queryEPG(test)
		self.l.setList(self.list)
		self.recalcEntrySize()
		self.selectionChanged()

	def updateMultiEPG(self, direction):
		test = [ x[3] and (x[1], direction, x[3]) or (x[1], direction, 0) for x in self.list ]
		test.insert(0, 'XRIBDTCn')
		epg_data = self.queryEPG(test)
		cnt = 0
		for x in epg_data:
			changecount = self.list[cnt][0] + direction
			if changecount >= 0:
				if x[2] is not None:
					self.list[cnt] = (changecount, x[0], x[1], x[2], x[3], x[4], x[5], x[6])
			cnt+=1
		self.l.setList(self.list)
		self.recalcEntrySize()
		self.selectionChanged()

	def getCurrentCursorLocation(self):
		return self.time_base

	def fillGraphEPG(self, services, stime = None):
		self.fillGraphEPGNoRefresh(services, stime)
		self.selEntry(0)

	def fillGraphEPGNoRefresh(self, services = None, stime = None):
		if (self.type == EPG_TYPE_GRAPH or self.type == EPG_TYPE_INFOBARGRAPH) and not self.graphicsloaded:
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

		if stime is not None:
			self.time_base = int(stime)
		if services is None:
			test = [ (service[0], 0, self.time_base, self.time_epoch) for service in self.list ]
			serviceList = self.list
			piconIdx = 3
			channelIdx = 4
		else:
			self.cur_event = None
			self.cur_service = None
			test = [ (service.ref.toString(), 0, self.time_base, self.time_epoch) for service in services ]
			serviceList = services
			piconIdx = 0
			channelIdx = None

		test.insert(0, 'XRnITBD') #return record, service ref, service name, event id, event title, begin time, duration
		epg_data = self.queryEPG(test)
		self.list = [ ]
		tmp_list = None
		service = ""
		sname = ""

		serviceIdx = 0
		for x in epg_data:
			if service != x[0]:
				if tmp_list is not None:
					picon = None if piconIdx == 0 else serviceList[serviceIdx][piconIdx]
					# We pass the serviceref if we don't have the channel number yet, so it can be grabbed
					channel = serviceList[serviceIdx] if (channelIdx == None) else serviceList[serviceIdx][channelIdx]
					self.list.append((service, sname, tmp_list[0][0] is not None and tmp_list or None, picon, channel))
					serviceIdx += 1
				service = x[0]
				sname = x[1]
				tmp_list = [ ]
			tmp_list.append((x[2], x[3], x[4], x[5])) #(event_id, event_title, begin_time, duration)
		if tmp_list and len(tmp_list):
			picon = None if piconIdx == 0 else serviceList[serviceIdx][piconIdx]
			channel = serviceList[serviceIdx] if (channelIdx == None) else serviceList[serviceIdx][channelIdx]
			self.list.append((service, sname, tmp_list[0][0] is not None and tmp_list or None, picon, channel))
			serviceIdx += 1

		self.l.setList(self.list)
		self.recalcEntrySize()
		self.selectEventFromTime()

	def sortSingleEPG(self, type):
		list = self.list
		if list:
			event_id = self.getSelectedEventId()
			if type == 1:
				list.sort(key=lambda x: (x[4] and x[4].lower(), x[2]))
			else:
				assert(type == 0)
				list.sort(key=lambda x: x[2])
			self.l.invalidate()
			self.moveToEventId(event_id)

	def getChannelNumber(self,service):
		if hasattr(service, "ref") and service.ref and '0:0:0:0:0:0:0:0:0' not in service.ref.toString():
			numservice = service.ref
			num = numservice and numservice.getChannelNum() or None
			if num is not None:
				return num
		return None

	def getEventRect(self):
		rc = self.event_rect
		return Rect( rc.left() + (self.instance and self.instance.position().x() or 0), rc.top(), rc.width(), rc.height() )

	def getServiceRect(self):
		rc = self.service_rect
		return Rect( rc.left() + (self.instance and self.instance.position().x() or 0), rc.top(), rc.width(), rc.height() )

	def getTimeBase(self):
		return self.time_base

# This used to set the (now gone) self.offs = 0
# Can be removed at some future time.
	def resetOffset(self):
		pass

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

class TimelineText(GUIComponent):
	def __init__(self, type = EPG_TYPE_GRAPH, graphic=False):
		GUIComponent.__init__(self)
		self.type = type
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
		if self.type == EPG_TYPE_GRAPH:
			font_conf= config.epgselection.graph_timelinefs.value
		elif self.type == EPG_TYPE_INFOBARGRAPH:
			font_conf = config.epgselection.infobar_timelinefs.value
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
				font = 0, flags = int(config.epgselection.graph_timelinedate_alignment.value),
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
					if (self.type == EPG_TYPE_GRAPH and config.epgselection.graph_timeline24h.value) or (self.type == EPG_TYPE_INFOBARGRAPH and config.epgselection.infobar_timeline24h.value):
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

class EPGBouquetList(GUIComponent):
	def __init__(self, graphic=False):
		GUIComponent.__init__(self)
		self.graphic = graphic
		self.l = eListboxPythonMultiContent()
		self.l.setBuildFunc(self.buildEntry)

		self.onSelChanged = [ ]

		self.foreColor = 0xffffff
		self.foreColorSelected = 0xffffff
		self.backColor = 0x2D455E
		self.backColorSelected = 0xd69600

		self.borderColor = 0xC0C0C0
		self.BorderWidth = 1

		self.othPix = None
		self.selPix = None
		self.graphicsloaded = False

		self.bouquetFontName = "Regular"
		self.bouquetFontSize = 20

		self.itemHeight = 31
		self.listHeight = None
		self.listWidth = None

		self.bouquetNamePadding = 3
		self.bouquetNameAlign = 'left'
		self.bouquetNameWrap = 'no'

	def applySkin(self, desktop, screen):
		if self.skinAttributes is not None:
			attribs = [ ]
			for (attrib, value) in self.skinAttributes:
				if attrib == "font":
					font = parseFont(value, ((1,1),(1,1)) )
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
					self.BorderWidth = int(value)
				elif attrib == "itemHeight":
					self.itemHeight = int(value)
				else:
					attribs.append((attrib,value))
			self.skinAttributes = attribs
		rc = GUIComponent.applySkin(self, desktop, screen)
		self.setBouquetFontsize()
		self.listHeight = self.instance.size().height()
		self.listWidth = self.instance.size().width()
		self.l.setItemHeight(self.itemHeight)
		return rc

	GUI_WIDGET = eListbox

	def getCurrentBouquet(self):
		return self.l.getCurrentSelection()[0]

	def getCurrentBouquetService(self):
		return self.l.getCurrentSelection()[1]

	def setCurrentBouquet(self, CurrentBouquetService):
		self.CurrentBouquetService = CurrentBouquetService

	def selectionChanged(self):
		for x in self.onSelChanged:
			if x is not None:
				x()

	def getIndexFromService(self, serviceref):
		if serviceref is not None:
			for x in range(len(self.bouquetslist)):
				if CompareWithAlternatives(self.bouquetslist[x][1].toString(), serviceref.toString()):
					return x
		return None

	def moveToService(self, serviceref):
		newIdx = self.getIndexFromService(serviceref)
		if newIdx is None:
			newIdx = 0
		self.setCurrentIndex(newIdx)

	def setCurrentIndex(self, index):
		if self.instance is not None:
			self.instance.moveSelectionTo(index)

	def moveTo(self, dir):
		if self.instance is not None:
			self.instance.moveSelection(dir)

	def setBouquetFontsize(self):
		self.l.setFont(0, gFont(self.bouquetFontName, self.bouquetFontSize))

	def postWidgetCreate(self, instance):
		self.l.setSelectableFunc(True)
		instance.setWrapAround(True)
		instance.selectionChanged.get().append(self.selectionChanged)
		instance.setContent(self.l)
		# self.l.setSelectionClip(eRect(0,0,0,0), False)
		self.setBouquetFontsize()

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
		self.bouquet_rect = Rect(0, 0, width, height)

	def getBouquetRect(self):
		rc = self.bouquet_rect
		return Rect( rc.left() + (self.instance and self.instance.position().x() or 0), rc.top(), rc.width(), rc.height() )

	def buildEntry(self, name, func):
		r1 = self.bouquet_rect
		left = r1.x
		top = r1.y
		# width = (len(name)+5)*8
		width = r1.w
		height = r1.h
		selected = self.CurrentBouquetService == func

		if self.bouquetNameAlign.lower() == 'left':
			if self.bouquetNameWrap.lower() == 'yes':
				alignnment = RT_HALIGN_LEFT | RT_VALIGN_CENTER | RT_WRAP
			else:
				alignnment = RT_HALIGN_LEFT | RT_VALIGN_CENTER
		else:
			if self.bouquetNameWrap.lower() == 'yes':
				alignnment = RT_HALIGN_CENTER | RT_VALIGN_CENTER | RT_WRAP
			else:
				alignnment = RT_HALIGN_CENTER | RT_VALIGN_CENTER

		res = [ None ]

		if selected:
			if self.graphic:
				borderTopPix = self.borderSelectedTopPix
				borderLeftPix = self.borderSelectedLeftPix
				borderBottomPix = self.borderSelectedBottomPix
				borderRightPix = self.borderSelectedRightPix
			foreColor = self.foreColor
			backColor = self.backColor
			foreColorSel = self.foreColorSelected
			backColorSel = self.backColorSelected
			bgpng = self.selPix
			if bgpng is not None and self.graphic:
				backColor = None
				backColorSel = None
		else:
			if self.graphic:
				borderTopPix = self.borderTopPix
				borderLeftPix = self.borderLeftPix
				borderBottomPix = self.borderBottomPix
				borderRightPix = self.borderRightPix
			backColor = self.backColor
			foreColor = self.foreColor
			foreColorSel = self.foreColorSelected
			backColorSel = self.backColorSelected
			bgpng = self.othPix
			if bgpng is not None and self.graphic:
				backColor = None
				backColorSel = None

		# box background
		if bgpng is not None and self.graphic:
			res.append(MultiContentEntryPixmapAlphaTest(
				pos = (left + self.BorderWidth, top + self.BorderWidth),
				size = (width - 2 * self.BorderWidth, height - 2 * self.BorderWidth),
				png = bgpng,
				flags = BT_SCALE))
		else:
			res.append(MultiContentEntryText(
				pos = (left , top), size = (width, height),
				font = 0, flags = RT_HALIGN_LEFT | RT_VALIGN_CENTER,
				text = "", color = None, color_sel = None,
				backcolor = backColor, backcolor_sel = backColorSel,
				border_width = self.BorderWidth, border_color = self.borderColor))

		evX = left + self.BorderWidth + self.bouquetNamePadding
		evY = top + self.BorderWidth
		evW = width - 2 * (self.BorderWidth + self.bouquetNamePadding)
		evH = height - 2 * self.BorderWidth

		res.append(MultiContentEntryText(
			pos = (evX, evY), size = (evW, evH),
			font = 0, flags = alignnment,
			text = name,
			color = foreColor, color_sel = foreColorSel,
			backcolor = backColor, backcolor_sel = backColorSel))

		# Borders
		if self.graphic:
			if borderTopPix is not None:
				res.append(MultiContentEntryPixmapAlphaTest(
						pos = (left, r1.y),
						size = (r1.w, self.BorderWidth),
						png = borderTopPix,
						flags = BT_SCALE))
			if borderBottomPix is not None:
				res.append(MultiContentEntryPixmapAlphaTest(
						pos = (left, r1.h-self.BorderWidth),
						size = (r1.w, self.BorderWidth),
						png = borderBottomPix,
						flags = BT_SCALE))
			if borderLeftPix is not None:
				res.append(MultiContentEntryPixmapAlphaTest(
						pos = (left, r1.y),
						size = (self.BorderWidth, r1.h),
						png = borderLeftPix,
						flags = BT_SCALE))
			if borderRightPix is not None:
				res.append(MultiContentEntryPixmapAlphaTest(
						pos = (r1.w-self.BorderWidth, left),
						size = (self.BorderWidth, r1.h),
						png = borderRightPix,
						flags = BT_SCALE))

		return res

	def fillBouquetList(self, bouquets):
		if self.graphic and not self.graphicsloaded:
			self.othPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/OtherEvent.png'))
			self.selPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/SelectedCurrentEvent.png'))

			self.borderTopPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/BorderTop.png'))
			self.borderBottomPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/BorderLeft.png'))
			self.borderLeftPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/BorderBottom.png'))
			self.borderRightPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/BorderRight.png'))
			self.borderSelectedTopPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/SelectedBorderTop.png'))
			self.borderSelectedLeftPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/SelectedBorderLeft.png'))
			self.borderSelectedBottomPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/SelectedBorderBottom.png'))
			self.borderSelectedRightPix = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'epg/SelectedBorderRight.png'))

			self.graphicsloaded = True
		self.bouquetslist = bouquets
		self.l.setList(self.bouquetslist)
		self.recalcEntrySize()
		self.selectionChanged()
		self.CurrentBouquetService = self.getCurrentBouquetService()
