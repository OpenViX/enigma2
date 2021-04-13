# -*- coding: UTF-8 -*-
from __future__ import print_function
from __future__ import absolute_import

import gettext
import locale
import os
from time import time, localtime, strftime
from Tools.Directories import SCOPE_LANGUAGE, resolveFilename

LPATH = resolveFilename(SCOPE_LANGUAGE, "")
Lpackagename = "enigma2-locale-"


class Language:
	def __init__(self):
		gettext.install('enigma2', resolveFilename(SCOPE_LANGUAGE, ""), codeset="utf-8")
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
		self.ll = os.listdir(LPATH)
		# FIXME make list dynamically
		# name, iso-639 language, iso-3166 country. Please don't mix language&country!
		self.addLanguage("Arabic", "ar", "AE", "ISO-8859-15")
		self.addLanguage("Български", "bg", "BG", "ISO-8859-15")
		self.addLanguage("Bokmål", "nb", "NO", "ISO-8859-15")
		self.addLanguage("Català", "ca", "AD", "ISO-8859-15")
		self.addLanguage("Česky", "cs", "CZ", "ISO-8859-15")
		self.addLanguage("SChinese", "zh", "CN", "UTF-8")
		self.addLanguage("TChinese", "zh", "HK", "UTF-8")
		self.addLanguage("Dansk", "da", "DK", "ISO-8859-15")
		self.addLanguage("Deutsch", "de", "DE", "ISO-8859-15")
		self.addLanguage("Ελληνικά", "el", "GR", "ISO-8859-7")
		self.addLanguage("English (AU)", "en", "AU", "ISO-8859-1")
		self.addLanguage("English (UK)", "en", "GB", "ISO-8859-15")
		self.addLanguage("English (US)", "en", "US", "ISO-8859-15")
		self.addLanguage("Español", "es", "ES", "ISO-8859-15")
		self.addLanguage("Eesti", "et", "EE", "ISO-8859-15")
		self.addLanguage("Persian", "fa", "IR", "ISO-8859-15")
		self.addLanguage("Suomi", "fi", "FI", "ISO-8859-15")
		self.addLanguage("Français", "fr", "FR", "ISO-8859-15")
		self.addLanguage("Frysk", "fy", "NL", "ISO-8859-15")
		self.addLanguage("Hebrew", "he", "IL", "ISO-8859-15")
		self.addLanguage("Hrvatski", "hr", "HR", "ISO-8859-15")
		self.addLanguage("Magyar", "hu", "HU", "ISO-8859-15")
		self.addLanguage("Indonesian", "id", "ID", "ISO-8859-15")
		self.addLanguage("Íslenska", "is", "IS", "ISO-8859-15")
		self.addLanguage("Italiano", "it", "IT", "ISO-8859-15")
		self.addLanguage("Kurdish", "ku", "KU", "ISO-8859-15")
		self.addLanguage("Lietuvių", "lt", "LT", "ISO-8859-15")
		self.addLanguage("Latviešu", "lv", "LV", "ISO-8859-15")
		self.addLanguage("Nederlands", "nl", "NL", "ISO-8859-15")
		self.addLanguage("Norsk Bokmål", "nb", "NO", "ISO-8859-15")
		self.addLanguage("Norsk", "no", "NO", "ISO-8859-15")
		self.addLanguage("Polski", "pl", "PL", "ISO-8859-15")
		self.addLanguage("Português", "pt", "PT", "ISO-8859-15")
		self.addLanguage("Português do Brasil", "pt", "BR", "ISO-8859-15")
		self.addLanguage("Romanian", "ro", "RO", "ISO-8859-15")
		self.addLanguage("Русский", "ru", "RU", "ISO-8859-15")
		self.addLanguage("Slovensky", "sk", "SK", "ISO-8859-15")
		self.addLanguage("Slovenščina", "sl", "SI", "ISO-8859-15")
		self.addLanguage("Srpski", "sr", "YU", "ISO-8859-15")
		self.addLanguage("Svenska", "sv", "SE", "ISO-8859-15")
		self.addLanguage("ภาษาไทย", "th", "TH", "ISO-8859-15")
		self.addLanguage("Türkçe", "tr", "TR", "ISO-8859-15")
		self.addLanguage("Українська", "uk", "UA", "ISO-8859-15")
		self.addLanguage("Tiếng Việt", "vi", "VN", "UTF-8")

	def addLanguage(self, name, lang, country, encoding):
		try:
			if lang in self.ll or (lang + "_" + country) in self.ll:
				self.lang[str(lang + "_" + country)] = ((name, lang, country, encoding))
				self.langlist.append(str(lang + "_" + country))

		except:
			print("[Language] Language " + str(name) + " not found")
		self.langlistselection.append((str(lang + "_" + country), name))

	def activateLanguage_TRY(self, index):
		try:
			if index not in self.lang:
				print("[Language] Selected language %s is not installed, fallback to en_US!" % index)
				index = "en_US"
				Notifications.AddNotification(MessageBox, _("The selected langugage is unavailable - using en_US"), MessageBox.TYPE_INFO, timeout=3)
			lang = self.lang[index]
			print("[Language] Activating language " + lang[0])
			self.catalog = gettext.translation('enigma2', resolveFilename(SCOPE_LANGUAGE, ""), languages=[index], fallback=True)
			self.catalog.install(names=("ngettext", "pgettext"))
			self.activeLanguage = index
			for x in self.callbacks:
				if x:
					x()
		except:
			print("[Language] Selected language does not exist!")
			return False

		# NOTE: we do not use LC_ALL, because LC_ALL will not set any of the categories, when one of the categories fails.
		# We'd rather try to set all available categories, and ignore the others
		for category in [locale.LC_CTYPE, locale.LC_COLLATE, locale.LC_TIME, locale.LC_MONETARY, locale.LC_MESSAGES, locale.LC_NUMERIC]:
			try:
				locale.setlocale(category, (self.getLanguage(), 'UTF-8'))
			except:
				pass

		# Also write a locale.conf as /home/root/.config/locale.conf to apply language to interactive shells as well:
		try:
			os.stat('/home/root/.config')
		except:
			os.mkdir('/home/root/.config')

		localeconf = open('/home/root/.config/locale.conf', 'w')
		for category in ["LC_TIME", "LC_DATE", "LC_MONETARY", "LC_MESSAGES", "LC_NUMERIC", "LC_NAME", "LC_TELEPHONE", "LC_ADDRESS", "LC_PAPER", "LC_IDENTIFICATION", "LC_MEASUREMENT", "LANG"]:
			if category == "LANG" or (category == "LC_DATE" and os.path.exists('/usr/lib/locale/' + self.getLanguage() + '/LC_TIME')) or os.path.exists('/usr/lib/locale/' + self.getLanguage() + '/' + category):
				localeconf.write('export %s="%s.%s"\n' % (category, self.getLanguage(), "UTF-8"))
			else:
				if os.path.exists('/usr/lib/locale/C.UTF-8/' + category):
					localeconf.write('export %s="C.UTF-8"\n' % category)
				else:
					localeconf.write('export %s="POSIX"\n' % category)
		localeconf.close()
		# HACK: sometimes python 2.7 reverts to the LC_TIME environment value, so make sure it has the correct value
		os.environ["LC_TIME"] = self.getLanguage() + '.UTF-8'
		os.environ["LANGUAGE"] = self.getLanguage() + '.UTF-8'
		os.environ["GST_SUBTITLE_ENCODING"] = self.getGStreamerSubtitleEncoding()
		return True

	def activateLanguage(self, index):
		from Tools import Notifications
		from Screens.MessageBox import MessageBox
		if not self.activateLanguage_TRY(index):
			print("[Language] - retry with ", "en_US")
			Notifications.AddNotification(MessageBox, _("The selected langugage is unavailable - using en_US"), MessageBox.TYPE_INFO, timeout=3)
			self.activateLanguage_TRY("en_US")

	def activateLanguageIndex(self, index):
		if index < len(self.langlist):
			self.activateLanguage(self.langlist[index])

	def getLanguageList(self):
		return [(x, self.lang[x]) for x in self.langlist]

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
		from shutil import rmtree

		if delLang:
			lang = config.osd.language.value
			print("[Language] DELETE LANG", delLang)
			if delLang[:2] == "en":
				print("[Language] Default Language can not be deleted !!")
				return
			elif delLang == "pt_BR":
				delLang = delLang.lower()
				delLang = delLang.replace('_', '-')
				os.system("opkg remove --autoremove --force-depends " + Lpackagename + delLang)
			else:
				os.system("opkg remove --autoremove --force-depends " + Lpackagename + delLang[:2])
		else:
			lang = self.activeLanguage
			print("[Language] Delete all lang except ", lang)
			ll = os.listdir(LPATH)
			for x in ll:
				if len(x) > 2:
					if x != lang and x[:2] != "en":
						x = x.lower()
						x = x.replace('_', '-')
						os.system("opkg remove --autoremove --force-depends " + Lpackagename + x)
				else:
					if x != lang[:2] and x != "en":
						os.system("opkg remove --autoremove --force-depends " + Lpackagename + x)
					elif x == "pt":
						if x != lang:
							os.system("opkg remove --autoremove --force-depends " + Lpackagename + x)

		os.system("touch /etc/enigma2/.removelang")

		self.InitLang()

	def updateLanguageCache(self):
		t = localtime(time())
		createdate = strftime("%d.%m.%Y  %H:%M:%S", t)
		f = open('/usr/lib/enigma2/python/Components/Language_cache.py', 'w')
		f.write('# -*- coding: UTF-8 -*-\n')
		f.write('# date: ' + createdate + '\n#\n\n')
		f.write('LANG_TEXT = {\n')
		for lang in self.langlist:
			catalog = gettext.translation('enigma2', resolveFilename(SCOPE_LANGUAGE, ""), languages=[str(lang)], fallback=True)
			T1 = catalog.gettext("Use the UP and DOWN keys to select language, Menu key to install new language. Afterwards press the OK button.")
			T2 = catalog.gettext("Language selection")
			T3 = catalog.gettext("Cancel")
			T4 = catalog.gettext("Save")
			f.write('"' + lang + '"' + ': {\n')
			f.write('\t "T1"' + ': "' + T1 + '",\n')
			f.write('\t "T2"' + ': "' + T2 + '",\n')
			f.write('\t "T3"' + ': "' + T3 + '",\n')
			f.write('\t "T4"' + ': "' + T4 + '",\n')
			f.write('},\n')
		f.write('}\n')
		f.close
		catalog = None
		lang = None


language = Language()
