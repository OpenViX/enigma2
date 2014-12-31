import os
import re
from MenuList import MenuList
from Components.Harddisk import harddiskmanager
from Tools.Directories import SCOPE_ACTIVE_SKIN, resolveFilename, fileExists, pathExists
from enigma import RT_HALIGN_LEFT, eListboxPythonMultiContent, \
	eServiceReference, eServiceCenter, gFont, getDesktop
from Tools.LoadPixmap import LoadPixmap

EXTENSIONS = {
		"m4a": "music",
		"mp2": "music",
		"mp3": "music",
		"wav": "music",
		"ogg": "music",
		"wma": "music",
		"flac": "music",
		"jpg": "picture",
		"jpeg": "picture",
		"png": "picture",
		"bmp": "picture",
		"ts": "movie",
		"avi": "movie",
		"divx": "movie",
		"m4v": "movie",
		"mpg": "movie",
		"mpeg": "movie",
		"mkv": "movie",
		"mp4": "movie",
		"mov": "movie",
		"m2ts": "movie",
		"3gp": "movie",
		"3g2": "movie",
		"asf": "movie",
		"wmv": "movie",
	}

def FileEntryComponent(name, absolute = None, isDir = False):
	screenwidth = getDesktop(0).size().width()
	if screenwidth and screenwidth == 1920:
		res = [(absolute, isDir), (eListboxPythonMultiContent.TYPE_TEXT, 90, 3, 470, 60, 1, RT_HALIGN_LEFT, name)]
	else:
		res = [(absolute, isDir), (eListboxPythonMultiContent.TYPE_TEXT, 35, 1, 470, 20, 0, RT_HALIGN_LEFT, name)]
	if isDir:
		png = LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, "extensions/directory.png"))
	else:
		extension = name.split('.')
		extension = extension[-1].lower()
		if EXTENSIONS.has_key(extension):
			png = LoadPixmap(resolveFilename(SCOPE_ACTIVE_SKIN, "extensions/" + EXTENSIONS[extension] + ".png"))
		else:
			png = None
	if png is not None:
		if screenwidth and screenwidth == 1920:
			res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, 10, 5, 50, 50, png))
		else:
			res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, 10, 2, 20, 20, png))
	return res

class FileList(MenuList):
	def __init__(self, directory, showDirectories = True, showFiles = True, showMountpoints = True, matchingPattern = None, useServiceRef = False, inhibitDirs = False, inhibitMounts = False, isTop = False, enableWrapAround = False, additionalExtensions = None):
		MenuList.__init__(self, list, enableWrapAround, eListboxPythonMultiContent)
		self.additional_extensions = additionalExtensions
		self.mountpoints = []
		self.current_directory = None
		self.current_mountpoint = None
		self.useServiceRef = useServiceRef
		self.showDirectories = showDirectories
		self.showMountpoints = showMountpoints
		self.showFiles = showFiles
		self.isTop = isTop
		# example: matching .nfi and .ts files: "^.*\.(nfi|ts)"
		if matchingPattern:
			self.matchingPattern = re.compile(matchingPattern)
		else:
			self.matchingPattern = None
		self.inhibitDirs = inhibitDirs or []
		self.inhibitMounts = inhibitMounts or []

		self.refreshMountpoints()
		self.changeDir(directory)
		self.l.setFont(0, gFont("Regular", 18))
		self.l.setFont(1, gFont("Regular", 32))
		self.l.setItemHeight(23)
		self.serviceHandler = eServiceCenter.getInstance()

	def refreshMountpoints(self):
		self.mountpoints = [os.path.join(p.mountpoint, "") for p in harddiskmanager.getMountedPartitions()]
		self.mountpoints.sort(reverse = True)

	def getMountpoint(self, file):
		file = os.path.join(os.path.realpath(file), "")
		for m in self.mountpoints:
			if file.startswith(m):
				return m
		return False

	def getMountpointLink(self, file):
		if os.path.realpath(file) == file:
			return self.getMountpoint(file)
		else:
			if file[-1] == "/":
				file = file[:-1]
			mp = self.getMountpoint(file)
			last = file
			file = os.path.dirname(file)
			while last != "/" and mp == self.getMountpoint(file):
				last = file
				file = os.path.dirname(file)
			return os.path.join(last, "")

	def getSelection(self):
		if self.l.getCurrentSelection() is None:
			return None
		return self.l.getCurrentSelection()[0]

	def getCurrentEvent(self):
		l = self.l.getCurrentSelection()
		if not l or l[0][1] == True:
			return None
		else:
			return self.serviceHandler.info(l[0][0]).getEvent(l[0][0])

	def getFileList(self):
		return self.list

	def inParentDirs(self, dir, parents):
		dir = os.path.realpath(dir)
		for p in parents:
			if dir.startswith(p):
				return True
		return False

	def changeDir(self, directory, select = None):
		self.list = []

		# if we are just entering from the list of mount points:
		if self.current_directory is None:
			if directory and self.showMountpoints:
				self.current_mountpoint = self.getMountpointLink(directory)
			else:
				self.current_mountpoint = None
		self.current_directory = directory
		directories = []
		files = []

		if directory is None and self.showMountpoints: # present available mountpoints
			for p in harddiskmanager.getMountedPartitions():
				path = os.path.join(p.mountpoint, "")
				if path not in self.inhibitMounts and not self.inParentDirs(path, self.inhibitDirs):
					self.list.append(FileEntryComponent(name = p.description, absolute = path, isDir = True))
			files = [ ]
			directories = [ ]
		elif directory is None:
			files = [ ]
			directories = [ ]
		elif self.useServiceRef:
			# we should not use the 'eServiceReference(string)' constructor, because it doesn't allow ':' in the directoryname
			root = eServiceReference(2, 0, directory)
			if self.additional_extensions:
				root.setName(self.additional_extensions)
			serviceHandler = eServiceCenter.getInstance()
			list = serviceHandler.list(root)

			while 1:
				s = list.getNext()
				if not s.valid():
					del list
					break
				if s.flags & s.mustDescent:
					directories.append(s.getPath())
				else:
					files.append(s)
			directories.sort()
			files.sort()
		else:
			if fileExists(directory):
				try:
					files = os.listdir(directory)
				except:
					files = []
				files.sort()
				tmpfiles = files[:]
				for x in tmpfiles:
					if os.path.isdir(directory + x):
						directories.append(directory + x + "/")
						files.remove(x)

		if directory is not None and self.showDirectories and not self.isTop:
			if directory == self.current_mountpoint and self.showMountpoints:
				self.list.append(FileEntryComponent(name = "<" +_("List of storage devices") + ">", absolute = None, isDir = True))
			elif (directory != "/") and not (self.inhibitMounts and self.getMountpoint(directory) in self.inhibitMounts):
				self.list.append(FileEntryComponent(name = "<" +_("Parent directory") + ">", absolute = '/'.join(directory.split('/')[:-2]) + '/', isDir = True))

		if self.showDirectories:
			for x in directories:
				if not (self.inhibitMounts and self.getMountpoint(x) in self.inhibitMounts) and not self.inParentDirs(x, self.inhibitDirs):
					name = x.split('/')[-2]
					self.list.append(FileEntryComponent(name = name, absolute = x, isDir = True))

		if self.showFiles:
			for x in files:
				if self.useServiceRef:
					path = x.getPath()
					name = path.split('/')[-1]
				else:
					path = directory + x
					name = x

				if (self.matchingPattern is None) or self.matchingPattern.search(path):
					self.list.append(FileEntryComponent(name = name, absolute = x , isDir = False))

		if self.showMountpoints and len(self.list) == 0:
			self.list.append(FileEntryComponent(name = _("nothing connected"), absolute = None, isDir = False))

		self.l.setList(self.list)

		if select is not None:
			i = 0
			self.moveToIndex(0)
			for x in self.list:
				p = x[0][0]

				if isinstance(p, eServiceReference):
					p = p.getPath()

				if p == select:
					self.moveToIndex(i)
				i += 1

	def getCurrentDirectory(self):
		return self.current_directory

	def canDescent(self):
		if self.getSelection() is None:
			return False
		return self.getSelection()[1]

	def descent(self):
		if self.getSelection() is None:
			return
		self.changeDir(self.getSelection()[0], select = self.current_directory)

	def getFilename(self):
		if self.getSelection() is None:
			return None
		x = self.getSelection()[0]
		if isinstance(x, eServiceReference):
			x = x.getPath()
		return x

	def getServiceRef(self):
		if self.getSelection() is None:
			return None
		x = self.getSelection()[0]
		if isinstance(x, eServiceReference):
			return x
		return None

	def execBegin(self):
		harddiskmanager.on_partition_list_change.append(self.partitionListChanged)

	def execEnd(self):
		harddiskmanager.on_partition_list_change.remove(self.partitionListChanged)

	def refresh(self):
		self.changeDir(self.current_directory, self.getFilename())

	def partitionListChanged(self, action, device):
		self.refreshMountpoints()
		if self.current_directory is None:
			self.refresh()


def MultiFileSelectEntryComponent(name, absolute = None, isDir = False, selected = False):
	screenwidth = getDesktop(0).size().width()
	if screenwidth and screenwidth == 1920:
		res = [(absolute, isDir, selected, name), (eListboxPythonMultiContent.TYPE_TEXT, 150, 3, 470, 60, 1, RT_HALIGN_LEFT, name)]
	else:
		res = [(absolute, isDir, selected, name), (eListboxPythonMultiContent.TYPE_TEXT, 55, 1, 470, 20, 0, RT_HALIGN_LEFT, name)]
	if isDir:
		png = LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, "extensions/directory.png"))
	else:
		extension = name.split('.')
		extension = extension[-1].lower()
		if EXTENSIONS.has_key(extension):
			png = LoadPixmap(resolveFilename(SCOPE_ACTIVE_SKIN, "extensions/" + EXTENSIONS[extension] + ".png"))
		else:
			png = None
	if png is not None:
		if screenwidth and screenwidth == 1920:
			res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, 80, 5, 50, 50, png))
		else:
			res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, 30, 2, 20, 20, png))
	if not name.startswith('<'):
		if selected:
			icon = LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, "icons/lock_on.png"))
		else:
			icon = LoadPixmap(cached=True, path=resolveFilename(SCOPE_ACTIVE_SKIN, "icons/lock_off.png"))
		if screenwidth and screenwidth == 1920:
			res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, 10, 5, 50, 50, icon))
		else:
			res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, 2, 0, 25, 25, icon))
	return res


class MultiFileSelectList(FileList):
	def __init__(self, preselectedFiles, directory, showMountpoints = False, matchingPattern = None, showDirectories = True, showFiles = True,  useServiceRef = False, inhibitDirs = False, inhibitMounts = False, isTop = False, enableWrapAround = False, additionalExtensions = None):
		if preselectedFiles is None:
			self.selectedFiles = []
		else:
				self.selectedFiles = preselectedFiles
		FileList.__init__(self, directory, showMountpoints = showMountpoints, matchingPattern = matchingPattern, showDirectories = showDirectories, showFiles = showFiles,  useServiceRef = useServiceRef, inhibitDirs = inhibitDirs, inhibitMounts = inhibitMounts, isTop = isTop, enableWrapAround = enableWrapAround, additionalExtensions = additionalExtensions)
		self.changeDir(directory)
		self.l.setItemHeight(25)
		self.l.setFont(0, gFont("Regular", 20))
		self.l.setFont(1, gFont("Regular", 32))
		self.onSelectionChanged = [ ]

	def selectionChanged(self):
		for f in self.onSelectionChanged:
			f()

	def changeSelectionState(self):
		if len(self.list):
			idx = self.l.getCurrentSelectionIndex()
			newList = self.list[:]
			x = self.list[idx]
			if not x[0][3].startswith('<'):
				if x[0][1] is True:
					realPathname = x[0][0]
				else:
					realPathname = self.current_directory + x[0][0]
				if x[0][2]:
					SelectState = False
					try:
						self.selectedFiles.remove(realPathname)
					except:
						try:
							self.selectedFiles.remove(os.path.normpath(realPathname))
						except:
							print "Couldn't remove:", realPathname
				else:
					SelectState = True
					if (realPathname not in self.selectedFiles) and (os.path.normpath(realPathname) not in self.selectedFiles):
						self.selectedFiles.append(realPathname)
				newList[idx] = MultiFileSelectEntryComponent(name = x[0][3], absolute = x[0][0], isDir = x[0][1], selected = SelectState)
			self.list = newList
			self.l.setList(self.list)

	def getSelectedList(self):
		selectedFilesExist = []
		for x in self.selectedFiles:
			if pathExists(x):
				selectedFilesExist.append(x)
		return selectedFilesExist

	def changeDir(self, directory, select = None):
		self.list = []

		# if we are just entering from the list of mount points:
		if self.current_directory is None:
			if directory and self.showMountpoints:
				self.current_mountpoint = self.getMountpointLink(directory)
			else:
				self.current_mountpoint = None
		self.current_directory = directory
		directories = []
		files = []

		if directory is None and self.showMountpoints: # present available mountpoints
			for p in harddiskmanager.getMountedPartitions():
				path = os.path.join(p.mountpoint, "")
				if path not in self.inhibitMounts and not self.inParentDirs(path, self.inhibitDirs):
					self.list.append(MultiFileSelectEntryComponent(name = p.description, absolute = path, isDir = True))
			files = [ ]
			directories = [ ]
		elif directory is None:
			files = [ ]
			directories = [ ]
		elif self.useServiceRef:
			root = eServiceReference("2:0:1:0:0:0:0:0:0:0:" + directory)
			if self.additional_extensions:
				root.setName(self.additional_extensions)
			serviceHandler = eServiceCenter.getInstance()
			list = serviceHandler.list(root)

			while 1:
				s = list.getNext()
				if not s.valid():
					del list
					break
				if s.flags & s.mustDescent:
					directories.append(s.getPath())
				else:
					files.append(s)
			directories.sort()
			files.sort()
		else:
			if fileExists(directory):
				try:
					files = os.listdir(directory)
				except:
					files = []
				files.sort()
				tmpfiles = files[:]
				for x in tmpfiles:
					if os.path.isdir(directory + x):
						directories.append(directory + x + "/")
						files.remove(x)

		if directory is not None and self.showDirectories and not self.isTop:
			if directory == self.current_mountpoint and self.showMountpoints:
				self.list.append(MultiFileSelectEntryComponent(name = "<" +_("List of storage devices") + ">", absolute = None, isDir = True))
			elif (directory != "/") and not (self.inhibitMounts and self.getMountpoint(directory) in self.inhibitMounts):
				self.list.append(MultiFileSelectEntryComponent(name = "<" +_("Parent directory") + ">", absolute = '/'.join(directory.split('/')[:-2]) + '/', isDir = True))

		if self.showDirectories:
			for x in directories:
				if not (self.inhibitMounts and self.getMountpoint(x) in self.inhibitMounts) and not self.inParentDirs(x, self.inhibitDirs):
					name = x.split('/')[-2]
					alreadySelected = (x in self.selectedFiles) or (os.path.normpath(x) in self.selectedFiles)
					self.list.append(MultiFileSelectEntryComponent(name = name, absolute = x, isDir = True, selected = alreadySelected))

		if self.showFiles:
			for x in files:
				if self.useServiceRef:
					path = x.getPath()
					name = path.split('/')[-1]
				else:
					path = directory + x
					name = x
				if (self.matchingPattern is None) or self.matchingPattern.search(path):
					alreadySelected = False
					for entry in self.selectedFiles:
						if os.path.basename(entry) == x:
							alreadySelected = True
					self.list.append(MultiFileSelectEntryComponent(name = name, absolute = x , isDir = False, selected = alreadySelected))

		self.l.setList(self.list)

		if select is not None:
			i = 0
			self.moveToIndex(0)
			for x in self.list:
				p = x[0][0]

				if isinstance(p, eServiceReference):
					p = p.getPath()

				if p == select:
					self.moveToIndex(i)
				i += 1

