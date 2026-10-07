import socket

from enigma import eStreamServer

from Components.Converter.Converter import Converter
from Components.Converter.Poll import Poll
from Components.Element import cached
from Components.Sources.StreamService import StreamServiceList
from ServiceReference import ServiceReference


class ClientsStreaming(Converter, Poll):
	UNKNOWN = -1
	REF = 0
	IP = 1
	NAME = 2
	ENCODER = 3
	NUMBER = 4
	SHORT_ALL = 5
	ALL = 6
	INFO = 7
	INFO_RESOLVE = 8
	INFO_RESOLVE_SHORT = 9

	TEXT_HANDLERS = {
		REF: "textRefs",
		IP: "textIPs",
		NAME: "textNames",
		ENCODER: "textEncoders",
		NUMBER: "textNumber",
		SHORT_ALL: "textShortAll",
		ALL: "textAll",
		INFO: "textInfo",
		INFO_RESOLVE: "textInfoResolve",
		INFO_RESOLVE_SHORT: "textInfoResolveShort",
	}

	def __init__(self, type):
		Converter.__init__(self, type)
		Poll.__init__(self)

		self.poll_interval = 5000
		self.poll_enabled = True

		self.type = {
			"REF": self.REF,
			"IP": self.IP,
			"NAME": self.NAME,
			"ENCODER": self.ENCODER,
			"NUMBER": self.NUMBER,
			"SHORT_ALL": self.SHORT_ALL,
			"ALL": self.ALL,
			"INFO": self.INFO,
			"INFO_RESOLVE": self.INFO_RESOLVE,
			"INFO_RESOLVE_SHORT": self.INFO_RESOLVE_SHORT,
		}.get(type, self.UNKNOWN)

		self.streamServer = eStreamServer.getInstance()

		self.textHandler = getattr(self, self.TEXT_HANDLERS.get(self.type, "textUnknown"))

	@cached
	def getText(self):
		if self.streamServer is None:
			return ""
		return self.textHandler()

	text = property(getText)

	# ---- Text ----

	def textUnknown(self):
		return _("(unknown)")

	def textRefs(self):
		return " ".join(client[1] for client in self.streamServer.getConnectedClients())

	def textIPs(self):
		return " ".join(client[0] for client in self.streamServer.getConnectedClients())

	def textNames(self):
		return " ".join(ServiceReference(client[1]).getServiceName() or "(unknown service)" for client in self.streamServer.getConnectedClients())

	def textEncoders(self):
		encoders = []

		for client in self.streamServer.getConnectedClients():
			encoders.append(_("YES") if int(client[2]) else _("NO"))

		return _("Transcoding: ") + " ".join(encoders)

	def textNumber(self):
		return str(len(self.streamServer.getConnectedClients()))

	def textShortAll(self):
		clients = self.streamServer.getConnectedClients()
		names = []

		for client in clients:
			names.append(ServiceReference(client[1]).getServiceName() or "(unknown service)")

		return _("Total clients streaming: %d (%s)") % (len(clients), " ".join(names))

	def getClientInfo(self):
		clients = []

		for client in self.streamServer.getConnectedClients():
			ip = client[0]
			service_name = (ServiceReference(client[1]).getServiceName() or "(unknown service)")
			encoder = _("YES") if int(client[2]) else _("NO")

			clients.append((ip, service_name, encoder))

		return clients

	def textAll(self):
		return "\n".join(" ".join(client) for client in self.getClientInfo())

	def textInfo(self, resolve=False, short=False):
		info = []

		for client in self.streamServer.getConnectedClients():
			ip = client[0]
			service_name = (ServiceReference(client[1]).getServiceName() or "(unknown service)")

			if resolve:
				try:
					ip = socket.gethostbyaddr(ip)[0]
				except Exception:
					pass

				if short:
					ip, _, _ = ip.partition(".")

			strtype = "Transcoding: " if int(client[2]) else "Streaming: "

			info.append("%s  %-8s  %s\n" % (strtype, ip, service_name))

		return "".join(info)

	def textInfoResolve(self):
		return self.textInfo(resolve=True)

	def textInfoResolveShort(self):
		return self.textInfo(resolve=True, short=True)

	# ---- Boolean ----

	@cached
	def getBoolean(self):
		if self.streamServer is None:
			return False

		return bool(self.streamServer.getConnectedClients() or StreamServiceList)

	boolean = property(getBoolean)

	def changed(self, what):
		Converter.changed(self, (self.CHANGED_POLL,))

	def doSuspend(self, suspended):
		pass
