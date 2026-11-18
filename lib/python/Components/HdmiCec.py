import datetime
from os import remove
from os.path import exists, join as join
from struct import pack
from sys import maxsize

from enigma import eActionMap, eHdmiCEC, eTimer
import NavigationInstance

from Components.config import config
import Screens.Standby
from Tools.Directories import fileReadLine, pathExists
from Tools import Notifications
from Tools.StbHardware import getFPWasTimerWakeup

CEC = ["1.1", "1.2", "1.2a", "1.3", "1.3a", "1.4", "2.0", "unknown"]  # CEC Version's table,  cmdList from http://www.cec-o-matic.com

CEC_VENDOR_UNKNOWN = 0x000000
CEC_VENDOR_TOSHIBA = 0x000039
CEC_VENDOR_SAMSUNG = 0x0000F0
CEC_VENDOR_DENON = 0x0005CD
CEC_VENDOR_MARANTZ = 0x000678
CEC_VENDOR_LOEWE = 0x000982
CEC_VENDOR_ONKYO = 0x0009B0
CEC_VENDOR_SONOS = 0x0009FD
CEC_VENDOR_MEDION = 0x000CB8
CEC_VENDOR_TOSHIBA2 = 0x000CE7
CEC_VENDOR_APPLE = 0x0010FA
CEC_VENDOR_PULSE_EIGHT = 0x001582
CEC_VENDOR_HARMAN_KARDON2 = 0x001950
CEC_VENDOR_SONOS_ID = 0x00199D
CEC_VENDOR_GOOGLE = 0x001A11
CEC_VENDOR_AKAI = 0x0020C7
CEC_VENDOR_OPPO = 0x0022DE
CEC_VENDOR_AOC = 0x002467
CEC_VENDOR_AMAZON = 0x004571
CEC_VENDOR_LG = 0x00E091
CEC_VENDOR_PANASONIC = 0x008045
CEC_VENDOR_PHILIPS = 0x00903E
CEC_VENDOR_DAEWOO = 0x009053
CEC_VENDOR_YAMAHA = 0x00A0DE
CEC_VENDOR_GRUNDIG = 0x00D0D5
CEC_VENDOR_PIONEER = 0x00E036
CEC_VENDOR_SHARP = 0x08001F
CEC_VENDOR_SONY = 0x080045
CEC_VENDOR_SONY2 = 0x080046
CEC_VENDOR_BROADCOM = 0x18C086
CEC_VENDOR_TEUFEL = 0x232425
CEC_VENDOR_SHARP2 = 0x534850
CEC_VENDOR_VIZIO = 0x6B746D
CEC_VENDOR_MEDIATEK = 0x6D746B
CEC_VENDOR_BENQ = 0x8065E9
CEC_VENDOR_HARMAN_KARDON = 0x9C645E

CEC_VENDOR_ENIGMA2_STB = 0x000934
CEC_OSD_NAME = "Enigma2 STB"


def getCecOsdName():
	name = fileReadLine("/etc/hostname", default=CEC_OSD_NAME) or CEC_OSD_NAME
	name = name.split(".", 1)[0].strip() or CEC_OSD_NAME
	while len(name.encode(encoding='utf-8', errors='ignore')) > 14:
		name = name[:-1].strip()
	return name or CEC_OSD_NAME


CEC_VENDOR = {
	CEC_VENDOR_TOSHIBA: "Toshiba Regza Link",
	CEC_VENDOR_SAMSUNG: "Samsung Anynet+",
	CEC_VENDOR_DENON: "Denon",
	CEC_VENDOR_MARANTZ: "Marantz",
	CEC_VENDOR_LOEWE: "Loewe Digital Link",
	CEC_VENDOR_ONKYO: "Onkyo RIHD",
	CEC_VENDOR_SONOS: "Sonos CEC",
	CEC_VENDOR_MEDION: "Medion",
	CEC_VENDOR_TOSHIBA2: "Toshiba Regza Link",
	CEC_VENDOR_APPLE: "Apple",
	CEC_VENDOR_PULSE_EIGHT: "Pulse Eight",
	CEC_VENDOR_HARMAN_KARDON2: "Harman/Kardon",
	CEC_VENDOR_GOOGLE: "Google",
	CEC_VENDOR_AKAI: "Akai",
	CEC_VENDOR_OPPO: "OPPO",
	CEC_VENDOR_AOC: "AOC",
	CEC_VENDOR_AMAZON: "Amazon",
	CEC_VENDOR_PANASONIC: "Panasonic Viera Link",
	CEC_VENDOR_PHILIPS: "Philips EasyLink",
	CEC_VENDOR_DAEWOO: "Daewoo",
	CEC_VENDOR_YAMAHA: "Yamaha",
	CEC_VENDOR_GRUNDIG: "Grundig",
	CEC_VENDOR_PIONEER: "Pioneer",
	CEC_VENDOR_LG: "LG Simplink",
	CEC_VENDOR_SHARP: "Sharp Aquos Link",
	CEC_VENDOR_SONY: "Sony Bravia Sync",
	CEC_VENDOR_SONY2: "Sony Bravia Sync",
	CEC_VENDOR_BROADCOM: "Broadcom",
	CEC_VENDOR_TEUFEL: "Teufel",
	CEC_VENDOR_SHARP2: "Sharp Aquos Link",
	CEC_VENDOR_MEDIATEK: "MediaTek",
	CEC_VENDOR_VIZIO: "Vizio",
	CEC_VENDOR_BENQ: "BenQ",
	CEC_VENDOR_HARMAN_KARDON: "Harman/Kardon",
	CEC_VENDOR_ENIGMA2_STB: "Enigma2 STB",
}

CECintcmd = {
	"Active Source": "sourceactive",
	"Device Vendor ID": "vendorid",
	"Give Device Vendor ID": "vendorrequest",
	"Give Device Power Status": "powerstate",
	"Give System Audio Mode Status": "givesystemaudiostatus",
	"Image View On": "wakeup",
	"Inactive Source": "sourceinactive",
	"Menu Status Activated": "menuactive",
	"Menu Status Deactivated": "menuinactive",
	"Report Physical Address": "reportaddress",
	"Report Power Status On": "poweractive",
	"Report Power Status Standby": "powerinactive",
	"Routing Information": "routinginfo",
	"Set Stream Path": "setstreampath",
	"Set OSD Name": "osdname",
	"Set System Audio Mode Off": "deactivatesystemaudiomode",
	"Set System Audio Mode On": "activatesystemaudiomode",
	"Standby": "standby",
	"System Audio Mode Request": "setsystemaudiomode",
	"User Control Pressed Power Off": "keypoweroff",
	"User Control Pressed Power On": "keypoweron",
	"Volume Down": "volumedown",
	"Volume Mute": "volumemute",
	"Volume Up": "volumeup"
}

CECaddr = {
	0x00: "<TV>",
	0x01: "<Recording 1>",
	0x02: "<Recording 2>",
	0x03: "<Tuner 1>",
	0x04: "<Playback 1>",
	0x05: "<Audio System>",
	0x06: "<Tuner 2>",
	0x07: "<Tuner 3>",
	0x08: "<Playback 2>",
	0x09: "<Playback 3>",
	0x0A: "<Tuner 4>",
	0x0B: "<Playback 2>",
	0x0C: "<Reserved>",
	0x0D: "<Reserved>",
	0x0E: "<Specific>",
	0x0F: "<Broadcast>"
}

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
	0x8C: "<Request Device Vendor ID>",					# request vendor ID from device(TV, AV receiver, audio device)
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
	0xA5: "<Give Features>",
	0xA6: "<Report Features>",
	0xFF: "<Abort>",
	}  # noqa E123

CtrlByte0 = {		# Information only: control byte 0 status/action request by command (see cmdList)
	0x00: {
		0x00: "<Unrecognized opcode>",
		0x01: "<Not in correct mode to respond>",
		0x02: "<Cannot provide source>",
		0x03: "<Invalid operand>",
		0x04: "<Refused>"
	},
	0x08: {
		0x01: "<On>",
		0x02: "<Off>",
		0x03: "<Once>"
	},
	0x0A: {
		0x01: "<Recording currently selected source>",
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
		0x1F: "<No recording - other reason>"
	},
	0x1B: {
		0x11: "<Play>",
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
		0x1F: "<Other Status>"
	},
	0x1A: {
		0x01: "<On>",
		0x02: "<Off>",
		0x03: "<Once>"
	},
	0x41: {
		0x05: "<Play Forward Min Speed>",
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
		0x25: "<Play Still>"
	},
	0x42: {
		0x01: "<Skip Forward / Wind>",
		0x02: "<Skip Reverse / Rewind",
		0x03: "<Stop>",
		0x04: "<Eject>"
	},
	0x43: {
		0x00: "<Timer not cleared - recording>",
		0x01: "<Timer not cleared - no matching>",
		0x02: "<Timer not cleared - no info available>",
		0x80: "<Timer cleared>"
	},
	0x44: {
		0x00: "<Select>",
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
		0x7F: "<Reserved 0x7F>"
	},
	0x64: {
		0x00: "<Display for default time>",
		0x40: "<Display until cleared>",
		0x80: "<Clear previous message>",
		0xC0: "<Reserved for future use>"
	},
	0x72: {
		0x00: "<Off>",
		0x01: "<On>"
	},
	0x7E: {
		0x00: "<Off>",
		0x01: "<On>"
	},
	0x84: {
		0x00: "<TV>",
		0x01: "<Recording Device>",
		0x02: "<Reserved>",
		0x03: "<Tuner>",
		0x04: "<Playback Devive>",
		0x05: "<Audio System>",
		0x06: "<Pure CEC Switch>",
		0x07: "<Video Processor>"
	},
	0x8D: {
		0x00: "<Activate>",
		0x01: "<Deactivate>",
		0x02: "<Query>"
	},
	0x8E: {
		0x00: "<Activated>",
		0x01: "<Deactivated>"
	},
	0x90: {
		0x00: "<On>",
		0x01: "<Standby>",
		0x02: "<In transition Standby to On>",
		0x03: "<In transition On to Standby>"
	},
	0x9A: {
		0x00: "<Rate Control Off>",
		0x01: "<WRC Standard Rate: 100% rate>",
		0x02: "<WRC Fast Rate: Max 101% rate>",
		0x03: "<WRC Slow Rate: Min 99% rate",
		0x04: "<NRC Standard Rate: 100% rate>",
		0x05: "<NRC Fast Rate: Max 100.1% rate>",
		0x06: "<NRC Slow Rate: Min 99.9% rate"
	},
	0x9E: {
		0x00: "<1.1>",
		0x01: "<1.2>",
		0x02: "<1.2a>",
		0x03: "<1.3>",
		0x04: "<1.3a>",
		0x05: "<1.4>",
		0x06: "<2.0>"
	},
}  # noqa E123


def getPhysicalAddress():
	physicaladdress = eHdmiCEC.getInstance().getPhysicalAddress()
	hexstring = "%04x" % physicaladdress
	return hexstring[0] + "." + hexstring[1] + "." + hexstring[2] + "." + hexstring[3]


def setFixedPhysicalAddress(address):
	hexstring = address[0] + address[2] + address[4] + address[6]
	eHdmiCEC.getInstance().setFixedPhysicalAddress(int(float.fromhex(hexstring)))


def printX(msg):
	if config.hdmicec.debug.value == "1":
		print(msg)


class HdmiCec:
	instance = None

	def __init__(self):
		if config.hdmicec.enabled.value:
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
			self.devices = {}
			self.tv_vendor = CEC_VENDOR_UNKNOWN
			self.audio_system_present = False
			self.system_audio_mode = False
			self.volumeforward72 = False
			self.volumeforward72cnt = 0
			self.local_vendor_id = CEC_VENDOR_ENIGMA2_STB
			self.tv_powerstate = "unknown"
			self.cmd87 = False
			self.enableCec()
#		else:
#			printX("[HdmiCEC][init] no set physical address ")
#			setFixedPhysicalAddress("0.0.0.0")			# no fixed physical address send 0 to eHdmiCec C++ driver

	def enableCec(self):
		eHdmiCEC.getInstance().setEnabled(config.hdmicec.enabled.value)
		printX(f"[HdmiCEC][init]3 physical address:{getPhysicalAddress()}")
		if not config.hdmicec.change_physaddress.value:
			config.hdmicec.fixed_physical_address.value = getPhysicalAddress()
		countDots = config.hdmicec.fixed_physical_address.value.count(".")
		# printX(f"[HdmiCEC][init]2countDots:{countDots}")
		if countDots == 3 and config.hdmicec.fixed_physical_address.value[1:3] != ".0" and config.hdmicec.change_physaddress.value:
			try:
				printX(f"[HdmiCEC][init]phsyical address changed by setup value:{config.hdmicec.fixed_physical_address.value}")
				setFixedPhysicalAddress(config.hdmicec.fixed_physical_address.value)
			except:
				setFixedPhysicalAddress("0.0.0.0")
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
			# if config.hdmicec.handle_deepstandby_events.value and not getFPWasTimerWakeup():
			if not getFPWasTimerWakeup():
				self.onLeaveStandby()

	def dataByte(self, data, index):
		item = data[index]
		return item if isinstance(item, int) else ord(item)

	def dataBytes(self, data, length):
		return [self.dataByte(data, idx) for idx in range(min(length, len(data)))]

	def payloadBytes(self, data):
		if isinstance(data, bytes):
			return data
		if isinstance(data, bytearray):
			return bytes(data)
		return data.encode("ISO-8859-1")

	def sendCecMessage(self, address, cmd, data):
		payload = self.payloadBytes(data)
		eHdmiCEC.getInstance().sendMessageBytes(address, cmd, payload.hex().upper())

	def vendorName(self, vendor):
		printX(f"[HdmiCec][vendorname] vendor:{vendor}")
		if vendor is not None:
			return CEC_VENDOR.get(vendor, f"0x{vendor:06X}")
		else:
			return ""

	def updateDevice(self, address, vendor=None, physical=None, device_type=None, name=None):
		if address < 0 or address > 0x0F:
			return
		device = self.devices.setdefault(address, {})
		if vendor is not None and device.get("vendor") != vendor:
			device["vendor"] = vendor
			if address == 0:
				self.tv_vendor = vendor
			elif address == 5:
				self.audio_system_present = True
			printX(f"[HdmiCec] device {address:02X} vendor: {self.vendorName(vendor)} (0x{vendor:06X})")
		if physical is not None:
			device["physical"] = physical
		if device_type is not None:
			device["type"] = device_type
			if address == 5 or device_type == 5:
				self.audio_system_present = True
				# self.volumeForwardingDestination = 5
		if name:
			device["name"] = name
		if vendor is not None:
			printX(f"[HdmiCec] device {address:02X} vendor: {self.vendorName(vendor)} (0x{vendor:06X} audio_system_present:{self.audio_system_present})")

	def getDeviceVendor(self, address):
		return self.devices.get(address, {}).get("vendor", CEC_VENDOR_UNKNOWN)

	def getAdvertisedVendor(self, destination):
		return self.local_vendor_id

	def vendorPayload(self, vendor):
		return pack("BBB", (vendor >> 16) & 0xFF, (vendor >> 8) & 0xFF, vendor & 0xFF)

	def deviceTypeFeature(self):
		return {
			0: 0x80,
			1: 0x40,
			3: 0x20,
			4: 0x10,
			5: 0x08,
			6: 0x04,
			7: 0x04,
		}.get(eHdmiCEC.getInstance().getDeviceType(), 0x40)

	def sendRawMessage(self, address, cmd, payload):
		data = bytes(payload)
		if config.misc.DeepStandby.value:
			if config.hdmicec.debug.value:
				self.debugTx(address, cmd, data)
			self.sendCecMessage(address, cmd, data)
		else:
			self.queue.append((address, cmd, data))
			if not self.wait.isActive():
				self.wait.start(int(config.hdmicec.minimum_send_interval.value), True)

	def sendVolumeKey(self, key):
		address = 5 if self.audio_system_present or self.system_audio_mode else 0
		self.volumeForwardingDestination = address
		self.sendRawMessage(address, 0x44, (key,))
		self.sendRawMessage(address, 0x45, ())

# 0x89: Vendor Command -> Vendor Specific Data
# 0xA0: Vendor Command with ID

	def handleVendorCommand(self, address, cmd, data, length):
		printX(f"[HdmiCec][handleVendorCommand] address:{address} cmd:{cmd} data:{data}")
		payload = self.dataBytes(data, length)
		vendor = self.getDeviceVendor(address)
		params = payload
		if cmd == 0xA0:
			if len(payload) < 3:
				return False
			vendor = (payload[0] << 16) | (payload[1] << 8) | payload[2]
			params = payload[3:]
			self.updateDevice(address, vendor=vendor)

		if vendor == CEC_VENDOR_LG and address == 0 and cmd in (0x89, 0xA0):
			return self.handleLGVendorCommand(address, cmd, params)
		if vendor == CEC_VENDOR_PANASONIC and address == 0:
			return self.handlePanasonicVendorCommand(address, cmd, params)
		if vendor == CEC_VENDOR_SAMSUNG and cmd == 0xA0 and len(params) >= 1 and params[0] == 0x23:
			self.sendRawMessage(address, 0xA0, (0x00, 0x00, 0xF0, 0x24, 0x00, 0x80))
			printX("[HdmiCec] Samsung vendor handshake acknowledged")
			return True
		return False

	def handleLGVendorCommand(self, address, cmd, params):
		printX(f"[HdmiCec] handleLGVendorCommand address:{address} cmd:{cmd} params:{params}")
		if not params:
			return False
		if params[0] == 0x01:
			self.sendRawMessage(address, 0x89, (0x02, 0x05))
			printX("[HdmiCec] LG Simplink init acknowledged")
			return True
		if params[0] == 0x03:
			printX("[HdmiCec] LG Simplink power-on request")
			if config.hdmicec.handle_tv_wakeup.value != "disabled":
				self.wakeup()
			self.sendMessage(address, "poweractive" if not Screens.Standby.inStandby else "powerinactive")
			if not Screens.Standby.inStandby and config.hdmicec.report_active_source.value:
				self.sendMessage(0, "sourceactive")
			return True
		if params[0] == 0x04:
			self.sendRawMessage(address, 0x89, (0x05, eHdmiCEC.getInstance().getDeviceType()))
			if self.activesource:
				self.sendMessage(address, "poweractive")
			printX("[HdmiCec] LG Simplink connect request acknowledged")
			return True
		if params[0] in (0x0B, 0xA0):
			self.sendMessage(address, "powerinactive" if Screens.Standby.inStandby else "poweractive")
			return True
		return False

	def handlePanasonicVendorCommand(self, address, cmd, params):
		printX(f"[HdmiCec] handlePanasonicVendorCommand address:{address} cmd:{cmd} params:{params}")
		if cmd == 0x89 and len(params) >= 2 and params[0] == 0x10 and params[1] == 0x01:
			self.sendRawMessage(address, 0x89, (0x10, 0x02, 0xFF, 0xFF, 0x00, 0x05, 0x05, 0x45, 0x55, 0x5C, 0x58, 0x32))
			printX("[HdmiCec] Panasonic Viera Link capabilities sent")
			return True
		if cmd == 0xA0 and len(params) >= 2 and params[0] == 0x20:
			if params[1] == 0x00:
				self.tv_powerstate = "on"
			elif params[1] == 0x01:
				self.tv_powerstate = "standby"
				if config.hdmicec.control_tv_wakeup.value:
					self.sendWakeupMessages()
			printX(f"[HdmiCec] Panasonic Viera self.tv_powerstate:{self.tv_powerstate}")
			return True
		return False

	# 	config.hdmicec.handle_tv_standby - if set inititates receiver Standby request
	# 	config.hdmicec.handle_tv_wakeup  - if set handle receiver wakeup from TV depending on config.hdmicec.tv_wakeup_detection setting

	def messageReceived(self, message):  # messgeReceived is called by HdmiCEC driver following input request on hdmi
		if config.hdmicec.enabled.value:
			cmd = message.getCommand()  # transmitted command in decimal
			cmd2 = f"{cmd:02X}"  # transmitted command in hexadecimal
			CECcmd = cmdList.get(cmd, "<Polling Message>")  # get Text of request from CEC command
			data, length = self.getMessageData(message)
			ctrl0 = message.getControl0()
			ctrl1 = message.getControl1()
			ctrl2 = message.getControl2()
			msgaddress = message.getAddress()  # 0 = TV, 5 = receiver 15 = broadcast
			inStandby = True if Screens.Standby.inStandby else False
			tvwakeupDetection = config.hdmicec.tv_wakeup_detection.value  # TV wakeup action depends on this setting
			if cmd == 0x87 and self.cmd87:  # some TV's throw this continuously
				return
			if CECcmd != "<Polling Message>":
				printX(f"[HdmiCEC][messageReceived0]: msgaddress={msgaddress}  CECcmd={CECcmd}, cmddec= {cmd} cmdhex={cmd2}, ctrl0={ctrl0}, datalength={length}")
				if config.hdmicec.debug.value in ["2", "3", "4"]:
					self.debugRx(length, cmd, ctrl0)
				if msgaddress > 15:  # workaround for wrong address from driver (e.g. hd51, message comes from tv -> address is only sometimes 0, dm920, same tv -> address is always 0)
					printX("[HdmiCEC][messageReceived1a]: msgaddress > 15 reset to 0")
					msgaddress = 0
				match cmd:
					case 0x00:
						if length == 0:  # only polling message ( it's same as ping )
							printX("[HdmiCEC][messageReceived1b]: received polling message")
						else:
							if ctrl0 == 68:  # feature abort
								printX(f"[HdmiCEC][messageReceived2]: volume forwarding not supported by device {msgaddress:02x}")
								self.volumeForwardingEnabled = False
					case 0x1a:  # give deck status
						self.sendMessage(msgaddress, "deckstatus")
					case 0x36:
						if config.hdmicec.handle_tv_standby.value:  # handle standby request from the tv
							self.handlingStandbyFromTV = True  # avoid echoing the "System Standby" command back to the tv
							self.standby()  # handle standby
							self.handlingStandbyFromTV = False  # after handling the standby command, we are free to send "standby" ourselves again
					case 0x46:  # request name
						self.sendMessage(msgaddress, "osdname")
					case 0x47 if length:  # set osd name
						self.updateDevice(msgaddress, name=data[:length].strip("\x00"))
					case 0x72 | 0x7e:  # system audio mode status 114 or 126
						self.volumeforward72 = True
						if ctrl0 == 1:
							self.system_audio_mode = 1
							self.audio_system_present = msgaddress == 5 or self.audio_system_present
							self.volumeForwardingDestination = 5  # on: send volume keys to receiver/sound system
						else:
							self.volumeForwardingDestination = 0  # off: send volume keys to tv
						printX(f"[HdmiCEC][messageReceived4]: volume forwarding={self.volumeForwardingDestination}, msgaddress={msgaddress}")
						if config.hdmicec.volume_forwarding.value:
							printX(f"[HdmiCEC][messageReceived5]: volume forwarding to device {self.volumeForwardingDestination:02x} enabled")
							self.volumeForwardingEnabled = True
					case 0x83:  # request address
						self.sendMessage(msgaddress, "reportaddress")
					case 0x84 if length >= 3:  # report physical address
						physical = (ctrl0 << 8) | ctrl1
						self.updateDevice(msgaddress, physical=physical, device_type=ctrl2)
						if msgaddress == 5 or ctrl2 == 5:
							self.audio_system_present = True
							if config.hdmicec.volume_forwarding.value:
								self.sendMessage(5, "givesystemaudiostatus")
						if self.getDeviceVendor(msgaddress) == CEC_VENDOR_UNKNOWN:
							self.sendMessage(msgaddress, "vendorrequest")
					case 0x85:  # request active source
						if not inStandby:
							if config.hdmicec.report_active_source.value:
								self.sendMessage(msgaddress, "sourceactive")
					case 0x86 | 0x82:  # set streaming path, active source changed
						physicaladdress = ctrl0 * 256 + ctrl1  # request streaming path
						ouraddress = eHdmiCEC.getInstance().getPhysicalAddress()
						printX(f"[HdmiCEC][messageReceived6]:cmd 134 physical address={physicaladdress} ouraddress={ouraddress}")
						if physicaladdress == ouraddress:
							if not inStandby:
								if config.hdmicec.report_active_source.value:
									self.sendMessage(msgaddress, "sourceactive")
					case 0x87 if length >= 3:  # device vendor id
						self.cmd87 = True
						printX(f"[HdmiCEC][messageReceived]Reporting Device Vendor ctrl0:{ctrl0:02X} ctrl1:{ctrl1:02X} ctrl2:{ctrl2:02X}")
						vendor = (ctrl0 << 16) | (ctrl1 << 8) | ctrl2
						self.updateDevice(msgaddress, vendor=vendor)
					case 0x89 | 0x8A | 0x8B | 0xA0:
						self.handleVendorCommand(msgaddress, cmd, data, length)
					case 0x8c:  # request vendor id
						self.sendMessage(msgaddress, "vendorid")
					case 0x8d:  # menu request
						if ctrl0 == 1:  # query
							if inStandby:
								self.sendMessage(msgaddress, "menuinactive")
							else:
								self.sendMessage(msgaddress, "menuactive")
					case 0x8f:  # request power status
						if inStandby:
							self.sendMessage(msgaddress, "powerinactive")
						else:
							self.sendMessage(msgaddress, "poweractive")
					case 0x90:  # report power state from the tv
						if ctrl0 == 0:
							self.tv_powerstate = "on"
						elif ctrl0 == 1:
							self.tv_powerstate = "standby"
						elif ctrl0 == 2:
							self.tv_powerstate = "get_on"
						elif ctrl0 == 3:
							self.tv_powerstate = "get_standby"
						if config.hdmicec.control_tv_wakeup.value and self.tv_powerstate == "standby":
							self.sendWakeupMessages()
						if config.hdmicec.next_boxes_detect.value:
							self.useStandby = False
						printX(f"[HDMI-CEC][messageReceived7] powered box found self.tv_powerstate:{self.tv_powerstate}")
					case 0x91:  # get menu language
						self.sendMessage(msgaddress, "menulanguage")
					case 0x9F:  # request get CEC version
						self.sendMessage(msgaddress, "cecversion")
					case 0xa5:  # give features
						self.sendMessage(msgaddress, "reportfeatures")

				if inStandby and config.hdmicec.handle_tv_wakeup.value:
					printX(f"[HDMI-CEC][messageReceived10] cmd:{cmd:02X} cmd2:{cmd2} ctrl0:{ctrl0}")
					if msgaddress == 0 and cmd == 0x44 and ctrl0 in (64, 109):  # handle wakeup from tv hdmi-cec menu (e.g. panasonic tv apps, viera link)
						self.wakeup()
					elif ((cmd == 0x04 and tvwakeupDetection == "wakeup") or
						(cmd != 0x36 and tvwakeupDetection == "activity") or
						(cmd == 0x46 and tvwakeupDetection == "osdnamerequest") or
						(cmd == 0x83 and tvwakeupDetection == "requestphysicaladdress") or
						(cmd == 0x85 and tvwakeupDetection == "sourcerequest") or
						(cmd == 0x8C and tvwakeupDetection == "requestvendor")):
						self.wakeup()
					elif ((cmd == 0x80 and tvwakeupDetection == "routingrequest") or (cmd == 0x86 and tvwakeupDetection == "streamrequest")):
						physicaladdress = ctrl0 * 256 + ctrl1
						ouraddress = eHdmiCEC.getInstance().getPhysicalAddress()
						printX(f"[HdmiCEC][messageReceived8]:cmd 128 physical address={physicaladdress} ouraddress={ouraddress}")
						if physicaladdress == ouraddress:
							self.wakeup()
					elif cmd == 0x84 and tvwakeupDetection == "tvreportphysicaladdress":
						if (ctrl0 * 256 + ctrl1) == 0 and ctrl2 == 0:
							self.wakeup()
			else:
				return

	def sendMessage(self, msgaddress, message):
		cmd = 0
		data = b""
		match message:
			case "wakeup":
				if config.hdmicec.tv_wakeup_command.value == "textview":
					cmd = 0x0d
				else:
					cmd = 0x04
			case "deckstatus":
				cmd = 0x1b
				data = pack("B", 0x20 if self.tv_vendor == CEC_VENDOR_LG else 0x1f)
			case "menulanguage":
				cmd = 0x32
				data = b"eng"
			case "standby":
				cecTimerWakeup = False
				if exists("/tmp/was_cectimer_wakeup",):
					with open("/tmp/was_cectimer_wakeup", "r") as f:
						file = f.read()
						cecTimerWakeup = int(file) and True or False
					remove("/tmp/was_cectimer_wakeup")
				printX(f"[HdmiCec][sendMessage]: send message={message}  cecTimerWakeup={cecTimerWakeup}")
				if not cecTimerWakeup:
					cmd = 0x36
			case "keypoweroff":
				cmd = 0x44  # 68
				data = pack("B", 0x6c)
			case "keypoweron":
				cmd = 0x44  # 68
				data = pack("B", 0x6d)
			case "osdname":
				cmd = 0x47
				data = getCecOsdName().encode(encoding='utf-8', errors='strict')
			case "setsystemaudiomode":
				cmd = 0x70  # 112
				data = self.packDevAddr()
			case "deactivatesystemaudiomode":
				cmd = 0x72
				data = pack("B", 0x00)
			case "audiostatus":
				cmd = 0x7a
				data = pack("B", 0x00)
			case "givesystemaudiostatus":
				cmd = 0x7d
			case "routinginfo":
				msgaddress = 0x0f  # use broadcast address
				cmd = 0x81
				data = self.packDevAddr()
			case "sourceactive":
				msgaddress = 0x0f  # use broadcast for active source command
				cmd = 0x82  # 130
				data = self.packDevAddr()
			case "reportaddress":
				msgaddress = 0x0f  # use broadcast address
				cmd = 0x84  # 132
				data = self.packDevAddr(True)
			case  "requestactivesource":
				cmd = 0x85
				msgaddress = 0x0f  # use broadcast address
			case "setstreampath":
				msgaddress = 0x0f  # use broadcast address
				cmd = 0x86
				physicaladdress = eHdmiCEC.getInstance().getPhysicalAddress()
				data = pack("BB", int(physicaladdress / 256), int(physicaladdress % 256))
			case "vendorid":
				cmd = 0x87
				data = self.vendorPayload(self.getAdvertisedVendor(msgaddress))
			case "vendorrequest":
				cmd = 0x8c
			case  "givesystemaudiostatus":
				cmd = 0x7d
			case "menuactive":
				cmd = 0x8e  # 142
				data = pack("B", 0x00)
			case  "getpowerstatus":
				self.useStandby = True
				cmd = 0x8f
				msgaddress = 0x0f  # use broadcast msgaddress => boxes will send info
			case "poweractive":
				cmd = 0x90  # 144
				data = pack("B", 0x00)
			case  "sourceinactive":
				cmd = 0x9d  # 157
				data = self.packDevAddr()
			case "cecversion":
				cmd = 0x9E  # 158
				data = pack("B", 0x04)  # v1.3a
			case "reportfeatures":
				cmd = 0xa6
				data = pack("BBBB", 0x06, self.deviceTypeFeature(), 0x00, 0x00)
		if cmd != 0:
			CECcmd = cmdList.get(cmd, "<Polling Message>")
			printX(f"[HdmiCEC][sendMessage3]: CECcmd={CECcmd} cmd={cmd:X}, msgaddress={msgaddress} data={data}")
			if config.hdmicec.minimum_send_interval.value != "0":
				self.queue.append((msgaddress, cmd, data))
				if not self.wait.isActive():
					self.wait.start(int(config.hdmicec.minimum_send_interval.value), True)
			else:
				self.sendCecMessage(msgaddress, cmd, data)
				# eHdmiCEC.getInstance().sendMessage(msgaddress, cmd, data, len(data))
			if config.hdmicec.debug.value in ["2", "4"]:
				self.debugTx(msgaddress, cmd, data)
			if not self.volumeforward72 and config.hdmicec.enabled.value and config.hdmicec.volume_forwarding.value:
				if self.volumeforward72cnt < 5:
					self.volumeforward72cnt += 1
					self.sendMessage(0x05, "givesystemaudiostatus")
					self.sendMessage(0x00, "givesystemaudiostatus")

	def sendMsgQ(self):
		if len(self.queue):
			(msgaddress, cmd, data) = self.queue.pop(0)
			CECcmd = cmdList.get(cmd, "<Polling Message>")  # noqa: F841
			self.sendCecMessage(msgaddress, cmd, data)
			self.wait.start(int(config.hdmicec.minimum_send_interval.value), True)

	def packDevAddr(self, devicetypeSend=False):
		physicaladdress = eHdmiCEC.getInstance().getPhysicalAddress()
		if devicetypeSend:
			devicetype = eHdmiCEC.getInstance().getDeviceType()
			return pack("BBB", int(physicaladdress // 256), int(physicaladdress % 256), devicetype)
		else:
			return pack("BB", int(physicaladdress // 256), int(physicaladdress % 256))

	def secondBoxActive(self):
		self.sendMessage(0, "getpowerstatus")

	def configVolumeForwarding(self, configElement):
		printX(f"[HdmiCEC][configVolumeForwarding]: hdmicec.enabled={config.hdmicec.enabled.value}, hdmicec.volume_forwarding={config.hdmicec.volume_forwarding.value}")
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
		printX(f"[HdmiCEC][sendStandbyMessages]: config.hdmicec.control_tv_standby={config.hdmicec.control_tv_standby.value}, self.handlingStandbyFromTV={self.handlingStandbyFromTV}")
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
		printX(f"[HdmiCEC][sendStandbyMessages]: messages={messages}")
		if messages:
			self.sendQMessages(0, messages)

		if config.hdmicec.control_receiver_standby.value:
			self.sendMessage(5, "keypoweroff")
			self.sendMessage(5, "standby")

	def standby(self):			# Standby initiated from TV
		if not Screens.Standby.inStandby:
			Notifications.AddNotification(Screens.Standby.Standby)

	def onLeaveStandby(self):
		printX("[HDMI-CEC][onLeaveStandby] entered")
		self.sendWakeupMessages()
		if int(config.hdmicec.repeat_wakeup_timer.value):
			self.repeat.startLongTimer(int(config.hdmicec.repeat_wakeup_timer.value))

	def wakeup(self):
		printX("[HDMI-CEC][wakeup] entered")
		self.wakeup_from_tv = True
		if Screens.Standby.inStandby:
			printX("[HDMI-CEC][wakeup] powered box found send Power from wakeup")
			Screens.Standby.inStandby.Power()

	def sendWakeupMessages(self):
		printX(f"[HDMI-CEC][sendWakeupMessages] entered self.wakeup_from_tv:{self.wakeup_from_tv}")
		if config.hdmicec.enabled.value:
			messages = []
			if config.hdmicec.control_tv_wakeup.value:
				if not self.wakeup_from_tv:
					messages.append("wakeup")
			self.wakeup_from_tv = False
			if config.hdmicec.report_active_source.value:
				messages.append("sourceactive")
				messages.append("setstreampath")
				messages.append("routinginfo")
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
		KEY_VOLUP = 115
		KEY_VOLDOWN = 114
		KEY_VOLMUTE = 113
		if keyCode in (KEY_VOLMUTE, KEY_VOLDOWN, KEY_VOLUP):						# if not volume key return
			if self.volumeForwardingEnabled or config.hdmicec.force_volume_forwarding.value:
				cmd = 0
				data = b""
				if keyEvent in (0, 2):
					if keyCode == KEY_VOLMUTE:
						cmd = 0x44
						data = pack("B", 0x43)		# 0x43: "<Mute>"
					if keyCode == KEY_VOLDOWN:
						cmd = 0x44
						data = pack("B", 0x42)		# 0x42: "<Volume Down>"
					if keyCode == KEY_VOLUP:
						cmd = 0x44
						data = pack("B", 0x41)		# 0x41: "<Volume Up>"
				elif keyEvent == 1:
					cmd = 0x45					# 0x45: "<stop>"
				if cmd != 0:
					if config.hdmicec.minimum_send_interval.value != "0":
						self.queueKeyEvent.append((self.volumeForwardingDestination, cmd, data))
						if not self.waitKeyEvent.isActive():
							self.waitKeyEvent.start(int(config.hdmicec.minimum_send_interval.value), True)
					else:
						# printX(f"[HdmiCEC][keyEvent3]: forwarding dest={self.volumeForwardingDestination}, cmd={cmd:X}, data={data}")
						if not config.hdmicec.force_volume_forwarding.value:
							self.sendCecMessage(self.volumeForwardingDestination, cmd, data)
						else:
							self.sendCecMessage(0, cmd, data)
							self.sendCecMessage(5, cmd, data)

					if config.hdmicec.debug.value in ["3", "4"]:
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
			# printX(f"[HdmiCEC][sendKeyEventQ]: msgaddress={msgaddress}, cmd={cmd:X}, data={data}")
			# eHdmiCEC.getInstance().sendMessage(msgaddress, cmd, data, len(data))
			self.sendCecMessage(msgaddress, cmd, data)
			self.waitKeyEvent.start(int(config.hdmicec.minimum_send_interval.value), True)

	def getMessageData(self, message):
		length = message.getDataLength()
		return "".join(chr(message.getDataByte(i) & 0xFF) for i in range(length)), length

	def debugTx(self, msgaddress, cmd, data):
		txt = self.now(True) + self.opCode(cmd, True) + " " + f"{cmd:02X}" + " "
		tmp = ""
		if len(data):
			if cmd in [0x32, 0x47]:  # set Menu Language/OSD Name
				for info in data:
					tmp += f"{info}"
			else:
				for bytes in data:
					tmp += f"{ord(bytes):02X}" + " "
		tmp += 48 * " "
		self.fdebug(txt + tmp[:48] + f"[0x{msgaddress:02X}]")

	def debugRx(self, length, cmd, ctrl0):
		txt = self.now()
		if cmd == 0 and length == 0:
			txt += "<Polling Message> -"
		else:

			if cmd == 0:
				txt += "<Feature Abort>" + 13 * " " + "<  " + f"{cmd:02X}" + " "
			else:
				txt += self.opCode(cmd) + f" {cmd:02X} "
			if cmd == 0x9e and ctrl0 < len(CEC):
				txt += f"{ctrl0:02X}" + 3 * " " + f"[version: {CEC[ctrl0]}]"
			else:
				txt += f"{ctrl0:02X}"
		txt += "\n"
		self.fdebug(txt)

	def opCode(self, cmd, out=False):
		send = "<"
		if out:
			send = ">"
		opCode = ""
		if cmd in cmdList:
			opCode += f"{cmdList[cmd]}"
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
			logpath = join(logpath, "hdmicec.log")
			fp = open(logpath, "a")
			fp.write(output)
			fp.close()
