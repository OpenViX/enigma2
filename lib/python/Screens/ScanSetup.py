from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
import six

from Screens.Screen import Screen
from Screens.ServiceScan import ServiceScan
from Components.config import config, ConfigSubsection, ConfigSelection, ConfigYesNo, ConfigInteger, getConfigListEntry, ConfigSlider, ConfigEnableDisable
from Components.ActionMap import NumberActionMap, ActionMap
from Components.Sources.StaticText import StaticText
from Components.SystemInfo import SystemInfo
from Components.ConfigList import ConfigListScreen
from Components.NimManager import nimmanager, getConfigSatlist
from Components.Label import Label
from Tools.HardwareInfo import HardwareInfo
from Tools.Transponder import getChannelNumber, supportedChannels, channel2frequency
from Screens.InfoBar import InfoBar
from Screens.MessageBox import MessageBox
from enigma import eTimer, eDVBFrontendParametersSatellite, eComponentScan, eDVBFrontendParametersTerrestrial, eDVBFrontendParametersCable, eConsoleAppContainer, eDVBResourceManager, eDVBFrontendParametersATSC


def buildTerTransponder(frequency,
		inversion=2, bandwidth=7000000, fechigh=6, feclow=6,
		modulation=2, transmission=2, guard=4,
		hierarchy=4, system=0, plp_id=0):
	#print("freq", frequency, "inv", inversion, "bw", bandwidth, "fech", fechigh, "fecl", feclow, "mod", modulation, "tm", transmission, "guard", guard, "hierarchy", hierarchy, "system", system, "plp_id", plp_id)
	parm = eDVBFrontendParametersTerrestrial()
	parm.frequency = frequency
	parm.inversion = inversion
	parm.bandwidth = bandwidth
	parm.code_rate_HP = fechigh
	parm.code_rate_LP = feclow
	parm.modulation = modulation
	parm.transmission_mode = transmission
	parm.guard_interval = guard
	parm.hierarchy = hierarchy
	parm.system = system
	parm.plp_id = plp_id
	return parm


def getInitialTransponderList(tlist, pos, feid=None):
	list = nimmanager.getTransponders(pos, feid)
	for x in list:
		if x[0] == 0: #SAT
			parm = eDVBFrontendParametersSatellite()
			parm.frequency = x[1]
			parm.symbol_rate = x[2]
			parm.polarisation = x[3]
			parm.fec = x[4]
			parm.inversion = x[7]
			parm.orbital_position = pos
			parm.system = x[5]
			parm.modulation = x[6]
			parm.rolloff = x[8]
			parm.pilot = x[9]
			parm.is_id = x[10]
			parm.pls_mode = x[11]
			parm.pls_code = x[12]
			parm.t2mi_plp_id = x[13]
			parm.t2mi_pid = x[14]
			tlist.append(parm)


def getInitialCableTransponderList(tlist, nim):
	list = nimmanager.getTranspondersCable(nim)
	for x in list:
		if x[0] == 1: #CABLE
			parm = eDVBFrontendParametersCable()
			parm.frequency = x[1]
			parm.symbol_rate = x[2]
			parm.modulation = x[3]
			parm.fec_inner = x[4]
			parm.inversion = x[5]
			parm.system = x[6]
			tlist.append(parm)


def getInitialTerrestrialTransponderList(tlist, region, tsystem=eDVBFrontendParametersTerrestrial.System_DVB_T_T2):
	list = nimmanager.getTranspondersTerrestrial(region)
	for x in list:
		if x[0] == 2: #TERRESTRIAL
			if tsystem == eDVBFrontendParametersTerrestrial.System_DVB_T_T2:
				parm = buildTerTransponder(x[1], x[9], x[2], x[4], x[5], x[3], x[7], x[6], x[8], x[10], x[11])
			elif x[10] == eDVBFrontendParametersTerrestrial.System_DVB_T_T2 or x[10] == tsystem:
				parm = buildTerTransponder(x[1], x[9], x[2], x[4], x[5], x[3], x[7], x[6], x[8], tsystem, x[11])
			else:
				continue
			tlist.append(parm)


def getInitialATSCTransponderList(tlist, nim):
	list = nimmanager.getTranspondersATSC(nim)
	for x in list:
		if x[0] == 3: #ATSC
			parm = eDVBFrontendParametersATSC()
			parm.frequency = x[1]
			parm.modulation = x[2]
			parm.inversion = x[3]
			parm.system = x[4]
			tlist.append(parm)


cable_bands = {
	"DVBC_BAND_EU_VHF_I": 1 << 0,
	"DVBC_BAND_EU_MID": 1 << 1,
	"DVBC_BAND_EU_VHF_III": 1 << 2,
	"DVBC_BAND_EU_SUPER": 1 << 3,
	"DVBC_BAND_EU_HYPER": 1 << 4,
	"DVBC_BAND_EU_UHF_IV": 1 << 5,
	"DVBC_BAND_EU_UHF_V": 1 << 6,
	"DVBC_BAND_US_LO": 1 << 7,
	"DVBC_BAND_US_MID": 1 << 8,
	"DVBC_BAND_US_HI": 1 << 9,
	"DVBC_BAND_US_SUPER": 1 << 10,
	"DVBC_BAND_US_HYPER": 1 << 11,
}

cable_autoscan_nimtype = {
'SSH108': 'ssh108',
'TT3L10': 'tt3l10',
'TURBO': 'vuplus_turbo_c',
'TURBO2': 'vuplus_turbo2_c',
'TT2L08': 'tt2l08',
'BCM3148': 'bcm3148', #BCM3158/BCM3148 use the same bcm3148 utility
'BCM3158': 'bcm3148'
}

terrestrial_autoscan_nimtype = {
'SSH108': 'ssh108_t2_scan',
'TT3L10': 'tt3l10_t2_scan',
'TURBO': 'vuplus_turbo_t',
'TURBO2': 'vuplus_turbo2_t',
'TT2L08': 'tt2l08_t2_scan',
'BCM3466': 'bcm3466'
}

dual_tuner_list = ('TT3L10', 'BCM3466')
vtuner_need_idx_list = ('TURBO2',)


def GetDeviceId(filter, nim_idx):
	socket_id = device_id = 0
	for nim in nimmanager.nim_slots:
		try:
			name_token = nim.description.split(' ')[-1][4:-1]
		except:
			name_token = ""
		if name_token == filter:
			if socket_id == nim_idx:
				break
			if device_id:
				device_id = 0
			else:
				device_id = 1
		socket_id += 1
	return device_id


def getVtunerId(filter, nim_idx):
	idx_count = 1
	for slot in nimmanager.nim_slots:
		if filter in slot.description:
			if slot.slot == nim_idx:
				return "--idx " + str(idx_count)
			else:
				idx_count += 1
	return ""


class CableTransponderSearchSupport:
	def tryGetRawFrontend(self, feid):
		res_mgr = eDVBResourceManager.getInstance()
		if res_mgr:
			raw_channel = res_mgr.allocateRawChannel(self.feid)
			if raw_channel:
				frontend = raw_channel.getFrontend()
				if frontend:
					frontend.closeFrontend() # immediate close...
					del frontend
					del raw_channel
					return True
		return False

	def cableTransponderSearchSessionClosed(self, *val):
		print("[ScanSetup] cableTransponderSearchSessionClosed, val", val)
		self.cable_search_container.appClosed.remove(self.cableTransponderSearchClosed)
		self.cable_search_container.dataAvail.remove(self.getCableTransponderData)
		if val and len(val):
			if val[0]:
				self.setCableTransponderSearchResult(self.__tlist)
			else:
				self.cable_search_container.sendCtrlC()
				self.setCableTransponderSearchResult(None)
		self.cable_search_container = None
		self.cable_search_session = None
		self.__tlist = None
		self.cableTransponderSearchFinished()

	def cableTransponderSearchClosed(self, retval):
		print("[ScanSetup] cableTransponderSearch finished", retval)
		self.cable_search_session.close(True)

	def getCableTransponderData(self, str):
		str = six.ensure_str(str)
		print("[getCableTransponderData] ", str)
		#prepend any remaining data from the previous call
		str = self.remainingdata + str
		lines = str.split('\n')
		#'str' should end with '\n', so when splitting, the last line should be empty. If this is not the case, we received an incomplete line
		if len(lines[-1]):
			#remember this data for next time
			self.remainingdata = lines[-1]
			lines = lines[0:-1]
		else:
			self.remainingdata = ""

		for line in lines:
			data = line.split()
			if len(data) > 3:
				if data[0] == 'OK' and data[4] != 'NOT_IMPLEMENTED':
					parm = eDVBFrontendParametersCable()
					qam = {"QAM16": parm.Modulation_QAM16,
						"QAM32": parm.Modulation_QAM32,
						"QAM64": parm.Modulation_QAM64,
						"QAM128": parm.Modulation_QAM128,
						"QAM256": parm.Modulation_QAM256}
					inv = {"INVERSION_OFF": parm.Inversion_Off,
						"INVERSION_ON": parm.Inversion_On,
						"INVERSION_AUTO": parm.Inversion_Unknown}
					fec = {"FEC_AUTO": parm.FEC_Auto,
						"FEC_1_2": parm.FEC_1_2,
						"FEC_2_3": parm.FEC_2_3,
						"FEC_3_4": parm.FEC_3_4,
						"FEC_3_5": parm.FEC_3_5,
						"FEC_4_5": parm.FEC_4_5,
						"FEC_5_6": parm.FEC_5_6,
						"FEC_6_7": parm.FEC_6_7,
						"FEC_7_8": parm.FEC_7_8,
						"FEC_8_9": parm.FEC_8_9,
						"FEC_9_10": parm.FEC_9_10,
						"FEC_NONE": parm.FEC_None}
					parm.frequency = int(data[1])
					parm.symbol_rate = int(data[2])
					parm.fec_inner = fec[data[3]]
					parm.modulation = qam[data[4]]
					parm.inversion = inv[data[5]]
					self.__tlist.append(parm)
				tmpstr = _("Try to find used transponders in cable network.. please wait...")
				tmpstr += "\n\n"
				tmpstr += data[1].isdigit() and "%s MHz " % (int(data[1]) // 1000.) or data[1]
				tmpstr += data[0]
				self.cable_search_session["text"].setText(tmpstr)

	def startCableTransponderSearch(self, nim_idx):
		def GetCommand(nim_idx):
			try:
				device_id = ""
				nim_name = nimmanager.getNimName(nim_idx).strip(':VTUNER').split(' ')[-1][4:-1]
				if nim_name == "TT3L10":
					try:
						device_id = "--device=%s" % GetDeviceId(nim_name, nim_idx)
					except Exception as err:
						device_id = "--device=0"
						print("[startCableTransponderSearch] GetCommand ->", err)
				elif nim_name in vtuner_need_idx_list:
					device_id = getVtunerId(nim_name, nim_idx)
				return "%s %s" % (cable_autoscan_nimtype[nim_name], device_id)
			except Exception as err:
				print("[startCableTransponderSearch] GetCommand ->", err)
			return "tda1002x"

		if not self.tryGetRawFrontend(nim_idx):
			self.session.nav.stopService()
			if not self.tryGetRawFrontend(nim_idx):
				if self.session.pipshown:
					self.session.infobar.showPiP()
				if not self.tryGetRawFrontend(nim_idx):
					self.cableTransponderSearchFinished()
					return
		self.__tlist = []
		self.remainingdata = ""
		self.cable_search_container = eConsoleAppContainer()
		self.cable_search_container.appClosed.append(self.cableTransponderSearchClosed)
		self.cable_search_container.dataAvail.append(self.getCableTransponderData)
		cableConfig = config.Nims[nim_idx].cable
		tunername = nimmanager.getNimName(nim_idx)
		try:
			bus = nimmanager.getI2CDevice(nim_idx)
			if bus is None:
				print("[ScanSetup] ERROR: could not get I2C device for nim", nim_idx, "for cable transponder search")
				bus = 2
		except:
			# older API
			if nim_idx < 2:
				if HardwareInfo().get_device_name() == "dm500hd":
					bus = 2
				else:
					bus = nim_idx
			else:
				if nim_idx == 2:
					bus = 2 # DM8000 first nim is /dev/i2c/2
				else:
					bus = 4 # DM8000 second num is /dev/i2c/4

		if tunername == "CXD1981":
			bin_name = "CXD1981"
			cmd = "cxd1978 --init --scan --verbose --wakeup --inv 2 --bus %d" % bus
		elif tunername == "ATBM781x":
			bin_name = "ATBM781x"
			cmd = "atbm781x --init --scan --verbose --wakeup --inv 2 --bus %d" % bus
		elif tunername.startswith("Sundtek"):
			bin_name = "mediaclient"
			cmd = "/opt/bin/mediaclient --blindscan %d" % nim_idx
		else:
			bin_name = GetCommand(nim_idx)
			cmd = "%(BIN_NAME)s --init --scan --verbose --wakeup --inv 2 --bus %(BUS)d" % {'BIN_NAME': bin_name, 'BUS': bus}

		if cableConfig.scan_type.value == "bands":
			cmd += " --scan-bands "
			bands = 0
			if cableConfig.scan_band_EU_VHF_I.value:
				bands |= cable_bands["DVBC_BAND_EU_VHF_I"]
			if cableConfig.scan_band_EU_MID.value:
				bands |= cable_bands["DVBC_BAND_EU_MID"]
			if cableConfig.scan_band_EU_VHF_III.value:
				bands |= cable_bands["DVBC_BAND_EU_VHF_III"]
			if cableConfig.scan_band_EU_UHF_IV.value:
				bands |= cable_bands["DVBC_BAND_EU_UHF_IV"]
			if cableConfig.scan_band_EU_UHF_V.value:
				bands |= cable_bands["DVBC_BAND_EU_UHF_V"]
			if cableConfig.scan_band_EU_SUPER.value:
				bands |= cable_bands["DVBC_BAND_EU_SUPER"]
			if cableConfig.scan_band_EU_HYPER.value:
				bands |= cable_bands["DVBC_BAND_EU_HYPER"]
			if cableConfig.scan_band_US_LOW.value:
				bands |= cable_bands["DVBC_BAND_US_LO"]
			if cableConfig.scan_band_US_MID.value:
				bands |= cable_bands["DVBC_BAND_US_MID"]
			if cableConfig.scan_band_US_HIGH.value:
				bands |= cable_bands["DVBC_BAND_US_HI"]
			if cableConfig.scan_band_US_SUPER.value:
				bands |= cable_bands["DVBC_BAND_US_SUPER"]
			if cableConfig.scan_band_US_HYPER.value:
				bands |= cable_bands["DVBC_BAND_US_HYPER"]
			cmd += str(bands)
		else:
			cmd += " --scan-stepsize "
			cmd += str(cableConfig.scan_frequency_steps.value)
		if cableConfig.scan_mod_qam16.value:
			cmd += " --mod 16"
		if cableConfig.scan_mod_qam32.value:
			cmd += " --mod 32"
		if cableConfig.scan_mod_qam64.value:
			cmd += " --mod 64"
		if cableConfig.scan_mod_qam128.value:
			cmd += " --mod 128"
		if cableConfig.scan_mod_qam256.value:
			cmd += " --mod 256"
		if cableConfig.scan_sr_6900.value:
			cmd += " --sr 6900000"
		if cableConfig.scan_sr_6875.value:
			cmd += " --sr 6875000"
		if cableConfig.scan_sr_ext1.value > 450:
			cmd += " --sr "
			cmd += str(cableConfig.scan_sr_ext1.value)
			cmd += "000"
		if cableConfig.scan_sr_ext2.value > 450:
			cmd += " --sr "
			cmd += str(cableConfig.scan_sr_ext2.value)
			cmd += "000"
		print(bin_name, " CMD is", cmd)

		self.cable_search_container.execute(cmd)
		tmpstr = _("Try to find used transponders in cable network.. please wait...")
		tmpstr += "\n\n..."
		self.cable_search_session = self.session.openWithCallback(self.cableTransponderSearchSessionClosed, MessageBox, tmpstr, MessageBox.TYPE_INFO)


class TerrestrialTransponderSearchSupport:
	def terrestrialTransponderSearchSessionClosed(self, *val):
		print("[ScanSetup] TerrestrialTransponderSearchSessionClosed, val", val)
		self.terrestrial_search_container.appClosed.remove(self.terrestrialTransponderSearchClosed)
		self.terrestrial_search_container.dataAvail.remove(self.getTerrestrialTransponderData)
		if val and len(val):
			if val[0]:
				self.setTerrestrialTransponderSearchResult(self.__tlist)
			else:
				self.terrestrial_search_container.sendCtrlC()
				self.setTerrestrialTransponderSearchResult(None)
		self.terrestrial_search_container = None
		self.terrestrial_search_session = None
		self.__tlist = None
		self.terrestrialTransponderSearchFinished()

	def terrestrialTransponderSearchClosed(self, retval):
		if self.terrestrial_tunerName.startswith("Sundtek"):
			self.terrestrial_search_session.close(True)
		else:
			self.setTerrestrialTransponderData()
			opt = self.terrestrialTransponderGetOpt()
			if opt is None:
				print("[ScanSetup] terrestrialTransponderSearch finished", retval)
				self.terrestrial_search_session.close(True)
			else:
				(freq, bandWidth) = opt
				self.terrestrialTransponderSearch(freq, bandWidth)

	def getTerrestrialTransponderData(self, str):
		str = six.ensure_str(str)
		print("[getTerrestrialTransponderData] ", str)
		if self.terrestrial_tunerName.startswith("Sundtek"):
			str = self.remaining_data + str
			lines = str.split('\n')
			if len(lines[-1]):
				self.remaining_data = lines[-1]
				lines = lines[0:-1]
			else:
				self.remaining_data = ""
			for line in lines:
				data = line.split()
				if len(data):
					if 'MODE' in data[0]:
						parm = eDVBFrontendParametersTerrestrial()
						parm.frequency = int(data[3])
						parm.bandwidth = self.terrestrialTransponderconvBandwidth_P(int(data[5]))
						parm.inversion = parm.Inversion_Unknown
						parm.code_rate_HP = parm.FEC_Auto
						parm.code_rate_LP = parm.FEC_Auto
						parm.modulation = parm.Modulation_Auto
						parm.transmission_mode = parm.TransmissionMode_Auto
						parm.guard_interval = parm.GuardInterval_Auto
						parm.hierarchy = parm.Hierarchy_Auto
						parm.system = 'DVB-T2' in data[1] and parm.System_DVB_T_T2 or parm.System_DVB_T
						parm.plp_id = 0
						self.__tlist.append(parm)
					tmpstr = _("Try to find used transponders in terrestrial network... please wait...") + "\n\n"
					if 'MODE' in line:
						tmpstr += data[3] + " kHz"
					else:
						title = _("Sundtek - hardware blind scan in progress.\nPlease wait(3-20 min) for the scan to finish.")
						if "Succeeded this device supports Hardware Blindscan" in line:
							tmpstr += title
					self.terrestrial_search_session["text"].setText(tmpstr)
		else:
			self.terrestrial_search_data += str

	def setTerrestrialTransponderData(self):
		data = self.terrestrial_search_data.split()
		if len(data):
			print("[setTerrestrialTransponderData] data : ", data)
			if data[0] == 'OK':
				# DVB-T : OK, frequency, bandwidth, system, -1
				# DVB-T2 : OK, frequency, bandwidth, system, number_of_plp, plp_id0:plp_type0
				if len(data) < 6: # DVB-T (caution: system may give an incorrect value of 2 for DVB-T multiplexes)
					if not hasattr(self, "scan_ter") or self.scan_ter.complete_system.value != eDVBFrontendParametersTerrestrial.System_DVB_T2: # do not scan if user selected DVB-T2 scan only
						parm = eDVBFrontendParametersTerrestrial()
						parm.frequency = int(data[1])
						parm.bandwidth = self.terrestrialTransponderconvBandwidth_P(int(data[2]))
						parm.inversion = parm.Inversion_Unknown
						parm.code_rate_HP = parm.FEC_Auto
						parm.code_rate_LP = parm.FEC_Auto
						parm.modulation = parm.Modulation_Auto
						parm.transmission_mode = parm.TransmissionMode_Auto
						parm.guard_interval = parm.GuardInterval_Auto
						parm.hierarchy = parm.Hierarchy_Auto
						parm.system = parm.System_DVB_T
						parm.plp_id = 0
						self.__tlist.append(parm)
				else:
					if not hasattr(self, "scan_ter") or self.scan_ter.complete_system.value != eDVBFrontendParametersTerrestrial.System_DVB_T:  # do not scan if user selected DVB-T scan only
						plp_list = data[5:]
						plp_num = int(data[4])
						if len(plp_list) > plp_num:
							plp_list = plp_list[:plp_num]
						for plp in plp_list:
							(plp_id, plp_type) = plp.split(':')
							if plp_type == '0': # common PLP:
								continue
							parm = eDVBFrontendParametersTerrestrial()
							parm.frequency = int(data[1])
							parm.bandwidth = self.terrestrialTransponderconvBandwidth_P(int(data[2]))
							parm.inversion = parm.Inversion_Unknown
							parm.code_rate_HP = parm.FEC_Auto
							parm.code_rate_LP = parm.FEC_Auto
							parm.modulation = parm.Modulation_Auto
							parm.transmission_mode = parm.TransmissionMode_Auto
							parm.guard_interval = parm.GuardInterval_Auto
							parm.hierarchy = parm.Hierarchy_Auto
							parm.system = parm.System_DVB_T2
							parm.plp_id = int(plp_id)
							self.__tlist.append(parm)
			tmpstr = _("Try to find used transponders in terrestrial network... please wait...")
			tmpstr += "\n\n"
			tmpstr += data[1][:-3]
			tmpstr += " kHz "
			tmpstr += data[0]
			self.terrestrial_search_session["text"].setText(tmpstr)

	def terrestrialTransponderInitSearchList(self, searchList, region):
		tpList = nimmanager.getTranspondersTerrestrial(region)
		for x in tpList:
			if x[0] == 2: #TERRESTRIAL
				freq = x[1] # frequency
				bandWidth = self.terrestrialTransponderConvBandwidth_I(x[2]) # bandWidth
				parm = (freq, bandWidth)
				searchList.append(parm)

	def terrestrialTransponderConvBandwidth_I(self, _bandWidth):
		bandWidth = {
			eDVBFrontendParametersTerrestrial.Bandwidth_8MHz: 8000000,
			eDVBFrontendParametersTerrestrial.Bandwidth_7MHz: 7000000,
			eDVBFrontendParametersTerrestrial.Bandwidth_6MHz: 6000000,
			eDVBFrontendParametersTerrestrial.Bandwidth_5MHz: 5000000,
			eDVBFrontendParametersTerrestrial.Bandwidth_1_712MHz: 1712000,
			eDVBFrontendParametersTerrestrial.Bandwidth_10MHz: 10000000,
		}.get(_bandWidth, 8000000)
		return bandWidth

	def terrestrialTransponderconvBandwidth_P(self, _bandWidth):
		bandWidth = {
			8000000: eDVBFrontendParametersTerrestrial.Bandwidth_8MHz,
			7000000: eDVBFrontendParametersTerrestrial.Bandwidth_7MHz,
			6000000: eDVBFrontendParametersTerrestrial.Bandwidth_6MHz,
			5000000: eDVBFrontendParametersTerrestrial.Bandwidth_5MHz,
			1712000: eDVBFrontendParametersTerrestrial.Bandwidth_1_712MHz,
			10000000: eDVBFrontendParametersTerrestrial.Bandwidth_10MHz,
		}.get(_bandWidth, eDVBFrontendParametersTerrestrial.Bandwidth_8MHz)
		return bandWidth

	def terrestrialTransponderGetOpt(self):
		if len(self.terrestrial_search_list) > 0:
			return self.terrestrial_search_list.pop(0)
		else:
			return None

	def terrestrialTransponderGetCmd(self, nim_idx):
		try:
			device_id = ""
			nim_name = nimmanager.getNimName(nim_idx).strip(':VTUNER').split(' ')[-1][4:-1]
			if nim_name in dual_tuner_list:
				try:
					device_id = "--device %s" % GetDeviceId(nim_name, nim_idx)
				except Exception as err:
					device_id = "--device 0"
					print("terrestrialTransponderGetCmd set device 0 ->", err)
			elif nim_name in vtuner_need_idx_list:
				device_id = getVtunerId(nim_name, nim_idx)
			return "%s %s" % (terrestrial_autoscan_nimtype[nim_name], device_id)
		except Exception as err:
			print("[ScanSetup] terrestrialTransponderGetCmd ->", err)
		return ""

	def startTerrestrialTransponderSearch(self, nim_idx, region):
		if not self.tryGetRawFrontend(nim_idx):
			self.session.nav.stopService()
			if not self.tryGetRawFrontend(nim_idx):
				if self.session.pipshown:
					self.session.infobar.showPiP()
				if not self.tryGetRawFrontend(nim_idx):
					self.terrestrialTransponderSearchFinished()
					return
		self.__tlist = []
		self.remaining_data = ""
		self.terrestrial_search_container = eConsoleAppContainer()
		self.terrestrial_search_container.appClosed.append(self.terrestrialTransponderSearchClosed)
		self.terrestrial_search_container.dataAvail.append(self.getTerrestrialTransponderData)
		self.terrestrial_tunerName = nimmanager.getNimName(nim_idx)
		if self.terrestrial_tunerName.startswith("Sundtek"):
			cmd = "/opt/bin/mediaclient --blindscan /dev/dvb/adapter0/frontend%d" % nim_idx
			print("[ScanSetup] SCAN CMD : ", cmd)
			self.terrestrial_search_container.execute(cmd)
		else:
			self.terrestrial_search_binName = self.terrestrialTransponderGetCmd(nim_idx)
			self.terrestrial_search_bus = nimmanager.getI2CDevice(nim_idx)
			if self.terrestrial_search_bus is None:
				self.terrestrial_search_bus = 2
			self.terrestrial_search_feid = nim_idx
			self.terrestrial_search_enable_5v = nimmanager.nim_slots[nim_idx].config.terrestrial_5V.value
			self.terrestrial_search_list = []
			self.terrestrialTransponderInitSearchList(self.terrestrial_search_list, region)
			opt = self.terrestrialTransponderGetOpt()
			if opt is None:
				freq = bandWidth = 0
			else:
				(freq, bandWidth) = opt
			self.terrestrialTransponderSearch(freq, bandWidth)
		tmpstr = _("Try to find used transponders in terrestrial network... please wait...")
		tmpstr += "\n\n..."
		self.terrestrial_search_session = self.session.openWithCallback(self.terrestrialTransponderSearchSessionClosed, MessageBox, tmpstr, MessageBox.TYPE_INFO)

	def terrestrialTransponderSearch(self, freq, bandWidth):
		self.terrestrial_search_data = ""
		cmd = "%s --freq %d --bw %d --bus %d --ds 2" % (self.terrestrial_search_binName, freq, bandWidth, self.terrestrial_search_bus)
		if self.terrestrial_search_enable_5v:
			cmd += " --feid %d --5v %d" % (self.terrestrial_search_feid, int(self.terrestrial_search_enable_5v))
		print("[ScanSetup] SCAN CMD : ", cmd)
		self.terrestrial_search_container.execute(cmd)


class ScanSetup(ConfigListScreen, Screen, CableTransponderSearchSupport, TerrestrialTransponderSearchSupport):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle(_("Manual Scan"))
		self.skinName = ["ScanSetup", "Setup"]
		self.finished_cb = None
		self.updateSatList()
		self.service = session.nav.getCurrentService()
		self.feinfo = None
		self.networkid = 0
		frontendData = None
		if self.service is not None:
			self.feinfo = self.service.frontendInfo()
			frontendData = self.feinfo and self.feinfo.getAll(True)

		self.ter_channel_input = False
		self.ter_tnumber = None
		self.createConfig(frontendData)

		del self.feinfo
		del self.service

		self.session.postScanService = session.nav.getCurrentlyPlayingServiceOrGroup()

		self["key_green"] = StaticText(_("Scan"))

		self["actions"] = NumberActionMap(["SetupActions"],
		{
			"save": self.keyGo,
		}, -2)

		self.statusTimer = eTimer()
		self.statusTimer.callback.append(self.updateStatus)

		self.list = []
		ConfigListScreen.__init__(self, self.list, on_change=self.newConfig, fullUI=True)
		self["introduction"] = Label("")
		if not self.scan_nims.value == "":
			self.createSetup()
		else:
			self["introduction"].text = _("Nothing to scan! Setup your tuner and try again.")

	def runAsync(self, finished_cb):
		self.finished_cb = finished_cb
		self.keyGo()

	def updateSatList(self):
		self.satList = []
		for slot in nimmanager.nim_slots:
			if slot.isCompatible("DVB-S"):
				self.satList.append(nimmanager.getSatListForNim(slot.slot))
			else:
				self.satList.append(None)

	def createSetup(self):
		self.list = []
		self.multiscanlist = []
		index_to_scan = int(self.scan_nims.value)
		print("[ScanSetup] ID: ", index_to_scan)

		self.tunerEntry = getConfigListEntry(_("Tuner"), self.scan_nims)
		self.list.append(self.tunerEntry)

		self.DVB_type = self.nim_type_dict[index_to_scan]["selection"]

		if self.scan_nims == []:
			return

		self.DVB_TypeEntry = getConfigListEntry(_("DVB type"), self.DVB_type) # multitype?
		if len(self.nim_type_dict[index_to_scan]["modes"]) > 1:
			self.list.append(self.DVB_TypeEntry)
		self.typeOfScanEntry = None
		self.typeOfInputEntry = None
		self.systemEntry = None
		self.modulationEntry = None
		self.preDefSatList = None
		self.TerrestrialTransponders = None
		self.TerrestrialRegionEntry = None
		self.TerrestrialCompleteEntry = None
		self.is_id_boolEntry = None
		self.t2mi_plp_id_boolEntry = None
		indent = "- "
		nim = nimmanager.nim_slots[index_to_scan]
		if self.DVB_type.value == "DVB-S":
			self.typeOfScanEntry = getConfigListEntry(_("Type of scan"), self.scan_type)
			self.list.append(self.typeOfScanEntry)
		elif self.DVB_type.value == "DVB-C":
			if config.Nims[index_to_scan].cable.scan_type.value != "provider": # only show predefined transponder if in provider mode
				if self.scan_typecable.value == "predefined_transponder":
					self.scan_typecable.value = self.cable_toggle[self.last_scan_typecable]
			self.last_scan_typecable = self.scan_typecable.value
			self.typeOfScanEntry = getConfigListEntry(_("Type of scan"), self.scan_typecable)
			self.list.append(self.typeOfScanEntry)
		elif self.DVB_type.value == "DVB-T":
			self.typeOfScanEntry = getConfigListEntry(_("Type of scan"), self.scan_typeterrestrial)
			self.list.append(self.typeOfScanEntry)
			if self.scan_typeterrestrial.value == "single_transponder":
				self.typeOfInputEntry = getConfigListEntry(_("Use frequency or channel"), self.scan_input_as)
				if self.ter_channel_input:
					self.list.append(self.typeOfInputEntry)
				else:
					self.scan_input_as.value = self.scan_input_as.choices[0]
		elif self.DVB_type.value == "ATSC":
			self.typeOfScanEntry = getConfigListEntry(_("Type of scan"), self.scan_type_atsc)
			self.list.append(self.typeOfScanEntry)

		self.scan_networkScan.value = False
		if self.DVB_type.value == "DVB-S":
			if self.scan_type.value == "single_transponder":
				self.updateSatList()
				if nim.isCompatible("DVB-S2"):
					self.systemEntry = getConfigListEntry(_('System'), self.scan_sat.system)
					self.list.append(self.systemEntry)
				else:
					# downgrade to dvb-s, in case a -s2 config was active
					self.scan_sat.system.value = eDVBFrontendParametersSatellite.System_DVB_S
				self.list.append(getConfigListEntry(_('Satellite'), self.scan_satselection[index_to_scan]))
				self.list.append(getConfigListEntry(_('Frequency'), self.scan_sat.frequency))
				self.list.append(getConfigListEntry(_('Inversion'), self.scan_sat.inversion))
				self.list.append(getConfigListEntry(_('Symbol rate'), self.scan_sat.symbolrate))
				self.list.append(getConfigListEntry(_('Polarization'), self.scan_sat.polarization))
				if self.scan_sat.system.value == eDVBFrontendParametersSatellite.System_DVB_S:
					self.list.append(getConfigListEntry(_("FEC"), self.scan_sat.fec))
				elif self.scan_sat.system.value == eDVBFrontendParametersSatellite.System_DVB_S2:
					self.list.append(getConfigListEntry(_("FEC"), self.scan_sat.fec_s2))
					self.modulationEntry = getConfigListEntry(_('Modulation'), self.scan_sat.modulation)
					self.list.append(self.modulationEntry)
					self.list.append(getConfigListEntry(_('Roll-off'), self.scan_sat.rolloff))
					self.list.append(getConfigListEntry(_('Pilot'), self.scan_sat.pilot))
					if nim.isMultistream():
						self.is_id_boolEntry = getConfigListEntry(_('Transport Stream Type'), self.scan_sat.is_id_bool)
						self.list.append(self.is_id_boolEntry)
						if self.scan_sat.is_id_bool.value:
							self.list.append(getConfigListEntry("%s%s" % (indent, _('Input Stream ID')), self.scan_sat.is_id))
							self.list.append(getConfigListEntry("%s%s" % (indent, _('PLS Mode')), self.scan_sat.pls_mode))
							self.list.append(getConfigListEntry("%s%s" % (indent, _('PLS Code')), self.scan_sat.pls_code))
					else:
						self.scan_sat.is_id.value = eDVBFrontendParametersSatellite.No_Stream_Id_Filter
						self.scan_sat.pls_mode.value = eDVBFrontendParametersSatellite.PLS_Gold
						self.scan_sat.pls_code.value = eDVBFrontendParametersSatellite.PLS_Default_Gold_Code
					if nim.isT2MI():
						self.t2mi_plp_id_boolEntry = getConfigListEntry(_('T2MI PLP'), self.scan_sat.t2mi_plp_id_bool)
						self.list.append(self.t2mi_plp_id_boolEntry)
						if self.scan_sat.t2mi_plp_id_bool.value:
							self.list.append(getConfigListEntry("%s%s" % (indent, _('T2MI PLP ID')), self.scan_sat.t2mi_plp_id))
							self.list.append(getConfigListEntry("%s%s" % (indent, _('T2MI PID')), self.scan_sat.t2mi_pid))
					else:
						self.scan_sat.t2mi_plp_id.value = eDVBFrontendParametersSatellite.No_T2MI_PLP_Id
						self.scan_sat.t2mi_pid.value = eDVBFrontendParametersSatellite.T2MI_Default_Pid
			elif self.scan_type.value == "predefined_transponder" and self.satList[index_to_scan]:
				self.updateSatList()
				self.preDefSatList = getConfigListEntry(_('Satellite'), self.scan_satselection[index_to_scan])
				self.list.append(self.preDefSatList)
				sat = self.satList[index_to_scan][self.scan_satselection[index_to_scan].index]
				self.predefinedTranspondersList(sat[0])
				self.list.append(getConfigListEntry(_('Transponder'), self.preDefTransponders))
			elif self.scan_type.value == "single_satellite":
				self.updateSatList()
				print(self.scan_satselection[index_to_scan])
				self.list.append(getConfigListEntry(_("Satellite"), self.scan_satselection[index_to_scan]))
				self.scan_networkScan.value = True
			elif "multisat" in self.scan_type.value:
				tlist = []
				SatList = nimmanager.getSatListForNim(index_to_scan)
				for x in SatList:
					if self.Satexists(tlist, x[0]) == 0:
						tlist.append(x[0])
						sat = ConfigEnableDisable(default="_yes" in self.scan_type.value and True or False)
						configEntry = getConfigListEntry(nimmanager.getSatDescription(x[0]), sat)
						self.list.append(configEntry)
						self.multiscanlist.append((x[0], sat))
				self.scan_networkScan.value = True
		elif self.DVB_type.value == "DVB-C":
			if self.scan_typecable.value == "single_transponder":
				self.list.append(getConfigListEntry(_("Frequency (kHz)"), self.scan_cab.frequency))
				self.list.append(getConfigListEntry(_("Inversion"), self.scan_cab.inversion))
				self.list.append(getConfigListEntry(_("Symbol rate"), self.scan_cab.symbolrate))
				self.list.append(getConfigListEntry(_("Modulation"), self.scan_cab.modulation))
				self.list.append(getConfigListEntry(_("FEC"), self.scan_cab.fec))
			elif self.scan_typecable.value == "predefined_transponder":
				self.predefinedCabTranspondersList()
				self.list.append(getConfigListEntry(_('Transponder'), self.CableTransponders))
			if config.Nims[index_to_scan].cable.scan_networkid.value:
				self.networkid = config.Nims[index_to_scan].cable.scan_networkid.value
				self.scan_networkScan.value = True
		elif self.DVB_type.value == "DVB-T":
			if self.scan_typeterrestrial.value == "single_transponder":
				if nim.canBeCompatible("DVB-T2"):
					self.systemEntry = getConfigListEntry(_('System'), self.scan_ter.system)
					self.list.append(self.systemEntry)
				else:
					self.scan_ter.system.value = eDVBFrontendParametersTerrestrial.System_DVB_T
				if self.ter_channel_input and self.scan_input_as.value == "channel":
					channel = getChannelNumber(self.scan_ter.frequency.value * 1000, self.ter_tnumber)
					if channel:
						self.scan_ter.channel.value = int(channel.replace("+", "").replace("-", ""))
					self.list.append(getConfigListEntry(_("Channel"), self.scan_ter.channel))
				else:
					prev_val = self.scan_ter.frequency.value
					self.scan_ter.frequency.value = channel2frequency(self.scan_ter.channel.value, self.ter_tnumber) // 1000
					if self.scan_ter.frequency.value == 474000:
						self.scan_ter.frequency.value = prev_val
					self.list.append(getConfigListEntry(_("Frequency (kHz)"), self.scan_ter.frequency))
				self.list.append(getConfigListEntry(_("Inversion"), self.scan_ter.inversion))
				self.list.append(getConfigListEntry(_("Bandwidth"), self.scan_ter.bandwidth))
				self.list.append(getConfigListEntry(_("Code rate HP"), self.scan_ter.fechigh))
				self.list.append(getConfigListEntry(_("Code rate LP"), self.scan_ter.feclow))
				self.list.append(getConfigListEntry(_("Modulation"), self.scan_ter.modulation))
				self.list.append(getConfigListEntry(_("Transmission mode"), self.scan_ter.transmission))
				self.list.append(getConfigListEntry(_("Guard interval"), self.scan_ter.guard))
				self.list.append(getConfigListEntry(_("Hierarchy info"), self.scan_ter.hierarchy))
				if self.scan_ter.system.value == eDVBFrontendParametersTerrestrial.System_DVB_T2:
					self.list.append(getConfigListEntry(_('PLP ID'), self.scan_ter.plp_id))
			elif self.scan_typeterrestrial.value == "predefined_transponder":
				if nim.canBeCompatible("DVB-T2"):
					self.systemEntry = getConfigListEntry(_('System'), self.scan_ter.system)
					self.list.append(self.systemEntry)
				else:
					self.scan_ter.system.value = eDVBFrontendParametersTerrestrial.System_DVB_T
				self.TerrestrialRegion = nim.config.terrestrial
				self.TerrestrialRegionEntry = getConfigListEntry(_('Region'), self.TerrestrialRegion)
				self.list.append(self.TerrestrialRegionEntry)
				self.predefinedTerrTranspondersList()
				self.list.append(getConfigListEntry(_('Transponder'), self.TerrestrialTransponders))
			elif self.scan_typeterrestrial.value == "complete":
				self.TerrestrialRegion = nim.config.terrestrial
				if nimmanager.getNimName(nim.slot).startswith("Sundtek"):
					self.TerrestrialCompleteEntry = getConfigListEntry(_('Scan options'), self.scan_ter_complete_type)
					self.list.append(self.TerrestrialCompleteEntry)
				elif SystemInfo["Blindscan_t2_available"] and nim.isCompatible("DVB-T2") and len(self.terrestrialTransponderGetCmd(nim.slot)):
					self.list.append(getConfigListEntry(_('Blindscan'), self.scan_terrestrial_binary_scan))
				if self.TerrestrialCompleteEntry is None or self.scan_ter_complete_type.value == "extended":
					if nim.canBeCompatible("DVB-T2"):
						self.systemEntry = getConfigListEntry(_('System'), self.scan_ter.complete_system)
						self.list.append(self.systemEntry)
					else:
						self.scan_ter.complete_system.value = eDVBFrontendParametersTerrestrial.System_DVB_T
					self.TerrestrialRegionEntry = getConfigListEntry(_('Region'), self.TerrestrialRegion)
					self.list.append(self.TerrestrialRegionEntry)
		elif self.DVB_type.value == "ATSC":
			if self.scan_type_atsc.value == "single_transponder":
				self.systemEntry = getConfigListEntry(_("System"), self.scan_ats.system)
				self.list.append(self.systemEntry)
				self.list.append(getConfigListEntry(_("Frequency"), self.scan_ats.frequency))
				self.list.append(getConfigListEntry(_("Inversion"), self.scan_ats.inversion))
				self.list.append(getConfigListEntry(_("Modulation"), self.scan_ats.modulation))
			elif self.scan_type_atsc.value == "predefined_transponder":
				#FIXME add region
				self.predefinedATSCTranspondersList()
				self.list.append(getConfigListEntry(_('Transponder'), self.ATSCTransponders))
			elif self.scan_type_atsc.value == "complete":
				pass #FIXME
		self.list.append(getConfigListEntry(_("Network scan"), self.scan_networkScan))
		self.list.append(getConfigListEntry(_("Clear before scan"), self.scan_clearallservices))
		self.list.append(getConfigListEntry(_("Only free scan"), self.scan_onlyfree))
		self["config"].list = self.list
		self["config"].l.setList(self.list)

	def Satexists(self, tlist, pos):
		for x in tlist:
			if x == pos:
				return 1
		return 0

	def newConfig(self):
		cur = self["config"].getCurrent()
		print("[ScanSetup] cur is", cur)
		if cur == self.typeOfScanEntry or \
			cur == self.DVB_TypeEntry or \
			cur == self.typeOfInputEntry or \
			cur == self.tunerEntry or \
			cur == self.systemEntry or \
			cur == self.preDefSatList or \
			cur == self.TerrestrialRegionEntry or \
			cur == self.TerrestrialCompleteEntry or \
			(self.modulationEntry and self.systemEntry[1].value == eDVBFrontendParametersSatellite.System_DVB_S2 and cur == self.modulationEntry):
			self.createSetup()
		elif cur == self.is_id_boolEntry:
			if self.is_id_boolEntry[1].value:
				self.scan_sat.is_id.value = 0 if self.is_id_memory < 0 else self.is_id_memory
				self.scan_sat.pls_mode.value = self.pls_mode_memory
				self.scan_sat.pls_code.value = self.pls_code_memory
			else:
				self.is_id_memory = self.scan_sat.is_id.value
				self.pls_mode_memory = self.scan_sat.pls_mode.value
				self.pls_code_memory = self.scan_sat.pls_code.value
				self.scan_sat.is_id.value = eDVBFrontendParametersSatellite.No_Stream_Id_Filter
				self.scan_sat.pls_mode.value = eDVBFrontendParametersSatellite.PLS_Gold
				self.scan_sat.pls_code.value = eDVBFrontendParametersSatellite.PLS_Default_Gold_Code
			self.createSetup()
		elif cur == self.t2mi_plp_id_boolEntry:
			if self.t2mi_plp_id_boolEntry[1].value:
				self.scan_sat.t2mi_plp_id.value = 0 if self.t2mi_plp_id_memory < 0 else self.t2mi_plp_id_memory
				self.scan_sat.t2mi_pid.value = self.t2mi_pid_memory
			else:
				self.t2mi_plp_id_memory = self.scan_sat.t2mi_plp_id.value
				self.t2mi_pid_memory = self.scan_sat.t2mi_pid.value
				self.scan_sat.t2mi_plp_id.value = eDVBFrontendParametersSatellite.No_T2MI_PLP_Id
				self.scan_sat.t2mi_pid.value = eDVBFrontendParametersSatellite.T2MI_Default_Pid
			self.createSetup()

	def createConfig(self, frontendData):
		defaultSat = {
			"orbpos": 192,
			"system": eDVBFrontendParametersSatellite.System_DVB_S,
			"frequency": 11836,
			"inversion": eDVBFrontendParametersSatellite.Inversion_Unknown,
			"symbolrate": 27500,
			"polarization": eDVBFrontendParametersSatellite.Polarisation_Horizontal,
			"fec": eDVBFrontendParametersSatellite.FEC_Auto,
			"fec_s2": eDVBFrontendParametersSatellite.FEC_9_10,
			"modulation": eDVBFrontendParametersSatellite.Modulation_QPSK,
			"is_id": eDVBFrontendParametersSatellite.No_Stream_Id_Filter,
			"pls_mode": eDVBFrontendParametersSatellite.PLS_Gold,
			"pls_code": eDVBFrontendParametersSatellite.PLS_Default_Gold_Code,
			"t2mi_plp_id": eDVBFrontendParametersSatellite.No_T2MI_PLP_Id,
			"t2mi_pid": eDVBFrontendParametersSatellite.T2MI_Default_Pid}
		defaultCab = {
			"frequency": 466000,
			"inversion": eDVBFrontendParametersCable.Inversion_Unknown,
			"modulation": eDVBFrontendParametersCable.Modulation_QAM64,
			"fec": eDVBFrontendParametersCable.FEC_Auto,
			"symbolrate": 6900,
			"system": eDVBFrontendParametersCable.System_DVB_C_ANNEX_A}
		defaultTer = {
			"frequency": 474000,
			"inversion": eDVBFrontendParametersTerrestrial.Inversion_Unknown,
			"bandwidth": 8000000,
			"fechigh": eDVBFrontendParametersTerrestrial.FEC_Auto,
			"feclow": eDVBFrontendParametersTerrestrial.FEC_Auto,
			"modulation": eDVBFrontendParametersTerrestrial.Modulation_Auto,
			"transmission_mode": eDVBFrontendParametersTerrestrial.TransmissionMode_Auto,
			"guard_interval": eDVBFrontendParametersTerrestrial.GuardInterval_Auto,
			"hierarchy": eDVBFrontendParametersTerrestrial.Hierarchy_Auto,
			"system": eDVBFrontendParametersTerrestrial.System_DVB_T,
			"plp_id": 0}
		defaultATSC = {
			"frequency": 474000,
			"inversion": eDVBFrontendParametersATSC.Inversion_Unknown,
			"modulation": eDVBFrontendParametersATSC.Modulation_Auto,
			"system": eDVBFrontendParametersATSC.System_ATSC}

		ttype = "UNKNOWN"
		if frontendData is not None:
			ttype = frontendData.get("tuner_type", "UNKNOWN")
			if ttype == "DVB-S":
				defaultSat["system"] = frontendData.get("system", eDVBFrontendParametersSatellite.System_DVB_S)
				defaultSat["frequency"] = frontendData.get("frequency", defaultSat["frequency"] * 1000) // 1000
				defaultSat["inversion"] = frontendData.get("inversion", eDVBFrontendParametersSatellite.Inversion_Unknown)
				defaultSat["symbolrate"] = frontendData.get("symbol_rate", 0) // 1000
				defaultSat["polarization"] = frontendData.get("polarization", eDVBFrontendParametersSatellite.Polarisation_Horizontal)
				if defaultSat["system"] == eDVBFrontendParametersSatellite.System_DVB_S2:
					defaultSat["fec_s2"] = frontendData.get("fec_inner", eDVBFrontendParametersSatellite.FEC_Auto)
					defaultSat["rolloff"] = frontendData.get("rolloff", eDVBFrontendParametersSatellite.RollOff_alpha_0_35)
					defaultSat["pilot"] = frontendData.get("pilot", eDVBFrontendParametersSatellite.Pilot_Unknown)
					defaultSat["is_id"] = frontendData.get("is_id", defaultSat["is_id"])
					defaultSat["pls_mode"] = frontendData.get("pls_mode", defaultSat["pls_mode"])
					defaultSat["pls_code"] = frontendData.get("pls_code", defaultSat["pls_code"])
					defaultSat["t2mi_plp_id"] = frontendData.get("t2mi_plp_id", defaultSat["t2mi_plp_id"])
					defaultSat["t2mi_pid"] = frontendData.get("t2mi_pid", defaultSat["t2mi_pid"])
				else:
					defaultSat["fec"] = frontendData.get("fec_inner", eDVBFrontendParametersSatellite.FEC_Auto)
				defaultSat["modulation"] = frontendData.get("modulation", eDVBFrontendParametersSatellite.Modulation_QPSK)
				defaultSat["orbpos"] = frontendData.get("orbital_position", 0)
			elif ttype == "DVB-C":
				defaultCab["frequency"] = frontendData.get("frequency", defaultCab["frequency"])
				defaultCab["symbolrate"] = frontendData.get("symbol_rate", 0) // 1000
				defaultCab["inversion"] = frontendData.get("inversion", eDVBFrontendParametersCable.Inversion_Unknown)
				defaultCab["fec"] = frontendData.get("fec_inner", eDVBFrontendParametersCable.FEC_Auto)
				defaultCab["modulation"] = frontendData.get("modulation", eDVBFrontendParametersCable.Modulation_QAM16)
				defaultCab["system"] = frontendData.get("system", eDVBFrontendParametersCable.System_DVB_C_ANNEX_A)
			elif ttype == "DVB-T":
				defaultTer["frequency"] = frontendData.get("frequency", defaultTer["frequency"] * 1000) // 1000
				defaultTer["inversion"] = frontendData.get("inversion", eDVBFrontendParametersTerrestrial.Inversion_Unknown)
				defaultTer["bandwidth"] = frontendData.get("bandwidth", 8000000)
				defaultTer["fechigh"] = frontendData.get("code_rate_hp", eDVBFrontendParametersTerrestrial.FEC_Auto)
				defaultTer["feclow"] = frontendData.get("code_rate_lp", eDVBFrontendParametersTerrestrial.FEC_Auto)
				defaultTer["modulation"] = frontendData.get("constellation", eDVBFrontendParametersTerrestrial.Modulation_Auto)
				defaultTer["transmission_mode"] = frontendData.get("transmission_mode", eDVBFrontendParametersTerrestrial.TransmissionMode_Auto)
				defaultTer["guard_interval"] = frontendData.get("guard_interval", eDVBFrontendParametersTerrestrial.GuardInterval_Auto)
				defaultTer["hierarchy"] = frontendData.get("hierarchy_information", eDVBFrontendParametersTerrestrial.Hierarchy_Auto)
				defaultTer["system"] = frontendData.get("system", eDVBFrontendParametersTerrestrial.System_DVB_T)
				defaultTer["plp_id"] = frontendData.get("plp_id", 0)
			elif ttype == "ATSC":
				defaultATSC["frequency"] = frontendData.get("frequency", defaultATSC["frequency"] * 1000) // 1000
				defaultATSC["inversion"] = frontendData.get("inversion", eDVBFrontendParametersATSC.Inversion_Unknown)
				defaultATSC["modulation"] = frontendData.get("modulation", eDVBFrontendParametersATSC.Modulation_Auto)
				defaultATSC["system"] = frontendData.get("system", eDVBFrontendParametersATSC.System_ATSC)

		self.scan_sat = ConfigSubsection()
		self.scan_cab = ConfigSubsection()
		self.scan_ter = ConfigSubsection()
		self.scan_ats = ConfigSubsection()

		nim_list = []
		self.nim_type_dict = {}
		# collect all nims which are *not* set to "nothing"
		for n in nimmanager.nim_slots:
			if n.config_mode == "nothing":
				continue
			if n.config_mode == "advanced" and len(nimmanager.getSatListForNim(n.slot)) < 1:
				continue
			if n.config_mode in ("loopthrough", "satposdepends"):
				root_id = nimmanager.sec.getRoot(n.slot_id, int(n.config.connectedTo.value))
				if n.type == nimmanager.nim_slots[root_id].type: # check if connected from a DVB-S to DVB-S2 Nim or vice versa
					continue
			nim_list.append((str(n.slot), n.friendly_full_description))

			modes = [x[:5] for x in n.getTunerTypesEnabled()]
			self.nim_type_dict[n.slot] = {"modes": modes,
				"selection": ConfigSelection(choices=[(x, {"DVB-S": _("Satellite"), "DVB-T": _("Terrestrial"), "DVB-C": _("Cable"), "ATSC": _("ATSC")}.get(x, "")) for x in modes])}
			if ttype in modes:
				self.nim_type_dict[n.slot]["selection"].value = ttype

		self.scan_nims = ConfigSelection(choices=nim_list)
		if frontendData is not None and len(nim_list) > 0:
			self.scan_nims.value = str(frontendData.get("tuner_number", nim_list[0][0]))

		for slot in nimmanager.nim_slots:
			if slot.isCompatible("DVB-T") or (slot.isCompatible("DVB-S") and slot.canBeCompatible("DVB-T")):
				self.ter_tnumber = slot.slot
		if self.ter_tnumber is not None:
			self.ter_channel_input = supportedChannels(self.ter_tnumber)

		# status
		self.scan_snr = ConfigSlider()
		self.scan_snr.enabled = False
		self.scan_agc = ConfigSlider()
		self.scan_agc.enabled = False
		self.scan_ber = ConfigSlider()
		self.scan_ber.enabled = False

		# sat
		self.scan_sat.system = ConfigSelection(default=defaultSat["system"], choices=[
			(eDVBFrontendParametersSatellite.System_DVB_S, _("DVB-S")),
			(eDVBFrontendParametersSatellite.System_DVB_S2, _("DVB-S2"))])
		self.scan_sat.frequency = ConfigInteger(default=defaultSat["frequency"], limits=(1, 99999))
		self.scan_sat.inversion = ConfigSelection(default=defaultSat["inversion"], choices=[
			(eDVBFrontendParametersSatellite.Inversion_Off, _("Off")),
			(eDVBFrontendParametersSatellite.Inversion_On, _("On")),
			(eDVBFrontendParametersSatellite.Inversion_Unknown, _("Auto"))])
		self.scan_sat.symbolrate = ConfigInteger(default=defaultSat["symbolrate"], limits=(1, 99999))
		self.scan_sat.polarization = ConfigSelection(default=defaultSat["polarization"], choices=[
			(eDVBFrontendParametersSatellite.Polarisation_Horizontal, _("horizontal")),
			(eDVBFrontendParametersSatellite.Polarisation_Vertical, _("vertical")),
			(eDVBFrontendParametersSatellite.Polarisation_CircularLeft, _("circular left")),
			(eDVBFrontendParametersSatellite.Polarisation_CircularRight, _("circular right"))])
		self.scan_sat.fec = ConfigSelection(default=defaultSat["fec"], choices=[
			(eDVBFrontendParametersSatellite.FEC_Auto, _("Auto")),
			(eDVBFrontendParametersSatellite.FEC_1_2, "1/2"),
			(eDVBFrontendParametersSatellite.FEC_2_3, "2/3"),
			(eDVBFrontendParametersSatellite.FEC_3_4, "3/4"),
			(eDVBFrontendParametersSatellite.FEC_5_6, "5/6"),
			(eDVBFrontendParametersSatellite.FEC_7_8, "7/8"),
			(eDVBFrontendParametersSatellite.FEC_None, _("None"))])
		self.scan_sat.fec_s2 = ConfigSelection(default=defaultSat["fec_s2"], choices=[
			(eDVBFrontendParametersSatellite.FEC_Auto, _("Auto")),
			(eDVBFrontendParametersSatellite.FEC_1_2, "1/2"),
			(eDVBFrontendParametersSatellite.FEC_2_3, "2/3"),
			(eDVBFrontendParametersSatellite.FEC_3_4, "3/4"),
			(eDVBFrontendParametersSatellite.FEC_3_5, "3/5"),
			(eDVBFrontendParametersSatellite.FEC_4_5, "4/5"),
			(eDVBFrontendParametersSatellite.FEC_5_6, "5/6"),
			(eDVBFrontendParametersSatellite.FEC_6_7, "6/7"),
			(eDVBFrontendParametersSatellite.FEC_7_8, "7/8"),
			(eDVBFrontendParametersSatellite.FEC_8_9, "8/9"),
			(eDVBFrontendParametersSatellite.FEC_9_10, "9/10")])
		self.scan_sat.modulation = ConfigSelection(default=defaultSat["modulation"], choices=[
			(eDVBFrontendParametersSatellite.Modulation_QPSK, "QPSK"),
			(eDVBFrontendParametersSatellite.Modulation_8PSK, "8PSK"),
			(eDVBFrontendParametersSatellite.Modulation_16APSK, "16APSK"),
			(eDVBFrontendParametersSatellite.Modulation_32APSK, "32APSK")])
		self.scan_sat.rolloff = ConfigSelection(default=defaultSat.get("rolloff", eDVBFrontendParametersSatellite.RollOff_alpha_0_35), choices=[
			(eDVBFrontendParametersSatellite.RollOff_alpha_0_35, "0.35"),
			(eDVBFrontendParametersSatellite.RollOff_alpha_0_25, "0.25"),
			(eDVBFrontendParametersSatellite.RollOff_alpha_0_20, "0.20"),
			(eDVBFrontendParametersSatellite.RollOff_auto, _("Auto"))])
		self.scan_sat.pilot = ConfigSelection(default=defaultSat.get("pilot", eDVBFrontendParametersSatellite.Pilot_Unknown), choices=[
			(eDVBFrontendParametersSatellite.Pilot_Off, _("Off")),
			(eDVBFrontendParametersSatellite.Pilot_On, _("On")),
			(eDVBFrontendParametersSatellite.Pilot_Unknown, _("Auto"))])
		self.scan_sat.is_id = ConfigInteger(default=defaultSat["is_id"], limits=(eDVBFrontendParametersSatellite.No_Stream_Id_Filter, 255))
		self.scan_sat.is_id_bool = ConfigSelection(default=defaultSat["is_id"] != eDVBFrontendParametersSatellite.No_Stream_Id_Filter, choices=[(True, _("Multistream")), (False, _("Ordinary"))])
		self.scan_sat.pls_mode = ConfigSelection(default=defaultSat["pls_mode"], choices=[
			(eDVBFrontendParametersSatellite.PLS_Root, _("Root")),
			(eDVBFrontendParametersSatellite.PLS_Gold, _("Gold")),
			(eDVBFrontendParametersSatellite.PLS_Combo, _("Combo"))])
		self.scan_sat.pls_code = ConfigInteger(default=defaultSat["pls_code"], limits=(0, 262142))
		self.scan_sat.t2mi_plp_id = ConfigInteger(default=defaultSat["t2mi_plp_id"], limits=(eDVBFrontendParametersSatellite.No_T2MI_PLP_Id, 255))
		self.scan_sat.t2mi_pid = ConfigInteger(default=defaultSat["t2mi_pid"] if self.scan_sat.t2mi_plp_id.value != eDVBFrontendParametersSatellite.No_T2MI_PLP_Id else eDVBFrontendParametersSatellite.T2MI_Default_Pid, limits=(0, 8191))
		self.scan_sat.t2mi_plp_id_bool = ConfigSelection(default=defaultSat["t2mi_plp_id"] != eDVBFrontendParametersSatellite.No_T2MI_PLP_Id, choices=[(True, _("Enabled")), (False, _("Disabled"))])

		self.is_id_memory = self.scan_sat.is_id.value # used to prevent is_id value being lost when self.scan_sat.is_id_bool state changes
		self.pls_mode_memory = self.scan_sat.pls_mode.value
		self.pls_code_memory = self.scan_sat.pls_code.value
		self.t2mi_plp_id_memory = self.scan_sat.t2mi_plp_id.value
		self.t2mi_pid_memory = self.scan_sat.t2mi_pid.value

		# cable
		self.scan_cab.frequency = ConfigInteger(default=defaultCab["frequency"], limits=(50000, 999000))
		self.scan_cab.inversion = ConfigSelection(default=defaultCab["inversion"], choices=[
			(eDVBFrontendParametersCable.Inversion_Off, _("Off")),
			(eDVBFrontendParametersCable.Inversion_On, _("On")),
			(eDVBFrontendParametersCable.Inversion_Unknown, _("Auto"))])
		self.scan_cab.modulation = ConfigSelection(default=defaultCab["modulation"], choices=[
			(eDVBFrontendParametersCable.Modulation_QAM16, "16-QAM"),
			(eDVBFrontendParametersCable.Modulation_QAM32, "32-QAM"),
			(eDVBFrontendParametersCable.Modulation_QAM64, "64-QAM"),
			(eDVBFrontendParametersCable.Modulation_QAM128, "128-QAM"),
			(eDVBFrontendParametersCable.Modulation_QAM256, "256-QAM")])
		self.scan_cab.fec = ConfigSelection(default=defaultCab["fec"], choices=[
			(eDVBFrontendParametersCable.FEC_Auto, _("Auto")),
			(eDVBFrontendParametersCable.FEC_1_2, "1/2"),
			(eDVBFrontendParametersCable.FEC_2_3, "2/3"),
			(eDVBFrontendParametersCable.FEC_3_4, "3/4"),
			(eDVBFrontendParametersCable.FEC_3_5, "3/5"),
			(eDVBFrontendParametersCable.FEC_4_5, "4/5"),
			(eDVBFrontendParametersCable.FEC_5_6, "5/6"),
			(eDVBFrontendParametersCable.FEC_6_7, "6/7"),
			(eDVBFrontendParametersCable.FEC_7_8, "7/8"),
			(eDVBFrontendParametersCable.FEC_8_9, "8/9"),
			(eDVBFrontendParametersCable.FEC_9_10, "9/10"),
			(eDVBFrontendParametersCable.FEC_None, _("None"))])
		self.scan_cab.symbolrate = ConfigInteger(default=defaultCab["symbolrate"], limits=(1, 99999))
		self.scan_cab.system = ConfigSelection(default=defaultCab["system"], choices=[
			(eDVBFrontendParametersCable.System_DVB_C_ANNEX_A, _("DVB-C")),
			(eDVBFrontendParametersCable.System_DVB_C_ANNEX_C, _("DVB-C ANNEX C"))])

		# terrestial
		self.scan_ter.frequency = ConfigInteger(default=defaultTer["frequency"], limits=(50000, 999000))
		self.scan_ter.channel = ConfigInteger(default=21, limits=(1, 99))
		self.scan_ter.inversion = ConfigSelection(default=defaultTer["inversion"], choices=[
			(eDVBFrontendParametersTerrestrial.Inversion_Off, _("Off")),
			(eDVBFrontendParametersTerrestrial.Inversion_On, _("On")),
			(eDVBFrontendParametersTerrestrial.Inversion_Unknown, _("Auto"))])
		# WORKAROUND: we can't use BW-auto
		self.scan_ter.bandwidth = ConfigSelection(default=defaultTer["bandwidth"], choices=[
			(1712000, "1.712MHz"),
			(5000000, "5MHz"),
			(6000000, "6MHz"),
			(7000000, "7MHz"),
			(8000000, "8MHz"),
			(10000000, "10MHz")
			])
		#, (eDVBFrontendParametersTerrestrial.Bandwidth_Auto, _("Auto"))))
		self.scan_ter.fechigh = ConfigSelection(default=defaultTer["fechigh"], choices=[
			(eDVBFrontendParametersTerrestrial.FEC_1_2, "1/2"),
			(eDVBFrontendParametersTerrestrial.FEC_2_3, "2/3"),
			(eDVBFrontendParametersTerrestrial.FEC_3_4, "3/4"),
			(eDVBFrontendParametersTerrestrial.FEC_3_5, "3/5"),
			(eDVBFrontendParametersTerrestrial.FEC_4_5, "4/5"),
			(eDVBFrontendParametersTerrestrial.FEC_5_6, "5/6"),
			(eDVBFrontendParametersTerrestrial.FEC_6_7, "6/7"),
			(eDVBFrontendParametersTerrestrial.FEC_7_8, "7/8"),
			(eDVBFrontendParametersTerrestrial.FEC_8_9, "8/9"),
			(eDVBFrontendParametersTerrestrial.FEC_Auto, _("Auto"))])
		self.scan_ter.feclow = ConfigSelection(default=defaultTer["feclow"], choices=[
			(eDVBFrontendParametersTerrestrial.FEC_1_2, "1/2"),
			(eDVBFrontendParametersTerrestrial.FEC_2_3, "2/3"),
			(eDVBFrontendParametersTerrestrial.FEC_3_4, "3/4"),
			(eDVBFrontendParametersTerrestrial.FEC_3_5, "3/5"),
			(eDVBFrontendParametersTerrestrial.FEC_4_5, "4/5"),
			(eDVBFrontendParametersTerrestrial.FEC_5_6, "5/6"),
			(eDVBFrontendParametersTerrestrial.FEC_6_7, "6/7"),
			(eDVBFrontendParametersTerrestrial.FEC_7_8, "7/8"),
			(eDVBFrontendParametersTerrestrial.FEC_8_9, "8/9"),
			(eDVBFrontendParametersTerrestrial.FEC_Auto, _("Auto"))])
		self.scan_ter.modulation = ConfigSelection(default=defaultTer["modulation"], choices=[
			(eDVBFrontendParametersTerrestrial.Modulation_QPSK, "QPSK"),
			(eDVBFrontendParametersTerrestrial.Modulation_QAM16, "QAM16"),
			(eDVBFrontendParametersTerrestrial.Modulation_QAM64, "QAM64"),
			(eDVBFrontendParametersTerrestrial.Modulation_QAM256, "QAM256"),
			(eDVBFrontendParametersTerrestrial.Modulation_Auto, _("Auto"))])
		self.scan_ter.transmission = ConfigSelection(default=defaultTer["transmission_mode"], choices=[
			(eDVBFrontendParametersTerrestrial.TransmissionMode_1k, "1K"),
			(eDVBFrontendParametersTerrestrial.TransmissionMode_2k, "2K"),
			(eDVBFrontendParametersTerrestrial.TransmissionMode_4k, "4K"),
			(eDVBFrontendParametersTerrestrial.TransmissionMode_8k, "8K"),
			(eDVBFrontendParametersTerrestrial.TransmissionMode_16k, "16K"),
			(eDVBFrontendParametersTerrestrial.TransmissionMode_32k, "32K"),
			(eDVBFrontendParametersTerrestrial.TransmissionMode_Auto, _("Auto"))])
		self.scan_ter.guard = ConfigSelection(default=defaultTer["guard_interval"], choices=[
			(eDVBFrontendParametersTerrestrial.GuardInterval_1_32, "1/32"),
			(eDVBFrontendParametersTerrestrial.GuardInterval_1_16, "1/16"),
			(eDVBFrontendParametersTerrestrial.GuardInterval_1_8, "1/8"),
			(eDVBFrontendParametersTerrestrial.GuardInterval_1_4, "1/4"),
			(eDVBFrontendParametersTerrestrial.GuardInterval_1_128, "1/128"),
			(eDVBFrontendParametersTerrestrial.GuardInterval_19_128, "19/128"),
			(eDVBFrontendParametersTerrestrial.GuardInterval_19_256, "19/256"),
			(eDVBFrontendParametersTerrestrial.GuardInterval_Auto, _("Auto"))])
		self.scan_ter.hierarchy = ConfigSelection(default=defaultTer["hierarchy"], choices=[
			(eDVBFrontendParametersTerrestrial.Hierarchy_None, _("None")),
			(eDVBFrontendParametersTerrestrial.Hierarchy_1, "1"),
			(eDVBFrontendParametersTerrestrial.Hierarchy_2, "2"),
			(eDVBFrontendParametersTerrestrial.Hierarchy_4, "4"),
			(eDVBFrontendParametersTerrestrial.Hierarchy_Auto, _("Auto"))])
		self.scan_ter.system = ConfigSelection(default=defaultTer["system"], choices=[
			(eDVBFrontendParametersTerrestrial.System_DVB_T_T2, _("Auto")),
			(eDVBFrontendParametersTerrestrial.System_DVB_T, _("DVB-T")),
			(eDVBFrontendParametersTerrestrial.System_DVB_T2, _("DVB-T2"))])
		self.scan_ter.complete_system = ConfigSelection(default=eDVBFrontendParametersTerrestrial.System_DVB_T_T2, choices=[
			(eDVBFrontendParametersTerrestrial.System_DVB_T_T2, _("Auto")),
			(eDVBFrontendParametersTerrestrial.System_DVB_T, _("DVB-T")),
			(eDVBFrontendParametersTerrestrial.System_DVB_T2, _("DVB-T2"))])
		self.scan_ter.plp_id = ConfigInteger(default=defaultTer["plp_id"], limits=(0, 255))

		# ATSC
		self.scan_ats.frequency = ConfigInteger(default=defaultATSC["frequency"], limits=(50000, 999000))
		self.scan_ats.inversion = ConfigSelection(default=defaultATSC["inversion"], choices=[
			(eDVBFrontendParametersATSC.Inversion_Off, _("Off")),
			(eDVBFrontendParametersATSC.Inversion_On, _("On")),
			(eDVBFrontendParametersATSC.Inversion_Unknown, _("Auto"))])
		self.scan_ats.modulation = ConfigSelection(default=defaultATSC["modulation"], choices=[
			(eDVBFrontendParametersATSC.Modulation_Auto, _("Auto")),
			(eDVBFrontendParametersATSC.Modulation_QAM16, "QAM16"),
			(eDVBFrontendParametersATSC.Modulation_QAM32, "QAM32"),
			(eDVBFrontendParametersATSC.Modulation_QAM64, "QAM64"),
			(eDVBFrontendParametersATSC.Modulation_QAM128, "QAM128"),
			(eDVBFrontendParametersATSC.Modulation_QAM256, "QAM256"),
			(eDVBFrontendParametersATSC.Modulation_VSB_8, "8VSB"),
			(eDVBFrontendParametersATSC.Modulation_VSB_16, "16VSB")])
		self.scan_ats.system = ConfigSelection(default=defaultATSC["system"], choices=[
			(eDVBFrontendParametersATSC.System_ATSC, _("ATSC")),
			(eDVBFrontendParametersATSC.System_DVB_C_ANNEX_B, _("DVB-C ANNEX B"))])

		self.scan_scansat = {}
		for sat in nimmanager.satList:
			#print(sat[1])
			self.scan_scansat[sat[0]] = ConfigYesNo(default=False)

		self.scan_satselection = []
		for slot in nimmanager.nim_slots:
			if slot.isCompatible("DVB-S"):
				self.scan_satselection.append(getConfigSatlist(defaultSat["orbpos"], self.satList[slot.slot]))
			else:
				self.scan_satselection.append(None)

		if frontendData is not None and ttype == "DVB-S" and self.predefinedTranspondersList(defaultSat["orbpos"]) is not None:
			defaultSatSearchType = "predefined_transponder"
		else:
			defaultSatSearchType = "single_transponder"
		if frontendData is not None and ttype == "DVB-T" and self.predefinedTerrTranspondersList() is not None:
			defaultTerrSearchType = "predefined_transponder"
		else:
			defaultTerrSearchType = "single_transponder"

		if frontendData is not None and ttype == "DVB-C" and self.predefinedCabTranspondersList() is not None:
			defaultCabSearchType = "predefined_transponder"
		else:
			defaultCabSearchType = "single_transponder"

		if frontendData is not None and ttype == "ATSC" and self.predefinedATSCTranspondersList() is not None:
			defaultATSCSearchType = "predefined_transponder"
		else:
			defaultATSCSearchType = "single_transponder"

		self.scan_type = ConfigSelection(default=defaultSatSearchType, choices=[("single_transponder", _("User defined transponder")), ("predefined_transponder", _("Predefined transponder")), ("single_satellite", _("Single satellite")), ("multisat", _("Multisat")), ("multisat_yes", _("Multisat all select"))])
		self.scan_typecable = ConfigSelection(default=defaultCabSearchType, choices=[("single_transponder", _("User defined transponder")), ("predefined_transponder", _("Predefined transponder")), ("complete", _("Complete"))])
		self.last_scan_typecable = "single_transponder"
		self.cable_toggle = {"single_transponder": "complete", "complete": "single_transponder"}
		self.scan_typeterrestrial = ConfigSelection(default=defaultTerrSearchType, choices=[("single_transponder", _("User defined transponder")), ("predefined_transponder", _("Predefined transponder")), ("complete", _("Complete"))])
		self.scan_type_atsc = ConfigSelection(default=defaultATSCSearchType, choices=[("single_transponder", _("User defined transponder")), ("predefined_transponder", _("Predefined transponder")), ("complete", _("Complete"))])
		self.scan_input_as = ConfigSelection(default="channel", choices=[("frequency", _("Frequency")), ("channel", _("Channel"))])
		self.scan_ter_complete_type = ConfigSelection(default="all", choices=[("all", _("All frequency")), ("extended", _("Extended"))])
		self.scan_clearallservices = ConfigSelection(default="no", choices=[("no", _("no")), ("yes", _("yes")), ("yes_hold_feeds", _("yes (keep feeds)"))])
		self.scan_onlyfree = ConfigYesNo(default=False)
		self.scan_networkScan = ConfigYesNo(default=False)
		self.scan_terrestrial_binary_scan = ConfigYesNo(default=False)

		return True

	def updateStatus(self):
		print("[ScanSetup] updatestatus")

	def addSatTransponder(self, tlist, frequency, symbol_rate, polarisation, fec, inversion, orbital_position, system, modulation, rolloff, pilot, is_id, pls_mode, pls_code, t2mi_plp_id, t2mi_pid):
		print("[ScanSetup] Add Sat: frequ: " + str(frequency) + " symbol: " + str(symbol_rate) + " pol: " + str(polarisation) + " fec: " + str(fec) + " inversion: " + str(inversion) + " modulation: " + str(modulation) + " system: " + str(system) + " rolloff: " + str(rolloff) + " pilot: " + str(pilot) + " is_id: " + str(is_id) + " pls_mode: " + str(pls_mode) + " pls_code: " + str(pls_code) + " t2mi_plp_id: " + str(t2mi_plp_id) + " t2mi_pid: " + str(t2mi_pid))
		print("[ScanSetup] orbpos: " + str(orbital_position))
		parm = eDVBFrontendParametersSatellite()
		parm.modulation = modulation
		parm.system = system
		parm.frequency = frequency * 1000
		parm.symbol_rate = symbol_rate * 1000
		parm.polarisation = polarisation
		parm.fec = fec
		parm.inversion = inversion
		parm.orbital_position = orbital_position
		parm.rolloff = rolloff
		parm.pilot = pilot
		parm.is_id = is_id
		parm.pls_mode = pls_mode
		parm.pls_code = pls_code
		parm.t2mi_plp_id = t2mi_plp_id
		parm.t2mi_pid = t2mi_pid
		tlist.append(parm)

	def addCabTransponder(self, tlist, frequency, symbol_rate, modulation, fec, inversion):
		print("[ScanSetup] Add Cab: frequ: " + str(frequency) + " symbol: " + str(symbol_rate) + " pol: " + str(modulation) + " fec: " + str(fec) + " inversion: " + str(inversion))
		parm = eDVBFrontendParametersCable()
		parm.frequency = frequency
		parm.symbol_rate = symbol_rate
		parm.modulation = modulation
		parm.fec_inner = fec
		parm.inversion = inversion
		tlist.append(parm)

	def addTerTransponder(self, tlist, *args, **kwargs):
		tlist.append(buildTerTransponder(*args, **kwargs))

	def addATSCTransponder(self, tlist, frequency, modulation, inversion, system):
		print("Add ATSC frequency: %s modulation: %s inversion: %s system: %s" % (frequency, modulation, inversion, system))
		parm = eDVBFrontendParametersATSC()
		parm.frequency = frequency
		parm.inversion = inversion
		parm.modulation = modulation
		parm.system = system
		tlist.append(parm)

	def keyGo(self):
		infoBarInstance = InfoBar.instance
		if infoBarInstance:
			infoBarInstance.checkTimeshiftRunning(self.keyGoCheckTimeshiftCallback)
		else:
			self.keyGoCheckTimeshiftCallback(True)

	def keyGoCheckTimeshiftCallback(self, answer):
		START_SCAN = 0
		SEARCH_CABLE_TRANSPONDERS = 1
		SEARCH_TERRESTRIAL2_TRANSPONDERS = 2
		if not answer or self.scan_nims.value == "":
			return
		tlist = []
		flags = 0
		removeAll = True
		action = START_SCAN
		index_to_scan = int(self.scan_nims.value)

		if self.scan_nims == []:
			self.session.open(MessageBox, _("No tuner is enabled!\nPlease setup your tuner settings before you start a service scan."), MessageBox.TYPE_ERROR)
			return

		nim = nimmanager.nim_slots[index_to_scan]
		print("[ScanSetup] nim", nim.slot)
		if self.DVB_type.value == "DVB-S":
			print("[ScanSetup] is compatible with DVB-S")
			if self.scan_type.value == "single_transponder":
				# these lists are generated for each tuner, so this has work.
				assert len(self.satList) > index_to_scan
				assert len(self.scan_satselection) > index_to_scan

				nimsats = self.satList[index_to_scan]
				selsatidx = self.scan_satselection[index_to_scan].index

				# however, the satList itself could be empty. in that case, "index" is 0 (for "None").
				if len(nimsats):
					orbpos = nimsats[selsatidx][0]
					if self.scan_sat.system.value == eDVBFrontendParametersSatellite.System_DVB_S:
						fec = self.scan_sat.fec.value
					else:
						fec = self.scan_sat.fec_s2.value
					print("[ScanSetup] add sat transponder")
					self.addSatTransponder(tlist, self.scan_sat.frequency.value,
								self.scan_sat.symbolrate.value,
								self.scan_sat.polarization.value,
								fec,
								self.scan_sat.inversion.value,
								orbpos,
								self.scan_sat.system.value,
								self.scan_sat.modulation.value,
								self.scan_sat.rolloff.value,
								self.scan_sat.pilot.value,
								self.scan_sat.is_id.value,
								self.scan_sat.pls_mode.value,
								self.scan_sat.pls_code.value,
								self.scan_sat.t2mi_plp_id.value,
								self.scan_sat.t2mi_pid.value)
				removeAll = False
			elif self.scan_type.value == "predefined_transponder":
				nimsats = self.satList[index_to_scan]
				selsatidx = self.scan_satselection[index_to_scan].index
				if len(nimsats):
					orbpos = nimsats[selsatidx][0]
					tps = nimmanager.getTransponders(orbpos, index_to_scan)
					if len(tps) and len(tps) > self.preDefTransponders.index:
						tp = tps[self.preDefTransponders.index]
						self.addSatTransponder(tlist, tp[1] // 1000, tp[2] // 1000, tp[3], tp[4], tp[7], orbpos, tp[5], tp[6], tp[8], tp[9], tp[10], tp[11], tp[12], tp[13], tp[14])
				removeAll = False
			elif self.scan_type.value == "single_satellite":
				sat = self.satList[index_to_scan][self.scan_satselection[index_to_scan].index]
				getInitialTransponderList(tlist, sat[0], index_to_scan)
			elif "multisat" in self.scan_type.value:
				SatList = nimmanager.getSatListForNim(index_to_scan)
				for x in self.multiscanlist:
					if x[1].value:
						print("[ScanSetup]    " + str(x[0]))
						getInitialTransponderList(tlist, x[0], index_to_scan)

		elif self.DVB_type.value == "DVB-C":
			if self.scan_typecable.value == "single_transponder":
				self.addCabTransponder(tlist, self.scan_cab.frequency.value,
							self.scan_cab.symbolrate.value * 1000,
							self.scan_cab.modulation.value,
							self.scan_cab.fec.value,
							self.scan_cab.inversion.value)
				removeAll = False
			elif self.scan_typecable.value == "predefined_transponder":
				tps = nimmanager.getTranspondersCable(index_to_scan)
				if len(tps) and len(tps) > self.CableTransponders.index:
					tp = tps[self.CableTransponders.index]
					# 0 transponder type, 1 freq, 2 sym, 3 mod, 4 fec, 5 inv, 6 sys
					self.addCabTransponder(tlist, tp[1], tp[2], tp[3], tp[4], tp[5])
				removeAll = False
			elif self.scan_typecable.value == "complete":
				if config.Nims[index_to_scan].cable.scan_type.value == "provider":
					getInitialCableTransponderList(tlist, index_to_scan)
				elif nimmanager.nim_slots[index_to_scan].supportsBlindScan():
					flags |= eComponentScan.scanBlindSearch
					self.addCabTransponder(tlist, 73000, (866000 - 73000) / 1000,
								eDVBFrontendParametersCable.Modulation_Auto,
								eDVBFrontendParametersCable.FEC_Auto,
								eDVBFrontendParametersCable.Inversion_Unknown)
					removeAll = False
				else:
					action = SEARCH_CABLE_TRANSPONDERS

		elif self.DVB_type.value == "DVB-T":
			if self.scan_typeterrestrial.value == "single_transponder":
				if self.scan_input_as.value == "channel":
					frequency = channel2frequency(self.scan_ter.channel.value, self.ter_tnumber)
				else:
					frequency = self.scan_ter.frequency.value * 1000
				self.addTerTransponder(tlist,
						frequency,
						inversion=self.scan_ter.inversion.value,
						bandwidth=self.scan_ter.bandwidth.value,
						fechigh=self.scan_ter.fechigh.value,
						feclow=self.scan_ter.feclow.value,
						modulation=self.scan_ter.modulation.value,
						transmission=self.scan_ter.transmission.value,
						guard=self.scan_ter.guard.value,
						hierarchy=self.scan_ter.hierarchy.value,
						system=self.scan_ter.system.value,
						plp_id=self.scan_ter.plp_id.value)
				removeAll = False
			elif self.scan_typeterrestrial.value == "predefined_transponder":
				if self.TerrestrialTransponders is not None:
					region = self.TerrestrialRegion.description[self.TerrestrialRegion.value]
					tps = nimmanager.getTranspondersTerrestrial(region)
					if len(tps) and len(tps) > self.TerrestrialTransponders.index:
						tp = tps[self.TerrestrialTransponders.index]
						tlist.append(buildTerTransponder(tp[1], tp[9], tp[2], tp[4], tp[5], tp[3], tp[7], tp[6], tp[8], self.scan_ter.system.value, tp[11]))
				removeAll = False
			elif self.scan_typeterrestrial.value == "complete":
				if nimmanager.getNimName(nim.slot).startswith("Sundtek") and self.scan_ter_complete_type.value == "all":
					action = SEARCH_TERRESTRIAL2_TRANSPONDERS
				elif SystemInfo["Blindscan_t2_available"] and self.scan_terrestrial_binary_scan.value and nim.isCompatible("DVB-T2") and len(self.terrestrialTransponderGetCmd(nim.slot)):
					action = SEARCH_TERRESTRIAL2_TRANSPONDERS
				else:
					getInitialTerrestrialTransponderList(tlist, self.TerrestrialRegion.description[self.TerrestrialRegion.value], int(self.scan_ter.complete_system.value))

		elif self.DVB_type.value == "ATSC":
			if self.scan_type_atsc.value == "single_transponder":
				self.addATSCTransponder(tlist,
						frequency=self.scan_ats.frequency.value * 1000,
						modulation=self.scan_ats.modulation.value,
						inversion=self.scan_ats.inversion.value,
						system=self.scan_ats.system.value)
				removeAll = False
			elif self.scan_type_atsc.value == "predefined_transponder":
				tps = nimmanager.getTranspondersATSC(index_to_scan)
				if tps and len(tps) > self.ATSCTransponders.index:
					tp = tps[self.ATSCTransponders.index]
					self.addATSCTransponder(tlist, tp[1], tp[2], tp[3], tp[4])
				removeAll = False
			elif self.scan_type_atsc.value == "complete":
				getInitialATSCTransponderList(tlist, index_to_scan)

		flags |= self.scan_networkScan.value and eComponentScan.scanNetworkSearch or 0

		tmp = self.scan_clearallservices.value
		if tmp == "yes":
			flags |= eComponentScan.scanRemoveServices
		elif tmp == "yes_hold_feeds":
			flags |= eComponentScan.scanRemoveServices
			flags |= eComponentScan.scanDontRemoveFeeds

		if tmp != "no" and not removeAll:
			flags |= eComponentScan.scanDontRemoveUnscanned

		if self.scan_onlyfree.value:
			flags |= eComponentScan.scanOnlyFree

		for x in self["config"].list:
			x[1].save()

		if action == START_SCAN:
			self.startScan(tlist, flags, index_to_scan, self.networkid)
		elif action == SEARCH_CABLE_TRANSPONDERS:
			self.flags = flags
			self.feid = index_to_scan
			self.startCableTransponderSearch(self.feid)
		elif action == SEARCH_TERRESTRIAL2_TRANSPONDERS:
			self.flags = flags
			self.feid = index_to_scan
			self.startTerrestrialTransponderSearch(self.feid, nimmanager.getTerrestrialDescription(self.feid))

	def setCableTransponderSearchResult(self, tlist):
		self.tlist = tlist

	def cableTransponderSearchFinished(self):
		if self.tlist is None:
			self.tlist = []
		else:
			self.startScan(self.tlist, self.flags, self.feid)

	def setTerrestrialTransponderSearchResult(self, tlist):
		self.tlist = tlist

	def terrestrialTransponderSearchFinished(self):
		if self.tlist is None:
			self.tlist = []
		else:
			self.startScan(self.tlist, self.flags, self.feid)

	def predefinedTranspondersList(self, orbpos):
		default = None
		if orbpos is not None:
			list = []
			if self.scan_sat.system.value == eDVBFrontendParametersSatellite.System_DVB_S2:
				fec = self.scan_sat.fec_s2.value
			else:
				fec = self.scan_sat.fec.value
			compare = [
				0, # DVB type
				self.scan_sat.frequency.value * 1000,  # 1
				self.scan_sat.symbolrate.value * 1000, # 2
				self.scan_sat.polarization.value,    # 3
				fec,                                 # 4
				self.scan_sat.system.value,          # 5
				self.scan_sat.modulation.value,      # 6
				self.scan_sat.inversion.value,       # 7
				self.scan_sat.rolloff.value,         # 8
				self.scan_sat.pilot.value,           # 9
				self.scan_sat.is_id.value,           # 10
				self.scan_sat.pls_mode.value,        # 11
				self.scan_sat.pls_code.value,        # 12
				self.scan_sat.t2mi_plp_id.value,     # 13
				self.scan_sat.t2mi_pid.value         # 14
				# tsid
				# onid
			]
			i = 0
			tps = nimmanager.getTransponders(orbpos, int(self.scan_nims.value))
			for tp in tps:
				if tp[0] == 0:
					if default is None and self.compareTransponders(tp, compare):
						default = str(i)
					list.append((str(i), self.humanReadableTransponder(tp)))
					i += 1
			self.preDefTransponders = ConfigSelection(choices=list, default=default)
		return default

	def humanReadableTransponder(self, tp):
		if tp[3] in list(range(4)) and tp[4] in list(range(11)):
			pol_list = ['H', 'V', 'L', 'R']
			fec_list = ['Auto', '1/2', '2/3', '3/4', '5/6', '7/8', '8/9', '3/5', '4/5', '9/10', 'None']
			tp_text = str(tp[1] // 1000) + " " + pol_list[tp[3]] + " " + str(tp[2] // 1000) + " " + fec_list[tp[4]]
			if tp[5] == eDVBFrontendParametersSatellite.System_DVB_S2:
				if tp[10] > eDVBFrontendParametersSatellite.No_Stream_Id_Filter:
					tp_text = ("%s MIS %d") % (tp_text, tp[10])
				if tp[12] > 0:
					tp_text = ("%s Gold %d") % (tp_text, tp[12])
				if tp[13] > eDVBFrontendParametersSatellite.No_T2MI_PLP_Id:
					tp_text = ("%s T2MI %d PID %d") % (tp_text, tp[13], tp[14])
			return tp_text
		return _("Invalid transponder data")

	def compareTransponders(self, tp, compare):
		frequencyTolerance = 2000 #2 MHz
		symbolRateTolerance = 10
		return abs(tp[1] - compare[1]) <= frequencyTolerance and abs(tp[2] - compare[2]) <= symbolRateTolerance and tp[3] == compare[3] and (not tp[4] or tp[4] == compare[4]) and (tp[5] == eDVBFrontendParametersSatellite.System_DVB_S or (tp[10] == eDVBFrontendParametersSatellite.No_Stream_Id_Filter or tp[10] == compare[10]) and tp[13] == compare[13])

	def predefinedTerrTranspondersList(self):
		default = None
		list = []
		compare = [2, self.scan_ter.frequency.value * 1000]
		i = 0
		index_to_scan = int(self.scan_nims.value)
		channels = supportedChannels(index_to_scan)
		terrestrialRegion = nimmanager.nim_slots[index_to_scan].config.terrestrial
		region = terrestrialRegion.description[terrestrialRegion.value]
		tps = nimmanager.getTranspondersTerrestrial(region)
		for tp in tps:
			if tp[0] == 2: #TERRESTRIAL
				channel = ''
				if channels:
					channel = _(' (Channel %s)') % (getChannelNumber(tp[1], index_to_scan))
				if default is None and self.compareTerrTransponders(tp, compare):
					default = str(i)
				list.append((str(i), '%s MHz %s' % (str(tp[1] // 1000000), channel)))
				i += 1
				print("[ScanSetup] channel", channel)
		self.TerrestrialTransponders = ConfigSelection(choices=list, default=default)
		return default

	def compareTerrTransponders(self, tp, compare):
		frequencyTolerance = 1000000 #1 MHz
		return abs(tp[1] - compare[1]) <= frequencyTolerance

	def getTerrestrialRegionsList(self, index_to_scan=None):
		default = None
		list = []
		if index_to_scan is None:
			index_to_scan = int(self.scan_nims.value)
		defaultRegionForNIM = nimmanager.getTerrestrialDescription(index_to_scan)
		for r in nimmanager.terrestrialsList:
			if default is None and r[0] == defaultRegionForNIM:
				default = r[0]
			list.append((r[0], r[0][:46]))
		return ConfigSelection(choices=list, default=default)

	def predefinedCabTranspondersList(self):
		default = None
		list = []
		# 0 transponder type, 1 freq, 2 sym, 3 mod, 4 fec, 5 inv, 6 sys
		compare = [1, self.scan_cab.frequency.value, self.scan_cab.symbolrate.value * 1000, self.scan_cab.modulation.value, self.scan_cab.fec.value, self.scan_cab.inversion.value, self.scan_cab.system.value]
		i = 0
		index_to_scan = int(self.scan_nims.value)
		tps = nimmanager.getTranspondersCable(index_to_scan)
		for tp in tps:
			if tp[0] == 1: #CABLE
				if default is None and self.compareCabTransponders(tp, compare):
					default = str(i)
				list.append((str(i), self.humanReadableCabTransponder(tp)))
				i += 1
		self.CableTransponders = ConfigSelection(choices=list, default=default)
		return default

	def humanReadableCabTransponder(self, tp):
		if tp[3] in list(range(6)) and (tp[4] in list(range(10) or tp[4] == 15)):
			mod_list = ['Auto', '16-QAM', '32-QAM', '64-QAM', '128-QAM', '256-QAM']
			fec_list = {0: "Auto", 1: '1/2', 2: '2/3', 3: '3/4', 4: '5/6', 5: '7/8', 6: '8/9', 7: '3/5', 8: '4/5', 9: '9/10', 15: 'None'}
			print(str(tp[1] // 1000.) + " MHz " + fec_list[tp[4]] + " " + str(tp[2] // 1000) + " " + mod_list[tp[3]])
			return str(tp[1] // 1000.) + " MHz " + fec_list[tp[4]] + " " + str(tp[2] // 1000) + " " + mod_list[tp[3]]
		return _("Invalid transponder data")

	def compareCabTransponders(self, tp, compare):
		frequencyTolerance = 1000 #1 MHz
		symbolRateTolerance = 10
		return abs(tp[1] - compare[1]) <= frequencyTolerance and abs(tp[2] - compare[2]) <= symbolRateTolerance and tp[3] == compare[3] and (not tp[4] or tp[4] == compare[4])

	def predefinedATSCTranspondersList(self):
		default = None
		list = []
		index_to_scan = int(self.scan_nims.value)
		tps = nimmanager.getTranspondersATSC(index_to_scan)
		for i, tp in enumerate(tps):
			if tp[0] == 3: #ATSC
				list.append((str(i), '%s MHz' % (str(tp[1] // 1000000))))
		self.ATSCTransponders = ConfigSelection(choices=list, default=default)
		return default

	def startScan(self, tlist, flags, feid, networkid=0):
		if len(tlist):
			# flags |= eComponentScan.scanSearchBAT
			if self.finished_cb:
				self.session.openWithCallback(self.finished_cb, ServiceScan, [{"transponders": tlist, "feid": feid, "flags": flags, "networkid": networkid}])
			else:
				self.session.openWithCallback(self.startScanCallback, ServiceScan, [{"transponders": tlist, "feid": feid, "flags": flags, "networkid": networkid}])
		else:
			if self.finished_cb:
				self.session.openWithCallback(self.finished_cb, MessageBox, _("Nothing to scan!\nPlease setup your tuner settings before you start a service scan."), MessageBox.TYPE_ERROR)
			else:
				self.session.open(MessageBox, _("Nothing to scan!\nPlease setup your tuner settings before you start a service scan."), MessageBox.TYPE_ERROR)

	def startScanCallback(self, answer=True):
		if answer:
			self.doCloseRecursive()

	def keyCancel(self):
		self.session.nav.playService(self.session.postScanService)
		for x in self["config"].list:
			x[1].cancel()
		self.close()

	def doCloseRecursive(self):
		self.session.nav.playService(self.session.postScanService)
		self.closeRecursive()


class ScanSimple(ConfigListScreen, Screen, CableTransponderSearchSupport, TerrestrialTransponderSearchSupport):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle(_("Automatic Scan"))
		self.skinName = ["ScanSimple", "Setup"]

		self["key_green"] = StaticText(_("Scan"))

		self["actions"] = ActionMap(["SetupActions"],
		{
			"save": self.keyGo,
		}, -2)

		self.session.postScanService = session.nav.getCurrentlyPlayingServiceOrGroup()

		self.list = []
		tlist = []

		known_networks = []
		nims_to_scan = []
		self.finished_cb = None
		self.t2_nim_found = False

		for nim in nimmanager.nim_slots:
			# collect networks provided by this tuner

			need_scan = False
			networks = self.getNetworksForNim(nim)

			print("[ScanSetup] nim %d provides" % nim.slot, networks)
			print("[ScanSetup] known:", known_networks)

			# we only need to scan on the first tuner which provides a network.
			# this gives the first tuner for each network priority for scanning.
			for x in networks:
				if x not in known_networks:
					need_scan = True
					print("[ScanSetup] %s not in %s" % (x, known_networks))
					known_networks.append(x)

			# don't offer to scan nims if nothing is connected
			if not nimmanager.somethingConnected(nim.slot):
				need_scan = False

			if need_scan:
				nims_to_scan.append(nim)
				if nim.isCompatible("DVB-T2") and SystemInfo["Blindscan_t2_available"] and len(self.terrestrialTransponderGetCmd(nim.slot)):
					self.t2_nim_found = True

		# we save the config elements to use them on keyGo
		self.nim_enable = []

		if len(nims_to_scan):
			self.scan_networkScan = ConfigYesNo(default=True)
			self.scan_clearallservices = ConfigSelection(default="yes", choices=[("no", _("no")), ("yes", _("yes")), ("yes_hold_feeds", _("yes (keep feeds)"))])
			self.list.append(getConfigListEntry(_("Network scan"), self.scan_networkScan))
			self.list.append(getConfigListEntry(_("Clear before scan"), self.scan_clearallservices))

			for nim in nims_to_scan:
				nimconfig = ConfigYesNo(default=True)
				nimconfig.nim_index = nim.slot
				self.nim_enable.append(nimconfig)
				self.list.append(getConfigListEntry(_("Scan ") + nim.slot_name + " (" + nim.friendly_type + ")", nimconfig))

			self.scan_terrestrial_binary_scan = ConfigYesNo(default=False)
			if self.t2_nim_found:
				self.list.append(getConfigListEntry(_("Blindscan terrestrial (if possible)"), self.scan_terrestrial_binary_scan))

		ConfigListScreen.__init__(self, self.list, fullUI=True)

	def getNetworksForNim(self, nim):
		if nim.isCompatible("DVB-S"):
			networks = nimmanager.getSatListForNim(nim.slot)
		elif nim.isCompatible("DVB-C"):
			networks = nimmanager.getTranspondersCable(nim.slot)
			if not networks and config.Nims[nim.slot].configMode.value == "enabled":
				networks = [nim.type]
		elif nim.isCompatible("DVB-T"):
			networks = [nimmanager.getTerrestrialDescription(nim.slot)]
			if not nimmanager.somethingConnected(nim.slot):
				networks = []
		elif not nim.empty:
			networks = [nim.type] # "DVB-C" or "DVB-T". TODO: seperate networks for different C/T tuners, if we want to support that.
		else:
			# empty tuners provide no networks.
			networks = []
		return networks

	def runAsync(self, finished_cb):
		self.finished_cb = finished_cb
		self.keyGo()

	def keyGo(self):
		InfoBarInstance = InfoBar.instance
		if InfoBarInstance:
			InfoBarInstance.checkTimeshiftRunning(self.keyGoCheckTimeshiftCallback)
		else:
			self.keyGoCheckTimeshiftCallback(True)

	def keyGoCheckTimeshiftCallback(self, answer):
		if answer:
			self.scanList = []
			self.known_networks = set()
			self.nim_iter = 0
			self.buildTransponderList()

	def buildTransponderList(self): # this method is called multiple times because of asynchronous stuff
		APPEND_NOW = 0
		SEARCH_CABLE_TRANSPONDERS = 1
		SEARCH_TERRESTRIAL2_TRANSPONDERS = 2
		action = APPEND_NOW

		n = self.nim_iter < len(self.nim_enable) and self.nim_enable[self.nim_iter] or None
		self.nim_iter += 1
		if n:
			if n.value: # check if nim is enabled
				flags = 0
				nim = nimmanager.nim_slots[n.nim_index]
				networks = set(self.getNetworksForNim(nim))
				print("[ScanSetup] [buildTransponderList] networks:%s" % networks)
				networkid = 0

				# don't scan anything twice
				networks.discard(self.known_networks)

				tlist = []
				if nim.isSupported():
					if nim.isCompatible("DVB-S"):
						# get initial transponders for each satellite to be scanned
						for sat in networks:
							getInitialTransponderList(tlist, sat[0], n.nim_index)
					if nim.isCompatible("DVB-C"):
						if config.Nims[nim.slot].cable.scan_type.value == "provider":
							getInitialCableTransponderList(tlist, nim.slot)
						else:
							action = SEARCH_CABLE_TRANSPONDERS
							networkid = config.Nims[nim.slot].cable.scan_networkid.value
					if nim.isCompatible("DVB-T"):
						if SystemInfo["Blindscan_t2_available"] and self.scan_terrestrial_binary_scan.value and nim.isCompatible("DVB-T2") and len(self.terrestrialTransponderGetCmd(nim.slot)):
							action = SEARCH_TERRESTRIAL2_TRANSPONDERS
						else:
							getInitialTerrestrialTransponderList(tlist, nimmanager.getTerrestrialDescription(nim.slot))
					if nim.isCompatible("ATSC"):
						getInitialATSCTransponderList(tlist, nim.slot)
				else:
					assert False

				flags = self.scan_networkScan.value and eComponentScan.scanNetworkSearch or 0
				tmp = self.scan_clearallservices.value
				if tmp == "yes":
					flags |= eComponentScan.scanRemoveServices
				elif tmp == "yes_hold_feeds":
					flags |= eComponentScan.scanRemoveServices
					flags |= eComponentScan.scanDontRemoveFeeds

				if action == APPEND_NOW:
					self.scanList.append({"transponders": tlist, "feid": nim.slot, "flags": flags})
				elif action == SEARCH_CABLE_TRANSPONDERS:
					self.flags = flags
					self.feid = nim.slot
					self.networkid = networkid
					self.startCableTransponderSearch(nim.slot)
					return
				elif action == SEARCH_TERRESTRIAL2_TRANSPONDERS:
					self.flags = flags
					self.feid = nim.slot
					self.startTerrestrialTransponderSearch(nim.slot, nimmanager.getTerrestrialDescription(nim.slot))
					return
				else:
					assert False

			self.buildTransponderList() # recursive call of this function !!!
			return
		# when we are here, then the recursion is finished and all enabled nims are checked
		# so we now start the real transponder scan
		self.startScan(self.scanList)

	def startScan(self, scanList):
		if len(scanList):
			if self.finished_cb:
				self.session.openWithCallback(self.finished_cb, ServiceScan, scanList=scanList)
			else:
				self.session.open(ServiceScan, scanList=scanList)
		else:
			if self.finished_cb:
				self.session.openWithCallback(self.finished_cb, MessageBox, _("Nothing to scan!\nPlease setup your tuner settings before you start a service scan."), MessageBox.TYPE_ERROR)
			else:
				self.session.open(MessageBox, _("Nothing to scan!\nPlease setup your tuner settings before you start a service scan."), MessageBox.TYPE_ERROR)

	def setCableTransponderSearchResult(self, tlist):
		if tlist is not None:
			self.scanList.append({"transponders": tlist, "feid": self.feid, "flags": self.flags})

	def cableTransponderSearchFinished(self):
		self.buildTransponderList()

	def setTerrestrialTransponderSearchResult(self, tlist):
		if tlist is not None:
			self.scanList.append({"transponders": tlist, "feid": self.feid, "flags": self.flags})

	def terrestrialTransponderSearchFinished(self):
		self.buildTransponderList()

	def keyCancel(self):
		self.session.nav.playService(self.session.postScanService)
		self.close()

	def doCloseRecursive(self):
		self.session.nav.playService(self.session.postScanService)
		self.closeRecursive()

	def Satexists(self, tlist, pos):
		for x in tlist:
			if x == pos:
				return 1
		return 0
