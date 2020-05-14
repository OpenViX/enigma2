from time import localtime, strftime, time

from enigma import eTimer

from Components.ActionMap import HelpableActionMap
from Components.config import config
from Components.EpgListMulti import EPGListMulti
from Components.Label import Label
from Components.Pixmap import Pixmap
from Screens.EpgSelectionBase import EPGBouquetSelection, EPGSelectionBase, EPGServiceZap
from Screens.Setup import Setup


class EPGSelectionMulti(EPGSelectionBase, EPGBouquetSelection, EPGServiceZap):
	def __init__(self, session, zapFunc, startBouquet, startRef, bouquets):
		EPGSelectionBase.__init__(self, session, config.epgselection.multi, startBouquet, startRef, bouquets)
		EPGBouquetSelection.__init__(self, False)
		EPGServiceZap.__init__(self, zapFunc)
		self.skinName = ["MultiEPG", "EPGSelectionMulti"]
		self.askTime = -1

		self["now_button"] = Pixmap()
		self["next_button"] = Pixmap()
		self["more_button"] = Pixmap()
		self["now_button_sel"] = Pixmap()
		self["next_button_sel"] = Pixmap()
		self["more_button_sel"] = Pixmap()
		self["now_text"] = Label()
		self["next_text"] = Label()
		self["more_text"] = Label()
		self["date"] = Label()

		helpDescription = _("EPG Commands")
		self["epgcursoractions"] = HelpableActionMap(self, "DirectionActions", {
			"left": (self.leftPressed, _("Go to previous event")),
			"right": (self.rightPressed, _("Go to next event")),
			"up": (self.moveUp, _("Go to previous channel")),
			"down": (self.moveDown, _("Go to next channel"))
		}, prio=-1, description=helpDescription)
		self["epgactions"] = HelpableActionMap(self, "EPGSelectActions", {
			"nextService": (self.nextPage, _("Move down a page")),
			"prevService": (self.prevPage, _("Move up a page")),
			"nextBouquet": (self.nextBouquet, _("Go to next bouquet")),
			"prevBouquet": (self.prevBouquet, _("Go to previous bouquet")),
			"input_date_time": (self.enterDateTime, _("Go to specific data/time")),
			"epg": (self.openSingleEPG, _("Show single epg for current channel")),
			"info": (self.openEventView, _("Show detailed event info")),
			"infolong": (self.openSingleEPG, _("Show single epg for current channel")),
			"tv": (self.toggleBouquetList, _("Toggle between bouquet/epg lists")),
			"timer": (self.openTimerList, _("Show timer list")),
			"timerlong": (self.openAutoTimerList, _("Show autotimer list")),
			"menu": (self.createSetup, _("Setup menu"))
		}, prio=-1, description=helpDescription)

		self["list"] = EPGListMulti(session, selChangedCB=self.onSelectionChanged)

	def createSetup(self):
		def onClose(test=None):
			self["list"].setFontsize()
			self["list"].setItemsPerPage()
			self["list"].recalcEntrySize()

		self.closeEventViewDialog()
		self.session.openWithCallback(onClose, Setup, "epgmulti")

	def onCreate(self):
		self["list"].recalcEntrySize()
		self["lab1"].show()
		self.show()
		self.listTimer = eTimer()
		self.listTimer.callback.append(self.loadEPGData)
		self.listTimer.start(1, True)

	def loadEPGData(self):
		self._populateBouquetList()
		self.setTitle(self.getCurrentBouquetName())
		self["list"].fillEPG(self.services, self.askTime)
		if self.epgConfig.browse_mode.value != "firstservice":
			self["list"].moveToService(self.startRef)
		self["lab1"].hide()

	def refreshList(self):
		self.refreshTimer.stop()
		self["list"].updateEPG(0)

	def leftPressed(self):
		self["list"].updateEPG(-1)

	def rightPressed(self):
		self["list"].updateEPG(1)

	def bouquetChanged(self):
		self.setTitle(self.getCurrentBouquetName())
		self["list"].fillEPG(self.services, self.askTime)
		self["list"].instance.moveSelectionTo(0)

	def getCurrentService(self):
		service = self["list"].getCurrent()[1]
		return service

	def onDateTimeInputClosed(self, ret):
		if len(ret) > 1 and ret[0]:
			self.askTime = ret[1]
			self["list"].fillEPG(self.services, self.askTime)

	def eventViewCallback(self, setEvent, setService, val):
		list = self["list"]
		old = list.getCurrent()
		if val == -1:
			self.moveUp()
		elif val == +1:
			self.moveDown()
		cur = list.getCurrent()
		if cur[0] is None and cur[1].ref != old[1].ref:
			self.eventViewCallback(setEvent, setService, val)
		else:
			setService(cur[1])
			setEvent(cur[0])

	def applyButtonState(self, state):
		if state == 0:
			self["now_button"].hide()
			self["now_button_sel"].hide()
			self["next_button"].hide()
			self["next_button_sel"].hide()
			self["more_button"].hide()
			self["more_button_sel"].hide()
			self["now_text"].hide()
			self["next_text"].hide()
			self["more_text"].hide()
			self["key_red"].setText("")
		else:
			if state == 1:
				self["now_button_sel"].show()
				self["now_button"].hide()
			else:
				self["now_button"].show()
				self["now_button_sel"].hide()
			if state == 2:
				self["next_button_sel"].show()
				self["next_button"].hide()
			else:
				self["next_button"].show()
				self["next_button_sel"].hide()
			if state == 3:
				self["more_button_sel"].show()
				self["more_button"].hide()
			else:
				self["more_button"].show()
				self["more_button_sel"].hide()

	def onSelectionChanged(self):
		count = self["list"].getCurrentChangeCount()
		if self.askTime != -1:
			self.applyButtonState(0)
		elif count > 1:
			self.applyButtonState(3)
		elif count > 0:
			self.applyButtonState(2)
		else:
			self.applyButtonState(1)
		datestr = ""
		cur = self["list"].getCurrent()
		event = cur[0]
		if event is not None:
			now = time()
			beg = event.getBeginTime()
			nowTime = localtime(now)
			begTime = localtime(beg)
			if nowTime[2] != begTime[2]:
				datestr = strftime(config.usage.date.dayshort.value, begTime)
			else:
				datestr = _("Today")
		self["date"].setText(datestr)
		EPGSelectionBase.onSelectionChanged(self)
