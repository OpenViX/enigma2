from __future__ import print_function
from Components.ActionMap import HelpableActionMap
from Components.EpgList import EPG_TYPE_SINGLE
from Screens.EpgSelectionChannel import EPGSelectionChannel


# Keep for backwards compatibility with plugins, including the parameter naming.
# This class assumes that EPGSelection is only used in the SingleEPG sense.
class EPGSelection(EPGSelectionChannel):
	def __init__(self, session, service=None, zapFunc=None, eventid=None, bouquetChangeCB=None, serviceChangeCB=None, EPGtype="similar", StartBouquet=None, StartRef=None, bouquets=None):
		if EPGtype not in ("similar", "single"):
			print("[EPGSelection] Warning: EPGSelection does not support type '%s'" % EPGtype)
			print("               Attempting to continue in single EPG mode")
		EPGSelectionChannel.__init__(self, session, service)

		# Rewrite the EPG actions to invoke the compatibility functions.
		helpDescription = _("EPG Commands")
		self["epgactions"] = HelpableActionMap(self, "EPGSelectActions", {
			"info": (self.Info, _("Show detailed event info")),
			"epg": (self.epgButtonPressed, _("Show detailed event info")),
			"menu": (self.createSetup, _("Setup menu"))
		}, prio=-1, description=helpDescription)
		self["colouractions"] = HelpableActionMap(self, "ColorActions", {
			"red": (self.redButtonPressed, _("IMDB search for current event")),
			"redlong": (self.redButtonPressedLong, _("Sort EPG list")),
			"green": (self.greenButtonPressed, _("Add/Remove timer for current event")),
			"greenlong": (self.greenButtonPressedLong, _("Show timer list")),
			"yellow": (self.yellowButtonPressed, _("Search for similar events")),
			"blue": (self.blueButtonPressed, _("Add an autotimer for current event")),
			"bluelong": (self.blueButtonPressedLong, _("Show autotimer list"))
		}, prio=-1, description=helpDescription)

	# Backwards compatibility properties for plugins.
	@property
	def ChoiceBoxDialog(self):
		return self.choiceBoxDialog

	@ChoiceBoxDialog.setter
	def ChoiceBoxDialog(self, value):
		self.choiceBoxDialog = value

	# Backwards compatibility functions for plugins.
	# Button names.
	def redButtonPressed(self):
		self.openIMDb()

	def redButtonPressedLong(self):
		self.sortEpg()

	def greenButtonPressed(self):
		self.addEditTimer()

	def greenButtonPressedLong(self):
		self.showTimerList()

	def yellowButtonPressed(self):
		self.openEPGSearch()

	def blueButtonPressed(self):
		self.addAutoTimer()

	def blueButtonPressedLong(self):
		self.showAutoTimerList()

	def Info(self):
		self.infoKeyPressed()

	def InfoLong(self):
		self.OpenSingleEPG()

	def infoKeyPressed(self):
		self.openEventView()

	def epgButtonPressed(self):
		self.openEventView()

	# Actions
	def showTimerList(self):
		self.openTimerList()

	def showAutoTimerList(self):
		self.openAutoTimerList()

	def OpenSingleEPG(self):
		self.openSingleEPG()

	def sortEpg(self):
		self.sortEPG(self)

	def timerAdd(self):
		self.addEditTimerMenu()

	def doRecordTimer(self):
		self.doInstantTimer(0)

	def doZapTimer(self):
		self.doInstantTimer(1)

	def RecordTimerQuestion(self, manual=False):
		if manual:
			self.addEditTimer()
		else:
			self.addEditTimerMenu()

	# Things that need to be able to be overridden.
	def refreshList(self):
		try:
			# Allow plugins to override using the old all lowercase method name.
			self.refreshlist()
		except AttributeError:
			EPGSelectionChannel.refreshList(self)
