from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.ScrollLabel import ScrollLabel


class TextBox(Screen):
	def __init__(self, session, text="", title=None):
		Screen.__init__(self, session)

		self.text = text
		self["text"] = ScrollLabel(self.text)

		self["key_red"] = Button(_("Close"))
		
		self["actions"] = ActionMap(["SetupActions", "NavigationActions"],
				{
					"cancel": self.close,
					"ok": self.close,
					"up": self["text"].pageUp,
					"down": self["text"].pageDown,
					"left": self["text"].pageUp,
					"right": self["text"].pageDown,
					"pageUp": self["text"].pageUp,
					"pageDown": self["text"].pageDown,
				}, -1)

		if title:
			self.setTitle(title)
