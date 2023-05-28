from Components.Console import Console
from Components.config import config
from enigma import eTimer, eDVBLocalTimeHandler, eEPGCache
from Tools.StbHardware import setRTCtime
from time import time
from os import chmod as oschmod

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
		self.ntpConfigUpdated() # update NTP url, create if not exists

	def stop(self):
		if self.timecheck in self.timer.callback:
			self.timer.callback.remove(self.timecheck)
		self.timer.stop()

	def timecheck(self):
		if config.misc.SyncTimeUsing.value == "ntp":
			print('[NetworkTime] Updating from NTP')
			# ntpd from BusyBox.
			# -n = Run in foreground
			# -q = Quit after clock is set
			# -p [keyno:NUM:]PEER... Obtain time from PEER (may be repeated)... Use key NUM for authentication... If -p is not given, 'server HOST' lines from /etc/ntp.conf are used.
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
		self.timer.stop() # stop current timer if this is an update from Time.py
		self.timer.startLongTimer(0)
