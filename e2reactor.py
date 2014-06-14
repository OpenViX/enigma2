# enigma2 reactor: based on pollreactor, which is
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Maintainer: U{Felix Domke<mailto:tmbinc@elitedvb.net>}
"""

# System imports
import select, errno, sys

# Twisted imports
from twisted.python import log, failure
from twisted.internet import main, posixbase, error
#from twisted.internet.pollreactor import PollReactor, poller

from enigma import getApplication

# globals
reads = {}
writes = {}
selectables = {}

POLL_DISCONNECTED = (select.POLLHUP | select.POLLERR | select.POLLNVAL)

class E2SharedPoll:
	def __init__(self):
		self.dict = { }
		self.eApp = getApplication()

	def register(self, fd, eventmask = select.POLLIN | select.POLLERR | select.POLLOUT):
		self.dict[fd] = eventmask

	def unregister(self, fd):
		del self.dict[fd]

	def poll(self, timeout = None):
		try:
			r = self.eApp.poll(timeout, self.dict)
		except KeyboardInterrupt:
			return None
		return r

poller = E2SharedPoll()

class PollReactor(posixbase.PosixReactorBase):
	"""A reactor that uses poll(2)."""

	def _updateRegistration(self, fd):
		"""Register/unregister an fd with the poller."""
		try:
			poller.unregister(fd)
		except KeyError:
			pass

		mask = 0
		if reads.has_key(fd): mask = mask | select.POLLIN
		if writes.has_key(fd): mask = mask | select.POLLOUT
		if mask != 0:
			poller.register(fd, mask)
		else:
			if selectables.has_key(fd): del selectables[fd]


		poller.eApp.interruptPoll()

	def _dictRemove(self, selectable, mdict):
		try:
			# the easy way
			fd = selectable.fileno()
			# make sure the fd is actually real.  In some situations we can get
			# -1 here.
			mdict[fd]
		except:
			# the hard way: necessary because fileno() may disappear at any
			# moment, thanks to python's underlying sockets impl
			for fd, fdes in selectables.items():
				if selectable is fdes:
					break
			else:
				# Hmm, maybe not the right course of action?  This method can't
				# fail, because it happens inside error detection...
				return
		if mdict.has_key(fd):
			del mdict[fd]
			self._updateRegistration(fd)

	def addReader(self, reader):
		"""Add a FileDescriptor for notification of data available to read.
		"""
		fd = reader.fileno()
		if not reads.has_key(fd):
			selectables[fd] = reader
			reads[fd] =  1
			self._updateRegistration(fd)

	def addWriter(self, writer, writes=writes, selectables=selectables):
		"""Add a FileDescriptor for notification of data available to write.
		"""
		fd = writer.fileno()
		if not writes.has_key(fd):
			selectables[fd] = writer
			writes[fd] =  1
			self._updateRegistration(fd)

	def removeReader(self, reader, reads=reads):
		"""Remove a Selectable for notification of data available to read.
		"""
		return self._dictRemove(reader, reads)

	def removeWriter(self, writer, writes=writes):
		"""Remove a Selectable for notification of data available to write.
		"""
		return self._dictRemove(writer, writes)

	def removeAll(self, reads=reads, writes=writes, selectables=selectables):
		"""Remove all selectables, and return a list of them."""
		if self.waker is not None:
			self.removeReader(self.waker)
		result = selectables.values()
		fds = selectables.keys()
		reads.clear()
		writes.clear()
		selectables.clear()
		for fd in fds:
			poller.unregister(fd)

		if self.waker is not None:
			self.addReader(self.waker)
		return result

	def doPoll(self, timeout,
			   reads=reads,
			   writes=writes,
			   selectables=selectables,
			   select=select,
			   log=log,
			   POLLIN=select.POLLIN,
			   POLLOUT=select.POLLOUT):
		"""Poll the poller for new events."""

		if timeout is not None:
			timeout = int(timeout * 1000) # convert seconds to milliseconds

		try:
			l = poller.poll(timeout)
			if l is None:
				if self.running:
					self.stop()
				l = [ ]
		except select.error, e:
			if e[0] == errno.EINTR:
				return
			else:
				raise
		_drdw = self._doReadOrWrite
		for fd, event in l:
			try:
				selectable = selectables[fd]
			except KeyError:
				# Handles the infrequent case where one selectable's
				# handler disconnects another.
				continue
			log.callWithLogger(selectable, _drdw, selectable, fd, event, POLLIN, POLLOUT, log)

	doIteration = doPoll

	def _doReadOrWrite(self, selectable, fd, event, POLLIN, POLLOUT, log, faildict=None):
		if not faildict: faildict = {
		error.ConnectionDone: failure.Failure(error.ConnectionDone()),
		error.ConnectionLost: failure.Failure(error.ConnectionLost())
		}
		why = None
		inRead = False
		if event & POLL_DISCONNECTED and not (event & POLLIN):
			why = main.CONNECTION_LOST
		else:
			try:
				if event & POLLIN:
					why = selectable.doRead()
					inRead = True
				if not why and event & POLLOUT:
					why = selectable.doWrite()
					inRead = False
				if not selectable.fileno() == fd:
					why = error.ConnectionFdescWentAway('Filedescriptor went away')
					inRead = False
			except:
				log.deferr()
				why = sys.exc_info()[1]
		if why:
			self._disconnectSelectable(selectable, why, inRead)

	def callLater(self, *args, **kwargs):
		poller.eApp.interruptPoll()
		return posixbase.PosixReactorBase.callLater(self, *args, **kwargs)

def install():
	"""Install the poll() reactor."""

	p = PollReactor()
	main.installReactor(p)

__all__ = ["PollReactor", "install"]
