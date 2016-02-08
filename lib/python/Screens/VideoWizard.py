from boxbranding import getBoxType, getMachineName
from Screens.Wizard import WizardSummary
from Screens.WizardLanguage import WizardLanguage
from Screens.Rc import Rc
from Components.AVSwitch import iAVSwitch

from Components.Pixmap import Pixmap
from Components.config import config, ConfigBoolean, configfile

from Tools.Directories import resolveFilename, SCOPE_SKIN, SCOPE_ACTIVE_SKIN
from Tools.HardwareInfo import HardwareInfo

config.misc.showtestcard = ConfigBoolean(default = False)

boxtype = getBoxType()

has_rca = False
has_dvi = False
if boxtype == 'gbquad' or boxtype == 'gbquadplus' or boxtype == 'et5x00' or boxtype == 'et6000' or boxtype == 'e3hd' or boxtype == 'odinm6' or getMachineName() == 'AX-Odin' or boxtype == 'ebox7358' or boxtype == 'eboxlumi' or boxtype == 'tmnano' or boxtype == 'ultra' or boxtype == "me" or boxtype == "minime" or boxtype == 'optimussos1' or boxtype == 'optimussos2' or boxtype == 'gb800seplus' or boxtype == 'gb800ueplus' or boxtype == 'ini-1000ru' or boxtype == 'ini-1000sv' or boxtype == 'ixussone' or boxtype == 'ixusszero' or boxtype == 'enfinity' or boxtype == 'force1':	
	has_rca = True
if boxtype == 'dm8000' or boxtype == 'dm800':
	has_dvi = True

class VideoWizardSummary(WizardSummary):
	def __init__(self, session, parent):
		WizardSummary.__init__(self, session, parent)

	def setLCDPicCallback(self):
		self.parent.setLCDTextCallback(self.setText)

	def setLCDPic(self, file):
		self["pic"].instance.setPixmapFromFile(file)

class VideoWizard(WizardLanguage, Rc):
	skin = """
		<screen position="fill" title="Welcome..." flags="wfNoBorder" >
			<panel name="WizardMarginsTemplate"/>
			<panel name="WizardPictureLangTemplate"/>
			<panel name="RemoteControlTemplate"/>
			<panel position="left" size="10,*" />
			<panel position="right" size="10,*" />
			<panel position="fill">
				<widget name="text" position="top" size="*,270" font="Regular;23" valign="center" />
				<panel position="fill">
					<panel position="left" size="150,*">
						<widget name="portpic" position="top" zPosition="10" size="150,150" transparent="1" alphatest="on"/>
					</panel>
					<panel position="fill" layout="stack">
						<widget source="list" render="Listbox" position="fill" scrollbarMode="showOnDemand" >
							<convert type="StringList" />
						</widget>
						<!--<widget name="config" position="fill" zPosition="1" scrollbarMode="showOnDemand" />-->
					</panel>
				</panel>
			</panel>
		</screen>"""

	def __init__(self, session):
		# FIXME anyone knows how to use relative paths from the plugin's directory?
		self.xmlfile = resolveFilename(SCOPE_SKIN, "videowizard.xml")
		self.hw = iAVSwitch

		WizardLanguage.__init__(self, session, showSteps = False, showStepSlider = False)
		Rc.__init__(self)
		self["wizard"] = Pixmap()
		self["portpic"] = Pixmap()

		self.port = None
		self.mode = None
		self.rate = None

	def createSummary(self):
		print "[VideoWizard] createSummary"
		return VideoWizardSummary

	def markDone(self):
		self.hw.saveMode(self.port, self.mode, self.rate)
		config.misc.videowizardenabled.value = 0
		config.misc.videowizardenabled.save()
		configfile.save()

	def listInputChannels(self):
		hw_type = HardwareInfo().get_device_name()
		has_hdmi = HardwareInfo().has_hdmi()
		list = []

		for port in self.hw.getPortList():
			if self.hw.isPortUsed(port):
				descr = port
				if descr == 'HDMI' and has_dvi:
					descr = 'DVI'
				elif descr == 'Scart' and has_rca:
					descr = 'RCA'					
				if port != "DVI-PC":
					list.append((descr,port))
		list.sort(key = lambda x: x[0])
		print "[VideoWizard] listInputChannels:", list
		return list

	def inputSelectionMade(self, index):
		print "[VideoWizard] inputSelectionMade:", index
		self.port = index
		self.inputSelect(index)

	def inputSelectionMoved(self):
		hw_type = HardwareInfo().get_device_name()
		has_hdmi = HardwareInfo().has_hdmi()
		print "[VideoWizard] input selection moved:", self.selection
		self.inputSelect(self.selection)
		if self["portpic"].instance is not None:
			picname = self.selection
			if picname == 'HDMI' and has_dvi:
				picname = "DVI"
			elif picname == 'Scart' and has_rca:
				picname = "RCA"	
			self["portpic"].instance.setPixmapFromFile(resolveFilename(SCOPE_ACTIVE_SKIN, "icons/" + picname + ".png"))

	def inputSelect(self, port):
		print "[VideoWizard] inputSelect:", port
		modeList = self.hw.getModeList(self.selection)
		print "[VideoWizard] modeList:", modeList
		self.port = port
		if len(modeList) > 0:
			ratesList = self.listRates(modeList[0][0])
			self.hw.setMode(port = port, mode = modeList[0][0], rate = ratesList[0][0])

	def listModes(self):
		list = []
		print "[VideoWizard] modes for port", self.port
		for mode in self.hw.getModeList(self.port):
			#if mode[0] != "PC":
				list.append((mode[0], mode[0]))
		print "[VideoWizard] modeslist:", list
		return list

	def modeSelectionMade(self, index):
		print "[VideoWizard] modeSelectionMade:", index
		self.mode = index
		self.modeSelect(index)

	def modeSelectionMoved(self):
		print "[VideoWizard] mode selection moved:", self.selection
		self.modeSelect(self.selection)

	def modeSelect(self, mode):
		ratesList = self.listRates(mode)
		print "[VideoWizard] ratesList:", ratesList
		if self.port == "HDMI" and mode in ("720p", "1080i", "1080p", "2160p"):
			self.rate = "multi"
			self.hw.setMode(port = self.port, mode = mode, rate = "multi")
		else:
			self.hw.setMode(port = self.port, mode = mode, rate = ratesList[0][0])

	def listRates(self, querymode = None):
		if querymode is None:
			querymode = self.mode
		list = []
		print "[VideoWizard] modes for port", self.port, "and mode", querymode
		for mode in self.hw.getModeList(self.port):
			print "[VideoWizard] mode:", mode
			if mode[0] == querymode:
				for rate in mode[1]:
					if self.port == "DVI-PC":
						print "[VideoWizard] rate:", rate
						if rate == "640x480":
							list.insert(0, (rate, rate))
							continue
					list.append((rate, rate))
		return list

	def rateSelectionMade(self, index):
		print "[VideoWizard] rateSelectionMade:", index
		self.rate = index
		self.rateSelect(index)

	def rateSelectionMoved(self):
		print "[VideoWizard] rate selection moved:", self.selection
		self.rateSelect(self.selection)

	def rateSelect(self, rate):
		self.hw.setMode(port = self.port, mode = self.mode, rate = rate)

	def showTestCard(self, selection = None):
		if selection is None:
			selection = self.selection
		print "[VideoWizard] set config.misc.showtestcard to", {'yes': True, 'no': False}[selection]
		if selection == "yes":
			config.misc.showtestcard.value = True
		else:
			config.misc.showtestcard.value = False

	def keyNumberGlobal(self, number):
		if number in (1,2,3):
			if number == 1:
				self.hw.saveMode("HDMI", "720p", "multi")
			elif number == 2:
				self.hw.saveMode("HDMI", "1080i", "multi")
			elif number == 3:
				self.hw.saveMode("Scart", "Multi", "multi")
			self.hw.setConfiguredMode()
			self.close()

		WizardLanguage.keyNumberGlobal(self, number)
