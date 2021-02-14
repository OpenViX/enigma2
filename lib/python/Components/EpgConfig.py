from enigma import RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, RT_VALIGN_CENTER, RT_WRAP

from .config import config, ConfigClock, ConfigSelection, ConfigSelectionNumber, ConfigSubsection, ConfigYesNo, NoSave
from Components.SystemInfo import SystemInfo
from Screens.EpgSelectionBase import channelDownActions, channelUpActions, epgActions, infoActions, okActions, recActions


def InitEPGConfig():
	config.epgselection = ConfigSubsection()
	config.epgselection.sort = ConfigSelection(default="0", choices = [("0", _("Time")),("1", _("Alphanumeric"))])
	config.epgselection.overjump = ConfigYesNo(default = False)

	serviceTitleChoices = [
		("servicename", _("Service Name")),
		("picon", _("Picon")),
		("picon+servicename", _("Picon and Service Name")),
		("servicenumber+picon", _("Service Number and Picon")),
		("picon+servicenumber", _("Picon and Service Number")),
		("servicenumber+servicename", _("Service Number and Service Name")),
		("picon+servicenumber+servicename", _("Picon, Service Number and Service Name")),
		("servicenumber+picon+servicename", _("Service Number, Picon and Service Name"))]

	singleBrowseModeChoices = [
		("currentservice", _("Select current service")),
		("lastepgservice", _("Select last browsed service"))]

	multiBrowseModeChoices = [
		("currentservice", _("Select current service")),
		("firstservice", _("Select first service in bouquet")),
		("lastepgservice", _("Select last browsed service"))]

	config.epgselection.infobar = ConfigSubsection()
	config.epgselection.infobar.browse_mode = ConfigSelection(default = "currentservice", choices = singleBrowseModeChoices)
	config.epgselection.infobar.type_mode = ConfigSelection(default="graphics", choices=[("text", _("Text Grid EPG")), ("graphics", _("Graphics Grid EPG")), ("single", _("Single EPG"))])
	if SystemInfo.get("NumVideoDecoders", 1) > 1:
		config.epgselection.infobar.preview_mode = ConfigSelection(choices = [("0",_("Disabled")), ("1", _("Full screen")), ("2", _("PiP"))], default = "1")
	else:
		config.epgselection.infobar.preview_mode = ConfigSelection(choices = [("0",_("Disabled")), ("1", _("Full screen"))], default = "1")
	choices = [(0, _("Use skin default"))] + [(i, _("%d") % i) for i in range(1, 5)]
	config.epgselection.infobar.itemsperpage = ConfigSelection(default=0, choices=choices)
	config.epgselection.infobar.roundto = ConfigSelection(default = "15", choices = [("15", _("%d minutes") % 15), ("30", _("%d minutes") % 30), ("60", _("%d minutes") % 60)])
	config.epgselection.infobar.prevtimeperiod = ConfigSelection(default = "180", choices = [("60", _("%d minutes") % 60), ("90", _("%d minutes") % 90), ("120", _("%d minutes") % 120), ("150", _("%d minutes") % 150), ("180", _("%d minutes") % 180), ("210", _("%d minutes") % 210), ("240", _("%d minutes") % 240), ("270", _("%d minutes") % 270), ("300", _("%d minutes") % 300)])
	config.epgselection.infobar.primetime = ConfigClock(default = 20 * 60)
	config.epgselection.infobar.servicetitle_mode = ConfigSelection(default = "servicename", choices = serviceTitleChoices)
	config.epgselection.infobar.servfs = ConfigSelectionNumber(default = 0, stepwidth = 1, min = -8, max = 10, wraparound = True)
	config.epgselection.infobar.eventfs = ConfigSelectionNumber(default = 0, stepwidth = 1, min = -8, max = 10, wraparound = True)
	config.epgselection.infobar.timelinefs = ConfigSelectionNumber(default = 0, stepwidth = 1, min = -8, max = 10, wraparound = True)
	config.epgselection.infobar.timeline24h = ConfigYesNo(default = True)
	config.epgselection.infobar.servicewidth = ConfigSelectionNumber(default = 250, stepwidth = 1, min = 70, max = 500, wraparound = True)
	config.epgselection.infobar.piconwidth = ConfigSelectionNumber(default = 100, stepwidth = 1, min = 50, max = 500, wraparound = True)
	config.epgselection.infobar.infowidth = ConfigSelectionNumber(default = 50, stepwidth = 25, min = 0, max = 150, wraparound = True)
	config.epgselection.infobar.btn_ok = ConfigSelection(choices=okActions, default="zap")
	config.epgselection.infobar.btn_oklong = ConfigSelection(choices=okActions, default="zapExit")
	config.epgselection.infobar.btn_epg = ConfigSelection(choices=infoActions, default="openSingleEPG")
	config.epgselection.infobar.btn_epglong = ConfigSelection(choices=infoActions, default="")
	config.epgselection.infobar.btn_info = ConfigSelection(choices=infoActions, default="openEventView")
	config.epgselection.infobar.btn_infolong = ConfigSelection(choices=infoActions, default="openSingleEPG")
	config.epgselection.infobar.btn_red = ConfigSelection(choices=epgActions, default="openIMDb")
	config.epgselection.infobar.btn_redlong = ConfigSelection(choices=epgActions, default="sortEPG")
	config.epgselection.infobar.btn_green = ConfigSelection(choices=epgActions, default="addEditTimer")
	config.epgselection.infobar.btn_greenlong = ConfigSelection(choices=epgActions, default="openTimerList")
	config.epgselection.infobar.btn_yellow = ConfigSelection(choices=epgActions, default="openEPGSearch")
	config.epgselection.infobar.btn_yellowlong = ConfigSelection(choices=epgActions, default="")
	config.epgselection.infobar.btn_blue = ConfigSelection(choices=epgActions, default="addEditAutoTimer")
	config.epgselection.infobar.btn_bluelong = ConfigSelection(choices=epgActions, default="openAutoTimerList")
	config.epgselection.infobar.btn_rec = ConfigSelection(choices=recActions, default="addEditTimerMenu")
	config.epgselection.infobar.btn_reclong = ConfigSelection(choices=recActions, default="addEditZapTimerSilent")

	config.epgselection.single = ConfigSubsection()
	config.epgselection.single.browse_mode = ConfigSelection(default = "lastepgservice", choices = singleBrowseModeChoices)
	config.epgselection.single.preview_mode = ConfigYesNo(default = True)
	config.epgselection.single.eventfs = ConfigSelectionNumber(default = 0, stepwidth = 1, min = -8, max = 10, wraparound = True)
	choices = [(0, _("Use skin default"))] + [(i, _("%d") % i) for i in range(1, 41)]
	config.epgselection.single.itemsperpage = ConfigSelection(default=0, choices=choices)
	config.epgselection.single.btn_red = ConfigSelection(choices=epgActions, default="openIMDb")
	config.epgselection.single.btn_redlong = ConfigSelection(choices=epgActions, default="sortEPG")
	config.epgselection.single.btn_green = ConfigSelection(choices=epgActions, default="addEditTimer")
	config.epgselection.single.btn_greenlong = ConfigSelection(choices=epgActions, default="openTimerList")
	config.epgselection.single.btn_yellow = ConfigSelection(choices=epgActions, default="openEPGSearch")
	config.epgselection.single.btn_yellowlong = ConfigSelection(choices=epgActions, default="")
	config.epgselection.single.btn_blue = ConfigSelection(choices=epgActions, default="addEditAutoTimer")
	config.epgselection.single.btn_bluelong = ConfigSelection(choices=epgActions, default="openAutoTimerList")
	config.epgselection.single.btn_ok = ConfigSelection(choices=okActions, default="zap")
	config.epgselection.single.btn_oklong = ConfigSelection(choices=okActions, default="zapExit")
	config.epgselection.single.btn_epg = ConfigSelection(choices=infoActions, default="openSingleEPG")
	config.epgselection.single.btn_epglong = ConfigSelection(choices=infoActions, default="")
	config.epgselection.single.btn_info = ConfigSelection(choices=infoActions, default="openEventView")
	config.epgselection.single.btn_infolong = ConfigSelection(choices=infoActions, default="openSingleEPG")
	config.epgselection.single.btn_rec = ConfigSelection(choices=recActions, default="addEditTimerMenu")
	config.epgselection.single.btn_reclong = ConfigSelection(choices=recActions, default="addEditZapTimerSilent")

	config.epgselection.multi = ConfigSubsection()
	config.epgselection.multi.showbouquet = ConfigYesNo(default = False)
	config.epgselection.multi.browse_mode = ConfigSelection(default = "currentservice", choices = multiBrowseModeChoices)
	config.epgselection.multi.preview_mode = ConfigYesNo(default = True)
	config.epgselection.multi.eventfs = ConfigSelectionNumber(default = 0, stepwidth = 1, min = -8, max = 10, wraparound = True)
	choices = [(0, _("Use skin default"))] + [(i, _("%d") % i) for i in range(12, 41)]
	config.epgselection.multi.itemsperpage = ConfigSelection(default=0, choices=choices)
	config.epgselection.multi.servicewidth = ConfigSelectionNumber(default = 7, stepwidth = 1, min = 5, max = 20, wraparound = True)
	config.epgselection.multi.btn_ok = ConfigSelection(choices=okActions, default="zap")
	config.epgselection.multi.btn_oklong = ConfigSelection(choices=okActions, default="zapExit")
	config.epgselection.multi.btn_epg = ConfigSelection(choices=infoActions, default="openSingleEPG")
	config.epgselection.multi.btn_epglong = ConfigSelection(choices=infoActions, default="")
	config.epgselection.multi.btn_info = ConfigSelection(choices=infoActions, default="openEventView")
	config.epgselection.multi.btn_infolong = ConfigSelection(choices=infoActions, default="openSingleEPG")
	config.epgselection.multi.btn_rec = ConfigSelection(choices=recActions, default="addEditTimerMenu")
	config.epgselection.multi.btn_reclong = ConfigSelection(choices=recActions, default="addEditZapTimerSilent")
	config.epgselection.multi.btn_red = ConfigSelection(choices=epgActions, default="openIMDb")
	config.epgselection.multi.btn_redlong = ConfigSelection(choices=epgActions, default="sortEPG")
	config.epgselection.multi.btn_green = ConfigSelection(choices=epgActions, default="addEditTimer")
	config.epgselection.multi.btn_greenlong = ConfigSelection(choices=epgActions, default="openTimerList")
	config.epgselection.multi.btn_yellow = ConfigSelection(choices=epgActions, default="openEPGSearch")
	config.epgselection.multi.btn_yellowlong = ConfigSelection(choices=epgActions, default="")
	config.epgselection.multi.btn_blue = ConfigSelection(choices=epgActions, default="addEditAutoTimer")
	config.epgselection.multi.btn_bluelong = ConfigSelection(choices=epgActions, default="openAutoTimerList")

	config.epgselection.grid = ConfigSubsection()
	config.epgselection.grid.showbouquet = ConfigYesNo(default = False)
	config.epgselection.grid.browse_mode = ConfigSelection(default = "currentservice", choices = multiBrowseModeChoices)
	config.epgselection.grid.preview_mode = ConfigYesNo(default = True)
	config.epgselection.grid.type_mode = ConfigSelection(choices = [("graphics",_("Graphics")), ("text", _("Text"))], default = "graphics")
	config.epgselection.grid.highlight_current_events = ConfigYesNo(default=True)
	config.epgselection.grid.roundto = ConfigSelection(default = "15", choices = [("15", _("%d minutes") % 15), ("30", _("%d minutes") % 30), ("60", _("%d minutes") % 60)])
	config.epgselection.grid.prevtimeperiod = ConfigSelection(default = "180", choices = [("60", _("%d minutes") % 60), ("90", _("%d minutes") % 90), ("120", _("%d minutes") % 120), ("150", _("%d minutes") % 150), ("180", _("%d minutes") % 180), ("210", _("%d minutes") % 210), ("240", _("%d minutes") % 240), ("270", _("%d minutes") % 270), ("300", _("%d minutes") % 300)])
	config.epgselection.grid.primetime = ConfigClock(default = 20 * 60)
	config.epgselection.grid.servicetitle_mode = ConfigSelection(default = "servicename", choices = serviceTitleChoices)
	possibleAlignmentChoices = [
			( str(RT_HALIGN_LEFT   | RT_VALIGN_CENTER          ) , _("left")),
			( str(RT_HALIGN_CENTER | RT_VALIGN_CENTER          ) , _("centered")),
			( str(RT_HALIGN_RIGHT  | RT_VALIGN_CENTER          ) , _("right")),
			( str(RT_HALIGN_LEFT   | RT_VALIGN_CENTER | RT_WRAP) , _("left, wrapped")),
			( str(RT_HALIGN_CENTER | RT_VALIGN_CENTER | RT_WRAP) , _("centered, wrapped")),
			( str(RT_HALIGN_RIGHT  | RT_VALIGN_CENTER | RT_WRAP) , _("right, wrapped"))]
	config.epgselection.grid.servicename_alignment = ConfigSelection(default = possibleAlignmentChoices[0][0], choices = possibleAlignmentChoices)
	config.epgselection.grid.servicenumber_alignment = ConfigSelection(default = possibleAlignmentChoices[0][0], choices = possibleAlignmentChoices)
	config.epgselection.grid.event_alignment = ConfigSelection(default = possibleAlignmentChoices[0][0], choices = possibleAlignmentChoices)
	config.epgselection.grid.timelinedate_alignment = ConfigSelection(default = possibleAlignmentChoices[0][0], choices = possibleAlignmentChoices)
	config.epgselection.grid.servfs = ConfigSelectionNumber(default = 0, stepwidth = 1, min = -8, max = 10, wraparound = True)
	config.epgselection.grid.eventfs = ConfigSelectionNumber(default = 0, stepwidth = 1, min = -8, max = 10, wraparound = True)
	config.epgselection.grid.timelinefs = ConfigSelectionNumber(default = 0, stepwidth = 1, min = -8, max = 10, wraparound = True)
	config.epgselection.grid.timeline24h = ConfigYesNo(default = True)
	choices = [(0, _("Use skin default"))] + [(i, _("%d") % i) for i in range(3, 21)]
	config.epgselection.grid.itemsperpage = ConfigSelection(default=0, choices=choices)
	config.epgselection.grid.pig = ConfigYesNo(default = True)
	config.epgselection.grid.heightswitch = NoSave(ConfigYesNo(default = False))
	config.epgselection.grid.servicewidth = ConfigSelectionNumber(default = 250, stepwidth = 1, min = 70, max = 500, wraparound = True)
	config.epgselection.grid.piconwidth = ConfigSelectionNumber(default = 100, stepwidth = 1, min = 50, max = 500, wraparound = True)
	config.epgselection.grid.infowidth = ConfigSelectionNumber(default = 50, stepwidth = 25, min = 0, max = 150, wraparound = True)
	config.epgselection.grid.rec_icon_height = ConfigSelection(choices = [("bottom",_("bottom")),("top", _("top")), ("middle", _("middle")),  ("hide", _("hide"))], default = "bottom")
	config.epgselection.grid.number_buttons_mode = ConfigSelection(choices = [("paging", _("Standard")), ("service", _("Enter service number"))], default="paging")
	config.epgselection.grid.btn_ok = ConfigSelection(choices=okActions, default="zap")
	config.epgselection.grid.btn_oklong = ConfigSelection(choices=okActions, default="zapExit")
	config.epgselection.grid.btn_epg = ConfigSelection(choices=infoActions, default="openSingleEPG")
	config.epgselection.grid.btn_epglong = ConfigSelection(choices=infoActions, default="")
	config.epgselection.grid.btn_info = ConfigSelection(choices=infoActions, default="openEventView")
	config.epgselection.grid.btn_infolong = ConfigSelection(choices=infoActions, default="openSingleEPG")
	config.epgselection.grid.btn_rec = ConfigSelection(choices=recActions, default="addEditTimerMenu")
	config.epgselection.grid.btn_reclong = ConfigSelection(choices=recActions, default="addEditZapTimerSilent")
	config.epgselection.grid.btn_channelup = ConfigSelection(choices=channelUpActions, default="forward24Hours")
	config.epgselection.grid.btn_channeldown = ConfigSelection(choices=channelDownActions, default="back24Hours")
	config.epgselection.grid.btn_red = ConfigSelection(choices=epgActions, default="openIMDb")
	config.epgselection.grid.btn_redlong = ConfigSelection(choices=epgActions, default="sortEPG")
	config.epgselection.grid.btn_green = ConfigSelection(choices=epgActions, default="addEditTimer")
	config.epgselection.grid.btn_greenlong = ConfigSelection(choices=epgActions, default="openTimerList")
	config.epgselection.grid.btn_yellow = ConfigSelection(choices=epgActions, default="openEPGSearch")
	config.epgselection.grid.btn_yellowlong = ConfigSelection(choices=epgActions, default="")
	config.epgselection.grid.btn_blue = ConfigSelection(choices=epgActions, default="addEditAutoTimer")
	config.epgselection.grid.btn_bluelong = ConfigSelection(choices=epgActions, default="openAutoTimerList")
