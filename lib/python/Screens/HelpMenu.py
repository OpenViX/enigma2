from Screens.Screen import Screen
from Tools.KeyBindings import keyBindings
from Tools.BoundFunction import boundFunction
from Components.Label import Label
from Components.ActionMap import ActionMap
from Components.Sources.HelpMenuList import HelpMenuList
from Components.Sources.StaticText import StaticText
from Screens.Rc import Rc
from enigma import eActionMap
from sys import maxsize

class HelpMenu(Screen, Rc):
	helpText = "\n\n".join([
		_("Help Screen"),
		_("Brief help information for buttons in your current context."),
		_("Navigate up/down with UP/DOWN buttons and page up/down with LEFT/RIGHT. EXIT to return to the help screen. OK to perform the action described in the currently highlighted help."),
		_("Other buttons will jump to the help for that button, if there is help."),
		_("If an action is user-configurable, its help entry will be flagged (C)"),
		_("A highlight on the remote control image shows which button the help refers to. If more than one button performs the indicated function, more than one highlight will be shown. Text below the list indicates whether the function is for a long press of the button(s)."),
		_("The order and grouping of the help information list can be controlled using MENU>Setup>User Interface>Settings>Sort order for help screen.")])

	def __init__(self, session, list):
		Screen.__init__(self, session)
		self.setup_title = _("Help")
		Screen.setTitle(self, self.setup_title)
		Rc.__init__(self)
		self["list"] = HelpMenuList(list, self.close, rcPos=self.getRcPositions())
		self["longshift_key0"] = Label("")
		self["longshift_key1"] = Label("")
		self["key_help"] = StaticText(_("HELP"))

		self["actions"] = ActionMap(["WizardActions"], {
			"ok": self["list"].ok,
			"back": self.close,
		}, -1)

		# Wildcard binding with slightly higher priority than
		# the wildcard bindings in
		# InfoBarGenerics.InfoBarUnhandledKey, but with a gap
		# so that other wildcards can be interposed if needed.

		self.onClose.append(self.doOnClose)
		eActionMap.getInstance().bindAction('', maxsize - 100, self["list"].handleButton)

		# Ignore keypress breaks for the keys in the
		# ListboxActions context.

		# Catch  ListboxActions on CH+/-, FF & REW and
		# divert them to "jump to help for button" in the Help
		# screen.  If CH+/-, FF & REW are to be allowed for list
		# navigation, replace their key mappings with ones that
		# simply have mapto="ignore" flags="b".

		# If that's done, then the help text for the HelpMenu
		# screen should be changed to indicate that those buttons
		# are used for navigation.

		intercepts = self.makeButtonIntercepts()

		# Ignore other keypress breaks for keys in the
		# ListboxActions context.

		intercepts["ignore"] = lambda: 1

		self["listboxFilterActions"] = ActionMap(["ListboxHelpMenuActions"], intercepts, prio=-1)

		self["helpActions"] = ActionMap(["HelpActions"], {
			"displayHelp": self.showHelp,
		})

		self.onLayoutFinish.append(self.doOnLayoutFinish)

	def doOnLayoutFinish(self):
		self["list"].onSelectionChanged.append(self.SelectionChanged)
		self.SelectionChanged()

	def doOnClose(self):
		eActionMap.getInstance().unbindAction('', self["list"].handleButton)
		self["list"].onSelectionChanged.remove(self.SelectionChanged)

	def SelectionChanged(self):
		self.clearSelectedKeys()
		selection = self["list"].getCurrent()

		longText = [""] * 2
		longButtons = []
		shiftButtons = []
		if selection:
			for button in selection[3]:
				if len(button) > 1:
					if button[1] == "SHIFT":
						self.selectKey("SHIFT")
						shiftButtons.append(button[0])
					elif button[1] == "long":
						longText[0] = _("Long key press")
						longButtons.append(button[0])
				self.selectKey(button[0])

			textline = 0
			if len(selection[3]) > 1:
				if longButtons:
					print("[HelpMenu] SelectionChanged", longButtons)
					longText[textline] = _("Long press: ") + ', '.join(longButtons)
					textline += 1
				if shiftButtons:
					longText[textline] = _("SHIFT: ") + ', '.join(shiftButtons)

		self["longshift_key0"].setText(longText[0])
		self["longshift_key1"].setText(longText[1])

	def makeButtonIntercepts(self):
		intercepts = {}
		for k, v in ((_k, _v) for _k, _v in keyBindings.items() if _k[0] == "ListboxHelpMenuActions" and _k[1] != "ignore"):
			for b in (_b for _b in v if not _b[0] & 0x8000):
				for f in (_f for _f in range(4) if 1 << _f & b[2]):
					intercepts[k[1]] = boundFunction(self.interceptButton, b[0], f)
		return intercepts

	def interceptButton(self, key, flag):
		from Screens.InfoBar import InfoBar
		res = self["list"].handleButton(key, flag)

		# The normal UnhandledKey procedure can't be used here
		# because we can't return 0 here, because that would fall
		# through to the native bindings, so call
		# InfoBar.instance.actionB() directly to indicate that the
		# button has no action on this flag.

		if not res and res is not None and InfoBar.instance:
			InfoBar.instance.actionB(key, flag)

		# Always return 1 to stop fallthrough to native bindings
		return 1

	def showHelp(self):
		# Import deferred so that MessageBox's import of HelpMenu doesn't cause an import loop
		from Screens.MessageBox import MessageBox
		self.session.open(MessageBox, _(HelpMenu.helpText), type=MessageBox.TYPE_INFO)


class HelpableScreen:
	def __init__(self):
		self["helpActions"] = ActionMap(["HelpActions"], {
			"displayHelp": self.showHelp,
		})
		self["key_help"] = StaticText(_("HELP"))

	def showHelp(self):
		try:
			if self.secondInfoBarScreen and self.secondInfoBarScreen.shown:
				self.secondInfoBarScreen.hide()
		except:
			pass
		self.session.openWithCallback(self.callHelpAction, HelpMenu, self.helpList)

	def callHelpAction(self, *args):
		if args:
			(actionmap, context, action) = args
			actionmap.action(context, action)
