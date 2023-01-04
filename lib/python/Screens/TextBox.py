from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Sources.StaticText import StaticText
from Components.ScrollLabel import ScrollLabel


class TextBox(Screen):
	def __init__(self, session, text="", title=None, skin_name=None, label=None):
		Screen.__init__(self, session)
		if isinstance(skin_name, str):
			self.skinName = [skin_name, "TextBox"]
		self.text = text
		self.label = "text"
		if isinstance(label, str):
			self.label = label
		self[self.label] = ScrollLabel(self.text)

		if "key_red" not in self:
			self["key_red"] = StaticText(_("Cancel"))
		
		self["actions"] = ActionMap(["SetupActions", "NavigationActions"],
				{
					"cancel": self.close,
					"ok": self.close,
					"up": self[self.label].pageUp,
					"down": self[self.label].pageDown,
					"left": self[self.label].pageUp,
					"right": self[self.label].pageDown,
					"pageUp": self[self.label].pageUp,
					"pageDown": self[self.label].pageDown,
				}, -1)

		if title:
			self.setTitle(title)
