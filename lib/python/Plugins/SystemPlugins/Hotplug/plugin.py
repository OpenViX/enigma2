import os

from twisted.internet import reactor
from twisted.internet.protocol import Protocol, Factory

from Components.Harddisk import harddiskmanager
from Plugins.Plugin import PluginDescriptor

hotplugNotifier = []
audioCd = False


def AudiocdAdded():
	global audioCd
	return True if audioCd else False


def processHotplugData(self, eventData):
	print "[Hotplug] DEBUG:", eventData
	action = eventData.get("ACTION")
	device = eventData.get("DEVPATH")
	physDevPath = eventData.get("PHYSDEVPATH")
	mediaState = eventData.get("X_E2_MEDIA_STATUS")
	global audioCd

	dev = device.split("/")[-1]
	print "[Hotplug] DEBUG: device = %s action = %s mediaState = %s physDevPath = %s dev = %s" % (device, action, mediaState, physDevPath, dev)
	if action == "add":
		error, blacklisted, removable, is_cdrom, partitions, medium_found = harddiskmanager.addHotplugPartition(dev, physDevPath)
	elif action == "remove":
		harddiskmanager.removeHotplugPartition(dev)
	elif action == "audiocdadd":
		audioCd = True
		mediaState = "audiocd"
		error, blacklisted, removable, is_cdrom, partitions, medium_found = harddiskmanager.addHotplugPartition(dev, physDevPath)
		print "[Hotplug] Adding Audio CD."
	elif action == "audiocdremove":
		audioCd = False
		# Removing the invalid playlist.e2pls if its still the audio cd's list.
		# Default setting is to save last playlist on closing Mediaplayer. If
		# audio cd is removed after Mediaplayer was closed, the playlist
		# remains in if no other media was played.
		try:
			with open("/etc/enigma2/playlist.e2pls", "r") as fd:
				file = f.readline().strip()
		except (IOError, OSError):
			file = None
		if file and ".cda" in file:
			try:
				os.remove("/etc/enigma2/playlist.e2pls")
			except (IOError, OSError):
				pass
		harddiskmanager.removeHotplugPartition(dev)
		print "[Hotplug] Removing Audio CD."
	elif mediaState is not None:
		if mediaState == "1":
			harddiskmanager.removeHotplugPartition(dev)
			harddiskmanager.addHotplugPartition(dev, physDevPath)
		elif mediaState == "0":
			harddiskmanager.removeHotplugPartition(dev)
	for callback in hotplugNotifier:
		try:
			callback(dev, action or mediaState)
		except AttributeError:
			hotplugNotifier.remove(callback)


class Hotplug(Protocol):
	def connectionMade(self):
		print "[Hotplug] Connection made."
		self.received = ""

	def dataReceived(self, data):
		self.received += data
		print "[Hotplug] Data received: '%s'." % ", ".join(self.received.split("\0")[:-1])

	def connectionLost(self, reason):
		print "[Hotplug] Connection lost."
		eventData = {}
		for item in self.received.split("\0")[:-1]:
			index = item.find("=")
			var, val = item[:index], item[index + 1:]
			eventData[var] = val
		print "[Hotplug] Calling processHotplugData, reason = %s eventData = %s." % (reason, eventData)
		processHotplugData(self, eventData)


def autostart(reason, **kwargs):
	if reason == 0:
		try:
			os.remove("/tmp/hotplug.socket")
		except (IOError, OSError):
			pass
		factory = Factory()
		factory.protocol = Hotplug
		reactor.listenUNIX("/tmp/hotplug.socket", factory)


def Plugins(**kwargs):
	return PluginDescriptor(name=_("Hotplug"), description=_("Listener for hotplug events."), where=[PluginDescriptor.WHERE_AUTOSTART], needsRestart=True, fnc=autostart)
