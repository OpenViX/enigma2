from __future__ import print_function
from __future__ import absolute_import
import six

import chardet
import datetime
import os
import struct
import time
from sys import maxsize

from enigma import eActionMap, eHdmiCEC, eTimer
import NavigationInstance

from Components.config import config, ConfigSelection, ConfigYesNo, ConfigSubsection, ConfigText, ConfigCECAddress, ConfigLocations, ConfigDirectory
import Screens.Standby
from Tools.Directories import pathExists
from Tools import Notifications
from Tools.StbHardware import getFPWasTimerWakeup

LOGPATH = "/hdd/"
LOGFILE = "hdmicec.log"

config.hdmicec = ConfigSubsection()
config.hdmicec.enabled = ConfigYesNo(default=False)
config.hdmicec.control_tv_standby = ConfigYesNo(default=True)
config.hdmicec.control_tv_wakeup = ConfigYesNo(default=True)
config.hdmicec.report_active_source = ConfigYesNo(default=True)
config.hdmicec.report_active_menu = ConfigYesNo(default=True)
config.hdmicec.handle_tv_standby = ConfigYesNo(default=True)
config.hdmicec.handle_tv_wakeup = ConfigYesNo(default=True)
config.hdmicec.tv_wakeup_detection = ConfigSelection(
	choices={
	"wakeup": _("Wakeup"),
	"requestphysicaladdress": _("Request for physical address report"),
	"tvreportphysicaladdress": _("TV physical address report"),
	"routingrequest": _("Routing request"),
	"sourcerequest": _("Source request"),
	"streamrequest": _("Stream request"),
	"requestvendor": _("Request for vendor report"),
	"osdnamerequest": _("OSD name request"),
	"activity": _("Any activity"),
	},
	default="streamrequest")
config.hdmicec.tv_wakeup_command = ConfigSelection(
	choices={
	"imageview": _("Image View On"),
	"textview": _("Text View On"),
	},
	default="imageview")
config.hdmicec.fixed_physical_address = ConfigText(default="0.0.0.0")
config.hdmicec.volume_forwarding = ConfigYesNo(default=False)
config.hdmicec.control_receiver_wakeup = ConfigYesNo(default=False)
config.hdmicec.control_receiver_standby = ConfigYesNo(default=False)
config.hdmicec.handle_deepstandby_events = ConfigYesNo(default=False)
choicelist = []
for i in (10, 50, 100, 150, 250, 500, 750, 1000):
	choicelist.append(("%d" % i, _("%d ms") % i))
config.hdmicec.minimum_send_interval = ConfigSelection(default="0", choices=[("0", _("Disabled"))] + choicelist)
choicelist = []
for i in [3] + list(range(5, 65, 5)):
	choicelist.append(("%d" % i, _("%d sec") % i))
config.hdmicec.repeat_wakeup_timer = ConfigSelection(default="3", choices=[("0", _("Disabled"))] + choicelist)
config.hdmicec.debug = ConfigSelection(default="0", choices=[("0", _("Disabled")), ("1", _("Messages")), ("2", _("Key Events")), ("3", _("All"))])
config.hdmicec.bookmarks = ConfigLocations(default=[LOGPATH])
config.hdmicec.log_path = ConfigDirectory(LOGPATH)
config.hdmicec.next_boxes_detect = ConfigYesNo(default=False)
config.hdmicec.sourceactive_zaptimers = ConfigYesNo(default=False)

CEC = ["1.1", "1.2", "1.2a", "1.3", "1.3a", "1.4", "2.0?", "unknown"]	# CEC Version's table,  cmdList from http://www.cec-o-matic.com
cmdList = {
	0x00: "<Feature Abort>",
	0x04: "<Image View On>",
	0x05: "<Tuner Step Increment>",
	0x06: "<Tuner Step Decrement>",
	0x07: "<Tuner Device Status>",
	0x08: "<Give Tuner Device Status>",
	0x09: "<Record On>",
	0x0A: "<Record Status>",
	0x0B: "<Record Off>",
	0x0D: "<Text View On>",
	0x0F: "<Record TV Screen>",
	0x1A: "<Give Deck Status>",
	0x1B: "<Deck Status>",
	0x32: "<Set Menu Language>",
	0x33: "<Clear Analogue Timer>",
	0x34: "<Set Analogue Timer>",
	0x35: "<Timer Status>",
	0x36: "<Standby>",
	0x41: "<Play>",
	0x42: "<Deck Control>",
	0x43: "<Timer Cleared Status>",
	0x44: "<User Control Pressed>",
	0x45: "<User Control Released>",
	0x46: "<Give OSD Name>",
	0x47: "<Set OSD Name>",
	0x64: "<Set OSD String>",
	0x67: "<Set Timer Program Title>",
	0x70: "<System Audio Mode Request>",
	0x71: "<Give Audio Status>",
	0x72: "<Set System Audio Mode>",
	0x7A: "<Report Audio Status>",
	0x7D: "<Give System Audio Mode Status>",
	0x7E: "<System Audio Mode Status>",
	0x80: "<Routing Change>",
	0x81: "<Routing Information>",
	0x82: "<Active Source>",
	0x83: "<Give Physical Address>",
	0x84: "<Report Physical Address>",
	0x85: "<Request Active Source>",
	0x86: "<Set Stream Path>",
	0x87: "<Device Vendor ID>",
	0x89: "<Vendor Command><Vendor Specific Data>",
	0x8A: "<Vendor Remote Button Down><Vendor Specific RC Code>",
	0x8B: "<Vendor Remote Button Up>",
	0x8C: "<Give Device Vendor ID>",
	0x8D: "<Menu Request>",
	0x8E: "<Menu Status>",
	0x8F: "<Give Device Power Status>",
	0x90: "<Report Power Status>",
	0x91: "<Get Menu Language>",
	0x92: "<Select Analogue Service>",
	0x93: "<Select Digital Service>",
	0x97: "<Set Digital Timer>",
	0x99: "<Clear Digital Timer>",
	0x9A: "<Set Audio Rate>",
	0x9D: "<Inactive Source>",
	0x9E: "<CEC Version>",
	0x9F: "<Get CEC Version>",
	0xA0: "<Vendor Command With ID>",
	0xA1: "<Clear External Timer>",
	0xA2: "<Set External Timer>",
	0xFF: "<Abort>",
	}


class HdmiCec:
	instance = None

	def __init__(self):
		assert HdmiCec.instance is None, "only one HdmiCec instance is allowed!"
		HdmiCec.instance = self
		self.wait = eTimer()
		self.wait.timeout.get().append(self.sendCmd)
		self.waitKeyEvent = eTimer()
		self.waitKeyEvent.timeout.get().append(self.sendKeyEvent)
		self.queueKeyEvent = []
		self.repeat = eTimer()
		self.repeat.timeout.get().append(self.wakeupMessages)
		self.queue = []

		self.delay = eTimer()
		self.delay.timeout.get().append(self.sendStandbyMessages)
		self.useStandby = True
		self.handlingStandbyFromTV = False

		eHdmiCEC.getInstance().messageReceived.get().append(self.messageReceived)
		config.misc.standbyCounter.addNotifier(self.onEnterStandby, initial_call=False)
		config.misc.DeepStandby.addNotifier(self.onEnterDeepStandby, initial_call=False)
		self.setFixedPhysicalAddress(config.hdmicec.fixed_physical_address.value)

		self.volumeForwardingEnabled = False
		self.volumeForwardingDestination = 0
		self.wakeup_from_tv = False
		eActionMap.getInstance().bindAction("", -maxsize - 1, self.keyEvent)
		config.hdmicec.volume_forwarding.addNotifier(self.configVolumeForwarding)
		config.hdmicec.enabled.addNotifier(self.configVolumeForwarding)
		if config.hdmicec.enabled.value:
			if config.hdmicec.report_active_menu.value:
				if config.hdmicec.report_active_source.value and NavigationInstance.instance and not NavigationInstance.instance.isRestartUI():
					self.sendMessage(0, "sourceinactive")
				self.sendMessage(0, "menuactive")
			if config.hdmicec.handle_deepstandby_events.value and not getFPWasTimerWakeup():
				self.onLeaveStandby()

	def getPhysicalAddress(self):
		physicaladdress = eHdmiCEC.getInstance().getPhysicalAddress()
		hexstring = "%04x" % physicaladdress
		return hexstring[0] + "." + hexstring[1] + "." + hexstring[2] + "." + hexstring[3]

	def setFixedPhysicalAddress(self, address):
		if address != config.hdmicec.fixed_physical_address.value:
			config.hdmicec.fixed_physical_address.value = address
			config.hdmicec.fixed_physical_address.save()
		hexstring = address[0] + address[2] + address[4] + address[6]
		eHdmiCEC.getInstance().setFixedPhysicalAddress(int(float.fromhex(hexstring)))

	def messageReceived(self, message):
		if config.hdmicec.enabled.value:
			cmd = message.getCommand()
			data = 16 * "\x00"
			length = message.getData(data, len(data))
			if config.hdmicec.debug.value != "0":
				self.debugRx(length, cmd, data)
			if cmd == 0x00:
				if length == 0: # only polling message ( it's some as ping )
					print("eHdmiCec: received polling message")
				else:
					if data[0] == "\x44":	# feature abort
						print("eHdmiCec: volume forwarding not supported by device %02x" % (message.getAddress()))
						self.volumeForwardingEnabled = False
			elif cmd == 0x46: 			# request name
				self.sendMessage(message.getAddress(), "osdname")
			elif cmd == 0x7e or cmd == 0x72: 	# system audio mode status
				if data[0] == "\x01":
					self.volumeForwardingDestination = 5 # on: send volume keys to receiver
				else:
					self.volumeForwardingDestination = 0 # off: send volume keys to tv
				if config.hdmicec.volume_forwarding.value:
					print("eHdmiCec: volume forwarding to device %02x enabled" % self.volumeForwardingDestination)
					self.volumeForwardingEnabled = True
			elif cmd == 0x8f: # request power status
				if Screens.Standby.inStandby:
					self.sendMessage(message.getAddress(), "powerinactive")
				else:
					self.sendMessage(message.getAddress(), "poweractive")
			elif cmd == 0x83: # request address
				self.sendMessage(message.getAddress(), "reportaddress")
			elif cmd == 0x85: # request active source
				if not Screens.Standby.inStandby:
					if config.hdmicec.report_active_source.value:
						self.sendMessage(message.getAddress(), "sourceactive")
			elif cmd == 0x86: # request streaming path
				physicaladdress = ord(data[0]) * 256 + ord(data[1])
				ouraddress = eHdmiCEC.getInstance().getPhysicalAddress()
				if physicaladdress == ouraddress:
					if not Screens.Standby.inStandby:
						if config.hdmicec.report_active_source.value:
							self.sendMessage(message.getAddress(), "sourceactive")
			elif cmd == 0x8c: # request vendor id
				self.sendMessage(message.getAddress(), "vendorid")
			elif cmd == 0x8d: # menu request
				requesttype = ord(data[0])
				if requesttype == 2: # query
					if Screens.Standby.inStandby:
						self.sendMessage(message.getAddress(), "menuinactive")
					else:
						self.sendMessage(message.getAddress(), "menuactive")
			elif cmd == 0x90: # receive powerstatus report
				if ord(data[0]) == 0: # some box is powered
					if config.hdmicec.next_boxes_detect.value:
						self.useStandby = False
					print("[HDMI-CEC] powered box found")
			elif cmd == 0x9F: # request get CEC version
				self.sendMessage(message.getAddress(), "sendcecversion")

			# handle standby request from the tv
			if cmd == 0x36 and config.hdmicec.handle_tv_standby.value:
				self.handlingStandbyFromTV = True	# avoid echoing the "System Standby" command back to the tv
				self.standby()				# handle standby
				self.handlingStandbyFromTV = False	# after handling the standby command, we are free to send "standby" ourselves again

			# handle wakeup requests from the tv
			if Screens.Standby.inStandby and config.hdmicec.handle_tv_wakeup.value:
				if ((cmd == 0x04 and config.hdmicec.tv_wakeup_detection.value == "wakeup") or
					(cmd == 0x83 and config.hdmicec.tv_wakeup_detection.value == "requestphysicaladdress") or
					(cmd == 0x85 and config.hdmicec.tv_wakeup_detection.value == "sourcerequest") or
					(cmd == 0x8C and config.hdmicec.tv_wakeup_detection.value == "requestvendor") or
					(cmd == 0x46 and config.hdmicec.tv_wakeup_detection.value == "osdnamerequest") or
					(cmd != 0x36 and config.hdmicec.tv_wakeup_detection.value == "activity")):
					self.wakeup()
				elif ((cmd == 0x80 and config.hdmicec.handle_tv_wakeup.value == "routingrequest") or (cmd == 0x86 and config.hdmicec.handle_tv_wakeup.value == "streamrequest")):
					physicaladdress = ord(data[0]) * 256 + ord(data[1])
					ouraddress = eHdmiCEC.getInstance().getPhysicalAddress()
					if physicaladdress == ouraddress:
						self.wakeup()
				elif cmd == 0x84 and config.hdmicec.tv_wakeup_detection.value == "tvreportphysicaladdress":
					if (ord(data[0]) * 256 + ord(data[1])) == 0 and ord(data[2]) == 0:
						self.wakeup()


	def sendMessage(self, address, message):
		cmd = 0
		data = ""
		if message == "sourceinactive":
			cmd = 0x9d
			data = self.setData()
		elif message == "menuactive":
			cmd = 0x8e
			data = struct.pack("B", 0x00)
		elif message == "menuinactive":
			cmd = 0x8e
			data = struct.pack("B", 0x01)
		elif message == "poweractive":
			cmd = 0x90
			data = struct.pack("B", 0x00)
		elif message == "powerinactive":
			cmd = 0x90
			data = struct.pack("B", 0x01)
		elif message == "keypoweron":
			cmd = 0x44
			data = struct.pack("B", 0x6d)
		elif message == "keypoweroff":
			cmd = 0x44
			data = struct.pack("B", 0x6c)
		elif message == "sendcecversion":
			cmd = 0x9E
			data = struct.pack("B", 0x04) # v1.3a
		elif message == "sourceactive":
			address = 0x0f # use broadcast for active source command
			cmd = 0x82
			data = self.setData()			
		elif message == "reportaddress":
			address = 0x0f # use broadcast address
			cmd = 0x84
			data = self.setData(True)			
		elif message == "setsystemaudiomode":
			cmd = 0x70
			address = 0x05
			data = self.setData()
		if data:				# keep cmd+data calls above this line so binary data converted
			encoder = chardet.detect(data)["encoding"]
			data = six.ensure_str(data, encoding=encoder, errors='ignore')	
			print("[eHdmiCec][sendMessage]: encoder=%s, cmd = %s, data=%s" % (encoder, cmd, data))
		elif message == "wakeup":
			if config.hdmicec.tv_wakeup_command.value == "textview":
				cmd = 0x0d
			else:
				cmd = 0x04
		elif message == "standby":
			cmd = 0x36
		elif message == "givesystemaudiostatus":
			cmd = 0x7d
			address = 0x05
		elif message == "requestactivesource":
			address = 0x0f # use broadcast address
			cmd = 0x85
		elif message == "getpowerstatus":
			self.useStandby = True
			address = 0x0f # use broadcast address => boxes will send info
			cmd = 0x8f
		elif message == "osdname":
			cmd = 0x47
			data = os.uname()[1]
			data = data[:14]
		elif message == "vendorid":
			cmd = 0x87
			data = "\x00\x00\x00"	

		#	print("[eHdmiCec][sendMessage3]: cmd=%s,data=%s" % (cmd, data))
		if cmd:
			if config.hdmicec.minimum_send_interval.value != "0":
				self.queue.append((address, cmd, data))
				if not self.wait.isActive():
					self.wait.start(int(config.hdmicec.minimum_send_interval.value), True)
			else:
				print("[eHdmiCec][sendmessage4]: address=%s, cmd=%s,data=%s" % (address, cmd, data))			
				eHdmiCEC.getInstance().sendMessage(address, cmd, data, len(data))
			if config.hdmicec.debug.value in ["1", "3"]:
				self.debugTx(address, cmd, data)

	def sendCmd(self):
		if len(self.queue):
			(address, cmd, data) = self.queue.pop(0)
			print("[eHdmiCec][sendmessage3]: address=%s, cmd=%s,data=%s" % (address, cmd, data))			
			eHdmiCEC.getInstance().sendMessage(address, cmd, data, len(data))
			self.wait.start(int(config.hdmicec.minimum_send_interval.value), True)

	def sendMessages(self, address, messages):
		for message in messages:
			self.sendMessage(address, message)

	def setData(self, devicetypeSend=False):
		physicaladdress = eHdmiCEC.getInstance().getPhysicalAddress()
		if devicetypeSend:
			devicetype = eHdmiCEC.getInstance().getDeviceType()
			return struct.pack("BBB", int(physicaladdress / 256), int(physicaladdress % 256), devicetype)
		return struct.pack("BB", int(physicaladdress / 256), int(physicaladdress % 256))

	def wakeupMessages(self):
		if config.hdmicec.enabled.value:
			messages = []
			if config.hdmicec.control_tv_wakeup.value:
				if not self.wakeup_from_tv:
					messages.append("wakeup")
			self.wakeup_from_tv = False
			if config.hdmicec.report_active_source.value:
				messages.append("sourceactive")
			if config.hdmicec.report_active_menu.value:
				messages.append("menuactive")
			if messages:
				self.sendMessages(0, messages)

			if config.hdmicec.control_receiver_wakeup.value:
				self.sendMessage(5, "keypoweron")
				self.sendMessage(5, "setsystemaudiomode")

	def standbyMessages(self):
		if config.hdmicec.enabled.value:
			if config.hdmicec.next_boxes_detect.value:
				self.secondBoxActive()
				self.delay.start(1000, True)
			else:
				self.sendStandbyMessages()

	def sendStandbyMessages(self):
			messages = []
			if config.hdmicec.control_tv_standby.value:
				if self.useStandby and not self.handlingStandbyFromTV:
					messages.append("standby")
				else:
					messages.append("sourceinactive")
					self.useStandby = True
			else:
				if config.hdmicec.report_active_source.value:
					messages.append("sourceinactive")
				if config.hdmicec.report_active_menu.value:
					messages.append("menuinactive")
			if messages:
				self.sendMessages(0, messages)

			if config.hdmicec.control_receiver_standby.value:
				self.sendMessage(5, "keypoweroff")
				self.sendMessage(5, "standby")

	def secondBoxActive(self):
		self.sendMessage(0, "getpowerstatus")

	def onLeaveStandby(self):
		self.wakeupMessages()
		if int(config.hdmicec.repeat_wakeup_timer.value):
			self.repeat.startLongTimer(int(config.hdmicec.repeat_wakeup_timer.value))

	def onEnterStandby(self, configElement):
		Screens.Standby.inStandby.onClose.append(self.onLeaveStandby)
		self.repeat.stop()
		self.standbyMessages()

	def onEnterDeepStandby(self, configElement):
		if config.hdmicec.enabled.value and config.hdmicec.handle_deepstandby_events.value:
			if config.hdmicec.next_boxes_detect.value:
				self.delay.start(750, True)
			else:
				self.sendStandbyMessages()

	def standby(self):
		if not Screens.Standby.inStandby:
			Notifications.AddNotification(Screens.Standby.Standby)

	def wakeup(self):
		self.wakeup_from_tv = True
		if Screens.Standby.inStandby:
			Screens.Standby.inStandby.Power()

	def configVolumeForwarding(self, configElement):
		if config.hdmicec.enabled.value and config.hdmicec.volume_forwarding.value:
			self.volumeForwardingEnabled = True
			self.sendMessage(0x05, "givesystemaudiostatus")
		else:
			self.volumeForwardingEnabled = False

	def keyEvent(self, keyCode, keyEvent):
		if not self.volumeForwardingEnabled:
			return
		cmd = 0
		data = ""
		if keyEvent == 0 or keyEvent == 2:
			if keyCode == 113:
				cmd = 0x44
				data = struct.pack("B", 0x43)
			if keyCode == 114:
				cmd = 0x44
				data = struct.pack("B", 0x42)
			if keyCode == 115:
				cmd = 0x44
				data = struct.pack("B", 0x41)
		if keyEvent == 1:
			if keyCode == 115 or keyCode == 114 or keyCode == 113:
				cmd = 0x45
		if cmd:
			#	print("[eHdmiCec][keyEvent1]: cmd=%s,data=%s" % (cmd, data))
			if data:
				encoder = chardet.detect(data)["encoding"]
				data = six.ensure_str(data, encoding=encoder, errors='ignore')	
				print("[eHdmiCec][keyEvent: encoder=%s, cmd = %s, data=%s" % (encoder, cmd, data))			
			if config.hdmicec.minimum_send_interval.value != "0":
				self.queueKeyEvent.append((self.volumeForwardingDestination, cmd, data))
				if not self.waitKeyEvent.isActive():
					self.waitKeyEvent.start(int(config.hdmicec.minimum_send_interval.value), True)
			else:
				#	print("[eHdmiCec][keyEvent3]: forwarding dest=%s, cmd=%s,data=%s" % (self.volumeForwardingDestination, cmd, data))			
				eHdmiCEC.getInstance().sendMessage(self.volumeForwardingDestination, cmd, data, len(data))
			if config.hdmicec.debug.value in ["2", "3"]:
				self.debugTx(self.volumeForwardingDestination, cmd, data)
			return 1
		else:
			return 0

	def sendKeyEvent(self):
		if len(self.queueKeyEvent):
			(address, cmd, data) = self.queueKeyEvent.pop(0)
			print("[eHdmiCec][sendmessage2]: address=%s, cmd=%s,data=%s" % (address, cmd, data))
			eHdmiCEC.getInstance().sendMessage(address, cmd, data, len(data))
			self.waitKeyEvent.start(int(config.hdmicec.minimum_send_interval.value), True)

	def debugTx(self, address, cmd, data):
		txt = self.now(True) + self.opCode(cmd, True) + " " + "%02X" % (cmd) + " "
		tmp = ""
		if len(data):
			if cmd in [0x32, 0x47]:
				for i in range(len(data)):
					tmp += "%s" % data[i]
			else:
				for i in range(len(data)):
					tmp += "%02X" % ord(data[i]) + " "
		tmp += 48 * " "
		self.fdebug(txt + tmp[:48] + "[0x%02X]" % (address) + "\n")

	def debugRx(self, length, cmd, data):
		txt = self.now()
		if cmd == 0 and length == 0:
			txt += self.opCode(cmd) + " - "
		else:
			if cmd == 0:
				txt += "<Feature Abort>" + 13 * " " + "<  " + "%02X" % (cmd) + " "
			else:
				txt += self.opCode(cmd) + " " + "%02X" % (cmd) + " "
			for i in range(length - 1):
				if cmd in [0x32, 0x47]:
					txt += "%s" % data[i]
				elif cmd == 0x9e:
					txt += "%02X" % ord(data[i]) + 3 * " " + "[version: %s]" % CEC[ord(data[i])]
				else:
					txt += "%02X" % ord(data[i]) + " "
		txt += "\n"
		self.fdebug(txt)

	def opCode(self, cmd, out=False):
		send = "<"
		if out:
			send = ">"
		opCode = ""
		if cmd in cmdList:
			opCode += "%s" % cmdList[cmd]
		opCode += 30 * " "
		return opCode[:28] + send + " "

	def now(self, out=False, fulldate=False):
		send = "Rx: "
		if out:
			send = "Tx: "
		now = datetime.datetime.now()
		if fulldate:
			return send + now.strftime("%d-%m-%Y %H:%M:%S") + 2 * " "
		return send + now.strftime("%H:%M:%S") + 2 * " "

	def fdebug(self, output):
		log_path = config.hdmicec.log_path.value
		path = os.path.join(log_path, LOGFILE)
		if pathExists(log_path):
			fp = open(path, "a")
			fp.write(output)
			fp.close()


hdmi_cec = HdmiCec()
