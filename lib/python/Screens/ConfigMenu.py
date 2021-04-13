from __future__ import absolute_import

from Components.ConfigList import ConfigList
from Components.ActionMap import ActionMap
from Screens.Screen import Screen


class ConfigMenu(Screen):
	#create a generic class for view/edit settings
	#all stuff come from xml file
	#configtype / datasource / validate-call / ...

	def __init__(self, session):
		Screen.__init__(self, session)

		self["actions"] = ActionMap(["OkCancelActions"],
			{
				"ok": self.okbuttonClick,
				"cancel": self.close
			})


class configTest(Screen):

	def __init__(self, session):
		Screen.__init__(self, session)

		self["config"] = ConfigList(
			[
				configEntry("HKEY_LOCAL_ENIGMA/IMPORTANT/USER_ANNOYING_STUFF/SDTV/FLASHES/GREEN"),
				configEntry("HKEY_LOCAL_ENIGMA/IMPORTANT/USER_ANNOYING_STUFF/HDTV/FLASHES/GREEN"),
			])

		self["actions"] = ActionMap(["OkCancelActions"],
			{
				"ok": self["config"].toggle,
				"cancel": self.close
			})
