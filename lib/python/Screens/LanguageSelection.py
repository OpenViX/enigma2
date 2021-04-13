from enigma import eTimer
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.config import config
from Components.Label import Label
from Components.Language import language
from Components.Language_cache import LANG_TEXT
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Components.Pixmap import Pixmap
from Screens.InfoBar import InfoBar
from Screens.MessageBox import MessageBox
from Screens.Rc import Rc
from Screens.Standby import TryQuitMainloop
from Tools.Directories import resolveFilename, SCOPE_ACTIVE_SKIN
from Tools.LoadPixmap import LoadPixmap
import gettext

inWizzard = False


def LanguageEntryComponent(file, name, index):
	png = LoadPixmap(resolveFilename(SCOPE_ACTIVE_SKIN, "countries/" + index + ".png"))
	if png is None:
		png = LoadPixmap(resolveFilename(SCOPE_ACTIVE_SKIN, "countries/" + file + ".png"))
		if png is None:
			png = LoadPixmap(resolveFilename(SCOPE_ACTIVE_SKIN, "countries/missing.png"))
	res = (index, name, png)
	return res


def _cached(x):
	return LANG_TEXT.get(config.osd.language.value, {}).get(x, "")


class LanguageSelection(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle(_("Language"))

		language.InitLang()
		self.oldActiveLanguage = language.getActiveLanguage()
		self.catalog = language.getActiveCatalog()

		self.list = []
		self["summarylangname"] = StaticText()
		self["summarylangsel"] = StaticText()
		self["languages"] = List(self.list)
		self["languages"].onSelectionChanged.append(self.changed)

		self.updateList()
		self.onLayoutFinish.append(self.selectActiveLanguage)

		self["key_red"] = Label("")
		self["key_green"] = Label("")
		self["key_yellow"] = Label(_("Add Language"))
		self["key_blue"] = Label(_("Delete Language(s)"))
		self["description"] = Label(_("'Save' changes active language.\n'Add Language' or MENU adds additional language(s).\n'Delete Language' allows either deletion of all but English and active language OR selected language"))

		self["actions"] = ActionMap(["SetupActions", "ColorActions"],
		{
			"ok": self.save,
			"cancel": self.cancel,
			"red": self.cancel,
			"green": self.save,
			"yellow": self.installLanguage,
			"blue": self.delLang,
			"menu": self.installLanguage,
		}, -1)

	def updateCache(self):
#		print "[LanguageSelection] updateCache"
		self["languages"].setList([('update cache', _('Updating cache, please wait...'), None)])
		self.updateTimer = eTimer()
		self.updateTimer.callback.append(self.startupdateCache)
		self.updateTimer.start(100)

	def startupdateCache(self):
		self.updateTimer.stop()
		language.updateLanguageCache()
		self["languages"].setList(self.list)
		self.selectActiveLanguage()

	def selectActiveLanguage(self):
		activeLanguage = language.getActiveLanguage()
		pos = 0
		for pos, x in enumerate(self.list):
			if x[0] == activeLanguage:
				self["languages"].index = pos
				break

	def save(self):
		self.run()
		global inWizzard
#		print "[LanguageSelection] save function inWizzard is %s", %inWizzard
		if inWizzard:
			inWizzard = False
			#self.session.openWithCallback(self.deletelanguagesCB, MessageBox, _("Do you want to delete all other languages?"), default = False)
			if self.oldActiveLanguage != config.osd.language.value:
				self.session.open(TryQuitMainloop, 3)
			self.close()
		else:
			if self.oldActiveLanguage != config.osd.language.value:
				self.session.openWithCallback(self.restartGUI, MessageBox, _("GUI needs a restart to apply a new language\nDo you want to restart the GUI now?"), MessageBox.TYPE_YESNO)
			else:
				self.close()

	def restartGUI(self, answer=True):
		if answer is True:
			self.session.open(TryQuitMainloop, 3)
		else:
			self.close()

	def cancel(self):
		language.activateLanguage(self.oldActiveLanguage)
		config.osd.language.setValue(self.oldActiveLanguage)
		config.osd.language.save()
		self.close()

	def delLang(self):
#		print "[LanguageSelection] deleting language"
		curlang = config.osd.language.value
		lang = curlang
		languageList = language.getLanguageListSelection()
#		print "[LanguageSelection] deleting language  lang = %s, languagelist = %s", %(lang, languageList)
		for t in languageList:
			if curlang == t[0]:
				lang = t[1]
				break
		self.session.openWithCallback(self.delLangCB, MessageBox, _("Select 'Yes' to delete all languages except English and current language:\n\nSelect 'No' to delete only the chosen language:\n\n") + _("%s") % (lang), default=True)

	def delLangCB(self, answer):
		if answer:
			language.delLanguage()
			language.activateLanguage(self.oldActiveLanguage)
			self.updateList()
			self.selectActiveLanguage()
		else:
			curlang = config.osd.language.value
			lang = curlang
			languageList = language.getLanguageListSelection()
	#		print "[LanguageSelection] deleting language  lang = %s, languagelist = %s", %(lang, languageList)
			for t in languageList:
				if curlang == t[0]:
					lang = t[1]
					break
			self.session.openWithCallback(self.deletelanguagesCB, MessageBox, _("Do you really want to delete selected language:\n\n") + _("%s") % (lang), default=False)

	def deletelanguagesCB(self, answer):
		if answer:
			curlang = config.osd.language.value
			lang = curlang
			language.delLanguage(delLang=lang)
			language.activateLanguage(self.oldActiveLanguage)
			self.updateList()
			self.selectActiveLanguage()
#		self.close()

	def run(self, justlocal=False):
#		print "[LanguageSelection] updating language..."
		lang = self["languages"].getCurrent()[0]

		if lang == 'update cache':
			self.setTitle(_("Updating Cache"))
			self["summarylangname"].setText(_("Updating cache"))
			return

		if lang != config.osd.language.value:
			config.osd.language.setValue(lang)
			config.osd.language.save()

		self.setTitle(_cached("T2"))
		self["summarylangname"].setText(_cached("T2"))
		self["summarylangsel"].setText(self["languages"].getCurrent()[1])
		self["key_red"].setText(_cached("T3"))
		self["key_green"].setText(_cached("T4"))

		if justlocal:
			return

		language.activateLanguage(lang)
		config.misc.languageselected.value = 0
		config.misc.languageselected.save()

	def updateList(self):
		languageList = language.getLanguageList()
		if not languageList: # no language available => display only english
			list = [LanguageEntryComponent("en", "English (UK)", "en_GB")]
		else:
			list = [LanguageEntryComponent(file=x[1][2].lower(), name=x[1][0], index=x[0]) for x in languageList]
		self.list = list
		self["languages"].list = list

	def installLanguage(self):
		from Screens.PluginBrowser import PluginDownloadBrowser
		self.session.openWithCallback(self.update_after_installLanguage, PluginDownloadBrowser, 0)

	def update_after_installLanguage(self):
		language.InitLang()
		self.updateList()
		self.updateCache()

	def changed(self):
		self.run(justlocal=True)


class LanguageWizard(LanguageSelection, Rc):
	def __init__(self, session):
		LanguageSelection.__init__(self, session)
		Rc.__init__(self)
		global inWizzard
		inWizzard = True
		self.onLayoutFinish.append(self.selectKeys)

		self["wizard"] = Pixmap()
		self["summarytext"] = StaticText()
		self["text"] = Label()
		self.setText()

	def selectKeys(self):
		self.clearSelectedKeys()
		self.selectKey("UP")
		self.selectKey("DOWN")

	def changed(self):
		self.run(justlocal=True)
		self.setText()

	def setText(self):
		self["text"].setText(_cached("T1"))
		self["summarytext"].setText(_cached("T1"))

	def createSummary(self):
		return LanguageWizardSummary


class LanguageWizardSummary(Screen):
	def __init__(self, session, parent):
		Screen.__init__(self, session, parent)
