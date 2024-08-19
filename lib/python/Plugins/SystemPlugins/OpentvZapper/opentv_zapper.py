from Components.config import config, configfile
from Components.NimManager import nimmanager

from Screens.ChannelSelection import ChannelSelection
from Screens.MessageBox import MessageBox

from Tools import Notifications

# from this plugin
from .providers import providers

from enigma import eDVBDB, eServiceReference, eTimer, eDVBFrontendParametersSatellite, eDVBFrontendParameters

from time import localtime, time, strftime, mktime


# for pip
from Screens.PictureInPicture import PictureInPicture
from Components.SystemInfo import SystemInfo
from enigma import ePoint, eSize

debug_name = "opentv_zapper"
download_interval = config.plugins.opentvzapper.update_interval.value * 60 * 60  # 6 hours
download_duration = 3 * 60  # stay tuned for 3 minutes
start_first_download = 5 * 60  # 5 minutes after booting
wait_time_on_fail = 15 * 60  # 15 minutes


def getNimListForSat(orb_pos):
	return [nim.slot for nim in nimmanager.nim_slots if nim.isCompatible("DVB-S") and orb_pos in [sat[0] for sat in nimmanager.getSatListForNim(nim.slot)]]


def make_sref(service):
	return eServiceReference("1:0:%X:%X:%X:%X:%X:0:0:0:" % (
		service["service_type"],
		service["service_id"],
		service["transport_stream_id"],
		service["original_network_id"],
		service["namespace"]))


class DefaultAdapter:
	def __init__(self, session):
		self.navcore = session.nav
		self.previousService = None
		self.currentService = ""
		self.currentBouquet = None

	def play(self, service):
		self.currentBouquet = ChannelSelection.instance is not None and ChannelSelection.instance.getRoot()
		self.previousService = self.navcore.getCurrentlyPlayingServiceReference()
		self.navcore.playService(service)
		self.currentService = self.navcore.getCurrentlyPlayingServiceReference()
		return True

	def stop(self):
		if isinstance(self.currentService, eServiceReference) and isinstance(playingref := self.navcore and self.navcore.getCurrentlyPlayingServiceReference(), eServiceReference) and self.currentService == playingref:  # check the user hasn't zapped in the mean time
			if self.currentBouquet is not None:
				ChannelSelection.instance.setRoot(self.currentBouquet)
			self.navcore.playService(self.previousService)


class RecordAdapter:
	def __init__(self, session):
		self.__service = None
		self.navcore = session.nav

	def play(self, service):
		self.stop()
		self.__service = self.navcore.recordService(service)
		if self.__service is not None:
			self.__service.prepareStreaming()
			self.__service.start()
			return True
		return False

	def stop(self):
		if self.__service is not None:
			self.navcore.stopRecordService(self.__service)
			self.__service = None


class PipAdapter:
	def __init__(self, session, hide=True):
		self.hide = hide
		self.session = session

	def __hidePiP(self):
		# set pip size to 1 pixel
		x = y = 0
		w = 1
		self.session.pip.instance.move(ePoint(x, y))
		self.session.pip.instance.resize(eSize(w, y))
		self.session.pip["video"].instance.resize(eSize(w, y))

	def __initPiP(self):
		self.session.pip = self.session.instantiateDialog(PictureInPicture)
		self.session.pip.show()
		if self.hide:
			self.__hidePiP()
		self.session.pipshown = True  # Always pretends it's shown (since the ressources are present)
		newservice = self.session.nav.getCurrentlyPlayingServiceReference()
		if self.session.pip.playService(newservice):
			self.session.pip.servicePath = newservice.getPath()

	def play(self, service):
		self.__initPiP()

		if self.session.pip.playService(service):
			self.session.pip.servicePath = service.getPath()
			return True
		return False

	def stop(self):
		try:
			del self.session.pip
		except Exception:
			pass
		self.session.pipshown = False


class Opentv_Zapper():
	def __init__(self):
		self.session = None
		self.adapter = None
		self.downloading = False
		self.force = False
		self.initialized = False
		self.callback = None
		self.downloadtimer = eTimer()
		self.downloadtimer.callback.append(self.start_download)
		self.enddownloadtimer = eTimer()
		self.enddownloadtimer.callback.append(self.stop_download)
		print("[%s] starting..." % (debug_name))
		if config.plugins.opentvzapper.enabled.value and not config.plugins.opentvzapper.schedule.value:  # auto interval, not schedule
			print("[%s] first download scheduled for %s" % (debug_name, strftime("%c", localtime(int(time()) + start_first_download))))
			self.downloadtimer.startLongTimer(start_first_download)

	def checkAvailableTuners(self):
		provider = config.plugins.opentvzapper.providers.value
		self.transponder = providers[provider]["transponder"]
		self.tuners = getNimListForSat(self.transponder["orbital_position"])
		self.num_tuners = len(self.tuners)
		return bool(self.num_tuners)

	def setParams(self):
		params = eDVBFrontendParametersSatellite()
		params.frequency = self.transponder["frequency"]
		params.symbol_rate = self.transponder["symbol_rate"]
		params.polarisation = self.transponder["polarization"]
		params.fec = self.transponder["fec_inner"]
		params.inversion = eDVBFrontendParametersSatellite.Inversion_Unknown
		params.orbital_position = self.transponder["orbital_position"]
		params.system = self.transponder["system"]
		params.modulation = self.transponder["modulation"]
		params.rolloff = eDVBFrontendParametersSatellite.RollOff_auto
		params.pilot = eDVBFrontendParametersSatellite.Pilot_Unknown
		if hasattr(eDVBFrontendParametersSatellite, "No_Stream_Id_Filter"):
			params.is_id = eDVBFrontendParametersSatellite.No_Stream_Id_Filter
		if hasattr(eDVBFrontendParametersSatellite, "PLS_Gold"):
			params.pls_mode = eDVBFrontendParametersSatellite.PLS_Gold
		if hasattr(eDVBFrontendParametersSatellite, "PLS_Default_Gold_Code"):
			params.pls_code = eDVBFrontendParametersSatellite.PLS_Default_Gold_Code
		if hasattr(eDVBFrontendParametersSatellite, "No_T2MI_PLP_Id"):
			params.t2mi_plp_id = eDVBFrontendParametersSatellite.No_T2MI_PLP_Id
		if hasattr(eDVBFrontendParametersSatellite, "T2MI_Default_Pid"):
			params.t2mi_pid = eDVBFrontendParametersSatellite.T2MI_Default_Pid
		return params

	def initialize(self):
		provider = config.plugins.opentvzapper.providers.value
		if not self.checkAvailableTuners() or self.initialized == provider:  # if no tuner is available for this provider or we are already initialized, abort.
			return
		self.service = providers[provider]["service"]
		self.sref = make_sref(self.service)
		self.sref.setName(self.service["service_name"])
		self.sref.setProvider(self.service["service_provider"])
		params_fe = eDVBFrontendParameters()
		params_fe.setDVBS(self.setParams(), False)
		eDVBDB.getInstance().addChannelToDB(self.sref, params_fe, self.service["service_cachedpids"], self.service["service_capids"], self.service["flags"])
		self.initialized = provider
		print("[%s] initialize completed." % (debug_name))

	def config_changed(self, configElement=None):
		print("[%s] config_changed." % (debug_name))
		if config.plugins.opentvzapper.enabled.value and not config.plugins.opentvzapper.schedule.value:  # auto interval, not schedule
			self.start_download()
		else:
			print("[%s] auto download timer stopped." % (debug_name))
			self.downloadtimer.stop()

	def set_session(self, session):
		self.session = session

	def force_download(self, callback=None):
		if self.checkAvailableTuners():
			if callback:
				self.callback = callback
			print("[%s] forced download." % (debug_name))
			self.force = True
			self.start_download()
		else:
			print("[%s] no tuner configured for %s." % (debug_name, config.plugins.opentvzapper.providers.value))
			if callback:
				callback()

	def start_download(self):
		print("[%s] start_download." % (debug_name))
		self.downloadtimer.stop()  # stop any running timer. e.g. we could be coming from "force_download" or "config_changed".
		from Screens.Standby import inStandby

		# this is here so tuner setup is fresh for every download
		self.initialize()

		self.adaptername = ""
		if self.session and self.num_tuners and not self.downloading and not self.session.nav.RecordTimer.isRecording():
			self.adapter = None
			self.downloading = False
			currentlyPlayingNIM = self.getCurrentlyPlayingNIM()
			print("[%s]currentlyPlayingNIM" % (debug_name), currentlyPlayingNIM)
			print("[%s]available tuners" % (debug_name), self.tuners)
			if not inStandby and (self.num_tuners > 1 or self.tuners[0] != currentlyPlayingNIM):
				if SystemInfo.get("PIPAvailable", False) and config.plugins.opentvzapper.use_pip_adapter.value and not (hasattr(self.session, 'pipshown') and self.session.pipshown):
					self.adapter = PipAdapter(self.session)
					self.downloading = self.adapter.play(self.sref)
					self.adaptername = "Pip"
				else:
					self.adapter = RecordAdapter(self.session)
					self.downloading = self.adapter.play(self.sref)
					self.adaptername = "Record"
			if not self.downloading and (inStandby or self.force):
				self.adapter = DefaultAdapter(self.session)
				self.downloading = self.adapter.play(self.sref)
				self.adaptername = "Default"
		self.force = False
		if self.downloading:
			self.enddownloadtimer.startLongTimer(download_duration)
			print("[%s]download running..." % (debug_name))
			print("[%s] %s" % (debug_name, "using '%s' adapter" % self.adaptername if self.adaptername else "a download is already in progress"))
			if not inStandby and config.plugins.opentvzapper.notifications.value:
				Notifications.AddPopup(text=_("OpenTV EPG download starting."), type=MessageBox.TYPE_INFO, timeout=5, id=debug_name)
		else:
			self.downloadtimer.startLongTimer(wait_time_on_fail)  # download not possible at this time. Try again in 10 minutes
			print("[%s]download not currently possible... Will try again at %s" % (debug_name, strftime("%c", localtime(int(time()) + wait_time_on_fail))))

	def stop_download(self):
		from Screens.Standby import inStandby
		if self.adapter:
			self.adapter.stop()
			del self.adapter
		self.downloading = False
		self.adapter = None
		if not config.plugins.opentvzapper.schedule.value:  # auto interval, not schedule
			self.downloadtimer.startLongTimer(download_interval)
			next_download = strftime("%c", localtime(int(time()) + download_interval))
			print("[%s]download completed... Next download scheduled for %s" % (debug_name, next_download))
			if not inStandby and config.plugins.opentvzapper.notifications.value:
				Notifications.AddPopup(text=_("OpenTV EPG download completed.\nNext download: %s") % next_download, type=MessageBox.TYPE_INFO, timeout=5, id=debug_name)
		if callable(self.callback):
			self.callback()
		self.callback = None

	def getCurrentlyPlayingNIM(self):
		currentlyPlayingNIM = None
		currentService = self.session and self.session.nav.getCurrentService()
		frontendInfo = currentService and currentService.frontendInfo()
		frontendData = frontendInfo and frontendInfo.getAll(True)
		if frontendData is not None:
			currentlyPlayingNIM = frontendData.get("tuner_number", None)
		return currentlyPlayingNIM


opentv_zapper = Opentv_Zapper()


autoScheduleTimer = None


def startSession(reason, session=None, **kwargs):
	#
	# This gets called twice at start up,once by WHERE_AUTOSTART without session,
	# and once by WHERE_SESSIONSTART with session. WHERE_AUTOSTART is needed though
	# as it is used to wake from deep standby. We need to read from session so if
	# session is not set just return and wait for the second call to this function.
	#
	# Called with reason=1 during /sbin/shutdown.sysvinit, and with reason=0 at startup.
	# Called with reason=1 only happens when using WHERE_AUTOSTART.
	# If only using WHERE_SESSIONSTART there is no call to this function on shutdown.
	#
	schedulename = "OpentvZapper-Scheduler"

	print("[%s][Scheduleautostart] reason(%d), session" % (schedulename, reason), session)
	if reason == 0 and session is None:
		return
	global autoScheduleTimer
	global wasScheduleTimerWakeup
	wasScheduleTimerWakeup = False
	if reason == 0:
		opentv_zapper.set_session(session)  # pass session to opentv_zapper
		wasScheduleTimerWakeup = session.nav.pluginTimerWakeupName() == "OpentvZapperScheduler"
		if wasScheduleTimerWakeup:
			session.nav.clearPluginTimerWakeupName()
			# if box is not in standby do it now
			from Screens.Standby import Standby, inStandby
			if not inStandby:
				# hack alert: session requires "pipshown" to avoid a crash in standby.py
				if not hasattr(session, "pipshown"):
					session.pipshown = False
				from Tools import Notifications
				Notifications.AddNotificationWithID("Standby", Standby)
			print("[%s][Scheduleautostart] was schedule timer wake up" % schedulename)

		print("[%s][Scheduleautostart] AutoStart Enabled" % schedulename)
		if autoScheduleTimer is None:
			autoScheduleTimer = AutoScheduleTimer(session)
	else:
		print("[%s][Scheduleautostart] Stop" % schedulename)
		if autoScheduleTimer is not None:
			autoScheduleTimer.schedulestop()
		opentv_zapper.stop_download()


class AutoScheduleTimer:
	instance = None

	def __init__(self, session):
		self.schedulename = "OpentvZapper-Scheduler"
		self.config = config.plugins.opentvzapper
		self.itemtorun = opentv_zapper.force_download
		self.session = session
		self.scheduletimer = eTimer()
		self.scheduletimer.callback.append(self.ScheduleonTimer)
		self.scheduleactivityTimer = eTimer()
		self.scheduleactivityTimer.timeout.get().append(self.scheduledatedelay)
		self.ScheduleTime = 0
		now = int(time())
		if self.config.schedule.value:
			print("[%s][AutoScheduleTimer] Schedule Enabled at " % self.schedulename, strftime("%c", localtime(now)))
			if now > 1546300800:  # Tuesday, January 1, 2019 12:00:00 AM
				self.scheduledate()
			else:
				print("[%s][AutoScheduleTimer] STB clock not yet set." % self.schedulename)
				self.scheduleactivityTimer.start(36000)
		else:
			print("[%s][AutoScheduleTimer] Schedule Disabled at" % self.schedulename, strftime("%c", localtime(now)))
			self.scheduleactivityTimer.stop()

		assert AutoScheduleTimer.instance is None, "class AutoScheduleTimer is a singleton class and just one instance of this class is allowed!"
		AutoScheduleTimer.instance = self

	def __onClose(self):
		AutoScheduleTimer.instance = None

	def scheduledatedelay(self):
		self.scheduleactivityTimer.stop()
		self.scheduledate()

	def getScheduleTime(self):
		now = localtime(time())
		return int(mktime((now.tm_year, now.tm_mon, now.tm_mday, self.config.scheduletime.value[0], self.config.scheduletime.value[1], 0, now.tm_wday, now.tm_yday, now.tm_isdst)))

	def getScheduleDayOfWeek(self):
		today = self.getToday()
		for i in range(1, 8):
			if self.config.days[(today + i) % 7].value:
				return i

	def getToday(self):
		return localtime(time()).tm_wday

	def scheduledate(self, atLeast=0):
		self.scheduletimer.stop()
		self.ScheduleTime = self.getScheduleTime()
		now = int(time())
		if self.ScheduleTime > 0:
			if self.ScheduleTime < now + atLeast:
				self.ScheduleTime += 86400 * self.getScheduleDayOfWeek()
			elif not self.config.days[self.getToday()].value:
				self.ScheduleTime += 86400 * self.getScheduleDayOfWeek()
			next = self.ScheduleTime - now
			self.scheduletimer.startLongTimer(next)
		else:
			self.ScheduleTime = -1
		print("[%s][scheduledate] Time set to" % self.schedulename, strftime("%c", localtime(self.ScheduleTime)), strftime("(now=%c)", localtime(now)))
		self.config.nextscheduletime.value = self.ScheduleTime
		self.config.nextscheduletime.save()
		configfile.save()
		return self.ScheduleTime

	def schedulestop(self):
		self.scheduletimer.stop()

	def ScheduleonTimer(self):
		self.scheduletimer.stop()
		now = int(time())
		wake = self.getScheduleTime()
		atLeast = 0
		if wake - now < 60:
			atLeast = 60
			print("[%s][ScheduleonTimer] onTimer occured at" % self.schedulename, strftime("%c", localtime(now)))
			from Screens.Standby import inStandby
			if not inStandby:
				message = _("%s update is about to start.\nDo you want to allow this?") % self.schedulename
				ybox = self.session.openWithCallback(self.doSchedule, MessageBox, message, MessageBox.TYPE_YESNO, timeout=30)
				ybox.setTitle(_('%s scheduled update') % self.schedulename)
			else:
				self.doSchedule(True)
		self.scheduledate(atLeast)

	def doSchedule(self, answer):
		now = int(time())
		if answer is False:
			if self.config.retrycount.value < 2:
				print("[%s][doSchedule] Schedule delayed." % self.schedulename)
				self.config.retrycount.value += 1
				self.ScheduleTime = now + (int(self.config.retry.value) * 60)
				print("[%s][doSchedule] Time now set to" % self.schedulename, strftime("%c", localtime(self.ScheduleTime)), strftime("(now=%c)", localtime(now)))
				self.scheduletimer.startLongTimer(int(self.config.retry.value) * 60)
			else:
				atLeast = 60
				print("[%s][doSchedule] Enough Retries, delaying till next schedule." % self.schedulename, strftime("%c", localtime(now)))
				self.session.open(MessageBox, _("Enough Retries, delaying till next schedule."), MessageBox.TYPE_INFO, timeout=10)
				self.config.retrycount.value = 0
				self.scheduledate(atLeast)
		else:
			self.timer = eTimer()
			self.timer.callback.append(self.runscheduleditem)
			print("[%s][doSchedule] Running Schedule" % self.schedulename, strftime("%c", localtime(now)))
			self.timer.start(100, 1)

	def runscheduleditem(self):
		self.itemtorun(self.runscheduleditemCallback)

	def runscheduleditemCallback(self):
		global wasScheduleTimerWakeup
		from Screens.Standby import inStandby, TryQuitMainloop, inTryQuitMainloop
		print("[%s][runscheduleditemCallback] inStandby" % self.schedulename, inStandby)
		if wasScheduleTimerWakeup and inStandby and self.config.scheduleshutdown.value and not self.session.nav.getRecordings() and not inTryQuitMainloop:
			print("[%s] Returning to deep standby after scheduled wakeup" % self.schedulename)
			self.session.open(TryQuitMainloop, 1)
		wasScheduleTimerWakeup = False  # clear this as any subsequent run will not be from wake up from deep

	def doneConfiguring(self):  # called from plugin on save
		now = int(time())
		if self.config.schedule.value:
			if autoScheduleTimer is not None:
				print("[%s][doneConfiguring] Schedule Enabled at" % self.schedulename, strftime("%c", localtime(now)))
				autoScheduleTimer.scheduledate()
		else:
			if autoScheduleTimer is not None:
				self.ScheduleTime = 0
				print("[%s][doneConfiguring] Schedule Disabled at" % self.schedulename, strftime("%c", localtime(now)))
				autoScheduleTimer.schedulestop()
		# scheduletext is not used for anything but could be returned to the calling function to display in the GUI.
		if self.ScheduleTime > 0:
			t = localtime(self.ScheduleTime)
			scheduletext = strftime(_("%a %e %b  %-H:%M"), t)
		else:
			scheduletext = ""
		return scheduletext
