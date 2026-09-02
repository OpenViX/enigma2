from Components.FileList import FileList
from Components.Sources.StaticText import StaticText
from Components.config import config, ConfigYesNo, ConfigDirectory
from Components.ActionMap import ActionMap
from Components.Pixmap import Pixmap
from Components.Sources.Boolean import Boolean
from Screens.Screen import Screen
from Screens.Setup import Setup
from Screens.HelpMenu import HelpableScreen

config.mediaplayer.repeat = ConfigYesNo(default=False)
config.mediaplayer.savePlaylistOnExit = ConfigYesNo(default=True)
config.mediaplayer.saveDirOnExit = ConfigYesNo(default=False)
config.mediaplayer.defaultDir = ConfigDirectory()
config.mediaplayer.sortPlaylists = ConfigYesNo(default=False)
config.mediaplayer.alwaysHideInfoBar = ConfigYesNo(default=True)
config.mediaplayer.onMainMenu = ConfigYesNo(default=False)


class DirectoryBrowser(Screen, HelpableScreen):

	def __init__(self, session, currDir, title=None):
		Screen.__init__(self, session)
		# for the skin: first try MediaPlayerDirectoryBrowser, then FileBrowser, this allows individual skinning
		self.skinName = ["MediaPlayerDirectoryBrowser", "FileBrowser"]

		HelpableScreen.__init__(self)

		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Use"))

		self["filelist"] = FileList(currDir, matchingPattern="")

		self["FilelistActions"] = ActionMap(["SetupActions", "ColorActions"],
			{
				"green": self.use,
				"red": self.exit,
				"ok": self.ok,
				"cancel": self.exit
			})
		self.title_ = title if title else _("Directory browser")

	def ok(self):
		if self["filelist"].canDescent():
			self["filelist"].descent()

	def use(self):
		if self["filelist"].getCurrentDirectory() is not None:
			if self["filelist"].canDescent() and self["filelist"].getFilename() and len(self["filelist"].getFilename()) > len(self["filelist"].getCurrentDirectory()):
				self["filelist"].descent()
				self.close(self["filelist"].getCurrentDirectory())
		else:
			self.close(self["filelist"].getFilename())

	def exit(self):
		self.close(False)


class MediaPlayerSettings(Setup):

	def __init__(self, session, mediaplayer):
		self.mediaplayer = mediaplayer
		Setup.__init__(self, session)
		self.title = _("Edit settings")

	def createSetup(self):
		clist = [
			(_("Repeat playlist"), config.mediaplayer.repeat, _("When the playlist comes to the end, continue playing, starting with the first item in the playlist.")),
			(_("Save playlist on exit"), config.mediaplayer.savePlaylistOnExit, _("Retains the playlist for the next time MediaPlayer is used.")),
			(_("Save last directory on exit"), config.mediaplayer.saveDirOnExit, _("Remembers the current directory location for the next time MediaPlayer is opened.")),
		]
		if not config.mediaplayer.saveDirOnExit.value:
			clist.append((_("Default directory"), config.mediaplayer.defaultDir, _("The default directory is used as the initial filelist location when opening MediaPlayer.")))
		clist += [
			(_("Sorting of playlists"), config.mediaplayer.sortPlaylists, _("Sorts stored playlists alphabetically before loading them")),
			(_("Always hide infobar"), config.mediaplayer.alwaysHideInfoBar, _("Automatically hides the infobar a few second after video playback starts.")),
			(_("Show MediaPlayer in the main menu"), config.mediaplayer.onMainMenu, _("Places a shortcut to MediaPlayer in the main menu.")),
		]
		self["config"].list = clist

	def keySelect(self):
		if self["config"].getCurrent()[1] == config.mediaplayer.defaultDir:
			self.session.openWithCallback(self.DirectoryBrowserClosed, DirectoryBrowser, self.mediaplayer["filelist"].getCurrentDirectory(), _("Select the default initial directory"))
		else:
			Setup.keySelect(self)

	def DirectoryBrowserClosed(self, path):
		if path:
			config.mediaplayer.defaultDir.setValue(path)
			self.createSetup()
