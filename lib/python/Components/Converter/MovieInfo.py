from os import lstat, scandir
from threading import Lock, Thread
from enigma import iServiceInformation, eServiceReference

from Components.Converter.Converter import Converter
from Components.Element import cached
from Components.Harddisk import bytesToHumanReadable
from time import localtime, strftime

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
	MOVIE_NAME = 6  # recording name
	FORMAT_STRING = 7  # it is formatted string based on parameter and with defined separator

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

	# Map each type to the name of the method that produces its text. They all take (service, info, event).
	HANDLERS = {
		MOVIE_SHORT_DESCRIPTION: "textShortDescription",
		MOVIE_META_DESCRIPTION: "textMetaDescription",
		MOVIE_REC_SERVICE_NAME: "textRecServiceName",
		MOVIE_REC_SERVICE_REF: "textRecServiceRef",
		MOVIE_REC_FILESIZE: "textRecFileSize",
		MOVIE_FULL_DESCRIPTION: "textFullDescription",
		MOVIE_NAME: "textName",
		FORMAT_STRING: "textFormatString"
	}

	# The tokens a format string understands. Anything else in the list is ignored.
	FORMAT_TOKENS = ("TIMECREATED", "DURATION", "FILESIZE")

	def __init__(self, type):
		Converter.__init__(self, type)
		self.textEvent = None
		self.type = None
		self.separator = "\n"
		self.trim = False

		parse = ","
		args = [(arg.strip() if i or arg.strip() in self.KEYWORDS else arg) for i, arg in enumerate(type.split(parse))]

		self.parts = args
		if len(self.parts) > 1 and self.parts[0] not in self.KEYWORDS:
			self.type = self.FORMAT_STRING
			self.separator = self.parts[0]

		else:
			for arg in args:
				name, value = self.KEYWORDS.get(arg, ("Error", None))
				if name == "Error":
					print("[MovieInfo] ERROR: Unexpected / Invalid argument token '%s'!" % arg)
				else:
					setattr(self, name, value)
			if ((name == "Error") or (type is None)):
				print("[MovieInfo] Valid arguments are: ShortDescription|MetaDescription|FullDescription|RecordServiceName|RecordServiceRef|FileSize.")
				print("[MovieInfo] Valid options for descriptions are: Separated|NotSeparated|Trimmed|NotTrimmed.")

		# Resolve everything that depends on the type and options once; getText never has to work it out again.
		self.trimText = self.trimStrip if self.trim else str
		self.formatTokens = tuple(token for token in (part.upper() for part in self.parts[1:]) if token in self.FORMAT_TOKENS)
		self.formatNeeds = frozenset(self.formatTokens)
		self.handler = getattr(self, self.HANDLERS.get(self.type, "textEmpty"))

	def destroy(self):
		Converter.destroy(self)
		# cancel any running directory scans
		MovieInfo.startNewScan = True
		MovieInfo.scanPath = None

	def trimStrip(self, text):
		return str(text).strip()

	def formatDescription(self, description, extended):
		description = self.trimText(description)
		extended = self.trimText(extended)
		if description[0:20] == extended[0:20]:
			return extended
		if description and extended:
			description += self.separator
		return description + extended

	def getFriendlyFilesize(self, filesize):
		if filesize in (None, 0):  # filesize for unread collections is 0
			return ""
		return bytesToHumanReadable(filesize)

	def isDirectory(self, service):
		return (service.flags & eServiceReference.flagDirectory) == eServiceReference.flagDirectory

	@cached
	def getText(self):
		service = self.source.service
		info = self.source.info
		event = self.source.event
		if info and service:
			return self.handler(service, info, event)
		return ""

	# ---- Text ----

	def textEmpty(self, service, info, event):
		return ""

	def textShortDescription(self, service, info, event):
		if self.isDirectory(service):
			# Short description for Directory is the full path
			return service.getPath()
		return (
			self.__getCollectionDescription(service)
			or force_valid_utf8(info.getInfoString(service, iServiceInformation.sDescription))
			or (event and self.trimText(event.getShortDescription()))
			or service.getPath()
		)

	def textMetaDescription(self, service, info, event):
		return (
			self.__getCollectionDescription(service)
			or (event and (self.trimText(event.getExtendedDescription()) or self.trimText(event.getShortDescription())))
			or force_valid_utf8(info.getInfoString(service, iServiceInformation.sDescription))
			or service.getPath()
		)

	def textFullDescription(self, service, info, event):
		return (
			self.__getCollectionDescription(service)
			or (event and self.formatDescription(event.getShortDescription(), event.getExtendedDescription()))
			or force_valid_utf8(info.getInfoString(service, iServiceInformation.sDescription))
			or service.getPath()
		)

	def textName(self, service, info, event):
		if self.isDirectory(service):
			# Name for directory is the full path
			return service.getPath()
		return event and event.getEventName() or info and info.getName(service)

	def textRecServiceName(self, service, info, event):
		rec_ref_str = info.getInfoString(service, iServiceInformation.sServiceref)
		return eServiceReference(rec_ref_str).getServiceName()

	def textRecServiceRef(self, service, info, event):
		return info.getInfoString(service, iServiceInformation.sServiceref)

	def textRecFileSize(self, service, info, event):
		return self.getFileSize(service, info)

	def textFormatString(self, service, info, event):
		# Only work out the values the format string asks for.
		needs = self.formatNeeds
		values = {}
		if "TIMECREATED" in needs:
			timeCreate = localtime(info.getInfo(service, iServiceInformation.sTimeCreate))
			values["TIMECREATED"] = strftime("%A %d %b %Y", timeCreate) if timeCreate and timeCreate.tm_year > 1970 else None
		if "DURATION" in needs:
			duration = info.getLength(service)
			values["DURATION"] = "%d min" % (duration / 60) if duration and duration > 0 else None
		if "FILESIZE" in needs:
			filesize = info.getInfoObject(service, iServiceInformation.sFileSize)
			values["FILESIZE"] = self.getFriendlyFilesize(filesize) if filesize else None
		res_str = ""
		for token in self.formatTokens:
			if values[token] is not None:
				res_str = self.appendToStringWithSeparator(res_str, values[token])
		return res_str

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
		failed = False

		def scanDirectory(path):
			nonlocal size, failed
			try:
				entries = scandir(path)
			except OSError:
				failed = True  # unreadable or vanished directory, the total is incomplete
				return
			for entry in entries:
				if MovieInfo.startNewScan:
					return
				try:
					if entry.is_dir():
						scanDirectory(entry.path)
					elif entry.is_file():
						stat = lstat(entry.path)
						if stat:
							size += stat.st_size
				except OSError:
					failed = True  # file vanished while scanning

		try:
			while True:
				with MovieInfo.scanDirectoryLock:
					path = MovieInfo.scanPath
					if path is None:
						MovieInfo.isScanning = False
						break
					MovieInfo.scanPath = None
					MovieInfo.startNewScan = False
				size = 0
				failed = False
				scanDirectory(path)
		except BaseException:
			# whatever went wrong, don't leave the flag set or no scan can ever start again
			with MovieInfo.scanDirectoryLock:
				MovieInfo.isScanning = False
			raise

		if not MovieInfo.startNewScan and not failed:
			# cache the value if the scan hasn't been cancelled or hit an error and fire off a changed event to update any renderers
			if self.source and self.source.additionalInfo:
				self.source.additionalInfo.directorySize = size
				self.changed((self.CHANGED_ALL,))

	text = property(getText)
