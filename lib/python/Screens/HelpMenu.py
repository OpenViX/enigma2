from __future__ import print_function
from __future__ import absolute_import

from Screens.Screen import Screen
from Components.Label import Label
from Components.ActionMap import ActionMap
from Components.HelpMenuList import HelpMenuList
from Components.Sources.StaticText import StaticText
from Screens.Rc import Rc


class HelpMenu(Screen, Rc):
	def __init__(self, session, list):
		Screen.__init__(self, session)
		self.setup_title = _("Help")
		Screen.setTitle(self, self.setup_title)
		self.onSelChanged = []
		self["list"] = HelpMenuList(list, self.close)
		self["list"].onSelChanged.append(self.SelectionChanged)
		Rc.__init__(self)
		self["long_key"] = Label("")

		self["actions"] = ActionMap(["WizardActions"],
		{
			"ok": self["list"].ok,
			"back": self.close,
		}, -1)

		self.onLayoutFinish.append(self.SelectionChanged)

	def SelectionChanged(self):
		self.clearSelectedKeys()
		selection = self["list"].getCurrent()
		if selection:
			selection = selection[3]
		#arrow = self["arrowup"]
		print("[HelpMenu] selection:", selection)

		longText = ""
		if selection and len(selection) > 1:
			if selection[1] == "SHIFT":
				self.selectKey("SHIFT")
			elif selection[1] == "long":
				longText = _("Long key press")
		self["long_key"].setText(longText)

		self.selectKey(selection[0])
		#if selection is None:
		print("[HelpMenu] select arrow")
		#	arrow.moveTo(selection[1], selection[2], 1)
		#	arrow.startMoving()
		#	arrow.show()


class HelpableScreen:
	def __init__(self):
		self["helpActions"] = ActionMap(["HelpActions"],
			{
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
