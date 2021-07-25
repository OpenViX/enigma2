from __future__ import absolute_import

from Components.Sources.Source import Source
from Components.Element import cached
from enigma import eServiceCenter


class ServiceEvent(Source, object):
	def __init__(self):
		Source.__init__(self)
		self.service = None
		self.additionalInfo = None

	@cached
	def getCurrentService(self):
		return self.service

	@cached
	def getCurrentEvent(self):
		return self.service and self.info and self.info.getEvent(self.service)

	@cached
	def getInfo(self):
		return self.service and eServiceCenter.getInstance().info(self.service)

	event = property(getCurrentEvent)
	info = property(getInfo)

	def newService(self, ref, additionalInfo=None):
		self.service = ref
		self.additionalInfo = additionalInfo
		if not ref:
			self.changed((self.CHANGED_CLEAR,))
		else:
			self.changed((self.CHANGED_ALL,))
