# -*- coding: utf-8 -*-
from enigma import iServiceInformation, iPlayableService, iPlayableServicePtr, eServiceReference, eEPGCache
from Components.Converter.Converter import Converter
from Components.config import config
from ServiceReference import resolveAlternate
from Components.Element import cached
from Tools.Directories import fileExists
from Tools.Transponder import ConvertToHumanReadable
from Session import SessionObject


class ServiceName(Converter):
	NAME = 0
	NAME_ONLY = 1
	NAME_EVENT = 2
	PROVIDER = 3
	REFERENCE = 4
	EDITREFERENCE = 5
	STREAM_URL = 6
	FORMAT_STRING = 7

	def __init__(self, type):
		Converter.__init__(self, type)
		self.epgQuery = eEPGCache.getInstance().lookupEventTime
		self.KEYWORDS = {
			"Provider": self.PROVIDER,
			"Reference": self.REFERENCE,
			"EditReference": self.EDITREFERENCE,
			"NameOnly": self.NAME_ONLY,
			"NameAndEvent": self.NAME_EVENT,
			"StreamUrl": self.STREAM_URL,
			"Name": self.NAME}

		self.parts = [(arg.strip() if i or arg.strip() in self.KEYWORDS else arg) for i, arg in enumerate(type.split(","))]
		if len(self.parts) > 1:
			self.type = self.FORMAT_STRING
			self.separator = self.parts[0]
		else:
			self.type = self.KEYWORDS.get(type, self.NAME)

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
				num = self.getNumber()
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
		elif self.type == self.STREAM_URL:
			srpart = "//%s:%s/" % (config.misc.softcam_streamrelay_url.getHTML(), config.misc.softcam_streamrelay_port.value)
			if not service:
				refstr = info.getInfoString(iServiceInformation.sServiceref)
				path = refstr and eServiceReference(refstr).getPath()
				if not path:
					curService = SessionObject.session.nav.getCurrentlyPlayingServiceReference()
					path = curService and curService.toString().split(":")[10].replace("%3a", ":")
				if not path.startswith("//") and path.find(srpart) == -1:
					return path
				else:
					return ""
			path = service.getPath()
			if not path:
				path = service.toString().split(":")[10].replace("%3a", ":")
			return "" if path.startswith("//") and path.find(srpart) == -1 else path
		elif self.type == self.FORMAT_STRING:
			name = self.getName(service, info)
			provider = self.getProvider(service, info)
			num = self.getNumber()
			orbpos, tp_data = self.getOrbitalPos(service, info)
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
		if what[0] != self.CHANGED_SPECIFIC or what[1] in (iPlayableService.evStart, ):
			Converter.changed(self, what)

	def getName(self, ref, info):
		name = ref and info.getName(ref)
		if name is None:
			name = info.getName()
		return name.replace('\xc2\x86', '').replace('\xc2\x87', '').replace('_', ' ')

	def getNumber(self):
		numservice = hasattr(self.source, "serviceref") and self.source.serviceref
		channelnum = numservice and str(numservice.getChannelNum()) or ""
		return channelnum

	def getProvider(self, ref, info):
		if ref:
			return ref.getProvider()
		return info.getInfoString(iServiceInformation.sProvider)

	def getOrbitalPos(self, ref, info):
		orbitalpos = ""
		tp_data = None
		if ref:
			tp_data = info.getInfoObject(ref, iServiceInformation.sTransponderData)
		else:
			tp_data = info.getInfoObject(iServiceInformation.sTransponderData)

		if tp_data is not None:
			try:
				position = tp_data["orbital_position"]
				if position > 1800:  # west
					orbitalpos = "%.1f° " % (float(3600 - position) / 10) + _("W")
				else:
					orbitalpos = "%.1f° " % (float(position) / 10) + _("E")
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

		fedata = None

		if feraw:
			fedata = ConvertToHumanReadable(feraw)

		return fedata and fedata.get("system") or ""
