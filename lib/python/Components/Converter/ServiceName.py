# -*- coding: utf-8 -*-

from Components.Converter.Converter import Converter
from Components.config import config
from enigma import iServiceInformation, iPlayableService, iPlayableServicePtr, eServiceReference, eEPGCache
from ServiceReference import resolveAlternate
from Components.Element import cached
from Tools.Directories import fileExists
from Tools.Transponder import ConvertToHumanReadable


class ServiceName(Converter):
	NAME = 0
	NAME_ONLY = 1
	NAME_EVENT = 2
	PROVIDER = 3
	REFERENCE = 4
	EDITREFERENCE = 5
	FORMAT_STRING = 6

	def __init__(self, type):
		Converter.__init__(self, type)
		self.epgQuery = eEPGCache.getInstance().lookupEventTime
		self.parts = type.split(",")
		if len(self.parts) > 1:
			self.type = self.FORMAT_STRING
			self.separatorChar = self.parts[0]
		else:
			if type == "Provider":
				self.type = self.PROVIDER
			elif type == "Reference":
				self.type = self.REFERENCE
			elif type == "EditReference":
				self.type = self.EDITREFERENCE
			elif type == "NameOnly":
				self.type = self.NAME_ONLY
			elif type == "NameAndEvent":
				self.type = self.NAME_EVENT
			else:
				self.type = self.NAME

	@cached
	def getText(self):
		service = self.source.service
		info = None
		if isinstance(service, eServiceReference):
			info = self.source.info
		elif isinstance(service, iPlayableServicePtr):
			info = service and service.info()
			service = None

		if not info:
			return ""

		if self.type == self.NAME or self.type == self.NAME_ONLY or self.type == self.NAME_EVENT:
			name = self.getName(service, info)
			if self.type == self.NAME_EVENT:
				act_event = info and info.getEvent(0)
				if not act_event and info:
					refstr = info.getInfoString(iServiceInformation.sServiceref)
					act_event = self.epgQuery(eServiceReference(refstr), -1, 0)
				if act_event is None:
					return "%s - " % name
				else:
					return "%s - %s" % (name, act_event.getEventName())
			elif self.type != self.NAME_ONLY and config.usage.show_infobar_channel_number.value and hasattr(self.source, "serviceref") and self.source.serviceref and '0:0:0:0:0:0:0:0:0' not in self.source.serviceref.toString():
				numservice = self.source.serviceref
				num = self.getNumber(numservice, info)
				if num is not None:
					return str(num) + '   ' + name
				else:
					return name
			else:
				return name
		elif self.type == self.PROVIDER:
			return self.getProvider(service, info)
		elif self.type == self.REFERENCE or self.type == self.EDITREFERENCE and hasattr(self.source, "editmode") and self.source.editmode:
			if not service:
				refstr = info.getInfoString(iServiceInformation.sServiceref)
				path = refstr and eServiceReference(refstr).getPath()
				if path and fileExists("%s.meta" % path):
					fd = open("%s.meta" % path, "r")
					refstr = fd.readline().strip()
					fd.close()
				return refstr
			nref = resolveAlternate(service)
			if nref:
				service = nref
			return service.toString()
		elif self.type == self.FORMAT_STRING:
			name = self.getName(service, info)
			numservice = hasattr(self.source, "serviceref") and self.source.serviceref
			num = numservice and self.getNumber(numservice, info) or ""
			orbpos, tp_data = self.getOrbitalPos(service, info)
			provider = self.getProvider(service, info, tp_data)
			tuner_system = service and info and self.getServiceSystem(service, info, tp_data)
			res_str = ""
			for x in self.parts[1:]:
				if x == "NUMBER" and num:
					res_str = self.appendToStringWithSeparator(res_str, num)
				if x == "NAME" and name:
					res_str = self.appendToStringWithSeparator(res_str, name)
				if x == "ORBPOS" and orbpos:
					res_str = self.appendToStringWithSeparator(res_str, orbpos)
				if x == "PROVIDER" and provider:
					res_str = self.appendToStringWithSeparator(res_str, provider)
				if x == "TUNERSYSTEM" and tuner_system:
					res_str = self.appendToStringWithSeparator(res_str, tuner_system)
			return res_str

	text = property(getText)

	def changed(self, what):
		if what[0] != self.CHANGED_SPECIFIC or what[1] in (iPlayableService.evStart, iPlayableService.evNewProgramInfo):
			Converter.changed(self, what)

	def getName(self, ref, info):
		name = ref and info.getName(ref)
		if name is None:
			name = info.getName()
		return name.replace('\xc2\x86', '').replace('\xc2\x87', '').replace('_', ' ')

	def getNumber(self, ref, info):
		if not ref:
			ref = eServiceReference(info.getInfoString(iServiceInformation.sServiceref))
		num = ref and ref.getChannelNum() or None
		if num is not None:
			num = str(num)
		return num

	def getProvider(self, ref, info, tp_data=None):
		if ref:
			return info.getInfoString(ref, iServiceInformation.sProvider)
		return info.getInfoString(iServiceInformation.sProvider)

	def getOrbitalPos(self, ref, info):
		orbitalpos = ""
		if ref:
			tp_data = info.getInfoObject(ref, iServiceInformation.sTransponderData)
		else:
			tp_data = info.getInfoObject(iServiceInformation.sTransponderData)

		if tp_data is not None:
			try:
				position = tp_data["orbital_position"]
				if position > 1800:  # west
					orbitalpos = "%.1f " % (float(3600 - position) / 10) + _("W")
				else:
					orbitalpos = "%.1f " % (float(position) / 10) + _("E")
			except:
				pass
		return orbitalpos, tp_data

	def getServiceSystem(self, ref, info, feraw):
		if ref:
			sref = info.getInfoObject(ref, iServiceInformation.sServiceref)
		else:
			sref = info.getInfoObject(iServiceInformation.sServiceref)

		if not sref:
			sref = ref.toString()

		if sref and "%3a//" in sref:
			return "IPTV"

		fedata = ConvertToHumanReadable(feraw)

		return fedata.get("system") or ""
