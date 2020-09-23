from enigma import eListbox, eListboxPythonConfigContent, ePoint, eRCInput, eTimer
from skin import parameters

from Components.ActionMap import HelpableActionMap, HelpableNumberActionMap
from Components.config import ConfigBoolean, ConfigElement, ConfigInteger, ConfigMacText, ConfigSelection, ConfigSequence, ConfigText, KEYA_0, KEYA_ASCII, KEYA_BACKSPACE, KEYA_DELETE, KEYA_ERASE, KEYA_FIRST, KEYA_LAST, KEYA_LEFT, KEYA_NUMBERS, KEYA_RIGHT, KEYA_SELECT, KEYA_TIMEOUT, KEYA_TOGGLE, config, configfile
from Components.GUIComponent import GUIComponent
from Components.Pixmap import Pixmap
from Components.Sources.Boolean import Boolean
from Components.Sources.StaticText import StaticText
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from Screens.Standby import QUIT_RESTART, TryQuitMainloop
from Screens.VirtualKeyBoard import VirtualKeyBoard


class ConfigList(GUIComponent, object):
	def __init__(self, list, session=None):
		GUIComponent.__init__(self)
		self.l = eListboxPythonConfigContent()
		seperation = parameters.get("ConfigListSeperator", 200)
		self.l.setSeperation(seperation)
		height, space = parameters.get("ConfigListSlider", (17, 0))
		self.l.setSlider(height, space)
		self.timer = eTimer()
		self.list = list
		self.onSelectionChanged = []
		self.current = None
		self.session = session

	def execBegin(self):
		rcinput = eRCInput.getInstance()
		rcinput.setKeyboardMode(rcinput.kmAscii)
		self.timer.callback.append(self.timeout)

	def execEnd(self):
		rcinput = eRCInput.getInstance()
		rcinput.setKeyboardMode(rcinput.kmNone)
		self.timer.stop()
		self.timer.callback.remove(self.timeout)

	def timeout(self):
		self.handleKey(KEYA_TIMEOUT)

	def handleKey(self, key):
		selection = self.getCurrent()
		if selection and selection[1].enabled:
			selection[1].handleKey(key)
			self.invalidateCurrent()
			if key in KEYA_NUMBERS:
				self.timer.start(1000, 1)

	def toggle(self):
		self.getCurrent()[1].toggle()
		self.invalidateCurrent()

	def getCurrent(self):
		return self.l.getCurrentSelection()

	def getCurrentIndex(self):
		return self.l.getCurrentSelectionIndex()

	def setCurrentIndex(self, index):
		if self.instance is not None:
			self.instance.moveSelectionTo(index)

	def invalidateCurrent(self):
		self.l.invalidateEntry(self.l.getCurrentSelectionIndex())

	def invalidate(self, entry):
		# When the entry to invalidate does not exist, just ignore the request.
		# This eases up conditional setup screens a lot.
		if entry in self.__list:
			self.l.invalidateEntry(self.__list.index(entry))

	GUI_WIDGET = eListbox

	def isChanged(self):
		for x in self.list:
			if x[1].isChanged():
				return True
		return False

	def selectionEnabled(self, enabled):
		if self.instance is not None:
			self.instance.setSelectionEnable(enabled)

	def selectionChanged(self):
		if isinstance(self.current, tuple) and len(self.current) >= 2:
			self.current[1].onDeselect(self.session)
		self.current = self.getCurrent()
		if isinstance(self.current, tuple) and len(self.current) >= 2:
			self.current[1].onSelect(self.session)
		else:
			return
		for x in self.onSelectionChanged:
			x()

	def postWidgetCreate(self, instance):
		instance.selectionChanged.get().append(self.selectionChanged)
		instance.setContent(self.l)
		self.instance.setWrapAround(True)

	def preWidgetRemove(self, instance):
		if isinstance(self.current, tuple) and len(self.current) >= 2:
			self.current[1].onDeselect(self.session)
		instance.selectionChanged.get().remove(self.selectionChanged)
		instance.setContent(None)

	def setList(self, l):
		self.__list = l
		self.l.setList(self.__list)
		if l is not None:
			for x in l:
				assert len(x) < 2 or isinstance(x[1], ConfigElement), "[ConfigList] Error: Entry in ConfigList '%s' must be a ConfigElement!" % str(x[1])

	def getList(self):
		return self.__list

	list = property(getList, setList)

	def moveTop(self):
		if self.instance is not None:
			self.instance.moveSelection(self.instance.moveTop)

	def pageUp(self):
		if self.instance is not None:
			self.instance.moveSelection(self.instance.pageUp)

	def moveUp(self):
		if self.instance is not None:
			self.instance.moveSelection(self.instance.moveUp)

	def moveDown(self):
		if self.instance is not None:
			self.instance.moveSelection(self.instance.moveDown)

	def pageDown(self):
		if self.instance is not None:
			self.instance.moveSelection(self.instance.pageDown)

	def moveBottom(self):
		if self.instance is not None:
			self.instance.moveSelection(self.instance.moveEnd)


class ConfigListScreen:
	def __init__(self, list, session=None, on_change=None, fullUI=False):
		self.entryChanged = on_change if on_change is not None else lambda: None
		if fullUI:
			if "key_red" not in self:
				self["key_red"] = StaticText(_("Cancel"))
			if "key_green" not in self:
				self["key_green"] = StaticText(_("Save"))
			self["fullUIActions"] = HelpableActionMap(self, ["ConfigListActions"], {
				"cancel": (self.keyCancel, _("Cancel any changed settings and exit")),
				"close": (self.closeRecursive, _("Cancel any changed settings and exit all menus")),
				"save": (self.keySave, _("Save all changed settings and exit"))
			}, prio=1, description=_("Common Setup Actions"))
		if "key_menu" not in self:
			self["key_menu"] = StaticText(_("MENU"))
		if "HelpWindow" not in self:
			self["HelpWindow"] = Pixmap()
			self["HelpWindow"].hide()
		if "VKeyIcon" not in self:
			self["VKeyIcon"] = Boolean(False)
		self["configActions"] = HelpableActionMap(self, ["ConfigListActions"], {
			"select": (self.keySelect, _("Select, toggle, process or edit the current entry"))
		}, prio=1, description=_("Common Setup Actions"))
		self["navigationActions"] = HelpableActionMap(self, ["NavigationActions"], {
			"top": (self.keyTop, _("Move to first line / screen")),
			"pageUp": (self.keyPageUp, _("Move up a screen")),
			"up": (self.keyUp, _("Move up a line")),
			"first": (self.keyFirst, _("Jump to first item in list or the start of text")),
			"left": (self.keyLeft, _("Select the previous item in list or move cursor left")),
			"right": (self.keyRight, _("Select the next item in list or move cursor right")),
			"last": (self.keyLast, _("Jump to last item in list or the end of text")),
			"down": (self.keyDown, _("Move down a line")),
			"pageDown": (self.keyPageDown, _("Move down a screen")),
			"bottom": (self.keyBottom, _("Move to last line / screen"))
		}, prio=1, description=_("Common Setup Actions"))
		self["menuConfigActions"] = HelpableActionMap(self, "ConfigListActions", {
			"menu": (self.keyMenu, _("Display selection list as a selection menu")),
		}, prio=1, description=_("Common Setup Actions"))
		self["menuConfigActions"].setEnabled(False)
		self["editConfigActions"] = HelpableNumberActionMap(self, ["NumberActions", "TextEditActions"], {
			"backspace": (self.keyBackspace, _("Delete character to left of cursor or select AM times")),
			"delete": (self.keyDelete, _("Delete character under cursor or select PM times")),
			"erase": (self.keyErase, _("Delete all the text")),
			"toggleOverwrite": (self.keyToggle, _("Toggle new text inserts before or overwrites existing text")),
			"1": (self.keyNumberGlobal, _("Number or SMS style data entry")),
			"2": (self.keyNumberGlobal, _("Number or SMS style data entry")),
			"3": (self.keyNumberGlobal, _("Number or SMS style data entry")),
			"4": (self.keyNumberGlobal, _("Number or SMS style data entry")),
			"5": (self.keyNumberGlobal, _("Number or SMS style data entry")),
			"6": (self.keyNumberGlobal, _("Number or SMS style data entry")),
			"7": (self.keyNumberGlobal, _("Number or SMS style data entry")),
			"8": (self.keyNumberGlobal, _("Number or SMS style data entry")),
			"9": (self.keyNumberGlobal, _("Number or SMS style data entry")),
			"0": (self.keyNumberGlobal, _("Number or SMS style data entry")),
			"gotAsciiCode": (self.keyGotAscii, _("Keyboard data entry"))
		}, prio=1, description=_("Common Setup Actions"))
		self["editConfigActions"].setEnabled(False)
		self["VirtualKB"] = HelpableActionMap(self, "VirtualKeyboardActions", {
			"showVirtualKeyboard": (self.keyText, _("Display the virtual keyboard for data entry"))
		}, prio=1, description=_("Common Setup Actions"))
		self["VirtualKB"].setEnabled(False)
		self["config"] = ConfigList(list, session=session)
		self.setCancelMessage(None)
		self.setRestartMessage(None)
		self.onChangedEntry = []
		if self.noNativeKeys not in self.onLayoutFinish:
			self.onLayoutFinish.append(self.noNativeKeys)
		if self.handleInputHelpers not in self["config"].onSelectionChanged:
			self["config"].onSelectionChanged.append(self.handleInputHelpers)
		if self.showHelpWindow not in self.onExecBegin:
			self.onExecBegin.append(self.showHelpWindow)
		if self.hideHelpWindow not in self.onExecEnd:
			self.onExecEnd.append(self.hideHelpWindow)

	def noNativeKeys(self):
		self["config"].instance.allowNativeKeys(False)

	def setCancelMessage(self, msg):
		self.cancelMsg = _("Really close without saving settings?") if msg is None else msg

	def setRestartMessage(self, msg):
		self.restartMsg = _("Restart GUI now?") if msg is None else msg

	def getCurrentItem(self):
		return self["config"].getCurrent() and self["config"].getCurrent()[1] or None

	def getCurrentEntry(self):
		return self["config"].getCurrent() and self["config"].getCurrent()[0] or ""

	def getCurrentValue(self):
		return self["config"].getCurrent() and str(self["config"].getCurrent()[1].getText()) or ""

	def getCurrentDescription(self):
		return self["config"].getCurrent() and len(self["config"].getCurrent()) > 2 and self["config"].getCurrent()[2] or ""

	def changedEntry(self):
		for x in self.onChangedEntry:
			x()

	def handleInputHelpers(self):
		currConfig = self["config"].getCurrent()
		if currConfig is not None:
			if isinstance(currConfig[1], (ConfigInteger, ConfigMacText, ConfigSequence, ConfigText)):
				self["editConfigActions"].setEnabled(True)
			else:
				self["editConfigActions"].setEnabled(False)
			if isinstance(currConfig[1], ConfigSelection):
				self["menuConfigActions"].setEnabled(True)
				self["key_menu"].setText(_("MENU"))
			else:
				self["menuConfigActions"].setEnabled(False)
				self["key_menu"].setText("")
			if isinstance(currConfig[1], ConfigText):
				self.showVKeyboard(True)
				if "HelpWindow" in self and currConfig[1].help_window and currConfig[1].help_window.instance is not None:
					helpwindowpos = self["HelpWindow"].getPosition()
					currConfig[1].help_window.instance.move(ePoint(helpwindowpos[0], helpwindowpos[1]))
			else:
				self.showVKeyboard(False)

	def showVKeyboard(self, state):
		if "VKeyIcon" in self:
			self["VirtualKB"].setEnabled(state)
			self["VKeyIcon"].boolean = state

	def showHelpWindow(self):
		self.displayHelp(True)

	def hideHelpWindow(self):
		self.displayHelp(False)

	def displayHelp(self, state):
		if "config" in self and "HelpWindow" in self and self["config"].getCurrent() is not None and len(self["config"].getCurrent()) > 1:
			currConf = self["config"].getCurrent()[1]
			if isinstance(currConf, ConfigText) and currConf.help_window is not None and currConf.help_window.instance is not None:
				if state:
					currConf.help_window.show()
				else:
					currConf.help_window.hide()

	def keySelect(self):
		if isinstance(self.getCurrentItem(), ConfigSelection):
			self.keyMenu()
		elif isinstance(self.getCurrentItem(), ConfigText):
			self.keyText()
		else:
			self["config"].handleKey(KEYA_SELECT)

	def keyOK(self):  # This is the deprecated version of keySelect!
		self.keySelect()

	def keyText(self):
		self.session.openWithCallback(self.keyTextCallback, VirtualKeyBoard, title=self.getCurrentEntry(), text=str(self.getCurrentValue()))

	def keyTextCallback(self, callback=None):
		if callback is not None:
			prev = str(self.getCurrentValue())
			self["config"].getCurrent()[1].setValue(callback)
			self["config"].invalidateCurrent()
			if callback != prev:
				self.entryChanged()

	def keyMenu(self):
		currConfig = self["config"].getCurrent()
		if currConfig and currConfig[1].enabled and hasattr(currConfig[1], "description"):
			self.session.openWithCallback(
				self.keyMenuCallback, ChoiceBox, title=currConfig[0],
				list=zip(currConfig[1].description, currConfig[1].choices),
				selection=currConfig[1].getIndex(),
				keys=[]
			)

	def keyMenuCallback(self, answer):
		if answer:
			self["config"].getCurrent()[1].value = answer[1]
			self["config"].invalidateCurrent()
			self.entryChanged()

	def keyTop(self):
		self["config"].moveTop()

	def keyPageUp(self):
		self["config"].pageUp()

	def keyUp(self):
		self["config"].moveUp()

	def keyFirst(self):
		self["config"].handleKey(KEYA_HOME)
		self.entryChanged()

	def keyLeft(self):
		self["config"].handleKey(KEYA_LEFT)
		self.entryChanged()

	def keyRight(self):
		self["config"].handleKey(KEYA_RIGHT)
		self.entryChanged()

	def keyLast(self):
		self["config"].handleKey(KEYA_END)
		self.entryChanged()

	def keyDown(self):
		self["config"].moveDown()

	def keyPageDown(self):
		self["config"].pageDown()

	def keyBottom(self):
		self["config"].moveBottom()

	def keyBackspace(self):
		self["config"].handleKey(KEYA_BACKSPACE)
		self.entryChanged()

	def keyDelete(self):
		self["config"].handleKey(KEYA_DELETE)
		self.entryChanged()

	def keyErase(self):
		self["config"].handleKey(KEYA_ERASE)
		self.entryChanged()

	def keyToggle(self):
		self["config"].handleKey(KEYA_TOGGLE)
		self.entryChanged()

	def keyGotAscii(self):
		self["config"].handleKey(KEYA_ASCII)
		self.entryChanged()

	def keyNumberGlobal(self, number):
		self["config"].handleKey(KEYA_0 + number)
		self.entryChanged()

	def keySave(self):
		self.saveAll()
		if self.restart:
			self.session.openWithCallback(self.restartConfirm, MessageBox, self.restartMsg, default=True, type=MessageBox.TYPE_YESNO)
		else:
			self.close()

	def saveAll(self):
		self.restart = False
		for x in self["config"].list:
			if x[0].endswith("*") and x[1].isChanged():
				self.restart = True
			x[1].save()
		configfile.save()

	def restartConfirm(self, result):
		if result:
			self.session.open(TryQuitMainloop, retvalue=QUIT_RESTART)
			self.close()

	def keyCancel(self):
		self.closeConfigList(())

	def closeRecursive(self):
		self.closeConfigList((True,))

	def closeConfigList(self, closeParameters=()):
		if self["config"].isChanged():
			self.closeParameters = closeParameters
			self.session.openWithCallback(self.cancelConfirm, MessageBox, self.cancelMsg, default=False, type=MessageBox.TYPE_YESNO)
		else:
			self.close(*closeParameters)

	def cancelConfirm(self, result):
		if not result:
			return
		for x in self["config"].list:
			x[1].cancel()
		self.close(*self.closeParameters)

	def createSummary(self):  # This should not be required if ConfigList is invoked via Setup (as it should).
		from Screens.Setup import SetupSummary
		return SetupSummary

	def run(self):  # Allow ConfigList based screens to be processed from the Wizard.
		self.keySave()
