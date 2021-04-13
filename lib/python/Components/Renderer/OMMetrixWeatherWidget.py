#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#######################################################################
#
#	MetrixWeather for Enigma2
#	Coded by Sinthex IT-Solutions (c) 2014
#	www.open-store.net
#
#    teamBlue - change to MSN weather step 1, thx to openatv
#
#  This plugin is licensed under the Creative Commons
#  Attribution-NonCommercial-ShareAlike 3.0 Unported License.
#  To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/3.0/
#  or send a letter to Creative Commons, 559 Nathan Abbott Way, Stanford, California 94305, USA.
#
#  This plugin is NOT free software. It is open source, you are allowed to
#  modify it (if you keep the license), but it may not be commercially
#  distributed other than under the conditions noted above.
#
#
#######################################################################

from Renderer import Renderer
from Components.VariableText import VariableText
from urllib2 import Request, URLError, urlopen as urlopen2, quote as urllib2_quote
from enigma import ePixmap
from datetime import datetime
from Components.Element import cached
from xml.dom.minidom import parseString
from Components.config import config, configfile, ConfigSubsection, ConfigSelection, ConfigNumber, ConfigSelectionNumber, ConfigYesNo, ConfigText

std_headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_3) AppleWebKit/534.53.11 (KHTML, like Gecko) Version/5.1.3 Safari/534.53.10',
 'Accept-Charset': 'windows-1251,utf-8;q=0.7,*;q=0.7',
 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
 'Accept-Language': 'ru,en-us;q=0.7,en;q=0.3'}


def initWeatherConfig():
	config.plugins.MetrixWeather = ConfigSubsection()
	#MetrixWeather
	config.plugins.MetrixWeather.enabled = ConfigYesNo(default=False)
	config.plugins.MetrixWeather.weathercity = ConfigText(default='Hamburg, Germany')
	config.plugins.MetrixWeather.tempUnit = ConfigSelection(default="Celsius", choices=[
		("Celsius", _("Celsius")),
		("Fahrenheit", _("Fahrenheit"))
	])
	config.plugins.MetrixWeather.refreshInterval = ConfigNumber(default=60)
	config.plugins.MetrixWeather.lastUpdated = ConfigText(default="2001-01-01 01:01:01")

	## RENDERER CONFIG:
	config.plugins.MetrixWeather.currentLocation = ConfigText(default="N/A")
	config.plugins.MetrixWeather.currentWeatherCode = ConfigText(default="(")
	config.plugins.MetrixWeather.currentWeatherText = ConfigText(default="N/A")
	config.plugins.MetrixWeather.currentWeatherTemp = ConfigText(default="0")
	config.plugins.MetrixWeather.forecastTodayCode = ConfigText(default="(")
	config.plugins.MetrixWeather.forecastTodayText = ConfigText(default="N/A")
	config.plugins.MetrixWeather.forecastTodayTempMin = ConfigText(default="0")
	config.plugins.MetrixWeather.forecastTodayTempMax = ConfigText(default="0")
	config.plugins.MetrixWeather.forecastTomorrowCode = ConfigText(default="(")
	config.plugins.MetrixWeather.forecastTomorrowText = ConfigText(default="N/A")
	config.plugins.MetrixWeather.forecastTomorrowTempMin = ConfigText(default="0")
	config.plugins.MetrixWeather.forecastTomorrowTempMax = ConfigText(default="0")

	config.plugins.MetrixWeather.save()
	configfile.save()


initWeatherConfig()


class OMMetrixWeatherWidget(Renderer):

	def __init__(self):
		Renderer.__init__(self)

	def changed(self, what):
		if self.instance:
			if what[0] != self.CHANGED_CLEAR:
				if config.plugins.MetrixWeather.enabled.saved_value:
					self.instance.show()
					self.getWeather()
				else:
					self.instance.hide()
	GUI_WIDGET = ePixmap

	def getWeather(self):
		# skip if weather-widget is already up to date
		tdelta = datetime.now() - datetime.strptime(config.plugins.MetrixWeather.lastUpdated.value, "%Y-%m-%d %H:%M:%S")
		if int(tdelta.seconds) < (config.plugins.MetrixWeather.refreshInterval.value * 60): ##### 1=60 for testing purpose #####
			return
		id = ""
		name = ""
		temp = ""
		temp_max = ""
		temp_min = ""
		cityname = config.plugins.MetrixWeather.weathercity.value
		print "[OMMetrixWeather] lookup for city " + str(cityname)
		language = config.osd.language.value.replace('_', '-')
		if language == 'en-EN':
			language = 'en-US'
		city = "%s" % cityname
		feedurl = "http://weather.service.msn.com/data.aspx?weadegreetype=%s&culture=%s&weasearchstr=%s&src=outlook" % (self.getTemp(), language, urllib2_quote(city))
		msnrequest = Request(feedurl, None, std_headers)
		try:
			msnpage = urlopen2(msnrequest)
		except (URLError) as err:
			print '[OMMetrixWeather] Error: Unable to retrieve page - Error code: ', str(err)
			config.plugins.MetrixWeather.lastUpdated.value = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
			return
		content = msnpage.read()
		msnpage.close()
		dom = parseString(content)
		currentWeather = dom.getElementsByTagName('weather')[0]
		titlemy = currentWeather.getAttributeNode('weatherlocationname')
		config.plugins.MetrixWeather.currentLocation.value = titlemy.nodeValue
		name = titlemy.nodeValue
		idmy = currentWeather.getAttributeNode('weatherlocationcode')
		id = idmy.nodeValue
		currentWeather = dom.getElementsByTagName('current')[0]
		currentWeatherCode = currentWeather.getAttributeNode('skycode')
		config.plugins.MetrixWeather.currentWeatherCode.value = self.ConvertCondition(currentWeatherCode.nodeValue)
		currentWeatherTemp = currentWeather.getAttributeNode('temperature')
		temp = currentWeatherTemp.nodeValue
		config.plugins.MetrixWeather.currentWeatherTemp.value = currentWeatherTemp.nodeValue
		currentWeatherText = currentWeather.getAttributeNode('skytext')
		config.plugins.MetrixWeather.currentWeatherText.value = currentWeatherText.nodeValue
		n = 1
		currentWeather = dom.getElementsByTagName('forecast')[n]
		currentWeatherCode = currentWeather.getAttributeNode('skycodeday')
		config.plugins.MetrixWeather.forecastTodayCode.value = self.ConvertCondition(currentWeatherCode.nodeValue)
		currentWeatherTemp = currentWeather.getAttributeNode('high')
		temp_max = currentWeatherTemp.nodeValue
		config.plugins.MetrixWeather.forecastTodayTempMax.value = currentWeatherTemp.nodeValue
		currentWeatherTemp = currentWeather.getAttributeNode('low')
		temp_min = currentWeatherTemp.nodeValue
		config.plugins.MetrixWeather.forecastTodayTempMin.value = currentWeatherTemp.nodeValue
		currentWeatherText = currentWeather.getAttributeNode('skytextday')
		config.plugins.MetrixWeather.forecastTodayText.value = currentWeatherText.nodeValue
		currentWeather = dom.getElementsByTagName('forecast')[n + 1]
		currentWeatherCode = currentWeather.getAttributeNode('skycodeday')
		config.plugins.MetrixWeather.forecastTomorrowCode.value = self.ConvertCondition(currentWeatherCode.nodeValue)
		currentWeatherTemp = currentWeather.getAttributeNode('high')
		config.plugins.MetrixWeather.forecastTomorrowTempMax.value = currentWeatherTemp.nodeValue
		currentWeatherTemp = currentWeather.getAttributeNode('low')
		config.plugins.MetrixWeather.forecastTomorrowTempMin.value = currentWeatherTemp.nodeValue
		currentWeatherText = currentWeather.getAttributeNode('skytextday')
		config.plugins.MetrixWeather.forecastTomorrowText.value = currentWeatherText.nodeValue
		config.plugins.MetrixWeather.save()
		configfile.save()

	def getText(self, nodelist):
		rc = []
		for node in nodelist:
			if node.nodeType == node.TEXT_NODE:
				rc.append(node.data)
		return ''.join(rc)

	def ConvertCondition(self, c):
		try:
			c = int(c)
		except:
			c = 49
		condition = "("
		if c == 0 or c == 1 or c == 2:
			condition = "S"
		elif c == 3 or c == 4:
			condition = "Z"
		elif c == 5 or c == 6 or c == 7 or c == 18:
			condition = "U"
		elif c == 8 or c == 10 or c == 25:
			condition = "G"
		elif c == 9:
			condition = "Q"
		elif c == 11 or c == 12 or c == 40:
			condition = "R"
		elif c == 13 or c == 14 or c == 15 or c == 16 or c == 41 or c == 46 or c == 42 or c == 43:
			condition = "W"
		elif c == 17 or c == 35:
			condition = "X"
		elif c == 19:
			condition = "F"
		elif c == 20 or c == 21 or c == 22:
			condition = "L"
		elif c == 23 or c == 24:
			condition = "S"
		elif c == 26 or c == 44:
			condition = "N"
		elif c == 27 or c == 29:
			condition = "I"
		elif c == 28 or c == 30:
			condition = "H"
		elif c == 31 or c == 33:
			condition = "C"
		elif c == 32 or c == 34:
			condition = "B"
		elif c == 36:
			condition = "B"
		elif c == 37 or c == 38 or c == 39 or c == 45 or c == 47:
			condition = "0"
		elif c == 49:
			condition = ")"
		else:
			condition = ")"
		return str(condition)

	def getTemp(self):
		if config.plugins.MetrixWeather.tempUnit.value == "Fahrenheit":
			return 'F'
		else:
			return 'C'
