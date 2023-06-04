from enigma import getPrevAsciiCode
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.VirtualKeyBoard import VirtualKeyBoard
from Components.ActionMap import HelpableNumberActionMap
from Components.config import config
from Components.Input import Input
from Components.Label import Label
from Components.Sources.StaticText import StaticText
from Tools.BoundFunction import boundFunction
from Tools.Notifications import AddPopup
from time import time


class InputBox(Screen, HelpableScreen):
	def __init__(self, session, title="", windowTitle=None, useableChars=None, **kwargs):
		Screen.__init__(self, session)

		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Save"))
		self["key_text"] = StaticText(_("TEXT"))
		self["text"] = Label(title)
		self["input"] = Input(**kwargs)

		HelpableScreen.__init__(self)

		if windowTitle is None:
			windowTitle = _("Input")
		self.onShown.append(boundFunction(self.setTitle, windowTitle))
		if useableChars is not None:
			self["input"].setUseableChars(useableChars)

		self["actions"] = HelpableNumberActionMap(self, ["WizardActions", "InputBoxActions", "InputAsciiActions", "KeyboardInputActions", "ColorActions", "VirtualKeyboardActions"],
		{
			"showVirtualKeyboard": (self.keyText, _("Open VirtualKeyboard")),
			"gotAsciiCode": (self.gotAsciiCode, _("Handle ASCII")),
			"green": (self.go, _("Save")),
			"ok": (self.go, _("Save")),
			"red": (self.cancel, _("Cancel")),
			"back": (self.cancel, _("Cancel")),
			"left": (self.keyLeft, _("Move left")),
			"right": (self.keyRight, _("Move right")),
			"home": (self.keyHome, _("Move to start")),
			"end": (self.keyEnd, _("Move to end")),
			"deleteForward": (self.keyDelete, _("Delete forwards")),
			"deleteBackward": (self.keyBackspace, _("Delete backwards")),
			"tab": (self.keyTab, _("Tab")),
			"toggleOverwrite": (self.keyInsert, _("Number or SMS style data entry")),
			"1": (self.keyNumberGlobal, _("Number or SMS style data entry")),
			"2": (self.keyNumberGlobal, _("Number or SMS style data entry")),
			"3": (self.keyNumberGlobal, _("Number or SMS style data entry")),
			"4": (self.keyNumberGlobal, _("Number or SMS style data entry")),
			"5": (self.keyNumberGlobal, _("Number or SMS style data entry")),
			"6": (self.keyNumberGlobal, _("Number or SMS style data entry")),
			"7": (self.keyNumberGlobal, _("Number or SMS style data entry")),
			"8": (self.keyNumberGlobal, _("Number or SMS style data entry")),
			"9": (self.keyNumberGlobal, _("Number or SMS style data entry")),
			"0": (self.keyNumberGlobal, _("Number or SMS style data entry")),
		}, prio=-1, description=_("InputBox Actions"))

		if self["input"].type == Input.TEXT:
			self.onExecBegin.append(self.setKeyboardModeAscii)
		else:
			self.onExecBegin.append(self.setKeyboardModeNone)

	def gotAsciiCode(self):
		self["input"].handleAscii(getPrevAsciiCode())

	def keyLeft(self):
		self["input"].left()

	def keyRight(self):
		self["input"].right()

	def keyNumberGlobal(self, number):
		self["input"].number(number)

	def keyDelete(self):
		self["input"].delete()

	def go(self):
		self.close(self["input"].getText())

	def cancel(self):
		self.close(None)

	def keyHome(self):
		self["input"].home()

	def keyEnd(self):
		self["input"].end()

	def keyBackspace(self):
		self["input"].deleteBackward()

	def keyTab(self):
		self["input"].tab()

	def keyInsert(self):
		self["input"].toggleOverwrite()

	def keyText(self):
		self.session.openWithCallback(self.VirtualKeyBoardCallback, VirtualKeyBoard, title=self["text"].text, text=self["input"].getText())

	def VirtualKeyBoardCallback(self, callback=None):
		if callback is not None and len(callback):
			self["input"].setText(callback)
			self.keyEnd()


class PinInput(InputBox):
	def __init__(self, session, service="", triesEntry=None, pinList=None, popup=False, simple=True, *args, **kwargs):
		if not pinList:
			pinList = []
		InputBox.__init__(self, session=session, text="    ", maxSize=True, type=Input.PIN, *args, **kwargs)

		self.waitTime = 15
		self.triesEntry = triesEntry
		self.pinList = pinList
		self["service"] = Label(service)

		if service and simple:
			self.skinName = "PinInputPopup"

		if self.getTries() == 0:
			if (self.triesEntry.time.value + (self.waitTime * 60)) > time():
				remaining = (self.triesEntry.time.value + (self.waitTime * 60)) - time()
				remainingMinutes = int(remaining / 60)
				remainingSeconds = int(remaining % 60)
				messageText = _("You have to wait %s!") % (str(remainingMinutes) + " " + _("minutes") + ", " + str(remainingSeconds) + " " + _("seconds"))
				if service and simple:
					AddPopup(messageText, type=MessageBox.TYPE_ERROR, timeout=3)
					self.closePinCancel()
				else:
					self.onFirstExecBegin.append(boundFunction(self.session.openWithCallback, self.closePinCancel, MessageBox, messageText, MessageBox.TYPE_ERROR, timeout=3))
			else:
				self.setTries(3)

		self["tries"] = Label("")
		self.onShown.append(self.showTries)

	def gotAsciiCode(self):
		if self["input"].currPos == len(self["input"]) - 1:
			InputBox.gotAsciiCode(self)
			self.go()
		else:
			InputBox.gotAsciiCode(self)

	def keyNumberGlobal(self, number):
		if self["input"].currPos == len(self["input"]) - 1:
			InputBox.keyNumberGlobal(self, number)
			self.go()
		else:
			InputBox.keyNumberGlobal(self, number)

	def checkPin(self, pin):
		if pin is not None and " " not in pin and int(pin) in self.pinList:
			return True
		return False

	def go(self):
		if self.pinList:
			self.triesEntry.time.value = int(time())
			self.triesEntry.time.save()
			if self.checkPin(self["input"].getText()):
				self.setTries(3)
				self.closePinCorrect()
			else:
				self.keyHome()
				self.decTries()
				if self.getTries() == 0:
					self.closePinWrong()
		else:
			pin = self["input"].getText()
			if pin and pin.isdigit():
				self.close(int(pin))
			else:
				self.close(None)

	def closePinWrong(self, *args):
		print("[InputBox] args:", args)
		self.close(False)

	def closePinCorrect(self, *args):
		self.setTries(3)
		self.close(True)

	def closePinCancel(self, *args):
		self.close(None)

	def cancel(self):
		self.closePinCancel()

	def getTries(self):
		return self.triesEntry and self.triesEntry.tries.value

	def decTries(self):
		self.setTries(self.triesEntry.tries.value - 1)
		self.showTries()

	def setTries(self, tries):
		self.triesEntry.tries.value = tries
		self.triesEntry.tries.save()

	def showTries(self):
		self["tries"].setText(self.triesEntry and _("Tries left:") + " " + str(self.getTries() or ""))

	def keyRight(self):
		pass
