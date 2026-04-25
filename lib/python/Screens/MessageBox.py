from enigma import eTimer, ePoint, eSize, getDesktop

from Components.ActionMap import ActionMap, HelpableNumberActionMap
from Components.config import config
from Components.Label import Label
from Components.MenuList import MenuList
from Components.Pixmap import MultiPixmap
from Components.Sources.StaticText import StaticText
from Screens.HelpMenu import HelpableScreen
from Screens.Screen import Screen
from Tools.decorators import classproperty
from Session import SessionObject
from skin import parseScale, applySkinFactor


class MessageBox(Screen, HelpableScreen):
	TYPE_YESNO = 0
	TYPE_INFO = 1
	TYPE_WARNING = 2
	TYPE_ERROR = 3
	TYPE_MESSAGE = 4

	def __init__(self, session, text, type=TYPE_YESNO, timeout=0, close_on_any_key=False, default=True, enable_input=True, msgBoxID=None, picon=True, simple=False, wizard=False, list=None, skin_name=None, timeout_default=None, title=None):
		Screen.__init__(self, session, mandatoryWidgets=["list", "text"])
		HelpableScreen.__init__(self)
		self.TYPE_PREFIX = {self.TYPE_YESNO: _("Question"), self.TYPE_INFO: _("Information"), self.TYPE_WARNING: _("Warning"), self.TYPE_ERROR: _("Error"), self.TYPE_MESSAGE: _("Message")}
		self.text = text
		self.type = type if type in self.TYPE_PREFIX else self.TYPE_MESSAGE
		self.timeout = int(timeout)
		self.close_on_any_key = close_on_any_key
		self.msgBoxID = msgBoxID
		self["icon"] = MultiPixmap()
		self["icon"].hide()
		self.picon = picon
		if picon:
			self["icon"].show()
		self.skinName = ["MessageBox"]
		if simple:
			self.skinName = ["MessageBoxSimple"] + self.skinName
		if wizard:
			self["rc"] = MultiPixmap()
			self["rc"].setPixmapNum(config.misc.rcused.value)
			self.skinName = ["MessageBoxWizard"]
		if isinstance(skin_name, str):
			self.skinName = [skin_name] + self.skinName
		if not list:
			list = []
		if type == self.TYPE_YESNO:
			if list:
				self.list = list
			elif default:
				self.list = [(_("Yes"), True), (_("No"), False)]
			else:
				self.list = [(_("No"), False), (_("Yes"), True)]
		else:
			self.list = []
		self.timeout_default = timeout_default
		self.baseTitle = title
		self.activeTitle = None
		self.timerRunning = False
		if timeout > 0:
			self.timerRunning = True
		self["text"] = Label(self.text)
		self["Text"] = StaticText(self.text)  # Used by summary screens
		self["selectedChoice"] = StaticText()  # Used by summary screens
		self["list"] = MenuList(self.list)
		if self.list:
			self["selectedChoice"].setText(self["list"].getCurrent()[0])
		else:
			self["list"].hide()
		self["key_help"] = StaticText(_("HELP"))
		self.timer = eTimer()
		self.timer.callback.append(self.processTimer)
		self.number = 0
		self.nextNumberTimer = eTimer()
		self.nextNumberTimer.callback.append(self.ok)
		if self.layoutFinished not in self.onLayoutFinish:
			self.onLayoutFinish.append(self.layoutFinished)
		if enable_input:
			self["actions"] = HelpableNumberActionMap(self, ["MsgBoxActions", "DirectionActions", "NumberActions",],
			{
				"cancel": (self.cancel, _("Cancel the selection")),
				"ok": (self.ok, _("Accept the current selection"))} | (({
				"alwaysOK": (self.alwaysOK, _("Always select OK")),
				"up": (self.up, _("Move up a line")),
				"down": (self.down, _("Move down a line")),
				"left": (self.left, _("Move up a page")),
				"right": (self.right, _("Move down a page"))} | {
				str(i): (self.keyNumberGlobal, _("Direct item selection")) for i in range(10)}
				) if self.list else {}),
			prio=-20, description=_("MessageBox Actions"))

	def layoutFinished(self):
		self["icon"].setPixmapNum(self.type)
		prefix = self.TYPE_PREFIX.get(self.type, self.TYPE_PREFIX[self.TYPE_MESSAGE])
		if self.baseTitle is None:
			title = self.getTitle()
			if title:
				if "%s" in title:
					self.baseTitle = title % prefix
				else:
					self.baseTitle = title
			else:
				self.baseTitle = prefix
		elif "%s" in self.baseTitle:
			self.baseTitle = self.baseTitle % prefix
		self.setTitle(self.baseTitle)
		if self.timeout > 0:
			print("[MessageBox] Timeout set to %d seconds." % self.timeout)
			self.timer.start(25)

	def processTimer(self):
		# Check if the title has been externally changed and if so make it the dominant title.
		if self.activeTitle is None:
			self.activeTitle = self.getTitle()
			if "%s" in self.activeTitle:
				self.activeTitle = self.activeTitle % self.TYPE_PREFIX.get(self.type, self.TYPE_PREFIX[self.TYPE_MESSAGE])
		if self.baseTitle != self.activeTitle:
			self.baseTitle = self.activeTitle
		if self.timeout > 0:
			if self.baseTitle:
				self.setTitle("%s (%d)" % (self.baseTitle, self.timeout))
			self.timer.start(1000)
			self.timeout -= 1
		else:
			self.stopTimer("Timeout!")
			if self.timeout_default is not None:
				self.close(self.timeout_default)
			else:
				self.ok()

	def stopTimer(self, reason):
		print("[MessageBox] %s" % reason)
		self.timer.stop()
		self.timeout = 0
		if self.baseTitle is not None:
			self.setTitle(self.baseTitle)

	def getListItemHeight(self):
		defaultItemHeight = 25  # if no itemHeight is present in the skin
		if self.list and hasattr(self["list"], "skinAttributes") and isinstance(self["list"].skinAttributes, list):
			for (attrib, value) in self["list"].skinAttributes:
				if attrib == "itemHeight":
					itemHeight = parseScale(value)  # if value does not parse (due to bad syntax in skin), itemHeight will be 0
					return itemHeight if itemHeight else defaultItemHeight
		return defaultItemHeight  # if itemHeight not in skinAttributes

	def getPixmapSize(self):
		defaultPixmapWidth = (53, 53)
		try:  # protect from skin errors
			return self["icon"].getSize()
		except Exception as err:
			print("[MessageBox] defaultPixmapWidth, %s: '%s'" % (type(err).__name__, err))
		return defaultPixmapWidth

	def autoResize(self):
		margin = applySkinFactor(4)
		separator = applySkinFactor(10)
		desktop_w = getDesktop(0).size().width()
		desktop_h = getDesktop(0).size().height()
		pixmapWidth = 0
		pixmapHeight = 0
		pixmapMargin = 0
		if self.picon:
			pixmapWidth, pixmapHeight = self.getPixmapSize()
			pixmapMargin = applySkinFactor(4)
		textsize = (0, 0)
		if self["text"].text:
			textsize = self["text"].getSize()
			if textsize[0] < textsize[1]:
				textsize = (textsize[1], textsize[0] + 10)
		listLen = len(self.list)
		itemheight = self.getListItemHeight()
		listMaxItems = int((desktop_h * 0.8 - textsize[1]) // itemheight)
		scrollbar = self["list"].instance.getScrollbarWidth() + 5 if listLen > listMaxItems else 0
		listWidth = int(min(self["list"].instance.getMaxItemTextWidth() + scrollbar, desktop_w * 0.9))
		count = min(listLen, listMaxItems)
		if textsize[1]:
			textsize = (textsize[0] + applySkinFactor(10), textsize[1] + applySkinFactor(2))
			if textsize[0] < listWidth:
				textsize = (listWidth, textsize[1])
		width = max(listWidth, textsize[0])
		listsize = (width, listMaxItems * itemheight)
		listPos = separator + (textsize[1] if textsize[1] > 0 else 0)
		# resize label
		self["text"].instance.resize(eSize(*textsize))
		self["text"].instance.move(ePoint(margin + pixmapWidth + pixmapMargin, 0))
		# move list
		self["list"].instance.resize(eSize(*listsize))
		self["list"].instance.move(ePoint(margin + pixmapWidth + pixmapMargin, listPos))

		wsizex = margin * 2 + width + pixmapWidth + pixmapMargin
		wsizey = max(listPos + (count * itemheight) + margin, pixmapMargin * 2 + pixmapHeight)
		wsize = (wsizex, wsizey)
		self.instance.resize(eSize(*wsize))

		# center window
		self.instance.move(ePoint((desktop_w - wsizex) // 2, (desktop_h - wsizey) // 2))

	def cancel(self):
		self.close(False)

	def ok(self):
		if self.number:
			self["list"].moveToIndex(self.number - 1)
			self.resetNumberKey()
		if current := self["list"].getCurrent():
			self.close(current[1])
		else:
			self.close(True)

	def alwaysOK(self):
		# Just returning True in this function would be wrong because
		# we don't know the return value of the item is True, i.e. it
		# could be an object or variable that our callback is waiting
		# to receive.
		if self.list:
			for x in self.list:
				if x[0].lower() in (_('yes'), _('true')):
					self.close(x[1])
					break
			else:
				if any([x[1] is True for x in self.list]):   # only close if True is an option
					self.close(True)
		else:
			self.close(True)

	def up(self):
		self.move(self["list"].instance.moveUp)

	def down(self):
		self.move(self["list"].instance.moveDown)

	def left(self):
		self.move(self["list"].instance.pageUp)

	def right(self):
		self.move(self["list"].instance.pageDown)

	def move(self, direction):
		if self.timeout > 0:
			self.stopTimer("Timeout stopped by user input!")
		if self.close_on_any_key:
			self.close(True)
		self["list"].instance.moveSelection(direction)
		if self.list:
			self["selectedChoice"].setText(self["list"].getCurrent()[0])

	def __repr__(self):
		return "%s(%s)" % (str(type(self)), self.text if hasattr(self, "text") else "<title>")

	def getListWidth(self):
		return self["list"].instance.getMaxItemTextWidth()

	def keyNumberGlobal(self, number):
		if self.list:
			listlength = len(self.list)
			self.number = self.number * 10 + number
			if self.number and self.number <= listlength:
				if number * 10 > listlength or self.number >= 10:
					self.ok()
				else:
					self.nextNumberTimer.start(1500, True)
			else:
				self.resetNumberKey()

	def resetNumberKey(self):
		self.nextNumberTimer.stop()
		self.number = 0


class ModalMessageBox:
	_instance = None

	def __init__(self, session):
		if ModalMessageBox._instance:
			print("[ModalMessageBox] Error: Only one ModalMessageBox instance is allowed!")
		else:
			self.session = session
			ModalMessageBox._instance = self
			self.dialog = None
			self.previousDialog = None
			self.previousEnabledActions = []

	def showMessageBox(self, text="", timeout=0, list=None, default=True, close_on_any_key=False, timeout_default=None, windowTitle=None, msgBoxID=None, typeIcon=MessageBox.TYPE_YESNO, enable_input=True, callback=None, title=None, type=None):
		if self.dialog:
			return  # sanity, nothing should be calling this with the dialog already open, so ignore it
		self.disableParentActions()
		title = title or windowTitle  # windowTitle is not openvix, but is retained for compatability
		self.dialog = self.session.instantiateDialog(MessageBox, text=text, type=type or typeIcon, timeout=timeout, close_on_any_key=close_on_any_key, default=default, enable_input=enable_input, msgBoxID=msgBoxID, list=list, skin_name="MessageBoxModal", timeout_default=timeout_default, title=title)
		self.dialog.setAnimationMode(0)
		self.callback = callback
		for x in self.dialog:
			if isinstance(self.dialog[x], ActionMap):
				self.dialog[x].execBegin()
		self.dialog.close = self.close
		self.dialog.show()

	def close(self, *retVal):
		if self.dialog:
			if self.callback and callable(self.callback):
				self.callback(*retVal)
			for x in self.dialog:
				if isinstance(self.dialog[x], ActionMap):
					self.dialog[x].execEnd()
			self.dialog.doClose()
			self.dialog = None
		self.enableParentActions()
		ModalMessageBox._instance = None

	def disableParentActions(self):
		self.previousDialog = self.session.current_dialog
		for x in self.previousDialog:
			if isinstance(self.previousDialog[x], ActionMap) and self.previousDialog[x].enabled:
				self.previousEnabledActions.append(x)
				self.previousDialog[x].setEnabled(False)

	def enableParentActions(self):
		if self.previousDialog:
			for x in self.previousEnabledActions:
				if x in self.previousDialog:  # sanity
					self.previousDialog[x].setEnabled(True)
			self.previousEnabledActions.clear()
			self.previousDialog = None

	@classproperty
	def instance(cls):
		if cls._instance:
			return cls._instance
		else:
			cls._instance = cls(SessionObject().session)
			return cls._instance
