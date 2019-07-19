#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#######################################################################
#
#    MetrixWeatherSetup for Enigma2
#    Coded by Sinthex IT-Solutions (c) 2014
#    www.open-store.net
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
from Screens.Screen import Screen
from Components.Renderer import OMMetrixWeatherWidget
from Components.Label import Label
from Components.config import ConfigSelection, getConfigListEntry, config, configfile, ConfigSubsection, ConfigNumber, ConfigSelectionNumber, ConfigYesNo, ConfigText
from Components.ConfigList import ConfigListScreen
from Components.ActionMap import ActionMap
from Components.Sources.StaticText import StaticText

class OMMetrixWeatherSetup(Screen,ConfigListScreen):
	skin = """
		<screen name="MetrixWeatherSetup" position="160,150" size="450,200" title="Weather Setup">
			<ePixmap pixmap="buttons/red.png" position="10,0" size="140,40" alphatest="on" />
			<ePixmap pixmap="buttons/green.png" position="300,0" size="140,40" alphatest="on" />
			<widget source="key_red" render="Label" position="10,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
			<widget source="key_green" render="Label" position="300,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" />
			<widget name="config" position="10,44" size="430,146" />
		</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Save"))

		ConfigListScreen.__init__(self, [])
		self.initConfigList()

		self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
			"green": self.save,
			"red": self.exit,
			"cancel": self.close},-1)

	def save(self):
		config.plugins.MetrixWeather.lastUpdated.value = "2000-01-01 01:01:01"
		config.plugins.MetrixWeather.save()
		configfile.save()
		self.close()

	def initConfigList(self):
		self.list = []
		self.list.append(getConfigListEntry(_("Show Weather Widget"), config.plugins.MetrixWeather.enabled))
		self.list.append(getConfigListEntry(_("MSN Weather City Name"), config.plugins.MetrixWeather.weathercity))
		self.list.append(getConfigListEntry(_("Unit"), config.plugins.MetrixWeather.tempUnit))
		self["config"].setList(self.list)

	def exit(self):
		for x in self["config"].list:
			if len(x) > 1:
				x[1].cancel()
			else:
				pass
		self.close()
