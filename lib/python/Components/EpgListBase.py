import skin
from time import localtime, time, strftime

from enigma import eEPGCache, eListbox, eListboxPythonMultiContent, loadPNG, gFont, getDesktop, eRect, eSize, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, RT_VALIGN_CENTER, RT_VALIGN_TOP, RT_WRAP, BT_SCALE, BT_KEEP_ASPECT_RATIO, BT_ALIGN_CENTER

from Components.GUIComponent import GUIComponent
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmapAlphaBlend, MultiContentEntryPixmapAlphaTest
from Components.Renderer.Picon import getPiconName
from skin import parseColor, parseFont
from Tools.Alternatives import CompareWithAlternatives
from ServiceReference import ServiceReference
from Tools.Directories import resolveFilename, SCOPE_ACTIVE_SKIN
from Tools.TextBoundary import getTextBoundarySize

class EPGListBase(GUIComponent):
	def __init__(self, selChangedCB = None, timer = None):
		GUIComponent.__init__(self)

		self.timer = timer
		self.onSelChanged = [ ]
		if selChangedCB is not None:
			self.onSelChanged.append(selChangedCB)
		self.l = eListboxPythonMultiContent()

		self.epgcache = eEPGCache.getInstance()

		# Common clock icons
		add = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_add.png'))
		pre = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_pre.png'))
		clock = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock.png'))
		zap = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_zap.png'))
		zaprec = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_zaprec.png'))
		prepost = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_prepost.png'))
		post = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_post.png'))
		self.clocks = [
			add, pre, clock, prepost, post,
			add, pre, zap, prepost, post,
			add, pre, zaprec, prepost, post,
			add, pre, clock, prepost, post]

		# Common selected clock icons
		pre = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_selpre.png'))
		prepost = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_selprepost.png'))
		post = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_selpost.png'))
		self.selclocks = [
			add, pre, clock, prepost, post,
			add, pre, zap, prepost, post,
			add, pre, zaprec, prepost, post]

		self.autotimericon = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, 'icons/epgclock_autotimer.png'))

		self.screenwidth = getDesktop(0).size().width()

		self.listHeight = None
		self.listWidth = None
		self.numberOfRows = None

	def applySkin(self, desktop, screen):
		if self.skinAttributes is not None:
			attribs = [ ]
			for (attrib, value) in self.skinAttributes:
				if attrib == "NumberOfRows":
					self.numberOfRows = int(value)
				else:
					attribs.append((attrib,value))
			self.skinAttributes = attribs
		rc = GUIComponent.applySkin(self, desktop, screen)
		self.listHeight = self.instance.size().height()
		self.listWidth = self.instance.size().width()
		self.setFontsize()

		return rc

	def getEventFromId(self, service, eventid):
		event = None
		if self.epgcache is not None and eventid is not None:
			event = self.epgcache.lookupEventId(service.ref, eventid)
		return event

	def getIndexFromService(self, serviceref):
		if serviceref is not None:
			for x in range(len(self.list)):
				if CompareWithAlternatives(self.list[x][0], serviceref):
					return x
				if CompareWithAlternatives(self.list[x][1], serviceref):
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
		tmp = self.l.getCurrentSelection()
		if tmp is None:
			return None, None
		service = ServiceReference(tmp[0])
		eventid = tmp[1]
		event = self.getEventFromId(service, eventid)
		return event, service

	def connectSelectionChanged(func):
		if not self.onSelChanged.count(func):
			self.onSelChanged.append(func)

	def disconnectSelectionChanged(func):
		self.onSelChanged.remove(func)

	def selectionChanged(self):
		for x in self.onSelChanged:
			if x is not None:
				x()

	GUI_WIDGET = eListbox

	def selectionEnabled(self, enabled):
		if self.instance is not None:
			self.instance.setSelectionEnable(enabled)

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

	def queryEPG(self, list):
		return self.epgcache.lookupEvent(list)
