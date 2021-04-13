# -*- coding: utf-8 -*-
#
#  PaxWeather Converter for teamBlue-image
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

class PaxWeather(Converter, object):
	TempNow = 1
	MeteoNow = 2
	HighNext = 3
	LowNext = 4
	MeteoNext = 5

	def __init__(self, type):
		Converter.__init__(self, type)

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

	def getMeteoFont(self):
		if self.type in (self.MeteoNow, self.MeteoNext):
			if self.type == self.MeteoNow:
				value = self.source.getCode(-1)
			else:
				value = self.source.getCode(3)
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

	@cached
	def getText(self):
		if self.type == self.TempNow:
			return self.source.getTemperature_Current()
		elif self.type in (self.MeteoNow, self.MeteoNext):
			return self.getMeteoFont()
		elif self.type == self.HighNext:
			return self.source.getTemperature_Heigh(3)
		elif self.type == self.LowNext:
			return self.source.getTemperature_Low(3)
		else:
			return ""

	text = property(getText)
