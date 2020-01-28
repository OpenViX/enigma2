from Screens.Screen import Screen
from Components.Label import Label
from enigma import eTimer, getDesktop

class SubtitleDisplay(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self['notification'] = Label("")
		self['notification'].hide()

	def showMessage(self, text, hideScreen):
		label = self['notification']
		label.instance.setNoWrap(1)
		label.setText(text)
		label.instance.setHAlign(1)
		label.instance.setVAlign(1)
		size = label.getSize()
		label.resize(size[0]+40, size[1])
		label.move((getDesktop(0).size().width()-size[0]-40) // 2, getDesktop(0).size().height() - size[1] - 30)
		label.show()
		self.show()
		self.hideTimer = eTimer()
		self.hideTimer.callback.append(self.hideScreen if hideScreen else self.hideMessage)
		self.hideTimer.start(2000, True)

	def hideMessage(self):
		self['notification'].hide()

	def hideScreen(self):
		self['notification'].hide()
		self.hide()
