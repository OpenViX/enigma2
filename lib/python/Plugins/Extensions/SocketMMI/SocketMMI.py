from __future__ import absolute_import

from Screens.Ci import MMIDialog
from . import socketmmi


class SocketMMIMessageHandler:
	def __init__(self):
		self.session = None
		self.dlgs = {}
		socketmmi.getSocketStateChangedCallbackList().append(self.socketStateChanged)

	def setSession(self, session):
		self.session = session

	def connected(self, slot=0):
		return socketmmi.getState(slot)

	def numConnections(self):
		if socketmmi.getState(0):
			return 1
		else:
			return 0

	def getState(self, slot=0):
		return socketmmi.getState(slot)

	def getName(self, slot=0):
		return socketmmi.getName(slot)

	def startMMI(self, slot=0):
		self.dlgs[slot] = self.session.openWithCallback(self.dlgClosed, MMIDialog, slot, 2, socketmmi, _("wait for mmi..."))

	def socketStateChanged(self, slot):
		if slot in self.dlgs:
			self.dlgs[slot].ciStateChanged()
		elif socketmmi.availableMMI(slot) == 1:
			if self.session:
				self.dlgs[slot] = self.session.openWithCallback(self.dlgClosed, MMIDialog, slot, 3, socketmmi, _("wait for mmi..."))

	def dlgClosed(self, slot):
		if slot in self.dlgs:
			del self.dlgs[slot]
