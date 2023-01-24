from os import lstat, scandir
from threading import Lock, Thread
from enigma import iServiceInformation, eServiceReference

from Components.Converter.Converter import Converter
from Components.Element import cached

# Handle any invalid utf8 in a description to avoid crash when
# displaying it.
#
def force_valid_utf8(strarray):
	return strarray.encode(errors='backslashreplace').decode(errors='ignore')

class MovieInfo(Converter):
	scanDirectoryLock = Lock()
	scanPath = None
	isScanning = False
	startNewScan = False

	MOVIE_SHORT_DESCRIPTION = 0  # meta description when available.. when not .eit short description
	MOVIE_META_DESCRIPTION = 1  # just meta description when available
	MOVIE_REC_SERVICE_NAME = 2  # name of recording service
	MOVIE_REC_SERVICE_REF = 3  # referance of recording service
	MOVIE_REC_FILESIZE = 4  # filesize of recording
	MOVIE_FULL_DESCRIPTION = 5  # combination of short and long description when available
	MOVIE_NAME = 6 # recording name

	KEYWORDS = {
		# Arguments...
		"FileSize": ("type", MOVIE_REC_FILESIZE),
		"FullDescription": ("type", MOVIE_FULL_DESCRIPTION),
		"MetaDescription": ("type", MOVIE_META_DESCRIPTION),
		"RecordServiceName": ("type", MOVIE_REC_SERVICE_NAME),
		"RecordServiceRef": ("type", MOVIE_REC_SERVICE_REF),
		"ShortDescription": ("type", MOVIE_SHORT_DESCRIPTION),
		"Name": ("type", MOVIE_NAME),
		# Options...
		"Separated": ("separator", "\n\n"),
		"NotSeparated": ("separator", "\n"),
		"Trimmed": ("trim", True),
		"NotTrimmed": ("trim", False)
	}

	def __init__(self, type):
		self.textEvent = None
		self.type = None
		self.separator = "\n"
		self.trim = False

		parse = ","
		type.replace(";", parse)  # Some builds use ";" as a separator, most use ",".
		args = [arg.strip() for arg in type.split(parse)]
		for arg in args:
			name, value = self.KEYWORDS.get(arg, ("Error", None))
			if name == "Error":
				print("[MovieInfo] ERROR: Unexpected / Invalid argument token '%s'!" % arg)
			else:
				setattr(self, name, value)
		if ((name == "Error") or (type is None)):
			print("[MovieInfo] Valid arguments are: ShortDescription|MetaDescription|FullDescription|RecordServiceName|RecordServiceRef|FileSize.")
			print("[MovieInfo] Valid options for descriptions are: Separated|NotSeparated|Trimmed|NotTrimmed.")
		Converter.__init__(self, type)

	def destroy(self):
		Converter.destroy(self)
		# cancel any running directory scans
		MovieInfo.startNewScan = True
		MovieInfo.scanPath = None

	def trimText(self, text):
		if self.trim:
			return str(text).strip()
		else:
			return str(text)

	def formatDescription(self, description, extended):
		description = self.trimText(description)
		extended = self.trimText(extended)
		if description[0:20] == extended[0:20]:
			return extended
		if description and extended:
			description += self.separator
		return description + extended

	def getFriendlyFilesize(self, filesize):
		if filesize is None:
			return ""
		if filesize >= 104857600000: #100000 * 1024 * 1024
			return _("%.0f GB") % (filesize / 1073741824.0)
		elif filesize >= 1073741824: #1024*1024 * 1024
			return _("%.2f GB") % (filesize / 1073741824.0)
		elif filesize >= 1048576:
			return _("%.0f MB") % (filesize / 1048576.0)
		elif filesize >= 1024:
			return _("%.0f kB") % (filesize / 1024.0)
		return _("%d B") % filesize

	@cached
	def getText(self):
		service = self.source.service
		info = self.source.info
		event = self.source.event
		if info and service:
			if self.type == self.MOVIE_SHORT_DESCRIPTION:
				if (service.flags & eServiceReference.flagDirectory) == eServiceReference.flagDirectory:
					# Short description for Directory is the full path
					return service.getPath()
				return (
					self.__getCollectionDescription(service)
					or force_valid_utf8(info.getInfoString(service, iServiceInformation.sDescription))
					or (event and self.trimText(event.getShortDescription()))
					or service.getPath()
				)
			elif self.type == self.MOVIE_META_DESCRIPTION:
				return (
					self.__getCollectionDescription(service)
					or (event and (self.trimText(event.getExtendedDescription()) or self.trimText(event.getShortDescription())))
					or force_valid_utf8(info.getInfoString(service, iServiceInformation.sDescription))
					or service.getPath()
				)
			elif self.type == self.MOVIE_FULL_DESCRIPTION:
				return (
					self.__getCollectionDescription(service)
					or (event and self.formatDescription(event.getShortDescription(), event.getExtendedDescription()))
					or force_valid_utf8(info.getInfoString(service, iServiceInformation.sDescription))
					or service.getPath()
				)
			elif self.type == self.MOVIE_NAME:
				if (service.flags & eServiceReference.flagDirectory) == eServiceReference.flagDirectory:
					# Name for directory is the full path
					return service.getPath()
				return event and event.getEventName() or info and info.getName(service)
			elif self.type == self.MOVIE_REC_SERVICE_NAME:
				rec_ref_str = info.getInfoString(service, iServiceInformation.sServiceref)
				return eServiceReference(rec_ref_str).getServiceName()
			elif self.type == self.MOVIE_REC_SERVICE_REF:
				return info.getInfoString(service, iServiceInformation.sServiceref)
			elif self.type == self.MOVIE_REC_FILESIZE:
				return self.getFileSize(service, info)
		return ""

	def __getCollectionDescription(self, service):
		if service.flags & eServiceReference.isGroup:
			items = getattr(self.source.additionalInfo, "collectionItems", None)
			if items and len(items) > 0:
				return force_valid_utf8(items[0][1].getInfoString(items[0][0], iServiceInformation.sDescription))
		return None

	def getFileSize(self, service, info):
		with MovieInfo.scanDirectoryLock:
			# signal the scanner thread to exit
			MovieInfo.startNewScan = True
			MovieInfo.scanPath = None
			if (self.source.service.flags & eServiceReference.flagDirectory) == eServiceReference.flagDirectory:
				# we might have a cached value that we can use
				fileSize = getattr(self.source.additionalInfo, "directorySize", -1)
				if fileSize != -1:
					return self.getFriendlyFilesize(fileSize)
				# tell the scanner thread to start walking the directory tree
				MovieInfo.scanPath = self.source.service.getPath()
				if not MovieInfo.isScanning:
					# if the scanner thread isn't in the scanning loop, start another thread
					MovieInfo.isScanning = True
					Thread(target=self.__directoryScanWorker).start()
				return _("Directory")
		if (service.flags & eServiceReference.isGroup) == eServiceReference.isGroup:
			fileSize = getattr(self.source.additionalInfo, "collectionSize", None)
			return self.getFriendlyFilesize(fileSize)
		filesize = info.getInfoObject(service, iServiceInformation.sFileSize)
		return "" if filesize is None else self.getFriendlyFilesize(filesize)

	def __directoryScanWorker(self):
		size = 0
		def scanDirectory(path):
			nonlocal size
			for entry in scandir(path):
				if MovieInfo.startNewScan:
					return
				if entry.is_dir():
					scanDirectory(entry.path)
				elif entry.is_file():
					stat = lstat(entry.path)
					if stat:
						size += stat.st_size

		while True:
			with MovieInfo.scanDirectoryLock:
				path = MovieInfo.scanPath
				if path is None:
					MovieInfo.isScanning = False
					break
				MovieInfo.scanPath = None
				MovieInfo.startNewScan = False
			size = 0
			scanDirectory(path)

		if not MovieInfo.startNewScan:
			# cache the value if the scan hasn't been cancelled and fire off a changed event to update any renderers
			if self.source and self.source.additionalInfo:
				self.source.additionalInfo.directorySize = size
				self.changed((self.CHANGED_ALL,))

	text = property(getText)
