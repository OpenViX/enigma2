# -*- coding: utf-8 -*-
from errno import ENOENT, EXDEV

from os.path import basename as pathBasename, dirname as pathDirname, exists as pathExists, getsize as pathGetsize, isdir as pathIsdir, isfile as pathIsfile, islink as pathIslink, join as pathJoin, normpath as pathNormpath, splitext as pathSplitext

from os import access, chmod, listdir, makedirs, mkdir, readlink, rename, rmdir, sep, stat as os_stat, statvfs, symlink, utime, walk, F_OK, R_OK, W_OK 

from enigma import eEnv, getDesktop
from re import compile, split
from stat import S_IMODE
from sys import _getframe as getframe
from unicodedata import normalize
from traceback import print_exc
from xml.etree.cElementTree import Element, fromstring, parse

SCOPE_HOME = 0  # DEBUG: Not currently used in Enigma2.
SCOPE_LANGUAGE = 1
SCOPE_KEYMAPS = 2
SCOPE_METADIR = 3
SCOPE_SKINS = 4
SCOPE_GUISKIN = 5
SCOPE_LCDSKIN = 6
SCOPE_FONTS = 7
SCOPE_PLUGINS = 8
SCOPE_PLUGIN = 9
SCOPE_PLUGIN_ABSOLUTE = 10
SCOPE_PLUGIN_RELATIVE = 11
SCOPE_SYSETC = 12
SCOPE_TRANSPONDERDATA = 13
SCOPE_CONFIG = 14
SCOPE_PLAYLIST = 15
SCOPE_MEDIA = 16
SCOPE_HDD = 17
SCOPE_TIMESHIFT = 18
SCOPE_DEFAULTDIR = 19
SCOPE_LIBDIR = 20

# Deprecated scopes:
SCOPE_ACTIVE_LCDSKIN = SCOPE_LCDSKIN
SCOPE_ACTIVE_SKIN = SCOPE_GUISKIN
SCOPE_CURRENT_LCDSKIN = SCOPE_LCDSKIN
SCOPE_CURRENT_PLUGIN = SCOPE_PLUGIN
SCOPE_CURRENT_SKIN = SCOPE_GUISKIN
SCOPE_SKIN = SCOPE_SKINS
SCOPE_SKIN_IMAGE = SCOPE_SKINS
SCOPE_USERETC = SCOPE_HOME

PATH_CREATE = 0
PATH_DONTCREATE = 1

defaultPaths = {
	SCOPE_HOME: ("", PATH_DONTCREATE),  # User home directory
	SCOPE_LANGUAGE: (eEnv.resolve("${datadir}/enigma2/po/"), PATH_DONTCREATE),
	SCOPE_KEYMAPS: (eEnv.resolve("${datadir}/keymaps/"), PATH_CREATE),
	SCOPE_METADIR: (eEnv.resolve("${datadir}/meta/"), PATH_CREATE),
	SCOPE_SKINS: (eEnv.resolve("${datadir}/enigma2/"), PATH_DONTCREATE),
	SCOPE_GUISKIN: (eEnv.resolve("${datadir}/enigma2/"), PATH_DONTCREATE),
	SCOPE_LCDSKIN: (eEnv.resolve("${datadir}/enigma2/display/"), PATH_DONTCREATE),
	SCOPE_FONTS: (eEnv.resolve("${datadir}/fonts/"), PATH_DONTCREATE),
	SCOPE_PLUGINS: (eEnv.resolve("${libdir}/enigma2/python/Plugins/"), PATH_CREATE),
	SCOPE_PLUGIN: (eEnv.resolve("${libdir}/enigma2/python/Plugins/"), PATH_CREATE),
	SCOPE_PLUGIN_ABSOLUTE: (eEnv.resolve("${libdir}/enigma2/python/Plugins/"), PATH_DONTCREATE),
	SCOPE_PLUGIN_RELATIVE: (eEnv.resolve("${libdir}/enigma2/python/Plugins/"), PATH_DONTCREATE),
	SCOPE_SYSETC: (eEnv.resolve("${sysconfdir}/"), PATH_DONTCREATE),
	SCOPE_TRANSPONDERDATA: (eEnv.resolve("${sysconfdir}/"), PATH_DONTCREATE),
	SCOPE_CONFIG: (eEnv.resolve("${sysconfdir}/enigma2/"), PATH_CREATE),
	SCOPE_PLAYLIST: (eEnv.resolve("${sysconfdir}/enigma2/playlist/"), PATH_CREATE),
	SCOPE_MEDIA: ("/media/", PATH_DONTCREATE),
	SCOPE_HDD: ("/media/hdd/movie/", PATH_DONTCREATE),
	SCOPE_TIMESHIFT: ("/media/hdd/timeshift/", PATH_DONTCREATE),
	SCOPE_DEFAULTDIR: (eEnv.resolve("${datadir}/enigma2/defaults/"), PATH_CREATE),
	SCOPE_LIBDIR: (eEnv.resolve("${libdir}/"), PATH_DONTCREATE)
}

scopeConfig = defaultPaths[SCOPE_CONFIG][0]
scopeGUISkin = defaultPaths[SCOPE_GUISKIN][0]
scopeLCDSkin = defaultPaths[SCOPE_LCDSKIN][0]
scopeFonts = defaultPaths[SCOPE_FONTS][0]
scopePlugins = defaultPaths[SCOPE_PLUGINS][0]

def addInList(*paths):
	return [path for path in paths if pathIsdir(path)]


skinResolveList = []
lcdskinResolveList = []
fontsResolveList = []


def resolveFilename(scope, base="", path_prefix=None):
	# You can only use the ~/ if we have a prefix directory.
	if str(base).startswith("~%s" % sep):  # You can only use the ~/ if we have a prefix directory.
		if path_prefix:
			base = pathJoin(path_prefix, base[2:])
		else:
			print("[Directories] Warning: resolveFilename called with base starting with '~%s' but 'path_prefix' is None!" % sep)
	if str(base).startswith(sep):  # Don't further resolve absolute paths.
		return pathNormpath(base)
	if scope not in defaultPaths:  # If an invalid scope is specified log an error and return None.
		print("[Directories] Error: Invalid scope=%s provided to resolveFilename!" % scope)
		return None
	path, flag = defaultPaths[scope]  # Ensure that the defaultPath directory that should exist for this scope does exist.
	if flag == PATH_CREATE and not pathExists(path):
		try:
			makedirs(path)
		except (IOError, OSError) as err:
			print("[Directories] Error %d: Couldn't create directory '%s'!  (%s)" % (err.errno, path, err.strerror))
			return None
	suffix = None  # Remove any suffix data and restore it at the end.
	data = base.split(":", 1)
	if len(data) > 1:
		base = data[0]
		suffix = data[1]
	path = base

	def itemExists(resolveList, base):
		baseList = [base]
		if base.endswith(".png"):
			baseList.append("%s%s" % (base[:-3], "svg"))
		elif base.endswith(".svg"):
			baseList.append("%s%s" % (base[:-3], "png"))
		for item in resolveList:
			for base in baseList:
				file = pathJoin(item, base)
				if pathExists(file):
					return file
		return base

	if base == "":  # If base is "" then set path to the scope.  Otherwise use the scope to resolve the base filename.
		path, flags = defaultPaths[scope]
		if scope == SCOPE_GUISKIN:  # If the scope is SCOPE_GUISKIN append the current skin to the scope path.
			from Components.config import config  # This import must be here as this module finds the config file as part of the config initialisation.
			skin = pathDirname(config.skin.primary_skin.value)
			path = pathJoin(path, skin)
		elif scope in (SCOPE_PLUGIN_ABSOLUTE, SCOPE_PLUGIN_RELATIVE):
			callingCode = pathNormpath(getframe(1).f_code.co_filename)
			plugins = pathNormpath(scopePlugins)
			path = None
			if comparePath(plugins, callingCode):
				pluginCode = callingCode[len(plugins) + 1:].split(sep)
				if len(pluginCode) > 2:
					relative = "%s%s%s" % (pluginCode[0], sep, pluginCode[1])
					path = pathJoin(plugins, relative)
	elif scope == SCOPE_GUISKIN:
		global skinResolveList
		if not skinResolveList:
			# This import must be here as this module finds the config file as part of the config initialisation.
			from Components.config import config
			skin = pathDirname(config.skin.primary_skin.value)
			skinResolveList = addInList(
				pathJoin(scopeConfig, skin),
				pathJoin(scopeConfig, "skin_common"),
				scopeConfig
			)
			if not "skin_default" in skin:
				skinResolveList += addInList(pathJoin(scopeGUISkin, skin))
			skinResolveList += addInList(
				pathJoin(scopeGUISkin, "skin_fallback_%d" % getDesktop(0).size().height()),
				pathJoin(scopeGUISkin, "skin_default"),
				scopeGUISkin
			)
		path = itemExists(skinResolveList, base)
	elif scope == SCOPE_LCDSKIN:
		global lcdskinResolveList
		if not lcdskinResolveList:
			# This import must be here as this module finds the config file as part of the config initialisation.
			from Components.config import config
			if hasattr(config.skin, "display_skin"):
				skin = pathDirname(config.skin.display_skin.value)
			else:
				skin = ""
			lcdskinResolveList = addInList(
				pathJoin(scopeConfig, "display", skin),
				pathJoin(scopeConfig, "display", "skin_common"),
				scopeConfig,
				pathJoin(scopeLCDSkin, skin),
				pathJoin(scopeLCDSkin, "skin_fallback_%s" % getDesktop(1).size().height()),
				pathJoin(scopeLCDSkin, "skin_default"),
				scopeLCDSkin
			)
		path = itemExists(lcdskinResolveList, base)
	elif scope == SCOPE_FONTS:
		global fontsResolveList
		if not fontsResolveList:
			# This import must be here as this module finds the config file as part of the config initialisation.
			from Components.config import config
			skin = pathDirname(config.skin.primary_skin.value)
			display = pathDirname(config.skin.display_skin.value) if hasattr(config.skin, "display_skin") else None
			fontsResolveList = addInList(
				pathJoin(scopeConfig, "fonts"),
				pathJoin(scopeConfig, skin, "fonts"),
				pathJoin(scopeConfig, skin)
			)
			if display:
				fontsResolveList += addInList(
					pathJoin(scopeConfig, "display", display, "fonts"),
					pathJoin(scopeConfig, "display", display)
				)
			fontsResolveList += addInList(
				pathJoin(scopeConfig, "skin_common"),
				scopeConfig,
				pathJoin(scopeGUISkin, skin, "fonts"),
				pathJoin(scopeGUISkin, skin),
				pathJoin(scopeGUISkin, "skin_default", "fonts"),
				pathJoin(scopeGUISkin, "skin_default")
			)
			if display:
				fontsResolveList += addInList(
					pathJoin(scopeLCDSkin, display, "fonts"),
					pathJoin(scopeLCDSkin, display)
				)
			fontsResolveList += addInList(
				pathJoin(scopeLCDSkin, "skin_default", "fonts"),
				pathJoin(scopeLCDSkin, "skin_default"),
				scopeFonts
			)
		path = itemExists(fontsResolveList, base)
	elif scope == SCOPE_PLUGIN:
		file = pathJoin(scopePlugins, base)
		if pathExists(file):
			path = file
	elif scope in (SCOPE_PLUGIN_ABSOLUTE, SCOPE_PLUGIN_RELATIVE):
		callingCode = pathNormpath(getframe(1).f_code.co_filename)
		plugins = pathNormpath(scopePlugins)
		path = None
		if comparePaths(plugins, callingCode):
			pluginCode = callingCode[len(plugins) + 1:].split(sep)
			if len(pluginCode) > 2:
				relative = pathJoin("%s%s%s" % (pluginCode[0], sep, pluginCode[1]), base)
				path = pathJoin(plugins, relative)
	else:
		path, flags = defaultPaths[scope]
		path = pathJoin(path, base)
	path = pathNormpath(path)
	if pathIsdir(path) and not path.endswith(sep):  # If the path is a directory then ensure that it ends with a "/".
		path = "%s%s" % (path, sep)
	if scope == SCOPE_PLUGIN_RELATIVE:
		path = path[len(plugins) + 1:]
	if suffix is not None:  # If a suffix was supplied restore it.
		path = "%s:%s" % (path, suffix)
	return path

def fileReadLine(filename, default=None, *args, **kwargs):
	try:
		with open(filename, "r") as fd:
			line = fd.read().strip().replace("\0", "")
	except (IOError, OSError) as err:
		if err.errno != ENOENT:  # ENOENT - No such file or directory.
			print_exc()
		line = default
	return line


def fileWriteLine(filename, line, *args, **kwargs):
	try:
		with open(filename, "w") as fd:
			fd.write(str(line))
		return 1
	except (IOError, OSError) as err:
		print_exc()
		return 0


def fileReadLines(filename, default=None, *args, **kwargs):
	try:
		with open(filename, "r") as fd:
			lines = fd.read().splitlines()
	except (IOError, OSError) as err:
		if err.errno != ENOENT:  # ENOENT - No such file or directory.
			print_exc()
		lines = default
	return lines


def fileWriteLines(filename, lines, *args, **kwargs):
	try:
		with open(filename, "w") as fd:
			if isinstance(lines, list):
				lines.append("")
				lines = "\n".join(lines)
			fd.write(lines)
		return 1
	except (IOError, OSError) as err:
		print_exc()
		return 0


def comparePaths(leftPath, rightPath):
	if leftPath.endswith(sep):
		leftPath = leftPath[:-1]
	if rightPath.endswith(sep):
		rightPath = rightPath[:-1]
	left = leftPath.split(sep)
	right = rightPath.split(sep)
	for segment in range(len(left)):
		if left[segment] != right[segment]:
			return False
	return True


def bestRecordingLocation(candidates):
	path = ""
	biggest = 0
	for candidate in candidates:
		try:
			# Must have some free space (i.e. not read-only).
			stat = statvfs(candidate[1])
			if stat.f_bavail:
				# Free space counts double.
				size = (stat.f_blocks + stat.f_bavail) * stat.f_bsize
				if size > biggest:
					biggest = size
					path = candidate[1]
		except (IOError, OSError) as err:
			print("[Directories] Error %d: Couldn't get free space for '%s' (%s)" % (err.errno, candidate[1], err.strerror))
	return path


def defaultRecordingLocation(candidate=None):
	if candidate and pathExists(candidate):
		return candidate
	# First, try whatever /hdd points to, or /media/hdd.
	try:
		path = readlink("/hdd")
	except OSError:
		path = "/media/hdd"
	if not pathExists(path):
		# Find the largest local disk.
		from Components import Harddisk
		mounts = [m for m in Harddisk.getProcMounts() if m[1].startswith("/media/")]
		# Search local devices first, use the larger one
		path = bestRecordingLocation([m for m in mounts if m[0].startswith("/dev/")])
		# If we haven't found a viable candidate yet, try remote mounts.
		if not path:
			path = bestRecordingLocation([m for m in mounts if not m[0].startswith("/dev/")])
	if path:
		# If there's a movie subdir, we'd probably want to use that.
		movie = pathJoin(path, "movie")
		if pathIsdir(movie):
			path = movie
		if not path.endswith("/"):
			path += "/"  # Bad habits die hard, old code relies on this.
	return path


def createDir(path, makeParents=False):
	try:
		if makeParents:
			makedirs(path)
		else:
			mkdir(path)
		return 1
	except OSError:
		return 0


def removeDir(path):
	try:
		rmdir(path)
		return 1
	except OSError:
		return 0


def fileExists(f, mode="r"):
	if mode == "r":
		acc_mode = R_OK
	elif mode == "w":
		acc_mode = W_OK
	else:
		acc_mode = F_OK
	return access(f, acc_mode)


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


def fileReadXML(filename, default=None, *args, **kwargs):
	dom = None
	try:
		with open(filename, "r") as fd:
			dom = parse(fd).getroot()
	except:
		print("[fileReadXML] failed to read", filename)
		print_exc()
	if dom is None and default:
		if isinstance(default, str):
			dom = fromstring(default)
		elif isinstance(default, Element):
			dom = default
	return dom

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
	# but we cannot leave the byte truncate in the middle of a
	# multi-byte utf8 character!
	# So convert to bytes, truncate then get back to unicode, ignoring
	# errors along the way, the result will be valid unicode.
	filename = filename.encode(encoding='utf-8', errors='ignore')[:247].decode(encoding='utf-8', errors='ignore')
	if dirname is not None:
		if not dirname.startswith("/"):
			dirname = pathJoin(defaultRecordingLocation(), dirname)
	else:
		dirname = defaultRecordingLocation()
	filename = pathJoin(dirname, filename)
	path = filename
	i = 1
	while True:
		if not pathIsfile(path + ".ts"):
			return path
		path = "%s_%03d" % (filename, i)
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
		for root, dirs, files in walk(directory):
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
		if pathIsdir(dst):
			dst = pathJoin(dst, pathBasename(src))
		f2 = open(dst, "w+b")
		while True:
			buf = f1.read(16 * 1024)
			if not buf:
				break
			f2.write(buf)
	except (IOError, OSError) as err:
		print("[Directories] Error %d: Copying file '%s' to '%s'! (%s)" % (err.errno, src, dst, err.strerror))
		status = -1
	if f1 is not None:
		f1.close()
	if f2 is not None:
		f2.close()
	try:
		st = os_stat(src)
		try:
			chmod(dst, S_IMODE(st.st_mode))
		except (IOError, OSError) as err:
			print("[Directories] Error %d: Setting modes from '%s' to '%s'! (%s)" % (err.errno, src, dst, err.strerror))
		try:
			utime(dst, (st.st_atime, st.st_mtime))
		except (IOError, OSError) as err:
			print("[Directories] Error %d: Setting times from '%s' to '%s'! (%s)" % (err.errno, src, dst, err.strerror))
	except (IOError, OSError) as err:
		print("[Directories] Error %d: Obtaining stats from '%s' to '%s'! (%s)" % (err.errno, src, dst, err.strerror))
	return status


def copytree(src, dst, symlinks=False):
	names = listdir(src)
	if pathIsdir(dst):
		dst = pathJoin(dst, pathBasename(src))
		if not pathIsdir(dst):
			mkdir(dst)
	else:
		makedirs(dst)
	for name in names:
		srcname = pathJoin(src, name)
		dstname = pathJoin(dst, name)
		try:
			if symlinks and pathIslink(srcname):
				linkto = readlink(srcname)
				symlink(linkto, dstname)
			elif pathIsdir(srcname):
				copytree(srcname, dstname, symlinks)
			else:
				copyfile(srcname, dstname)
		except (IOError, OSError) as err:
			print("[Directories] Error %d: Copying tree '%s' to '%s'! (%s)" % (err.errno, srcname, dstname, err.strerror))
	try:
		st = os_stat(src)
		try:
			chmod(dst, S_IMODE(st.st_mode))
		except (IOError, OSError) as err:
			print("[Directories] Error %d: Setting modes from '%s' to '%s'! (%s)" % (err.errno, src, dst, err.strerror))
		try:
			utime(dst, (st.st_atime, st.st_mtime))
		except (IOError, OSError) as err:
			print("[Directories] Error %d: Setting times from '%s' to '%s'! (%s)" % (err.errno, src, dst, err.strerror))
	except (IOError, OSError) as err:
		print("[Directories] Error %d: Obtaining stats from '%s' to '%s'! (%s)" % (err.errno, src, dst, err.strerror))

# Renames files or if source and destination are on different devices moves them in background
# input list of (source, destination)
#


def moveFiles(fileList):
	errorFlag = False
	movedList = []
	try:
		for item in fileList:
			rename(item[0], item[1])
			movedList.append(item)
	except (IOError, OSError) as err:
		if err.errno == EXDEV:  # Invalid cross-device link
			print("[Directories] Warning: Cannot rename across devices, trying slower move.")
			from Tools.CopyFiles import moveFiles as extMoveFiles  # OpenViX, OpenATV, Beyonwiz
			# from Screens.CopyFiles import moveFiles as extMoveFiles  # OpenPLi
			extMoveFiles(fileList, item[0])
			print("[Directories] Moving files in background.")
		else:
			print("[Directories] Error %d: Moving file '%s' to '%s'! (%s)" % (err.errno, item[0], item[1], err.strerror))
			errorFlag = True
	if errorFlag:
		print("[Directories] Reversing renamed files due to error.")
		for item in movedList:
			try:
				rename(item[1], item[0])
			except (IOError, OSError) as err:
				print("[Directories] Error %d: Renaming '%s' to '%s'! (%s)" % (err.errno, item[1], item[0], err.strerror))
				print("[Directories] Failed to undo move:", item)


def getSize(path, pattern=".*"):
	path_size = 0
	if pathIsdir(path):
		files = crawlDirectory(path, pattern)
		for file in files:
			filepath = pathJoin(file[0], file[1])
			path_size += pathGetsize(filepath)
	elif pathIsfile(path):
		path_size = pathGetsize(path)
	return path_size


def lsof():
	lsof = []
	for pid in listdir("/proc"):
		if pid.isdigit():
			try:
				prog = readlink(pathJoin("/proc", pid, "exe"))
				dir = pathJoin("/proc", pid, "fd")
				for file in [pathJoin(dir, file) for file in listdir(dir)]:
					lsof.append((pid, prog, readlink(file)))
			except OSError:
				pass
	return lsof


def getExtension(file):
	filename, extension = pathSplitext(file)
	return extension


def mediafilesInUse(session):
	from Components.MovieList import KNOWN_EXTENSIONS
	files = [pathBasename(x[2]) for x in lsof() if getExtension(x[2]) in KNOWN_EXTENSIONS]
	service = session.nav.getCurrentlyPlayingServiceOrGroup()
	filename = service and service.getPath()
	if filename:
		if "://" in filename:  # When path is a stream ignore it.
			filename = None
		else:
			filename = pathBasename(filename)
	return set([file for file in files if not(filename and file == filename and files.count(filename) < 2)])

# Prepare filenames for use in external shell processing. Filenames may
# contain spaces or other special characters.  This method adjusts the
# filename to be a safe and single entity for passing to a shell.
#


def shellquote(s):
	return "'%s'" % s.replace("'", "'\\''")


def isPluginInstalled(pluginname, pluginfile="plugin", pluginType=None):
	path = resolveFilename(SCOPE_PLUGINS)
	pluginfolders = [name for name in listdir(path) if pathIsdir(pathJoin(path, name)) and name not in ["__pycache__"]]
	if pluginType is None or pluginType in pluginfolders:
		plugintypes = pluginType and [pluginType] or pluginfolders
		for fileext in [".pyc", ".py"]:
			for plugintype in plugintypes:
				if pathIsfile(pathJoin(path, plugintype, pluginname, pluginfile + fileext)):
					return True
	return False


def sanitizeFilename(filename):
	"""Return a fairly safe version of the filename.

	We don't limit ourselves to ascii, because we want to keep municipality
	names, etc, but we do want to get rid of anything potentially harmful,
	and make sure we do not exceed Windows filename length limits.
	Hence a less safe blacklist, rather than a whitelist.
	"""
	blacklist = ["\\", "/", ":", "*", "?", "\"", "<", ">", "|", "\0", "(", ")", " "]
	reserved = [
		"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5",
		"COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5",
		"LPT6", "LPT7", "LPT8", "LPT9",
	]  # Reserved words on Windows
	filename = "".join(c for c in filename if c not in blacklist)
	# Remove all charcters below code point 32
	filename = "".join(c for c in filename if 31 < ord(c))
	filename = normalize("NFKD", filename)
	filename = filename.rstrip(". ")  # Windows does not allow these at end
	filename = filename.strip()
	if all([x == "." for x in filename]):
		filename = "__" + filename
	if filename in reserved:
		filename = "__" + filename
	if len(filename) == 0:
		filename = "__"
	if len(filename) > 255:
		parts = split(r"/|\\", filename)[-1].split(".")
		if len(parts) > 1:
			ext = "." + parts.pop()
			filename = filename[:-len(ext)]
		else:
			ext = ""
		if filename == "":
			filename = "__"
		if len(ext) > 254:
			ext = ext[254:]
		maxl = 255 - len(ext)
		filename = filename[:maxl]
		filename = filename + ext
		# Re-check last character (if there was no extension)
		filename = filename.rstrip(". ")
		if len(filename) == 0:
			filename = "__"
	return filename
