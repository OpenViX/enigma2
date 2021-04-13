from __future__ import absolute_import

from enigma import eButton

from Components.GUIComponent import GUIComponent
from Components.VariableText import VariableText


class Button(VariableText, GUIComponent):
	def __init__(self, text="", onClick=None):
		if not onClick:
			onClick = []
		GUIComponent.__init__(self)
		VariableText.__init__(self)
		self.setText(text)
		self.onClick = onClick

	def push(self):
		for x in self.onClick:
			x()
		return 0

	def disable(self):
		pass

	def enable(self):
		pass

# fake Source methods:
	def connectDownstream(self, downstream):
		pass

	def checkSuspend(self):
		pass

	def disconnectDownstream(self, downstream):
		pass

	GUI_WIDGET = eButton

	def postWidgetCreate(self, instance):
		instance.setText(self.text)
		instance.selected.get().append(self.push)

	def preWidgetRemove(self, instance):
		instance.selected.get().remove(self.push)
