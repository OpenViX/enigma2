# -*- coding: utf-8 -*-
from time import localtime, strftime

from enigma import eEPGCache, eTimer, eServiceReference, ePoint

from Screens.Screen import Screen
from Screens.TimerEntry import TimerEntry, addTimerFromEvent
from Screens.ChoiceBox import ChoiceBox
from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.Label import Label
from Components.config import config
from Components.Sources.StaticText import StaticText
from Components.ScrollLabel import ScrollLabel
from Components.PluginComponent import plugins
from Components.MenuList import MenuList
from Components.Pixmap import Pixmap
from Components.Sources.ServiceEvent import ServiceEvent
from Components.Sources.Event import Event
from RecordTimer import AFTEREVENT
from Plugins.Plugin import PluginDescriptor
from Tools.BoundFunction import boundFunction


class EventViewContextMenu(Screen):
	def __init__(self, session, menu):
		Screen.__init__(self, session)
		self.setTitle(_('Event view menu'))

		self["description"] = StaticText()

		self["actions"] = ActionMap(["OkCancelActions"],
			{
				"ok": self.okbuttonClick,
				"cancel": self.cancelClick
			}  # noqa: E123
		)

		self["menu"] = MenuList(menu)
		if self.updateDescription not in self["menu"].onSelectionChanged:
			self["menu"].onSelectionChanged.append(self.updateDescription)
		self.updateDescription()

	def okbuttonClick(self):
		self["menu"].getCurrent() and self["menu"].getCurrent()[1]()

	def cancelClick(self):
		self.close(False)

	def updateDescription(self):
		current = self["menu"].getCurrent()
		self["description"].text = current and len(current) > 2 and hasattr(current[2], "description") and current[2].description or ""


class EventViewBase:
	def __init__(self, event, ref, callback=None, similarEPGCB=None):
		self.similarEPGCB = similarEPGCB
		self.cbFunc = callback
		self.currentService = ref
		self.isRecording = not ref.ref.flags & eServiceReference.isGroup and ref.ref.getPath() and "%3a//" not in ref.ref.toString()
		self.event = event
		self["Service"] = ServiceEvent()
		self["Event"] = Event()
		self["epg_eventname"] = ScrollLabel()
		self["epg_description"] = ScrollLabel()
		self["FullDescription"] = ScrollLabel()
		self["summary_description"] = StaticText()
		self["datetime"] = Label()
		self["channel"] = Label()
		self["duration"] = Label()
		if [p for p in plugins.getPlugins(PluginDescriptor.WHERE_EVENTINFO) if "servicelist" not in p.fnc.__code__.co_varnames]:
			self["key_menu"] = StaticText(_("MENU"))
		if similarEPGCB is not None:
			self["key_red"] = Button("")
			self.SimilarBroadcastTimer = eTimer()
			self.SimilarBroadcastTimer.callback.append(self.getSimilarEvents)
		else:
			self.SimilarBroadcastTimer = None
		self["actions"] = ActionMap(["OkCancelActions", "EventViewActions"],
			{
				"cancel": self.close,
				"ok": self.close,
				"pageUp": self.pageUp,
				"pageDown": self.pageDown,
				"prevEvent": self.prevEvent,
				"nextEvent": self.nextEvent,
				"contextMenu": self.doContext,
			})  # noqa: E123
		self["dialogactions"] = ActionMap(["WizardActions"],
			{
				"back": self.closeChoiceBoxDialog,
			}, -1  # noqa: E123
		)
		self['dialogactions'].csel = self
		self["dialogactions"].setEnabled(False)
		self.onLayoutFinish.append(self.onCreate)

	def onCreate(self):
		self.setService(self.currentService)
		self.setEvent(self.event)

	def prevEvent(self):
		if self.cbFunc is not None:  # noqa: E402
			self.cbFunc(self.setEvent, self.setService, -1)

	def nextEvent(self):
		if self.cbFunc is not None:
			self.cbFunc(self.setEvent, self.setService, +1)

	def removeTimer(self, timer):
		timer.afterEvent = AFTEREVENT.NONE
		self.session.nav.RecordTimer.removeEntry(timer)
		self.updateButtons()

	def updateButtons(self):
		if "key_green" in self:
			if self.isRecording or self.event is None:
				self["key_green"].setText("")
				return
			timer = self.session.nav.RecordTimer.getTimerForEvent(self.currentService, self.event)
			if timer is not None:
				self["key_green"].setText(_("Change Timer"))
			else:
				self["key_green"].setText(_("Add Timer"))

	def editTimer(self, timer):
		def callback(choice):
			self.updateButtons()
		self.session.openWithCallback(callback, TimerEntry, timer)

	def timerAdd(self):
		def callback(choice):
			if choice:
				choice(self)
			self.closeChoiceBoxDialog()

		if self.isRecording:
			return
		event = self.event
		if event is None:
			return
		timer = self.session.nav.RecordTimer.getTimerForEvent(self.currentService, event)
		if timer is not None:
			if "epgactions1" in self:
				self["epgactions1"].setEnabled(False)
			if "epgactions2" in self:
				self["epgactions2"].setEnabled(False)
			if "epgactions3" in self:
				self["epgactions3"].setEnabled(False)
			cb_func1 = lambda ret: self.removeTimer(timer)  # noqa: E731
			cb_func2 = lambda ret: self.editTimer(timer)  # noqa: E731
			menu = [(_("Delete Timer"), 'CALLFUNC', callback, cb_func1), (_("Edit Timer"), 'CALLFUNC', callback, cb_func2)]
			self.ChoiceBoxDialog = self.session.instantiateDialog(ChoiceBox, title=_("Select action for timer %s:") % event.getEventName(), list=menu, keys=['green', 'blue'], skin_name="RecordTimerQuestion")
			self.ChoiceBoxDialog.instance.move(ePoint(self.instance.position().x() + self["key_green"].getPosition()[0], self.instance.position().y() + self["key_green"].getPosition()[1] - self["key_green"].instance.size().height()))
			self.showChoiceBoxDialog()
		else:
			addTimerFromEvent(self.session, lambda _: self.updateButtons(), event, self.currentService)

	def showChoiceBoxDialog(self):
		self['actions'].setEnabled(False)
		self["dialogactions"].setEnabled(True)
		self.ChoiceBoxDialog['actions'].execBegin()
		self.ChoiceBoxDialog.show()

	def closeChoiceBoxDialog(self):
		self["dialogactions"].setEnabled(False)
		if self.ChoiceBoxDialog:
			self.ChoiceBoxDialog['actions'].execEnd()
			self.session.deleteDialog(self.ChoiceBoxDialog)
		self['actions'].setEnabled(True)
		if "epgactions1" in self:
			self["epgactions1"].setEnabled(True)
		if "epgactions2" in self:
			self["epgactions2"].setEnabled(True)
		if "epgactions3" in self:
			self["epgactions3"].setEnabled(True)

	def setService(self, service):
		self.currentService = service
		self["Service"].newService(service.ref)
		if self.isRecording:
			self["channel"].setText(_("Recording"))
		else:
			name = service.getServiceName()
			if name is not None:
				self["channel"].setText(name)
			else:
				self["channel"].setText(_("unknown service"))

	def setEvent(self, event):
		if event is None or not hasattr(event, 'getEventName'):
			return

		self["Event"].newEvent(event)
		self.event = event
		text = event.getEventName()
		self.setTitle(text)
		self["epg_eventname"].setText(text)

		short = event.getShortDescription()
		extended = event.getExtendedDescription()

		if short == text:
			short = ""

		if short and extended:
			extended = short + '\n' + extended
		elif short:
			extended = short

		if text and extended:
			text += "\n\n"
		text += extended
		self["epg_description"].setText(text)
		self["FullDescription"].setText(extended)

		self["summary_description"].setText(extended)

		begint = event.getBeginTime()
		begintime = localtime(begint)
		endtime = localtime(begint + event.getDuration())
		self["datetime"].setText("%s - %s" % (strftime("%s, %s" % (config.usage.date.short.value, config.usage.time.short.value), begintime), strftime(config.usage.time.short.value, endtime)))
		self["duration"].setText(_("%d min") % (event.getDuration() / 60))
		if self.SimilarBroadcastTimer is not None:
			self.SimilarBroadcastTimer.start(400, True)
		self.updateButtons()

	def pageUp(self):
		self["epg_eventname"].pageUp()
		self["epg_description"].pageUp()
		self["FullDescription"].pageUp()

	def pageDown(self):
		self["epg_eventname"].pageDown()
		self["epg_description"].pageDown()
		self["FullDescription"].pageDown()

	def getSimilarEvents(self):
		# search similar broadcastings
		if not self.event:
			return
		refstr = str(self.currentService)
		id = self.event.getEventId()
		epgcache = eEPGCache.getInstance()
		ret = epgcache.search(('NB', 100, eEPGCache.SIMILAR_BROADCASTINGS_SEARCH, refstr, id))
		if ret is not None:
			text = "\n\n" + _("Similar broadcasts:")
			for x in sorted(ret, key=lambda x: x[1]):
				text += "\n%s  -  %s" % (strftime(config.usage.date.long.value + ", " + config.usage.time.short.value, localtime(x[1])), x[0])
			descr = self["epg_description"]
			descr.setText(descr.getText() + text)
			descr = self["FullDescription"]
			descr.setText(descr.getText() + text)
			self["key_red"].setText(_("Similar"))

	def openSimilarList(self):
		if self.similarEPGCB is not None and self["key_red"].getText():
			id = self.event and self.event.getEventId()
			refstr = str(self.currentService)
			if id is not None:
				self.similarEPGCB(id, refstr)

	def doContext(self):
		if self.event:
			menu = []
			for p in plugins.getPlugins(PluginDescriptor.WHERE_EVENTINFO):
				# only list service or event specific eventinfo plugins here, no servelist plugins
				if "servicelist" not in p.fnc.__code__.co_varnames:
					menu.append((p.name, boundFunction(self.runPlugin, p), p))
			if menu:
				self.session.open(EventViewContextMenu, menu)

	def runPlugin(self, plugin):
		plugin(session=self.session, service=self.currentService, event=self.event, eventName=self.event.getEventName())


class EventViewSimple(Screen, EventViewBase):
	def __init__(self, session, event, ref, callback=None, singleEPGCB=None, multiEPGCB=None, similarEPGCB=None, skin='EventViewSimple'):
		Screen.__init__(self, session)
		self.setTitle(_('Event view'))
		self.skinName = [skin, "EventView"]
		EventViewBase.__init__(self, event, ref, callback, similarEPGCB)


class EventViewEPGSelect(Screen, EventViewBase):
	def __init__(self, session, event, ref, callback=None, singleEPGCB=None, multiEPGCB=None, similarEPGCB=None):
		Screen.__init__(self, session)
		self.skinName = "EventView"
		EventViewBase.__init__(self, event, ref, callback, similarEPGCB)

		# Background for Buttons
		self["red"] = Pixmap()
		self["green"] = Pixmap()
		self["yellow"] = Pixmap()
		self["blue"] = Pixmap()

		self["epgactions1"] = ActionMap(["EventViewActions"],
			{
				"timerAdd": self.timerAdd,
				"openSimilarList": self.openSimilarList,
			})  # noqa: E123
		self["key_green"] = Button("")

		if singleEPGCB:
			self["key_yellow"] = Button(_("Single EPG"))
			self["epgactions2"] = ActionMap(["EventViewEPGActions"],
				{
					"openSingleServiceEPG": singleEPGCB,
				})  # noqa: E123
		else:
			self["key_yellow"] = Button("")
			self["yellow"].hide()

		if multiEPGCB:
			self["key_blue"] = Button(_("Multi EPG"))
			self["epgactions3"] = ActionMap(["EventViewEPGActions"],
				{
					"openMultiServiceEPG": multiEPGCB,
				})  # noqa: E123
		else:
			self["key_blue"] = Button("")
			self["blue"].hide()

		self.updateButtons()
