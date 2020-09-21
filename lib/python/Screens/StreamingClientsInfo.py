from Screen import Screen
from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.ScrollLabel import ScrollLabel
from Components.Converter.ClientsStreaming import ClientsStreaming
from Components.config import config
from Components.Sources.StaticText import StaticText
from enigma import eTimer, eStreamServer
import skin


class StreamingClientsInfo(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.timer = eTimer()
		self.setTitle(_("Streaming Clients Info"))

		self["ScrollLabel"] = ScrollLabel()

		self["key_red"] = Button(_("Close"))
		self["key_blue"] = StaticText()
		self["actions"] = ActionMap(["ColorActions", "SetupActions", "DirectionActions"],
			{
				"cancel": self.exit,
				"ok": self.exit,
				"red": self.exit,
				"blue": self.stopStreams,
				"up": self["ScrollLabel"].pageUp,
				"down": self["ScrollLabel"].pageDown
			})

		self.onLayoutFinish.append(self.start)

	def exit(self):
		self.stop()
		self.close()

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
		self["ScrollLabel"].setText(text or _("No clients streaming"))
		self["key_blue"].setText(text and _("Stop Streams") or "")
		self.timer.startLongTimer(5)

	def stopStreams(self):
		streamServer = eStreamServer.getInstance()
		if not streamServer:
			return
		for x in streamServer.getConnectedClients():
			streamServer.stopStream()
