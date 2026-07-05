from Components.Console import Console
from Components.config import config
from enigma import eTimer, eDVBLocalTimeHandler, eEPGCache
from Tools.StbHardware import setRTCtime
from time import time
import Components.ClockRealtimeMonitor


def AutoNTPSync(session=None, **kwargs):
	global ntpsyncpoller
	ntpsyncpoller = NTPSyncPoller()
	ntpsyncpoller.start()


class NTPSyncPoller:
	"""Automatically Poll NTP"""

	def __init__(self):
		# Init Timer
		self.timer = eTimer()
		self.Console = Console()
		self.onTimeUpdated = []
		Components.ClockRealtimeMonitor.realtimeMonitor.addRealtimeChangedCallback(self._timeUpdated)

	def start(self):
		if self.timecheck not in self.timer.callback:
			self.timer.callback.append(self.timecheck)
		self.ntpConfigUpdated()  # update NTP url, create if not exists

	def stop(self):
		if self.timecheck in self.timer.callback:
			self.timer.callback.remove(self.timecheck)
		self.timer.stop()

	def timecheck(self):
		if config.misc.SyncTimeUsing.value == "ntp":
			print('[NetworkTime] Updating from NTP')
			self.Console.ePopen(["/usr/sbin/ntpd", "/usr/sbin/ntpd", "-nq", "-p", config.misc.NTPserver.value], self.update_schedule)
		else:
			self.update_schedule()

	def update_schedule(self, result=None, retval=None, extra_args=None):
		if retval and result:
			print("[NetworkTime] Error %d: Unable to synchronize the time!\n%s" % (retval, result.strip()))
		nowTime = time()
		if nowTime > 10000:
			print('[NetworkTime] setting E2 time:', nowTime)
			setRTCtime(nowTime)
			eDVBLocalTimeHandler.getInstance().setUseDVBTime(config.misc.SyncTimeUsing.value == "dvb")
			eEPGCache.getInstance().timeUpdated()
			self.timer.startLongTimer(int(config.misc.useNTPminutes.value if config.misc.SyncTimeUsing.value == "ntp" else config.misc.useNTPminutes.default) * 60)
		else:
			print('[NetworkTime] NO TIME SET')
			self.timer.startLongTimer(10)

	def ntpConfigUpdated(self):
		self.timer.stop()  # stop current timer if this is an update from Time.py
		self.timer.startLongTimer(0)

	def _timeUpdated(self):
		print("[NetworkTime] system clock was stepped")
		for f in self.onTimeUpdated:
			if callable(f):
				f()

	def addTimeUpdatedCallback(self, f):
		if f not in self.onTimeUpdated:
			self.onTimeUpdated.append(f)

	def removeTimeUpdatedCallback(self, f):
		if f in self.onTimeUpdated:
			self.onTimeUpdated.remove(f)

	def __del__(self):
		try:
			Components.ClockRealtimeMonitor.realtimeMonitor.removeRealtimeChangedCallback(self._timeUpdated)
		except Exception:
			pass
