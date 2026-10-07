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

	KEYWORDS = {
		"Provider": PROVIDER,
		"Reference": REFERENCE,
		"EditReference": EDITREFERENCE,
		"NameOnly": NAME_ONLY,
		"NameAndEvent": NAME_EVENT,
		"StreamUrl": STREAM_URL,
		"Name": NAME
	}

	# Map each type to the name of the method that produces its text.
	HANDLERS = {
		NAME: "textName",
		NAME_ONLY: "textNameOnly",
		NAME_EVENT: "textNameAndEvent",
		PROVIDER: "textProvider",
		REFERENCE: "textReference",
		EDITREFERENCE: "textEditReference",
		STREAM_URL: "textStreamUrl",
		FORMAT_STRING: "textFormatString"
	}

	# The tokens a format string understands. Anything else in the list is ignored.
	FORMAT_TOKENS = frozenset(("NUMBER", "NAME", "ORBPOS", "PROVIDER", "TUNERSYSTEM"))

	def __init__(self, type):
		Converter.__init__(self, type)
		self.epgQuery = eEPGCache.getInstance().lookupEventTime
		self.parts = [(arg.strip() if i or arg.strip() in self.KEYWORDS else arg) for i, arg in enumerate(type.split(","))]
		if len(self.parts) > 1:
			self.type = self.FORMAT_STRING
			self.separator = self.parts[0]
		else:
			self.type = self.KEYWORDS.get(type, self.NAME)
		# Work out once which values the format string needs, and in which order they are shown.
		self.formatParts = tuple(part for part in self.parts[1:] if part in self.FORMAT_TOKENS)
		self.formatNeeds = frozenset(self.formatParts)
		self.handler = getattr(self, self.HANDLERS[self.type])

	@cached
	def getText(self):
		service = self.source.service or (hasattr(self.source, "serviceref") and self.source.serviceref)
		info = None
		if isinstance(service, eServiceReference):
			info = self.source.info
		elif isinstance(service, iPlayableServicePtr):
			info = service and service.info()
			service = None

		if not info:
			return ""
		return self.handler(service, info)

	text = property(getText)

	def changed(self, what):
		if what[0] != self.CHANGED_SPECIFIC or what[1] in (iPlayableService.evStart, ):
			Converter.changed(self, what)

	# ---- Text ----

	def textName(self, service, info):
		name = self.getName(service, info)
		if config.usage.show_infobar_channel_number.value and hasattr(self.source, "serviceref") and self.source.serviceref and '0:0:0:0:0:0:0:0:0' not in self.source.serviceref.toString():
			return self.getNumber() + '   ' + name
		return name

	def textNameOnly(self, service, info):
		return self.getName(service, info)

	def textNameAndEvent(self, service, info):
		name = self.getName(service, info)
		act_event = info.getEvent(0)
		if not act_event:
			refstr = info.getInfoString(iServiceInformation.sServiceref)
			act_event = self.epgQuery(eServiceReference(refstr), -1, 0)
		if act_event is None:
			return "%s - " % name
		return "%s - %s" % (name, act_event.getEventName())

	def textProvider(self, service, info):
		return self.getProvider(service, info)

	def textEditReference(self, service, info):
		if hasattr(self.source, "editmode") and self.source.editmode:
			return self.textReference(service, info)

	def textReference(self, service, info):
		if not service:
			if self.source.info:
				sref = hasattr(self.source, "serviceref") and self.source.serviceref
				nref = sref and resolveAlternate(sref)
				if nref:
					sref = nref
				return sref and sref.toString()
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

	def textStreamUrl(self, service, info):
		path = ""
		if not service:
			refstr = info.getInfoString(iServiceInformation.sServiceref)
			path = refstr and refstr.split(":")[10].replace("%3a", ":")
		if "://" in path and "http" not in path:
			path = SessionObject().session.nav.getCurrentServiceReference().toString().split(":")[10].replace("%3a", ":")
		if path.startswith("//"):
			srpart = "//%s:%s/" % (config.misc.softcam_streamrelay_url.getHTML(), config.misc.softcam_streamrelay_port.value)
			if path.find(srpart) > -1 and "://" not in path:
				return ""
		return path

	def textFormatString(self, service, info):
		# Only work out the values the format string asks for.
		needs = self.formatNeeds
		values = {}
		if "NUMBER" in needs:
			values["NUMBER"] = self.getNumber()
		if "NAME" in needs:
			values["NAME"] = self.getName(service, info)
		if "PROVIDER" in needs:
			values["PROVIDER"] = self.getProvider(service, info)
		wantSystem = "TUNERSYSTEM" in needs and service
		if "ORBPOS" in needs or wantSystem:
			orbpos, tp_data = self.getOrbitalPos(service, info)
			values["ORBPOS"] = orbpos
			if wantSystem:
				values["TUNERSYSTEM"] = self.getServiceSystem(service, info, tp_data)
		res_str = ""
		for part in self.formatParts:
			value = values.get(part)
			if value:
				res_str = self.appendToStringWithSeparator(res_str, value)
		return res_str

	def getName(self, ref, info):
		sref = hasattr(self.source, "serviceref") and self.source.serviceref
		name = ref and hasattr(info, "getName") and info.getName(ref) or sref and hasattr(self.source.info, "getName") and self.source.info.getName(sref) or hasattr(sref, "getName") and sref.getName() or ""
		if not name:
			if not ref:
				name = info.getName()

		return name.replace('\xc2\x86', '').replace('\xc2\x87', '').replace('_', ' ')

	def getNumber(self):
		numservice = hasattr(self.source, "serviceref") and self.source.serviceref
		channelNumInt = numservice and numservice.getChannelNum() or 0
		channelnum = str(channelNumInt) if channelNumInt else ""
		return channelnum

	def getProvider(self, ref, info):
		sref = hasattr(self.source, "serviceref") and self.source.serviceref
		prov = ((ref and hasattr(ref, "getProvider") and ref.getProvider()) or (ref and info.getInfoString(ref, iServiceInformation.sProvider))) or (sref and ref and (self.source.info and self.source.info.getInfoString(sref, iServiceInformation.sProvider)) or (hasattr(sref, "getProvider") and sref.getProvider()))
		if not prov:
			if not ref:
				prov = info.getInfoString(iServiceInformation.sProvider)
			else:
				prov = ""
		return prov

	def getOrbitalPos(self, ref, info):
		orbitalpos = ""
		tp_data = None
		sref = hasattr(self.source, "serviceref") and self.source.serviceref
		if ref:
			tp_data = info.getInfoObject(ref, iServiceInformation.sTransponderData)
		elif not self.source.info:
			tp_data = info.getInfoObject(iServiceInformation.sTransponderData)
		else:
			tp_data = sref and self.source.info.getInfoObject(sref, iServiceInformation.sTransponderData)

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
