from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.ScrollLabel import ScrollLabel
from Components.Sources.StaticText import StaticText
from Components.SystemInfo import BoxInfo
from Screens.Screen import Screen, ScreenSummary

class AboutBoxInfo(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle(_("BoxInfo"))
		self.skinName = "AboutOE"

		self["key_red"] = Button(_("Close"))
		self["actions"] = ActionMap(["SetupActions", "NavigationActions"],
		{
			"cancel": self.close,
			"up": self.pageUp,
			"down": self.pageDown,
			"left": self.pageUp,
			"right": self.pageDown,
			"pageUp": self.pageUp,
			"pageDown": self.pageDown,
		}, -2)

		BIlist = []
		for item in BoxInfo.getEnigmaInfoList():
			value = str(BoxInfo.getItem(item))
			for x in ("http://", "https://"):  # Trim URLs to domain only
				if value.startswith(x):
					value = value.split(x)[1].split('/')[0] + " [...]"
					break
			BIlist.append("%s:\t %s\n" % (item, value))
		self["AboutScrollLabel"] = ScrollLabel(''.join(BIlist))

	def pageUp(self):
		self["AboutScrollLabel"].pageUp()

	def pageDown(self):
		self["AboutScrollLabel"].pageDown()

	def createSummary(self):
		return AboutBoxInfoSummary


class AboutBoxInfoSummary(ScreenSummary):
	def __init__(self, session, parent):
		ScreenSummary.__init__(self, session, parent=parent)
		self.skinName = "AboutSummary"
		self["AboutText"] = StaticText(_("AboutBoxInfo"))
		