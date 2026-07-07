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

		self.onRealtimeChanged = []

		self.fd = -1
		self._notifier = None

		if not self._create() or not self._arm():
			print("[ClockRealtimeMonitor] Failed to initialise.")
			return

		self._add_notifier()

	def _create(self):
		self.fd = self._libc.timerfd_create(self.CLOCK_REALTIME, 0)
		if self.fd < 0:
			print("[ClockRealtimeMonitor] timerfd_create failed")
			self.fd = -1
			return False
		return True

	def _recreate(self):
		self._remove_notifier()

		self._close_fd()

		if not self._create():
			return False

		if not self._arm():
			return False

		self._add_notifier()

		return True

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
			err = ctypes.get_errno()
			print(f"[ClockRealtimeMonitor] timerfd_settime failed ({err}: {os.strerror(err)})")
			return False

		return True

	def _activated(self, what):
		try:
			os.read(self.fd, 8)
		except OSError as e:
			if e.errno != errno.ECANCELED:
				print(f"[ClockRealtimeMonitor] read failed ({e.errno})")
				return

			print("[ClockRealtimeMonitor] system clock step detected")

			for f in list(self.onRealtimeChanged):
				if callable(f):
					f()

		# Either after a clock step or a genuine expiry (year 2038),
		# continue monitoring.
		self._arm() or self._recover()

	def _add_notifier(self):
		self._notifier = eSocketNotifier(self.fd, select.POLLIN)
		self._notifier.callback.append(self._activated)

	def _remove_notifier(self):
		if self._notifier is not None:
			if self._activated in self._notifier.callback:
				self._notifier.callback.remove(self._activated)
			self._notifier.stop()
			self._notifier = None

	def _recover(self):
		print("[ClockRealtimeMonitor] Recreating timerfd...")
		if not self._recreate():
			print("[ClockRealtimeMonitor] Recreate failed, monitoring disabled.")
			return False
		return True

	def _close_fd(self):
		if self.fd >= 0:
			os.close(self.fd)
			self.fd = -1

	def addRealtimeChangedCallback(self, f):
		if f not in self.onRealtimeChanged:
			self.onRealtimeChanged.append(f)

	def removeRealtimeChangedCallback(self, f):
		if f in self.onRealtimeChanged:
			self.onRealtimeChanged.remove(f)

	def close(self):
		self._remove_notifier()
		self._close_fd()

	def __del__(self):
		try:
			self.close()
		except Exception:
			pass
