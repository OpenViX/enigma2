from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.config import config
from Components.MenuList import MenuList
from Components.TimerList import TimerList
from Components.TimerSanityCheck import TimerSanityCheck
from Components.UsageConfig import preferredTimerPath
from Components.Sources.StaticText import StaticText
from RecordTimer import RecordTimerEntry, parseEvent, AFTEREVENT
from Screens.Screen import Screen
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from Screens.ParentalControlSetup import ProtectedScreen
from Screens.InputBox import PinInput
from ServiceReference import ServiceReference
from Screens.TimerEntry import TimerEntry, TimerLog
from Screens.Setup import Setup
from Tools.BoundFunction import boundFunction
from Tools.FuzzyDate import FuzzyTime
from time import time
from timer import TimerEntry as RealTimerEntry

class TimerEditList(Screen, ProtectedScreen):
	EMPTY = 0
	ENABLE = 1
	DISABLE = 2
	CLEANUP = 3
	DELETE = 4
	STOP = 5

	def __init__(self, session, menu_path = "", selectItem = None):
		Screen.__init__(self, session)
		screentitle = _("Timer List")
		self.menu_path = menu_path
		self.selectItem = selectItem
		ProtectedScreen.__init__(self)
		if config.usage.show_menupath.value == 'large':
			self.menu_path += screentitle
			title = self.menu_path
			self["menu_path_compressed"] = StaticText("")
			self.menu_path += ' / '
		elif config.usage.show_menupath.value == 'small':
			title = screentitle
			condtext = ""
			if self.menu_path and not self.menu_path.endswith(' / '):
				condtext = self.menu_path + " >"
			elif self.menu_path:
				condtext = self.menu_path[:-3] + " >"
			self["menu_path_compressed"] = StaticText(condtext)
			self.menu_path += screentitle + ' / '
		else:
			title = screentitle
			self["menu_path_compressed"] = StaticText("")
		Screen.setTitle(self, title)
		
		self.onChangedEntry = [ ]
		self.list = []
		self["timerlist"] = TimerList(self.list)

		self.key_red_choice = self.EMPTY
		self.key_yellow_choice = self.EMPTY
		self.key_blue_choice = self.EMPTY

		self["key_red"] = StaticText("")
		self["key_green"] = StaticText(_("Add"))
		self["key_yellow"] = StaticText("")
		self["key_blue"] = StaticText("")

		self["description"] = Label()

		self["actions"] = ActionMap(["OkCancelActions", "DirectionActions", "ShortcutActions", "TimerEditActions"],
			{
				"ok": self.openEdit,
				"cancel": self.leave,
				"green": self.addCurrentTimer,
				"log": self.showLog,
				"left": self.left,
				"right": self.right,
				"up": self.up,
				"down": self.down,
				"moveTop": self.moveTop,
				"moveEnd": self.moveEnd,
				"menu": self.createSetup
			}, -1)
		self.session.nav.RecordTimer.on_state_change.append(self.onStateChange)
		self.onLayoutFinish.append(self.onCreate)

	def onCreate(self):
		self.fillTimerList()
		self["timerlist"].l.setList(self.list)

		if self.selectItem is not None:
			(event, service) = self.selectItem
			if event is not None:
				eventid = event.getEventId()
				refstr = ':'.join(service.ref.toString().split(':')[:11])
				idx = 0
				for (timer, processed) in self.list:
					if timer.eit == eventid and ':'.join(timer.service_ref.ref.toString().split(':')[:11]) == refstr:
						self["timerlist"].moveToIndex(idx)
						break
					idx += 1
		self.updateState()

	def createSetup(self):
		def onSetupClose(test = None):
			self.refill()
			pass

		self.session.openWithCallback(onSetupClose, Setup, 'recording')

	def isProtected(self):
		return config.ParentalControl.setuppinactive.value and (not config.ParentalControl.config_sections.main_menu.value or hasattr(self.session, 'infobar') and self.session.infobar is None) and config.ParentalControl.config_sections.timer_menu.value and config.ParentalControl.servicepin[0].value

	def createSummary(self):
		return TimerEditListSummary

	def up(self):
		self["timerlist"].instance.moveSelection(self["timerlist"].instance.moveUp)
		self.updateState()

	def down(self):
		self["timerlist"].instance.moveSelection(self["timerlist"].instance.moveDown)
		self.updateState()

	def left(self):
		self["timerlist"].instance.moveSelection(self["timerlist"].instance.pageUp)
		self.updateState()

	def right(self):
		self["timerlist"].instance.moveSelection(self["timerlist"].instance.pageDown)
		self.updateState()

	def moveTop(self):
		self["timerlist"].instance.moveSelection(self["timerlist"].instance.moveTop)
		self.updateState()

	def moveEnd(self):
		self["timerlist"].instance.moveSelection(self["timerlist"].instance.moveEnd)
		self.updateState()

	def toggleDisabledState(self):
		cur = self["timerlist"].getCurrent()
		if cur:
			t = cur
			if t.disabled:
				t.enable()
				timersanitycheck = TimerSanityCheck(self.session.nav.RecordTimer.timer_list, cur)
				if not timersanitycheck.check():
					t.disable()
					print "[TimerEdit] Sanity check failed"
					simulTimerList = timersanitycheck.getSimulTimerList()
					if simulTimerList is not None:
						self.session.openWithCallback(self.finishedEdit, TimerSanityConflict, simulTimerList, self.menu_path)
				else:
					print "[TimerEdit] Sanity check passed"
					if timersanitycheck.doubleCheck():
						t.disable()
			else:
				if t.isRunning():
					if t.repeated:
						list = (
							(_("Stop current event but not future events"), "stoponlycurrent"),
							(_("Stop current event and disable future events"), "stopall"),
							(_("Don't stop current event but disable future events"), "stoponlycoming")
						)
						self.session.openWithCallback(boundFunction(self.runningEventCallback, t), ChoiceBox, title=_("Repeating event currently recording... What do you want to do?"), list = list)
				else:
					t.disable()
			self.session.nav.RecordTimer.timeChanged(t)
			self.refill()
			self.updateState()

	def runningEventCallback(self, t, result):
		if result is not None:
			if result[1] == "stoponlycurrent" or result[1] == "stopall":
				t.enable()
				t.processRepeated(findRunningEvent = False)
				self.session.nav.RecordTimer.doActivate(t)
			if result[1] == "stoponlycoming" or result[1] == "stopall":
				t.disable()
			self.session.nav.RecordTimer.timeChanged(t)
			self.refill()
			self.updateState()

	def removeAction(self, descr):
		actions = self["actions"].actions
		if descr in actions:
			del actions[descr]

	def updateState(self):
		cur = self["timerlist"].getCurrent()
		if cur:
			self["description"].setText(cur.description)
			if cur.state == 2 and self.key_red_choice != self.STOP:
				self["actions"].actions.update({"red":self.stopTimerQuestion})
				self["key_red"].setText(_("Stop"))
				self.key_red_choice = self.STOP
			elif cur.state != 2 and self.key_red_choice != self.DELETE:
				self["actions"].actions.update({"red":self.removeTimerQuestion})
				self["key_red"].setText(_("Delete"))
				self.key_red_choice = self.DELETE

			if cur.disabled and (self.key_yellow_choice != self.ENABLE):
				self["actions"].actions.update({"yellow":self.toggleDisabledState})
				self["key_yellow"].setText(_("Enable"))
				self.key_yellow_choice = self.ENABLE
			elif cur.isRunning() and not cur.repeated and (self.key_yellow_choice != self.EMPTY):
				self.removeAction("yellow")
				self["key_yellow"].setText("")
				self.key_yellow_choice = self.EMPTY
			elif ((not cur.isRunning())or cur.repeated ) and (not cur.disabled) and (self.key_yellow_choice != self.DISABLE):
				self["actions"].actions.update({"yellow":self.toggleDisabledState})
				self["key_yellow"].setText(_("Disable"))
				self.key_yellow_choice = self.DISABLE
		else:
			if self.key_red_choice != self.EMPTY:
				self.removeAction("red")
				self["key_red"].setText("")
				self.key_red_choice = self.EMPTY
			if self.key_yellow_choice != self.EMPTY:
				self.removeAction("yellow")
				self["key_yellow"].setText("")
				self.key_yellow_choice = self.EMPTY

		showCleanup = True
		for x in self.list:
			if (not x[0].disabled) and (x[1] == True):
				break
		else:
			showCleanup = False

		if showCleanup and (self.key_blue_choice != self.CLEANUP):
			self["actions"].actions.update({"blue":self.cleanupQuestion})
			self["key_blue"].setText(_("Cleanup"))
			self.key_blue_choice = self.CLEANUP
		elif (not showCleanup) and (self.key_blue_choice != self.EMPTY):
			self.removeAction("blue")
			self["key_blue"].setText("")
			self.key_blue_choice = self.EMPTY
		if len(self.list) == 0:
			return
		timer = self['timerlist'].getCurrent()

		if timer:
			try:
				name = str(timer.name)
				time = "%s %s ... %s" % (FuzzyTime(timer.begin)[0], FuzzyTime(timer.begin)[1], FuzzyTime(timer.end)[1])
				duration = ("(%d " + _("mins") + ")") % ((timer.end - timer.begin) / 60)
				service = str(timer.service_ref.getServiceName())

				if timer.state == RealTimerEntry.StateWaiting:
					state = _("waiting")
				elif timer.state == RealTimerEntry.StatePrepared:
					state = _("about to start")
				elif timer.state == RealTimerEntry.StateRunning:
					if timer.justplay:
						state = _("zapped")
					else:
						state = _("recording...")
				elif timer.state == RealTimerEntry.StateEnded:
					state = _("done!")
				else:
					state = _("<unknown>")
			except:
				name = ""
				time = ""
				duration = ""
				service = ""
				state = ""
		else:
			name = ""
			time = ""
			duration = ""
			service = ""
			state = ""
		for cb in self.onChangedEntry:
			cb(name, time, duration, service, state)

	def fillTimerList(self):
		#helper function to move finished timers to end of list
		def eol_compare(x, y):
			if x[0].state != y[0].state and x[0].state == RealTimerEntry.StateEnded or y[0].state == RealTimerEntry.StateEnded:
				return cmp(x[0].state, y[0].state)
			return cmp(x[0].begin, y[0].begin)

		list = self.list
		del list[:]
		list.extend([(timer, False) for timer in self.session.nav.RecordTimer.timer_list])
		now = time()
		if config.usage.timerlist_finished_timer_position.index == 2:
			# if the "hide" option is set, continue to add disabled timers so
			# timer conflicts remain visible
			list.extend([(timer, True) for timer in self.session.nav.RecordTimer.processed_timers if timer.disabled and timer.end > now])
		else:
			list.extend([(timer, True) for timer in self.session.nav.RecordTimer.processed_timers])
		if config.usage.timerlist_finished_timer_position.index == 1: #end of list
			list.sort(cmp = eol_compare)
		else:
			list.sort(key = lambda x: x[0].begin)

	def showLog(self):
		cur = self["timerlist"].getCurrent()
		if cur:
			self.session.openWithCallback(self.finishedEdit, TimerLog, cur, self.menu_path)

	def openEdit(self):
		cur = self["timerlist"].getCurrent()
		if cur:
			self.session.openWithCallback(self.finishedEdit, TimerEntry, cur, self.menu_path)

	def cleanupQuestion(self):
		self.session.openWithCallback(self.cleanupTimer, MessageBox, _("Really delete completed timers?"))

	def cleanupTimer(self, delete):
		if delete:
			self.session.nav.RecordTimer.cleanup()
			self.refill()
			self.updateState()

	def stopTimerQuestion(self):
		cur = self["timerlist"].getCurrent()
		if cur:
			self.session.openWithCallback(self.removeTimer, MessageBox, _("Do you really want to stop the current recording and delete timer %s?") % cur.name, default = False)

	def removeTimerQuestion(self):
		cur = self["timerlist"].getCurrent()
		if cur:
			self.session.openWithCallback(self.removeTimer, MessageBox, _("Do you really want to delete %s?") % cur.name, default = False)

	def removeTimer(self, result):
		if not result:
			return
		list = self["timerlist"]
		cur = list.getCurrent()
		if cur:
			timer = cur
			timer.afterEvent = AFTEREVENT.NONE
			self.session.nav.RecordTimer.removeEntry(timer)
			self.refill()
			self.updateState()


	def refill(self):
		oldsize = len(self.list)
		self.fillTimerList()
		lst = self["timerlist"]
		newsize = len(self.list)
		if oldsize and oldsize != newsize:
			idx = lst.getCurrentIndex()
			lst.entryRemoved(idx)
		else:
			lst.invalidate()

	def addCurrentTimer(self):
		event = None
		service = self.session.nav.getCurrentService()
		if service is not None:
			info = service.info()
			if info is not None:
				event = info.getEvent(0)

		# FIXME only works if already playing a service
		serviceref = ServiceReference(self.session.nav.getCurrentlyPlayingServiceOrGroup())

		if event is None:
			data = (int(time()), int(time() + 60), "", "", None)
		else:
			data = parseEvent(event, description = False)

		self.addTimer(RecordTimerEntry(serviceref, checkOldTimers = True, dirname = preferredTimerPath(), *data))

	def addTimer(self, timer):
		self.session.openWithCallback(self.finishedAdd, TimerEntry, timer, self.menu_path)


	def finishedEdit(self, answer):
		if answer[0]:
			entry = answer[1]
			timersanitycheck = TimerSanityCheck(self.session.nav.RecordTimer.timer_list, entry)
			success = False
			if not timersanitycheck.check():
				simulTimerList = timersanitycheck.getSimulTimerList()
				if simulTimerList is not None:
					for x in simulTimerList:
						if x.setAutoincreaseEnd(entry):
							self.session.nav.RecordTimer.timeChanged(x)
					if not timersanitycheck.check():
						simulTimerList = timersanitycheck.getSimulTimerList()
						if simulTimerList is not None:
							self.session.openWithCallback(self.finishedEdit, TimerSanityConflict, timersanitycheck.getSimulTimerList(), self.menu_path)
					else:
						success = True
			else:
				success = True
			if success:
				print "[TimerEdit] Sanity check passed"
				self.session.nav.RecordTimer.timeChanged(entry)

			self.fillTimerList()
			self.updateState()

	def finishedAdd(self, answer):
		if answer[0]:
			entry = answer[1]
			simulTimerList = self.session.nav.RecordTimer.record(entry)
			if simulTimerList is not None:
				for x in simulTimerList:
					if x.setAutoincreaseEnd(entry):
						self.session.nav.RecordTimer.timeChanged(x)
				simulTimerList = self.session.nav.RecordTimer.record(entry)
				if simulTimerList is not None:
					self.session.openWithCallback(self.finishSanityCorrection, TimerSanityConflict, simulTimerList, self.menu_path)
			self.fillTimerList()
			self.updateState()

	def finishSanityCorrection(self, answer):
		self.finishedAdd(answer)

	def leave(self):
		self.session.nav.RecordTimer.on_state_change.remove(self.onStateChange)
		self.close()

	def onStateChange(self, entry):
		self.refill()
		self.updateState()

class TimerSanityConflict(Screen):
	EMPTY = 0
	ENABLE = 1
	DISABLE = 2
	EDIT = 3

	def __init__(self, session, timer, menu_path=""):
		Screen.__init__(self, session)
		screentitle = _("Timer sanity error")
		self.menu_path = menu_path
		if config.usage.show_menupath.value == 'large':
			self.menu_path += screentitle
			title = self.menu_path
			self["menu_path_compressed"] = StaticText("")
			self.menu_path += ' / '
		elif config.usage.show_menupath.value == 'small':
			title = screentitle
			condtext = ""
			if self.menu_path and not self.menu_path.endswith(' / '):
				condtext = self.menu_path + " >"
			elif self.menu_path:
				condtext = self.menu_path[:-3] + " >"
			self["menu_path_compressed"] = StaticText(condtext)
			self.menu_path += screentitle + ' / '
		else:
			title = screentitle
			self["menu_path_compressed"] = StaticText("")
		Screen.setTitle(self, title)

		self.timer = timer
		print "[TimerEdit] TimerSanityConflict"

		self["timer1"] = TimerList(self.getTimerList(timer[0]))
		self.list = []
		self.list2 = []
		count = 0
		for x in timer:
			if count != 0:
				self.list.append((_("Conflicting timer") + " " + str(count), x))
				self.list2.append((timer[count], False))
			count += 1
		if count == 1:
			self.list.append((_("Channel not in services list")))

		self["list"] = MenuList(self.list)
		self["timer2"] = TimerList(self.list2)

		self["key_red"] = StaticText(_("Edit new entry"))
# 		self["key_green"] = StaticText("")
		self["key_yellow"] = StaticText("")
		self["key_blue"] = StaticText("")

		self.key_green_choice = self.EMPTY
		self.key_yellow_choice = self.EMPTY
		self.key_blue_choice = self.EMPTY

		self["actions"] = ActionMap(["OkCancelActions", "DirectionActions", "ShortcutActions", "TimerEditActions"],
			{
				"ok": self.leave_ok,
				"cancel": self.leave_cancel,
				"red": self.editTimer1,
				"up": self.up,
				"down": self.down
			}, -1)
		self.onShown.append(self.updateState)

	def getTimerList(self, timer):
		return [(timer, False)]

	def editTimer1(self):
		self.session.openWithCallback(self.finishedEdit, TimerEntry, self["timer1"].getCurrent(), self.menu_path)

	def editTimer2(self):
		self.session.openWithCallback(self.finishedEdit, TimerEntry, self["timer2"].getCurrent(), self.menu_path)

	def toggleTimer(self):
		x = self["list"].getSelectedIndex() + 1 # the first is the new timer so we do +1 here
		if self.timer[x].disabled:
			self.timer[x].disabled = False
			self.session.nav.RecordTimer.timeChanged(self.timer[x])
			if not self.timer[0].isRunning():
				self.timer[0].disabled = True
				self.session.nav.RecordTimer.timeChanged(self.timer[0])

		elif not self.timer[x].isRunning():
			self.timer[x].disabled = True
			self.session.nav.RecordTimer.timeChanged(self.timer[x])
			if self.timer[x].disabled:
				self.timer[0].disabled = False
				self.session.nav.RecordTimer.timeChanged(self.timer[0])
		self.finishedEdit((True, self.timer[0]))

	def finishedEdit(self, answer):
		self.leave_ok()

	def leave_ok(self):
		self.close((True, self.timer[0]))

	def leave_cancel(self):
		self.close((False, self.timer[0]))

	def up(self):
		self["list"].instance.moveSelection(self["list"].instance.moveUp)
		self["timer2"].moveToIndex(self["list"].getSelectedIndex())

	def down(self):
		self["list"].instance.moveSelection(self["list"].instance.moveDown)
		self["timer2"].moveToIndex(self["list"].getSelectedIndex())

	def removeAction(self, descr):
		actions = self["actions"].actions
		if descr in actions:
			del actions[descr]

	def updateState(self):
		if len(self.timer) > 1:
			x = self["list"].getSelectedIndex() + 1 # the first is the new timer so we do +1 here
			if self.timer[x] is not None:
				if self.key_yellow_choice == self.EMPTY:
					self["actions"].actions.update({"yellow":self.editTimer2})
					self["key_yellow"].setText(_("Edit"))
					self.key_yellow_choice = self.EDIT
				if self.timer[x].disabled and self.key_blue_choice != self.ENABLE:
					self["actions"].actions.update({"blue":self.toggleTimer})
					self["key_blue"].setText(_("Enable"))
					self.key_blue_choice = self.ENABLE
				elif self.timer[x].isRunning() and not self.timer[x].repeated and self.key_blue_choice != self.EMPTY:
					self.removeAction("blue")
					self["key_blue"].setText("")
					self.key_blue_choice = self.EMPTY
				elif (not self.timer[x].isRunning() or self.timer[x].repeated ) and self.key_blue_choice != self.DISABLE:
					self["actions"].actions.update({"blue":self.toggleTimer})
					self["key_blue"].setText(_("Disable"))
					self.key_blue_choice = self.DISABLE
		else:
			if self.key_yellow_choice != self.EMPTY:
				self.removeAction("yellow")
				self["key_yellow"].setText("")
				self.key_yellow_choice = self.EMPTY
			if self.key_blue_choice != self.EMPTY:
				self.removeAction("blue")
				self["key_blue"].setText("")
				self.key_blue_choice = self.EMPTY

class TimerEditListSummary(Screen):
	def __init__(self, session, parent):
		Screen.__init__(self, session, parent = parent)
		self["name"] = StaticText("")
		self["service"] = StaticText("")
		self["time"] = StaticText("")
		self["duration"] = StaticText("")
		self["state"] = StaticText("")
		self.onShow.append(self.addWatcher)
		self.onHide.append(self.removeWatcher)

	def addWatcher(self):
		self.parent.onChangedEntry.append(self.selectionChanged)
		self.parent.updateState()

	def removeWatcher(self):
		self.parent.onChangedEntry.remove(self.selectionChanged)

	def selectionChanged(self, name, time, duration, service, state):
		self["name"].text = name
		self["service"].text = service
		self["time"].text = time
		self["duration"].text = duration
		self["state"].text = state

