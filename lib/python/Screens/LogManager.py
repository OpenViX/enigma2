from Screens.Screen import Screen
from Components.GUIComponent import GUIComponent
from Components.VariableText import VariableText
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Button import Button
from Components.FileList import FileList
from Components.ScrollLabel import ScrollLabel
from Components.config import config, configfile
from Components.FileList import MultiFileSelectList
from Screens.MessageBox import MessageBox
from os import path, remove, walk, stat, rmdir
from time import time
from enigma import eTimer, eBackgroundFileEraser, eLabel
from glob import glob
import sys

import Components.Task

# Import smtplib for the actual sending function
import smtplib
import base64

# Here are the email package modules we'll need
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
if sys.version_info[0] >= 3:
	from email.utils import formatdate
else:
	from email.Utils import formatdate

_session = None


def get_size(start_path=None):
	total_size = 0
	if start_path:
		for dirpath, dirnames, filenames in walk(start_path):
			for f in filenames:
				fp = path.join(dirpath, f)
				total_size += path.getsize(fp)
		return total_size
	return 0


def AutoLogManager(session=None, **kwargs):
	global debuglogcheckpoller
	debuglogcheckpoller = LogManagerPoller()
	debuglogcheckpoller.start()


class LogManagerPoller:
	"""Automatically Poll LogManager"""

	def __init__(self):
		# Init Timer
		self.TrimTimer = eTimer()
		self.TrashTimer = eTimer()

	def start(self):
		if self.TrimTimerJob not in self.TrimTimer.callback:
			self.TrimTimer.callback.append(self.TrimTimerJob)
		if self.TrashTimerJob not in self.TrashTimer.callback:
			self.TrashTimer.callback.append(self.TrashTimerJob)
		self.TrimTimer.startLongTimer(0)
		self.TrashTimer.startLongTimer(0)

	def stop(self):
		if self.TrimTimerJob in self.TrimTimer.callback:
			self.TrimTimer.callback.remove(self.TrimTimerJob)
		if self.TrashTimerJob in self.TrashTimer.callback:
			self.TrashTimer.callback.remove(self.TrashTimerJob)
		self.TrimTimer.stop()
		self.TrashTimer.stop()

	def TrimTimerJob(self):
		print("[LogManager] Trim Poll Started")
		Components.Task.job_manager.AddJob(self.createTrimJob())

	def TrashTimerJob(self):
		print("[LogManager] Trash Poll Started")
		Components.Task.job_manager.AddJob(self.createTrashJob())

	def createTrimJob(self):
		job = Components.Task.Job(_("LogManager"))
		task = Components.Task.PythonTask(job, _("Checking Logs..."))
		task.work = self.JobTrim
		task.weighting = 1
		return job

	def createTrashJob(self):
		job = Components.Task.Job(_("LogManager"))
		task = Components.Task.PythonTask(job, _("Checking Logs..."))
		task.work = self.JobTrash
		task.weighting = 1
		return job

	def openFiles(self, ctimeLimit, allowedBytes):
		ctimeLimit = ctimeLimit
		allowedBytes = allowedBytes

	def JobTrim(self):
		filename = ""
		for filename in glob(config.crash.debug_path.value + '*.log'):
			if path.getsize(filename) > (config.crash.debugloglimit.value * 1024 * 1024):
				fh = open(filename, 'rb+')
				fh.seek(-(config.crash.debugloglimit.value * 1024 * 1024), 2)
				data = fh.read()
				fh.seek(0) # rewind
				fh.write(data)
				fh.truncate()
				fh.close()
		self.TrimTimer.startLongTimer(3600) #once an hour

	def JobTrash(self):
		ctimeLimit = time() - (config.crash.daysloglimit.value * 3600 * 24)
		allowedBytes = 1024 * 1024 * int(config.crash.sizeloglimit.value)

		mounts = []
		matches = []
		print("[LogManager] probing folders")
		with open("/proc/mounts", "r") as f:
			for line in f.readlines():
				parts = line.strip().split()
				mounts.append(parts[1])

		for mount in mounts:
			if path.isdir(path.join(mount, 'logs')):
				matches.append(path.join(mount, 'logs'))
		matches.append('/home/root/logs')

		print("[LogManager] found following log's:", matches)
		if len(matches):
			for logsfolder in matches:
				print("[LogManager] looking in:", logsfolder)
				logssize = get_size(logsfolder)
				bytesToRemove = logssize - allowedBytes
				candidates = []
				size = 0
				for root, dirs, files in walk(logsfolder, topdown=False):
					for name in files:
						try:
							fn = path.join(root, name)
							st = stat(fn)
							if st.st_ctime < ctimeLimit:
								print("[LogManager] " + str(fn) + ": Too old:", name, st.st_ctime)
								eBackgroundFileEraser.getInstance().erase(fn)
								bytesToRemove -= st.st_size
							else:
								candidates.append((st.st_ctime, fn, st.st_size))
								size += st.st_size
						except Exception as e:
							print("[LogManager] Failed to stat %s:" % name, e)
					# Remove empty directories if possible
					for name in dirs:
						try:
							rmdir(path.join(root, name))
						except:
							pass
					candidates.sort()
					# Now we have a list of ctime, candidates, size. Sorted by ctime (=deletion time)
					for st_ctime, fn, st_size in candidates:
						print("[LogManager] " + str(logsfolder) + ": bytesToRemove", bytesToRemove)
						if bytesToRemove < 0:
							break
						eBackgroundFileEraser.getInstance().erase(fn)
						bytesToRemove -= st_size
						size -= st_size
		self.TrashTimer.startLongTimer(43200) #twice a day


class LogManager(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.logtype = 'crashlogs'

		self['myactions'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions'],
			{
				'ok': self.changeSelectionState,
				'cancel': self.close,
				'red': self.changelogtype,
				'green': self.showLog,
				'yellow': self.deletelog,
				"left": self.left,
				"right": self.right,
				"down": self.down,
				"up": self.up
			}, -1)

		self["key_red"] = Button(_("Debug Logs"))
		self["key_green"] = Button(_("View"))
		self["key_yellow"] = Button(_("Delete"))

		self.onChangedEntry = []
		self.sentsingle = ""
		self.selectedFiles = config.logmanager.sentfiles.value
		self.defaultDir = config.crash.debug_path.value
		self.matchingPattern = 'Enigma2_crash_'
		self.filelist = MultiFileSelectList(self.selectedFiles, self.defaultDir, showDirectories=False, matchingPattern=self.matchingPattern)
		self["list"] = self.filelist
		self["LogsSize"] = self.logsinfo = LogInfo(config.crash.debug_path.value, LogInfo.USED, update=False)
		self.onLayoutFinish.append(self.layoutFinished)
		if not self.selectionChanged in self["list"].onSelectionChanged:
			self["list"].onSelectionChanged.append(self.selectionChanged)

	def createSummary(self):
		from Screens.PluginBrowser import PluginBrowserSummary
		return PluginBrowserSummary

	def selectionChanged(self):
		item = self["list"].getCurrent()
		desc = ""
		if item:
			name = str(item[0][0])
		else:
			name = ""
		for cb in self.onChangedEntry:
			cb(name, desc)

	def layoutFinished(self):
		self["LogsSize"].update(config.crash.debug_path.value)
		idx = 0
		self["list"].moveToIndex(idx)
		self.setWindowTitle()

	def setWindowTitle(self):
		self.setTitle(self.defaultDir)

	def up(self):
		self["list"].up()

	def down(self):
		self["list"].down()

	def left(self):
		self["list"].pageUp()

	def right(self):
		self["list"].pageDown()

	def saveSelection(self):
		self.selectedFiles = self["list"].getSelectedList()
		config.logmanager.sentfiles.setValue(self.selectedFiles)
		config.logmanager.sentfiles.save()
		configfile.save()

	def exit(self):
		self.close(None)

	def changeSelectionState(self):
		try:
			self.sel = self["list"].getCurrent()[0]
		except:
			self.sel = None
		if self.sel:
			self["list"].changeSelectionState()
			self.selectedFiles = self["list"].getSelectedList()

	def changelogtype(self):
		self["LogsSize"].update(config.crash.debug_path.value)
		import re
		if self.logtype == 'crashlogs':
			self["key_red"].setText(_("Crash Logs"))
			self.logtype = 'debuglogs'
			self.matchingPattern = 'Enigma2_debug_'
		else:
			self["key_red"].setText(_("Debug Logs"))
			self.logtype = 'crashlogs'
			self.matchingPattern = 'Enigma2_crash_'
		self["list"].matchingPattern = re.compile(self.matchingPattern)
		self["list"].changeDir(self.defaultDir)

	def showLog(self):
		try:
			self.sel = self["list"].getCurrent()[0]
		except:
			self.sel = None
		if self.sel:
			self.session.open(LogManagerViewLog, self.sel[0])

	def deletelog(self):
		try:
			self.sel = self["list"].getCurrent()[0]
		except:
			self.sel = None
		self.selectedFiles = self["list"].getSelectedList()
		if self.selectedFiles:
			message = _("Do you want to delete all the selected files:\n(choose 'No' to only delete the currently selected file.)")
			ybox = self.session.openWithCallback(self.doDelete1, MessageBox, message, MessageBox.TYPE_YESNO)
			ybox.setTitle(_("Delete Confirmation"))
		elif self.sel:
			message = _("Are you sure you want to delete this log:\n") + str(self.sel[0])
			ybox = self.session.openWithCallback(self.doDelete3, MessageBox, message, MessageBox.TYPE_YESNO)
			ybox.setTitle(_("Delete Confirmation"))
		else:
			self.session.open(MessageBox, _("You have not selected any logs to delete."), MessageBox.TYPE_INFO, timeout=10)

	def doDelete1(self, answer):
		self.selectedFiles = self["list"].getSelectedList()
		self.selectedFiles = ",".join(self.selectedFiles).replace(",", " ")
		self.sel = self["list"].getCurrent()[0]
		if answer is True:
			message = _("Are you sure you want to delete all the selected logs:\n") + self.selectedFiles
			ybox = self.session.openWithCallback(self.doDelete2, MessageBox, message, MessageBox.TYPE_YESNO)
			ybox.setTitle(_("Delete Confirmation"))
		else:
			message = _("Are you sure you want to delete this log:\n") + str(self.sel[0])
			ybox = self.session.openWithCallback(self.doDelete3, MessageBox, message, MessageBox.TYPE_YESNO)
			ybox.setTitle(_("Delete Confirmation"))

	def doDelete2(self, answer):
		if answer is True:
			self.selectedFiles = self["list"].getSelectedList()
			self["list"].instance.moveSelectionTo(0)
			for f in self.selectedFiles:
				remove(f)
			config.logmanager.sentfiles.setValue("")
			config.logmanager.sentfiles.save()
			configfile.save()
			self["list"].changeDir(self.defaultDir)

	def doDelete3(self, answer):
		if answer is True:
			self.sel = self["list"].getCurrent()[0]
			self["list"].instance.moveSelectionTo(0)
			if path.exists(self.defaultDir + self.sel[0]):
				remove(self.defaultDir + self.sel[0])
			self["list"].changeDir(self.defaultDir)
			self["LogsSize"].update(config.crash.debug_path.value)


class LogManagerViewLog(Screen):
	def __init__(self, session, selected):
		Screen.__init__(self, session)
		self.session = session
		self.setTitle(selected)

		if path.exists(config.crash.debug_path.value + selected):
			log = open(config.crash.debug_path.value + selected).read()
		else:
			log = ""
		self["list"] = ScrollLabel(str(log))
		self["setupActions"] = ActionMap(["SetupActions", "ColorActions", "DirectionActions"],
		{
			"cancel": self.cancel,
			"ok": self.cancel,
			"up": self["list"].pageUp,
			"down": self["list"].pageDown,
			"right": self["list"].lastPage
		}, -2)

	def cancel(self):
		self.close()


class LogManagerFb(Screen):
	def __init__(self, session, logpath=None):
		if logpath is None:
			if path.isdir(config.logmanager.path.value):
				logpath = config.logmanager.path.value
			else:
				logpath = "/"

		self.session = session
		Screen.__init__(self, session)

		self["list"] = FileList(logpath, matchingPattern="^.*")
		self["red"] = Label(_("delete"))
		self["green"] = Label(_("move"))
		self["yellow"] = Label(_("copy"))
		self["blue"] = Label(_("rename"))

		self["actions"] = ActionMap(["ChannelSelectBaseActions", "WizardActions", "DirectionActions", "MenuActions", "NumberActions", "ColorActions"],
			{
			 "ok": self.ok,
			 "back": self.exit,
			 "up": self.goUp,
			 "down": self.goDown,
			 "left": self.goLeft,
			 "right": self.goRight,
			 "0": self.doRefresh,
			 }, -1)
		self.onLayoutFinish.append(self.mainlist)

	def exit(self):
		if self["list"].getCurrentDirectory():
			config.logmanager.path.setValue(self["list"].getCurrentDirectory())
			config.logmanager.path.save()
		self.close()

	def ok(self):
		if self.SOURCELIST.canDescent(): # isDir
			self.SOURCELIST.descent()
			if self.SOURCELIST.getCurrentDirectory(): #??? when is it none
				self.setTitle(self.SOURCELIST.getCurrentDirectory())
		else:
			self.onFileAction()

	def goLeft(self):
		self.SOURCELIST.pageUp()

	def goRight(self):
		self.SOURCELIST.pageDown()

	def goUp(self):
		self.SOURCELIST.up()

	def goDown(self):
		self.SOURCELIST.down()

	def doRefresh(self):
		self.SOURCELIST.refresh()

	def mainlist(self):
		self["list"].selectionEnabled(1)
		self.SOURCELIST = self["list"]
		self.setTitle(self.SOURCELIST.getCurrentDirectory())

	def onFileAction(self):
		if self["list"].getCurrentDirectory():
			config.logmanager.path.setValue(self["list"].getCurrentDirectory())
			config.logmanager.path.save()
		self.close()


class LogInfo(VariableText, GUIComponent):
	FREE = 0
	USED = 1
	SIZE = 2

	def __init__(self, path, type, update=True):
		GUIComponent.__init__(self)
		VariableText.__init__(self)
		self.type = type
# 		self.path = config.crash.debug_path.value
		if update:
			self.update(path)

	def update(self, path):
		try:
			total_size = get_size(path)
		except OSError:
			return -1

		if self.type == self.USED:
			try:
				if total_size < 10000000:
					total_size = "%d kB" % (total_size >> 10)
				elif total_size < 10000000000:
					total_size = "%d MB" % (total_size >> 20)
				else:
					total_size = "%d GB" % (total_size >> 30)
				self.setText(_("Space used:") + " " + total_size)
			except:
				# occurs when f_blocks is 0 or a similar error
				self.setText("-?-")

	GUI_WIDGET = eLabel
