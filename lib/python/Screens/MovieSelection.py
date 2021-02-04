from Screen import Screen
from Components.Button import Button
from Components.ActionMap import HelpableActionMap, ActionMap, HelpableNumberActionMap
from Components.ChoiceList import ChoiceList, ChoiceEntryComponent
from Components.MenuList import MenuList
from Components.MovieList import MovieList, getItemDisplayName, resetMoviePlayState, AUDIO_EXTENSIONS, DVD_EXTENSIONS, IMAGE_EXTENSIONS, moviePlayState
from Components.DiskInfo import DiskInfo
from Tools.Trashcan import TrashInfo
from Components.Pixmap import Pixmap, MultiPixmap
from Components.Label import Label
from Components.PluginComponent import plugins
from Components.config import config, ConfigSubsection, ConfigText, ConfigInteger, ConfigLocations, ConfigSet, ConfigYesNo, ConfigSelection, ConfigSelectionNumber
from Components.ServiceEventTracker import ServiceEventTracker, InfoBarBase
from Components.Sources.ServiceEvent import ServiceEvent
from Components.Sources.StaticText import StaticText
import Components.Harddisk
from Components.UsageConfig import preferredTimerPath
from Screens.VirtualKeyBoard import VirtualKeyBoard
from Screens.Setup import Setup
from Plugins.Plugin import PluginDescriptor
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from Screens.LocationBox import MovieLocationBox
from Screens.HelpMenu import HelpableScreen
from Screens.InputBox import PinInput
import Screens.InfoBar
from Tools import NumericalTextInput
from Tools.Directories import resolveFilename, SCOPE_HDD
from Tools.BoundFunction import boundFunction
import Tools.CopyFiles
import Tools.Trashcan
import NavigationInstance
import RecordTimer

from enigma import eServiceReference, eServiceCenter, eTimer, eSize, iPlayableService, iServiceInformation, getPrevAsciiCode, eRCInput
import os
import time
import cPickle as pickle

config.movielist = ConfigSubsection()
config.movielist.curentlyplayingservice = ConfigText()
config.movielist.show_live_tv_in_movielist = ConfigYesNo(default=True)
config.movielist.fontsize = ConfigSelectionNumber(default = 0, stepwidth = 1, min = -8, max = 10, wraparound = True)
config.movielist.itemsperpage = ConfigSelectionNumber(default = 20, stepwidth = 1, min = 3, max = 30, wraparound = True)
config.movielist.useslim = ConfigYesNo(default=False)
config.movielist.use_fuzzy_dates = ConfigYesNo(default=True)
config.movielist.moviesort = ConfigInteger(default=MovieList.SORT_GROUPWISE)
config.movielist.description = ConfigInteger(default=MovieList.SHOW_DESCRIPTION)
config.movielist.last_videodir = ConfigText(default=resolveFilename(SCOPE_HDD))
config.movielist.last_timer_videodir = ConfigText(default=resolveFilename(SCOPE_HDD))
config.movielist.videodirs = ConfigLocations(default=[resolveFilename(SCOPE_HDD)])
config.movielist.last_selected_tags = ConfigSet([], default=[])
config.movielist.play_audio_internal = ConfigYesNo(default=True)
config.movielist.settings_per_directory = ConfigYesNo(default=True)
config.movielist.perm_sort_changes = ConfigYesNo(default=True)
config.movielist.root = ConfigSelection(default="/media", choices=["/","/media","/media/hdd","/media/hdd/movie","/media/usb","/media/usb/movie"])
config.movielist.hide_extensions = ConfigYesNo(default=False)
config.movielist.stop_service = ConfigYesNo(default=True)

userDefinedButtons = None
last_selected_dest = []
preferredTagEditor = None

# this kludge is needed because ConfigSelection only takes numbers
# and someone appears to be fascinated by 'enums'.
l_moviesort = [
	(str(MovieList.SORT_GROUPWISE), _("recordings by date then other media by name") , '02/01 & A-Z'),
	(str(MovieList.SORT_RECORDED), _("by date"), '03/02/01'),
	(str(MovieList.SORT_ALPHANUMERIC), _("alphabetic"), 'A-Z'),
	(str(MovieList.SORT_ALPHA_DATE_OLDEST_FIRST), _("alpha then oldest"), 'A1 A2 Z1'),
	(str(MovieList.SORT_ALPHANUMERIC_FLAT_REVERSE), _("flat alphabetic reverse"), 'Z-A Flat'),
	(str(MovieList.SORT_LONGEST), _("longest"), 'long-short'),
	(str(MovieList.SORT_SHORTEST), _("shortest"), 'short-long'),
	(str(MovieList.SHUFFLE), _("shuffle"), '?'),
	(str(MovieList.SORT_ALPHANUMERIC_FLAT), _("flat alphabetic"), 'A-Z Flat'),
	(str(MovieList.SORT_RECORDED_REVERSE), _("reverse by date"), '01/02/03'),
	(str(MovieList.SORT_ALPHANUMERIC_REVERSE), _("alphabetic reverse"), 'Z-A'),
	(str(MovieList.SORT_ALPHAREV_DATE_NEWEST_FIRST), _("alpharev then newest"),  'Z1 A2 A1')]

# 4th item is the textual value set in UsageConfig.py
l_trashsort = [
	(str(MovieList.TRASHSORT_SHOWRECORD), _("delete time - show record time (Trash ONLY)"), '03/02/01', "show record time"),
	(str(MovieList.TRASHSORT_SHOWDELETE), _("delete time - show delete time (Trash ONLY)"), '03/02/01', "show delete time")]

try:
	from Plugins.Extensions import BlurayPlayer
except Exception as e:
	print "[MovieSelection] Bluray Player is not installed:", e
	BlurayPlayer = None


def defaultMoviePath():
	result = config.usage.default_path.value
	if not os.path.isdir(result):
		from Tools import Directories
		return Directories.defaultRecordingLocation()
	return result

def setPreferredTagEditor(te):
	global preferredTagEditor
	if preferredTagEditor is None:
		preferredTagEditor = te
		print "[MovieSelection] Preferred tag editor changed to", preferredTagEditor
	else:
		print "[MovieSelection] Preferred tag editor already set to", preferredTagEditor, "ignoring", te

def getPreferredTagEditor():
	global preferredTagEditor
	return preferredTagEditor

def isTrashFolder(ref):
	if not config.usage.movielist_trashcan.value or not ref.flags & eServiceReference.mustDescent:
		return False
	return os.path.realpath(ref.getPath()).endswith('.Trash') or os.path.realpath(ref.getPath()).endswith('.Trash/')

def isInTrashFolder(ref):
	if not config.usage.movielist_trashcan.value:
		return False
	path = os.path.realpath(ref.getPath())
	return path.startswith(Tools.Trashcan.getTrashFolder(path))

def isSimpleFile(item):
	if not item:
		return False
	if not item[0] or not item[1]:
		return False
	return (item[0].flags & eServiceReference.mustDescent) == 0

def isFolder(item):
	if not item:
		return False
	if not item[0] or not item[1]:
		return False
	return (item[0].flags & eServiceReference.mustDescent) != 0

def canMove(item):
	if not item:
		return False
	if not item[0] or not item[1] or isTrashFolder(item[0]):
		return False
	return True

def canDelete(item):
	if not item:
		return False
	if not item[0] or not item[1]:
		return False
	return True

canCopy = canMove
canRename = canMove

def createMoveList(serviceref, dest):
	#normpath is to remove the trailing '/' from directories
	src = isinstance(serviceref, str) and serviceref + ".ts" or os.path.normpath(serviceref.getPath())
	srcPath, srcName = os.path.split(src)
	if os.path.normpath(srcPath) == dest:
		# move file to itself is allowed, so we have to check it
		raise Exception, "Refusing to move to the same directory"
	# Make a list of items to move
	moveList = [(src, os.path.join(dest, srcName))]
	if isinstance(serviceref, str) or not serviceref.flags & eServiceReference.mustDescent:
		# Real movie, add extra files...
		srcBase = os.path.splitext(src)[0]
		baseName = os.path.split(srcBase)[1]
		eitName =  srcBase + '.eit'
		if os.path.exists(eitName):
			moveList.append((eitName, os.path.join(dest, baseName+'.eit')))
		baseName = os.path.split(src)[1]
		for ext in ('.ap', '.cuts', '.meta', '.sc'):
			candidate = src + ext
			if os.path.exists(candidate):
				moveList.append((candidate, os.path.join(dest, baseName+ext)))
	return moveList

def moveServiceFiles(serviceref, dest, name=None, allowCopy=True):
	moveList = createMoveList(serviceref, dest)
	# Try to "atomically" move these files
	movedList = []
	try:
		# print "[MovieSelection] Moving in background..."
		# start with the smaller files, do the big one later.
		moveList.reverse()
		if name is None:
			name = os.path.split(moveList[-1][0])[1]
		Tools.CopyFiles.moveFiles(moveList, name)
	except Exception, e:
		print "[MovieSelection] Failed move:", e
		# rethrow exception
		raise

def copyServiceFiles(serviceref, dest, name=None):
	# current should be 'ref' type, dest a simple path string
	moveList = createMoveList(serviceref, dest)
	# Try to "atomically" move these files
	movedList = []
	try:
		# print "[MovieSelection] Copying in background..."
		# start with the smaller files, do the big one later.
		moveList.reverse()
		if name is None:
			name = os.path.split(moveList[-1][0])[1]
		Tools.CopyFiles.copyFiles(moveList, name)
	except Exception, e:
		print "[MovieSelection] Failed copy:", e
		# rethrow exception
		raise

# Changes the title contained in a media file's .meta if it exists, otherwise, renames 
# the media file and it's associated data files. Also renames a directory.
def renameServiceFiles(serviceref, newName):
	oldPath = serviceref.getPath().rstrip("/")
	oldDir, oldBaseName = os.path.split(oldPath)
	oldName, oldExt = os.path.splitext(oldPath)
	newPath = os.path.join(oldDir, newName + oldExt)
	# rename will overwrite existing files, check first
	if os.path.exists(newPath):
		return False
	# rename the directory/media file. If successful we'll rename any associated files
	print("[MovieSelection] Rename %s to %s" % (oldPath, newPath))
	os.rename(oldPath, newPath)
	if os.path.isdir(newPath):
		serviceref.setPath(newPath)
		return serviceref
	# Now rename any data files associated with the media file. If there are any same
	# named orphaned file types, this will either either overwrite them using rename, or remove them
	cleanupList = [".eit", oldExt+".cuts"]
	for ext in cleanupList[:]:
		oldPath = os.path.join(oldDir, oldName + ext)
		if os.path.exists(oldPath):
			newPath = os.path.join(oldDir, newName + ext)
			os.rename(oldPath, newPath)
			cleanupList.remove(ext)
	try:
		for item in cleanupList + [oldExt+".ap", oldExt+".meta", oldExt+".sc"]:
			newPath = os.path.join(oldDir, newName + ext)
			if os.path.exists(newPath):
				os.remove(newPath)
	except Exception as ex:
		# cleanup failures aren't so terrible; just log and carry on
		print("[MovieSelection] Error removing orphaned data files. %s" % ex)
	return None

# Appends possible destinations to the bookmarks dictionary
def buildMovieLocationList(includeOther=False, path=None, includeSubdirs=False, includeParentDir=False):
	inlist = []
	bookmarks = []
	if includeOther:
		bookmarks.append(("(" + _("Other") + "...)", None))
	if path:
		base = os.path.split(path)[0]
		if includeParentDir and base != config.movielist.root.value:
			d = os.path.split(base)[0]
			if os.path.isdir(d) and d != config.movielist.root.value and (d not in inlist):
				bookmarks.append((d, d))
				inlist.append(d)
		if includeSubdirs:
			try:
				base = os.path.split(path)[0]
				for fn in os.listdir(base):
					if not fn.startswith('.'): # Skip hidden things
						d = os.path.join(base, fn)
						if os.path.isdir(d) and (d not in inlist):
							bookmarks.append((fn, d))
							inlist.append(d)
			except Exception as e:
				print("[MovieSelection] %s" % e)
	# Last favourites
	for d in last_selected_dest:
		if d not in inlist:
			bookmarks.append((d,d))
			inlist.append(d)
	# Other favourites
	for d in config.movielist.videodirs.value:
		d = os.path.normpath(d)
		if d not in inlist:
			bookmarks.append((d,d))
			inlist.append(d)
	# Mount points
	for p in Components.Harddisk.harddiskmanager.getMountedPartitions():
		d = os.path.normpath(p.mountpoint)
		if d in inlist:
			# improve shortcuts to mountpoints
			try:
				bookmarks[bookmarks.index((d,d))] = (p.tabbedDescription(), d)
			except:
				pass # When already listed as some "friendly" name
		else:
			bookmarks.append((p.tabbedDescription(), d))
			inlist.append(d)
	return bookmarks

def countFiles(directory):
	directories = files = 0
	for filename in os.listdir(directory):
		if filename not in (".", "..", ".e2settings.pkl"):
			filepath = os.path.join(directory, filename)
			if os.path.isdir(filepath):
				directories += 1
			else:
				filenameOnly, extension = os.path.splitext(filename)
				if extension not in (".eit", ".ap", ".cuts", ".meta", ".sc"):
					files += 1
	return directories, files

class MovieBrowserConfiguration(Setup):
	def __init__(self, session, args = 0):
		if args:
			print "[MovieBrowserConfiguration] args is deprecated, because it is unused"
		# self.cfg is referred to from setup.xml
		# and needs to be defined before Setup.__init__() is called.
		cfg = ConfigSubsection()
		cfg.moviesort = ConfigSelection(default=str(config.movielist.moviesort.value), choices = l_moviesort)
		cfg.description = ConfigYesNo(default=(config.movielist.description.value != MovieList.HIDE_DESCRIPTION))
		self.cfg = cfg

		Setup.__init__(self, session=session, setup="movieselection")

	def save(self):  # Deprecated - for backwards compatibility
		print "[MovieBrowserConfiguration] save() is deprecated, call keySave() instead"
		self.keySave()

	def keySave(self):
		self.saveAll()
		cfg = self.cfg
		config.movielist.moviesort.value = int(cfg.moviesort.value)
		if cfg.description.value:
			config.movielist.description.value = MovieList.SHOW_DESCRIPTION
		else:
			config.movielist.description.value = MovieList.HIDE_DESCRIPTION
		if not config.movielist.settings_per_directory.value:
			config.movielist.moviesort.save()
			config.movielist.description.save()
			config.movielist.useslim.save()
			config.usage.on_movie_eof.save()
		self.close(True)

	def cancel(self):  # Deprecated - for backwards compatibility
		print "[MovieBrowserConfiguration] cancel() is deprecated, call keyCancel() instead"
		self.keyCancel()

	def keyCancel(self):
		self.closeConfigList((False,))

	def closeRecursive(self):
		self.keyCancel()

class MovieContextMenuSummary(Screen):
	def __init__(self, session, parent):
		Screen.__init__(self, session, parent = parent)
		self["selected"] = StaticText("")
		self.onShow.append(self.__onShow)
		self.onHide.append(self.__onHide)

	def __onShow(self):
		self.parent["config"].onSelectionChanged.append(self.selectionChanged)
		self.selectionChanged()

	def __onHide(self):
		self.parent["config"].onSelectionChanged.remove(self.selectionChanged)

	def selectionChanged(self):
		self["selected"].text = self.parent["config"].getCurrent()[0][0]

from Screens.ParentalControlSetup import ProtectedScreen

class MovieContextMenu(Screen, ProtectedScreen):
	# Contract: On OK returns a callable object (e.g. delete)
	def __init__(self, session, csel, currentSelection):
		Screen.__init__(self, session)
		self.skinName = "Setup"
		self.setup_title = _("Movie List Setup")
		Screen.setTitle(self, _(self.setup_title))

		self['footnote'] = Label("")
		self["description"] = StaticText()

		self.csel = csel
		ProtectedScreen.__init__(self)
		self.title = _("Movielist menu")

		self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "NumberActions", "MenuActions"],
			{
				"red": self.cancelClick,
				"ok": self.okbuttonClick,
				"cancel": self.cancelClick,
				"green": boundFunction(self.close, csel.showDeviceMounts),
				"yellow": boundFunction(self.close, csel.showNetworkMounts),
				"blue": boundFunction(self.close, csel.selectSortby),
				"menu": boundFunction(self.close, csel.configure),
				"1": boundFunction(self.close, csel.do_addbookmark),
				"2": boundFunction(self.close, csel.do_createdir),
				"3": boundFunction(self.close, csel.do_delete),
				"4": boundFunction(self.close, csel.do_move),
				"5": boundFunction(self.close, csel.do_copy),
				"6": boundFunction(self.close, csel.do_rename),
				"7": boundFunction(self.close, csel.do_reset),
				"8": boundFunction(self.close, csel.do_decode),
				"9": boundFunction(self.close, csel.unhideParentalServices)
			})

		self["key_red"] = StaticText(_("Cancel"))

		def append_to_menu(menu, args, key=""):
			menu.append(ChoiceEntryComponent(key, args))

		menu = []
		append_to_menu(menu, (_("Settings") + "...", csel.configure), key="menu")
		append_to_menu(menu, (_("Device mounts") + "...", csel.showDeviceMounts), key="green")
		append_to_menu(menu, (_("Network mounts") + "...", csel.showNetworkMounts), key="yellow")
		append_to_menu(menu, (_("Sort by") + "...", csel.selectSortby), key="blue")
		if csel.exist_bookmark():
			append_to_menu(menu, (_("Remove bookmark"), csel.do_addbookmark), key="1")
		else:
			append_to_menu(menu, (_("Add bookmark"), csel.do_addbookmark), key="1")
		append_to_menu(menu, (_("Create directory"), csel.do_createdir), key="2")

		if currentSelection:
			service = currentSelection[0]
			if isTrashFolder(service):
				append_to_menu(menu, (_("Empty trash can"), csel.purgeAll), key="3")
			elif csel.can_delete(currentSelection):
				append_to_menu(menu, (_("Delete"), csel.do_delete), key="3")
			if csel.can_move(currentSelection):
				append_to_menu(menu, (_("Move"), csel.do_move), key="4")
				append_to_menu(menu, (_("Copy"), csel.do_copy), key="5")
			if csel.can_rename(currentSelection):
				append_to_menu(menu, (_("Rename"), csel.do_rename), key="6")
			if csel.can_reset(currentSelection):
				append_to_menu(menu, (_("Reset playback position"), csel.do_reset), key="7")
			if csel.can_decode(currentSelection):
				append_to_menu(menu, (_("Start offline decode"), csel.do_decode), key="8")
			if (service.flags & eServiceReference.mustDescent) and BlurayPlayer is None and csel.isBlurayFolderAndFile(service):
				append_to_menu(menu, (_("Auto play blu-ray file"), csel.playBlurayFile))
			if config.ParentalControl.hideBlacklist.value and config.ParentalControl.storeservicepin.value != "never":
				from Components.ParentalControl import parentalControl
				if not parentalControl.sessionPinCached:
					append_to_menu(menu, (_("Unhide parental control services"), csel.unhideParentalServices), key="9")
			# Plugins expect a valid selection, so only include them if we selected a non-dir
			if not(service.flags & eServiceReference.mustDescent):
				for p in plugins.getPlugins(PluginDescriptor.WHERE_MOVIELIST):
					append_to_menu( menu, (p.description, boundFunction(p, session, service)), key="bullet")

		self["config"] = ChoiceList(menu)


	def isProtected(self):
		return self.csel.protectContextMenu and config.ParentalControl.setuppinactive.value and config.ParentalControl.config_sections.context_menus.value

	def pinEntered(self, answer):
		if answer:
			self.csel.protectContextMenu = False
		ProtectedScreen.pinEntered(self, answer)

	def createSummary(self):
		return MovieContextMenuSummary

	def okbuttonClick(self):
		self.close(self["config"].getCurrent()[0][1])

	def cancelClick(self):
		self.close(None)

class SelectionEventInfo:
	def __init__(self):
		self["Service"] = ServiceEvent()
		self.list.connectSelChanged(self.__selectionChanged)
		self.timer = eTimer()
		self.timer.callback.append(self.updateEventInfo)
		self.onShown.append(self.__selectionChanged)

	def __selectionChanged(self):
		if self.execing and self.settings["description"] == MovieList.SHOW_DESCRIPTION:
			self.timer.start(100, True)

	def updateEventInfo(self):
		serviceref = self.getCurrent()
		self["Service"].newService(serviceref)

class MovieSelectionSummary(Screen):
	# Kludgy component to display current selection on LCD. Should use
	# parent.Service as source for everything, but that seems to have a
	# performance impact as the MovieSelection goes through hoops to prevent
	# this when the info is not selected
	def __init__(self, session, parent):
		Screen.__init__(self, session, parent = parent)
		self["name"] = StaticText("")
		self.onShow.append(self.__onShow)
		self.onHide.append(self.__onHide)

	def __onShow(self):
		self.parent.list.connectSelChanged(self.selectionChanged)
		self.selectionChanged()

	def __onHide(self):
		self.parent.list.disconnectSelChanged(self.selectionChanged)

	def selectionChanged(self):
		item = self.parent.getCurrentSelection()
		if item and item[0]:
			data = item[3]
			if data and hasattr(data, 'txt'):
				name = data.txt
			elif not item[1]:
				# special case, one up
				name = ".."
			else:
				name = item[1].getName(item[0])
			if item[0].flags & eServiceReference.mustDescent:
				if len(name) > 12:
					name = os.path.split(os.path.normpath(name))[1]
					if name == ".Trash":
						name = _("Trash")
				else:
					path, dir = os.path.split(os.path.normpath(name))
					if dir == ".Trash":
						name = os.path.join(path, _("Trash") + "/")
				name = "> " + name
			self["name"].text = name
		else:
			self["name"].text = ""

class MovieSelection(Screen, HelpableScreen, SelectionEventInfo, InfoBarBase, ProtectedScreen):
	# SUSPEND_PAUSES actually means "please call my pauseService()"
	ALLOW_SUSPEND = Screen.SUSPEND_PAUSES

	def __init__(self, session, selectedmovie = None, timeshiftEnabled = False):
		Screen.__init__(self, session)
		if config.movielist.useslim.value:
			self.skinName = ["MovieSelectionSlim","MovieSelection"]
		else:
			self.skinName = "MovieSelection"
		HelpableScreen.__init__(self)
		if not timeshiftEnabled:
			InfoBarBase.__init__(self) # For ServiceEventTracker
		ProtectedScreen.__init__(self)
		self.protectContextMenu = True

		self.initUserDefinedActions()
		self.tags = {}
		if selectedmovie:
			self.selected_tags = config.movielist.last_selected_tags.value
		else:
			self.selected_tags = None
		self.selected_tags_ele = None
		self.nextInBackground = None

		self.movemode = False
		self.bouquet_mark_edit = False

		self.feedbackTimer = None
		self.pathselectEnabled = False

		self.numericalTextInput = NumericalTextInput.NumericalTextInput(mapping=NumericalTextInput.MAP_SEARCH_UPCASE)
		self["chosenletter"] = Label("")
		self["chosenletter"].visible = False

		self["waitingtext"] = Label(_("Please wait... Loading list..."))

		self.LivePlayTimer = eTimer()
		self.LivePlayTimer.timeout.get().append(self.LivePlay)

		self.filePlayingTimer = eTimer()
		self.filePlayingTimer.timeout.get().append(self.FilePlaying)

		self.playingInForeground = None
		# create optional description border and hide immediately
		self["DescriptionBorder"] = Pixmap()
		self["DescriptionBorder"].hide()

		if config.ParentalControl.servicepinactive.value:
			from Components.ParentalControl import parentalControl
			if not parentalControl.sessionPinCached and config.movielist.last_videodir.value and [x for x in config.movielist.last_videodir.value[1:].split("/") if x.startswith(".") and not x.startswith(".Trash")]:
				config.movielist.last_videodir.value = ""
		if not os.path.isdir(config.movielist.last_videodir.value):
			config.movielist.last_videodir.value = defaultMoviePath()
			config.movielist.last_videodir.save()
		self.setCurrentRef(config.movielist.last_videodir.value)

		self.settings = {
			"moviesort": config.movielist.moviesort.value,
			"description": config.movielist.description.value,
			"movieoff": config.usage.on_movie_eof.value
		}
		self.movieOff = self.settings["movieoff"]

		self["list"] = MovieList(None, sort_type=self.settings["moviesort"], descr_state=self.settings["description"])

		self.list = self["list"]
		self.selectedmovie = selectedmovie

		self.playGoTo = None #1 - preview next item / -1 - preview previous

		title = _("Movie selection")
		self.setTitle(title)

		# Need list for init
		SelectionEventInfo.__init__(self)

		self["key_red"] = Button("")
		self["key_green"] = Button("")
		self["key_yellow"] = Button("")
		self["key_blue"] = Button("")
		self._updateButtonTexts()
		
		self["key_menu"] = StaticText(_("MENU"))
		self["key_info"] = StaticText(_("INFO"))

		self["movie_off"] = MultiPixmap()
		self["movie_off"].hide()

		self["movie_sort"] = MultiPixmap()
		self["movie_sort"].hide()

		self["freeDiskSpace"] = self.diskinfo = DiskInfo(config.movielist.last_videodir.value, DiskInfo.FREE, update=False)
		self["TrashcanSize"] = self.trashinfo = TrashInfo(config.movielist.last_videodir.value, TrashInfo.USED, update=False)

		self["InfobarActions"] = HelpableActionMap(self, "InfobarActions",
			{
				"showMovies": (self.doPathSelect, _("Select the movie path")),
				"showRadio": (self.btn_radio, boundFunction(self.getinitUserDefinedActionsDescription, "btn_radio")),
				"showTv": (self.btn_tv, boundFunction(self.getinitUserDefinedActionsDescription, "btn_tv")),
				"showText": (self.btn_text, boundFunction(self.getinitUserDefinedActionsDescription, "btn_text")),
			}, description=_("Basic functions"))

		numberActionHelp = _("Search by first letter of name")
		self["NumberActions"] =  HelpableNumberActionMap(self, ["NumberActions", "InputAsciiActions"],
			{
				"gotAsciiCode": self.keyAsciiCode,
				"1": (self.keyNumberGlobal, numberActionHelp),
				"2": (self.keyNumberGlobal, numberActionHelp),
				"3": (self.keyNumberGlobal, numberActionHelp),
				"4": (self.keyNumberGlobal, numberActionHelp),
				"5": (self.keyNumberGlobal, numberActionHelp),
				"6": (self.keyNumberGlobal, numberActionHelp),
				"7": (self.keyNumberGlobal, numberActionHelp),
				"8": (self.keyNumberGlobal, numberActionHelp),
				"9": (self.keyNumberGlobal, numberActionHelp),
			}, description=_("Search by name (SMS-style entry on remote)"))

		self["playbackActions"] = HelpableActionMap(self, "MoviePlayerActions",
			{
				"leavePlayer": (self.playbackStop, _("Stop")),
				"moveNext": (self.playNext, _("Play next")),
				"movePrev": (self.playPrev, _("Play previous")),
				"channelUp": (self.moveToFirstOrFirstFile, _("Go to first movie or top of list")),
				"channelDown": (self.moveToLastOrFirstFile, _("Go to first movie or last item")),
			}, description=_("Recording/media selection"))
		self["MovieSelectionActions"] = HelpableActionMap(self, "MovieSelectionActions",
			{
				"contextMenu": (self.doContext, _("Menu")),
				"showEventInfo": (self.showEventInformation, _("Show event details")),
				"toggleMark": (self.toggleMark, _("Toggle a selection mark")),
				"clearMarks": (self.clearMarks, _("Remove all selection marks"))
			}, description=_("Settings, information and more functions"))

		self["ColorActions"] = HelpableActionMap(self, "ColorActions",
			{
				"red": (self.btn_red, boundFunction(self.getinitUserDefinedActionsDescription, "btn_red")),
				"green": (self.btn_green, boundFunction(self.getinitUserDefinedActionsDescription, "btn_green")),
				"yellow": (self.btn_yellow, boundFunction(self.getinitUserDefinedActionsDescription, "btn_yellow")),
				"blue": (self.btn_blue, boundFunction(self.getinitUserDefinedActionsDescription, "btn_blue")),
				"redlong": (self.btn_redlong, boundFunction(self.getinitUserDefinedActionsDescription, "btn_redlong")),
				"greenlong": (self.btn_greenlong, boundFunction(self.getinitUserDefinedActionsDescription, "btn_greenlong")),
				"yellowlong": (self.btn_yellowlong, boundFunction(self.getinitUserDefinedActionsDescription, "btn_yellowlong")),
				"bluelong": (self.btn_bluelong, boundFunction(self.getinitUserDefinedActionsDescription, "btn_bluelong")),
			}, description=_("User-selectable functions"))
		self["FunctionKeyActions"] = HelpableActionMap(self, "FunctionKeyActions",
			{
				"f1": (self.btn_F1, boundFunction(self.getinitUserDefinedActionsDescription, "btn_F1")),
				"f2": (self.btn_F2, boundFunction(self.getinitUserDefinedActionsDescription, "btn_F2")),
				"f3": (self.btn_F3, boundFunction(self.getinitUserDefinedActionsDescription, "btn_F3")),
			}, description=_("User-selectable functions"))
		self["OkCancelActions"] = HelpableActionMap(self, "OkCancelActions",
			{
				"cancel": (self.abort, _("Exit movie list")),
				"ok": (self.itemSelected, _("Select movie")),
			}, description=_("Selection and exit"))
		self["DirectionActions"] = HelpableActionMap(self, "DirectionActions",
			{
				"up": (self.keyUp, _("Go up the list")),
				"down": (self.keyDown, _("Go down the list"))
			}, prio = -2, description=_("Navigation"))

		tPreview = _("Preview")
		tFwd = _("skip forward") + " (" + tPreview +")"
		tBack= _("skip backward") + " (" + tPreview +")"
		sfwd = lambda: self.seekRelative(1, config.seek.selfdefined_46.value * 90000)
		ssfwd = lambda: self.seekRelative(1, config.seek.selfdefined_79.value * 90000)
		sback = lambda: self.seekRelative(-1, config.seek.selfdefined_46.value * 90000)
		ssback = lambda: self.seekRelative(-1, config.seek.selfdefined_79.value * 90000)
		self["SeekActions"] = HelpableActionMap(self, "MovielistSeekActions",
			{
				"playpauseService": (self.preview, _("Preview")),
				"seekFwd": (sfwd, tFwd),
				"seekFwdManual": (ssfwd, tFwd),
				"seekBack": (sback, tBack),
				"seekBackManual": (ssback, tBack),
			}, prio=5, description=_("Pause, rewind and fast forward"))
		self.onShown.append(self.onFirstTimeShown)
		self.onLayoutFinish.append(self.saveListsize)
		self.list.connectSelChanged(self.updateButtons)
		self.onClose.append(self.__onClose)
		NavigationInstance.instance.RecordTimer.on_state_change.append(self.list.updateRecordings)
		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				#iPlayableService.evSeekableStatusChanged: self.__seekableStatusChanged,
				iPlayableService.evStart: self.__serviceStarted,
				iPlayableService.evEOF: self.__evEOF,
				#iPlayableService.evSOF: self.__evSOF,
			})
		self.onExecBegin.append(self.asciiOn)
		config.misc.standbyCounter.addNotifier(self.standbyCountChanged, initial_call=False)

	def isProtected(self):
		return config.ParentalControl.setuppinactive.value and config.ParentalControl.config_sections.movie_list.value

	def standbyCountChanged(self, value):
		path = self.getTitle().split(" /", 1)
		if path and len(path) > 1:
			if [x for x in path[1].split("/") if x.startswith(".") and not x.startswith(".Trash")]:
				moviepath = defaultMoviePath()
				if moviepath:
					config.movielist.last_videodir.value = defaultMoviePath()
					self.close(None)

	def unhideParentalServices(self):
		if self.protectContextMenu:
			self.session.openWithCallback(self.unhideParentalServicesCallback, PinInput, pinList=[config.ParentalControl.servicepin[0].value], triesEntry=config.ParentalControl.retries.servicepin, title=_("Enter the service pin"), windowTitle=_("Enter pin code"))
		else:
			self.unhideParentalServicesCallback(True)

	def unhideParentalServicesCallback(self, answer):
		if answer:
			from Components.ParentalControl import parentalControl
			parentalControl.setSessionPinCached()
			parentalControl.hideBlacklist()
			self.reloadList()
		elif answer is not None:
			self.session.openWithCallback(self.close, MessageBox, _("The pin code you entered is wrong."), MessageBox.TYPE_ERROR)

	def asciiOn(self):
		rcinput = eRCInput.getInstance()
		rcinput.setKeyboardMode(rcinput.kmAscii)

	def asciiOff(self):
		rcinput = eRCInput.getInstance()
		rcinput.setKeyboardMode(rcinput.kmNone)

	def initUserDefinedActions(self):
		global userDefinedButtons, userDefinedActions, config
		if userDefinedButtons is None:
			userDefinedActions = {
				'delete': _("Delete"),
				'move': _("Move"),
				'copy': _("Copy"),
				'reset': _("Reset"),
				'tags': _("Tags"),
				"createdir": _("Create directory"),
				'addbookmark': _("Add bookmark"),
				'bookmarks': _("Location"),
				'rename': _("Rename"),
				'gohome': _("Home"),
				'sort': _("Sort"),
				'sortby': _("Sort by"),
				'sortdefault': _("Sort by default"),
				'preview': _("Preview"),
				'movieoff': _("On end of movie"),
				'movieoff_menu': _("On end of movie (as menu)"),
				'mark': _("Toggle mark"),
				'clearmarks': _("Clear marks")
			}
			for p in plugins.getPlugins(PluginDescriptor.WHERE_MOVIELIST):
				userDefinedActions['@' + p.name] = p.description.capitalize()
			prefix = _("Goto") + ": "
			for d,p in buildMovieLocationList():
				if p and p.startswith('/'):
					userDefinedActions[p] = prefix + d
			choices = [(k, v) for k, v in userDefinedActions.items()]
			choices.sort(key=lambda t: t[1])
			config.movielist.btn_red = ConfigSelection(default='delete', choices=choices)
			config.movielist.btn_green = ConfigSelection(default='move', choices=choices)
			config.movielist.btn_yellow = ConfigSelection(default='bookmarks', choices=choices)
			config.movielist.btn_blue = ConfigSelection(default='sortby', choices=choices)
			config.movielist.btn_redlong = ConfigSelection(default='rename', choices=choices)
			config.movielist.btn_greenlong = ConfigSelection(default='copy', choices=choices)
			config.movielist.btn_yellowlong = ConfigSelection(default='tags', choices=choices)
			config.movielist.btn_bluelong = ConfigSelection(default='sortdefault', choices=choices)
			config.movielist.btn_radio = ConfigSelection(default='tags', choices=choices)
			config.movielist.btn_tv = ConfigSelection(default='gohome', choices=choices)
			config.movielist.btn_text = ConfigSelection(default='movieoff', choices=choices)
			config.movielist.btn_F1 = ConfigSelection(default='movieoff_menu', choices=choices)
			config.movielist.btn_F2 = ConfigSelection(default='preview', choices=choices)
			config.movielist.btn_F3 = ConfigSelection(default='/media', choices=choices)
			userDefinedButtons ={
				'red': config.movielist.btn_red,
				'green': config.movielist.btn_green,
				'yellow': config.movielist.btn_yellow,
				'blue': config.movielist.btn_blue,
				'redlong': config.movielist.btn_redlong,
				'greenlong': config.movielist.btn_greenlong,
				'yellowlong': config.movielist.btn_yellowlong,
				'bluelong': config.movielist.btn_bluelong,
				'Radio': config.movielist.btn_radio,
				'TV': config.movielist.btn_tv,
				'Text': config.movielist.btn_text,
				'F1': config.movielist.btn_F1,
				'F2': config.movielist.btn_F2,
				'F3': config.movielist.btn_F3
			}

	def getinitUserDefinedActionsDescription(self, key):
		return _(userDefinedActions.get(eval("config.movielist." + key + ".value"), _("Not Defined")))

	def _callButton(self, name):
		if name.startswith('@'):
			item = self.getCurrentSelection()
			if isSimpleFile(item):
				name = name[1:]
				for p in plugins.getPlugins(PluginDescriptor.WHERE_MOVIELIST):
					if name == p.name:
						p(self.session, item[0])
		elif name.startswith('/'):
			self.gotFilename(name)
		else:
			try:
				a = getattr(self, 'do_' + name)
			except Exception:
				# Undefined action
				return
			a()

	def btn_red(self):
		self._callButton(config.movielist.btn_red.value)
	def btn_green(self):
		self._callButton(config.movielist.btn_green.value)
	def btn_yellow(self):
		self._callButton(config.movielist.btn_yellow.value)
	def btn_blue(self):
		self._callButton(config.movielist.btn_blue.value)
	def btn_redlong(self):
		self._callButton(config.movielist.btn_redlong.value)
	def btn_greenlong(self):
		self._callButton(config.movielist.btn_greenlong.value)
	def btn_yellowlong(self):
		self._callButton(config.movielist.btn_yellowlong.value)
	def btn_bluelong(self):
		self._callButton(config.movielist.btn_bluelong.value)
	def btn_radio(self):
		self._callButton(config.movielist.btn_radio.value)
	def btn_tv(self):
		self._callButton(config.movielist.btn_tv.value)
	def btn_text(self):
		self._callButton(config.movielist.btn_text.value)
	def btn_F1(self):
		self._callButton(config.movielist.btn_F1.value)
	def btn_F2(self):
		self._callButton(config.movielist.btn_F2.value)
	def btn_F3(self):
		self._callButton(config.movielist.btn_F3.value)

	def keyUp(self):
		if self["list"].getCurrentIndex() < 1:
			self["list"].moveToLast()
		else:
			self["list"].moveUp()

	def keyDown(self):
		if self["list"].getCurrentIndex() == len(self["list"]) - 1:
			self["list"].moveToFirst()
		else:
			self["list"].moveDown()

	def moveToFirstOrFirstFile(self):
		if self.list.getCurrentIndex() <= self.list.firstFileEntry: #selection above or on first movie
			if self.list.getCurrentIndex() < 1:
				self.list.moveToLast()
			else:
				self.list.moveToFirst()
		else:
			self.list.moveToFirstMovie()

	def moveToLastOrFirstFile(self):
		if self.list.getCurrentIndex() >= self.list.firstFileEntry or self.list.firstFileEntry == len(self.list): #selection below or on first movie or no files
			if self.list.getCurrentIndex() == len(self.list) - 1:
				self.list.moveToFirst()
			else:
				self.list.moveToLast()
		else:
			self.list.moveToFirstMovie()

	def keyNumberGlobal(self, number):
		unichar = self.numericalTextInput.getKey(number)
		charstr = unichar.encode("utf-8")
		if len(charstr) == 1:
			self.list.moveToChar(charstr[0], self["chosenletter"])

	def keyAsciiCode(self):
		unichar = unichr(getPrevAsciiCode())
		charstr = unichar.encode("utf-8")
		if len(charstr) == 1:
			self.list.moveToString(charstr[0], self["chosenletter"])

	def isItemPlayable(self, index):
		item = self.list.getItem(index)
		if item:
			path = item.getPath()
			if not item.flags & eServiceReference.mustDescent:
				ext = os.path.splitext(path)[1].lower()
				if ext in IMAGE_EXTENSIONS:
					return False
				else:
					return True
		return False

	def goToPlayingService(self):
		service = self.session.nav.getCurrentlyPlayingServiceOrGroup()
		if service:
			path = service.getPath()
			if path:
				path = os.path.split(os.path.normpath(path))[0]
				if not path.endswith('/'):
					path += '/'
				self.gotFilename(path, selItem = service)
				return True
		return False

	def playNext(self):
		if self.list.playInBackground:
			if self.list.moveTo(self.list.playInBackground):
				if self.isItemPlayable(self.list.getCurrentIndex() + 1):
					self.list.moveDown()
					self.callLater(self.preview)
			else:
				self.playGoTo = 1
				self.goToPlayingService()
		else:
			self.preview()

	def playPrev(self):
		if self.list.playInBackground:
			if self.list.moveTo(self.list.playInBackground):
				if self.isItemPlayable(self.list.getCurrentIndex() - 1):
					self.list.moveUp()
					self.callLater(self.preview)
			else:
				self.playGoTo = -1
				self.goToPlayingService()
		else:
			current = self.getCurrent()
			if current is not None:
				if self["list"].getCurrentIndex() > 0:
					path = current.getPath()
					path = os.path.abspath(os.path.join(path, os.path.pardir))
					path = os.path.abspath(os.path.join(path, os.path.pardir))
					self.gotFilename(path)

	def __onClose(self):
		config.misc.standbyCounter.removeNotifier(self.standbyCountChanged)
		try:
			NavigationInstance.instance.RecordTimer.on_state_change.remove(self.list.updateRecordings)
		except Exception, e:
			print "[MovieSelection] failed to unsubscribe:", e
			pass

	def createSummary(self):
		return MovieSelectionSummary

	def updateDescription(self):
		if self.settings["description"] == MovieList.SHOW_DESCRIPTION:
			self["DescriptionBorder"].show()
			self["list"].instance.resize(eSize(self.listWidth, self.listHeight-self["DescriptionBorder"].instance.size().height()))
		else:
			self["Service"].newService(None)
			self["DescriptionBorder"].hide()
			self["list"].instance.resize(eSize(self.listWidth, self.listHeight))

	def pauseService(self):
		# Called when pressing Power button (go to standby)
		self.playbackStop()
		self.session.nav.stopService()

	def unPauseService(self):
		# When returning from standby. It might have been a while, so
		# reload the list.
		self.reloadList()

	def can_move(self, item):
		if self.list.countMarked() > 0:
			return True
		return canMove(item)

	def can_delete(self, item):
		if self.list.countMarked() > 0:
			return True
		return canDelete(item)

	def can_default(self, item):
		# returns whether item is a regular file
		return isSimpleFile(item)

	def can_sort(self, item):
		return True

	def can_preview(self, item):
		return isSimpleFile(item)

	def _updateButtonTexts(self):
		for k in ('red', 'green', 'yellow', 'blue'):
			btn = userDefinedButtons[k]
			self['key_' + k].setText(userDefinedActions[btn.value])

	def updateButtons(self):
		item = self.getCurrentSelection()
		for name in ('red', 'green', 'yellow', 'blue'):
			action = userDefinedButtons[name].value
			if action.startswith('@'):
				check = self.can_default
			elif action.startswith('/'):
				check = self.can_gohome
			else:
				try:
					check = getattr(self, 'can_' + action)
				except:
					check = self.can_default
			gui = self["key_" + name]
			if check(item):
				gui.show()
			else:
				gui.hide()

	def showEventInformation(self):
		from Screens.EventView import EventViewSimple
		evt = self["list"].getCurrentEvent()
		if evt:
			self.session.open(EventViewSimple, evt, self.getCurrent())

	def saveListsize(self):
		listsize = self["list"].instance.size()
		self.listWidth = listsize.width()
		self.listHeight = listsize.height()
		self.updateDescription()

	def FilePlaying(self):
		if self.session.nav.getCurrentlyPlayingServiceReference() and ':0:/' in self.session.nav.getCurrentlyPlayingServiceReference().toString():
			self.list.playInForeground = self.session.nav.getCurrentlyPlayingServiceReference()
		else:
			self.list.playInForeground = None
		self.filePlayingTimer.stop()

	def onFirstTimeShown(self):
		self.filePlayingTimer.start(100)
		self.onShown.remove(self.onFirstTimeShown) # Just once, not after returning etc.
		self.show()
		self.reloadList(self.selectedmovie, home=True)
		del self.selectedmovie
		if config.movielist.show_live_tv_in_movielist.value:
			self.LivePlayTimer.start(100)

	def hidewaitingtext(self):
		self.hidewaitingTimer.stop()
		self["waitingtext"].hide()

	def LivePlay(self):
		if self.session.nav.getCurrentlyPlayingServiceReference():
			if ':0:/' not in self.session.nav.getCurrentlyPlayingServiceReference().toString():
				config.movielist.curentlyplayingservice.setValue(self.session.nav.getCurrentlyPlayingServiceReference().toString())
		checkplaying = self.session.nav.getCurrentlyPlayingServiceReference()
		if checkplaying:
			checkplaying = checkplaying.toString()
		if checkplaying is None or (config.movielist.curentlyplayingservice.value != checkplaying and ':0:/' not in self.session.nav.getCurrentlyPlayingServiceReference().toString()):
			self.session.nav.playService(eServiceReference(config.movielist.curentlyplayingservice.value))
		self.LivePlayTimer.stop()

	def getCurrent(self):
		# Returns selected serviceref (may be None)
		return self["list"].getCurrent()

	def getCurrentSelection(self):
		# Returns None or (serviceref, info, begin, len)
		return self["list"].l.getCurrentSelection()

	def getMarkedOrCurrentSelection(self):
		items = self.list.getMarked()
		if not items:
			item = self.getCurrentSelection()
			items = [item] if item else []
		return items

	def playAsBLURAY(self, path):
		try:
			from Plugins.Extensions.BlurayPlayer import BlurayUi
			self.session.open(BlurayUi.BlurayMain, path)
			return True
		except Exception as e:
			print "[MovieSelection] Cannot open BlurayPlayer:", e

	def playAsDVD(self, path):
		try:
			from Screens import DVD
			if path.endswith('VIDEO_TS/'):
				# strip away VIDEO_TS/ part
				path = os.path.split(path.rstrip('/'))[0]
			self.session.open(DVD.DVDPlayer, dvd_filelist=[path])
			return True
		except Exception, e:
			print "[MovieSelection] DVD Player not installed:", e

	def playSuburi(self, path):
		suburi = os.path.splitext(path)[0][:-7]
		for ext in AUDIO_EXTENSIONS:
			if os.path.exists("%s%s" % (suburi, ext)):
				current = eServiceReference(4097, 0, "file://%s&suburi=file://%s%s" % (path, suburi, ext))
				self.close(current)
				return True

	def __serviceStarted(self):
		if not self.list.playInBackground or not self.list.playInForeground:
			return
		ref = self.session.nav.getCurrentService()
		cue = ref.cueSheet()
		if not cue:
			return
		# disable writing the stop position
		cue.setCutListEnable(2)
		# find "resume" position
		cuts = cue.getCutList()
		if not cuts:
			return
		for (pts, what) in cuts:
			if what == 3:
				last = pts
				break
		else:
			# no resume, jump to start of program (first marker)
			last = cuts[0][0]
		self.doSeekTo = last
		self.callLater(self.doSeek)

	def doSeek(self, pts = None):
		if pts is None:
			pts = self.doSeekTo
		seekable = self.getSeek()
		if seekable is None:
			return
		seekable.seekTo(pts)

	def getSeek(self):
		service = self.session.nav.getCurrentService()
		if service is None:
			return None
		seek = service.seek()
		if seek is None or not seek.isCurrentlySeekable():
			return None
		return seek

	def callLater(self, function):
		self.previewTimer = eTimer()
		self.previewTimer.callback.append(function)
		self.previewTimer.start(10, True)

	def __evEOF(self):
		playInBackground = self.list.playInBackground
		playInForeground = self.list.playInForeground
		if not playInBackground:
			print "[MovieSelection] Not playing anything in background"
			return
		self.session.nav.stopService()
		self.list.playInBackground = None
		self.list.playInForeground = None
		if config.movielist.play_audio_internal.value:
			index = self.list.findService(playInBackground)
			if index is None:
				return # Not found?
			next = self.list.getItem(index + 1)
			if not next:
				return
			path = next.getPath()
			ext = os.path.splitext(path)[1].lower()
			print "[MovieSelection] Next up:", path
			if ext in AUDIO_EXTENSIONS:
				self.nextInBackground = next
				self.callLater(self.preview)
				self["list"].moveToIndex(index+1)

		if config.movielist.show_live_tv_in_movielist.value:
			self.LivePlayTimer.start(100)

	def preview(self):
		current = self.getCurrent()
		if current is not None:
			path = current.getPath()
			if current.flags & eServiceReference.mustDescent:
				self.gotFilename(path)
			else:
				Screens.InfoBar.InfoBar.instance.checkTimeshiftRunning(self.previewCheckTimeshiftCallback)

	def startPreview(self):
		if self.nextInBackground is not None:
			current = self.nextInBackground
			self.nextInBackground = None
		else:
			current = self.getCurrent()
		playInBackground = self.list.playInBackground
		playInForeground = self.list.playInForeground
		if playInBackground:
			self.list.playInBackground = None
			from Screens.InfoBar import MoviePlayer
			MoviePlayerInstance = MoviePlayer.instance
			if MoviePlayerInstance is not None:
				from Screens.InfoBarGenerics import setResumePoint
				setResumePoint(MoviePlayer.instance.session)
			self.session.nav.stopService()
			if playInBackground != current:
				# come back to play the new one
				self.callLater(self.preview)
		elif playInForeground:
			self.playingInForeground = playInForeground
			self.list.playInForeground = None
			from Screens.InfoBar import MoviePlayer
			MoviePlayerInstance = MoviePlayer.instance
			if MoviePlayerInstance is not None:
				from Screens.InfoBarGenerics import setResumePoint
				setResumePoint(MoviePlayer.instance.session)
			self.session.nav.stopService()
			if playInForeground != current:
				self.callLater(self.preview)
		else:
			self.list.playInBackground = current
			self.session.nav.playService(current)

	def previewCheckTimeshiftCallback(self, answer):
		if answer:
			self.startPreview()

	def seekRelative(self, direction, amount):
		if self.list.playInBackground or self.list.playInBackground:
			seekable = self.getSeek()
			if seekable is None:
				return
			seekable.seekRelative(direction, amount)

	def playbackStop(self):
		if self.list.playInBackground:
			self.list.playInBackground = None
			from Screens.InfoBar import MoviePlayer
			MoviePlayerInstance = MoviePlayer.instance
			if MoviePlayerInstance is not None:
				from Screens.InfoBarGenerics import setResumePoint
				setResumePoint(MoviePlayer.instance.session)
			self.session.nav.stopService()
			if config.movielist.show_live_tv_in_movielist.value:
				self.LivePlayTimer.start(100)
			self.filePlayingTimer.start(100)
			return
		elif self.list.playInForeground:
			from Screens.InfoBar import MoviePlayer
			MoviePlayerInstance = MoviePlayer.instance
			if MoviePlayerInstance is not None:
				from Screens.InfoBarGenerics import setResumePoint
				setResumePoint(MoviePlayer.instance.session)
				MoviePlayerInstance.close()
			self.session.nav.stopService()
			if config.movielist.show_live_tv_in_movielist.value:
				self.LivePlayTimer.start(100)
			self.filePlayingTimer.start(100)

	def toggleMark(self):
		self.list.toggleMark()
		if self.list.getCurrentIndex() < len(self.list)-1:
			self.list.moveDown()
		self.hideActionFeedback()

	def clearMarks(self):
		self.list.clearMarks()
		self.hideActionFeedback()

	def itemSelected(self):
		markedFiles = self.list.getMarked(excludeDirs=True)
		markedFilesCount = len(markedFiles)
		currentSelection = self.getCurrentSelection()
	
		# Rules:
		#  - if a directory (include parent .. and trash can) is selected, marks are completely ignored and the directory is opened
		#  - if a recording is selected, it's played using the single selection code
		#  - if there are marked recordings and another unmarked recording is selected, ask what to do
		if (currentSelection[0].flags and eServiceReference.isDirectory) or markedFilesCount == 0 or (markedFilesCount == 1 and markedFiles[0] == currentSelection):
			self.__playCurrentItem()
			return

		if currentSelection in markedFiles:
			self.__addItemsToPlaylist(markedFiles)
		else:
			title = ngettext("You have a marked recording", "You have marked recordings", markedFilesCount)
			choices = [
				(ngettext("Play the marked recording", "Play %d marked recordings" % markedFilesCount, markedFilesCount), self.__addItemsToPlaylist, markedFiles),
				(_("Play the selected recording"), self.__playCurrentItem)]
			self.session.open(ChoiceBox, title=title, list=choices)

	def __addItemsToPlaylist(self, markedItems):
		global playlist
		items = playlist
		del items[:]
		audio = config.movielist.play_audio_internal.value
		for item in markedItems:
			itemRef = item[0]
			path = itemRef.getPath()
			if not itemRef.flags & eServiceReference.mustDescent:
				ext = os.path.splitext(path)[1].lower()
				if ext in IMAGE_EXTENSIONS:
					continue
				else:
					items.append(itemRef)
					if audio and ext not in AUDIO_EXTENSIONS:
						audio = False
		if items:
			Screens.InfoBar.InfoBar.instance.checkTimeshiftRunning(boundFunction(self.__addItemsToPlaylistTimeshiftCallback, audio, items))

	def __addItemsToPlaylistTimeshiftCallback(self, audio, items, answer):
		if answer:
			global playingList
			playingList = True
			if audio:
				self.list.moveTo(items[0])
				self.preview()
			else:
				self.saveconfig()
				self.close(items[0])

	def __playCurrentItem(self):
		current = self.getCurrent()
		if current is not None:
			path = current.getPath()
			if current.flags & eServiceReference.mustDescent:
				if BlurayPlayer is not None and os.path.isdir(os.path.join(path, 'BDMV/STREAM/')):
					#force a BLU-RAY extention
					Screens.InfoBar.InfoBar.instance.checkTimeshiftRunning(boundFunction(self.itemSelectedCheckTimeshiftCallback, 'bluray', path))
					return
				if os.path.isdir(os.path.join(path, 'VIDEO_TS/')) or os.path.exists(os.path.join(path, 'VIDEO_TS.IFO')):
					#force a DVD extention
					Screens.InfoBar.InfoBar.instance.checkTimeshiftRunning(boundFunction(self.itemSelectedCheckTimeshiftCallback, '.img', path))
					return
				self.gotFilename(path)
			else:
				ext = os.path.splitext(path)[1].lower()
				if config.movielist.play_audio_internal.value and (ext in AUDIO_EXTENSIONS):
					self.preview()
					return
				if self.list.playInBackground:
					# Stop preview, come back later
					self.session.nav.stopService()
					self.list.playInBackground = None
					self.callLater(self.__playCurrentItem)
					return
				if ext in IMAGE_EXTENSIONS:
					try:
						from Plugins.Extensions.PicturePlayer import ui
						# Build the list for the PicturePlayer UI
						filelist = []
						index = 0
						for item in self.list.list:
							p = item[0].getPath()
							if p == path:
								index = len(filelist)
							if os.path.splitext(p)[1].lower() in IMAGE_EXTENSIONS:
								filelist.append(((p,False), None))
						self.session.open(ui.Pic_Full_View, filelist, index, path)
					except Exception, ex:
						print "[MovieSelection] Cannot display", str(ex)
					return
				Screens.InfoBar.InfoBar.instance.checkTimeshiftRunning(boundFunction(self.itemSelectedCheckTimeshiftCallback, ext, path))

	def itemSelectedCheckTimeshiftCallback(self, ext, path, answer):
		if answer:
			if ext in (".iso", ".img", ".nrg") and BlurayPlayer is not None:
				try:
					from Plugins.Extensions.BlurayPlayer import blurayinfo
					if blurayinfo.isBluray(path) == 1:
						ext = 'bluray'
				except Exception as e:
					print "[MovieSelection] Error in blurayinfo:", e
			if ext == 'bluray':
				if self.playAsBLURAY(path):
					return
			elif ext in DVD_EXTENSIONS:
				if self.playAsDVD(path):
					return
			elif "_suburi." in path:
				if self.playSuburi(path):
					return
			self.movieSelected()

	# Note: DVDBurn overrides this method, hence the itemSelected indirection.
	def movieSelected(self):
		current = self.getCurrent()
		if current is not None:
			self.saveconfig()
			self.close(current)

	def doContext(self):
		currentSelection = self.getCurrentSelection()
		if currentSelection is not None:
			self.session.openWithCallback(self.doneContext, MovieContextMenu, self, currentSelection)

	def doneContext(self, action):
		if action is not None:
			action()

	def saveLocalSettings(self):
		if not config.movielist.settings_per_directory.value:
			return
		try:
			path = os.path.join(config.movielist.last_videodir.value, ".e2settings.pkl")
			file = open(path, "wb")
			pickle.dump(self.settings, file)
			file.close()
		except Exception, e:
			print "[MovieSelection] Failed to save settings to %s: %s" % (path, e)
		# Also set config items, in case the user has a read-only disk
		config.movielist.moviesort.value = self.settings["moviesort"]
		config.movielist.description.value = self.settings["description"]
		config.usage.on_movie_eof.value = self.settings["movieoff"]
		# save movieeof values for using by hotkeys
		config.usage.on_movie_eof.save()

	def loadLocalSettings(self):
		'Load settings, called when entering a directory'
		if config.movielist.settings_per_directory.value:
			try:
				path = os.path.join(config.movielist.last_videodir.value, ".e2settings.pkl")
				file = open(path, "rb")
				updates = pickle.load(file)
				file.close()
				self.applyConfigSettings(updates)
			except IOError, e:
				updates = {
					"moviesort": config.movielist.moviesort.default,
					"description": config.movielist.description.default,
					"movieoff": config.usage.on_movie_eof.default
				}
				self.applyConfigSettings(updates)
				pass # ignore fail to open errors
			except Exception, e:
				print "[MovieSelection] Failed to load settings from %s: %s" % (path, e)
		else:
			updates = {
				"moviesort": config.movielist.moviesort.value,
				"description": config.movielist.description.value,
				"movieoff": config.usage.on_movie_eof.value
				}
			self.applyConfigSettings(updates)

# Remember this starting sort method for this dir.
# selectSortby() needs this to highlight the current sort and
# do_sort() needs it to know whence to move on.
#
		self["list"].current_sort = self.settings["moviesort"]

	def applyConfigSettings(self, updates):
		needUpdate = ("description" in updates) and (updates["description"] != self.settings["description"])
		self.settings.update(updates)
		if needUpdate:
			self["list"].setDescriptionState(self.settings["description"])
			self.updateDescription()
		if self.settings["moviesort"] != self["list"].sort_type:
			self["list"].setSortType(int(self.settings["moviesort"]))
			needUpdate = True
		if self.settings["movieoff"] != self.movieOff:
			self.movieOff = self.settings["movieoff"]
			needUpdate = True
		config.movielist.moviesort.value = self.settings["moviesort"]
		config.movielist.description.value = self.settings["description"]
		config.usage.on_movie_eof.value = self.settings["movieoff"]
		return needUpdate

	def sortBy(self, newType):
		print '[MovieSelection] SORTBY:',newType
		if newType < MovieList.TRASHSORT_SHOWRECORD:
			self.settings["moviesort"] = newType
# If we are using per-directory sort methods then set it now...
#
			if config.movielist.settings_per_directory.value:
				self.saveLocalSettings()
			else:
# ..otherwise, if we are setting permanent sort methods, save it,
# while, for temporary sort methods, indicate to MovieList.py to
# use a temporary sort override.
#
				if config.movielist.perm_sort_changes.value:
					config.movielist.moviesort.setValue(newType)
					config.movielist.moviesort.save()
				else:
					self["list"].temp_sort = newType
			self.setSortType(newType)
# Unset specific trash-sorting if other sort chosen while in Trash
			if MovieList.InTrashFolder:
				config.usage.trashsort_deltime.value = "no"
		else:
			if newType == MovieList.TRASHSORT_SHOWRECORD:
				config.usage.trashsort_deltime.value = "show record time"
			elif newType == MovieList.TRASHSORT_SHOWDELETE:
				config.usage.trashsort_deltime.value = "show delete time"
		self.reloadList()

	def showDescription(self, newType):
		self.settings["description"] = newType
		self.saveLocalSettings()
		self.setDescriptionState(newType)
		self.updateDescription()

	def abort(self):
		def saveAndClose():
			self.saveconfig()
			self.close(None)

		global playlist
		del playlist[:]
		if self.list.playInBackground:
			self.list.playInBackground = None
			self.session.nav.stopService()
			self.saveconfig()
			self.callLater(saveAndClose)
			return

		if self.playingInForeground:
			self.list.playInForeground = self.playingInForeground
			self.session.nav.stopService()
			self.close(self.playingInForeground)
			return

		self.saveconfig()
		self.close(None)

	def saveconfig(self):
		config.movielist.last_selected_tags.value = self.selected_tags

	def configure(self):
		self.session.openWithCallback(self.configureDone, MovieBrowserConfiguration)

	def configureDone(self, result):
		if result:
			self.applyConfigSettings({
			"moviesort": config.movielist.moviesort.value,
				"description": config.movielist.description.value,
				"movieoff": config.usage.on_movie_eof.value})
			self.saveLocalSettings()
			self._updateButtonTexts()
			self["list"].setItemsPerPage()
			self["list"].setFontsize()
			self.reloadList()
			self.updateDescription()

	def can_sortby(self, item):
		return True

	def do_sortby(self):
		self.selectSortby()

# This is the code that displays a menu of all sort options and lets you
# select one to use.  The "Sort by" option.
# It must be compatible with do_sort().
# NOTE: sort methods may be temporary or permanent!
#
	def selectSortby(self):
		menu = []
		index = 0
		used = 0
# Determine the current sorting method so that it may be highlighted...
#
		for x in l_moviesort:
			if int(x[0]) == self["list"].current_sort:
				used = index
			menu.append((_(x[1]), x[0], "%d" % index))
			index += 1
		if MovieList.InTrashFolder:
			for x in l_trashsort:
				if x[3] == config.usage.trashsort_deltime.value:
					used = index
				menu.append((_(x[1]), x[0], "%d" % index))
				index += 1

# Add a help window message to remind the user whether this will set a
# per-directory method or just a temporary override.
# Done by using the way that ChoiceBox handles a multi-line title:
# it makes line1 the title and all succeeding lines go into the "text"
# display.
# We set a text for "settings_per_directory" even though it will never
# get here...just in case one day it does.
#
		title=_("Sort list:")
		if config.movielist.settings_per_directory.value:
			title = title + "\n\n" + _("Set the sort method for this directory")
		else:
			if config.movielist.perm_sort_changes.value:
				title = title + "\n\n" + _("Set the global sort method")
			else:
				title = title + "\n\n" + _("Set a temporary sort method for this directory")
# You can't be currently using a temporary sort method if you use
# perm_sort_changes
				if self["list"].current_sort != self["list"].sort_type:
					title = title + "\n" + _("(You are currently using a temporary sort method)")
		self.session.openWithCallback(self.sortbyMenuCallback, ChoiceBox, title=title, list=menu, selection = used)

	def getPixmapSortIndex(self, which):
		index = int(which)
		if index == MovieList.SORT_ALPHA_DATE_OLDEST_FIRST:
			index = MovieList.SORT_ALPHANUMERIC
		elif index == MovieList.SORT_ALPHAREV_DATE_NEWEST_FIRST:
			index = MovieList.SORT_ALPHANUMERIC_REVERSE
		elif (index == MovieList.TRASHSORT_SHOWRECORD) or (index == MovieList.TRASHSORT_SHOWDELETE):
			index = MovieList.SORT_RECORDED
		return index - 1

	def sortbyMenuCallback(self, choice):
		if choice is None:
			return
		self.sortBy(int(choice[1]))
		self["movie_sort"].setPixmapNum(self.getPixmapSortIndex(choice[1]))

	def getTagDescription(self, tag):
		# TODO: access the tag database
		return tag

	def updateTags(self):
		# get a list of tags available in this list
		self.tags = self["list"].tags

	def setDescriptionState(self, val):
		self["list"].setDescriptionState(val)

	def setSortType(self, type):
		self["list"].setSortType(type)

	def setCurrentRef(self, path):
		self.current_ref = eServiceReference.fromDirectory(path)
		# Magic: this sets extra things to show
		self.current_ref.setName('16384:jpg 16384:png 16384:gif 16384:bmp')

	def reloadList(self, sel = None, home = False):
		self.reload_sel = sel
		self.reload_home = home
		self["waitingtext"].visible = True
		self.pathselectEnabled = False
		self.callLater(self.reloadWithDelay)

	def reloadWithDelay(self):
		if not os.path.isdir(config.movielist.last_videodir.value):
			path = defaultMoviePath()
			config.movielist.last_videodir.value = path
			config.movielist.last_videodir.save()
			self.setCurrentRef(path)
			self["freeDiskSpace"].path = path
			self["TrashcanSize"].update(path)
		else:
			self["TrashcanSize"].update(config.movielist.last_videodir.value)
		if self.reload_sel is None:
			self.reload_sel = self.getCurrent()
		if config.usage.movielist_trashcan.value and os.access(config.movielist.last_videodir.value, os.W_OK):
			Tools.Trashcan.createTrashFolder(config.movielist.last_videodir.value)
		self.loadLocalSettings()
		self["list"].reload(self.current_ref, self.selected_tags)
		self.updateTags()
		title = ""
		if config.usage.setup_level.index >= 2: # expert+
			title += config.movielist.last_videodir.value
		if self.selected_tags:
			title += " - " + ','.join(self.selected_tags)
		self.setTitle(title)
		self.displayMovieOffStatus()
		self.displaySortStatus()
		if not (self.reload_sel and self["list"].moveTo(self.reload_sel)):
			if self.reload_home:
				self["list"].moveToFirstMovie()
		self["freeDiskSpace"].update()
		self["waitingtext"].visible = False
		self.createPlaylist()
		if self.playGoTo:
			if self.isItemPlayable(self.list.getCurrentIndex() + 1):
				if self.playGoTo > 0:
					self.list.moveDown()
				else:
					self.list.moveUp()
				self.playGoTo = None
				self.callLater(self.preview)
		self.callLater(self.enablePathSelect)

	def enablePathSelect(self):
		self.pathselectEnabled = True

	def doPathSelect(self):
		if self.pathselectEnabled:
			self.session.openWithCallback(
				self.gotFilename,
				MovieLocationBox,
				_("Please select the movie path..."),
				config.movielist.last_videodir.value
			)

	def gotFilename(self, res, selItem=None):
		def servicePinEntered(res, selItem, result):
			if result:
				from Components.ParentalControl import parentalControl
				parentalControl.setSessionPinCached()
				parentalControl.hideBlacklist()
				self.gotFilename(res, selItem)
			elif result == False:
				self.session.open(MessageBox, _("The pin code you entered is wrong."), MessageBox.TYPE_INFO, timeout=3)
		if not res:
			return
		# serviceref must end with /
		if not res.endswith('/'):
			res += '/'
		currentDir = config.movielist.last_videodir.value
		if res != currentDir:
			if os.path.isdir(res):
				baseName = os.path.basename(res[:-1])
				if config.ParentalControl.servicepinactive.value and baseName.startswith(".") and not baseName.startswith(".Trash"):
					from Components.ParentalControl import parentalControl
					if not parentalControl.sessionPinCached:
						self.session.openWithCallback(boundFunction(servicePinEntered, res, selItem), PinInput, pinList=[x.value for x in config.ParentalControl.servicepin], triesEntry=config.ParentalControl.retries.servicepin, title=_("Please enter the correct pin code"), windowTitle=_("Enter pin code"))
						return
				config.movielist.last_videodir.value = res
				config.movielist.last_videodir.save()
				self.loadLocalSettings()
				self.setCurrentRef(res)
				self["freeDiskSpace"].path = res
				self["TrashcanSize"].update(res)
				if selItem:
					self.reloadList(home = True, sel = selItem)
				else:
					self.reloadList(home = True, sel = eServiceReference.fromDirectory(currentDir))
			else:
				mbox=self.session.open(
					MessageBox,
					_("Directory %s does not exist.") % res,
					type = MessageBox.TYPE_ERROR,
					timeout = 5
					)
				mbox.setTitle(self.getTitle())

	def pinEntered(self, res, selItem, result):
		if result:
			from Components.ParentalControl import parentalControl
			parentalControl.setSessionPinCached()
			self.gotFilename(res, selItem, False)

	def showAll(self):
		self.selected_tags_ele = None
		self.selected_tags = None
		self.saveconfig()
		self.reloadList(home = True)

	def showTagsN(self, tagele):
		if not self.tags:
			self.showTagWarning()
		elif not tagele or (self.selected_tags and tagele.value in self.selected_tags) or not tagele.value in self.tags:
			self.showTagsMenu(tagele)
		else:
			self.selected_tags_ele = tagele
			self.selected_tags = self.tags[tagele.value]
			self.reloadList(home = True)

	def showTagsFirst(self):
		self.showTagsN(config.movielist.first_tags)

	def showTagsSecond(self):
		self.showTagsN(config.movielist.second_tags)

	def can_tags(self, item):
		return self.tags
	def do_tags(self):
		self.showTagsN(None)

	def tagChosen(self, tag):
		if tag is not None:
			if tag[1] is None: # all
				self.showAll()
				return
			# TODO: Some error checking maybe, don't wanna crash on KeyError
			self.selected_tags = self.tags[tag[0]]
			if self.selected_tags_ele:
				self.selected_tags_ele.value = tag[0]
				self.selected_tags_ele.save()
			self.saveconfig()
			self.reloadList(home = True)

	def showTagsMenu(self, tagele):
		self.selected_tags_ele = tagele
		lst = [(_("show all tags"), None)] + [(tag, self.getTagDescription(tag)) for tag in sorted(self.tags)]
		self.session.openWithCallback(self.tagChosen, ChoiceBox, title=_("Please select the tag to filter..."), list = lst, skin_name = "MovieListTags")

	def showTagWarning(self):
		mbox=self.session.open(MessageBox, _("No tags are set on these movies."), MessageBox.TYPE_ERROR)
		mbox.setTitle(self.getTitle())

	def selectMovieLocation(self, title, callback):
		bookmarks = buildMovieLocationList(includeOther=True)
		self.session.openWithCallback(lambda choice: self.gotMovieLocation(title, callback, choice), ChoiceBox, title=title, list=bookmarks)

	def gotMovieLocation(self, title, callback, choice):
		if not choice:
			# cancelled
			callback(None)
			return
		if isinstance(choice, tuple):
			if choice[1] is None:
				# Display full browser, which returns string
				self.session.openWithCallback(
					lambda choice: self.gotMovieLocation(title, callback, choice),
					MovieLocationBox,
					title,
					config.movielist.last_videodir.value
				)
				return
			choice = choice[1]
		choice = os.path.normpath(choice)
		self.rememberMovieLocation(choice)
		callback(choice)

	def rememberMovieLocation(self, where):
		if where in last_selected_dest:
			last_selected_dest.remove(where)
		last_selected_dest.insert(0, where)
		if len(last_selected_dest) > 5:
			del last_selected_dest[-1]

	def playBlurayFile(self):
		if self.playfile:
			Screens.InfoBar.InfoBar.instance.checkTimeshiftRunning(self.autoBlurayCheckTimeshiftCallback)

	def autoBlurayCheckTimeshiftCallback(self, answer):
		if answer:
			playRef = eServiceReference(3, 0, self.playfile)
			self.playfile = ""
			self.close(playRef)

	def isBlurayFolderAndFile(self, service):
		self.playfile = ""
		folder = os.path.join(service.getPath(), "STREAM/")
		if "BDMV/STREAM/" not in folder:
			folder = folder[:-7] + "BDMV/STREAM/"
		if os.path.isdir(folder):
			fileSize = 0
			for name in os.listdir(folder):
				try:
					if name.endswith(".m2ts"):
						size = os.stat(folder + name).st_size
						if size > fileSize:
							fileSize = size
							self.playfile = folder + name
				except:
					print "[ML] Error calculate size for %s" % (folder + name)
			if self.playfile:
				return True
		return False

	def can_mark(self):
		return True

	def do_mark(self):
		self.toggleMark()

	def can_clearmarks(self):
		return True

	def do_clearmarks(self):
		self.clearMarks()

	def can_bookmarks(self, item):
		return True
	def do_bookmarks(self):
		self.selectMovieLocation(title=_("Please select the movie path..."), callback=self.gotFilename)

	def can_addbookmark(self, item):
		self.list.countMarked() == 0

	def exist_bookmark(self):
		path = config.movielist.last_videodir.value
		if path in config.movielist.videodirs.value:
			return True
		return False

	def do_addbookmark(self):
		if self.list.countMarked():
			return
		path = config.movielist.last_videodir.value
		if path in config.movielist.videodirs.value:
			if len(path) > 40:
				path = '...' + path[-40:]
			mbox=self.session.openWithCallback(self.removeBookmark, MessageBox, _("Do you really want to remove your bookmark of %s?") % path)
			mbox.setTitle(self.getTitle())
		else:
			config.movielist.videodirs.value += [path]
			config.movielist.videodirs.save()
	def removeBookmark(self, yes):
		if not yes:
			return
		path = config.movielist.last_videodir.value
		bookmarks = config.movielist.videodirs.value
		bookmarks.remove(path)
		config.movielist.videodirs.value = bookmarks
		config.movielist.videodirs.save()

	def can_createdir(self, item):
		return True

	def do_createdir(self):
		dirname = ""
		# use most recently marked item or the selection as a template 
		# for the new directory name
		items = self.getMarkedOrCurrentSelection()
		item = items[-1] if len(items) > 0 else None
		if item is not None and item[0] and item[1]:
			dirname = getItemDisplayName(item[0], item[1], removeExtension=True)
		self.session.openWithCallback(self.createDirCallback, VirtualKeyBoard,
			title = _("Please enter the name of the new directory"),
			text = dirname)
	def createDirCallback(self, name):
		if not name:
			return
		msg = None
		try:
			path = os.path.join(config.movielist.last_videodir.value, name)
			os.mkdir(path)
			if not path.endswith('/'):
				path += '/'
			self.reloadList(sel = eServiceReference.fromDirectory(path))
		except OSError, e:
			print "[MovieSelection] Error %s:" % e.errno, e
			if e.errno == 17:
				msg = _("The path %s already exists.") % name
			else:
				msg = _("Error") + '\n' + str(e)
		except Exception, e:
			print "[MovieSelection] Unexpected error:", e
			msg = _("Error") + '\n' + str(e)
		if msg:
			mbox=self.session.open(MessageBox, msg, type = MessageBox.TYPE_ERROR, timeout = 5)
			mbox.setTitle(self.getTitle())

	def can_rename(self, item):
		return self.can_move(item)

	def do_rename(self):
		renameList = []
		itemCount = 0
		msg = None
		for item in self.getMarkedOrCurrentSelection():
			itemRef = item[0]
		 	if not canRename(item):
				continue
			if isFolder(item):
				if itemCount > 0:
					msg = _("Directories cannot be bulk renamed")
					break
			else:
				path = itemRef.getPath().rstrip('/')
				meta = path + '.meta'
				if not os.path.isfile(meta):
					name, extension = os.path.splitext(path)
					if itemCount > 0:
						msg = _("%s files cannot be bulk renamed") % extension[1:]
						break
			itemCount += 1
			renameList.append(item)

		if msg:
			mbox = self.session.open(MessageBox, msg, type=MessageBox.TYPE_ERROR, timeout=5)
			mbox.setTitle(self.getTitle())
			return
		if not renameList:
			return

		# use the most recently marked item as the rename suggestion
		primaryItem = renameList[-1]
		itemRef, info = primaryItem[:2]
		name = getItemDisplayName(itemRef, info, removeExtension=True)

		self.session.openWithCallback(lambda newname: self.renameCallback(renameList, newname), VirtualKeyBoard,
			title=_("Rename"), text=name)

	def renameCallback(self, renameList, newname):
		if not newname:
			return

		newname = newname.strip()
		failedList = []
		for item in renameList:
			itemRef = item[0]
			path = itemRef.getPath().rstrip('/')
			meta = path + '.meta'
			try:
				if isFolder(item) or not os.path.isfile(meta):
					newItemRef = renameServiceFiles(itemRef, newname)
					if newItemRef:
						self.list.removeMark(itemRef)
						index = self.list.findService(newItemRef)
						self.list.invalidateItem(index)
					else:
						failedList.append(_("'%s' already exists") % os.path.basename(path))
				else:
					metafile = open(meta, "r+")
					sid = metafile.readline()
					oldtitle = metafile.readline()
					rest = metafile.read()
					metafile.seek(0)
					metafile.write("%s%s\n%s" % (sid, newname, rest))
					metafile.truncate()
					metafile.close()
					self.list.removeMark(itemRef)
					if item[3]:
						item[3].txt = newname
					else:
						index = self.list.findService(itemRef)
						self.list.invalidateItem(index)
			except Exception as ex:
				print("[MovieSelection] Unexpected error renaming '%s':%s" % (path, ex))
				failedList.append(_("Error renaming '%s'") % os.path.basename(path) + '\n' + str(ex))
		if len(failedList) > 0:
			msg = "\n".join(failedList)
			mbox = self.session.open(MessageBox, msg, type=MessageBox.TYPE_ERROR, timeout=5)
			mbox.setTitle(self.getTitle())

	def can_decode(self, item):
		return self.list.countMarked() == 0 and item[0].getPath().endswith('.ts')

	def do_decode(self):
		if self.list.countMarked() > 0:
			return
		item = self.getCurrentSelection()
		info = item[1]
		filepath = item[0].getPath()
		if not filepath.endswith('.ts'):
			return
		serviceref = eServiceReference(eServiceReference.idDVB, 0, filepath)
		name = info.getName(item[0]) + ' - decoded'
		description = info.getInfoString(item[0], iServiceInformation.sDescription)
		recording = RecordTimer.RecordTimerEntry(serviceref, int(time.time()), int(time.time()) + 3600, name, description, 0, dirname = preferredTimerPath())
		recording.dontSave = True
		recording.autoincrease = True
		recording.setAutoincreaseEnd()
		self.session.nav.RecordTimer.record(recording, ignoreTSC = True)

	def can_reset(self, item):
		for item in self.getMarkedOrCurrentSelection():
			if isSimpleFile(item):
				return True
		return False

	def do_reset(self):
		for item in self.getMarkedOrCurrentSelection():
			itemRef = item[0]
			path = itemRef.getPath()
			if os.path.isfile(path):
				resetMoviePlayState(itemRef.getPath() + ".cuts", itemRef)
				index = self.list.findService(itemRef)
				self.list.removeMark(itemRef)
				self.list.invalidateItem(index)

	def do_move(self):
		moveList = [item for item in self.getMarkedOrCurrentSelection() if canMove(item)]
		if not moveList:
			return

		itemRef, info = moveList[0][:2]
		path = os.path.normpath(itemRef.getPath())
		moveCount = len(moveList)
		if moveCount == 1:
			name = getItemDisplayName(itemRef, info)
		else:
			name = _("%d items") % moveCount
		# show a more limited list of destinations, no point in showing mountpoints.
		title = _("Select destination for:") + " " + name
		bookmarks = buildMovieLocationList(includeOther=True, path=path, includeSubdirs=True, includeParentDir=True)
		callback = lambda choice: self.gotMoveMovieDest(moveList, choice)
		self.session.openWithCallback(lambda choice: self.gotMovieLocation(title, callback, choice), ChoiceBox, title=title, list=bookmarks)

	def gotMoveMovieDest(self, moveList, choice):
		if not choice:
			return
		dest = os.path.normpath(choice)
		movedList = []
		failedList = []
		name = ""
		for item in moveList:
			itemRef, info = item[:2]
			name = getItemDisplayName(itemRef, info)
			try:
				moveServiceFiles(itemRef, dest, name)
				movedList.append(itemRef)
			except Exception as ex:
				failedList.append((name, ex))
		
		if movedList:
			self["list"].removeServices(movedList)
			movedCount = len(movedList)
			self.showActionFeedback(_("Moved '%s'") % name if movedCount == 1 else _("Moved %d items") % movedCount)
		if failedList:
			failedCount = len(failedList)
			if failedCount == 1:
				msg = _("Couldn't move '%s'.\n%s") % (failedList[0], failedList[1])
			else:
				msg = _("Couldn't move %d items.\n%s") % (failedCount, failedList[0][1])
			mbox = self.session.open(MessageBox, msg, MessageBox.TYPE_ERROR)
			mbox.setTitle(self.getTitle())

	def do_copy(self):
		copyList = [item for item in self.getMarkedOrCurrentSelection() if canCopy(item)]
		if not copyList:
			return
		copyCount = len(copyList)
		if copyCount == 1:
			item = copyList[0]
			itemRef, info = item[:2]
			name = getItemDisplayName(itemRef, info)
		else:
			name = _("%d items") % copyCount

		self.selectMovieLocation(title=_("Select copy destination for:") + " " + name, callback=lambda choice: self.gotCopyMovieDest(copyList, choice))

	def gotCopyMovieDest(self, copyList, choice):
		if not choice:
			return
		dest = os.path.normpath(choice)
		failedList = []
		for item in copyList:
			itemRef, info = item[:2]
			name = getItemDisplayName(itemRef, info)
			try:
				copyServiceFiles(itemRef, dest, name)
				self.list.removeMark(itemRef)
			except Exception as ex:
				failedList.append((name, ex))
		
		if failedList:
			failedCount = len(failedList)
			if failedCount == 1:
				msg = _("Couldn't copy '%s'.\n%s") % (failedList[0][0], failedList[0][1])
			else:
				msg = _("Couldn't copy %d items.\n%s") % (failedCount, failedList[0][1])
			mbox = self.session.open(MessageBox, msg, MessageBox.TYPE_ERROR)
			mbox.setTitle(self.getTitle())

	def stopTimer(self, timer):
		if timer.isRunning():
			if timer.repeated:
				timer.enable()
				timer.processRepeated(findRunningEvent = False)
				self.session.nav.RecordTimer.doActivate(timer)
			else:
				timer.afterEvent = RecordTimer.AFTEREVENT.NONE
				NavigationInstance.instance.RecordTimer.removeEntry(timer)

	def do_delete(self):
		delList = []
		recList = []
		dirCount = fileCount = subItemCount = 0
		inTrash = None
		markedItems = self.getMarkedOrCurrentSelection()
		# Check for the items that can only be single selected:
		#  - Trash can't be marked but can be deleted as a shortcut for deleting all trash
		#  - Parent directory (..) cannot be deleted
		if len(markedItems) == 1:
			item = markedItems[0]
			itemRef, info = item[:2]
			if isTrashFolder(itemRef):
				self.purgeAll()
				return
			elif not info: # parent directory
				return
		for item in markedItems:
			itemRef = item[0]
			if inTrash is None:
				inTrash = isInTrashFolder(itemRef)
			itemPath = os.path.realpath(itemRef.getPath())
			if not os.path.exists(itemPath):
				continue
			delList.append(item)
			if isFolder(item):
				dirs, files = countFiles(itemPath)
				dirCount += 1
				subItemCount += dirs + files
			else:
				fileCount += 1
				# check if this item is currently recording
				rec_filename = itemPath[:-3] if itemPath.endswith(".ts") else itemPath
				for timer in NavigationInstance.instance.RecordTimer.timer_list:
					if timer.isRunning() and not timer.justplay and rec_filename == timer.Filename:
						recList.append((item, timer))

		delInfo = (dirCount, fileCount, subItemCount, inTrash)
		if len(recList) == 0:
			self.__showDeleteConfirmation(delList, delInfo)
		else:
			# Some of the recordings are in progress, show timer confirmation
			recCount = len(recList)
			if recCount == 1:
				item = recList[0][0]
				itemRef, info = item[:2]
				name = item and info.getName(itemRef) or ""
			else:
				name = ""
			title = "Recording in progress: %s" % name if recCount == 1 else "Recordings in progress: %d" % recCount
			choices = [
				(_("Cancel"), None),
				(ngettext("Stop this recording", "Stop these recordings", recCount), "s"),
				(ngettext("Stop this recording and delete it", "Stop these recordings and delete them", recCount), "d")]
			self.session.openWithCallback(lambda choice: self.__onTimerChoice(delList, recList, delInfo, choice), ChoiceBox, title=title, list=choices)

	def __onTimerChoice(self, delList, recList, delInfo, choice):
		if choice is None or choice[1] is None:
			return
		for rec in recList:
			self.stopTimer(rec[1])
		# only continue if the delete option was selected, otherwise unmark everything
		if choice[1] == "d":
			self.__showDeleteConfirmation(delList, delInfo)
		else:
			self.clearMarks()

	def __showDeleteConfirmation(self, delList, delInfo):
		dirCount, fileCount, subItemCount, inTrash = delInfo
		callback = lambda confirmed: self.__permanentDeleteListConfirmed(delList, confirmed)
		itemCount = dirCount + fileCount
		singleName = None
		if itemCount == 1:
			itemRef, info = delList[0][:2]
			singleName = getItemDisplayName(itemRef, info)
		if inTrash:
			if itemCount == 1:
				are_you_sure = _("Do you really want to permanently delete '%s' from the trash can?") % singleName
			else:
				are_you_sure = _("Do you really want to permanently delete these %d items from the trash can?") % itemCount
		elif config.usage.movielist_trashcan.value:
			if itemCount == 1:
				are_you_sure = _("Do you really want to move '%s' to the trash can?") % singleName
			else:
				are_you_sure = _("Do you really want to move these %d items to the trash can?") % itemCount
			callback = lambda confirmed: self.__deleteListConfirmed(delList, confirmed)
		else:
			if itemCount == 1:
				are_you_sure = _("Do you really want to permanently delete '%s'?") % singleName
			else:
				are_you_sure = _("Do you really want to permanently delete these %d items?") % itemCount
		if dirCount > 0 and subItemCount > 0:
			# deleting one or more non empty directories, so it's a good idea to get confirmation
			if itemCount == 1:
				are_you_sure += _("\nIt contains other items.")
			else:
				are_you_sure += ngettext("\nOne is a directory that isn't empty.", "\nThere are directories that aren't empty.", dirCount)
		elif not inTrash and config.usage.movielist_trashcan.value:
			# currently we don't ask for confirmation when moving just files into the trash can
			self.__deleteListConfirmed(delList, True)
			return
		mbox = self.session.openWithCallback(callback, MessageBox, are_you_sure)
		mbox.setTitle(self.getTitle())

	def __deleteListConfirmed(self, delList, confirmed):
		if not confirmed or not delList:
			return

		path = os.path.realpath(delList[0][0].getPath())
		trash = Tools.Trashcan.createTrashFolder(path)
		name = ""
		if trash:
			deletedList = []
			failedList = []
			for delItem in delList:
				itemRef, info = delItem[:2]
				name = getItemDisplayName(itemRef, info)
				path = os.path.realpath(itemRef.getPath())
				if not os.path.exists(path):
					continue
				try:
					moveServiceFiles(itemRef, trash)
					from Screens.InfoBarGenerics import delResumePoint
					delResumePoint(itemRef)
					deletedList.append(itemRef)
				except Exception as ex:
					print("[MovieSelection] Couldn't move to trash '%s'. %s" % (path, ex))
					failedList.append(delItem)

			if deletedList:
				self["list"].removeServices(deletedList)
				deletedCount = len(deletedList)
				self.showActionFeedback(_("Deleted '%s'") % name if deletedCount == 1 else _("Deleted %d items") % deletedCount)
		else:
			failedList = delList

		# some things didn't move to the trash can. Ask whether we should try doing a permanent delete instead
		if failedList:
			failedCount = len(failedList)
			if failedCount == 1:
				msg = _("Couldn't move '%s' to the trash can. Do you want to delete it instead?") % getItemDisplayName(*failedList[0][:2])
			else:
				msg= _("Couldn't move %d items to the trash can. Do you want to delete them instead?") % failedCount
			mbox = self.session.openWithCallback(lambda confirmed: self.__permanentDeleteListConfirmed(failedList, confirmed), MessageBox, msg)
			mbox.setTitle(self.getTitle())

	def __permanentDeleteListConfirmed(self, delList, confirmed):
		if not confirmed:
			return

		deletedList = []
		failedList = []
		name = ""
		for delItem in delList:
			itemRef, info = delItem[:2]
			name = getItemDisplayName(itemRef, info)
			serviceHandler = eServiceCenter.getInstance()
			offline = serviceHandler.offlineOperations(itemRef)
			path = os.path.realpath(itemRef.getPath())
			try:
				if offline is None:
					from enigma import eBackgroundFileEraser
					eBackgroundFileEraser.getInstance().erase(path)
				else:
					if offline.deleteFromDisk(0):
						raise Exception("Offline delete failed")
				from Screens.InfoBarGenerics import delResumePoint
				delResumePoint(itemRef)
				deletedList.append(itemRef)
			except Exception as ex:
				print("[MovieSelection] Couldn't delete '%s'. %s" % (path, ex))
				failedList.append((name, ex))

		if deletedList:
			self["list"].removeServices(deletedList)
			deletedCount = len(deletedList)
			self.showActionFeedback(_("Deleted '%s'") % name if deletedCount == 1 else _("Deleted %d items") % deletedCount)

		# some things didn't delete. Ask whether we should try doing a permanent delete instead
		if failedList:
			failedCount = len(failedList)
			msg = _("Couldn't delete '%s'.") % failedList[0] if failedCount == 1 else _("Couldn't delete %d items.") % failedCount
			mbox = self.session.open(MessageBox, msg, MessageBox.TYPE_ERROR)
			mbox.setTitle(self.getTitle())

	def purgeAll(self):
		recordings = self.session.nav.getRecordings()
		next_rec_time = -1
		if not recordings:
			next_rec_time = self.session.nav.RecordTimer.getNextRecordingTime()
		if recordings or (next_rec_time > 0 and (next_rec_time - time.time()) < 120):
			msg = "\n" + _("Recording(s) are in progress or coming up in few seconds!")
		else:
			msg = ""
		mbox=self.session.openWithCallback(self.purgeConfirmed, MessageBox, _("Permanently delete all recordings in the trash can?") + msg)
		mbox.setTitle(self.getTitle())

	def purgeConfirmed(self, confirmed):
		if not confirmed:
			return
		item = self.getCurrentSelection()
		current = item[0]
		Tools.Trashcan.cleanAll(os.path.split(current.getPath())[0])

	def showNetworkMounts(self):
		import NetworkSetup
		self.session.open(NetworkSetup.NetworkMountsMenu)

	def showDeviceMounts(self):
		import Plugins.SystemPlugins.ViX.MountManager
		self.session.open(Plugins.SystemPlugins.ViX.MountManager.VIXDevicesPanel)

	def showActionFeedback(self, text):
		if self.feedbackTimer is None:
			self.feedbackTimer = eTimer()
			self.feedbackTimer.callback.append(self.hideActionFeedback)
		else:
			self.feedbackTimer.stop()
		self.feedbackTimer.start(3000, 1)
		self.diskinfo.setText(text)

	def hideActionFeedback(self):
		markedCount = self.list.countMarked()
		if markedCount > 0:
			self.diskinfo.setText(ngettext(_("%d marked item"), _("%d marked items"), markedCount) % markedCount)
		else:
			self.diskinfo.update()
			current = self.getCurrent()
			if current is not None:
				self.trashinfo.update(current.getPath())

	def can_gohome(self, item):
		return True

	def do_gohome(self):
		self.gotFilename(defaultMoviePath())

	def do_sortdefault(self):
		print '[MovieSelection] SORT:',config.movielist.moviesort.value
		config.movielist.moviesort.load()
		print '[MovieSelection] SORT:',config.movielist.moviesort.value
		self.sortBy(int(config.movielist.moviesort.value))

# This is the code that advances to the "next" sort method
# on each button press.  The "Sort" option.
# It must be compatible with selectSortby().
# NOTE: sort methods may be temporary or permanent!
#
	def do_sort(self):
		index = 0
# Find the current sort method, then advance to the next...
#
		for index, item in enumerate(l_moviesort):
			if int(item[0]) == self["list"].current_sort:
				break
		if index >= len(l_moviesort) - 1:
			index = 0
		else:
			index += 1
		#descriptions in native languages too long...
		sorttext = l_moviesort[index][2]
		if config.movielist.btn_red.value == "sort": self['key_red'].setText(sorttext)
		if config.movielist.btn_green.value == "sort": self['key_green'].setText(sorttext)
		if config.movielist.btn_yellow.value == "sort": self['key_yellow'].setText(sorttext)
		if config.movielist.btn_blue.value == "sort": self['key_blue'].setText(sorttext)
		self.sorttimer = eTimer()
		self.sorttimer.callback.append(self._updateButtonTexts)
		self.sorttimer.start(3000, True) #time for displaying sorting type just applied
		self.sortBy(int(l_moviesort[index][0]))
		self["movie_sort"].setPixmapNum(self.getPixmapSortIndex(l_moviesort[index][0]))

	def installedMovieManagerPlugin(self):
		try:
			from Plugins.Extensions.MovieManager.ui import MovieManager
			return True
		except Exception as e:
			print "[MovieSelection] MovieManager is not installed...", e
			return False

	def runMovieManager(self):
		if self.installedMovieManagerPlugin():
			from Plugins.Extensions.MovieManager.ui import MovieManager
			self.session.open(MovieManager, self["list"])

	def do_preview(self):
		self.preview()

	def displaySortStatus(self):
		self["movie_sort"].setPixmapNum(self.getPixmapSortIndex(config.movielist.moviesort.value))
		self["movie_sort"].show()

	def can_movieoff(self, item):
		return True

	def do_movieoff(self):
		self.setNextMovieOffStatus()
		self.displayMovieOffStatus()

	def displayMovieOffStatus(self):
		self["movie_off"].setPixmapNum(config.usage.on_movie_eof.getIndex())
		self["movie_off"].show()

	def setNextMovieOffStatus(self):
		config.usage.on_movie_eof.selectNext()
		self.settings["movieoff"] = config.usage.on_movie_eof.value
		self.saveLocalSettings()

	def can_movieoff_menu(self, item):
		return True

	def do_movieoff_menu(self):
		current_movie_eof = config.usage.on_movie_eof.value
		menu = []
		for x in config.usage.on_movie_eof.choices:
			config.usage.on_movie_eof.value = x
			menu.append((config.usage.on_movie_eof.getText(), x))
		config.usage.on_movie_eof.value = current_movie_eof
		used = config.usage.on_movie_eof.getIndex()
		self.session.openWithCallback(self.movieoffMenuCallback, ChoiceBox, title = _("On end of movie"), list = menu, selection = used)

	def movieoffMenuCallback(self, choice):
		if choice is None:
			return
		self.settings["movieoff"] = choice[1]
		self.saveLocalSettings()
		self.displayMovieOffStatus()

	def createPlaylist(self):
		global playlist
		items = playlist
		del items[:]
		for index, item in enumerate(self["list"]):
			if item:
				item = item[0]
				path = item.getPath()
				if not item.flags & eServiceReference.mustDescent:
					ext = os.path.splitext(path)[1].lower()
					if ext in IMAGE_EXTENSIONS:
						continue
					else:
						items.append(item)

playlist = []
