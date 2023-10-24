import chardet
import datetime
from os import path, uname
import struct
from sys import maxsize

from enigma import eActionMap, eHdmiCEC, eTimer
import NavigationInstance

from Components.config import config
import Screens.Standby
from Tools.Directories import pathExists
from Tools import Notifications
from Tools.StbHardware import getFPWasTimerWakeup


CEC = ["1.1", "1.2", "1.2a", "1.3", "1.3a", "1.4", "2.0?", "unknown"]  # CEC Version's table,  cmdList from http://www.cec-o-matic.com
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
	0x87: "<Reporting Device Vendor ID>",				# device (TV, AV receiver, audio device) returns its vendor ID (3 bytes)
	0x89: "<Vendor Command><Vendor Specific Data>",
	0x8A: "<Vendor Remote Button Down><Vendor Specific RC Code>",
	0x8B: "<Vendor Remote Button Up>",
	0x8C: "<Request Device Vendor ID>",				# request vendor ID from device(TV, AV receiver, audio device)
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

CtrlByte0 = {		# Information only: control byte 0 status/action request by command (see cmdList)
	0x00: {0x00: "<Unrecognized opcode>",
			0x01: "<Not in correct mode to respond>",
			0x02: "<Cannot provide source>",
			0x03: "<Invalid operand>",
			0x04: "<Refused>"},
	0x08: {0x01: "<On>",
			0x02: "<Off>",
			0x03: "<Once>"},
	0x0A: {0x01: "<Recording currently selected source>",
			0x02: "<Recording Digital Service>",
			0x03: "<Recording Analogue Service>",
			0x04: "<Recording External Input>",
			0x05: "<No recording - unable to record Digital Service>",
			0x06: "<No recording - unable to record Analogue Service>",
			0x07: "<No recording - unable to select required Service>",
			0x09: "<No recording - unable External plug number>",
			0x0A: "<No recording - unable External plug number>",
			0x0B: "<No recording - CA system not supported>",
			0x0C: "<No recording - No or Insufficent CA Entitlements>",
			0x0D: "<No recording - No allowed to copy source>",
			0x0E: "<No recording - No futher copies allowed>",
			0x10: "<No recording - no media>",
			0x11: "<No recording - playing>",
			0x12: "<No recording - already recording>",
			0x13: "<No recording - media protected>",
			0x14: "<No recording - no source signa>",
			0x15: "<No recording - media problem>",
			0x16: "<No recording - no enough space available>",
			0x17: "<No recording - Parental Lock On>",
			0x1A: "<Recording terminated normally>",
			0x1B: "<Recording has already terminated>",
			0x1F: "<No recording - other reason>"},
	0x1B: {0x11: "<Play>",
			0x12: "<Record",
			0x13: "<Play Reverse>",
			0x14: "<Still>",
			0x15: "<Slow>",
			0x16: "<Slow Reverse>",
			0x17: "<Fast Forward>",
			0x18: "<Fast Reverse>",
			0x19: "<No Media>",
			0x1A: "<Stop>",
			0x1B: "<Skip Forward / Wind>",
			0x1C: "<Skip Reverse / Rewind>",
			0x1D: "<Index Search Forward>",
			0x1E: "<Index Search Reverse>",
			0x1F: "<Other Status>"},
	0x1A: {0x01: "<On>",
			0x02: "<Off>",
			0x03: "<Once>"},
	0x41: {0x05: "<Play Forward Min Speed>",
			0x06: "<Play Forward Medium Speed>",
			0x07: "<Play Forward Max Speed>",
			0x09: "<Play Reverse Min Speed>",
			0x0A: "<Play Reverse Medium Speed>",
			0x0B: "<Play Reverse Max Speed>",
			0x15: "<Slow Forward Min Speed>",
			0x16: "<Slow Forward Medium Speed>",
			0x17: "<Slow Forward Max Speed>",
			0x19: "<Slow Reverse Min Speed>",
			0x1A: "<Slow Reverse Medium Speed>",
			0x1B: "<Slow Reverse Max Speed>",
			0x20: "<Play Reverse>",
			0x24: "<Play Forward>",
			0x25: "<Play Still>"},
	0x42: {0x01: "<Skip Forward / Wind>",
			0x02: "<Skip Reverse / Rewind",
			0x03: "<Stop>",
			0x04: "<Eject>"},
	0x43: {0x00: "<Timer not cleared - recording>",
			0x01: "<Timer not cleared - no matching>",
			0x02: "<Timer not cleared - no info available>",
			0x80: "<Timer cleared>"},
	0x44: {0x00: "<Select>",
			0x01: "<Up>",
			0x02: "<Down>",
			0x03: "<Left>",
			0x04: "<Right>",
			0x05: "<Right-Up>",
			0x06: "<Right-Down>",
			0x07: "<Left-Up>",
			0x08: "<Left-Down>",
			0x09: "<Root Menu>",
			0x0A: "<Setup Menu>",
			0x0B: "<Contents Menu>",
			0x0C: "<Favorite Menu>",
			0x0D: "<Exit>",
			0x0E: "<Reserved 0x0E>",
			0x0F: "<Reserved 0x0F>",
			0x10: "<Media Top Menu>",
			0x11: "<Media Context-sensitive Menu>",
			0x12: "<Reserved 0x12>",
			0x13: "<Reserved 0x13>",
			0x14: "<Reserved 0x14>",
			0x15: "<Reserved 0x15>",
			0x16: "<Reserved 0x16>",
			0x17: "<Reserved 0x17>",
			0x18: "<Reserved 0x18>",
			0x19: "<Reserved 0x19>",
			0x1A: "<Reserved 0x1A>",
			0x1B: "<Reserved 0x1B>",
			0x1C: "<Reserved 0x1C>",
			0x1D: "<Number Entry Mode>",
			0x1E: "<Number 11>",
			0x1F: "<Number 12>",
			0x20: "<Number 0 or Number 10>",
			0x21: "<Number 1>",
			0x22: "<Number 2>",
			0x23: "<Number 3>",
			0x24: "<Number 4>",
			0x25: "<Number 5>",
			0x26: "<Number 6>",
			0x27: "<Number 7>",
			0x28: "<Number 8>",
			0x29: "<Number 9>",
			0x2A: "<Dot>",
			0x2B: "<Enter>",
			0x2C: "<Clear>",
			0x2D: "<Reserved 0x2D>",
			0x2E: "<Reserved 0x2E>",
			0x2F: "<Next Favorite>",
			0x30: "<Channel Up>",
			0x31: "<Channel Down>",
			0x32: "<Previous Channel>",
			0x33: "<Sound Select>",
			0x34: "<Input Select>",
			0x35: "<Display Informationen>",
			0x36: "<Help>",
			0x37: "<Page Up>",
			0x38: "<Page Down>",
			0x39: "<Reserved 0x39>",
			0x3A: "<Reserved 0x3A>",
			0x3B: "<Reserved 0x3B>",
			0x3C: "<Reserved 0x3C>",
			0x3D: "<Reserved 0x3D>",
			0x3E: "<Reserved 0x3E>",
			0x3F: "<Reserved 0x3F>",
			0x40: "<Power>",
			0x41: "<Volume Up>",
			0x42: "<Volume Down>",
			0x43: "<Mute>",
			0x44: "<Play>",
			0x45: "<Stop>",
			0x46: "<Pause>",
			0x47: "<Record>",
			0x48: "<Rewind>",
			0x49: "<Fast Forward>",
			0x4A: "<Eject>",
			0x4B: "<Forward>",
			0x4C: "<Backward>",
			0x4D: "<Stop-Record>",
			0x4E: "<Pause-Record>",
			0x4F: "<Reserved 0x4F>",
			0x50: "<Angle>",
			0x51: "<Sub Picture>",
			0x52: "<Video On Demand>",
			0x53: "<Electronic Program Guide>",
			0x54: "<Timer programming>",
			0x55: "<Initial Configuration>",
			0x56: "<Reserved 0x56>",
			0x57: "<Reserved 0x57>",
			0x58: "<Reserved 0x58>",
			0x59: "<Reserved 0x59>",
			0x5A: "<Reserved 0x5A>",
			0x5B: "<Reserved 0x5B>",
			0x5C: "<Reserved 0x5C>",
			0x5D: "<Reserved 0x5D>",
			0x5E: "<Reserved 0x5E>",
			0x5F: "<Reserved 0x5F>",
			0x60: "<Play Function>",
			0x61: "<Pause-Play Function>",
			0x62: "<Record Function>",
			0x63: "<Pause-Record Function>",
			0x64: "<Stop Function>",
			0x65: "<Mute Function>",
			0x66: "<Restore Volume Function>",
			0x67: "<Tune Function>",
			0x68: "<Select Media Function>",
			0x69: "<Select A/V Input Function>",
			0x6A: "<Select Audio Input Function>",
			0x6B: "<Power Toggle Function>",
			0x6C: "<Power Off Function>",
			0x6D: "<Power On Function>",
			0x6E: "<Reserved 0x6E>",
			0x6F: "<Reserved 0x6E>",
			0x70: "<Reserved 0x70>",
			0x71: "<F1 (Blue)>",
			0x72: "<F2 (Red)>",
			0x73: "<F3 (Green)>",
			0x74: "<F4 (Yellow)>",
			0x75: "<F5>",
			0x76: "<Data>",
			0x77: "<Reserved 0x77>",
			0x78: "<Reserved 0x78>",
			0x79: "<Reserved 0x79>",
			0x7A: "<Reserved 0x7A>",
			0x7B: "<Reserved 0x7B>",
			0x7C: "<Reserved 0x7C>",
			0x7D: "<Reserved 0x7D>",
			0x7E: "<Reserved 0x7E>",
			0x7F: "<Reserved 0x7F>"},
	0x64: {0x00: "<Display for default time>",
			0x40: "<Display until cleared>",
			0x80: "<Clear previous message>",
			0xC0: "<Reserved for future use>"},
	0x72: {0x00: "<Off>",
			0x01: "<On>"},
	0x7E: {0x00: "<Off>",
			0x01: "<On>"},
	0x84: {0x00: "<TV>",
			0x01: "<Recording Device>",
			0x02: "<Reserved>",
			0x03: "<Tuner>",
			0x04: "<Playback Devive>",
			0x05: "<Audio System>",
			0x06: "<Pure CEC Switch>",
			0x07: "<Video Processor>"},
	0x8D: {0x00: "<Activate>",
			0x01: "<Deactivate>",
			0x02: "<Query>"},
	0x8E: {0x00: "<Activated>",
			0x01: "<Deactivated>"},
	0x90: {0x00: "<On>",
			0x01: "<Standby>",
			0x02: "<In transition Standby to On>",
			0x03: "<In transition On to Standby>"},
	0x9A: {0x00: "<Rate Control Off>",
			0x01: "<WRC Standard Rate: 100% rate>",
			0x02: "<WRC Fast Rate: Max 101% rate>",
			0x03: "<WRC Slow Rate: Min 99% rate",
			0x04: "<NRC Standard Rate: 100% rate>",
			0x05: "<NRC Fast Rate: Max 100.1% rate>",
			0x06: "<NRC Slow Rate: Min 99.9% rate"},
	0x9E: {0x00: "<1.1>",
			0x01: "<1.2>",
			0x02: "<1.2a>",
			0x03: "<1.3>",
			0x04: "<1.3a>",
			0x05: "<1.4>",
			0x06: "<2.0>"},
	}


def getPhysicalAddress():
	physicaladdress = eHdmiCEC.getInstance().getPhysicalAddress()
	hexstring = "%04x" % physicaladdress
	return hexstring[0] + "." + hexstring[1] + "." + hexstring[2] + "." + hexstring[3]


def setFixedPhysicalAddress(address):
	hexstring = address[0] + address[2] + address[4] + address[6]
	eHdmiCEC.getInstance().setFixedPhysicalAddress(int(float.fromhex(hexstring)))


class HdmiCec:
	instance = None

	def __init__(self):
		assert HdmiCec.instance is None, "only one HdmiCec instance is allowed!"
		HdmiCec.instance = self
		self.wait = eTimer()
		self.wait.timeout.get().append(self.sendMsgQ)
		self.queue = []			# if config.hdmicec.minimum_send_interval.value != "0" queue send message ->  (sendMsgQ)
		self.waitKeyEvent = eTimer()
		self.waitKeyEvent.timeout.get().append(self.sendKeyEventQ)
		self.queueKeyEvent = []		# if config.hdmicec.minimum_send_interval.value != "0" queue key event -> sendKeyEventQ
		self.repeat = eTimer()
		self.repeat.timeout.get().append(self.sendWakeupMessages)
		self.delay = eTimer()
		self.delay.timeout.get().append(self.sendStandbyMessages)
		self.useStandby = True
		self.handlingStandbyFromTV = False
		if config.hdmicec.enabled.value and config.hdmicec.fixed_physical_address.value[1:3] != ".0":
			print("[HdmiCEC][init]phsyical address changed by setup value:", config.hdmicec.fixed_physical_address.value)
			setFixedPhysicalAddress(config.hdmicec.fixed_physical_address.value)
		else:
			print("[HdmiCEC][init] no set physical address ")
			setFixedPhysicalAddress("0.0.0.0")			# no fixed physical address send 0 to eHdmiCec C++ driver
		eHdmiCEC.getInstance().messageReceived.get().append(self.messageReceived)
		config.misc.standbyCounter.addNotifier(self.onEnterStandby, initial_call=False)
		# config.misc.DeepStandby.addNotifier(self.onEnterDeepStandby, initial_call=False)
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

	def messageReceived(self, message):
		if config.hdmicec.enabled.value:
			data = 16 * "\x00"
			cmd = message.getCommand()
			CECcmd = cmdList.get(cmd, "<Polling Message>")
			length = message.getData(data, len(data))
			ctrl0 = message.getControl0()
			ctrl1 = message.getControl1()
			ctrl2 = message.getControl2()
			msgaddress = message.getAddress()			# 0 = TV, 5 = receiver 15 = broadcast
			print("[HdmiCEC][messageReceived0]: msgaddress=%s  CECcmd=%s, cmd=%X, ctrl0=%s, length=%s" % (msgaddress, CECcmd, cmd, ctrl0, length))
			if config.hdmicec.debug.value != "0":
				self.debugRx(length, cmd, ctrl0)
			if msgaddress > 15:  # workaround for wrong address from driver (e.g. hd51, message comes from tv -> address is only sometimes 0, dm920, same tv -> address is always 0)
				print("[HdmiCEC][messageReceived1a]: msgaddress > 15 reset to 0")
				msgaddress = 0
			if cmd == 0x00:
				if length == 0: 			# only polling message ( it's same as ping )
					print("[HdmiCEC][messageReceived1b]: received polling message")
				else:
					if ctrl0 == 68:		# feature abort
						print("[HdmiCEC][messageReceived2]: volume forwarding not supported by device %02x" % (msgaddress))
						self.volumeForwardingEnabled = False
			elif cmd == 0x46: 				# request name
				self.sendMessage(msgaddress, "osdname")
			elif cmd == 0x72 or cmd == 0x7e: 		# system audio mode status 114 or 126
				if ctrl0 == 1:
					self.volumeForwardingDestination = 5 		# on: send volume keys to receiver
				else:
					self.volumeForwardingDestination = 0 		# off: send volume keys to tv
				print("[HdmiCEC][messageReceived4]: volume forwarding=%s, msgaddress=%s" % (self.volumeForwardingDestination, msgaddress))
				if config.hdmicec.volume_forwarding.value:
					print("[HdmiCEC][messageReceived5]: volume forwarding to device %02x enabled" % self.volumeForwardingDestination)
					self.volumeForwardingEnabled = True
			elif cmd == 0x83: 				# request address
				self.sendMessage(msgaddress, "reportaddress")
			elif cmd == 0x85: 				# request active source
				if not Screens.Standby.inStandby:
					if config.hdmicec.report_active_source.value:
						self.sendMessage(msgaddress, "sourceactive")
			elif cmd == 0x86:
				physicaladdress = ctrl0 * 256 + ctrl1  # request streaming path
				ouraddress = eHdmiCEC.getInstance().getPhysicalAddress()
				print("[HdmiCEC][messageReceived6]:cmd 134 physical address=%s ouraddress=%s" % (physicaladdress, ouraddress))
				if physicaladdress == ouraddress:
					if not Screens.Standby.inStandby:
						if config.hdmicec.report_active_source.value:
							self.sendMessage(msgaddress, "sourceactive")
			elif cmd == 0x8c: 				# request vendor id
				self.sendMessage(msgaddress, "vendorid")
			elif cmd == 0x8d: 				# menu request
				if ctrl0 == 1: 			# query
					if Screens.Standby.inStandby:
						self.sendMessage(msgaddress, "menuinactive")
					else:
						self.sendMessage(msgaddress, "menuactive")
			elif cmd == 0x8f: 				# request power status
				if Screens.Standby.inStandby:
					self.sendMessage(msgaddress, "powerinactive")
				else:
					self.sendMessage(msgaddress, "poweractive")
			elif cmd == 0x90: 				# receive powerstatus report
				if ctrl0 == 0: 			# some box is powered
					if config.hdmicec.next_boxes_detect.value:
						self.useStandby = False
					print("[HDMI-CEC][messageReceived7] powered box found")
			elif cmd == 0x9F: 				# request get CEC version
				self.sendMessage(msgaddress, "sendcecversion")

			if cmd == 0x36 and config.hdmicec.handle_tv_standby.value:  # handle standby request from the tv
				self.handlingStandbyFromTV = True  # avoid echoing the "System Standby" command back to the tv
				self.standby()				# handle standby
				self.handlingStandbyFromTV = False  # after handling the standby command, we are free to send "standby" ourselves again

			if Screens.Standby.inStandby and config.hdmicec.handle_tv_wakeup.value:  # handle wakeup requests from the tv
				if ((cmd == 0x04 and config.hdmicec.tv_wakeup_detection.value == "wakeup") or
					(cmd == 0x83 and config.hdmicec.tv_wakeup_detection.value == "requestphysicaladdress") or
					(cmd == 0x85 and config.hdmicec.tv_wakeup_detection.value == "sourcerequest") or
					(cmd == 0x8C and config.hdmicec.tv_wakeup_detection.value == "requestvendor") or
					(cmd == 0x46 and config.hdmicec.tv_wakeup_detection.value == "osdnamerequest") or
					(cmd != 0x36 and config.hdmicec.tv_wakeup_detection.value == "activity")):
					self.wakeup()
				elif ((cmd == 0x80 and config.hdmicec.handle_tv_wakeup.value == "routingrequest") or (cmd == 0x86 and config.hdmicec.handle_tv_wakeup.value == "streamrequest")):
					physicaladdress = ctrl0 * 256 + ctrl1
					ouraddress = eHdmiCEC.getInstance().getPhysicalAddress()
					print("[HdmiCEC][messageReceived8]:cmd 128 physical address=%s ouraddress=%s" % (physicaladdress, ouraddress))
					if physicaladdress == ouraddress:
						self.wakeup()
				elif cmd == 0x84 and config.hdmicec.tv_wakeup_detection.value == "tvreportphysicaladdress":
					if (ctrl0 * 256 + ctrl1) == 0 and ctrl2 == 0:
						self.wakeup()

	def sendMessage(self, msgaddress, message):
		cmd = 0
		data = ""
		if message == "keypoweroff":
			cmd = 0x44  # 68
			data = struct.pack("B", 0x6c)
		elif message == "keypoweron":
			cmd = 0x44  # 68
			data = struct.pack("B", 0x6d)
		elif message == "setsystemaudiomode":
			cmd = 0x70  # 112
			msgaddress = 0x05
			data = self.packDevAddr()
		elif message == "sourceactive":
			msgaddress = 0x0f  # use broadcast for active source command
			cmd = 0x82  # 130
			data = self.packDevAddr()
		elif message == "reportaddress":
			msgaddress = 0x0f  # use broadcast address
			cmd = 0x84  # 132
			data = self.packDevAddr(True)
		elif message == "vendorid":
			cmd = 0x87
			data = b"\x00\x00\x00"
		elif message == "menuactive":
			cmd = 0x8e  # 142
			data = struct.pack("B", 0x00)
		elif message == "menuinactive":
			cmd = 0x8e  # 142
			data = struct.pack("B", 0x01)
		elif message == "poweractive":
			cmd = 0x90  # 144
			data = struct.pack("B", 0x00)
		elif message == "powerinactive":
			cmd = 0x90  # 144
			data = struct.pack("B", 0x01)
		elif message == "sourceinactive":
			cmd = 0x9d  # 157
			data = self.packDevAddr()
		elif message == "sendcecversion":
			cmd = 0x9E  # 158
			data = struct.pack("B", 0x04)  # v1.3a
		if data:				# keep cmd+data calls above this line so binary data converted
			CECcmd = cmdList.get(cmd, "<Polling Message>")
			if data:
				encoder = chardet.detect(data)["encoding"]
				data = data.decode(encoding=encoder, errors="ignore")
			print("[HdmiCec][sendMessage]: CECcmd=%s  cmd=%X, data=struct.pack" % (CECcmd, cmd))
		elif message == "wakeup":
			if config.hdmicec.tv_wakeup_command.value == "textview":
				cmd = 0x0d
			else:
				cmd = 0x04
		elif message == "standby":
			cmd = 0x36
		elif message == "osdname":
			cmd = 0x47
			data = uname()[1]
			data = data[:14]
		elif message == "givesystemaudiostatus":
			cmd = 0x7d
			msgaddress = 0x05
		elif message == "requestactivesource":
			cmd = 0x85
			msgaddress = 0x0f  # use broadcast address
		elif message == "getpowerstatus":
			self.useStandby = True
			cmd = 0x8f
			msgaddress = 0x0f  # use broadcast msgaddress => boxes will send info
		if cmd != 0:
			CECcmd = cmdList.get(cmd, "<Polling Message>")
			# print("[HdmiCEC][sendMessage3]: CECcmd=%s cmd=%X, msgaddress=%s data=%s" % (CECcmd, cmd, msgaddress, data))
			if config.hdmicec.minimum_send_interval.value != "0":
				self.queue.append((msgaddress, cmd, data))
				if not self.wait.isActive():
					self.wait.start(int(config.hdmicec.minimum_send_interval.value), True)
			else:
				eHdmiCEC.getInstance().sendMessage(msgaddress, cmd, data, len(data))
			if config.hdmicec.debug.value in ["1", "3"]:
				self.debugTx(msgaddress, cmd, data)

	def sendMsgQ(self):
		if len(self.queue):
			(msgaddress, cmd, data) = self.queue.pop(0)
			CECcmd = cmdList.get(cmd, "<Polling Message>")  # noqa: F841
			# print("[HdmiCEC][sendMsgQ1]: msgaddress=%s, CECcmd=%s cmd=%X,data=%s \n" % (msgaddress, CECcmd, cmd, data))
			eHdmiCEC.getInstance().sendMessage(msgaddress, cmd, data, len(data))
			self.wait.start(int(config.hdmicec.minimum_send_interval.value), True)

	def packDevAddr(self, devicetypeSend=False):
		physicaladdress = eHdmiCEC.getInstance().getPhysicalAddress()
		if devicetypeSend:
			devicetype = eHdmiCEC.getInstance().getDeviceType()
			return struct.pack("BBB", int(physicaladdress // 256), int(physicaladdress % 256), devicetype)
		else:
			return struct.pack("BB", int(physicaladdress // 256), int(physicaladdress % 256))

	def secondBoxActive(self):
		self.sendMessage(0, "getpowerstatus")

	def configVolumeForwarding(self, configElement):
		print("[HdmiCEC][configVolumeForwarding]: hdmicec.enabled=%s, hdmicec.volume_forwarding=%s" % (config.hdmicec.enabled.value, config.hdmicec.volume_forwarding.value))
		if config.hdmicec.enabled.value and config.hdmicec.volume_forwarding.value:
			self.sendMessage(0x05, "givesystemaudiostatus")
			self.sendMessage(0x00, "givesystemaudiostatus")
		else:
			self.volumeForwardingEnabled = False

	def onEnterStandby(self, configElement):
		Screens.Standby.inStandby.onClose.append(self.onLeaveStandby)
		self.repeat.stop()
		self.standbyMessages()

	def onEnterDeepStandby(self, configElement):
		if config.hdmicec.enabled.value and config.hdmicec.handle_deepstandby_events.value:
			self.standbyMessages()

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
			self.sendQMessages(0, messages)

		if config.hdmicec.control_receiver_standby.value:
			self.sendMessage(5, "keypoweroff")
			self.sendMessage(5, "standby")

	def standby(self):			# Standby initiated from TV
		if not Screens.Standby.inStandby:
			Notifications.AddNotification(Screens.Standby.Standby)

	def onLeaveStandby(self):
		self.sendWakeupMessages()
		if int(config.hdmicec.repeat_wakeup_timer.value):
			self.repeat.startLongTimer(int(config.hdmicec.repeat_wakeup_timer.value))

	def wakeup(self):
		self.wakeup_from_tv = True
		if Screens.Standby.inStandby:
			Screens.Standby.inStandby.Power()

	def sendWakeupMessages(self):
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
				self.sendQMessages(0, messages)

			if config.hdmicec.control_receiver_wakeup.value:
				self.sendMessage(5, "keypoweron")
				self.sendMessage(5, "setsystemaudiomode")

	def sendQMessages(self, msgaddress, messages):
		for message in messages:
			self.sendMessage(msgaddress, message)

	def keyEvent(self, keyCode, keyEvent):
		if keyCode in (113, 114, 115):						# if not volume key return
			if self.volumeForwardingEnabled or config.hdmicec.force_volume_forwarding.value:
				cmd = 0
				data = ""
				if keyEvent in (0, 2):
					if keyCode == 113:
						cmd = 0x44
						data = struct.pack("B", 0x43)		# 0x43: "<Mute>"
					if keyCode == 114:
						cmd = 0x44
						data = struct.pack("B", 0x42)		# 0x42: "<Volume Down>"
					if keyCode == 115:
						cmd = 0x44
						data = struct.pack("B", 0x41)		# 0x41: "<Volume Up>"
				elif keyEvent == 1:
					cmd = 0x45					# 0x45: "<stop>"
				if cmd != 0:
					if data:
						encoder = chardet.detect(data)["encoding"]
						data = data.decode(encoding=encoder, errors="ignore")
					if config.hdmicec.minimum_send_interval.value != "0":
						self.queueKeyEvent.append((self.volumeForwardingDestination, cmd, data))
						if not self.waitKeyEvent.isActive():
							self.waitKeyEvent.start(int(config.hdmicec.minimum_send_interval.value), True)
					else:
						# print("[HdmiCEC][keyEvent3]: forwarding dest=%s, cmd=%X, data=%s" % (self.volumeForwardingDestination, cmd, data))
						if config.hdmicec.force_volume_forwarding.value:
							eHdmiCEC.getInstance().sendMessage(0, cmd, data, len(data))
							eHdmiCEC.getInstance().sendMessage(5, cmd, data, len(data))
						else:
							eHdmiCEC.getInstance().sendMessage(self.volumeForwardingDestination, cmd, data, len(data))
					if config.hdmicec.debug.value in ["2", "3"]:
						self.debugTx(self.volumeForwardingDestination, cmd, data)
					return 1
				else:
					return 0
			else:
				return
		else:
			return

	def sendKeyEventQ(self):
		if len(self.queueKeyEvent):
			(msgaddress, cmd, data) = self.queueKeyEvent.pop(0)
			# print("[HdmiCEC][sendKeyEventQ]: msgaddress=%s, cmd=%X, data=%s" % (msgaddress, cmd, data))
			eHdmiCEC.getInstance().sendMessage(msgaddress, cmd, data, len(data))
			self.waitKeyEvent.start(int(config.hdmicec.minimum_send_interval.value), True)

	def debugTx(self, msgaddress, cmd, data):
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
		self.fdebug(txt + tmp[:48] + "[0x%02X]" % (msgaddress) + "\n")

	def debugRx(self, length, cmd, ctrl):
		txt = self.now()
		if cmd == 0 and length == 0:
			txt += self.opCode(cmd) + " - "
		else:
			if cmd == 0:
				txt += "<Feature Abort>" + 13 * " " + "<  " + "%02X" % (cmd) + " "
			else:
				txt += self.opCode(cmd) + " " + "%02X" % (cmd) + " "
			if cmd == 0x9e:
				txt += "%02X" % ctrl + 3 * " " + "[version: %s]" % CEC[ctrl]
			else:
				txt += "%02X" % ctrl + " "
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
		logpath = config.hdmicec.log_path.value
		if pathExists(logpath):
			logpath = path.join(logpath, "hdmicec.log")
			fp = open(logpath, "a")
			fp.write(output)
			fp.close()
