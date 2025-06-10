from enigma import eTimer, eStreamServer

from Components.ActionMap import ActionMap
from Components.Converter.ClientsStreaming import ClientsStreaming
from Components.Sources.StaticText import StaticText
from Screens.About import AboutBase
import skin  # noqa: F401


class StreamingClientsInfo(AboutBase):
	def __init__(self, session):
		AboutBase.__init__(self, session, labels=True)
		self.timer = eTimer()
		self.setTitle(_("Streaming Clients Info"))

		self["key_blue"] = StaticText()
		self["actions"] = ActionMap(["ColorActions"],
			{
				"blue": self.stopStreams,
			})  # noqa: E123

		self.onLayoutFinish.append(self.start)

	def close(self):
		self.stop()
		AboutBase.close(self)

	def start(self):
		if self.update_info not in self.timer.callback:
			self.timer.callback.append(self.update_info)
		self.timer.startLongTimer(0)

	def stop(self):
		if self.update_info in self.timer.callback:
			self.timer.callback.remove(self.update_info)
		self.timer.stop()

	def update_info(self):
		clients = ClientsStreaming("INFO_RESOLVE")
		text = clients.getText()
		self["AboutScrollLabel"].split = False  # don't split
		self["AboutScrollLabel"].setText(text or _("No clients streaming"))
		self["key_blue"].setText(text and _("Stop Streams") or "")
		self.timer.startLongTimer(5)

	def stopStreams(self):
		streamServer = eStreamServer.getInstance()
		if not streamServer:
			return
		for x in streamServer.getConnectedClients():
			streamServer.stopStream()
