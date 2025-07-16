from Screens.HelpMenu import HelpableScreen
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import HelpableActionMap, HelpableNumberActionMap
from Components.config import config, ConfigSubsection, ConfigText
from Components.Label import Label
from Components.ChoiceList import ChoiceEntryComponent, ChoiceList
from Components.Sources.StaticText import StaticText
from Tools.BoundFunction import boundFunction
from enigma import ePoint, eSize, getDesktop
from skin import applySkinFactor

config.misc.pluginlist = ConfigSubsection()
config.misc.pluginlist.eventinfo_order = ConfigText(default="")
config.misc.pluginlist.extension_order = ConfigText(default="")


class ChoiceBox(Screen, HelpableScreen):
	def __init__(self, session, title="", list=None, keys=None, selection=0, skin_name=None, text="", reorderConfig="", windowTitle=None, var="", callbackList=None, *args, **kwargs):
		# list is in the format (<display text>, [<parameters to pass to close callback>,])
		# callbackList is in the format (<display text>, <callback func>, [<parameters>,])
		self.isCallbackList = bool(callbackList)
		list = list or callbackList
		if not list:
			list = []
		if not skin_name:
			skin_name = []
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)

		if isinstance(skin_name, str):
			skin_name = [skin_name]
		self.skinName = skin_name + ["ChoiceBox"]

		self.reorderConfig = reorderConfig
		self["text"] = Label()
		self.var = ""
		if reorderConfig:
			self["key_menu"] = StaticText(_("MENU"))
			self["key_previous"] = StaticText(_("PREVIOUS"))
			self["key_next"] = StaticText(_("NEXT"))

		if title:
			title = _(title)
			if len(title) < 55 and title.find('\n') == -1:
				self.setTitle(title)
			elif title.find('\n') != -1:
				temptext = title.split('\n')
				if len(temptext[0]) < 55:
					self.setTitle(temptext[0])
					count = 2
					labeltext = ""
					while len(temptext) >= count:
						if labeltext:
							labeltext += '\n'
						labeltext = labeltext + temptext[count - 1]
						count += 1
					self["text"].setText(labeltext)
				else:
					self["text"].setText(title)
			else:
				self["text"].setText(title)
		elif text:
			self["text"].setText(_(text))
		self["description"] = Label()
		self.list = []
		self.summarylist = []
		if keys is None:
			self.__keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "red", "green", "yellow", "blue"] + (len(list) - 14) * [""]
		else:
			self.__keys = keys + (len(list) - len(keys)) * [""]

		self.keymap = {}
		if self.reorderConfig:
			self.config_type = getattr(config.misc.pluginlist, self.reorderConfig)
			if self.config_type.value:
				prev_list = [i for i in zip(list, self.__keys)]
				new_list = []
				for x in self.config_type.value.split(","):
					for entry in prev_list:
						if entry[0][0] == x:
							new_list.append(entry)
							prev_list.remove(entry)
				list = [i for i in zip(*(new_list + prev_list))]
				list, self.__keys = list[0], list[1]
				number = 1
				new_keys = []
				for x in self.__keys:
					if (not x or x.isdigit()) and number <= 10:
						new_keys.append(str(number % 10))
						number += 1
					else:
						new_keys.append(not x.isdigit() and x or "")
				self.__keys = new_keys
		colors = {"red": self.keyRed, "green": self.keyGreen, "yellow": self.keyYellow, "blue": self.keyBlue}
		colorActions = {}
		selectionActions = {}
		for i, x in enumerate(list):
			if x:
				key = str(self.__keys[i])
				self.list.append(ChoiceEntryComponent(key=key, text=x))
				if self.__keys[i] != "":
					self.keymap[self.__keys[i]] = list[i]
					if key in colors:
						colorActions[key] = (colors[key], _("Select item directly"))
					else:
						selectionActions[key] = (self.keyNumberGlobal, _("Select item directly"))
				self.summarylist.append((self.__keys[i], x[0]))

		self["list"] = ChoiceList(list=self.list, selection=selection)
		self["summary_list"] = StaticText()
		self["summary_selection"] = StaticText()
		if self.updateSummary not in self["list"].onSelectionChanged:
			self["list"].onSelectionChanged.append(self.updateSummary)
		self.updateSummary()

		self["okActions"] = HelpableActionMap(self, ["OkCancelActions"], {"ok": (self.keySelect, _("Select the current item")), }, prio=0, description=_("Selection Actions"))
		self["cancelActions"] = HelpableActionMap(self, ["OkCancelActions"], {"cancel": (self.cancel, _("Cancel the current action and exit")), }, prio=0, description=_("Cancel Actions"))
		self["colorActions"] = HelpableActionMap(self, ["ColorActions"], colorActions, prio=-1, description=_("Selection Actions"))
		self["selectionActions"] = HelpableNumberActionMap(self, ["NumberActions"], selectionActions, prio=-1, description=_("Selection Actions"))

		self["navigationActions"] = HelpableActionMap(self, ["DirectionActions"],
		{
			"up": (self.up, _("Move selection to the next item up")),
			"down": (self.down, _("Move selection to the next item down")),
			"left": (self.pageUp, _("Move selection one page up")),
			"right": (self.pageDown, _("Move selection one page down")),
		}, prio=-1, description=_("Navigation Actions"))
		self["navigationActions"].setEnabled(len(list) > 1)

		self["sortActions"] = HelpableActionMap(self, ["DirectionActions", "MenuActions"],
		{
			"menu": (self.setDefaultChoiceList, _("Reset the list order to the default")),
			"shiftDown": (self.additionalMoveDown, _("Move the current item down the list")),
			"shiftUp": (self.additionalMoveUp, _("Move the current item up the list")),
		}, prio=-1, description=_("List Sort Actions"))
		self["sortActions"].setEnabled(reorderConfig and len(list) > 1)

	def autoResize(self):
		margin = applySkinFactor(4)
		separator = applySkinFactor(10)
		desktop_w = getDesktop(0).size().width()
		desktop_h = getDesktop(0).size().height()
		itemheight = self["list"].getItemHeight()
		textsize = (0, 0)
		if self["text"].text:
			textsize = self["text"].getSize()
			if textsize[0] < textsize[1]:
				textsize = (textsize[1], textsize[0] + 10)
		listLen = len(self.list)
		listMaxItems = int(desktop_h * 0.8 - textsize[1]) // itemheight
		scrollbar = self["list"].instance.getScrollbarWidth() + 5 if listLen > listMaxItems else 0
		listWidth = int(min(self["list"].instance.getMaxItemTextWidth() + scrollbar, desktop_w * 0.9))
		count = min(listLen, listMaxItems)
		if textsize[1] and textsize[0] < listWidth:
			textsize = (listWidth, textsize[1])
		width = max(listWidth, textsize[0])
		listsize = (width, listMaxItems * itemheight)
		listPos = separator + textsize[1] if textsize[1] > 0 else margin
		# resize label
		self["text"].instance.resize(eSize(*textsize))
		self["text"].instance.move(ePoint(margin, margin))
		# move list
		self["list"].instance.resize(eSize(*listsize))
		self["list"].instance.move(ePoint(margin, listPos))

		wsizex = margin * 2 + width
		wsizey = listPos + (count * itemheight) + margin
		wsize = (wsizex, wsizey)
		self.instance.resize(eSize(*wsize))

		# center window
		self.instance.move(ePoint((desktop_w - wsizex) // 2, (desktop_h - wsizey) // 2))

	def pageUp(self):
		if self.list:
			self["list"].pageUp()
			if self["list"].getCurrent()[0][0] == ChoiceList.SPACER:  # if we landed on a spacer skip to previous item
				self.up()

	def pageDown(self):
		if self.list:
			self["list"].pageDown()
			if self["list"].getCurrent()[0][0] == ChoiceList.SPACER:  # if we landed on a spacer skip to next item
				self.down()

	def up(self):
		if self.list:
			while True:
				self["list"].up()
				if self["list"].getCurrent()[0][0] != ChoiceList.SPACER or self["list"].getSelectionIndex() == 0:  # if we didn't land on a spacer stop loop
					break

	def down(self):
		if self.list:
			while True:
				self["list"].down()
				if self["list"].getCurrent()[0][0] != ChoiceList.SPACER or self["list"].getSelectionIndex() == len(self.list) - 1:  # if we didn't land on a spacer stop loop
					break

	# runs a number shortcut
	def keyNumberGlobal(self, number):
		self.goKey(str(number))

	# runs the current selected entry
	def keySelect(self):
		cursel = self["list"].getCurrent()
		if cursel:
			self.goEntry(cursel[0])
		else:  # list is empty
			self.cancel()

	# runs a specific entry
	def goEntry(self, entry):
		if self.isCallbackList:
			if entry and len(entry) > 1 and entry[1]:
				# stuff the selected item's callback function into the dialog's session callback
				# (callers shouldn't need to be using the session callback)
				# This allows the ChoiceBox to close itself and schedule the selected item's
				# callback to happen on the next poll execution
				self.callback = boundFunction(*entry[1:])
			self.close()
		elif entry and len(entry) > 3 and isinstance(entry[1], str) and entry[1] == "CALLFUNC":
			arg = entry[3]
			entry[2](arg)
		elif entry and len(entry) > 2 and isinstance(entry[1], str) and entry[1] == "CALLFUNC":
			entry[2](None)
		else:
			self.close(entry)

	# lookups a key in the keymap, then runs it
	def goKey(self, key):
		if key in self.keymap:
			entry = self.keymap[key]
			self.goEntry(entry)

	# runs a color shortcut
	def keyRed(self):
		self.goKey("red")

	def keyGreen(self):
		self.goKey("green")

	def keyYellow(self):
		self.goKey("yellow")

	def keyBlue(self):
		self.goKey("blue")

	def updateSummary(self):
		curpos = self["list"].getSelectionIndex()
		self.displayDescription(curpos)
		summarytext = ""
		for i, entry in enumerate(self.summarylist):
			if curpos - 2 < i < curpos + 5:
				if i == curpos:
					summarytext += ">"
					self["summary_selection"].setText(entry[1])
				else:
					summarytext += entry[0]
				summarytext += ' ' + entry[1] + '\n'
		self["summary_list"].setText(summarytext)

	def displayDescription(self, curpos=0):
		if self.list and len(self.list[curpos][0]) > 2 and isinstance(self.list[curpos][0][2], str):
			self["description"].setText(self.list[curpos][0][2])
		else:
			self["description"].setText("")

	def cancel(self):
		if self.updateSummary in self["list"].onSelectionChanged:
			self["list"].onSelectionChanged.remove(self.updateSummary)
		self.close(None)

	def setDefaultChoiceList(self):
		if self.reorderConfig:
			if len(self.list) > 0 and self.config_type.value != "":
				self.session.openWithCallback(self.setDefaultChoiceListCallback, MessageBox, _("Sort list to default and exit?"), MessageBox.TYPE_YESNO)
			else:
				self.session.open(MessageBox, _("The list is already sorted to the default."), MessageBox.TYPE_INFO, timeout=5)

	def setDefaultChoiceListCallback(self, answer):
		if answer:
			self.config_type.value = self.config_type.default
			self.config_type.save()
			self.cancel()

	def additionalMoveUp(self):
		if self.reorderConfig:
			self.additionalMove(-1)

	def additionalMoveDown(self):
		if self.reorderConfig:
			self.additionalMove(1)

	def additionalMove(self, direction):
		if len(self.list) > 1:
			currentIndex = self["list"].getSelectionIndex()
			swapIndex = (currentIndex + direction) % len(self.list)
			if currentIndex == 0 and swapIndex != 1:
				self.list = self.list[1:] + [self.list[0]]
			elif swapIndex == 0 and currentIndex != 1:
				self.list = [self.list[-1]] + self.list[:-1]
			else:
				self.list[currentIndex], self.list[swapIndex] = self.list[swapIndex], self.list[currentIndex]
			self["list"].l.setList(self.list)
			if direction == 1:
				self["list"].down()
			else:
				self["list"].up()
			self.config_type.value = ",".join(x[0][0] for x in self.list)
			self.config_type.save()


# This choicebox overlays the current screen
class PopupChoiceBox(ChoiceBox):
	def __init__(self, session, title="", list=None, keys=None, selection=0, skin_name=None, closeCB=None):
		ChoiceBox.__init__(self, session, title, None, keys, selection, skin_name, callbackList=list)
		self.closeCB = closeCB

	def show(self):
		for action in ("okActions", "cancelActions", "colorActions", "selectionActions", "navigationActions"):
			self[action].execBegin()
		ChoiceBox.show(self)

	def hide(self):
		for action in ("okActions", "cancelActions", "colorActions", "selectionActions", "navigationActions"):
			self[action].execEnd()
		ChoiceBox.hide(self)

	def goEntry(self, entry):
		self.cancel()
		if entry and len(entry) > 1:
			entry[1](*entry[2:])

	def cancel(self):
		# doClose will remove all properties so grab the callback function first
		cb = self.closeCB
		self.doClose()
		cb()
