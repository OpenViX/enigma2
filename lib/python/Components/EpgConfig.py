from enigma import RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, RT_VALIGN_CENTER, RT_WRAP

from config import config, ConfigClock, ConfigSelection, ConfigSelectionNumber, ConfigSubsection, ConfigYesNo, NoSave
from Components.SystemInfo import SystemInfo


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

	okButtonChoices = [("zap",_("Zap")), ("zapExit", _("Zap + Exit"))]
	infoButtonChoices = [("openEventView", _("Event Info")), ("openSingleEPG", _("Single EPG"))]

	config.epgselection.infobar = ConfigSubsection()
	config.epgselection.infobar.browse_mode = ConfigSelection(default = "currentservice", choices = singleBrowseModeChoices)
	config.epgselection.infobar.type_mode = ConfigSelection(default="graphics", choices=[("text", _("Text Grid EPG")), ("graphics", _("Graphics Grid EPG")), ("single", _("Single EPG"))])
	if SystemInfo.get("NumVideoDecoders", 1) > 1:
		config.epgselection.infobar.preview_mode = ConfigSelection(choices = [("0",_("Disabled")), ("1", _("Full screen")), ("2", _("PiP"))], default = "1")
	else:
		config.epgselection.infobar.preview_mode = ConfigSelection(choices = [("0",_("Disabled")), ("1", _("Full screen"))], default = "1")
	config.epgselection.infobar.btn_ok = ConfigSelection(choices = okButtonChoices, default = "zap")
	config.epgselection.infobar.btn_oklong = ConfigSelection(choices = okButtonChoices, default = "zapExit")
	config.epgselection.infobar.itemsperpage = ConfigSelectionNumber(default = 2, stepwidth = 1, min = 1, max = 4, wraparound = True)
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
	config.epgselection.single = ConfigSubsection()
	config.epgselection.single.browse_mode = ConfigSelection(default = "lastepgservice", choices = singleBrowseModeChoices)
	config.epgselection.single.preview_mode = ConfigYesNo(default = True)
	config.epgselection.single.btn_ok = ConfigSelection(choices = okButtonChoices, default = "zap")
	config.epgselection.single.btn_oklong = ConfigSelection(choices = okButtonChoices, default = "zapExit")
	config.epgselection.single.eventfs = ConfigSelectionNumber(default = 0, stepwidth = 1, min = -8, max = 10, wraparound = True)
	config.epgselection.single.itemsperpage = ConfigSelectionNumber(default = 18, stepwidth = 1, min = 1, max = 40, wraparound = True)
	config.epgselection.multi = ConfigSubsection()
	config.epgselection.multi.showbouquet = ConfigYesNo(default = False)
	config.epgselection.multi.browse_mode = ConfigSelection(default = "currentservice", choices = multiBrowseModeChoices)
	config.epgselection.multi.preview_mode = ConfigYesNo(default = True)
	config.epgselection.multi.btn_ok = ConfigSelection(choices = okButtonChoices, default = "zap")
	config.epgselection.multi.btn_oklong = ConfigSelection(choices = okButtonChoices, default = "zapExit")
	config.epgselection.multi.eventfs = ConfigSelectionNumber(default = 0, stepwidth = 1, min = -8, max = 10, wraparound = True)
	config.epgselection.multi.itemsperpage = ConfigSelectionNumber(default = 18, stepwidth = 1, min = 12, max = 40, wraparound = True)
	config.epgselection.multi.servicewidth = ConfigSelectionNumber(default = 7, stepwidth = 1, min = 5, max = 20, wraparound = True)
	config.epgselection.grid = ConfigSubsection()
	config.epgselection.grid.showbouquet = ConfigYesNo(default = False)
	config.epgselection.grid.browse_mode = ConfigSelection(default = "currentservice", choices = multiBrowseModeChoices)
	config.epgselection.grid.preview_mode = ConfigYesNo(default = True)
	config.epgselection.grid.type_mode = ConfigSelection(choices = [("graphics",_("Graphics")), ("text", _("Text"))], default = "graphics")
	config.epgselection.grid.highlight_current_events = ConfigYesNo(default=True)
	config.epgselection.grid.btn_ok = ConfigSelection(choices = okButtonChoices, default = "zap")
	config.epgselection.grid.btn_oklong = ConfigSelection(choices = okButtonChoices, default = "zapExit")
	config.epgselection.grid.btn_info = ConfigSelection(choices = infoButtonChoices, default = "openEventView")
	config.epgselection.grid.btn_infolong = ConfigSelection(choices = infoButtonChoices, default = "openSingleEPG")
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
	config.epgselection.grid.itemsperpage = ConfigSelectionNumber(default = 8, stepwidth = 1, min = 3, max = 20, wraparound = True)
	config.epgselection.grid.pig = ConfigYesNo(default = True)
	config.epgselection.grid.heightswitch = NoSave(ConfigYesNo(default = False))
	config.epgselection.grid.servicewidth = ConfigSelectionNumber(default = 250, stepwidth = 1, min = 70, max = 500, wraparound = True)
	config.epgselection.grid.piconwidth = ConfigSelectionNumber(default = 100, stepwidth = 1, min = 50, max = 500, wraparound = True)
	config.epgselection.grid.infowidth = ConfigSelectionNumber(default = 50, stepwidth = 25, min = 0, max = 150, wraparound = True)
	config.epgselection.grid.rec_icon_height = ConfigSelection(choices = [("bottom",_("bottom")),("top", _("top")), ("middle", _("middle")),  ("hide", _("hide"))], default = "bottom")
