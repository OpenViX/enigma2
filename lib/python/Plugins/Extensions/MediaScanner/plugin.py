from os import access as osaccess, path as ospath, F_OK, R_OK
from Components.Harddisk import harddiskmanager
from Components.Scanner import scanDevice
from Plugins.Plugin import PluginDescriptor
from Screens.ChoiceBox import ChoiceBox
from Screens.InfoBar import InfoBar


def execute(option):
	# print("[MediaScanner] execute", option)
	if option is None:
		return

	(_, scanner, files, session) = option
	scanner.open(files, session)


def mountpoint_chosen(option):
	if option is None:
		return

	# print("[MediaScanner][ mountpoint_chosen] scanning", option)
	(description, mountpoint, session) = option
	res = scanDevice(mountpoint)
	list = [(r.description, r, res[r], session) for r in res]
	# print("[MediaScanner][ mountpoint_chosen]  description=%s, mountpoint=%s res=%s list=%s" % (description, mountpoint, res, list))

	if not list:
		from Screens.MessageBox import MessageBox
		if osaccess(mountpoint, F_OK | R_OK):
			session.open(MessageBox, _("No displayable files on this medium found!"), MessageBox.TYPE_INFO, simple=True, timeout=5)
		else:
			print("[MediaScanner][ mountpoint_chosen] ignore", mountpoint, "because its not accessible")
		return

	session.openWithCallback(execute, ChoiceBox,
		title=_("The following files were found..."),
		list=list)


def scan(session):
	from Screens.ChoiceBox import ChoiceBox
	parts = [(r.tabbedDescription(), r.mountpoint, session) for r in harddiskmanager.getMountedPartitions(onlyhotplug=False) if osaccess(r.mountpoint, F_OK | R_OK)]
	# print("[MediaScanner][scan] parts", parts)
	parts.append((_("Memory") + "\t/tmp", "/tmp", session))
	session.openWithCallback(mountpoint_chosen, ChoiceBox, title=_("Please select medium to be scanned"), list=parts)


def main(session, **kwargs):
	scan(session)


def menuEntry(*args):
	mountpoint_chosen(args)


def menuHook(menuid):
	if menuid != "mainmenu":
		return []
	from Tools.BoundFunction import boundFunction
	return [("%s (files)" % r.description, boundFunction(menuEntry, r.description, r.mountpoint), "hotplug_%s" % r.mountpoint, None) for r in harddiskmanager.getMountedPartitions(onlyhotplug=True)]


global_session = None


def partitionListChanged(action, device):
	if InfoBar.instance:
		if InfoBar.instance.execing:
			if action == 'add' and device.is_hotplug:
				print("[MediaScanner][partitionListChanged] mountpoint", device.mountpoint)
				print("[MediaScanner][partitionListChanged] description", device.description)
				print("[MediaScanner][partitionListChanged] force_mounted", device.force_mounted)
				mountpoint_chosen((device.description, device.mountpoint, global_session))
		else:
			print("[MediaScanner][partitionListChanged] main infobar is not execing... so we ignore hotplug event!")
	else:
		print("[MediaScanner][partitionListChanged] hotplug event.. but no infobar")


def sessionstart(reason, session):
	global global_session
	global_session = session


def autostart(reason, **kwargs):
	global global_session
	if reason == 0:
		harddiskmanager.on_partition_list_change.append(partitionListChanged)
	elif reason == 1:
		harddiskmanager.on_partition_list_change.remove(partitionListChanged)
		global_session = None


def movielist_open(list, session, **kwargs):
	from Components.config import config
	if not list:
		# sanity
		return
	from enigma import eServiceReference
	from Screens.InfoBar import InfoBar
	f = list[0]
	if f.mimetype == "video/MP2T":
		stype = 1
	else:
		stype = 4097
	if InfoBar.instance:
		path = ospath.split(f.path)[0]
		if not path.endswith('/'):
			path += '/'
		config.movielist.last_videodir.value = path
		InfoBar.instance.showMovies(eServiceReference(stype, 0, f.path))


def filescan(**kwargs):
	from Components.Scanner import Scanner, ScanPath
	return [
		Scanner(mimetypes=["video/mpeg", "video/MP2T", "video/x-msvideo", "video/mkv", "video/avi"],
			paths_to_scan=[
				ScanPath(path="", with_subdirs=False),
				ScanPath(path="movie", with_subdirs=False),
			],
			name="Movie",
			description=_("View Movies..."),
			openfnc=movielist_open,
		),
		Scanner(mimetypes=["video/x-vcd"],
			paths_to_scan=[
				ScanPath(path="mpegav", with_subdirs=False),
				ScanPath(path="MPEGAV", with_subdirs=False),
			],
			name="Video CD",
			description=_("View Video CD..."),
			openfnc=movielist_open,
		),
		Scanner(mimetypes=["audio/mpeg", "audio/x-wav", "application/ogg", "audio/x-flac"],
			paths_to_scan=[
				ScanPath(path="", with_subdirs=False),
			],
			name="Music",
			description=_("Play Music..."),
			openfnc=movielist_open,
		),
		Scanner(mimetypes=["audio/x-cda"],
			paths_to_scan=[
				ScanPath(path="", with_subdirs=False),
			],
			name="Audio-CD",
			description=_("Play Audio-CD..."),
			openfnc=movielist_open,
		),
		]


def Plugins(**kwargs):
	return [
		PluginDescriptor(name=_("Media scanner"), description=_("Scan files..."), where=PluginDescriptor.WHERE_PLUGINMENU, needsRestart=True, fnc=main),
		# PluginDescriptor(where = PluginDescriptor.WHERE_MENU, fnc=menuHook),
		PluginDescriptor(name=_("Media scanner"), where=PluginDescriptor.WHERE_FILESCAN, needsRestart=False, fnc=filescan),
		PluginDescriptor(where=PluginDescriptor.WHERE_SESSIONSTART, needsRestart=True, fnc=sessionstart),
		PluginDescriptor(where=PluginDescriptor.WHERE_AUTOSTART, needsRestart=True, fnc=autostart)
		]
