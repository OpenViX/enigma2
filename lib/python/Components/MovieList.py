import os
import struct
import random
from time import localtime, strftime

from GUIComponent import GUIComponent
from Tools.FuzzyDate import FuzzyTime
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmapAlphaBlend, MultiContentEntryProgress
from Components.config import config
from Components.Renderer.Picon import getPiconName
from Screens.LocationBox import defaultInhibitDirs
from Tools.Directories import SCOPE_ACTIVE_SKIN, resolveFilename
from Tools.Trashcan import getTrashFolder, isTrashFolder
import NavigationInstance
from skin import parseColor, parseFont, parseScale

from enigma import eListboxPythonMultiContent, eListbox, gFont, iServiceInformation, eSize, loadPNG, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_VALIGN_CENTER, BT_SCALE, BT_KEEP_ASPECT_RATIO, BT_HALIGN_CENTER, BT_ALIGN_CENTER, BT_VALIGN_CENTER, eServiceReference, eServiceCenter, eTimer

AUDIO_EXTENSIONS = frozenset((".dts", ".mp3", ".wav", ".wave", ".wv", ".oga", ".ogg", ".flac", ".m4a", ".mp2", ".m2a", ".wma", ".ac3", ".mka", ".aac", ".ape", ".alac", ".amr", ".au", ".mid"))
DVD_EXTENSIONS = frozenset((".iso", ".img", ".nrg"))
IMAGE_EXTENSIONS = frozenset((".jpg", ".png", ".gif", ".bmp", ".jpeg", ".jpe"))
MOVIE_EXTENSIONS = frozenset((".mpg", ".vob", ".m4v", ".mkv", ".avi", ".divx", ".dat", ".flv", ".mp4", ".mov", ".wmv", ".asf", ".3gp", ".3g2", ".mpeg", ".mpe", ".rm", ".rmvb", ".ogm", ".ogv", ".m2ts", ".mts", ".webm", ".pva", ".wtv", ".ts"))
KNOWN_EXTENSIONS = MOVIE_EXTENSIONS.union(IMAGE_EXTENSIONS, DVD_EXTENSIONS, AUDIO_EXTENSIONS)

# Gets the name of a movielist item for display in the UI honouring the hide extensions setting
def getItemDisplayName(itemRef, info, removeExtension=None):
	if itemRef.flags & eServiceReference.isGroup:
		name = itemRef.getName()
	elif itemRef.flags & eServiceReference.isDirectory:
		name = info.getName(itemRef)
		name = os.path.basename(name.rstrip("/"))
	else:
		name = info.getName(itemRef)
		removeExtension = config.movielist.hide_extensions.value if removeExtension is None else removeExtension
		if removeExtension:
			fileName, fileExtension = os.path.splitext(name)
			if fileExtension in KNOWN_EXTENSIONS:
				name = fileName
	return name

def expandCollections(items):
	expanded = []
	for item in items:
		if item[0].flags & eServiceReference.isGroup:
			expanded.extend(item[3].collectionItems)
		else:
			expanded.append(item)
	return expanded

cutsParser = struct.Struct('>QI') # big-endian, 64-bit PTS and 32-bit type

class MovieListData:
	def __init__(self):
		self.dirty = True

# iStaticServiceInformation
class StubInfo:
	def __init__(self):
		pass

	def getName(self, serviceref):
		return os.path.split(serviceref.getPath())[1]
	def getLength(self, serviceref):
		return -1
	def getEvent(self, serviceref, *args):
		return None
	def isPlayable(self):
		return True
	def getInfo(self, serviceref, w):
		if w == iServiceInformation.sTimeCreate:
			return os.stat(serviceref.getPath()).st_ctime
		if w == iServiceInformation.sFileSize:
			return os.stat(serviceref.getPath()).st_size
		if w == iServiceInformation.sDescription:
			return serviceref.getPath()
		return 0
	def getInfoString(self, serviceref, w):
		return ''
justStubInfo = StubInfo()

def lastPlayPosFromCache(ref):
	from Screens.InfoBarGenerics import resumePointCache
	return resumePointCache.get(ref.toString(), None)

def moviePlayState(cutsFileName, ref, length):
	"""Returns None, 0..100 for percentage"""
	try:
		# read the cuts file first
		f = open(cutsFileName, 'rb')
		lastPosition = None
		while 1:
			data = f.read(cutsParser.size)
			if len(data) < cutsParser.size:
				break
			cut, cutType = cutsParser.unpack(data)
			if cutType == 3: # undocumented, but 3 appears to be the stop
				lastPosition = cut
		f.close()
		# See what we have in RAM (it might help)
		last = lastPlayPosFromCache(ref)
		if last:
			# Get the cut point from the cache if not in the file
			lastPosition = last[1]
			# Get the length from the cache
			length = last[2]
		else:
			if length and (length > 0):
				length = length * 90000
			else:
				if lastPosition:
					return 50
		if lastPosition is None:
			# Unseen movie
			return None
		if lastPosition >= length:
			return 100
		return (100 * lastPosition) // length
	except:
		last = lastPlayPosFromCache(ref)
		if last:
			lastPosition = last[1]
			if not length or (length < 0):
				length = last[2]
			if length:
				if lastPosition >= length:
					return 100
				return (100 * lastPosition) // length
			else:
				if lastPosition:
					return 50
		return None

def resetMoviePlayState(cutsFileName, ref=None):
	try:
		if ref is not None:
			from Screens.InfoBarGenerics import delResumePoint
			delResumePoint(ref)
		f = open(cutsFileName, 'rb')
		cutlist = []
		while 1:
			data = f.read(cutsParser.size)
			if len(data) < cutsParser.size:
				break
			cut, cutType = cutsParser.unpack(data)
			if cutType != 3:
				cutlist.append(data)
		f.close()
		f = open(cutsFileName, 'wb')
		f.write(''.join(cutlist))
		f.close()
	except:
		pass

class MovieList(GUIComponent):
	SORT_ALPHANUMERIC = 1
	SORT_RECORDED = 2
	SHUFFLE = 3
	SORT_ALPHANUMERIC_REVERSE = 4
	SORT_RECORDED_REVERSE = 5
	SORT_ALPHANUMERIC_FLAT = 6
	SORT_ALPHANUMERIC_FLAT_REVERSE = 7
	SORT_GROUPWISE = 8
	SORT_ALPHA_DATE_OLDEST_FIRST = 9
	SORT_ALPHAREV_DATE_NEWEST_FIRST = 10
	SORT_LONGEST = 11
	SORT_SHORTEST = 12

	HIDE_DESCRIPTION = 1
	SHOW_DESCRIPTION = 2

	# So MovieSelection.selectSortby() can find out whether we are
	# in a Trash folder and, if so, what the last sort was
	# The numbering starts after SORT_* values above.
	# in MovieSelection.py (that has no SORT_GROUPWISE)
	# NOTE! that these two *must* *follow on* from the end of the
	#       SORT_* items above!
	#
	TRASHSORT_SHOWRECORD = 13
	TRASHSORT_SHOWDELETE = 14
	UsingTrashSort = False
	InTrashFolder = False

	def __init__(self, root, sort_type=None, descr_state=None, allowCollections=False):
		GUIComponent.__init__(self)
		self.list = []
		self.descr_state = descr_state or self.HIDE_DESCRIPTION
		self.sort_type = sort_type or self.SORT_GROUPWISE
		self.firstFileEntry = 0
		self.parentDirectory = 0
		self.fontName = "Regular"
		self.fontSize = 20
		self.skinItemHeight = None
		self.listHeight = None
		self.listWidth = None
		self.pbarShift = None
		self.pbarHeight = 16
		self.pbarLargeWidth = 48
		self.pbarColour = 0x206333
		self.pbarColourSeen = 0xffc71d
		self.pbarColourRec = 0xff001d
		self.partIconeShift = None
		self.spaceRight = 2
		self.spaceIconeText = 2
		self.iconsWidth = 22
		self.durationWidth = 160
		self.dateWidth = 160
		if config.usage.time.wide.value:
			self.dateWidth = int(self.dateWidth * 1.15)
		self.reloadDelayTimer = None
		self.l = eListboxPythonMultiContent()
		self.tags = set()
		self.markList = []
		self.allowCollections = allowCollections # used to disable collections when loaded by OpenWebIf
		self.root = None
		self._playInBackground = None
		self._playInForeground = None
		self._char = ''

		if root is not None:
			self.reload(root)

		self.onSelectionChanged = [ ]
		self.iconPart = []
		for part in range(5):
			self.iconPart.append(loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, "icons/part_%d_4.png" % part)))
		self.iconMovieRec = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, "icons/part_new.png"))
		self.iconMoviePlay = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, "icons/movie_play.png"))
		self.iconMoviePlayRec = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, "icons/movie_play_rec.png"))
		self.iconUnwatched = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, "icons/part_unwatched.png"))
		self.iconFolder = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, "icons/folder.png"))
		self.iconMarked = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, "icons/mark_on.png"))
		self.iconCollection = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, "icons/collection.png")) or self.iconFolder
		self.iconTrash = loadPNG(resolveFilename(SCOPE_ACTIVE_SKIN, "icons/trashcan.png"))
		self.runningTimers = {}
		self.updateRecordings()
		self.updatePlayPosCache()

	def get_playInBackground(self):
		return self._playInBackground

	def set_playInBackground(self, value):
		if self._playInBackground is not value:
			index = self.findService(self._playInBackground)
			if index is not None:
				self.invalidateItem(index)
			index = self.findService(value)
			if index is not None:
				self.invalidateItem(index)
			self._playInBackground = value

	playInBackground = property(get_playInBackground, set_playInBackground)

	def get_playInForeground(self):
		return self._playInForeground

	def set_playInForeground(self, value):
		self._playInForeground = value

	playInForeground = property(get_playInForeground, set_playInForeground)

	def updatePlayPosCache(self):
		from Screens.InfoBarGenerics import updateresumePointCache
		updateresumePointCache()

	def updateRecordings(self, timer=None):
		if timer is not None:
			if timer.justplay:
				return
		result = {}
		for timer in NavigationInstance.instance.RecordTimer.timer_list:
			if timer.isRunning() and not timer.justplay and hasattr(timer, 'Filename'):
				result[os.path.split(timer.Filename)[1]+'.ts'] = timer
		if self.runningTimers == result:
			return
		self.runningTimers = result
		if timer is not None:
			if self.reloadDelayTimer is not None:
				self.reloadDelayTimer.stop()
			self.reloadDelayTimer = eTimer()
			self.reloadDelayTimer.callback.append(self.reload)
			self.reloadDelayTimer.start(5000, 1)

	def connectSelChanged(self, fnc):
		if not fnc in self.onSelectionChanged:
			self.onSelectionChanged.append(fnc)

	def disconnectSelChanged(self, fnc):
		if fnc in self.onSelectionChanged:
			self.onSelectionChanged.remove(fnc)

	def selectionChanged(self):
		for x in self.onSelectionChanged:
			x()

	def setDescriptionState(self, val):
		self.descr_state = val

	def setSortType(self, type):
		self.sort_type = type

	def applySkin(self, desktop, parent):
		def warningWrongSkinParameter(string):
			print "[MovieList] wrong '%s' skin parameters" % string
		def font(value):
			font = parseFont(value, ((1,1),(1,1)))
			self.fontName = font.family
			self.fontSize = font.pointSize
		def itemHeight(value):
			self.skinItemHeight = parseScale(value)
		def pbarShift(value):
			self.pbarShift = parseScale(value)
		def pbarHeight(value):
			self.pbarHeight = parseScale(value)
		def pbarLargeWidth(value):
			self.pbarLargeWidth = parseScale(value)
		def pbarColour(value):
			self.pbarColour = parseColor(value).argb()
		def pbarColourSeen(value):
			self.pbarColourSeen = parseColor(value).argb()
		def pbarColourRec(value):
			self.pbarColourRec = parseColor(value).argb()
		def partIconeShift(value):
			self.partIconeShift = parseScale(value)
		def spaceIconeText(value):
			self.spaceIconeText = parseScale(value)
		def iconsWidth(value):
			self.iconsWidth = parseScale(value)
		def spaceRight(value):
			self.spaceRight = parseScale(value)
		def durationWidth(value):
			self.durationWidth = parseScale(value)
		def dateWidth(value):
			self.dateWidth = parseScale(value)
			if config.usage.time.wide.value:
				self.dateWidth = parseScale(self.dateWidth * 1.15)
		for (attrib, value) in self.skinAttributes[:]:
			try:
				locals().get(attrib)(value)
				self.skinAttributes.remove((attrib, value))
			except:
				pass
		rc = GUIComponent.applySkin(self, desktop, parent)
		self.listHeight = self.instance.size().height()
		self.listWidth = self.instance.size().width()
		self.setFontsize()
		self.setItemsPerPage()
		return rc

	def setItemsPerPage(self):
		numberOfRows = config.movielist.itemsperpage.value
		itemHeight = (self.listHeight // numberOfRows if numberOfRows else self.skinItemHeight) or 25
		self.itemHeight = itemHeight
		self.l.setItemHeight(itemHeight)
		self.instance.resize(eSize(self.listWidth, self.listHeight / itemHeight * itemHeight))

	def setFontsize(self):
		self.l.setFont(0, gFont(self.fontName, self.fontSize + config.movielist.fontsize.value))
		self.l.setFont(1, gFont(self.fontName, (self.fontSize - 3) + config.movielist.fontsize.value))

	def invalidateItem(self, index):
		data = self.list[index][3]
		if data:
			data.dirty = True
		self.l.invalidateEntry(index)

	def invalidateCurrentItem(self):
		self.invalidateItem(self.getCurrentIndex())

	def buildMovieListEntry(self, serviceref, info, begin, data):

		showPicons = "picon" in config.usage.movielist_servicename_mode.value
		switch = config.usage.show_icons_in_movielist.value
		piconWidth = config.usage.movielist_piconwidth.value if showPicons else 0
		durationWidth = self.durationWidth if config.usage.load_length_of_movies_in_moviellist.value else 0

		width = self.l.getItemSize().width()

		dateWidth = self.dateWidth
		if not config.movielist.use_fuzzy_dates.value:
			dateWidth += 30

		iconSize = self.iconsWidth
		if switch == 'p':
			iconSize = self.pbarLargeWidth
		ih = self.itemHeight
		col0iconSize = piconWidth if showPicons else iconSize

		space = self.spaceIconeText
		r = self.spaceRight
		pathName = serviceref.getPath()
		res = [ None ]

		if serviceref.flags & eServiceReference.isGroup:
			# Collections
			res.append(MultiContentEntryPixmapAlphaBlend(pos=(0, 0), size=(col0iconSize, self.itemHeight), png=self.iconCollection, flags=BT_ALIGN_CENTER))
			if self.getCurrent() in self.markList:
				res.append(MultiContentEntryPixmapAlphaBlend(pos=(0, 0), size=(col0iconSize, self.itemHeight), png=self.iconMarked))
			res.append(MultiContentEntryText(pos=(col0iconSize + space, 0), size=(width-220, self.itemHeight), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = data.txt))
			recordingCount = ngettext("%d Recording", "%d Recordings", data.collectionCount) % data.collectionCount
			res.append(MultiContentEntryText(pos=(width-220-r, 0), size=(220, self.itemHeight), font=1, flags=RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text=recordingCount))
			return res
		if serviceref.flags & eServiceReference.mustDescent:
			# Directory
			# Name is full path name
			if info is None:
				# Special case: "parent"
				txt = ".."
			else:
				p = os.path.split(pathName)
				if not p[1]:
					# if path ends in '/', p is blank.
					p = os.path.split(p[0])
				txt = p[1]
			if txt == ".Trash":
				res.append(MultiContentEntryPixmapAlphaBlend(pos=(0, 0), size=(col0iconSize, self.itemHeight), png=self.iconTrash, flags=BT_ALIGN_CENTER))
				res.append(MultiContentEntryText(pos=(col0iconSize + space, 0), size=(width-145, self.itemHeight), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = _("Deleted items")))
				res.append(MultiContentEntryText(pos=(width-145-r, 0), size=(145, self.itemHeight), font=1, flags=RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text=_("Trash can")))
				return res
			res.append(MultiContentEntryPixmapAlphaBlend(pos=(0, 0), size=(col0iconSize, self.itemHeight), png=self.iconFolder, flags=BT_ALIGN_CENTER))
			if self.getCurrent() in self.markList:
				res.append(MultiContentEntryPixmapAlphaBlend(pos=(0, 0), size=(col0iconSize, self.itemHeight), png=self.iconMarked))
			res.append(MultiContentEntryText(pos=(col0iconSize + space, 0), size=(width-145, self.itemHeight), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = txt))
			res.append(MultiContentEntryText(pos=(width-145-r, 0), size=(145, self.itemHeight), font=1, flags=RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text=_("Directory")))
			return res
		if data.dirty:
			cur_idx = self.l.getCurrentSelectionIndex()
			x = self.list[cur_idx] # x = ref,info,begin,...
			if config.usage.load_length_of_movies_in_moviellist.value:
				data.len = x[1].getLength(x[0]) #recalc the movie length...
			else:
				data.len = 0 #dont recalc movielist to speedup loading the list
			self.list[cur_idx] = (x[0], x[1], x[2], data) #update entry in list... so next time we don't need to recalc
			data.picon = None
			if showPicons:
				refs = info.getInfoString(x[0], iServiceInformation.sServiceref)
				picon = getPiconName(refs)
				if picon != "":
					data.picon = loadPNG(picon)
			data.txt = getItemDisplayName(serviceref, info)
			data.icon = None
			data.part = None
			if os.path.split(pathName)[1] in self.runningTimers:
				if switch == 'i':
					if (self.playInBackground or self.playInForeground) and serviceref == (self.playInBackground or self.playInForeground):
						data.icon = self.iconMoviePlayRec
					else:
						data.icon = self.iconMovieRec
				elif switch in ('p', 's'):
					data.part = 100
					if (self.playInBackground or self.playInForeground) and serviceref == (self.playInBackground or self.playInForeground):
						data.partcol = self.pbarColourSeen
					else:
						data.partcol = self.pbarColourRec
			elif (self.playInBackground or self.playInForeground) and serviceref == (self.playInBackground or self.playInForeground):
				data.icon = self.iconMoviePlay
			else:
				data.part = moviePlayState(pathName + '.cuts', serviceref, data.len)
				if switch == 'i':
					if data.part is not None and data.part > 0:
						data.icon = self.iconPart[data.part // 25]
					else:
						if config.usage.movielist_unseen.value:
							data.icon = self.iconUnwatched
				elif switch in ('p', 's'):
					if data.part is not None and data.part > 0:
						data.partcol = self.pbarColourSeen
					else:
						if config.usage.movielist_unseen.value:
							data.part = 100
							data.partcol = self.pbarColour

		colX = 0
		if switch == 'p':
			iconSize = self.pbarLargeWidth
		ih = self.itemHeight

		def addProgress():
			# icon/progress
			if data:
				if switch == 'i' and hasattr(data, 'icon') and data.icon is not None:
					if self.partIconeShift is None:
						res.append(MultiContentEntryPixmapAlphaBlend(pos=(colX,0), size=(iconSize,ih), png=data.icon, flags=BT_ALIGN_CENTER))
					else:
						res.append(MultiContentEntryPixmapAlphaBlend(pos=(colX,self.partIconeShift), size=(iconSize,data.icon.size().height()), png=data.icon))
				elif switch in ('p', 's'):
					if hasattr(data, 'part') and data.part > 0:
						pbarY = (self.itemHeight - self.pbarHeight) // 2 if self.pbarShift is None else self.pbarShift
						res.append(MultiContentEntryProgress(pos=(colX,pbarY), size=(iconSize, self.pbarHeight), percent=data.part, borderWidth=2, foreColor=data.partcol, foreColorSelected=None, backColor=None, backColorSelected=None))
					elif hasattr(data, 'icon') and data.icon is not None:
						if self.pbarShift is None:
							res.append(MultiContentEntryPixmapAlphaBlend(pos=(colX,0), size=(iconSize, ih), png=data.icon, flags=BT_ALIGN_CENTER))
						else:
							res.append(MultiContentEntryPixmapAlphaBlend(pos=(colX,self.pbarShift), size=(iconSize, self.pbarHeight), png=data.icon))
			return iconSize

		if piconWidth > 0:
			# Picon
			if data and data.picon is not None:
				res.append(MultiContentEntryPixmapAlphaBlend(
					pos = (colX, 0), size = (piconWidth, ih),
					png = data.picon,
					backcolor = None, backcolor_sel = None, flags = BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_CENTER | BT_VALIGN_CENTER))
			colX += piconWidth
		else:
			colX += addProgress()

		# The selection mark floats over the top of the first column
		if self.getCurrent() in self.markList:
			res.append(MultiContentEntryPixmapAlphaBlend(pos=(0, 0), size=(colX, self.itemHeight), png=self.iconMarked))
		colX += space

		# Recording name
		res.append(MultiContentEntryText(pos=(colX, 0), size=(width-iconSize-space-durationWidth-dateWidth-r-colX, ih), font = 0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = data.txt))
		colX = width-iconSize-space-durationWidth-dateWidth-r

		if piconWidth > 0:
			colX += addProgress()

		# Duration - optionally active
		if durationWidth > 0:
			if data:
				len = data.len
				if len > 0:
					len = ngettext("%d Min", "%d Mins", (len / 60)) % (len / 60)
					res.append(MultiContentEntryText(pos=(colX, 0), size=(durationWidth, ih), font=1, flags=RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text=len))

		# Date
		begin_string = ""
		if begin > 0:
			if config.movielist.use_fuzzy_dates.value:
				begin_string = ', '.join(FuzzyTime(begin, inPast = True))
			else:
				begin_string = strftime("%s, %s" % (config.usage.date.daylong.value, config.usage.time.short.value), localtime(begin))

		res.append(MultiContentEntryText(pos=(width-dateWidth-r, 0), size=(dateWidth, ih), font=1, flags=RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text=begin_string))

		return res

	def moveToFirstMovie(self):
		if self.firstFileEntry < len(self.list):
			self.instance.moveSelectionTo(self.firstFileEntry)
		else:
			# there are no movies, just directories...
			self.moveToFirst()

	def moveToParentDirectory(self):
		if self.parentDirectory < len(self.list):
			self.instance.moveSelectionTo(self.parentDirectory)
		else:
			self.moveToFirst()

	def moveToLast(self):
		if self.list:
			self.instance.moveSelectionTo(len(self.list) - 1)

	def moveToFirst(self):
		if self.list:
			self.instance.moveSelectionTo(0)

	def moveToIndex(self, index):
		self.instance.moveSelectionTo(index)

	def getCurrentIndex(self):
		return self.instance.getCurrentIndex()

	def getCurrentEvent(self):
		l = self.l.getCurrentSelection()
		return l and l[0] and l[1] and l[1].getEvent(l[0])

	def getCurrent(self):
		l = self.l.getCurrentSelection()
		return l and l[0]

	def getItem(self, index):
		if self.list:
			if len(self.list) > index:
				return self.list[index] and self.list[index][0]

	GUI_WIDGET = eListbox

	def postWidgetCreate(self, instance):
		instance.setContent(self.l)
		instance.selectionChanged.get().append(self.selectionChanged)
		self.setFontsize()

	def preWidgetRemove(self, instance):
		instance.setContent(None)
		instance.selectionChanged.get().remove(self.selectionChanged)

	def reload(self, root=None, filter_tags=None, collection=None):
		if self.reloadDelayTimer is not None:
			self.reloadDelayTimer.stop()
			self.reloadDelayTimer = None
		if root is not None:
			self.load(root, filter_tags, collection)
		else:
			self.load(self.root, filter_tags, collection)
		self.l.setBuildFunc(self.buildMovieListEntry)  # don't move that to __init__ as this will create memory leak when calling MovieList from WebIf
		self.refreshDisplay()

	def refreshDisplay(self):
		self.l.setList(self.list)

	def removeServices(self, services):
		refresh = False
		for service in services:
			refresh = self.removeService(service) or refresh
		if refresh:
			self.l.setList(self.list)

	def removeService(self, service):
		for index, item in enumerate(self.list):
			if item[0] == service:
				self.removeMark(item[0])
				del self.list[index]
				if index < self.instance.getCurrentIndex():
					self.moveUp()
				return True
			data = item[3]
			if item[0].flags & eServiceReference.isGroup and data:
				for colIemIndex, colItem in enumerate(data.collectionItems):
					if colItem[0] == service:
						del data.collectionItems[colIemIndex]
						if len(data.collectionItems) == 0:
							self.removeMark(item[0])
							del self.list[index]
						return True
		return False

	def findService(self, service):
		if service is None:
			return None
		for index, l in enumerate(self.list):
			if l[0] == service:
				return index
		return None

	def __len__(self):
		return len(self.list)

	def __getitem__(self, index):
		return self.list[index]

	def __iter__(self):
		return self.list.__iter__()

	def load(self, root, filter_tags, collectionName=None):
		# this lists our root service, then building a
		# nice list
		del self.list[:]
		del self.markList[:]
		serviceHandler = eServiceCenter.getInstance()
		numberOfDirs = 0
		collectionMode = config.movielist.enable_collections.value
		if not collectionMode or not self.allowCollections:
			collectionName = None

		reflist = root and serviceHandler.list(root)
		if reflist is None:
			print "listing of movies failed"
			return
		realtags = set()
		autotags = {}
		rootPath = os.path.normpath(root.getPath())
		split = os.path.split(rootPath)
		parent = None
		# Don't navigate above the "root"
		if len(rootPath) > 1 and (os.path.realpath(rootPath) != os.path.realpath(config.movielist.root.value)):
			parent = split[0]
			currentFolder = os.path.normpath(rootPath) + '/'
			if collectionName:
				self.list.append((eServiceReference.fromDirectory(currentFolder), None, 0, MovieListData()))
				numberOfDirs += 1
			elif parent and (parent not in defaultInhibitDirs) and not currentFolder.endswith(config.usage.default_path.value):
				# enigma wants an extra '/' appended
				if not parent.endswith('/'):
					parent += '/'
				ref = eServiceReference.fromDirectory(parent)
				self.list.append((ref, None, 0, MovieListData()))
				numberOfDirs += 1
		firstDir = numberOfDirs

		if config.usage.movielist_trashcan.value:
			here = os.path.realpath(rootPath)
			MovieList.InTrashFolder = here.startswith(getTrashFolder(here))
		else:
	 		MovieList.InTrashFolder = False
 		MovieList.UsingTrashSort = False
		if MovieList.InTrashFolder:
			if (config.usage.trashsort_deltime.value == "show record time"):
		 		MovieList.UsingTrashSort = MovieList.TRASHSORT_SHOWRECORD
			elif (config.usage.trashsort_deltime.value == "show delete time"):
		 		MovieList.UsingTrashSort = MovieList.TRASHSORT_SHOWDELETE

		while 1:
			serviceref = reflist.getNext()
			if not serviceref.valid():
				break
			if config.ParentalControl.servicepinactive.value and config.ParentalControl.storeservicepin.value != "never":
				from Components.ParentalControl import parentalControl
				if not parentalControl.sessionPinCached and parentalControl.isProtected(serviceref):
					continue
			info = serviceHandler.info(serviceref)
			if info is None:
				info = justStubInfo
			begin = info.getInfo(serviceref, iServiceInformation.sTimeCreate)
			begin2 = 0
			name = info.getName(serviceref)
			# OSX put a lot of stupid files ._* everywhere... we need to skip them
			if name[:2] == "._":
				continue
			if MovieList.UsingTrashSort:
				f_path = serviceref.getPath()
				if os.path.exists(f_path):  # Override with deltime for sorting
					if MovieList.UsingTrashSort == MovieList.TRASHSORT_SHOWRECORD:
						begin2 = begin      # Save for later re-instatement
					begin = os.stat(f_path).st_ctime

			# Filter on a specific collections. Users don't care about case of the name
			if collectionName and collectionName.lower() != name.strip().lower():
				continue

			if not collectionName and serviceref.flags & eServiceReference.mustDescent:
				if not name.endswith('.AppleDouble/') and not name.endswith('.AppleDesktop/') and not name.endswith('.AppleDB/') and not name.endswith('Network Trash Folder/') and not name.endswith('Temporary Items/'):
					self.list.append((serviceref, info, begin, MovieListData()))
					numberOfDirs += 1
				continue

			# convert space-separated list of tags into a set
			this_tags = info.getInfoString(serviceref, iServiceInformation.sTags).split(' ')
			if this_tags == ['']:
				# No tags? Auto tag!
				this_tags = name.replace(',',' ').replace('.',' ').replace('_',' ').replace(':',' ').split()
				# For auto tags, we are keeping a (tag, movies) dictionary.
				#It will be used later to check if movies have a complete sentence in common.
				for tag in this_tags:
					if tag in autotags:
						autotags[tag].append(name)
					else:
						autotags[tag] = [name]
			else:
				realtags.update(this_tags)
			# filter_tags is either None (which means no filter at all), or
			# a set. In this case, all elements of filter_tags must be present,
			# otherwise the entry will be dropped.
			if filter_tags is not None:
				this_tags_fullname = [" ".join(this_tags)]
				this_tags_fullname = set(this_tags_fullname)
				this_tags = set(this_tags)
				if not this_tags.issuperset(filter_tags) and not this_tags_fullname.issuperset(filter_tags):
					continue
			if begin2 != 0:
				self.list.append((serviceref, info, begin, MovieListData(), begin2))
			else:
				self.list.append((serviceref, info, begin, MovieListData()))

		if not collectionName and collectionMode and self.allowCollections:
			# not displaying the contents of a collection, group similar named 
			# recordings into collections ignoring case
			groupedFiles = {}
			items = []
			for item in self.list:
				if item[0].flags & eServiceReference.mustDescent:
					items.append(item)
				else:
					name = item[1].getName(item[0]).strip().lower()
					if collectionMode == 1 and name == split[1].lower():
						items.append(item)
					elif groupedFiles.get(name):
						groupedFiles[name].append(item)
					else:
						groupedFiles[name] = [item]

			for key, groupedItems in groupedFiles.items():
				if len(groupedItems) == 1:
					# insert single items as normal files
					items.append(groupedItems[0])
				elif len(groupedItems) > 1:
					# more than one item, display a collection
					firstItem = groupedItems[0]
					data = MovieListData()
					data.collectionCount = len(groupedItems)
					data.collectionItems = groupedItems
					data.txt = firstItem[1].getName(firstItem[0]).strip()
					serviceref = eServiceReference(eServiceReference.idFile, eServiceReference.isGroup, data.txt)
					items.append((serviceref, serviceref.info(), max(groupedItems, key=lambda i: i[2])[2], data))
			self.list = items

		self.firstFileEntry = numberOfDirs
		self.parentDirectory = 0

		self.list.sort(key=self.buildGroupwiseSortkey)

		# Have we had a temporary sort method override set in MovieSelectiom.py?
		# If so use it, remove it (it's a one-off) and set the current method so
		# that the "Sort by" menu can highlight it and "Sort" knows which to
		# move on from (both in Screens/MovieSelection.py).
		#
		try:
			self.current_sort = self.temp_sort
			del self.temp_sort
		except:
			self.current_sort = self.sort_type

		if MovieList.UsingTrashSort:      # Same as SORT_RECORDED, but must come first...
			self.list = sorted(self.list[:numberOfDirs], key=self.buildBeginTimeSortKey) + sorted(self.list[numberOfDirs:], key=self.buildBeginTimeSortKey)
			# Having sorted on *deletion* times, re-instate any record times for
			# *display* if that option is set.
			# self.list is a list of tuples, so we can't just assign to elements...
			#
			if config.usage.trashsort_deltime.value == "show record time":
				for i in range(len(self.list)):
					if len(self.list[i]) == 5:
						x = self.list[i]
						self.list[i] = (x[0], x[1], x[4], x[3])
		elif self.current_sort == MovieList.SORT_ALPHANUMERIC:
			self.list = sorted(self.list[:numberOfDirs], key=self.buildAlphaNumericSortKey) + sorted(self.list[numberOfDirs:], key=self.buildAlphaNumericSortKey)
		elif self.current_sort == MovieList.SORT_ALPHANUMERIC_REVERSE:
			self.list = (self.list[:firstDir] + sorted(self.list[firstDir:numberOfDirs], key=self.buildAlphaNumericSortKey, reverse = True) +
				sorted(self.list[numberOfDirs:], key=self.buildAlphaNumericSortKey, reverse = True))
		elif self.current_sort == MovieList.SORT_ALPHANUMERIC_FLAT:
			self.list.sort(key=self.buildAlphaNumericFlatSortKey)
		elif self.current_sort == MovieList.SORT_ALPHANUMERIC_FLAT_REVERSE:
			self.list = self.list[:firstDir] + sorted(self.list[firstDir:], key=self.buildAlphaNumericFlatSortKey, reverse = True)
		elif self.current_sort == MovieList.SORT_RECORDED:
			self.list = sorted(self.list[:numberOfDirs], key=self.buildBeginTimeSortKey) + sorted(self.list[numberOfDirs:], key=self.buildBeginTimeSortKey)
		elif self.current_sort == MovieList.SORT_RECORDED_REVERSE:
			self.list = self.list[:firstDir] + sorted(self.list[firstDir:numberOfDirs], key=self.buildBeginTimeSortKey, reverse = True) + sorted(self.list[numberOfDirs:], key=self.buildBeginTimeSortKey, reverse = True)
		elif self.current_sort == MovieList.SHUFFLE:
			dirlist = self.list[:numberOfDirs]
			shufflelist = self.list[numberOfDirs:]
			random.shuffle(shufflelist)
			self.list = dirlist + shufflelist
		elif self.current_sort == MovieList.SORT_ALPHA_DATE_OLDEST_FIRST:
			self.list = sorted(self.list[:numberOfDirs], key=self.buildAlphaDateSortKey) + sorted(self.list[numberOfDirs:], key=self.buildAlphaDateSortKey)
		elif self.current_sort == MovieList.SORT_ALPHAREV_DATE_NEWEST_FIRST:
			self.list = self.list[:firstDir] + sorted(self.list[firstDir:numberOfDirs], key=self.buildAlphaDateSortKey, reverse = True) + sorted(self.list[numberOfDirs:], key=self.buildAlphaDateSortKey, reverse = True)
		elif self.current_sort == MovieList.SORT_LONGEST:
			self.list = sorted(self.list[:numberOfDirs], key=self.buildAlphaNumericSortKey) + sorted(self.list[numberOfDirs:], key=self.buildLengthSortKey, reverse = True)
		elif self.current_sort == MovieList.SORT_SHORTEST:
			self.list = sorted(self.list[:numberOfDirs], key=self.buildAlphaNumericSortKey) + sorted(self.list[numberOfDirs:], key=self.buildLengthSortKey)

		for x in self.list:
			if x[1]:
				tmppath = x[1].getName(x[0])[:-1] if x[1].getName(x[0]).endswith('/') else x[1].getName(x[0])
				if tmppath.endswith('.Trash'):
					self.list.insert(0, self.list.pop(self.list.index(x)))
					break

		if self.root and numberOfDirs > 0:
			rootPath = os.path.normpath(self.root.getPath())
			if not rootPath.endswith('/'):
				rootPath += '/'
			if rootPath != parent:
				# with new sort types directories may be in between files, so scan whole
				# list for parentDirectory index. Usually it is the first one anyway
				for index, item in enumerate(self.list):
					if item[0].flags & eServiceReference.mustDescent:
						itempath = os.path.normpath(item[0].getPath())
						if not itempath.endswith('/'):
							itempath += '/'
						if itempath == rootPath:
							self.parentDirectory = index
							break
		self.root = root
		# finally, store a list of all tags which were found. these can be presented
		# to the user to filter the list
		# ML: Only use the tags that occur more than once in the list OR that were
		# really in the tag set of some file.

		# reverse the dictionary to see which unique movie each tag now references
		rautotags = {}
		for tag, movies in autotags.items():
			if (len(movies) > 1):
				movies = tuple(movies) # a tuple can be hashed, but a list not
				item = rautotags.get(movies, [])
				if not item: rautotags[movies] = item
				item.append(tag)
		self.tags = {}
		for movies, tags in rautotags.items():
			movie = movies[0]
			# format the tag lists so that they are in 'original' order
			tags.sort(key = movie.find)
			first = movie.find(tags[0])
			last = movie.find(tags[-1]) + len(tags[-1])
			match = movie
			start = 0
			end = len(movie)
			# Check if the set has a complete sentence in common, and how far
			for m in movies[1:]:
				if m[start:end] != match:
					if not m.startswith(movie[:last]):
						start = first
					if not m.endswith(movie[first:]):
						end = last
					match = movie[start:end]
					if m[start:end] != match:
						match = ''
						break
			# Adding the longest common sentence to the tag list
			if match:
				self.tags[match] = set(tags)
			else:
				match = ' '.join(tags)
				if (len(match) > 2) or (match in realtags): #Omit small words, only for auto tags
					self.tags[match] = set(tags)
		# Adding the realtags to the tag list
		for tag in realtags:
			self.tags[tag] = set([tag])

	def buildLengthSortKey(self, x):
		# x = ref,info,begin,...
		ref = x[0]
		name = x[1] and x[1].getName(ref)
		# if a collection, use the first item in the collection for the length
		if ref.flags & eServiceReference.isGroup:
			firstItem = x[3].collectionItems[0]
			if firstItem:
				ref = firstItem[0] or ref
		len = x[1] and (x[1].getLength(ref) // 60) # we only display minutes, so sort by minutes
		if ref.flags & eServiceReference.mustDescent:
			return 0, len or 0, name and name.lower() or "", -x[2]
		return 1, len or 0, name and name.lower() or "", -x[2]

	def buildAlphaNumericSortKey(self, x):
		# x = ref,info,begin,...
		ref = x[0]
		name = x[1] and x[1].getName(ref)
		if ref.flags & eServiceReference.mustDescent:
			return 0, name and name.lower() or "", -x[2]
		return 1, name and name.lower() or "", -x[2]

	# as for buildAlphaNumericSortKey, but without negating dates
	def buildAlphaDateSortKey(self, x):
		# x = ref,info,begin,...
		ref = x[0]
		name = x[1] and x[1].getName(ref)
		if ref.flags & eServiceReference.mustDescent:
			return 0, name and name.lower() or "", x[2]
		return 1, name and name.lower() or "", x[2]

	def buildAlphaNumericFlatSortKey(self, x):
		# x = ref,info,begin,...
		ref = x[0]
		name = x[1] and x[1].getName(ref)
		if name and ref.flags & eServiceReference.mustDescent:
			# only use directory basename for sorting
			p = os.path.split(name)
			if not p[1]:
				# if path ends in '/', p is blank.
				p = os.path.split(p[0])
			name = p[1]
		return 1, name and name.lower() or "", -x[2]

	def buildBeginTimeSortKey(self, x):
		ref = x[0]
		if ref.flags & eServiceReference.mustDescent and os.path.exists(ref.getPath()):
			return 0, x[1] and -os.stat(ref.getPath()).st_mtime
		return 1, -x[2]

	def buildGroupwiseSortkey(self, x):
		# Sort recordings by date, sort MP3 and stuff by name
		ref = x[0]
		if ref.type >= eServiceReference.idUser:
			return self.buildAlphaNumericSortKey(x)
		else:
			return self.buildBeginTimeSortKey(x)

	def moveTo(self, serviceref):
		index = self.findService(serviceref)
		if index is not None:
			self.instance.moveSelectionTo(index)
			return True
		return False

	def moveDown(self):
		self.instance.moveSelection(self.instance.moveDown)

	def moveUp(self):
		self.instance.moveSelection(self.instance.moveUp)

	def moveToChar(self, char, lbl=None):
		self._char = char
		self._lbl = lbl
		if lbl:
			lbl.setText(self._char)
			lbl.visible = True
		self.moveToCharTimer = eTimer()
		self.moveToCharTimer.callback.append(self._moveToChrStr)
		self.moveToCharTimer.start(1000, True) #time to wait for next key press to decide which letter to use...

	def moveToString(self, char, lbl=None):
		self._char = self._char + char.upper()
		self._lbl = lbl
		if lbl:
			lbl.setText(self._char)
			lbl.visible = True
		self.moveToCharTimer = eTimer()
		self.moveToCharTimer.callback.append(self._moveToChrStr)
		self.moveToCharTimer.start(1000, True) #time to wait for next key press to decide which letter to use...

	def _moveToChrStr(self):
		currentIndex = self.instance.getCurrentIndex()
		found = False
		if currentIndex < (len(self.list) - 1):
			itemsBelow = self.list[currentIndex + 1:]
			#first search the items below the selection
			for index, item in enumerate(itemsBelow):
				# Just ignore any "root tagged" item - for which item[1] is None
				if not item[1]:
					continue
				ref = item[0]
				itemName = getShortName(item[1].getName(ref).upper(), ref)
				if len(self._char) == 1 and itemName.startswith(self._char):
					found = True
					self.instance.moveSelectionTo(index + currentIndex + 1)
					break
				elif len(self._char) > 1 and itemName.find(self._char) >= 0:
					found = True
					self.instance.moveSelectionTo(index + currentIndex + 1)
					break
		if found == False and currentIndex > 0:
			itemsAbove = self.list[1:currentIndex] #first item (0) points parent folder - no point to include
			for index, item in enumerate(itemsAbove):
				# Just ignore any "root tagged" item - for which item[1] is None
				if not item[1]:
					continue
				ref = item[0]
				itemName = getShortName(item[1].getName(ref).upper(), ref)
				if len(self._char) == 1 and itemName.startswith(self._char):
					found = True
					self.instance.moveSelectionTo(index + 1)
					break
				elif len(self._char) > 1 and itemName.find(self._char) >= 0:
					found = True
					self.instance.moveSelectionTo(index + 1)
					break

		self._char = ''
		if self._lbl:
			self._lbl.visible = False

	def clearMarks(self):
		if self.markList:
			self.markList = []
			self.refreshDisplay()

	def removeMark(self, itemRef):
		if self.markList:
			try:
				self.markList.remove(itemRef)
			except:
				pass

	def toggleMark(self):
		item = self.l.getCurrentSelection()
		if not item:
			return
		itemRef, info = item[:2]
		# don't allow marks on the parent directory or trash can items
		if item and item[0] and item[1] and not isTrashFolder(item[0].getPath()):
			if item[0] in self.markList:
				self.markList.remove(item[0])
			else:
				self.markList.append(item[0])
			self.invalidateCurrentItem()

	def getMarked(self, excludeDirs=False):
		marked = []
		for service in self.markList[:]:
			idx = self.findService(service)
			if idx is not None:
				if not excludeDirs or not(service.flags & eServiceReference.isDirectory):
					marked.append(self.list[idx])
			else:
				self.markList.remove(service)
		return marked

	def countMarked(self):
		return len(self.markList)

def getShortName(name, serviceref):
	if serviceref.flags & eServiceReference.mustDescent: #Directory
		pathName = serviceref.getPath()
		p = os.path.split(pathName)
		if not p[1]: #if path ends in '/', p is blank.
			p = os.path.split(p[0])
		return p[1].upper()
	else:
		return name
