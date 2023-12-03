from Components.ActionMap import HelpableActionMap
from Components.config import ConfigNothing, NoSave
from Components.Sources.StaticText import StaticText
from Screens.InfoBarGenerics import streamrelay
from Screens.Setup import Setup

from ServiceReference import ServiceReference

class StreamRelaySetup(Setup):
	def __init__(self, session):
		self.serviceitems = []
		self.services = streamrelay.data[:]
		Setup.__init__(self, session=session, setup="streamrelay")
		self["key_yellow"] = StaticText()
		self["key_blue"] = StaticText()
		self["addActions"] = HelpableActionMap(self, ["ColorActions"], {
			"yellow": (self.keyAddService, _("Play service with Stream Relay"))
		}, prio=0, description=_("Stream Relay Setup Actions"))
		self["removeActions"] = HelpableActionMap(self, ["ColorActions"], {
			"blue": (self.keyRemoveService, _("Play service without Stream Relay"))
		}, prio=0, description=_("Stream Relay Setup Actions"))
		self["removeActions"].setEnabled(False)

	def layoutFinished(self):
		Setup.layoutFinished(self)
		self.createItems()

	def createItems(self):
		self.serviceitems = []
		if self.services:
			for serviceref in self.services:
				service = ServiceReference(serviceref)
				self.serviceitems.append(((service and service.getServiceName() or serviceref) + " " + self.formatOrbPos(serviceref), NoSave(ConfigNothing()), serviceref, self.getOrbPos(serviceref)))
			self.serviceitems.sort(key=self.sort)
			self.serviceitems.insert(0, ("**************************",))
		self.createSetup()

	def createSetup(self):
		Setup.createSetup(self, appendItems=self.serviceitems)

	def selectionChanged(self):
		self.updateButtons()
		Setup.selectionChanged(self)

	def updateButtons(self):
		if self.services and isinstance(self.getCurrentItem(), ConfigNothing):
			self["removeActions"].setEnabled(True)
			self["key_blue"].setText(_("Remove"))
		else:
			self["removeActions"].setEnabled(False)
			self["key_blue"].setText("")
		self["key_yellow"].setText(_("Add service"))

	def keySelect(self):
		if not isinstance(self.getCurrentItem(), ConfigNothing):
			Setup.keySelect(self)

	def keyMenu(self):
		if not isinstance(self.getCurrentItem(), ConfigNothing):
			Setup.keyMenu(self)

	def keyRemoveService(self):
		currentItem = self.getCurrentItem()
		if currentItem:
			serviceref = self["config"].getCurrent()[2]
			self.services.remove(serviceref)
			index = self["config"].getCurrentIndex()
			self.createItems()
			self["config"].setCurrentIndex(index)

	def keyAddService(self):
		def keyAddServiceCallback(*result):
			if result:
				service = ServiceReference(result[0])
				serviceref = str(service)
				if serviceref not in self.services:
					self.services.append(serviceref)
					self.createItems()
					self["config"].setCurrentIndex(2)

		from Screens.ChannelSelection import SimpleChannelSelection  # deferred to avoid circular import
		self.session.openWithCallback(keyAddServiceCallback, SimpleChannelSelection, _("Select"), currentBouquet=False)

	def keySave(self):
		if streamrelay.data != self.services:
			streamrelay.data = self.services
		Setup.keySave(self)
		self.close()

	def getOrbPos(self, sref):
		orbpos = 0
		try:
			orbpos = int(sref.split(":")[6], 16) >> 16
		except:
			pass
		return orbpos

	def formatOrbPos(self, sref):
		orbpos = self.getOrbPos(sref)
		if isinstance(orbpos, int) and 1 <= orbpos <= 3600:  # sanity
			if orbpos > 1800:
				return str((float(3600 - orbpos)) / 10.0) + "\xb0" + "W"
			else:
				return str((float(orbpos)) / 10.0) + "\xb0" + "E"
		return ""

	def sort(self, item):
		return (item[3], item[0].lower() if item and item[0] and ord(item[0].lower()[0]) in range(97, 123) else f"zzzzz{item[0].lower()}")
