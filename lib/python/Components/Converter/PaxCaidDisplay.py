#
#  CaidDisplay - Converter
#
#  Coded by Dr.Best & weazle (c) 2010
#  Support: www.dreambox-tools.info
#
#  This plugin is licensed under the Creative Commons 
#  Attribution-NonCommercial-ShareAlike 3.0 Unported 
#  License. To view a copy of this license, visit
#  http://creativecommons.org/licenses/by-nc-sa/3.0/ or send a letter to Creative
#  Commons, 559 Nathan Abbott Way, Stanford, California 94305, USA.
#
#  Alternatively, this plugin may be distributed and executed on hardware which
#  is licensed by Dream Multimedia GmbH.
#
#  This plugin is NOT free software. It is open source, you are allowed to
#  modify it (if you keep the license), but it may not be commercially 
#  distributed other than under the conditions noted above.
#

from Components.Converter.Converter import Converter
from enigma import iServiceInformation, iPlayableService
from Components.Element import cached
from Poll import Poll
import datetime

def cardnames(caid,prov):
		if caid   == '098C' and prov =='000000':cn = 'SKY NDS V14'		#19E
		elif caid == '09C4' and prov =='000000':cn = 'SKY NDS V13'		#19E
		elif caid == '09C7' and prov =='000000':cn = 'KD G02/G09'
		elif caid == '09AF' and prov =='000000':cn = 'KabelKiosk'
		elif caid == '1702' and prov =='000000':cn = 'SKY BC S02'		#19E
		elif caid == '1833' and prov =='000000':cn = 'SKY(BTun)S02'		#19E
		elif caid == '1722' and prov =='000000':cn = 'KD D01/D02'
		elif caid == '1810' and prov =='000000':cn = 'Digital+ Esp'		#19E
		elif caid == '1815' and prov =='000000':cn = 'UPC Direct'		#0.8W
		elif caid == '1830' and prov =='000000':cn = 'HD+ HD01'			#19E
		elif caid == '1843' and prov =='000000':cn = 'HD+ HD02'			#19E
		elif caid == '1834' and prov =='000000':cn = 'KD D02/D09'		#Cable DE
		elif caid == '098E' and prov =='000000':cn = 'UMKBW V23'		#Cable DE
		elif caid == '1831' and prov =='000000':cn = 'UMKBW UM1/3'		#Cable DE
		elif caid == '1838' and prov =='000000':cn = 'UMKBW UM02'		#Cable DE
		elif caid == '183D' and prov =='000000':cn = 'Mediaset Premium'
		elif caid == '183E' and prov =='000000':cn = 'Mediaset Premium'
		elif caid == '0D95' and prov =='000004':cn = 'ORF-CW'			#19E
		elif caid == '0648' and prov =='000000':cn = 'ORF-Irdeto'		#19E
		elif caid == '0D96' and prov =='000004':cn = 'SkyLink CZ'		#23E
		elif caid == '0500' and prov =='023800':cn = 'SRGv2'			#13E
		elif caid == '0500' and prov =='040810':cn = 'SRGv4'			#13E
		elif caid == '0500' and prov =='032500':cn = 'BRAZZERS TV'		#19E
		elif caid == '0500' and prov =='042700':cn = 'MCT/SCT'
		elif caid == '0500' and prov =='042800':cn = 'BisTV'
		elif caid == '0500' and prov =='043800':cn = 'RedlightHD'		#13E
		elif caid == '0500' and prov =='050800':cn = 'SRGv5'			#13E
		elif caid == '0500' and prov =='050F00':cn = 'Dorcel TV'		#19E
		elif caid == '0500' and prov =='030B00':cn = 'TNTSAT'
		elif caid == '0500' and prov =='032940':cn = 'CSAT'
		elif caid == '0B00' and prov =='000000':cn = 'Conax Card'
		elif caid == '0BAA' and prov =='000000':cn = 'Conax Card'
		elif caid == '0B01' and prov =='000000':cn = 'UPC Direct'
		elif caid == '0100' and prov =='00006A':cn = 'C+ Nederland'		#19E
		elif caid == '0100' and prov =='00006C':cn = 'TV Vlaanderen'		#19E
		else: cn = 'Card'
		return cn

class PaxCaidDisplay(Poll, Converter, object):
	def __init__(self, type):
		Poll.__init__(self)
		Converter.__init__(self, type)
		self.type = type
		self.systemCaids = {
			"26" : "BiSS",
			"01" : "SEC",
			"06" : "IRD",
			"17" : "BET",
			"05" : "VIA",
			"18" : "NAG",
			"09" : "NDS",
			"0B" : "CON",
			"0D" : "CRW",
			"4A" : "DRE" }
		self.poll_interval = 3000
		self.poll_enabled = True

	@cached
	def get_caidlist(self):
		caidlist = {}
		service = self.source.service
		if service:
			info = service and service.info()
			if info:
				caids = info.getInfoObject(iServiceInformation.sCAIDs)
				if caids:
					for cs in self.systemCaids:
						caidlist[cs] = (self.systemCaids.get(cs),0)
					for caid in caids:
						c = "%x" % int(caid)
						if len(c) == 3:
							c = "0%s" % c
						c = c[:2].upper()
						if self.systemCaids.has_key(c):
							caidlist[c] = (self.systemCaids.get(c),1)
					ecm_info = self.ecmfile()
					if ecm_info:
						emu_caid = ecm_info.get("caid", "")
						if emu_caid and emu_caid != "0x000":
							c = emu_caid.lstrip("0x")
							if len(c) == 3:
								c = "0%s" % c
							c = c[:2].upper()
							caidlist[c] = (self.systemCaids.get(c),2)
		return caidlist

	getCaidlist = property(get_caidlist)

	@cached
	def getText(self):
		textvalue = ""
		service = self.source.service
		if service:
			info = service and service.info()
			if info:
				if info.getInfoObject(iServiceInformation.sCAIDs):
					ecm_info = self.ecmfile()
					if ecm_info:
						# caid
						caid = ecm_info.get("caid", "")
						caid = caid.lstrip("0x")
						caid = caid.upper()
						caid = caid.zfill(4)
						caid = "%s" % caid

						# prov
						prov = ecm_info.get("prov", "")
						prov = prov.lstrip("0x")
						prov = prov.upper()
						if prov == '':
						 prov = ''
						 prov = "%s" % prov.zfill(6)
						else:
						 prov = prov.zfill(6)
						 prov = "%s" % prov

						#provid cccam
						provid = ecm_info.get("provid", "")
						provid = provid.lstrip("0x")
						provid = provid.upper()
						provid = provid.zfill(6)
						provid = "%s" % provid
						
						#provider cccam
						provider = ecm_info.get("provider", "")
						provider = "%s" % provider
						provider = provider[:25]
						
						# hops
						hops = ecm_info.get("hops", None)
						hops = "%s" % hops
						
						# from
						froms = ecm_info.get("from", "")
						fromsorg = froms
						if froms.count("192.168.")>0 or froms.count("172.16.")>0 or froms.count("10.")>0:froms = 'HomeNet'
						if froms.count(".")==0:
							froms = 'HomeNet'
						else:
							froms = 'Internet'
						froms = "%s" % froms
						fromsorg = "%s" % fromsorg
						
						# ecm time	
						ecm_time = ecm_info.get("ecm time", None)
						if ecm_time:
							if "msec" in ecm_time:
								ecm_time = "%s " % ecm_time
							else:
								ecm_time = "%s s" % ecm_time

						# address
						address = ecm_info.get("address", "")
						address = address.split(":")
						address = address[0]
						if address.count("192.168.")>0 or  address.count("172.16.")>0 or address.count("10.")>0:
							address = address
						else:
							address = address.split(".")
							address = address[0]
						# source
						using = ecm_info.get("using", "")
						# protocol
						protocol = ecm_info.get("protocol", "")
						protocol = "%s" % protocol
						if using:
							karte = cardnames(caid,provid)
							if karte =='Card':karte = provider
							karte = karte[:15]
							karte = '(' + karte +')'
							if using == "emu":textvalue = "%s - %s %s (EMU)" % (caid, ecm_time, karte)
							elif using == "CCcam-s2s":
								if provid == '000000':
									textvalue = "%s - %s - HOP:%s - %s %s" % (caid, ecm_time, hops, address, karte)
								else:
									textvalue = "%s:%s - %s - HOP:%s - %s %s" % (caid, provid, ecm_time, hops, address, karte)
							elif using == "sci":textvalue = "%s%s - %s - (local) %s" % (caid, provid, ecm_time, karte)
							else:textvalue = "%s %s%s - hop:%s - %s %s" % (using, caid, provid, hops, ecm_time, karte)
						else:
							# mgcamd
							source = ecm_info.get("source", None)
							if source:
								if source == "emu":
									emprov = ecm_info.get("prov", "")
									emprov= emprov.split(",")
									emprov = emprov[0]
									karte = cardnames(caid,emprov)
									emprov = ":%s" % emprov
									textvalue = "%s%s %s (EMU)" % (caid, emprov , karte)
								else:
									karte = cardnames(caid,prov)
									share = ecm_info.get("source", "")
									share = share.lstrip("net").replace('(cccamd at ','').replace(')','').replace(' ','')
									share = share.split(":")
									share = share[0]
									if karte =='Card':karte=''
									else:karte =' (' + karte + ')'
									if share.count("192.168.")>0 or  share.count("172.16.")>0 or share.count("10.")>0:share = share
									else:share = share.split(".");share = share[0]
									if prov == '000000':
										textvalue = "%s - %s - %s %s" % (caid, ecm_time, share, karte)
									else:
										textvalue = "%s:%s - %s - %s %s" % (caid, prov, ecm_time, share, karte)
							#- oscam---#
							oscsource = ecm_info.get("reader", "")
							oscsource = oscsource.replace('emulator','EMU')
							if oscsource:
								karte = cardnames(caid,prov)
								karte = karte[:15]
								if karte =='Card':
									karte=''
								else:
									karte = '(' + karte + ') '
								oscsource = str(oscsource[:12])
								first =("%s %s:%s - Hop:%s - %s" % (karte, caid, prov, hops, ecm_time))
								#last = ("%s - %s - %s: %s" % (protocol, oscsource, froms, fromsorg))
								froms = ""
								last = ("%s - %s@%s" % (protocol, oscsource, fromsorg))
								ax ='{:%S}'.format(datetime.datetime.now())
								ax = float(ax)
								if ax >0 and ax <4 or ax> 6 and ax<10 or ax>12 and ax<16 or ax>18 and ax<22 or ax>24 and ax<28 or ax>27 and ax<31 or ax>33 and ax<37 or ax>39 and ax<43 or ax>45 and ax<49 or ax>51 and ax<55 or ax>57 and ax<60:
									textvalue=first
								else:
									textvalue=last
								if protocol == "internal":		textvalue = "%s %s:%s - %s - local - %s" % (karte, caid, prov, ecm_time, oscsource)
								elif protocol == "emu":			textvalue = "%s %s:%s - %s - %s" % (karte, caid, prov, ecm_time, oscsource)
								elif oscsource == "Cache":		textvalue = "%s %s:%s - %s - %s" % (karte, caid, prov, ecm_time, fromsorg)
								elif protocol == "cccam": 		textvalue = textvalue.replace('cccam','OsCam')
								elif protocol == "cccam_ext":	textvalue = textvalue.replace('cccam_ext','OsCam')
								elif protocol == "cs357x":		textvalue = textvalue.replace('cs357x','Cs357x')
								elif protocol == "cs378x":		textvalue = textvalue.replace('cs378x','Cs378x')
								elif protocol == "newcamd":		textvalue = textvalue.replace('newcamd','Newcamd')
								elif protocol == "mouse":		textvalue = textvalue.replace('mouse','Mouse')
								else:
									textvalue = textvalue
							#--oscam--#
									
							# gbox
							decode = ecm_info.get("decode", None)
							if decode:
								if decode == "Internal":textvalue = "(EMU) %s" % (caid)
								else:textvalue = "%s - %s" % (caid, decode)

		return textvalue 

	text = property(getText)


	def ecmfile(self):
		ecm = None
		info = {}
		service = self.source.service
		if service:
			frontendInfo = service.frontendInfo()
			if frontendInfo:
				try:
					ecmpath = "/tmp/ecm.info"
					ecm = open(ecmpath, "rb").readlines()
				except:
					try:
						ecm = open("/tmp/ecm.info", "rb").readlines()
					except: pass
			if ecm:
				for line in ecm:
					x = line.lower().find("msec")
					if x != -1:
						info["ecm time"] = line[0:x+4]
					else:
						item = line.split(":", 1)
						if len(item) > 1:
							info[item[0].strip().lower()] = item[1].strip()
						else:
							if not info.has_key("caid"):
								x = line.lower().find("caid")
								if x != -1:
									y = line.find(",")
									if y != -1:
										info["caid"] = line[x+5:y]

		return info

	def changed(self, what):
		if (what[0] == self.CHANGED_SPECIFIC and what[1] == iPlayableService.evUpdatedInfo) or what[0] == self.CHANGED_POLL:
			Converter.changed(self, what)