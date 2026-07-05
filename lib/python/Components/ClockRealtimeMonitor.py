import ctypes
import errno
import os
import select

from enigma import eSocketNotifier


realtimeMonitor = None


def InitRealtimeMonitor():
	global realtimeMonitor
	if realtimeMonitor is None:
		realtimeMonitor = ClockRealtimeMonitor()


class timespec(ctypes.Structure):
	_fields_ = [
		("tv_sec", ctypes.c_long),
		("tv_nsec", ctypes.c_long),
	]


class itimerspec(ctypes.Structure):
	_fields_ = [
		("it_interval", timespec),
		("it_value", timespec),
	]


class ClockRealtimeMonitor:
	"""Calls back whenever CLOCK_REALTIME is stepped (settimeofday/clock_settime).
	Slew-only adjustments (adjtime/adjtimex, e.g. small NTP corrections) do not
	trigger this, by kernel design -- only discontinuous jumps do.

	Call close() explicitly when done. Relying on __del__ works too, but the
	callback list holds a reference back to self, so without close() the
	fd/notifier only get released whenever Python's cyclic gc next runs, not
	the moment the last external reference is dropped."""

	CLOCK_REALTIME = 0

	TFD_TIMER_ABSTIME = 1
	TFD_TIMER_CANCEL_ON_SET = 2

	def __init__(self):
		self._libc = ctypes.CDLL("libc.so.6", use_errno=True)

		self._libc.timerfd_create.argtypes = [ctypes.c_int, ctypes.c_int]
		self._libc.timerfd_create.restype = ctypes.c_int

		self._libc.timerfd_settime.argtypes = [
			ctypes.c_int,
			ctypes.c_int,
			ctypes.POINTER(itimerspec),
			ctypes.c_void_p,
		]
		self._libc.timerfd_settime.restype = ctypes.c_int

		self.fd = self._libc.timerfd_create(self.CLOCK_REALTIME, 0)
		if self.fd < 0:
			raise OSError(ctypes.get_errno(), "timerfd_create failed")

		self._arm()

		self.onRealtimeChanged = []
		self._notifier = eSocketNotifier(self.fd, select.POLLIN)
		self._notifier.callback.append(self._activated)

	def _arm(self):
		spec = itimerspec()

		#
		# An absolute deadline as far out as a 32-bit time_t allows.
		# Expiry is irrelevant -- only TFD_TIMER_CANCEL_ON_SET matters.
		# (Year 2038 problem, deliberately: see _activated().)
		#
		spec.it_value.tv_sec = 0x7fffffff
		spec.it_value.tv_nsec = 0
		spec.it_interval.tv_sec = 0
		spec.it_interval.tv_nsec = 0

		ret = self._libc.timerfd_settime(
			self.fd,
			self.TFD_TIMER_ABSTIME | self.TFD_TIMER_CANCEL_ON_SET,
			ctypes.byref(spec),
			None,
		)
		if ret != 0:
			raise OSError(ctypes.get_errno(), "timerfd_settime failed")

	def _activated(self, what):
		try:
			os.read(self.fd, 8)
		except OSError as e:
			if e.errno != errno.ECANCELED:
				raise
			self._arm()
			print("[ClockRealtimeMonitor] system clock step detected")
			for f in list(self.onRealtimeChanged):
				if callable(f):
					f()
			return
		# Only reachable on genuine expiry (year 2038) -- keep watching.
		self._arm()

	def addRealtimeChangedCallback(self, f):
		if f not in self.onRealtimeChanged:
			self.onRealtimeChanged.append(f)

	def removeRealtimeChangedCallback(self, f):
		if f in self.onRealtimeChanged:
			self.onRealtimeChanged.remove(f)

	def close(self):
		if self._notifier is not None:
			self._notifier.callback.remove(self._activated)
			self._notifier.stop()
			self._notifier = None
		if self.fd >= 0:
			os.close(self.fd)
			self.fd = -1

	def __del__(self):
		try:
			self.close()
		except Exception:
			pass
