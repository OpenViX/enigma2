from Components.ActionMap import HelpableActionMap
from Components.EpgList import EPG_TYPE_SINGLE
from Screens.Epg.EpgSelectionSingle import EPGSelectionSingle

# We're going to assume that EPGSelection is only used in the SingleEPG sense
class EPGSelection(EPGSelectionSingle):
	def __init__(self, session, service = None, zapFunc = None, eventid = None, bouquetChangeCB = None, serviceChangeCB = None, EPGtype = 'similar', StartBouquet = None, StartRef = None, bouquets = None):
		if EPGtype not in ('similar', 'single'):
			print "[EPGSelection] Warning: EPGSelection does not support type", EPGtype
			print "               Attempting to continue in single EPG mode"
		EPGSelectionSingle.__init__(self, session, service)

		# rewrite the EPG actions to invoke the compatibility functions
		self['epgactions'] = HelpableActionMap(self, 'EPGSelectActions',
			{
				'info': (self.Info, _('Show detailed event info')),
				'epg': (self.epgButtonPressed, _('Show detailed event info')),
				'menu': (self.createSetup, _('Setup menu'))
			}, -1)
		self['colouractions'] = HelpableActionMap(self, 'ColorActions',
			{
				'red': (self.redButtonPressed, _('IMDB search for current event')),
				'redlong': (self.redButtonPressedLong, _('Sort EPG list')),
				'green': (self.greenButtonPressed, _('Add/Remove timer for current event')),
				'greenlong': (self.greenButtonPressedLong, _('Show timer list')),
				'yellow': (self.yellowButtonPressed, _('Search for similar events')),
				'blue': (self.blueButtonPressed, _('Add an autotimer for current event')),
				'bluelong': (self.blueButtonPressedLong, _('Show autotimer list'))
			}, -1)

	# backwards compatibility functions for plugins
	# Button names
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

	# actions
	def showTimerList(self):
		self.openTimerList()

	def showAutoTimerList(self):
		self.openAutoTimerList()

	def OpenSingleEPG(self):
		self.openSingleEPG()

	def sortEpg(self):
		self.sortEPG(self)

	def RecordTimerQuestion(self, manual = False):
		self.recordTimerQuestion(manual)

	# things that need to be able to be overridden
	def refreshList(self):
		try:
			# allow plugins to override using the old all lowercase method name
			self.refreshlist()
		except AttributeError:
			EPGSelectionSingle.refreshList(self)
