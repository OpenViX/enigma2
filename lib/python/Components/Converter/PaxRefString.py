#######################################################################
#
#
#    PaxRefString for Enigma-2
#    Coded by Vali (c)2011
#
#
#  This plugin is licensed under the Creative Commons 
#  Attribution-NonCommercial-ShareAlike 3.0 Unported License.
#  To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/3.0/
#  or send a letter to Creative Commons, 559 Nathan Abbott Way, Stanford, California 94305, USA.
#
#
#######################################################################

from Components.Converter.Converter import Converter
from Components.Element import cached
from Screens.InfoBar import InfoBar

class PaxRefString(Converter, object):
	CURRENT = 0
	EVENT = 1
	
	def __init__(self, type):
		Converter.__init__(self, type)
		self.CHANSEL = None
		self.type = {
				"CurrentRef": self.CURRENT,
				"ServicelistRef": self.EVENT
			}[type]

	@cached
	def getText(self):
		if (self.type == self.EVENT):
			antw = str(self.source.service.toString())
			if antw[:6] == "1:7:0:":
				teilantw = antw.split("ORDER BY name:")
				if len(teilantw)>1:
					teil2antw = teilantw[1].split()
					if len(teil2antw)>0:
						return teil2antw[0]
			elif antw[:6] == "1:7:1:":
				teilantw = antw.split(".")
				if len(teilantw)>1:
					return teilantw[1]
			return antw
		elif (self.type == self.CURRENT):
			if self.CHANSEL == None:
				self.CHANSEL = InfoBar.instance.servicelist
			# if len(InfoBar.instance.session.dialog_stack)>1:
				# for zz in InfoBar.instance.session.dialog_stack:
					# if (str(zz[0]) == "<class 'Screens.MovieSelection.MovieSelection'>") or (str(InfoBar.instance.session.dialog_stack[1][0]) == "<class 'Screens.InfoBar.MoviePlayer'>"):
						# try:
							# return self.source.text
						# except:
							# raise Exception("error trying to return self.source.text")
			vSrv = self.CHANSEL.servicelist.getCurrent()
			return str(vSrv.toString())
		else:
			return "na"

	text = property(getText)
