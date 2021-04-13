# -*- coding: utf-8 -*-
#
#  PaxWeather2 Converter for teamBlue-image
#
#  Coded by örlgrey
#  Based on teamBlue image source code
#
#  This code is licensed under the Creative Commons
#  Attribution-NonCommercial-ShareAlike 3.0 Unported
#  License. To view a copy of this license, visit
#  http://creativecommons.org/licenses/by-nc-sa/3.0/
#  or send a letter to Creative Commons, 559 Nathan
#  Abbott Way, Stanford, California 94305, USA.
#
#  If you think this license infringes any rights,
#  please contact me at ochzoetna@gmail.com

from Components.Converter.Converter import Converter
from Components.Element import cached
from Components.config import config
from enigma import eTimer
import requests
from Poll import Poll
from Plugins.Extensions.PaxWeather import ping
from lxml import etree
from xml.etree.cElementTree import fromstring

WEATHER_DATA = None
WEATHER_LOAD = True

class PaxWeather2(Poll, Converter, object):
	TempNow = 1
	MeteoNow = 2
	HighNext = 3
	LowNext = 4
	MeteoNext = 5

	def __init__(self, type):
		Poll.__init__(self)
		Converter.__init__(self, type)
		self.poll_interval = 60000
		self.poll_enabled = True
		self.timer = eTimer()
		self.timer.callback.append(self.reset)
		self.timer.callback.append(self.get_Data)
		self.data = None
		self.get_Data()

		if type == "tempnow":
			self.type = self.TempNow
		elif type == "meteonow":
			self.type = self.MeteoNow
		elif type == "highnext":
			self.type = self.HighNext
		elif type == "lownext":
			self.type = self.LowNext
		elif type == "meteonext":
			self.type = self.MeteoNext

	@cached
	def getText(self):
		global WEATHER_DATA
		self.data = WEATHER_DATA
		if self.type == self.TempNow:
			return self.getTemperature_Current()
		elif self.type in (self.MeteoNow, self.MeteoNext):
			return self.getMeteoFont()
		elif self.type == self.HighNext:
			return self.getTemperature_HighNext()
		elif self.type == self.LowNext:
			return self.getTemperature_LowNext()
		else:
			return ""

	text = property(getText)

	def reset(self):
		global WEATHER_LOAD
		WEATHER_LOAD = True
		self.timer.stop()

	def get_Data(self):
		global WEATHER_DATA
		global WEATHER_LOAD
		if WEATHER_LOAD == True:
			try:
				r = ping.doOne("8.8.8.8", 1.5)
				if r != None and r <= 1.5:
					print "PaxWeather: download from URL"
					res = requests.get('http://weather.service.msn.com/data.aspx?src=windows&weadegreetype=C&culture=de-DE&wealocations=wc:' + str(config.plugins.PaxWeather.gmcode.value), timeout=1.5)
					self.data = fromstring(res.text)
					WEATHER_DATA = self.data
					WEATHER_LOAD = False
			except:
				pass
			timeout = max(15, int(config.plugins.PaxWeather.refreshInterval.value)) * 1000.0 * 60.0
			self.timer.start(int(timeout), True)
		else:
			self.data = WEATHER_DATA

	def getTemperature_Current(self):
		try:
			for childs in self.data:
				for items in childs:
					if items.tag == 'current':
						value = items.attrib.get("temperature").encode("utf-8", 'ignore')
						return str(value) + "°C"
		except:
			return ''

	def getTemperature_HighNext(self):
		try:
			for items in self.data.findall(".//forecast[3]"):
				value = items.get("high").encode("utf-8", 'ignore')
				return str(value) + "°C"
		except:
			return ''

	def getTemperature_LowNext(self):
		try:
			for items in self.data.findall(".//forecast[3]"):
				value = items.get("low").encode("utf-8", 'ignore')
				return str(value) + "°C"
		except:
			return ''

	def getMeteoFont(self):
		if self.type in (self.MeteoNow, self.MeteoNext):
			try:
				if self.type == self.MeteoNow:
					for childs in self.data:
						for items in childs:
							if items.tag == "current":
								value = items.attrib.get("skycode").encode("utf-8", 'ignore')
				if self.type == self.MeteoNext:
					for items in self.data.findall(".//forecast[3]"):
						value = items.get("skycodeday").encode("utf-8", 'ignore')
			except:
				return ''

			if value in ("0", "1", "2", "23", "24"):
				return "S"
			elif value in ("3", "4"):
				return "Z"
			elif value in ("5", "6", "7", "18"):
				return "U"
			elif value in ("8", "10", "25"):
				return "G"
			elif value == "9":
				return "Q"
			elif value in ("11", "12", "40"):
				return "R"
			elif value in ("13", "14", "15", "16", "41", "42", "43", "46"):
				return "W"
			elif value in ("17", "35"):
				return "X"
			elif value == "19":
				return "F"
			elif value in ("20", "21", "22"):
				return "L"
			elif value in ("26", "44"):
				return "N"
			elif value in ("27", "29"):
				return "I"
			elif value in ("28", "30"):
				return "H"
			elif value in ("31", "33"):
				return "C"
			elif value in ("32", "34", "36"):
				return "B"
			elif value in ("37", "38", "39", "45", "47"):
				return "0"
			else:
				return ")"
