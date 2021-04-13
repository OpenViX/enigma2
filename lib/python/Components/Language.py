# -*- coding: UTF-8 -*-
import gettext
import locale
import os

from Tools.Directories import SCOPE_LANGUAGE, resolveFilename

class Language:
	def __init__(self):
		gettext.install('enigma2', resolveFilename(SCOPE_LANGUAGE, ""), unicode=0, codeset="utf-8")
		gettext.bindtextdomain("enigma2", resolveFilename(SCOPE_LANGUAGE))
		gettext.textdomain("enigma2")
		self.activeLanguage = 0
		self.catalog = None
		self.lang = {}
		self.InitLang()
		self.callbacks = []

	def InitLang(self):
		self.langlist = []
		self.langlistselection = []
		# FIXME make list dynamically
		# name, iso-639 language, iso-3166 country. Please don't mix language&country!
		self.addLanguage("Arabic",	"ar", "AE", "ISO-8859-15")
		self.addLanguage("Български",	"bg", "BG", "ISO-8859-15")
		self.addLanguage("Català",	"ca", "AD", "ISO-8859-15")
		self.addLanguage("Česky",	"cs", "CZ", "ISO-8859-15")
		self.addLanguage("Dansk",	"da", "DK", "ISO-8859-15")
		self.addLanguage("Deutsch",	"de", "DE", "ISO-8859-15")
		self.addLanguage("Ελληνικά",	"el", "GR", "ISO-8859-7")
		self.addLanguage("English",	"en", "EN", "ISO-8859-15")
		self.addLanguage("Español",	"es", "ES", "ISO-8859-15")
		self.addLanguage("Eesti",	"et", "EE", "ISO-8859-15")
		self.addLanguage("فارسی",	"fa", "IR", "UTF-8")
		self.addLanguage("Suomi",	"fi", "FI", "ISO-8859-15")
		self.addLanguage("Français",	"fr", "FR", "ISO-8859-15")
		self.addLanguage("Frysk",	"fy", "NL", "ISO-8859-15")
		self.addLanguage("Galician",	"gl", "ES", "ISO-8859-15")
		self.addLanguage("Hebrew",	"he", "IL", "ISO-8859-15")
		self.addLanguage("Hrvatski",	"hr", "HR", "ISO-8859-15")
		self.addLanguage("Magyar",	"hu", "HU", "ISO-8859-15")
		self.addLanguage("Indonesian",	"id", "ID", "ISO-8859-15")
		self.addLanguage("Íslenska",	"is", "IS", "ISO-8859-15")
		self.addLanguage("Italiano",	"it", "IT", "ISO-8859-15")
		self.addLanguage("Kurdish",	"ku", "KU", "ISO-8859-15")
		self.addLanguage("Lietuvių",	"lt", "LT", "ISO-8859-15")
		self.addLanguage("Latviešu",	"lv", "LV", "ISO-8859-15")
		self.addLanguage("Македонски",	"mk", "MK", "ISO-8859-5")
		self.addLanguage("Nederlands",	"nl", "NL", "ISO-8859-15")
		self.addLanguage("Norsk Bokmål","nb", "NO", "ISO-8859-15")
		self.addLanguage("Norsk Nynorsk", "nn", "NO", "ISO-8859-15")
		self.addLanguage("Polski",	"pl", "PL", "ISO-8859-15")
		self.addLanguage("Português",	"pt", "PT", "ISO-8859-15")
		self.addLanguage("Português do Brasil","pt", "BR", "ISO-8859-15")
		self.addLanguage("Romanian",	"ro", "RO", "ISO-8859-15")
		self.addLanguage("Русский",	"ru", "RU", "ISO-8859-15")
		self.addLanguage("Slovensky",	"sk", "SK", "ISO-8859-15")
		self.addLanguage("Slovenščina",	"sl", "SI", "ISO-8859-15")
		self.addLanguage("Srpski",	"sr", "YU", "ISO-8859-15")
		self.addLanguage("Svenska",	"sv", "SE", "ISO-8859-15")
		self.addLanguage("ภาษาไทย",	"th", "TH", "ISO-8859-15")
		self.addLanguage("Türkçe",	"tr", "TR", "ISO-8859-15")
		self.addLanguage("Українська",	"uk", "UA", "ISO-8859-15")
		self.addLanguage("Tiếng Việt",	"vi", "VN", "UTF-8")
		self.addLanguage("SChinese",	"zh", "CN", "UTF-8")
		self.addLanguage("TChinese",	"zh", "HK", "UTF-8")

	def addLanguage(self, name, lang, country, encoding):
		try:
			self.lang[str(lang + "_" + country)] = ((name, lang, country, encoding))
			self.langlist.append(str(lang + "_" + country))
		except:
			print "Language " + str(name) + " not found"
		self.langlistselection.append((str(lang + "_" + country), name))

	def activateLanguage(self, index):
		try:
			if index not in self.lang:
				print "Selected language %s does not exist, fallback to en_EN!" % index
				index = "en_EN"
			lang = self.lang[index]
			if not os.path.exists(resolveFilename(SCOPE_LANGUAGE, lang[1])):
				print "Language %s is not installed. Try to install it now." % lang[0]
				os.system("opkg install enigma2-locale-%s" % lang[1])
				self.delLanguage()
			print "Activating language " + lang[0]
			os.environ["LANGUAGE"] = lang[1] # set languange in order gettext to work properly on external plugins
			self.catalog = gettext.translation('enigma2', resolveFilename(SCOPE_LANGUAGE, ""), languages=[index], fallback=True)
			self.catalog.install(names=("ngettext", "pgettext"))
			self.activeLanguage = index
			for x in self.callbacks:
				x()
		except:
			print "Error in activating language!"
		# NOTE: we do not use LC_ALL, because LC_ALL will not set any of the categories, when one of the categories fails.
		# We'd rather try to set all available categories, and ignore the others
		for category in [locale.LC_CTYPE, locale.LC_COLLATE, locale.LC_TIME, locale.LC_MONETARY, locale.LC_MESSAGES, locale.LC_NUMERIC]:
			try:
				locale.setlocale(category, (self.getLanguage(), 'UTF-8'))
			except:
				pass
		# HACK: sometimes python 2.7 reverts to the LC_TIME environment value, so make sure it has the correct value
		os.environ["LC_TIME"] = self.getLanguage() + '.UTF-8'
		os.environ["LANGUAGE"] = self.getLanguage() + '.UTF-8'
		os.environ["GST_SUBTITLE_ENCODING"] = self.getGStreamerSubtitleEncoding()

	def activateLanguageIndex(self, index):
		if index < len(self.langlist):
			self.activateLanguage(self.langlist[index])

	def getLanguageList(self):
		return [ (x, self.lang[x]) for x in self.langlist ]

	def getLanguageListSelection(self):
		return self.langlistselection

	def getActiveLanguage(self):
		return self.activeLanguage

	def getActiveCatalog(self):
		return self.catalog

	def getActiveLanguageIndex(self):
		idx = 0
		for x in self.langlist:
			if x == self.activeLanguage:
				return idx
			idx += 1
		return None

	def getLanguage(self):
		try:
			return str(self.lang[self.activeLanguage][1]) + "_" + str(self.lang[self.activeLanguage][2])
		except:
			return ''

	def getGStreamerSubtitleEncoding(self):
		try:
			return str(self.lang[self.activeLanguage][3])
		except:
			return 'ISO-8859-15'

	def addCallback(self, callback):
		self.callbacks.append(callback)

	def delLanguage(self, delLang=None):
		from Components.config import config, configfile

		LPATH = resolveFilename(SCOPE_LANGUAGE, "")
		Lpackagename = "enigma2-locale-"
		lang = config.osd.language.value

		if delLang:
			print"DELETE LANG", delLang
			if delLang == "en_US" or delLang == "de_DE":
				print"Default Language can not be deleted !!"
				return
			elif delLang == "en_GB" or delLang == "pt_BR":
				delLang = delLang.lower()
				delLang = delLang.replace('_','-')
				os.system("opkg remove --autoremove --force-depends " + Lpackagename + delLang)
			else:
				os.system("opkg remove --autoremove --force-depends " + Lpackagename + delLang[:2])
		else:
			print"Delete all lang except ", lang
			ll = os.listdir(LPATH)
			for x in ll:
				if len(x) > 2:
					if x != lang and x != "de":
						x = x.lower()
						x = x.replace('_','-')
						os.system("opkg remove --autoremove --force-depends " + Lpackagename + x)
				else:
					if x != lang[:2] and x != "en" and x != "de":
						os.system("opkg remove --autoremove --force-depends " + Lpackagename + x)
					elif x == "pt":
						if x != lang:
							os.system("opkg remove --autoremove --force-depends " + Lpackagename + x)

language = Language()
