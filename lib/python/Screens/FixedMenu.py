from Components.ActionMap import ActionMap
from Components.Sources.List import List
from Screens.Screen import Screen
from Tools.Hex2strColor import ColorizeText


class FixedMenu(Screen, ColorizeText):
	def okbuttonClick(self):
		selection = self["menu"].getCurrent()
		if selection and len(selection) > 1 and callable(selection[1]):
			selection[1]()

	def __init__(self, session, title, list):
		Screen.__init__(self, session)
		ColorizeText.__init__(self, session, "FixedMenuColors")

		self["menu"] = List(list)

		self.watcher = [None]
		
		if self.selectionChanged not in self["menu"].onSelectionChanged:
			self["menu"].onSelectionChanged.append(self.selectionChanged)

		self["actions"] = ActionMap(["OkCancelActions"],
			{
				"ok": self.okbuttonClick,
				"cancel": self.close,
			}, prio=-5)  # noqa: E123

		self.title = title

	def selectionChanged(self):
		i = self["menu"].getIndex()
		entries = self["menu"].list
		n = len(entries)
		self.watcher.append(i)
		self.watcher = self.watcher[-2:]
		if self.watcher[0] is None:
			return
		previous, current = self.watcher
		step = (current - previous + n // 2) % n - n // 2
		print("[FixedMenu] selectionChanged, step", step)
		if step:
			is_selectable = len(entries[i]) > 1 and callable(entries[i][1])
			if not is_selectable:
				self["menu"].setIndex((i + step) % n)

