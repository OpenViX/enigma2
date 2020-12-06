from enigma import eEPGCache, eListbox, eListboxPythonMultiContent, eServiceReference, loadPNG, getDesktop

from Components.GUIComponent import GUIComponent
from Tools.Alternatives import CompareWithAlternatives
from Tools.Directories import SCOPE_CURRENT_SKIN, resolveFilename


class EPGListBase(GUIComponent):
	def __init__(self, session, selChangedCB=None):
		GUIComponent.__init__(self)

		self.session = session
		self.onSelChanged = []
		if selChangedCB is not None:
			self.onSelChanged.append(selChangedCB)
		self.l = eListboxPythonMultiContent()
		self.epgcache = eEPGCache.getInstance()

		# Load the common clock icons.
		self.clocks = [
			loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "icons/epgclock_pre.png")),
			loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "icons/epgclock_post.png")),
			loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "icons/epgclock_prepost.png")),
			loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "icons/epgclock.png")),
			loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "icons/epgclock_zap.png")),
			loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "icons/epgclock_zaprec.png"))
		]
		self.selclocks = [
			loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "icons/epgclock_selpre.png")) or self.clocks[0],
			loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "icons/epgclock_selpost.png")) or self.clocks[1],
			loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "icons/epgclock_selprepost.png")) or self.clocks[2],
			self.clocks[3],
			self.clocks[4],
			self.clocks[5]
		]

		self.autotimericon = loadPNG(resolveFilename(SCOPE_CURRENT_SKIN, "icons/epgclock_autotimer.png"))

		self.isFullHd = getDesktop(0).size().width() == 1920
		self.listHeight = None
		self.listWidth = None
		self.numberOfRows = None

	def applySkin(self, desktop, screen):
		if self.skinAttributes is not None:
			attribs = []
			for (attrib, value) in self.skinAttributes:
				if attrib == "NumberOfRows":
					self.numberOfRows = int(value)
				else:
					attribs.append((attrib, value))
			self.skinAttributes = attribs
		rc = GUIComponent.applySkin(self, desktop, screen)
		self.listHeight = self.instance.size().height()
		self.listWidth = self.instance.size().width()
		self.setFontsize()
		self.setItemsPerPage()
		return rc

	def getEventFromId(self, service, eventId):
		event = None
		if self.epgcache is not None and eventId is not None:
			event = self.epgcache.lookupEventId(service.ref, eventId)
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
		service = eServiceReference(tmp[0])
		eventId = tmp[1]
		event = self.getEventFromId(service, eventId)
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

	def getPixmapsForTimer(self, timer, matchType, selected=False):
		if timer is None:
			return (None, None)
		autoTimerIcon = None
		if matchType == 3:
			# recording whole event, add timer type onto pixmap lookup index
			matchType += 2 if timer.always_zap else 1 if timer.justplay else 0
			autoTimerIcon = self.autotimericon if timer.isAutoTimer else None
		return self.selclocks[matchType] if selected else self.clocks[matchType], autoTimerIcon

	def queryEPG(self, list):
		return self.epgcache.lookupEvent(list)
