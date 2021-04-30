from Screens.Screen import Screen
from Components.Label import Label
from enigma import eTimer, getDesktop, eActionMap, gFont
from Components.ActionMap import ActionMap
from sys import maxint
import skin


class SubtitleDisplay(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		eActionMap.getInstance().bindAction('', -maxint - 1, self.__keypress)

		self.messageShown = False
		self['message'] = Label()
		self['message'].hide()

		self.onClose.append(self.__close)
		self.onLayoutFinish.append(self.__layoutFinished)

	def __close(self):
		eActionMap.getInstance().unbindAction('', self.__keypress)

	def __layoutFinished(self):
		# Not expecting skins to contain this element
		label = self['message']
		label.instance.setFont(gFont("Regular", 50))
		label.instance.setZPosition(1)
		label.instance.setNoWrap(1)
		label.instance.setHAlign(1)
		label.instance.setVAlign(1)

	def __keypress(self, key, flag):
		# Releasing the subtitle button after a long press unintentionally pops up the subtitle dialog,
		# This blocks it without causing issues for anyone that sets the buttons up the other way round
		if self.messageShown:
			# whilst the notification is shown any keydown event dismisses the notification
			if flag == 0:
				self.hideMessage()
			else: # any key repeat or keyup event is discarded
				return 1

	def showMessage(self, message, hideScreen):
		padding = (40, 10)
		label = self['message']
		label.setText(message)
		size = label.getSize()
		label.resize(size[0] + padding[0] * 2, size[1] + padding[1] * 2)
		label.move((getDesktop(0).size().width() - size[0] - padding[0]) // 2, getDesktop(0).size().height() - size[1] - padding[1] * 2 - 30)
		label.show()
		self.messageShown = True
		self.show()
		self.hideTimer = eTimer()
		self.hideTimer.callback.append(self.hideScreen if hideScreen else self.hideMessage)
		self.hideTimer.start(2000, True)

	def hideMessage(self):
		self.messageShown = False
		self['message'].hide()

	def hideScreen(self):
		self.hideMessage()
		self.hide()
