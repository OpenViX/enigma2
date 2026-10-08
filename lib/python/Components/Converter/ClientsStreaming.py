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

	KEYWORDS = {
		"REF": REF,
		"IP": IP,
		"NAME": NAME,
		"ENCODER": ENCODER,
		"NUMBER": NUMBER,
		"SHORT_ALL": SHORT_ALL,
		"ALL": ALL,
		"INFO": INFO,
		"INFO_RESOLVE": INFO_RESOLVE,
		"INFO_RESOLVE_SHORT": INFO_RESOLVE_SHORT
	}

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
		INFO_RESOLVE_SHORT: "textInfoResolveShort"
	}

	# Host names found by reverse lookups, shared by every instance. Looking an address up can take
	# seconds, so it is done once per connected client and not on every poll.
	hostnames = {}

	def __init__(self, type):
		Converter.__init__(self, type)
		Poll.__init__(self)

		self.poll_interval = 5000
		self.poll_enabled = True

		self.type = self.KEYWORDS.get(type, self.UNKNOWN)

		self.streamServer = eStreamServer.getInstance()

		self.textHandler = getattr(self, self.TEXT_HANDLERS.get(self.type, "textUnknown"))

	@cached
	def getText(self):
		if self.streamServer is None:
			return ""
		return self.textHandler()

	text = property(getText)

	# ---- Helpers ----

	def serviceName(self, ref):
		return ServiceReference(ref).getServiceName() or "(unknown service)"

	def resolveHost(self, ip):
		# The host name for an address, or the address itself when it cannot be resolved. Failures are remembered too.
		if ip not in self.hostnames:
			try:
				self.hostnames[ip] = socket.gethostbyaddr(ip)[0]
			except Exception:
				self.hostnames[ip] = ip
		return self.hostnames[ip]

	def forgetDisconnected(self, clients):
		# Once a client has gone, look its address up again the next time it connects.
		connected = {client[0] for client in clients}
		for ip in list(self.hostnames):
			if ip not in connected:
				del self.hostnames[ip]

	# ---- Text ----

	def textUnknown(self):
		return _("(unknown)")

	def textRefs(self):
		return " ".join(client[1] for client in self.streamServer.getConnectedClients())

	def textIPs(self):
		return " ".join(client[0] for client in self.streamServer.getConnectedClients())

	def textNames(self):
		return " ".join(self.serviceName(client[1]) for client in self.streamServer.getConnectedClients())

	def textEncoders(self):
		encoders = []

		for client in self.streamServer.getConnectedClients():
			encoders.append(_("YES") if int(client[2]) else _("NO"))

		return _("Transcoding: ") + " ".join(encoders)

	def textNumber(self):
		return str(len(self.streamServer.getConnectedClients()))

	def textShortAll(self):
		clients = self.streamServer.getConnectedClients()
		names = [self.serviceName(client[1]) for client in clients]

		return _("Total clients streaming: %d (%s)") % (len(clients), " ".join(names))

	def textAll(self):
		lines = []

		for client in self.streamServer.getConnectedClients():
			encoder = _("YES") if int(client[2]) else _("NO")

			lines.append(" ".join((client[0], self.serviceName(client[1]), encoder)))

		return "\n".join(lines)

	def textInfo(self, resolve=False, short=False):
		info = []
		clients = self.streamServer.getConnectedClients()

		if resolve:
			self.forgetDisconnected(clients)

		for client in clients:
			ip = client[0]

			if resolve:
				ip = self.resolveHost(ip)

				if short:
					ip = ip.partition(".")[0]

			strtype = "Transcoding: " if int(client[2]) else "Streaming: "

			info.append("%s  %-8s  %s\n" % (strtype, ip, self.serviceName(client[1])))

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
