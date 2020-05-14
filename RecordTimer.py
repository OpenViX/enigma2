from boxbranding import getMachineBrand, getMachineName
import os
from enigma import eEPGCache, getBestPlayableServiceReference, eStreamServer, eServiceReference, iRecordableService, quitMainloop, eActionMap, setPreferredTuner, eServiceCenter

from Components.config import config
from Components.UsageConfig import defaultMoviePath
from Components.SystemInfo import SystemInfo
from Components.TimerSanityCheck import TimerSanityCheck

from Screens.MessageBox import MessageBox
from Screens.PictureInPicture import PictureInPicture
import Screens.Standby
import Screens.InfoBar
import Components.ParentalControl
from Tools import Directories, Notifications, ASCIItranslit, Trashcan
from Tools.XMLTools import stringToXML

import timer
import xml.etree.cElementTree
import NavigationInstance
from ServiceReference import ServiceReference

from time import localtime, strftime, ctime, time
from bisect import insort
from sys import maxint

# ok, for descriptions etc we have:
# service reference  (to get the service name)
# name               (title)
# description        (description)
# event data         (ONLY for time adjustments etc.)


# We need to handle concurrency when updating timers.xml
#
import threading
write_lock = threading.Lock()

# parses an event, and gives out a (begin, end, name, duration, eit)-tuple.
# begin and end will be corrected
def parseEvent(ev, description = True):
	if description:
		name = ev.getEventName()
		description = ev.getShortDescription()
		if description == "":
			description = ev.getExtendedDescription()
	else:
		name = ""
		description = ""
	begin = ev.getBeginTime()
	end = begin + ev.getDuration()
	eit = ev.getEventId()
	begin -= config.recording.margin_before.value * 60
	end += config.recording.margin_after.value * 60
	return (begin, end, name, description, eit)

class AFTEREVENT:
	def __init__(self):
		pass

	NONE = 0
	STANDBY = 1
	DEEPSTANDBY = 2
	AUTO = 3

def findSafeRecordPath(dirname):
	if not dirname:
		return None
	from Components import Harddisk
	dirname = os.path.realpath(dirname)
	mountpoint = Harddisk.findMountPoint(dirname)
	if not os.path.ismount(mountpoint):
		print '[RecordTimer] media is not mounted:', dirname
		return None
	if not os.path.isdir(dirname):
		try:
			os.makedirs(dirname)
		except Exception, ex:
			print '[RecordTimer] Failed to create dir "%s":' % dirname, ex
			return None
	return dirname

# This code is for use by hardware with a stb device file which, when
# non-zero, can display a visual indication on the front-panel that
# recordings are in progress, with possibly different icons for
# different numbers of concurrent recordings.
# NOTE that Navigation.py uses symbol_signal (which the mbtwin does not
#  have) to indicate that a recording is being played back. Different.
#
# Define the list of boxes which can use the code by setting the device
# path and number of different states it supports.
# Any undefined box will not use this code.
#
SID_symbol_states = {
	"mbtwin": ('/proc/stb/lcd/symbol_circle', 4)
}
from boxbranding import getBoxType
SID_code_states = SID_symbol_states.setdefault(getBoxType(), (None, 0))

n_recordings = 0  # Must be when we start running...
def SetIconDisplay(nrec):
	if SID_code_states[0] == None:  # Not the code for us
		return
	(wdev, max_states) = SID_code_states
	if nrec == 0:                   # An absolute setting - clear it...
		f = open(wdev, 'w')
		f.write('0')
		f.close()
		return
#
	sym = nrec
	if sym > max_states:
		sym = max_states
	if sym < 0:		    # Sanity check - just in case...
		sym = 0
	f = open(wdev, 'w')
	f.write(str(sym))
	f.close()
	return

# Define a function that is called at the start and stop of all
# recordings. This allows us to track the number of actual recordings.
# Other recording-related accounting could also be added here.
# alter is 1 at a recording start, -1 at a stop and 0 as enigma2 starts
# (to initialize things).


def RecordingsState(alter):
# Since we are about to modify it we need to declare it as global
#
	global n_recordings
	if not -1 <= alter <= 1:
		return

# Adjust the number of currently running recordings...
#
	if alter == 0:              # Initialize
		n_recordings = 0
	else:
		n_recordings += alter
	if n_recordings < 0:        # Sanity check - just in case...
		n_recordings = 0
	SetIconDisplay(n_recordings)
	return

RecordingsState(0)       # Initialize

# type 1 = digital television service
# type 4 = nvod reference service (NYI)
# type 17 = MPEG-2 HD digital television service
# type 22 = advanced codec SD digital television
# type 24 = advanced codec SD NVOD reference service (NYI)
# type 25 = advanced codec HD digital television
# type 27 = advanced codec HD NVOD reference service (NYI)
# type 2 = digital radio sound service
# type 10 = advanced codec digital radio sound service

service_types_tv = '1:7:1:0:0:0:0:0:0:0:(type == 1) || (type == 17) || (type == 22) || (type == 25) || (type == 134) || (type == 195)'
wasRecTimerWakeup = False

# please do not translate log messages
class RecordTimerEntry(timer.TimerEntry, object):
	def __init__(self, serviceref, begin, end, name, description, eit, disabled = False, justplay = False, afterEvent = AFTEREVENT.AUTO, checkOldTimers = False, dirname = None, tags = None, descramble = 'notset', record_ecm = 'notset', isAutoTimer = False, always_zap = False, rename_repeat = True, conflict_detection = True, pipzap = False):
		timer.TimerEntry.__init__(self, int(begin), int(end))
		if checkOldTimers:
			if self.begin < time() - 1209600:
				self.begin = int(time())

		if self.end < self.begin:
			self.end = self.begin

		assert isinstance(serviceref, ServiceReference)

		if serviceref and serviceref.isRecordable():
			self.service_ref = serviceref
		else:
			self.service_ref = ServiceReference(None)
		self.eit = eit
		self.dontSave = False
		self.name = name
		self.description = description
		self.disabled = disabled
		self.timer = None
		self.__record_service = None
		self.start_prepare = 0
		self.justplay = justplay
		self.always_zap = always_zap
		self.pipzap = pipzap
		self.afterEvent = afterEvent
		self.dirname = dirname
		self.dirnameHadToFallback = False
		self.autoincrease = False
		self.autoincreasetime = 3600 * 24 # 1 day
		self.tags = tags or []
		self.conflict_detection = conflict_detection

		if descramble == 'notset' and record_ecm == 'notset':
			if config.recording.ecm_data.value == 'descrambled+ecm':
				self.descramble = True
				self.record_ecm = True
			elif config.recording.ecm_data.value == 'scrambled+ecm':
				self.descramble = False
				self.record_ecm = True
			elif config.recording.ecm_data.value == 'normal':
				self.descramble = True
				self.record_ecm = False
		else:
			self.descramble = descramble
			self.record_ecm = record_ecm

		self.rename_repeat = rename_repeat
		self.setAdvancedPriorityFrontend = None
		if SystemInfo["DVB-T_priority_tuner_available"] or SystemInfo["DVB-C_priority_tuner_available"] or SystemInfo["DVB-S_priority_tuner_available"] or SystemInfo["ATSC_priority_tuner_available"]:
			rec_ref = self.service_ref and self.service_ref.ref
			str_service = rec_ref and rec_ref.toString()
			if str_service and '%3a//' not in str_service and not str_service.rsplit(":", 1)[1].startswith("/"):
				type_service = rec_ref.getUnsignedData(4) >> 16
				if type_service == 0xEEEE:
					if SystemInfo["DVB-T_priority_tuner_available"] and config.usage.recording_frontend_priority_dvbt.value != "-2":
						if config.usage.recording_frontend_priority_dvbt.value != config.usage.frontend_priority.value:
							self.setAdvancedPriorityFrontend = config.usage.recording_frontend_priority_dvbt.value
					if SystemInfo["ATSC_priority_tuner_available"] and config.usage.recording_frontend_priority_atsc.value != "-2":
						if config.usage.recording_frontend_priority_atsc.value != config.usage.frontend_priority.value:
							self.setAdvancedPriorityFrontend = config.usage.recording_frontend_priority_atsc.value
				elif type_service == 0xFFFF:
					if SystemInfo["DVB-C_priority_tuner_available"] and config.usage.recording_frontend_priority_dvbc.value != "-2":
						if config.usage.recording_frontend_priority_dvbc.value != config.usage.frontend_priority.value:
							self.setAdvancedPriorityFrontend = config.usage.recording_frontend_priority_dvbc.value
					if SystemInfo["ATSC_priority_tuner_available"] and config.usage.recording_frontend_priority_atsc.value != "-2":
						if config.usage.recording_frontend_priority_atsc.value != config.usage.frontend_priority.value:
							self.setAdvancedPriorityFrontend = config.usage.recording_frontend_priority_atsc.value
				else:
					if SystemInfo["DVB-S_priority_tuner_available"] and config.usage.recording_frontend_priority_dvbs.value != "-2":
						if config.usage.recording_frontend_priority_dvbs.value != config.usage.frontend_priority.value:
							self.setAdvancedPriorityFrontend = config.usage.recording_frontend_priority_dvbs.value
		self.needChangePriorityFrontend = self.setAdvancedPriorityFrontend is not None or config.usage.recording_frontend_priority.value != "-2" and config.usage.recording_frontend_priority.value != config.usage.frontend_priority.value

		self.change_frontend = False
		self.InfoBarInstance = Screens.InfoBar.InfoBar.instance
		self.ts_dialog = None
		self.isAutoTimer = isAutoTimer
		self.wasInStandby = False

		self.log_entries = []
		self.flags = set()
		self.resetState()

	def __repr__(self):
		if not self.disabled:
			return "RecordTimerEntry(name=%s, begin=%s, serviceref=%s, justplay=%s, isAutoTimer=%s)" % (self.name, ctime(self.begin), self.service_ref, self.justplay, self.isAutoTimer)
		else:
			return "RecordTimerEntry(name=%s, begin=%s, serviceref=%s, justplay=%s, isAutoTimer=%s, Disabled)" % (self.name, ctime(self.begin), self.service_ref, self.justplay, self.isAutoTimer)

	def log(self, code, msg):
		self.log_entries.append((int(time()), code, msg))
		print "[RecordTimer]", msg

	def freespace(self):
		self.MountPath = None
		if not self.dirname:
			dirname = findSafeRecordPath(defaultMoviePath())
		else:
			dirname = findSafeRecordPath(self.dirname)
			if dirname is None:
				dirname = findSafeRecordPath(defaultMoviePath())
				self.dirnameHadToFallback = True
		if not dirname:
			return False

		self.MountPath = dirname
		mountwriteable = os.access(dirname, os.W_OK)
		if not mountwriteable:
			self.log(0, ("Mount '%s' is not writeable." % dirname))
			return False

		s = os.statvfs(dirname)
		if (s.f_bavail * s.f_bsize) / 1000000 < 1024:
			self.log(0, "Not enough free space to record")
			return False
		else:
			self.log(0, "Found enough free space to record")
			return True

	def calculateFilename(self, name=None):
# An external caller (e.g. the enigma2 plugin Series Plugin) may well
# not have called freespace(). So we need to set MountPath here.
# There is no point in calling freespace() as the caller won't be able
# to handle anything it does anyway.
#
		if not hasattr(self, "MountPath"):
			self.MountPath = self.dirname

		service_name = self.service_ref.getServiceName()
		begin_date = strftime("%Y%m%d %H%M", localtime(self.begin))

		name = name or self.name
		filename = begin_date + " - " + service_name
		if name:
			if config.recording.filename_composition.value == "event":
				filename = name + ' - ' + begin_date + "_" + service_name
			elif config.recording.filename_composition.value == "short":
				filename = strftime("%Y%m%d", localtime(self.begin)) + " - " + name
			elif config.recording.filename_composition.value == "long":
				filename += " - " + name + " - " + self.description
			else:
				filename += " - " + name # standard

		if config.recording.ascii_filenames.value:
			filename = ASCIItranslit.legacyEncode(filename)

		self.Filename = Directories.getRecordingFilename(filename, self.MountPath)
		self.log(0, "Filename calculated as: '%s'" % self.Filename)
		return self.Filename

	def tryPrepare(self):
		if self.justplay:
			return True
		else:
			if not self.calculateFilename():
				self.do_backoff()
				self.start_prepare = time() + self.backoff
				return False
			rec_ref = self.service_ref and self.service_ref.ref
			if rec_ref and rec_ref.flags & eServiceReference.isGroup:
				rec_ref = getBestPlayableServiceReference(rec_ref, eServiceReference())
				if not rec_ref:
					self.log(1, "'get best playable service for group... record' failed")
					return False

			self.setRecordingPreferredTuner()
			self.record_service = rec_ref and NavigationInstance.instance.recordService(rec_ref)

			if not self.record_service:
				self.log(1, "'record service' failed")
				self.setRecordingPreferredTuner(setdefault=True)
				return False

			name = self.name
			description = self.description
			if self.repeated:
				epgcache = eEPGCache.getInstance()
				queryTime=self.begin+(self.end-self.begin)/2
				evt = epgcache.lookupEventTime(rec_ref, queryTime)
				if evt:
					if self.rename_repeat:
						event_description = evt.getShortDescription()
						if not event_description:
							event_description = evt.getExtendedDescription()
						if event_description and event_description != description:
							description = event_description
						event_name = evt.getEventName()
						if event_name and event_name != name:
							name = event_name
							if not self.calculateFilename(event_name):
								self.do_backoff()
								self.start_prepare = time() + self.backoff
								return False
					event_id = evt.getEventId()
				else:
					event_id = -1
			else:
				event_id = self.eit
				if event_id is None:
					event_id = -1

			prep_res=self.record_service.prepare(self.Filename + self.record_service.getFilenameExtension(), self.begin, self.end, event_id, name.replace("\n", ""), description.replace("\n", ""), ' '.join(self.tags), bool(self.descramble), bool(self.record_ecm))
			if prep_res:
				if prep_res == -255:
					self.log(4, "failed to write meta information")
				else:
					self.log(2, "'prepare' failed: error %d" % prep_res)

				# we must calc nur start time before stopRecordService call because in Screens/Standby.py TryQuitMainloop tries to get
				# the next start time in evEnd event handler...
				self.do_backoff()
				self.start_prepare = time() + self.backoff

				NavigationInstance.instance.stopRecordService(self.record_service)
				self.record_service = None
				self.setRecordingPreferredTuner(setdefault=True)
				return False
			return True

	def do_backoff(self):
		if self.backoff == 0:
			self.backoff = 5
		else:
			self.backoff *= 2
			if self.backoff > 100:
				self.backoff = 100
		self.log(10, "backoff: retry in %d seconds" % self.backoff)

	def sendactivesource(self):
		if SystemInfo["HasHDMI-CEC"] and config.hdmicec.enabled.value and config.hdmicec.sourceactive_zaptimers.value:
			import Components.HdmiCec
			Components.HdmiCec.hdmi_cec.sendMessage(0, "sourceactive")
			print "[TIMER] sourceactive was send"

# This same block of code appeared twice....
#
	def _bouquet_search(self):
		from Screens.ChannelSelection import ChannelSelection
		ChannelSelectionInstance = ChannelSelection.instance
		self.service_types = service_types_tv
		if ChannelSelectionInstance:
			if config.usage.multibouquet.value:
				bqrootstr = '1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "bouquets.tv" ORDER BY bouquet'
			else:
				bqrootstr = '%s FROM BOUQUET "userbouquet.favourites.tv" ORDER BY bouquet'% self.service_types
			rootstr = ''
			serviceHandler = eServiceCenter.getInstance()
			rootbouquet = eServiceReference(bqrootstr)
			bouquet = eServiceReference(bqrootstr)
			bouquetlist = serviceHandler.list(bouquet)
			if not bouquetlist is None:
				while True:
					bouquet = bouquetlist.getNext()
					if not bouquet.valid(): # Reached end of bouquets
						print "[RecordTimer] _bouquet_search reached end of bouquets..??"
						break
					if bouquet.flags & eServiceReference.isDirectory:
						ChannelSelectionInstance.clearPath()
						ChannelSelectionInstance.setRoot(bouquet)
						servicelist = serviceHandler.list(bouquet)
						if not servicelist is None:
							serviceIterator = servicelist.getNext()
							while serviceIterator.valid():
								if self.service_ref.ref == serviceIterator:
									break
								serviceIterator = servicelist.getNext()
							if self.service_ref.ref == serviceIterator:
								break
				ChannelSelectionInstance.enterPath(rootbouquet)
				ChannelSelectionInstance.enterPath(bouquet)
				ChannelSelectionInstance.saveRoot()
				ChannelSelectionInstance.saveChannel(self.service_ref.ref)
			ChannelSelectionInstance.addToHistory(self.service_ref.ref)
		NavigationInstance.instance.playService(self.service_ref.ref)

# Report the tuner that the current recording is using
	def log_tuner(self, level, state):
# If we have a Zap timer then the tuner is for the current service
		if self.justplay:
			timer_rs = NavigationInstance.instance.getCurrentService()
		else:
			timer_rs = self.record_service
		feinfo = timer_rs and hasattr(timer_rs, "frontendInfo") and timer_rs.frontendInfo()
		fedata = feinfo and hasattr(feinfo, "getFrontendData") and feinfo.getFrontendData()
		tuner_info = fedata and "tuner_number" in fedata and chr(ord('A') + fedata.get("tuner_number")) or "(fallback) stream"
		self.log(level, "%s recording on tuner: %s" % (state, tuner_info))

	def activate(self):
		next_state = self.state + 1
		self.log(5, "activating state %d" % next_state)

		if next_state == self.StatePrepared:
			if not self.justplay and not self.freespace():
				Notifications.AddPopup(text = _("Write error while recording. Disk full?\n%s") % self.name, type = MessageBox.TYPE_ERROR, timeout = 5, id = "DiskFullMessage")
				self.failed = True
				self.next_activation = time()
				self.end = time() + 5
				self.backoff = 0
				return True

			if self.always_zap:
				if Screens.Standby.inStandby:
					self.wasInStandby = True
					eActionMap.getInstance().bindAction('', -maxint - 1, self.keypress)
					#set service to zap after standby
					Screens.Standby.inStandby.prev_running_service = self.service_ref.ref
					Screens.Standby.inStandby.paused_service = None
					#wakeup standby
					Screens.Standby.inStandby.Power()
					self.log(5, "wakeup and zap to recording service")
				else:
					self.sendactivesource()
					cur_ref = NavigationInstance.instance.getCurrentlyPlayingServiceReference()
					if not cur_ref or not cur_ref.getPath():
						if self.checkingTimeshiftRunning():
							if self.ts_dialog is None:
								self.openChoiceActionBeforeZap()
						else:
							Notifications.AddNotification(MessageBox, _("In order to record a timer, the TV was switched to the recording service!\n"), type=MessageBox.TYPE_INFO, timeout=20)
							self.setRecordingPreferredTuner()
							self.failureCB(True)
							self.log(5, "zap to recording service")

			if self.tryPrepare():
				self.log(6, "prepare ok, waiting for begin")
				# create file to "reserve" the filename
				# because another recording at the same time on another service can try to record the same event
				# i.e. cable / sat.. then the second recording needs an own extension... when we create the file
				# here than calculateFilename is happy
				if not self.justplay:
					open(self.Filename + self.record_service.getFilenameExtension(), "w").close()
					# Give the Trashcan a chance to clean up
					# Need try/except as Trashcan.instance may not exist
					# for a missed recording started at boot-time.
					try:
						Trashcan.instance.cleanIfIdle()
					except Exception, e:
						print "[RecordTimer] Failed to call Trashcan.instance.cleanIfIdle()"
						print "[RecordTimer] Error:", e
				# fine. it worked, resources are allocated.
				self.next_activation = self.begin
				self.backoff = 0
				return True
			self.log(7, "prepare failed")
			if eStreamServer.getInstance().getConnectedClients():
				eStreamServer.getInstance().stopStream()
				return False
			if self.first_try_prepare or (self.ts_dialog is not None and not self.checkingTimeshiftRunning()):
				self.first_try_prepare = False
				cur_ref = NavigationInstance.instance.getCurrentlyPlayingServiceReference()
				if cur_ref and not cur_ref.getPath():
					if self.always_zap:
						return False
					if Screens.Standby.inStandby:
						self.setRecordingPreferredTuner()
						self.failureCB(True)
					elif self.checkingTimeshiftRunning():
						if self.ts_dialog is None:
							self.openChoiceActionBeforeZap()
					elif not config.recording.asktozap.value:
						self.log(8, "asking user to zap away")
						Notifications.AddNotificationWithCallback(self.failureCB, MessageBox, _("A timer failed to record!\nDisable TV and try again?\n"), timeout=20)
					else: # zap without asking
						self.log(9, "zap without asking")
						Notifications.AddNotification(MessageBox, _("In order to record a timer, the TV was switched to the recording service!\n"), type=MessageBox.TYPE_INFO, timeout=20)
						self.setRecordingPreferredTuner()
						self.failureCB(True)
				elif cur_ref:
					self.log(8, "currently running service is not a live service.. so stop it makes no sense")
				else:
					self.log(8, "currently no service running... so we dont need to stop it")
			return False

		elif next_state == self.StateRunning:
			global wasRecTimerWakeup
			if os.path.exists("/tmp/was_rectimer_wakeup") and not wasRecTimerWakeup:
				wasRecTimerWakeup = int(open("/tmp/was_rectimer_wakeup", "r").read()) and True or False
				os.remove("/tmp/was_rectimer_wakeup")

			self.autostate = Screens.Standby.inStandby

			# if this timer has been cancelled, just go to "end" state.
			if self.cancelled:
				return True

			if self.failed:
				return True

			if self.justplay:
				if Screens.Standby.inStandby:
					self.wasInStandby = True
					eActionMap.getInstance().bindAction('', -maxint - 1, self.keypress)
					self.log(11, "wakeup and zap")
					#set service to zap after standby
					Screens.Standby.inStandby.prev_running_service = self.service_ref.ref
					Screens.Standby.inStandby.paused_service = None
					#wakeup standby
					Screens.Standby.inStandby.Power()
				else:
					self.sendactivesource()
					notify = config.usage.show_message_when_recording_starts.value and self.InfoBarInstance and self.InfoBarInstance.execing
					if self.pipzap:
						cur_ref = NavigationInstance.instance.getCurrentlyPlayingServiceOrGroup()
						if cur_ref and cur_ref != self.service_ref.ref and self.InfoBarInstance and hasattr(self.InfoBarInstance.session, 'pipshown') and not Components.ParentalControl.parentalControl.isProtected(self.service_ref.ref):
							if self.InfoBarInstance.session.pipshown:
								hasattr(self.InfoBarInstance, "showPiP") and self.InfoBarInstance.showPiP()
							if hasattr(self.InfoBarInstance.session, 'pip'):
								del self.InfoBarInstance.session.pip
								self.InfoBarInstance.session.pipshown = False
							self.InfoBarInstance.session.pip = self.InfoBarInstance.session.instantiateDialog(PictureInPicture)
							self.InfoBarInstance.session.pip.show()
							if self.InfoBarInstance.session.pip.playService(self.service_ref.ref):
								self.InfoBarInstance.session.pipshown = True
								self.InfoBarInstance.session.pip.servicePath = self.InfoBarInstance.servicelist and self.InfoBarInstance.servicelist.getCurrentServicePath()
								self.log(11, "zapping as PiP")
								if notify:
									Notifications.AddPopup(text=_("Zapped to timer service %s as PiP!") % self.service_ref.getServiceName(), type=MessageBox.TYPE_INFO, timeout=5)
								return True
							else:
								del self.InfoBarInstance.session.pip
								self.InfoBarInstance.session.pipshown = False
 					if self.checkingTimeshiftRunning():
						if self.ts_dialog is None:
							self.openChoiceActionBeforeZap()
					else:
						self.log(11, "zapping")
						if notify:
							Notifications.AddPopup(text=_("Zapped to timer service %s!") % self.service_ref.getServiceName(), type=MessageBox.TYPE_INFO, timeout=5)

# If the user is looking at a MovieList then we need to update this
# lastservice, so that we get back to the updated one when closing the
# list.
#
						if self.InfoBarInstance:
							self.InfoBarInstance.lastservice = self.service_ref.ref

# If there is a MoviePlayer active it will set things back to the
# original channel after it finishes (which will be after we run) unless
# we update the lastservice entry.
#
						from Screens.InfoBar import MoviePlayer
						if MoviePlayer.instance is not None:
							MoviePlayer.instance.lastservice = self.service_ref.ref
# Shut it down if it's actually running...
# ...uses one of the more weirdly named functions, it actually
# functions as setMoviePlayerInactive
#
							if MoviePlayer.instance.execing:
								print "[RecordTimer] Shutting down MoviePlayer"
								NavigationInstance.instance.isMovieplayerActive()

						self._bouquet_search()
				return True
			else:
				record_res = self.record_service.start()
				self.setRecordingPreferredTuner(setdefault=True)
				if record_res:
					self.log(13, "start recording error: %d" % record_res)
					self.do_backoff()
					# retry
					self.begin = time() + self.backoff
					return False
				self.log_tuner(11, "start")
				return True

		elif next_state == self.StateEnded or next_state == self.StateFailed:
			old_end = self.end
			self.ts_dialog = None
			if self.setAutoincreaseEnd():
				self.log(12, "autoincrease recording %d minute(s)" % int((self.end - old_end)/60))
				self.state -= 1
				return True
			self.log_tuner(12, "stop")
			RecordingsState(-1)
			if not self.justplay:
				if self.record_service:
					NavigationInstance.instance.stopRecordService(self.record_service)
					self.record_service = None

			NavigationInstance.instance.RecordTimer.saveTimer()

# From here on we are checking whether to put the box into Standby or
# Deep Standby.
# Don't even *bother* checking this if a playback is in progress or an
# IPTV channel is active (unless we are in Standby - in which case it
# isn't really in playback or active)
# ....just say the timer has been handled.
# Trying to back off isn't worth it as backing off in Record timers
# currently only refers to *starting* a recording.
#
# But first, if this is just a zap timer there is no more to do!!!
# This prevents a daft "go to standby?" prompt if a Zap timer wakes the
# box up from standby.
			if self.justplay:
				return True
			from Components.Converter.ClientsStreaming import ClientsStreaming;
			if (not Screens.Standby.inStandby and NavigationInstance.instance.getCurrentlyPlayingServiceReference() and
				('0:0:0:0:0:0:0:0:0' in NavigationInstance.instance.getCurrentlyPlayingServiceReference().toString() or
				 '4097:' in NavigationInstance.instance.getCurrentlyPlayingServiceReference().toString())
			    ):
				return True

			if self.afterEvent == AFTEREVENT.STANDBY or (not wasRecTimerWakeup and self.autostate and self.afterEvent == AFTEREVENT.AUTO) or self.wasInStandby:
				self.keypress() #this unbinds the keypress detection
				if not Screens.Standby.inStandby: # not already in standby
					Notifications.AddNotificationWithCallback(self.sendStandbyNotification, MessageBox, _("A finished record timer wants to set your\n%s %s to standby. Do that now?") % (getMachineBrand(), getMachineName()), timeout = 180)
			elif self.afterEvent == AFTEREVENT.DEEPSTANDBY or (wasRecTimerWakeup and self.afterEvent == AFTEREVENT.AUTO and Screens.Standby.inStandby):
				if (abs(NavigationInstance.instance.RecordTimer.getNextRecordingTime() - time()) <= 900 or abs(NavigationInstance.instance.RecordTimer.getNextZapTime() - time()) <= 900) or NavigationInstance.instance.RecordTimer.getStillRecording():
					print '[RecordTimer] Recording or Recording due is next 15 mins, not return to deepstandby'
					return True

# Also check for someone streaming remotely - in which case we don't
# want DEEPSTANDBY.
# Might consider going to standby instead, but probably not worth it...
# Also might want to back off - but that is set-up for trying to start
# recordings, so has a low maximum delay.
#
				from Components.Converter.ClientsStreaming import ClientsStreaming;
				if int(ClientsStreaming("NUMBER").getText()) > 0:
					if not Screens.Standby.inStandby: # not already in standby
						Notifications.AddNotificationWithCallback(self.sendStandbyNotification, MessageBox,
							 _("A finished record timer wants to set your\n%s %s to standby. Do that now?") % (getMachineBrand(), getMachineName())
							 + _("\n(DeepStandby request changed to Standby owing to there being streaming clients.)"), timeout = 180)
					return True
#
				if not Screens.Standby.inTryQuitMainloop: # not a shutdown messagebox is open
					if Screens.Standby.inStandby: # in standby
						quitMainloop(1)
					else:
						Notifications.AddNotificationWithCallback(self.sendTryQuitMainloopNotification, MessageBox, _("A finished record timer wants to shut down\nyour %s %s. Shutdown now?") % (getMachineBrand(), getMachineName()), timeout = 180)
			return True

	def keypress(self, key=None, flag=1):
		if flag and self.wasInStandby:
			self.wasInStandby = False
			eActionMap.getInstance().unbindAction('', self.keypress)

	def setAutoincreaseEnd(self, entry = None):
		if not self.autoincrease:
			return False
		if entry is None:
			new_end =  int(time()) + self.autoincreasetime
		else:
			new_end = entry.begin -30

		dummyentry = RecordTimerEntry(self.service_ref, self.begin, new_end, self.name, self.description, self.eit, disabled=True, justplay = self.justplay, afterEvent = self.afterEvent, dirname = self.dirname, tags = self.tags)
		dummyentry.disabled = self.disabled
		timersanitycheck = TimerSanityCheck(NavigationInstance.instance.RecordTimer.timer_list, dummyentry)
		if not timersanitycheck.check():
			simulTimerList = timersanitycheck.getSimulTimerList()
			if simulTimerList is not None and len(simulTimerList) > 1:
				new_end = simulTimerList[1].begin
				new_end -= 30				# 30 Sekunden Prepare-Zeit lassen
		if new_end <= time():
			return False
		self.end = new_end
		return True

	def setRecordingPreferredTuner(self, setdefault=False):
		if self.needChangePriorityFrontend:
			elem = None
			if not self.change_frontend and not setdefault:
				elem = (self.setAdvancedPriorityFrontend is not None and self.setAdvancedPriorityFrontend) or config.usage.recording_frontend_priority.value
				self.change_frontend = True
			elif self.change_frontend and setdefault:
				elem = config.usage.frontend_priority.value
				self.change_frontend = False
				self.setAdvancedPriorityFrontend = None
			if elem is not None:
				setPreferredTuner(int(elem))

	def checkingTimeshiftRunning(self):
		return config.usage.check_timeshift.value and self.InfoBarInstance and self.InfoBarInstance.timeshiftEnabled() and self.InfoBarInstance.isSeekable()

	def openChoiceActionBeforeZap(self):
		if self.ts_dialog is None:
			type = _("record")
			if self.justplay:
				type = _("zap")
			elif self.always_zap:
				type = _("zap and record")
			message = _("You must switch to the service %s (%s - '%s')!\n") % (type, self.service_ref.getServiceName(), self.name)
			if self.repeated:
				message += _("Attention, this is repeated timer!\n")
			message += _("Timeshift is running. Select an action.\n")
			choice = [(_("Zap"), "zap"), (_("Don't zap and disable timer"), "disable"), (_("Don't zap and remove timer"), "remove")]
			if not self.InfoBarInstance.save_timeshift_file:
				choice.insert(0, (_("Save timeshift and zap"), "save"))
			else:
				message += _("Reminder, you have chosen to save timeshift file.")
			#if self.justplay or self.always_zap:
			#	choice.insert(2, (_("Don't zap"), "continue"))
			choice.insert(2, (_("Don't zap"), "continue"))
			def zapAction(choice):
				start_zap = True
				if choice:
					if choice in ("zap", "save"):
						self.log(8, "zap to recording service")
						if choice == "save":
							ts = self.InfoBarInstance.getTimeshift()
							if ts and ts.isTimeshiftEnabled():
								del ts
								self.InfoBarInstance.save_timeshift_file = True
								self.InfoBarInstance.SaveTimeshift()
					elif choice == "disable":
						self.disable()
						NavigationInstance.instance.RecordTimer.timeChanged(self)
						start_zap = False
						self.log(8, "zap canceled by the user, timer disabled")
					elif choice == "remove":
						start_zap = False
						self.afterEvent = AFTEREVENT.NONE
						NavigationInstance.instance.RecordTimer.removeEntry(self)
						self.log(8, "zap canceled by the user, timer removed")
					elif choice == "continue":
						if self.justplay:
							self.end = self.begin
						start_zap = False
						self.log(8, "zap canceled by the user")
				if start_zap:
					if not self.justplay:
						self.setRecordingPreferredTuner()
						self.failureCB(True)
					else:
						self.log(8, "zapping")
						NavigationInstance.instance.playService(self.service_ref.ref)
			self.ts_dialog = self.InfoBarInstance.session.openWithCallback(zapAction, MessageBox, message, simple=True, list=choice, timeout=20)

	def sendStandbyNotification(self, answer):
		if answer:
			Notifications.AddNotification(Screens.Standby.Standby)

	def sendTryQuitMainloopNotification(self, answer):
		if answer:
			Notifications.AddNotification(Screens.Standby.TryQuitMainloop, 1)
		else:
			global wasRecTimerWakeup
			wasRecTimerWakeup = False

	def getNextActivation(self):
		self.isStillRecording = False
		if self.state == self.StateEnded or self.state == self.StateFailed:
			if self.end > time():
				self.isStillRecording = True
			return self.end
		next_state = self.state + 1
		if next_state == self.StateEnded or next_state == self.StateFailed:
			if self.end > time():
				self.isStillRecording = True
		return {self.StatePrepared: self.start_prepare,
				self.StateRunning: self.begin,
				self.StateEnded: self.end}[next_state]

	def failureCB(self, answer):
		if answer:
			self.log(13, "ok, zapped away")
			#NavigationInstance.instance.stopUserServices()
			self._bouquet_search()
			if not self.first_try_prepare and self.InfoBarInstance and hasattr(self.InfoBarInstance.session, 'pipshown') and self.InfoBarInstance.session.pipshown:
				hasattr(self.InfoBarInstance, "showPiP") and self.InfoBarInstance.showPiP()
				if hasattr(self.InfoBarInstance.session, 'pip'):
					del self.InfoBarInstance.session.pip
					self.InfoBarInstance.session.pipshown = False
		else:
			self.log(14, "user didn't want to zap away, record will probably fail")

	def timeChanged(self):
		old_prepare = self.start_prepare
		self.start_prepare = self.begin - self.prepare_time
		self.backoff = 0

		if int(old_prepare) > 60 and int(old_prepare) != int(self.start_prepare):
			self.log(15, "record time changed, start prepare is now: %s" % ctime(self.start_prepare))

	def gotRecordEvent(self, record, event):
		# TODO: this is not working (never true), please fix. (comparing two swig wrapped ePtrs)
		if self.__record_service.__deref__() != record.__deref__():
			return
		# self.log(16, "record event %d" % event)
		if event == iRecordableService.evRecordWriteError:
			print "[RecordTimer] WRITE ERROR on recording, disk full?"
			# show notification. the 'id' will make sure that it will be
			# displayed only once, even if more timers are failing at the
			# same time. (which is very likely in case of disk fullness)
			Notifications.AddPopup(text = _("Write error while recording. Disk full?\n"), type = MessageBox.TYPE_ERROR, timeout = 0, id = "DiskFullMessage")
			# ok, the recording has been stopped. we need to properly note
			# that in our state, with also keeping the possibility to re-try.
			# TODO: this has to be done.
		elif event == iRecordableService.evStart:
			RecordingsState(1)
			text = _("A recording has been started:\n%s") % self.name
			notify = config.usage.show_message_when_recording_starts.value and not Screens.Standby.inStandby and self.InfoBarInstance and self.InfoBarInstance.execing
			if self.dirnameHadToFallback:
				text = '\n'.join((text, _("Please note that the previously selected media could not be accessed and therefore the default directory is being used instead.")))
				notify = True
			if notify:
				Notifications.AddPopup(text = text, type = MessageBox.TYPE_INFO, timeout = 3)
		elif event == iRecordableService.evRecordAborted:
			NavigationInstance.instance.RecordTimer.removeEntry(self)
		elif event == iRecordableService.evGstRecordEnded:
			if self.repeated:
				self.processRepeated(findRunningEvent = False)
			NavigationInstance.instance.RecordTimer.doActivate(self)

	# we have record_service as property to automatically subscribe to record service events
	def setRecordService(self, service):
		if self.__record_service is not None:
#			print "[RecordTimer][remove callback]"
			NavigationInstance.instance.record_event.remove(self.gotRecordEvent)

		self.__record_service = service

		if self.__record_service is not None:
#			print "[RecordTimer][add callback]"
			NavigationInstance.instance.record_event.append(self.gotRecordEvent)

	record_service = property(lambda self: self.__record_service, setRecordService)

def createTimer(xml):
	begin = int(xml.get("begin"))
	end = int(xml.get("end"))
	serviceref = ServiceReference(xml.get("serviceref").encode("utf-8"))
	description = xml.get("description").encode("utf-8")
	repeated = xml.get("repeated").encode("utf-8")
	rename_repeat = long(xml.get("rename_repeat") or "1")
	disabled = long(xml.get("disabled") or "0")
	justplay = long(xml.get("justplay") or "0")
	always_zap = long(xml.get("always_zap") or "0")
	pipzap = long(xml.get("pipzap") or "0")
	conflict_detection = long(xml.get("conflict_detection") or "1")
	afterevent = str(xml.get("afterevent") or "nothing")
	afterevent = {
		"nothing": AFTEREVENT.NONE,
		"standby": AFTEREVENT.STANDBY,
		"deepstandby": AFTEREVENT.DEEPSTANDBY,
		"auto": AFTEREVENT.AUTO
		}[afterevent]
	eit = xml.get("eit")
	if eit and eit != "None":
		eit = long(eit)
	else:
		eit = None
	location = xml.get("location")
	if location and location != "None":
		location = location.encode("utf-8")
	else:
		location = None
	tags = xml.get("tags")
	if tags and tags != "None":
		tags = tags.encode("utf-8").split(' ')
	else:
		tags = None
	descramble = int(xml.get("descramble") or "1")
	record_ecm = int(xml.get("record_ecm") or "0")
	isAutoTimer = int(xml.get("isAutoTimer") or "0")

	name = xml.get("name").encode("utf-8")
	#filename = xml.get("filename").encode("utf-8")
	entry = RecordTimerEntry(serviceref, begin, end, name, description, eit, disabled, justplay, afterevent, dirname = location, tags = tags, descramble = descramble, record_ecm = record_ecm, isAutoTimer = isAutoTimer, always_zap = always_zap, rename_repeat = rename_repeat, conflict_detection = conflict_detection, pipzap = pipzap)
	entry.repeated = int(repeated)
	flags = xml.get("flags")
	if flags:
		entry.flags = set(flags.encode("utf-8").split(' '))

	for l in xml.findall("log"):
		time = int(l.get("time"))
		code = int(l.get("code"))
		msg = l.text.strip().encode("utf-8")
		entry.log_entries.append((time, code, msg))

	return entry

class RecordTimer(timer.Timer):
	def __init__(self):
		timer.Timer.__init__(self)

		self.Filename = Directories.resolveFilename(Directories.SCOPE_CONFIG, "timers.xml")

		try:
			self.loadTimer()
		except IOError:
			print "[RecordTimer] unable to load timers from file!"

	def doActivate(self, w):
		# when activating a timer which has already passed,
		# simply abort the timer. don't run trough all the stages.
		if w.shouldSkip():
			w.state = RecordTimerEntry.StateEnded
		else:
			# when active returns true, this means "accepted".
			# otherwise, the current state is kept.
			# the timer entry itself will fix up the delay then.
			if w.activate():
				w.state += 1

		try:
			self.timer_list.remove(w)
		except:
			print '[RecordTimer] Remove list failed'

		# did this timer reached the last state?
		if w.state < RecordTimerEntry.StateEnded:
			# no, sort it into active list
			insort(self.timer_list, w)
		else:
			# yes. Process repeated, and re-add.
			if w.repeated:
				w.processRepeated()
				w.state = RecordTimerEntry.StateWaiting
				w.first_try_prepare = True
				self.addTimerEntry(w)
			else:
				# correct wrong running timers
				self.checkWrongRunningTimers()
				# check for disabled timers, if time as passed set to completed
				self.cleanupDisabled()
				# Remove old timers as set in config
				self.cleanupDaily(config.recording.keep_timers.value)
				# If we want to keep done timers, re-insert in the active list
				if config.recording.keep_timers.value > 0:
					insort(self.processed_timers, w)

		self.stateChanged(w)

	def isRecTimerWakeup(self):
		return wasRecTimerWakeup

	def checkWrongRunningTimers(self):
		now = time() + 100
		if int(now) > 1072224000:
			wrong_timers = [entry for entry in (self.processed_timers + self.timer_list) if entry.state in (1, 2) and entry.begin > now]
			for timer in wrong_timers:
				timer.state = RecordTimerEntry.StateWaiting
				self.timeChanged(timer)

 	def isRecording(self):
		for timer in self.timer_list:
			if timer.isRunning() and not timer.justplay:
				return True
		return False

# justLoad is passed on to record()
#
	def loadTimer(self, justLoad=False):
		try:
			file = open(self.Filename, 'r')
			doc = xml.etree.cElementTree.parse(file)
			file.close()
		except SyntaxError:
			from Tools.Notifications import AddPopup
			from Screens.MessageBox import MessageBox

			AddPopup(_("The timer file (timers.xml) is corrupt and could not be loaded."), type = MessageBox.TYPE_ERROR, timeout = 0, id = "TimerLoadFailed")

			print "[RecordTimer] timers.xml failed to load!"
			try:
				os.rename(self.Filename, self.Filename + "_old")
			except (IOError, OSError):
				print "[RecordTimer] renaming broken timer failed"
			return
		except IOError:
			print "[RecordTimer] timers.xml not found!"
			return

		root = doc.getroot()

		# put out a message when at least one timer overlaps
		checkit = False
		timer_text = ""
		for timer in root.findall("timer"):
			newTimer = createTimer(timer)
			conflict_list = self.record(newTimer, ignoreTSC=True, dosave=False, loadtimer=True, justLoad=justLoad)
			if conflict_list:
				checkit = True
				if newTimer in conflict_list:
					timer_text += _("\nTimer '%s' disabled!") % newTimer.name
		if checkit:
			from Tools.Notifications import AddPopup
			from Screens.MessageBox import MessageBox
			AddPopup(_("Timer overlap in timers.xml detected!\nPlease recheck it!") + timer_text, type = MessageBox.TYPE_ERROR, timeout = 0, id = "TimerLoadFailed")

	def saveTimer(self):
		list = ['<?xml version="1.0" ?>\n', '<timers>\n']

		for timer in self.timer_list + self.processed_timers:
			if timer.dontSave:
				continue
			list.append('<timer')
			list.append(' begin="' + str(int(timer.begin)) + '"')
			list.append(' end="' + str(int(timer.end)) + '"')
			list.append(' serviceref="' + stringToXML(str(timer.service_ref)) + '"')
			list.append(' repeated="' + str(int(timer.repeated)) + '"')
			list.append(' rename_repeat="' + str(int(timer.rename_repeat)) + '"')
			list.append(' name="' + str(stringToXML(timer.name)) + '"')
			list.append(' description="' + str(stringToXML(timer.description)) + '"')
			list.append(' afterevent="' + str(stringToXML({
				AFTEREVENT.NONE: "nothing",
				AFTEREVENT.STANDBY: "standby",
				AFTEREVENT.DEEPSTANDBY: "deepstandby",
				AFTEREVENT.AUTO: "auto"
				}[timer.afterEvent])) + '"')
			if timer.eit is not None:
				list.append(' eit="' + str(timer.eit) + '"')
			if timer.dirname:
				list.append(' location="' + str(stringToXML(timer.dirname)) + '"')
			if timer.tags:
				list.append(' tags="' + str(stringToXML(' '.join(timer.tags))) + '"')
			if timer.disabled:
				list.append(' disabled="' + str(int(timer.disabled)) + '"')
			list.append(' justplay="' + str(int(timer.justplay)) + '"')
			list.append(' always_zap="' + str(int(timer.always_zap)) + '"')
			list.append(' pipzap="' + str(int(timer.pipzap)) + '"')
			list.append(' conflict_detection="' + str(int(timer.conflict_detection)) + '"')
			list.append(' descramble="' + str(int(timer.descramble)) + '"')
			list.append(' record_ecm="' + str(int(timer.record_ecm)) + '"')
			list.append(' isAutoTimer="' + str(int(timer.isAutoTimer)) + '"')
			if timer.flags:
				list.append(' flags="' + ' '.join([stringToXML(x) for x in timer.flags]) + '"')
			list.append('>\n')

#		Handle repeat entries, which never end and so never get pruned by cleanupDaily
#       Repeating timers get, e.g., repeated="127" (dow bitmap)

			ignore_before = 0
			if config.recording.keep_timers.value > 0:
				if int(timer.repeated) > 0:
					ignore_before = time() - config.recording.keep_timers.value*86400

			for log_time, code, msg in timer.log_entries:
				if log_time < ignore_before:
					continue
				list.append('<log')
				list.append(' code="' + str(code) + '"')
				list.append(' time="' + str(log_time) + '"')
				list.append('>')
				list.append(str(stringToXML(msg)))
				list.append('</log>\n')

			list.append('</timer>\n')

		list.append('</timers>\n')

# We have to run this section with a lock.
#  Imagine setting a timer manually while the (background) AutoTimer
#  scan is also setting a timer.
#  So we have two timers being set at "the same time".
# Two process arrive at the open().
# First opens it and writes to *.writing.
# Second opens it and overwrites (possibly slightly different data) to
# the same file.
# First then gets to the rename - succeeds
# Second then tries to rename, but the "*.writing" file is now absent.
# Result:
#  OSError: [Errno 2] No such file or directory
#
# NOTE that as Python threads are not concurrent (they run serially and
# switch when one does something like I/O) we don't need to run the
# list-creating loop under the lock.
#
		with write_lock:
			file = open(self.Filename + ".writing", "w")
			for x in list:
				file.write(x)
			file.flush()

			os.fsync(file.fileno())
			file.close()
			os.rename(self.Filename + ".writing", self.Filename)

	def getNextZapTime(self):
		now = time()
		for timer in self.timer_list:
			if not timer.justplay or timer.begin < now:
				continue
			return timer.begin
		return -1

	def getStillRecording(self):
		isStillRecording = False
		now = time()
		for timer in self.timer_list:
			if timer.isStillRecording:
				isStillRecording = True
				break
			elif abs(timer.begin - now) <= 10:
				isStillRecording = True
				break
		return isStillRecording

	def getNextRecordingTimeOld(self):
		now = time()
		for timer in self.timer_list:
			next_act = timer.getNextActivation()
			if timer.justplay or next_act < now:
				continue
			return next_act
		return -1

	def getNextRecordingTime(self):
		nextrectime = self.getNextRecordingTimeOld()
		faketime = time()+300

		if config.timeshift.isRecording.value:
			if 0 < nextrectime < faketime:
				return nextrectime
			else:
				return faketime
		else:
			return nextrectime

	def isNextRecordAfterEventActionAuto(self):
		for timer in self.timer_list:
			if timer.justplay:
				continue
			if timer.afterEvent == AFTEREVENT.AUTO or timer.afterEvent == AFTEREVENT.DEEPSTANDBY:
				return True
		return False

# If justLoad is True then we (temporarily) turn off conflict detection
# as we load.  On a restore we may not have the correct tuner
# configuration (and no USB tuners)...
#
	def record(self, entry, ignoreTSC=False, dosave=True, loadtimer=False, justLoad=False):
		real_cd = entry.conflict_detection
		if justLoad:
			entry.conflict_detection = False
		check_timer_list = self.timer_list[:]
		timersanitycheck = TimerSanityCheck(check_timer_list, entry)
		answer = None
		if not timersanitycheck.check():
			if not ignoreTSC:
				print "[RecordTimer] timer conflict detected!"
				print timersanitycheck.getSimulTimerList()
				return timersanitycheck.getSimulTimerList()
			else:
				print "[RecordTimer] ignore timer conflict..."
				if not dosave and loadtimer:
					simulTimerList = timersanitycheck.getSimulTimerList()
					if entry in simulTimerList:
						entry.disabled = True
						if entry in check_timer_list:
							check_timer_list.remove(entry)
					answer = simulTimerList
		elif timersanitycheck.doubleCheck():
			print "[RecordTimer] ignore double timer..."
			return None
		elif not loadtimer and not entry.disabled and not entry.justplay and not (entry.service_ref and '%3a//' in entry.service_ref.ref.toString()):
			for x in check_timer_list:
				if x.begin == entry.begin and not x.disabled and not x.justplay and not (x.service_ref and '%3a//' in x.service_ref.ref.toString()):
					entry.begin += 1
		entry.conflict_detection = real_cd
		entry.timeChanged()
		print "[Timer] Record " + str(entry)
		entry.Timer = self
		self.addTimerEntry(entry)
		if dosave:
			self.saveTimer()
		return answer

	@staticmethod
	def __checkTimer(x, check_offset_time, begin, end, duration):
		timer_end = x.end
		timer_begin = x.begin
		if not x.repeated and check_offset_time:
			if 0 < end - timer_end <= 59:
				timer_end = end
			elif 0 < timer_begin - begin <= 59:
				timer_begin = begin
		if x.justplay and (timer_end - x.begin) <= 1:
			timer_end += 60

		if x.repeated == 0:
			if begin < timer_begin <= end:
				# recording within / last part of event
				return 2 if timer_end < end else 0
			elif timer_begin <= begin <= timer_end:
				if timer_end < end:
					# recording first part of event
					return 3 if x.justplay else 1
				else: # recording whole event
					return 3
		else:
			bt = localtime(begin)
			bday = bt.tm_wday
			begin2 = 1440 + bt.tm_hour * 60 + bt.tm_min
			end2 = begin2 + duration / 60
			xbt = localtime(x.begin)
			xet = localtime(timer_end)
			offset_day = False
			checking_time = x.begin < begin or begin <= x.begin <= end
			if xbt.tm_yday != xet.tm_yday:
				oday = bday - 1
				if oday == -1: oday = 6
				offset_day = x.repeated & (1 << oday)
			xbegin = 1440 + xbt.tm_hour * 60 + xbt.tm_min
			xend = xbegin + ((timer_end - x.begin) / 60)
			if xend < xbegin:
				xend += 1440
			if x.repeated & (1 << bday) and checking_time:
				if begin2 < xbegin <= end2:
					# recording within / last part of event
					return 2 if xend < end2 else 0
				elif xbegin <= begin2 <= xend:
					# recording first part / whole event
					return 1 if xend < end2 else 3
				elif offset_day:
					xbegin -= 1440
					xend -= 1440
					if begin2 < xbegin <= end2:
						# recording within / last part of event
						return 2 if xend < end2 else 0
					elif xbegin <= begin2 <= xend:
						# recording first part / whole event
						return 1 if xend < end2 else 3
			elif offset_day and checking_time:
				xbegin -= 1440
				xend -= 1440
				if begin2 < xbegin <= end2:
					# recording within / last part of event
					return 2 if xend < end2 else 0
				elif xbegin <= begin2 <= xend:
					# recording first part / whole event
					return 1 if xend < end2 else 3
		return None

	# matchType values can be:
	# 0 last part of event
	# 1 first part of event
	# 2 within event
	# 3 exact event match
	def isInTimer(self, service, begin, duration):
		returnValue = None
		check_offset_time = not config.recording.margin_before.value and not config.recording.margin_after.value
		end = begin + duration
		startAt = begin - config.recording.margin_before.value * 60
		bailAt = end + config.recording.margin_after.value * 60
		if isinstance(service, ServiceReference):
			refstr = service.ref.toCompareString()
		else:
			refstr = ':'.join(service.split(':')[:11])

		# iterating is faster than using bisect+indexing to find the first relevant timer
		for timer in self.timer_list:
			if not timer.repeated and timer.end < startAt:
				# skip timers that aren't in the requested range
				# we need to try all repeat timers though
				continue
			if timer.begin > bailAt:
				# exit when we hit timers that are after the requested range
				break
			check = timer.service_ref.ref.toCompareString() == refstr
			if check:
				matchType = RecordTimer.__checkTimer(timer, check_offset_time, begin, end, duration)
				if matchType is not None:
					returnValue = (timer, matchType)
					if matchType in (2, 3): # When full recording or within an event do not look further
						break
		return returnValue or (None, None)

	@staticmethod
	def isInTimerOnService(serviceTimerList, begin, duration):
		returnValue = None
		check_offset_time = not config.recording.margin_before.value and not config.recording.margin_after.value
		end = begin + duration
	
		for timer in serviceTimerList:
			matchType = RecordTimer.__checkTimer(timer, check_offset_time, begin, end, duration)
			if matchType is not None:
				returnValue = (timer, matchType)
				if matchType in (2, 3): # When full recording or within an event do not look further
					break
		return returnValue or (None, None)

	def removeEntry(self, entry):
		print "[RecordTimer] Remove " + str(entry)

		# avoid re-enqueuing
		entry.repeated = False

		# abort timer.
		# this sets the end time to current time, so timer will be stopped.
		entry.autoincrease = False
		entry.abort()

		if entry.state != entry.StateEnded:
			self.timeChanged(entry)

		# print "[RecordTimer]state: ", entry.state
		# print "[RecordTimer]in processed: ", entry in self.processed_timers
		# print "[RecordTimer]in running: ", entry in self.timer_list
		# autoincrease instanttimer if possible
		if not entry.dontSave:
			for x in self.timer_list:
				if x.setAutoincreaseEnd():
					self.timeChanged(x)
		# now the timer should be in the processed_timers list. remove it from there.
		self.processed_timers.remove(entry)
		self.saveTimer()

	def shutdown(self):
		self.saveTimer()

	def cleanup(self):
		timer.Timer.cleanup(self)
		self.saveTimer()

	def cleanupDaily(self, days):
		timer.Timer.cleanupDaily(self, days)
		self.saveTimer()
