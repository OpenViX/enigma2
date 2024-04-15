from os import stat
import time

from Components.config import config

ECM_INFO = '/tmp/ecm.info'
EMPTY_ECM_INFO = '', '0', '0', '0', ''

old_ecm_time = time.time()
info = {}
ecm = ''
data = EMPTY_ECM_INFO


class GetEcmInfo:
	def __init__(self):
		pass

	def createCurrentDevice(self, current_device, isLong):
		if not current_device:
			return ""
		if "/sci0" in current_device.lower():
			return _("Card reader 1") if isLong else "CRD 1"
		elif "/sci1" in current_device.lower():
			return _("Card reader 2") if isLong else "CRD 2"
		elif "/ttyusb0" in current_device.lower():
			return _("USB reader 1") if isLong else "USB 1"
		elif "/ttyusb1" in current_device.lower():
			return _("USB reader 2") if isLong else "USB 2"
		elif "/ttyusb2" in current_device.lower():
			return _("USB reader 3") if isLong else "USB 3"
		elif "/ttyusb3" in current_device.lower():
			return _("USB reader 4") if isLong else "USB 4"
		elif "/ttyusb4" in current_device.lower():
			return _("USB reader 5") if isLong else "USB 5"
		elif "emulator" in current_device.lower():
			return _("Emulator") if isLong else "EMU"
		elif "const" in current_device.lower():
			return _("Constcw") if isLong else "CCW"

	def pollEcmData(self):
		global data
		global old_ecm_time
		global info
		global ecm
		try:
			ecm_time = stat(ECM_INFO).st_mtime
		except:
			ecm_time = old_ecm_time
			data = EMPTY_ECM_INFO
			info = {}
			ecm = ''
		if ecm_time != old_ecm_time:
			oecmi1 = info.get('ecminterval1', '')
			oecmi0 = info.get('ecminterval0', '')
			info = {'ecminterval2': oecmi1, 'ecminterval1': oecmi0}
			old_ecm_time = ecm_time
			try:
				ecm = open(ECM_INFO, 'r').readlines()
			except:
				ecm = ''
			for line in ecm:
				d = line.split(':', 1)
				if len(d) > 1:
					info[d[0].strip()] = d[1].strip()
			data = self.getText()
			return True
		else:
			info['ecminterval0'] = int(time.time() - ecm_time + 0.5)

	def getEcm(self):
		return (self.pollEcmData(), ecm)

	def getEcmData(self):
		self.pollEcmData()
		return data

	def getInfo(self, member, ifempty=''):
		self.pollEcmData()
		return str(info.get(member, ifempty))

	def getInfoRaw(self):
		self.pollEcmData()
		return info

	def getText(self):
		global ecm
		try:
			# info is dictionary
			using = info.get('using', '')
			protocol = info.get('protocol', '')
			device = ''
			if using or protocol:
				if config.usage.show_cryptoinfo.value == '0':
					self.textvalue = ' '
				elif config.usage.show_cryptoinfo.value == '1':
					# CCcam
					if using == 'fta':
						self.textvalue = _("Free To Air")
					elif protocol == 'emu':
						self.textvalue = "Emu (%ss)" % (info.get('ecm time', '?'))
					elif protocol == 'constcw':
						self.textvalue = "Constcw (%ss)" % (info.get('ecm time', '?'))
					else:
						if info.get('address', None):
							address = info.get('address', '')
						elif info.get('from', None):
							address = info.get('from', '').replace(":0", "").replace("cache", "cache ")
							if "Local" in address:
								from_arr = address.split("-")
								address = from_arr[0].strip()
								if len(from_arr) > 1:
									device = from_arr[1].strip()
						else:
							address = ''
							device = ''
						hops = info.get('hops', None)
						if hops and hops != '0':
							hops = ' @' + hops
						else:
							hops = ''
						self.textvalue = address + hops + " (%ss)" % info.get('ecm time', '?')
				elif config.usage.show_cryptoinfo.value == '2':
					# CCcam
					if using == 'fta':
						self.textvalue = _("Free To Air")
					else:
						address = _('Server:') + ' '
						if info.get('address', None):
							address += info.get('address', '')
						elif info.get('from', None):
							address = info.get('from', '').replace(":0", "").replace("cache", "cache ")
							if "const" in protocol.lower():
								device = "constcw"
							if "const" in address.lower():
								address = ""
							if "local" in address.lower():
								from_arr = address.split("-")
								address = from_arr[0].strip().replace("Local", "").replace("local", "")
								if len(from_arr) > 1:
									device = from_arr[1].strip()
						protocol = _('Protocol:') + ' '
						if info.get('protocol', None):
							protocol += info.get('protocol', '').replace("-s2s", "-S2s").replace("ext", "Ext").replace("mcs", "Mcs").replace("Cccam", "CCcam").replace("cccam", "CCcam")
						elif info.get('using', None):
							protocol += info.get('using', '').replace("-s2s", "-S2s").replace("ext", "Ext").replace("mcs", "Mcs").replace("Cccam", "CCcam").replace("cccam", "CCcam")

						hops = _('Hops:') + ' '
						if info.get('hops', None):
							hops += info.get('hops', '')

						ecm = _('Ecm:') + ' '
						if info.get('ecm time', None):
							ecm += info.get('ecm time', '')
						device_str = self.createCurrentDevice(device, True)
						self.textvalue = address + ((device_str) if device else "") + '\n' + protocol + '  ' + hops + '  ' + ecm
				elif config.usage.show_cryptoinfo.value == '3':
					# CCcam
					if using == 'fta':
						self.textvalue = _("Free To Air")
					else:
						address = ' '
						if info.get('reader', None):
							address += info.get('reader', '')
						elif info.get('from', None):
							address = info.get('from', '').replace(":0", "").replace("cache", "cache ")
							if "const" in protocol.lower():
								device = "constcw"
							if "const" in address.lower():
								address = ""
							if "local" in address.lower():
								from_arr = address.split("-")
								address = from_arr[0].strip().replace("Local", "").replace("local", "")
								if len(from_arr) > 1:
									device = from_arr[1].strip()
						protocol = _('Protocol:') + ' '
						if info.get('protocol', None):
							protocol += info.get('protocol', '').capitalize().replace("-s2s", "-S2s").replace("ext", "Ext").replace("mcs", "Mcs").replace("Cccam", "CCcam").replace("cccam", "CCcam")
						elif info.get('using', None):
							protocol += info.get('using', '').capitalize().replace("-s2s", "-S2s").replace("ext", "Ext").replace("mcs", "Mcs").replace("Cccam", "CCcam").replace("cccam", "CCcam")
			else:
				decode = info.get('decode', None)
				if decode:
					# gbox (untested)
					if info['decode'] == 'Network':
						cardid = 'id:' + info.get('prov', '')
						try:
							share = open('/tmp/share.info', 'r').readlines()
							for line in share:
								if cardid in line:
									self.textvalue = line.strip()
									break
							else:
								self.textvalue = cardid
						except:
							self.textvalue = decode
					else:
						self.textvalue = decode
					if ecm[1].startswith('SysID'):
						info['prov'] = ecm[1].strip()[6:]
					if 'response' in info:
						self.textvalue += " (0.%ss)" % info['response']
						info['caid'] = ecm[0][ecm[0].find('CaID 0x') + 7:ecm[0].find(',')]
						info['pid'] = ecm[0][ecm[0].find('pid 0x') + 6:ecm[0].find(' =')]
						info['provid'] = info.get('prov', '0')[:4]
				else:
					source = info.get('source', None)
					if source:
						# wicardd - type 2 / mgcamd
						caid = info.get('caid', None)
						if caid:
							info['caid'] = info['caid'][2:]
							info['pid'] = info['pid'][2:]
						info['provid'] = info['prov'][2:]
						time = ""
						for line in ecm:
							if 'msec' in line:
								line = line.split(' ')
								if line[0]:
									time = " (%ss)" % (float(line[0]) / 1000)
									continue
						self.textvalue = source + time
					else:
						reader = info.get('reader', '')
						if reader:
							hops = info.get('hops', None)
							if hops and hops != '0':
								hops = ' @' + hops
							else:
								hops = ''
							self.textvalue = reader + hops + " (%ss)" % info.get('ecm time', '?')
						else:
							response = info.get('response time', None)
							if response:
								# wicardd - type 1
								response = response.split(' ')
								self.textvalue = "%s (%ss)" % (response[4], float(response[0]) / 1000)
							else:
								self.textvalue = ""
			decCI = info.get('caid', info.get('CAID', '0'))
			provid = info.get('provid', info.get('prov', info.get('Provider', '0')))
			ecmpid = info.get('pid', info.get('ECM PID', '0'))
		except:
			ecm = ''
			self.textvalue = ""
			device = ''
			decCI = '0'
			provid = '0'
			ecmpid = '0'
		return self.textvalue, decCI, provid, ecmpid, device
