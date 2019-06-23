# -*- coding: utf-8 -*-
import os
import traceback

from enigma import eEnv, getDesktop
from re import compile

pathExists = os.path.exists
isMount = os.path.ismount  # Only used in OpenATV /lib/python/Plugins/SystemPlugins/NFIFlash/downloader.py.

screenResolution = getDesktop(0).size().height()
lcdResolution = getDesktop(1).size().height()

SCOPE_TRANSPONDERDATA = 0
SCOPE_SYSETC = 1
SCOPE_FONTS = 2
SCOPE_SKIN = 3
SCOPE_SKIN_IMAGE = 4  # DEBUG: How is this different from SCOPE_SKIN?
SCOPE_USERETC = 5  # DEBUG: Not used in Enigma2.
SCOPE_CONFIG = 6
SCOPE_LANGUAGE = 7
SCOPE_HDD = 8
SCOPE_PLUGINS = 9
SCOPE_MEDIA = 10
SCOPE_PLAYLIST = 11
SCOPE_CURRENT_SKIN = 12

SCOPE_METADIR = 16
SCOPE_CURRENT_PLUGIN = 17
SCOPE_TIMESHIFT = 18
SCOPE_ACTIVE_SKIN = 19
SCOPE_LCDSKIN = 20
SCOPE_ACTIVE_LCDSKIN = 21
SCOPE_AUTORECORD = 22
SCOPE_DEFAULTDIR = 23
SCOPE_DEFAULTPARTITION = 24
SCOPE_DEFAULTPARTITIONMOUNTDIR = 25

SCOPE_CURRENT_LCDSKIN = 30

scopeNames = {
	SCOPE_TRANSPONDERDATA: "SCOPE_TRANSPONDERDATA",
	SCOPE_SYSETC: "SCOPE_SYSETC",
	SCOPE_FONTS: "SCOPE_FONTS",
	SCOPE_SKIN: "SCOPE_SKIN",
	SCOPE_SKIN_IMAGE: "SCOPE_SKIN_IMAGE",
	SCOPE_USERETC: "SCOPE_USERETC",
	SCOPE_CONFIG: "SCOPE_CONFIG",
	SCOPE_LANGUAGE: "SCOPE_LANGUAGE",
	SCOPE_HDD: "SCOPE_HDD",
	SCOPE_PLUGINS: "SCOPE_PLUGINS",
	SCOPE_MEDIA: "SCOPE_MEDIA",
	SCOPE_PLAYLIST: "SCOPE_PLAYLIST",
	SCOPE_CURRENT_SKIN: "SCOPE_CURRENT_SKIN",
	SCOPE_METADIR: "SCOPE_METADIR",
	SCOPE_CURRENT_PLUGIN: "SCOPE_CURRENT_PLUGIN",
	SCOPE_TIMESHIFT: "SCOPE_TIMESHIFT",
	SCOPE_ACTIVE_SKIN: "SCOPE_ACTIVE_SKIN",
	SCOPE_LCDSKIN: "SCOPE_LCDSKIN",
	SCOPE_ACTIVE_LCDSKIN: "SCOPE_ACTIVE_LCDSKIN",
	SCOPE_AUTORECORD: "SCOPE_AUTORECORD",
	SCOPE_DEFAULTDIR: "SCOPE_DEFAULTDIR",
	SCOPE_DEFAULTPARTITION: "SCOPE_DEFAULTPARTITION",
	SCOPE_DEFAULTPARTITIONMOUNTDIR: "SCOPE_DEFAULTPARTITIONMOUNTDIR",
	SCOPE_CURRENT_LCDSKIN: "SCOPE_CURRENT_LCDSKIN"
}

PATH_CREATE = 0
PATH_DONTCREATE = 1

defaultPaths = {
	SCOPE_TRANSPONDERDATA: (eEnv.resolve("${sysconfdir}/"), PATH_DONTCREATE),
	SCOPE_SYSETC: (eEnv.resolve("${sysconfdir}/"), PATH_DONTCREATE),
	SCOPE_FONTS: (eEnv.resolve("${datadir}/fonts/"), PATH_DONTCREATE),
	SCOPE_CONFIG: (eEnv.resolve("${sysconfdir}/enigma2/"), PATH_CREATE),
	SCOPE_PLUGINS: (eEnv.resolve("${libdir}/enigma2/python/Plugins/"), PATH_CREATE),
	SCOPE_LANGUAGE: (eEnv.resolve("${datadir}/enigma2/po/"), PATH_DONTCREATE),
	SCOPE_SKIN: (eEnv.resolve("${datadir}/enigma2/"), PATH_DONTCREATE),
	SCOPE_LCDSKIN: (eEnv.resolve("${datadir}/enigma2/display/"), PATH_DONTCREATE),
	SCOPE_SKIN_IMAGE: (eEnv.resolve("${datadir}/enigma2/"), PATH_DONTCREATE),
	SCOPE_HDD: ("/media/hdd/movie/", PATH_DONTCREATE),
	SCOPE_TIMESHIFT: ("/media/hdd/timeshift/", PATH_DONTCREATE),
	SCOPE_AUTORECORD: ("/media/hdd/movie/", PATH_DONTCREATE),
	SCOPE_MEDIA: ("/media/", PATH_DONTCREATE),
	SCOPE_PLAYLIST: (eEnv.resolve("${sysconfdir}/enigma2/playlist/"), PATH_CREATE),
	SCOPE_USERETC: ("", PATH_DONTCREATE),  # User home directory
	SCOPE_DEFAULTDIR: (eEnv.resolve("${datadir}/enigma2/defaults/"), PATH_CREATE),
	SCOPE_DEFAULTPARTITION: ("/dev/mtdblock6", PATH_DONTCREATE),
	SCOPE_DEFAULTPARTITIONMOUNTDIR: (eEnv.resolve("${datadir}/enigma2/dealer"), PATH_CREATE),
	SCOPE_METADIR: (eEnv.resolve("${datadir}/meta"), PATH_CREATE)
}

# FILE_COPY = 0  # Copy files from fallback dir to the basedir.
# FILE_MOVE = 1  # Move files.
# PATH_COPY = 2  # Copy the complete fallback dir to the basedir.
# PATH_MOVE = 3  # Move the fallback dir to the basedir (can be used for changes in paths).

# fallbackPaths = {
# 	SCOPE_CONFIG: [("/home/root/", FILE_MOVE), (eEnv.resolve("${datadir}/enigma2/defaults/"), FILE_COPY)],
# 	SCOPE_HDD: [("/media/hdd/movies", PATH_MOVE)],  # OpenATV uses "movie"!
# 	SCOPE_AUTORECORD: [("/media/hdd/movie", PATH_MOVE)],
# 	SCOPE_TIMESHIFT: [("/media/hdd/timeshift", PATH_MOVE)]
# }

def resolveFilename(scope, base="", path_prefix=None):
	# You can only use the ~/ if we have a prefix directory.
	if base.startswith("~/"):
		assert path_prefix is not None  # Assert only works in debug mode!
		if path_prefix:
			base = os.path.join(path_prefix, base[2:])
		else:
			print "[Directories] Warning: resolveFilename called with base starting with '~/' but 'path_prefix' is None!"
	# Don't further resolve absolute paths.
	if base.startswith("/"):
		print "[Directories] DEBUG: resolveFilename (Absolute path) scope=%s, base='%s', path_prefix='%s'" % (scopeNames.get(scope), base, path_prefix)
		return base
	# Ensure that the defaultPaths directories that should exist do exist.
	path, flag = defaultPaths.get(scope, ("/", PATH_DONTCREATE))
	if flag == PATH_CREATE and not pathExists(path):
		try:
			os.makedirs(path)
		except OSError, e:
			print "[Directories] Error %d: Couldn't create directory '%s' (%s)" % (e.errno, path, os.strerror(e.error))
			return None
	# Remove any suffix data and restore it at the end.
	suffix = None
	data = base.split(":", 1)
	if len(data) > 1:
		base = data[0]
		suffix = data[1]
	path = base
	# If base is "" then set path to the scope.  Otherwise use the scope to resolve the base filename.
	if base is "":
		path, flags = defaultPaths.get(scope, ("/", PATH_DONTCREATE))
		path = os.path.normpath(path)
	elif scope in (SCOPE_CURRENT_SKIN, SCOPE_ACTIVE_SKIN):
		from Components.config import config
		pos = config.skin.primary_skin.value.rfind("/")
		if pos == -1:
			skin = ""
		else:
			skin = config.skin.primary_skin.value[:pos + 1]
		resolveList = [
			os.path.join(defaultPaths[SCOPE_CONFIG][0], skin),
			defaultPaths[SCOPE_CONFIG][0],  # Deprecated top level of SCOPE_CONFIG directory.
			os.path.join(defaultPaths[SCOPE_SKIN][0], skin),
			defaultPaths[SCOPE_SKIN][0],  # Deprecated top level of SCOPE_SKIN directory.
			os.path.join(defaultPaths[SCOPE_SKIN][0], "skin_%d" % screenResolution),
			os.path.join(defaultPaths[SCOPE_SKIN][0], "skin_default")
		]
		for item in resolveList:
			file = os.path.normpath(os.path.join(item, base))
			if pathExists(file):
				path = file
				break
	elif scope in (SCOPE_CURRENT_LCDSKIN, SCOPE_ACTIVE_LCDSKIN):
		from Components.config import config
		pos = config.skin.display_skin.value.rfind("/")
		if pos == -1:
			skin = ""
		else:
			skin = config.skin.display_skin.value[:pos + 1]
		resolveList = [
			os.path.join(defaultPaths[SCOPE_CONFIG][0], "display", skin),
			defaultPaths[SCOPE_CONFIG][0],  # Deprecated top level of SCOPE_CONFIG directory.
			os.path.join(defaultPaths[SCOPE_LCDSKIN][0], skin),
			defaultPaths[SCOPE_LCDSKIN][0],  # Deprecated top level of SCOPE_LCDSKIN directory.
			os.path.join(defaultPaths[SCOPE_LCDSKIN][0], "skin_%s" % lcdResolution),
			os.path.join(defaultPaths[SCOPE_LCDSKIN][0], "skin_default")
		]
		for item in resolveList:
			file = os.path.normpath(os.path.join(item, base))
			if pathExists(file):
				path = file
				break
	elif scope == SCOPE_FONTS:
		from Components.config import config
		pos = config.skin.primary_skin.value.rfind("/")
		if pos == -1:
			skin = ""
		else:
			skin = config.skin.primary_skin.value[:pos + 1]
		pos = config.skin.display_skin.value.rfind("/")
		if pos == -1:
			display = ""
		else:
			display = config.skin.display_skin.value[:pos + 1]
		resolveList = [
			os.path.join(defaultPaths[SCOPE_CONFIG][0], "fonts"),
			os.path.join(defaultPaths[SCOPE_CONFIG][0], skin),
			os.path.join(defaultPaths[SCOPE_CONFIG][0], display),
			os.path.join(defaultPaths[SCOPE_SKIN][0], skin),
			os.path.join(defaultPaths[SCOPE_SKIN][0], "skin_default"),
			os.path.join(defaultPaths[SCOPE_LCDSKIN][0], display),
			os.path.join(defaultPaths[SCOPE_LCDSKIN][0], "skin_default"),
			defaultPaths[SCOPE_FONTS][0]
		]
		for item in resolveList:
			file = os.path.normpath(os.path.join(item, base))
			if pathExists(file):
				path = file
				break
	elif scope == SCOPE_CURRENT_PLUGIN:
		resolveList = [defaultPaths[SCOPE_PLUGINS][0]]
		file = os.path.normpath(os.path.join(defaultPaths[SCOPE_PLUGINS][0], base))
		if pathExists(file):
			path = file
	else:
		path, flags = defaultPaths.get(scope, ("/", PATH_DONTCREATE))
		resolveList = [path]
		path = os.path.normpath(os.path.join(path, base))

	# fallbackPath = fallbackPaths.get(scope)
	#
	# if fallbackPath and not fileExists(path + base):
	# 	for x in fallbackPath:
	# 		try:
	# 			if x[1] == FILE_COPY:
	# 				if fileExists(x[0] + base):
	# 					try:
	# 						os.link(x[0] + base, path + base)
	# 					except:
	# 						os.system("cp " + x[0] + base + " " + path + base)
	# 					break
	# 			elif x[1] == FILE_MOVE:
	# 				if fileExists(x[0] + base):
	# 					try:
	# 						os.rename(x[0] + base, path + base)
	# 					except:
	# 						os.system("mv " + x[0] + base + " " + path + base)
	# 					break
	# 			elif x[1] == PATH_COPY:
	# 				if pathExists(x[0]):
	# 					if not pathExists(defaultPaths[scope][0]):
	# 						os.mkdir(path)
	# 					os.system("cp -a " + x[0] + "* " + path)
	# 					break
	# 			elif x[1] == PATH_MOVE:
	# 				if pathExists(x[0]):
	# 					os.rename(x[0], path + base)
	# 					break
	# 		except Exception, e:
	# 			print "[D] Failed to recover %s:" % (path+base), e

	# If the path is a directory then ensure that it ends with a "/".
	if os.path.isdir(path) and not path.endswith("/"):
		path += "/"
	# If a suffix was supplier restore it.
	if suffix is not None:
		path = "%s:%s" % (path, suffix)
	# Log a warning if resolveFilename can't resolve a path.
	if not path.startswith("/"):
		if path_prefix is None:
			prefix = ""
		else:
			prefix = " (path_prefix='%s')" % path_prefix
		print "[Directories] Warning: resolveFilename could not resolve '%s' for scope '%s'%s" % (path, scopeNames.get(scope), prefix)
		print "[Directories]          Searched in:", resolveList
		traceback.print_stack()
	print "[Directories] DEBUG: resolveFilename scope=%s, base='%s', path_prefix='%s', path='%s'" % (scopeNames.get(scope), base, path_prefix, path)
	return path

def bestRecordingLocation(candidates):
	path = ""
	biggest = 0
	for candidate in candidates:
		try:
			# Must have some free space (i.e. not read-only).
			stat = os.statvfs(candidate[1])
			if stat.f_bavail:
				# Free space counts double.
				size = (stat.f_blocks + stat.f_bavail) * stat.f_bsize
				if size > biggest:
					biggest = size
					path = candidate[1]
		except Exception, e:
			print "[Directories] Error %d: Couldn't get free space for '%s' (%s)" % (e.errno, candidate[1], os.strerror(e.error))
	return path

def defaultRecordingLocation(candidate=None):
	if candidate and pathExists(candidate):
		return candidate
	# First, try whatever /hdd points to, or /media/hdd.
	try:
		path = os.readlink("/hdd")
	except OSError:
		path = "/media/hdd"
	if not pathExists(path):
		path = ""
		# Find the largest local disk.
		from Components import Harddisk
		mounts = [m for m in Harddisk.getProcMounts() if m[1].startswith("/media/")]
		# Search local devices first, use the larger one
		path = bestRecordingLocation([m for m in mounts if m[0].startswith("/dev/")])
		# If we haven't found a viable candidate yet, try remote mounts.
		if not path:
			path = bestRecordingLocation(mounts)
	if path:
		# If there's a movie subdir, we'd probably want to use that.
		movie = os.path.join(path, "movie")
		if os.path.isdir(movie):
			path = movie
		if not path.endswith("/"):
			path += "/"  # Bad habits die hard, old code relies on this.
	return path

def createDir(path, makeParents=False):
	try:
		if makeParents:
			os.makedirs(path)
		else:
			os.mkdir(path)
		return 1
	except OSError:
		return 0

def removeDir(path):
	try:
		os.rmdir(path)
		return 1
	except OSError:
		return 0

def fileExists(f, mode="r"):
	if mode == "r":
		acc_mode = os.R_OK
	elif mode == "w":
		acc_mode = os.W_OK
	else:
		acc_mode = os.F_OK
	return os.access(f, acc_mode)

def fileCheck(f, mode="r"):
	return fileExists(f, mode) and f

def fileHas(f, content, mode="r"):
	result = False
	if fileExists(f, mode):
		file = open(f, mode)
		text = file.read()
		file.close()
		if content in text:
			result = True
	return result

def getRecordingFilename(basename, dirname=None):
	# Filter out non-allowed characters.
	non_allowed_characters = "/.\\:*?<>|\""
	basename = basename.replace("\xc2\x86", "").replace("\xc2\x87", "")
	filename = ""
	for c in basename:
		if c in non_allowed_characters or ord(c) < 32:
			c = "_"
		filename += c
	# Max filename length for ext4 is 255 (minus 8 characters for .ts.meta)
	# but must not truncate in the middle of a multi-byte utf8 character!
	# So convert the truncation to unicode and back, ignoring errors, the
	# result will be valid utf8 and so xml parsing will be OK.
	filename = unicode(filename[:247], "utf8", "ignore").encode("utf8", "ignore")
	if dirname is not None:
		if not dirname.startswith("/"):
			dirname = os.path.join(defaultRecordingLocation(), dirname)
	else:
		dirname = defaultRecordingLocation()
	filename = os.path.join(dirname, filename)
	path = filename
	i = 1
	while True:
		if not os.path.isfile(path + ".ts"):
			return path
		path += "_%03d" % i
		i += 1

# This is clearly a hack:
#
def InitFallbackFiles():
	resolveFilename(SCOPE_CONFIG, "userbouquet.favourites.tv")
	resolveFilename(SCOPE_CONFIG, "bouquets.tv")
	resolveFilename(SCOPE_CONFIG, "userbouquet.favourites.radio")
	resolveFilename(SCOPE_CONFIG, "bouquets.radio")

# Returns a list of tuples containing pathname and filename matching the given pattern
# Example-pattern: match all txt-files: ".*\.txt$"
#
def crawlDirectory(directory, pattern):
	list = []
	if directory:
		expression = compile(pattern)
		for root, dirs, files in os.walk(directory):
			for file in files:
				if expression.match(file) is not None:
					list.append((root, file))
	return list

def copyfile(src, dst):
	f1 = None
	f2 = None
	status = 0
	try:
		f1 = open(src, "rb")
		if os.path.isdir(dst):
			dst = os.path.join(dst, os.path.basename(src))
		f2 = open(dst, "w+b")
		while True:
			buf = f1.read(16 * 1024)
			if not buf:
				break
			f2.write(buf)
	except OSError, e:
		print "[Directories] Error %d: Copying file '%s' to '%s'! (%s)" % (e.errno, src, dst, os.strerror(e.error))
		status = -1
	if f1 is not None:
		f1.close()
	if f2 is not None:
		f2.close()
	try:
		st = os.stat(src)
		mode = os.stat.S_IMODE(st.st_mode)
		os.chmod(dst, mode)
		os.utime(dst, (st.st_atime, st.st_mtime))
	except OSError, e:
		print "[Directories] Error %d: Copying stats from '%s' to '%s'! (%s)" % (e.errno, src, dst, os.strerror(e.error))
	return status

def copytree(src, dst, symlinks=False):
	names = os.listdir(src)
	if os.path.isdir(dst):
		dst = os.path.join(dst, os.path.basename(src))
		if not os.path.isdir(dst):
			os.mkdir(dst)
	else:
		os.makedirs(dst)
	for name in names:
		srcname = os.path.join(src, name)
		dstname = os.path.join(dst, name)
		try:
			if symlinks and os.path.islink(srcname):
				linkto = os.readlink(srcname)
				os.symlink(linkto, dstname)
			elif os.path.isdir(srcname):
				copytree(srcname, dstname, symlinks)
			else:
				copyfile(srcname, dstname)
		except OSError, e:
			print "[Directories] Error %d: Copying tree '%s' to '%s'! (%s)" % (e.errno, srcname, dstname, os.strerror(e.error))
	try:
		st = os.stat(src)
		mode = os.stat.S_IMODE(st.st_mode)
		os.chmod(dst, mode)
		os.utime(dst, (st.st_atime, st.st_mtime))
	except OSError, e:
		print "[Directories] Error %d: Copying stats from '%s' to '%s'! (%s)" % (e.errno, src, dst, os.strerror(e.error))

# Renames files or if source and destination are on different devices moves them in background
# input list of (source, destination)
#
def moveFiles(fileList):
	errorFlag = False
	movedList = []
	try:
		for item in fileList:
			os.rename(item[0], item[1])
			movedList.append(item)
	except OSError, e:
		if e.errno == 18:  # errno.EXDEV - Invalid cross-device link
			print "[Directories] Warning: Cannot rename across devices, trying slower move."
			from Tools.CopyFiles import moveFiles as extMoveFiles  # OpenViX, OpenATV, Beyonwiz
			# from Screens.CopyFiles import moveFiles as extMoveFiles  # OpenPLi
			extMoveFiles(fileList, item[0])
			print "[Directories] Moving files in background."
		else:
			print "[Directories] Error %d: Moving file '%s' to '%s'! (%s)" % (e.errno, item[0], item[1], os.strerror(e.error))
			errorFlag = True
	if errorFlag:
		print "[Directories] Reversing renamed files due to error."
		for item in movedList:
			try:
				os.rename(item[1], item[0])
			except OSError, e:
				print "[Directories] Error %d: Renaming '%s' to '%s'! (%s)" % (e.errno, item[1], item[0], os.strerror(e.error))
				print "[Directories] Failed to undo move:", item

def getSize(path, pattern=".*"):
	path_size = 0
	if os.path.isdir(path):
		files = crawlDirectory(path, pattern)
		for file in files:
			filepath = os.path.join(file[0], file[1])
			path_size += os.path.getsize(filepath)
	elif os.path.isfile(path):
		path_size = os.path.getsize(path)
	return path_size

def lsof():
	lsof = []
	for pid in os.listdir("/proc"):
		if pid.isdigit():
			try:
				prog = os.readlink(os.path.join("/proc", pid, "exe"))
				dir = os.path.join("/proc", pid, "fd")
				for file in [os.path.join(dir, file) for file in os.listdir(dir)]:
					lsof.append((pid, prog, os.readlink(file)))
			except OSError:
				pass
	return lsof

def getExtension(file):
	filename, extension = os.path.splitext(file)
	return extension

def mediafilesInUse(session):
	from Components.MovieList import KNOWN_EXTENSIONS
	files = [x[2] for x in lsof() if getExtension(x[2]) in KNOWN_EXTENSIONS]
	service = session.nav.getCurrentlyPlayingServiceOrGroup()
	filename = service and service.getPath()
	if filename and "://" in filename:  # When path is a stream ignore it.
		filename = None
	return set([file for file in files if not(filename and file.startswith(filename) and files.count(filename) < 2)])

def shellquote(s):
	return "'" + s.replace("'", "'\\''") + "'"
