import codecs
import re

from Components.config import config, configfile
from Components.NimManager import nimmanager

from Screens.ChannelSelection import ChannelSelection
from Screens.MessageBox import MessageBox

from Tools import Notifications

# from this plugin
from .providers import providers

from enigma import eDVBDB, eServiceReference, eTimer, eDVBFrontendParametersSatellite

from time import localtime, time, strftime, mktime


# for pip
from Screens.PictureInPicture import PictureInPicture
from Components.SystemInfo import SystemInfo
from enigma import ePoint, eSize

debug_name = "opentv_zapper"
lamedb_path = "/etc/enigma2"
download_interval = config.plugins.opentvzapper.update_interval.value * 60 * 60  # 6 hours
download_duration = 3 * 60  # stay tuned for 3 minutes
start_first_download = 5 * 60  # 5 minutes after booting
wait_time_on_fail = 15 * 60  # 15 minutes


def getNimListForSat(orb_pos):
	return [nim.slot for nim in nimmanager.nim_slots if nim.isCompatible("DVB-S") and orb_pos in [sat[0] for sat in nimmanager.getSatListForNim(nim.slot)]]


def make_sref(service):
	return eServiceReference("1:0:%X:%X:%X:%X:%X:0:0:0:" % (
		service["service_type"],
		service["service_id"],
		service["transport_stream_id"],
		service["original_network_id"],
		service["namespace"]))


class DefaultAdapter:
	def __init__(self, session):
		self.navcore = session.nav
		self.previousService = None
		self.currentService = ""
		self.currentBouquet = None

	def play(self, service):
		self.currentBouquet = ChannelSelection.instance is not None and ChannelSelection.instance.getRoot()
		self.previousService = self.navcore.getCurrentlyPlayingServiceReference()
		self.navcore.playService(service)
		self.currentService = self.navcore.getCurrentlyPlayingServiceReference()
		return True

	def stop(self):
		if self.currentService == (self.navcore and self.navcore.getCurrentlyPlayingServiceReference()):  # check the user hasn't zapped in the mean time
			if self.currentBouquet is not None:
				ChannelSelection.instance.setRoot(self.currentBouquet)
			self.navcore.playService(self.previousService)


class RecordAdapter:
	def __init__(self, session):
		self.__service = None
		self.navcore = session.nav

	def play(self, service):
		self.stop()
		self.__service = self.navcore.recordService(service)
		if self.__service is not None:
			self.__service.prepareStreaming()
			self.__service.start()
			return True
		return False

	def stop(self):
		if self.__service is not None:
			self.navcore.stopRecordService(self.__service)
			self.__service = None


class PipAdapter:
	def __init__(self, session, hide=True):
		self.hide = hide
		self.session = session

	def __hidePiP(self):
		# set pip size to 1 pixel
		x = y = 0
		w = 1
		self.session.pip.instance.move(ePoint(x, y))
		self.session.pip.instance.resize(eSize(w, y))
		self.session.pip["video"].instance.resize(eSize(w, y))

	def __initPiP(self):
		self.session.pip = self.session.instantiateDialog(PictureInPicture)
		self.session.pip.show()
		if self.hide:
			self.__hidePiP()
		self.session.pipshown = True  # Always pretends it's shown (since the ressources are present)
		newservice = self.session.nav.getCurrentlyPlayingServiceReference()
		if self.session.pip.playService(newservice):
			self.session.pip.servicePath = newservice.getPath()

	def play(self, service):
		self.__initPiP()

		if self.session.pip.playService(service):
			self.session.pip.servicePath = service.getPath()
			return True
		return False

	def stop(self):
		try:
			del self.session.pip
		except Exception:
			pass
		self.session.pipshown = False


class LamedbReader():
	def readLamedb(self, path):
		# print("[%s-LamedbReader] Reading lamedb..." % (debug_name))

		transponders = {}

		try:
			lamedb = open(path + "/lamedb", "r")
		except Exception:
			return transponders

		content = lamedb.read()
		lamedb.close()

		lamedb_ver = 4
		result = re.match('eDVB services /([45])/', content)
		if result:
			lamedb_ver = int(result.group(1))
			# print("[%s-LamedbReader] lamedb ver" % (debug_name), lamedb_ver)
		if lamedb_ver == 4:
			transponders = self.parseLamedbV4Content(content)
		elif lamedb_ver == 5:
			transponders = self.parseLamedbV5Content(content)
		return transponders

	def parseLamedbV4Content(self, content):
		transponders = {}
		transponders_count = 0
		services_count = 0

		tp_start = content.find("transponders\n")
		tp_stop = content.find("end\n")

		tp_blocks = content[tp_start + 13:tp_stop].strip().split("/")
		content = content[tp_stop + 4:]

		for block in tp_blocks:
			rows = block.strip().split("\n")
			if len(rows) != 2:
				continue

			first_row = rows[0].strip().split(":")
			if len(first_row) != 3:
				continue

			transponder = {}
			transponder["services"] = {}
			transponder["namespace"] = int(first_row[0], 16)
			transponder["transport_stream_id"] = int(first_row[1], 16)
			transponder["original_network_id"] = int(first_row[2], 16)

			# print("%x:%x:%x" % (namespace, transport_stream_id, original_network_id))
			second_row = rows[1].strip()
			transponder["dvb_type"] = 'dvb' + second_row[0]
			if transponder["dvb_type"] not in ["dvbs", "dvbt", "dvbc"]:
				continue

			second_row = second_row[2:].split(":")

			if transponder["dvb_type"] == "dvbs" and len(second_row) not in (7, 11, 14, 16):
				continue
			if transponder["dvb_type"] == "dvbt" and len(second_row) != 12:
				continue
			if transponder["dvb_type"] == "dvbc" and len(second_row) != 7:
				continue

			if transponder["dvb_type"] == "dvbs":
				transponder["frequency"] = int(second_row[0])
				transponder["symbol_rate"] = int(second_row[1])
				transponder["polarization"] = int(second_row[2])
				transponder["fec_inner"] = int(second_row[3])
				orbital_position = int(second_row[4])
				if orbital_position < 0:
					transponder["orbital_position"] = orbital_position + 3600
				else:
					transponder["orbital_position"] = orbital_position

				transponder["inversion"] = int(second_row[5])
				transponder["flags"] = int(second_row[6])
				if len(second_row) == 7:  # DVB-S
					transponder["system"] = 0
				else:  # DVB-S2
					transponder["system"] = int(second_row[7])
					transponder["modulation"] = int(second_row[8])
					transponder["roll_off"] = int(second_row[9])
					transponder["pilot"] = int(second_row[10])
					if len(second_row) > 13:  # Multistream
						transponder["is_id"] = int(second_row[11])
						transponder["pls_code"] = int(second_row[12])
						transponder["pls_mode"] = int(second_row[13])
						if len(second_row) > 15:  # T2MI
							transponder["t2mi_plp_id"] = int(second_row[14])
							transponder["t2mi_pid"] = int(second_row[15])
			elif transponder["dvb_type"] == "dvbt":
				transponder["frequency"] = int(second_row[0])
				transponder["bandwidth"] = int(second_row[1])
				transponder["code_rate_hp"] = int(second_row[2])
				transponder["code_rate_lp"] = int(second_row[3])
				transponder["modulation"] = int(second_row[4])
				transponder["transmission_mode"] = int(second_row[5])
				transponder["guard_interval"] = int(second_row[6])
				transponder["hierarchy"] = int(second_row[7])
				transponder["inversion"] = int(second_row[8])
				transponder["flags"] = int(second_row[9])
				transponder["system"] = int(second_row[10])
				transponder["plpid"] = int(second_row[11])
			elif transponder["dvb_type"] == "dvbc":
				transponder["frequency"] = int(second_row[0])
				transponder["symbol_rate"] = int(second_row[1])
				transponder["inversion"] = int(second_row[2])
				transponder["modulation"] = int(second_row[3])
				transponder["fec_inner"] = int(second_row[4])
				transponder["flags"] = int(second_row[5])
				transponder["system"] = int(second_row[6])

			key = "%x:%x:%x" % (transponder["namespace"], transponder["transport_stream_id"], transponder["original_network_id"])
			transponders[key] = transponder
			transponders_count += 1

		srv_start = content.find("services\n")
		srv_stop = content.rfind("end\n")

		srv_blocks = content[srv_start + 9:srv_stop].strip().split("\n")

		for i in range(0, len(srv_blocks) // 3):
			service_reference = srv_blocks[i * 3].strip()
			service_name = srv_blocks[(i * 3) + 1].strip()
			service_provider = srv_blocks[(i * 3) + 2].strip()
			service_reference = service_reference.split(":")

			if len(service_reference) not in (6, 7):
				continue

			service = {}
			service["service_name"] = service_name
			service["service_line"] = service_provider
			service["service_id"] = int(service_reference[0], 16)
			service["namespace"] = int(service_reference[1], 16)
			service["transport_stream_id"] = int(service_reference[2], 16)
			service["original_network_id"] = int(service_reference[3], 16)
			service["service_type"] = int(service_reference[4])
			service["flags"] = int(service_reference[5])
			if len(service_reference) == 7 and int(service_reference[6], 16) != 0:
				service["ATSC_source_id"] = int(service_reference[6], 16)

			key = "%x:%x:%x" % (service["namespace"], service["transport_stream_id"], service["original_network_id"])
			if key not in transponders:
				continue

			# The original (correct) code
			# transponders[key]["services"][service["service_id"]] = service

			# Dirty hack to work around the (well known) service type bug in lamedb/enigma2
			transponders[key]["services"]["%x:%x" % (service["service_type"], service["service_id"])] = service

			services_count += 1

		# print("[%s-LamedbReader] Read %d transponders and %d services" % (debug_name, transponders_count, services_count))
		return transponders

	def parseLamedbV5Content(self, content):
		transponders = {}
		transponders_count = 0
		services_count = 0

		lines = content.splitlines()
		for line in lines:
			if line.startswith("t:"):
				first_part = line.strip().split(",")[0][2:].split(":")
				if len(first_part) != 3:
					continue

				transponder = {}
				transponder["services"] = {}
				transponder["namespace"] = int(first_part[0], 16)
				transponder["transport_stream_id"] = int(first_part[1], 16)
				transponder["original_network_id"] = int(first_part[2], 16)

				second_part = line.strip().split(",")[1]
				transponder["dvb_type"] = 'dvb' + second_part[0]
				if transponder["dvb_type"] not in ["dvbs", "dvbt", "dvbc"]:
					continue

				second_part = second_part[2:].split(":")

				if transponder["dvb_type"] == "dvbs" and len(second_part) not in (7, 11):
					continue
				if transponder["dvb_type"] == "dvbt" and len(second_part) != 12:
					continue
				if transponder["dvb_type"] == "dvbc" and len(second_part) != 7:
					continue

				if transponder["dvb_type"] == "dvbs":
					transponder["frequency"] = int(second_part[0])
					transponder["symbol_rate"] = int(second_part[1])
					transponder["polarization"] = int(second_part[2])
					transponder["fec_inner"] = int(second_part[3])
					orbital_position = int(second_part[4])
					if orbital_position < 0:
						transponder["orbital_position"] = orbital_position + 3600
					else:
						transponder["orbital_position"] = orbital_position

					transponder["inversion"] = int(second_part[5])
					transponder["flags"] = int(second_part[6])
					if len(second_part) == 7:  # DVB-S
						transponder["system"] = 0
					else:  # DVB-S2
						transponder["system"] = int(second_part[7])
						transponder["modulation"] = int(second_part[8])
						transponder["roll_off"] = int(second_part[9])
						transponder["pilot"] = int(second_part[10])
						for part in line.strip().split(",")[2:]:  # Multistream/T2MI
							if part.startswith("MIS/PLS:") and len(part[8:].split(":")) == 3:
								transponder["is_id"] = int(part[8:].split(":")[0])
								transponder["pls_code"] = int(part[8:].split(":")[1])
								transponder["pls_mode"] = int(part[8:].split(":")[2])
							elif part.startswith("T2MI:") and len(part[5:].split(":")) == 2:
								transponder["t2mi_plp_id"] = int(part[5:].split(":")[0])
								transponder["t2mi_pid"] = int(part[5:].split(":")[1])
				elif transponder["dvb_type"] == "dvbt":
					transponder["frequency"] = int(second_part[0])
					transponder["bandwidth"] = int(second_part[1])
					transponder["code_rate_hp"] = int(second_part[2])
					transponder["code_rate_lp"] = int(second_part[3])
					transponder["modulation"] = int(second_part[4])
					transponder["transmission_mode"] = int(second_part[5])
					transponder["guard_interval"] = int(second_part[6])
					transponder["hierarchy"] = int(second_part[7])
					transponder["inversion"] = int(second_part[8])
					transponder["flags"] = int(second_part[9])
					transponder["system"] = int(second_part[10])
					transponder["plpid"] = int(second_part[11])
				elif transponder["dvb_type"] == "dvbc":
					transponder["frequency"] = int(second_part[0])
					transponder["symbol_rate"] = int(second_part[1])
					transponder["inversion"] = int(second_part[2])
					transponder["modulation"] = int(second_part[3])
					transponder["fec_inner"] = int(second_part[4])
					transponder["flags"] = int(second_part[5])
					transponder["system"] = int(second_part[6])

				key = "%x:%x:%x" % (transponder["namespace"], transponder["transport_stream_id"], transponder["original_network_id"])
				transponders[key] = transponder
				transponders_count += 1
			elif line.startswith("s:"):
				service_reference = line.strip().split(",")[0][2:]
				service_name = line.strip().split('"', 1)[1].split('"')[0]
				third_part = line.strip().split('"', 2)[2]
				service_provider = ""
				if len(third_part):
					service_provider = third_part[1:]
				service_reference = service_reference.split(":")
				if len(service_reference) != 6 and len(service_reference) != 7:
					continue

				service = {}
				service["service_name"] = service_name
				service["service_line"] = service_provider
				service["service_id"] = int(service_reference[0], 16)
				service["namespace"] = int(service_reference[1], 16)
				service["transport_stream_id"] = int(service_reference[2], 16)
				service["original_network_id"] = int(service_reference[3], 16)
				service["service_type"] = int(service_reference[4])
				service["flags"] = int(service_reference[5])
				if len(service_reference) == 7 and int(service_reference[6], 16) != 0:
					service["ATSC_source_id"] = int(service_reference[6], 16)

				key = "%x:%x:%x" % (service["namespace"], service["transport_stream_id"], service["original_network_id"])
				if key not in transponders:
					continue

				# The original (correct) code
				# transponders[key]["services"][service["service_id"]] = service

				# Dirty hack to work around the (well known) service type bug in lamedb/enigma2
				transponders[key]["services"]["%x:%x" % (service["service_type"], service["service_id"])] = service

				services_count += 1

		# print("[%s-LamedbReader] Read %d transponders and %d services" % (debug_name, transponders_count, services_count))
		return transponders


class LamedbWriter():
	def writeLamedb(self, path, transponders, filename="lamedb"):
		# print("[%s-LamedbWriter] Writing lamedb..." % (debug_name))

		transponders_count = 0
		services_count = 0

		lamedblist = []
		lamedblist.append("eDVB services /4/\n")
		lamedblist.append("transponders\n")

		for key in transponders.keys():
			transponder = transponders[key]
			if "services" not in transponder.keys() or len(transponder["services"]) < 1:
				continue
			lamedblist.append("%08x:%04x:%04x\n" %
				(transponder["namespace"],
				transponder["transport_stream_id"],
				transponder["original_network_id"]))

			if transponder["dvb_type"] == "dvbs":
				if transponder["orbital_position"] > 1800:
					orbital_position = transponder["orbital_position"] - 3600
				else:
					orbital_position = transponder["orbital_position"]

				if transponder["system"] == 0:  # DVB-S
					lamedblist.append("\ts %d:%d:%d:%d:%d:%d:%d\n" %
						(transponder["frequency"],
						transponder["symbol_rate"],
						transponder["polarization"],
						transponder["fec_inner"],
						orbital_position,
						transponder["inversion"],
						transponder["flags"]))
				else:  # DVB-S2
					multistream = ''
					t2mi = ''
					if "t2mi_plp_id" in transponder and "t2mi_pid" in transponder:
						t2mi = ':%d:%d' % (
							transponder["t2mi_plp_id"],
							transponder["t2mi_pid"])
					if "is_id" in transponder and "pls_code" in transponder and "pls_mode" in transponder:
						multistream = ':%d:%d:%d' % (
							transponder["is_id"],
							transponder["pls_code"],
							transponder["pls_mode"])
					if t2mi and not multistream:  # this is to pad t2mi values if necessary.
						try:  # some images are still not multistream aware after all this time
							multistream = ':%d:%d:%d' % (
								eDVBFrontendParametersSatellite.No_Stream_Id_Filter,
								eDVBFrontendParametersSatellite.PLS_Gold,
								eDVBFrontendParametersSatellite.PLS_Default_Gold_Code)
						except AttributeError:
							pass
						lamedblist.append("\ts %d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d%s%s\n" %
						(transponder["frequency"],
						transponder["symbol_rate"],
						transponder["polarization"],
						transponder["fec_inner"],
						orbital_position,
						transponder["inversion"],
						transponder["flags"],
						transponder["system"],
						transponder["modulation"],
						transponder["roll_off"],
						transponder["pilot"],
						multistream,
						t2mi))
			elif transponder["dvb_type"] == "dvbt":
				lamedblist.append("\tt %d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d\n" %
					(transponder["frequency"],
					transponder["bandwidth"],
					transponder["code_rate_hp"],
					transponder["code_rate_lp"],
					transponder["modulation"],
					transponder["transmission_mode"],
					transponder["guard_interval"],
					transponder["hierarchy"],
					transponder["inversion"],
					transponder["flags"],
					transponder["system"],
					transponder["plpid"]))
			elif transponder["dvb_type"] == "dvbc":
				lamedblist.append("\tc %d:%d:%d:%d:%d:%d:%d\n" %
					(transponder["frequency"],
					transponder["symbol_rate"],
					transponder["inversion"],
					transponder["modulation"],
					transponder["fec_inner"],
					transponder["flags"],
					transponder["system"]))
			lamedblist.append("/\n")
			transponders_count += 1

		lamedblist.append("end\nservices\n")
		for key in transponders.keys():
			transponder = transponders[key]
			if "services" not in transponder.keys():
				continue

			for key2 in transponder["services"].keys():
				service = transponder["services"][key2]

				lamedblist.append("%04x:%08x:%04x:%04x:%d:%d%s\n" %
					(service["service_id"],
					service["namespace"],
					service["transport_stream_id"],
					service["original_network_id"],
					service["service_type"],
					service["flags"],
					":%x" % service["ATSC_source_id"] if "ATSC_source_id" in service else ""))

				control_chars = ''.join(list(map(chr, list(range(0, 32)) + list(range(127, 160)))))
				control_char_re = re.compile('[%s]' % re.escape(control_chars))
				if 'provider_name' in service.keys():
					service_name = control_char_re.sub('', service["service_name"])
					provider_name = control_char_re.sub('', service["provider_name"])
				else:
					service_name = service["service_name"]

				lamedblist.append("%s\n" % service_name)

				service_ca = ""
				if "free_ca" in service.keys() and service["free_ca"] != 0:
					service_ca = ",C:0000"

				service_flags = ""
				if "service_flags" in service.keys() and service["service_flags"] > 0:
					service_flags = ",f:%x" % service["service_flags"]

				if 'service_line' in service.keys():
					lamedblist.append("%s\n" % service["service_line"])
				else:
					lamedblist.append("p:%s%s%s\n" % (provider_name, service_ca, service_flags))
				services_count += 1

		lamedblist.append("end\nHave a lot of bugs!\n")
		lamedb = codecs.open(path + "/" + filename, "w", encoding="utf-8", errors="ignore")
		lamedb.write(''.join(lamedblist))
		lamedb.close()
		del lamedblist

		# print("[%s-LamedbWriter] Wrote %d transponders and %d services" % (debug_name, transponders_count, services_count))

	def writeLamedb5(self, path, transponders, filename="lamedb5"):
		# print("[%s-LamedbWriter] Writing lamedb V5..." % (debug_name))

		transponders_count = 0
		services_count = 0

		lamedblist = []
		lamedblist.append("eDVB services /5/\n")
		lamedblist.append("# Transponders: t:dvb_namespace:transport_stream_id:original_network_id,FEPARMS\n")
		lamedblist.append("#     DVBS  FEPARMS:   s:frequency:symbol_rate:polarisation:fec:orbital_position:inversion:flags\n")
		lamedblist.append("#     DVBS2 FEPARMS:   s:frequency:symbol_rate:polarisation:fec:orbital_position:inversion:flags:system:modulation:rolloff:pilot[,MIS/PLS:is_id:pls_code:pls_mode][,T2MI:t2mi_plp_id:t2mi_pid]\n")
		lamedblist.append("#     DVBT  FEPARMS:   t:frequency:bandwidth:code_rate_HP:code_rate_LP:modulation:transmission_mode:guard_interval:hierarchy:inversion:flags:system:plp_id\n")
		lamedblist.append("#     DVBC  FEPARMS:   c:frequency:symbol_rate:inversion:modulation:fec_inner:flags:system\n")
		lamedblist.append('# Services: s:service_id:dvb_namespace:transport_stream_id:original_network_id:service_type:service_number:source_id,"service_name"[,p:provider_name][,c:cached_pid]*[,C:cached_capid]*[,f:flags]\n')

		for key in transponders.keys():
			transponder = transponders[key]
			if "services" not in transponder.keys() or len(transponder["services"]) < 1:
				continue
			lamedblist.append("t:%08x:%04x:%04x," %
				(transponder["namespace"],
				transponder["transport_stream_id"],
				transponder["original_network_id"]))

			if transponder["dvb_type"] == "dvbs":
				if transponder["orbital_position"] > 1800:
					orbital_position = transponder["orbital_position"] - 3600
				else:
					orbital_position = transponder["orbital_position"]

				if transponder["system"] == 0:  # DVB-S
					lamedblist.append("s:%d:%d:%d:%d:%d:%d:%d\n" %
						(transponder["frequency"],
						transponder["symbol_rate"],
						transponder["polarization"],
						transponder["fec_inner"],
						orbital_position,
						transponder["inversion"],
						transponder["flags"]))
				else:  # DVB-S2
					multistream = ''
					t2mi = ''
					if "is_id" in transponder and "pls_code" in transponder and "pls_mode" in transponder:
						try:  # some images are still not multistream aware after all this time
							# don't write default values
							if not (transponder["is_id"] == eDVBFrontendParametersSatellite.No_Stream_Id_Filter and transponder["pls_code"] == eDVBFrontendParametersSatellite.PLS_Gold and transponder["pls_mode"] == eDVBFrontendParametersSatellite.PLS_Default_Gold_Code):
								multistream = ',MIS/PLS:%d:%d:%d' % (
									transponder["is_id"],
									transponder["pls_code"],
									transponder["pls_mode"])
						except AttributeError:
							pass
					if "t2mi_plp_id" in transponder and "t2mi_pid" in transponder:
						t2mi = ',T2MI:%d:%d' % (
							transponder["t2mi_plp_id"],
							transponder["t2mi_pid"])
					lamedblist.append("s:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d%s%s\n" %
						(transponder["frequency"],
						transponder["symbol_rate"],
						transponder["polarization"],
						transponder["fec_inner"],
						orbital_position,
						transponder["inversion"],
						transponder["flags"],
						transponder["system"],
						transponder["modulation"],
						transponder["roll_off"],
						transponder["pilot"],
						multistream,
						t2mi))
			elif transponder["dvb_type"] == "dvbt":
				lamedblist.append("t:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d\n" %
					(transponder["frequency"],
					transponder["bandwidth"],
					transponder["code_rate_hp"],
					transponder["code_rate_lp"],
					transponder["modulation"],
					transponder["transmission_mode"],
					transponder["guard_interval"],
					transponder["hierarchy"],
					transponder["inversion"],
					transponder["flags"],
					transponder["system"],
					transponder["plpid"]))
			elif transponder["dvb_type"] == "dvbc":
				lamedblist.append("c:%d:%d:%d:%d:%d:%d:%d\n" %
					(transponder["frequency"],
					transponder["symbol_rate"],
					transponder["inversion"],
					transponder["modulation"],
					transponder["fec_inner"],
					transponder["flags"],
					transponder["system"]))
			transponders_count += 1

		for key in transponders.keys():
			transponder = transponders[key]
			if "services" not in transponder.keys():
				continue

			for key2 in transponder["services"].keys():
				service = transponder["services"][key2]

				lamedblist.append("s:%04x:%08x:%04x:%04x:%d:%d%s," %
					(service["service_id"],
					service["namespace"],
					service["transport_stream_id"],
					service["original_network_id"],
					service["service_type"],
					service["flags"],
					":%x" % service["ATSC_source_id"] if "ATSC_source_id" in service else ":0"))

				control_chars = ''.join(list(map(chr, list(range(0, 32)) + list(range(127, 160)))))
				control_char_re = re.compile('[%s]' % re.escape(control_chars))
				if 'provider_name' in service.keys():
					service_name = control_char_re.sub('', service["service_name"])
					provider_name = control_char_re.sub('', service["provider_name"])
				else:
					service_name = service["service_name"]

				lamedblist.append('"%s"' % service_name)

				service_ca = ""
				if "free_ca" in service.keys() and service["free_ca"] != 0:
					service_ca = ",C:0000"

				service_flags = ""
				if "service_flags" in service.keys() and service["service_flags"] > 0:
					service_flags = ",f:%x" % service["service_flags"]

				if 'service_line' in service.keys():  # from lamedb
					if len(service["service_line"]):
						lamedblist.append(",%s\n" % service["service_line"])
					else:
						lamedblist.append("\n")
				else:  # from scanner
					lamedblist.append(",p:%s%s%s\n" % (provider_name, service_ca, service_flags))
				services_count += 1

		lamedb = codecs.open(path + "/" + filename, "w", encoding="utf-8", errors="ignore")
		lamedb.write(''.join(lamedblist))
		lamedb.close()
		del lamedblist

		# print("[%s-LamedbWriter] Wrote %d transponders and %d services" % (debug_name, transponders_count, services_count))


class Opentv_Zapper():
	def __init__(self):
		self.session = None
		self.adapter = None
		self.downloading = False
		self.force = False
		self.initialized = False
		self.callback = None
		self.downloadtimer = eTimer()
		self.downloadtimer.callback.append(self.start_download)
		self.enddownloadtimer = eTimer()
		self.enddownloadtimer.callback.append(self.stop_download)
		print("[%s] starting..." % (debug_name))
		if config.plugins.opentvzapper.enabled.value and not config.plugins.opentvzapper.schedule.value:  # auto interval, not schedule
			print("[%s] first download scheduled for %s" % (debug_name, strftime("%c", localtime(int(time()) + start_first_download))))
			self.downloadtimer.startLongTimer(start_first_download)

	def checkAvailableTuners(self):
		provider = config.plugins.opentvzapper.providers.value
		self.transponder = providers[provider]["transponder"]
		self.tuners = getNimListForSat(self.transponder["orbital_position"])
		self.num_tuners = len(self.tuners)
		return bool(self.num_tuners)

	def initialize(self):
		provider = config.plugins.opentvzapper.providers.value
		if not self.checkAvailableTuners() or self.initialized == provider:  # if no tuner is available for this provider or we are already initialized, abort.
			return
		self.service = providers[provider]["service"]
		self.sref = make_sref(self.service)
		transponder_key = "%x:%x:%x" % (self.transponder["namespace"], self.transponder["transport_stream_id"], self.transponder["original_network_id"])
		service_key = "%x:%x" % (self.service["service_type"], self.service["service_id"])
		transponders = LamedbReader().readLamedb(lamedb_path)
		if transponder_key not in transponders:
			transponders[transponder_key] = self.transponder
		if service_key not in transponders[transponder_key]["services"]:
			transponders[transponder_key]["services"][service_key] = self.service
			print("[%s] download service missing from lamedb. Adding now." % (debug_name))
			writer = LamedbWriter()
			writer.writeLamedb(lamedb_path, transponders)
			writer.writeLamedb5(lamedb_path, transponders)
			eDVBDB.getInstance().reloadServicelist()
		self.initialized = provider
		print("[%s] initialize completed." % (debug_name))

	def config_changed(self, configElement=None):
		print("[%s] config_changed." % (debug_name))
		if config.plugins.opentvzapper.enabled.value and not config.plugins.opentvzapper.schedule.value:  # auto interval, not schedule
			self.start_download()
		else:
			print("[%s] auto download timer stopped." % (debug_name))
			self.downloadtimer.stop()

	def set_session(self, session):
		self.session = session

	def force_download(self, callback=None):
		if self.checkAvailableTuners():
			if callback:
				self.callback = callback
			print("[%s] forced download." % (debug_name))
			self.force = True
			self.start_download()
		else:
			print("[%s] no tuner configured for %s." % (debug_name, config.plugins.opentvzapper.providers.value))
			if callback:
				callback()

	def start_download(self):
		print("[%s] start_download." % (debug_name))
		self.downloadtimer.stop()  # stop any running timer. e.g. we could be coming from "force_download" or "config_changed".
		from Screens.Standby import inStandby

		# this is here so tuner setup is fresh for every download
		self.initialize()

		self.adaptername = ""
		if self.session and self.num_tuners and not self.downloading and not self.session.nav.RecordTimer.isRecording():
			self.adapter = None
			self.downloading = False
			currentlyPlayingNIM = self.getCurrentlyPlayingNIM()
			print("[%s]currentlyPlayingNIM" % (debug_name), currentlyPlayingNIM)
			print("[%s]available tuners" % (debug_name), self.tuners)
			if not inStandby and (self.num_tuners > 1 or self.tuners[0] != currentlyPlayingNIM):
				if SystemInfo.get("PIPAvailable", False) and config.plugins.opentvzapper.use_pip_adapter.value and not (hasattr(self.session, 'pipshown') and self.session.pipshown):
					self.adapter = PipAdapter(self.session)
					self.downloading = self.adapter.play(self.sref)
					self.adaptername = "Pip"
				else:
					self.adapter = RecordAdapter(self.session)
					self.downloading = self.adapter.play(self.sref)
					self.adaptername = "Record"
			if not self.downloading and (inStandby or self.force):
				self.adapter = DefaultAdapter(self.session)
				self.downloading = self.adapter.play(self.sref)
				self.adaptername = "Default"
		self.force = False
		if self.downloading:
			self.enddownloadtimer.startLongTimer(download_duration)
			print("[%s]download running..." % (debug_name))
			print("[%s] %s" % (debug_name, "using '%s' adapter" % self.adaptername if self.adaptername else "a download is already in progress"))
			if not inStandby and config.plugins.opentvzapper.notifications.value:
				Notifications.AddPopup(text=_("OpenTV EPG download starting."), type=MessageBox.TYPE_INFO, timeout=5, id=debug_name)
		else:
			self.downloadtimer.startLongTimer(wait_time_on_fail)  # download not possible at this time. Try again in 10 minutes
			print("[%s]download not currently possible... Will try again at %s" % (debug_name, strftime("%c", localtime(int(time()) + wait_time_on_fail))))

	def stop_download(self):
		from Screens.Standby import inStandby
		if self.adapter:
			self.adapter.stop()
			del self.adapter
		self.downloading = False
		self.adapter = None
		if not config.plugins.opentvzapper.schedule.value:  # auto interval, not schedule
			self.downloadtimer.startLongTimer(download_interval)
			next_download = strftime("%c", localtime(int(time()) + download_interval))
			print("[%s]download completed... Next download scheduled for %s" % (debug_name, next_download))
			if not inStandby and config.plugins.opentvzapper.notifications.value:
				Notifications.AddPopup(text=_("OpenTV EPG download completed.\nNext download: %s") % next_download, type=MessageBox.TYPE_INFO, timeout=5, id=debug_name)
		if callable(self.callback):
			self.callback()
		self.callback = None

	def getCurrentlyPlayingNIM(self):
		currentlyPlayingNIM = None
		currentService = self.session and self.session.nav.getCurrentService()
		frontendInfo = currentService and currentService.frontendInfo()
		frontendData = frontendInfo and frontendInfo.getAll(True)
		if frontendData is not None:
			currentlyPlayingNIM = frontendData.get("tuner_number", None)
		return currentlyPlayingNIM


opentv_zapper = Opentv_Zapper()


autoScheduleTimer = None


def startSession(reason, session=None, **kwargs):
	#
	# This gets called twice at start up,once by WHERE_AUTOSTART without session,
	# and once by WHERE_SESSIONSTART with session. WHERE_AUTOSTART is needed though
	# as it is used to wake from deep standby. We need to read from session so if
	# session is not set just return and wait for the second call to this function.
	#
	# Called with reason=1 during /sbin/shutdown.sysvinit, and with reason=0 at startup.
	# Called with reason=1 only happens when using WHERE_AUTOSTART.
	# If only using WHERE_SESSIONSTART there is no call to this function on shutdown.
	#
	schedulename = "OpentvZapper-Scheduler"

	print("[%s][Scheduleautostart] reason(%d), session" % (schedulename, reason), session)
	if reason == 0 and session is None:
		return
	global autoScheduleTimer
	global wasScheduleTimerWakeup
	wasScheduleTimerWakeup = False
	if reason == 0:
		opentv_zapper.set_session(session)  # pass session to opentv_zapper
		wasScheduleTimerWakeup = session.nav.pluginTimerWakeupName() == "OpentvZapperScheduler"
		if wasScheduleTimerWakeup:
			session.nav.clearPluginTimerWakeupName()
			# if box is not in standby do it now
			from Screens.Standby import Standby, inStandby
			if not inStandby:
				# hack alert: session requires "pipshown" to avoid a crash in standby.py
				if not hasattr(session, "pipshown"):
					session.pipshown = False
				from Tools import Notifications
				Notifications.AddNotificationWithID("Standby", Standby)
			print("[%s][Scheduleautostart] was schedule timer wake up" % schedulename)

		print("[%s][Scheduleautostart] AutoStart Enabled" % schedulename)
		if autoScheduleTimer is None:
			autoScheduleTimer = AutoScheduleTimer(session)
	else:
		print("[%s][Scheduleautostart] Stop" % schedulename)
		if autoScheduleTimer is not None:
			autoScheduleTimer.schedulestop()
		opentv_zapper.stop_download()


class AutoScheduleTimer:
	instance = None

	def __init__(self, session):
		self.schedulename = "OpentvZapper-Scheduler"
		self.config = config.plugins.opentvzapper
		self.itemtorun = opentv_zapper.force_download
		self.session = session
		self.scheduletimer = eTimer()
		self.scheduletimer.callback.append(self.ScheduleonTimer)
		self.scheduleactivityTimer = eTimer()
		self.scheduleactivityTimer.timeout.get().append(self.scheduledatedelay)
		self.ScheduleTime = 0
		now = int(time())
		if self.config.schedule.value:
			print("[%s][AutoScheduleTimer] Schedule Enabled at " % self.schedulename, strftime("%c", localtime(now)))
			if now > 1546300800:  # Tuesday, January 1, 2019 12:00:00 AM
				self.scheduledate()
			else:
				print("[%s][AutoScheduleTimer] STB clock not yet set." % self.schedulename)
				self.scheduleactivityTimer.start(36000)
		else:
			print("[%s][AutoScheduleTimer] Schedule Disabled at" % self.schedulename, strftime("%c", localtime(now)))
			self.scheduleactivityTimer.stop()

		assert AutoScheduleTimer.instance is None, "class AutoScheduleTimer is a singleton class and just one instance of this class is allowed!"
		AutoScheduleTimer.instance = self

	def __onClose(self):
		AutoScheduleTimer.instance = None

	def scheduledatedelay(self):
		self.scheduleactivityTimer.stop()
		self.scheduledate()

	def getScheduleTime(self):
		now = localtime(time())
		return int(mktime((now.tm_year, now.tm_mon, now.tm_mday, self.config.scheduletime.value[0], self.config.scheduletime.value[1], 0, now.tm_wday, now.tm_yday, now.tm_isdst)))

	def getScheduleDayOfWeek(self):
		today = self.getToday()
		for i in range(1, 8):
			if self.config.days[(today + i) % 7].value:
				return i

	def getToday(self):
		return localtime(time()).tm_wday

	def scheduledate(self, atLeast=0):
		self.scheduletimer.stop()
		self.ScheduleTime = self.getScheduleTime()
		now = int(time())
		if self.ScheduleTime > 0:
			if self.ScheduleTime < now + atLeast:
				self.ScheduleTime += 86400 * self.getScheduleDayOfWeek()
			elif not self.config.days[self.getToday()].value:
				self.ScheduleTime += 86400 * self.getScheduleDayOfWeek()
			next = self.ScheduleTime - now
			self.scheduletimer.startLongTimer(next)
		else:
			self.ScheduleTime = -1
		print("[%s][scheduledate] Time set to" % self.schedulename, strftime("%c", localtime(self.ScheduleTime)), strftime("(now=%c)", localtime(now)))
		self.config.nextscheduletime.value = self.ScheduleTime
		self.config.nextscheduletime.save()
		configfile.save()
		return self.ScheduleTime

	def schedulestop(self):
		self.scheduletimer.stop()

	def ScheduleonTimer(self):
		self.scheduletimer.stop()
		now = int(time())
		wake = self.getScheduleTime()
		atLeast = 0
		if wake - now < 60:
			atLeast = 60
			print("[%s][ScheduleonTimer] onTimer occured at" % self.schedulename, strftime("%c", localtime(now)))
			from Screens.Standby import inStandby
			if not inStandby:
				message = _("%s update is about to start.\nDo you want to allow this?") % self.schedulename
				ybox = self.session.openWithCallback(self.doSchedule, MessageBox, message, MessageBox.TYPE_YESNO, timeout=30)
				ybox.setTitle(_('%s scheduled update') % self.schedulename)
			else:
				self.doSchedule(True)
		self.scheduledate(atLeast)

	def doSchedule(self, answer):
		now = int(time())
		if answer is False:
			if self.config.retrycount.value < 2:
				print("[%s][doSchedule] Schedule delayed." % self.schedulename)
				self.config.retrycount.value += 1
				self.ScheduleTime = now + (int(self.config.retry.value) * 60)
				print("[%s][doSchedule] Time now set to" % self.schedulename, strftime("%c", localtime(self.ScheduleTime)), strftime("(now=%c)", localtime(now)))
				self.scheduletimer.startLongTimer(int(self.config.retry.value) * 60)
			else:
				atLeast = 60
				print("[%s][doSchedule] Enough Retries, delaying till next schedule." % self.schedulename, strftime("%c", localtime(now)))
				self.session.open(MessageBox, _("Enough Retries, delaying till next schedule."), MessageBox.TYPE_INFO, timeout=10)
				self.config.retrycount.value = 0
				self.scheduledate(atLeast)
		else:
			self.timer = eTimer()
			self.timer.callback.append(self.runscheduleditem)
			print("[%s][doSchedule] Running Schedule" % self.schedulename, strftime("%c", localtime(now)))
			self.timer.start(100, 1)

	def runscheduleditem(self):
		self.itemtorun(self.runscheduleditemCallback)

	def runscheduleditemCallback(self):
		global wasScheduleTimerWakeup
		from Screens.Standby import inStandby, TryQuitMainloop, inTryQuitMainloop
		print("[%s][runscheduleditemCallback] inStandby" % self.schedulename, inStandby)
		if wasScheduleTimerWakeup and inStandby and self.config.scheduleshutdown.value and not self.session.nav.getRecordings() and not inTryQuitMainloop:
			print("[%s] Returning to deep standby after scheduled wakeup" % self.schedulename)
			self.session.open(TryQuitMainloop, 1)
		wasScheduleTimerWakeup = False  # clear this as any subsequent run will not be from wake up from deep

	def doneConfiguring(self):  # called from plugin on save
		now = int(time())
		if self.config.schedule.value:
			if autoScheduleTimer is not None:
				print("[%s][doneConfiguring] Schedule Enabled at" % self.schedulename, strftime("%c", localtime(now)))
				autoScheduleTimer.scheduledate()
		else:
			if autoScheduleTimer is not None:
				self.ScheduleTime = 0
				print("[%s][doneConfiguring] Schedule Disabled at" % self.schedulename, strftime("%c", localtime(now)))
				autoScheduleTimer.schedulestop()
		# scheduletext is not used for anything but could be returned to the calling function to display in the GUI.
		if self.ScheduleTime > 0:
			t = localtime(self.ScheduleTime)
			scheduletext = strftime(_("%a %e %b  %-H:%M"), t)
		else:
			scheduletext = ""
		return scheduletext
