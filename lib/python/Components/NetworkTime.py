from Components.Console import Console
from Components.config import config
from enigma import eTimer, eDVBLocalTimeHandler, eEPGCache
from Tools.StbHardware import setRTCtime
from time import time

# _session = None
#


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

	def start(self):
		if self.timecheck not in self.timer.callback:
			self.timer.callback.append(self.timecheck)
			def useNTPminutesChanged(configElement):
				self.timer.stop()
				self.timecheck()
			config.misc.useNTPminutes.addNotifier(useNTPminutesChanged, initial_call=False, immediate_feedback=False)
		self.timer.startLongTimer(0)

	def stop(self):
		if self.timecheck in self.timer.callback:
			self.timer.callback.remove(self.timecheck)
		self.timer.stop()

	def timecheck(self):
		if config.misc.SyncTimeUsing.value == "ntp":
			print('[NetworkTime] Updating')
			self.Console.ePopen('/usr/bin/ntpdate-sync', self.update_schedule)
		else:
			self.update_schedule()

	def update_schedule(self, result=None, retval=None, extra_args=None):
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
