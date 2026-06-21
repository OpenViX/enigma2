from os import unlink

from time import time

from twisted.internet import reactor
from twisted.internet.threads import deferToThread
from twisted.web.client import Agent, RedirectAgent, BrowserLikePolicyForHTTPS, ResponseDone
from twisted.web.http_headers import Headers
from twisted.internet.protocol import Protocol

from urllib.request import Request, urlopen


# ------------------------------------------------------------
# USER_AGENTS
# ------------------------------------------------------------
class USER_AGENTS:
	FIREFOX = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0"
	CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
	HBBTV = "HbbTV/1.1.1 (+PVR+RTSP+DL; Sonic; TV44; 1.32.455; 2.002) Bee/3.5"

# ------------------------------------------------------------
# NON-BLOCKING HEAD SUPPORT, run in deferToThread()
# ------------------------------------------------------------


def get_content_length(url, headers=None, timeout=5):
	try:
		req = Request(url, headers=headers or {}, method="HEAD")
		with urlopen(req, timeout=timeout) as r:
			val = r.headers.get("Content-Length")
			return int(val) if val else 0
	except Exception:
		return 0


# ------------------------------------------------------------
# SHARED HELPERS
# ------------------------------------------------------------
HTTP_DEFAULT_HEADERS = {
	"User-Agent": USER_AGENTS.CHROME,
	"Accept": "*/*",
	"Accept-Encoding": "identity",
	"Connection": "keep-alive",
}


def _makeAgent():
	base = Agent(reactor, contextFactory=BrowserLikePolicyForHTTPS())
	return RedirectAgent(base)


def _normaliseHeaders(headers):
	""" normalise to str """
	return {
		k.decode("utf-8") if isinstance(k, bytes) else str(k):
		v.decode("utf-8") if isinstance(v, bytes) else str(v)
		for k, v in (headers or {}).items()
	}


def _buildHeaders(headers=None):
	return Headers({
		k.encode("utf-8"): [v.encode("utf-8")]
		for k, v in {**HTTP_DEFAULT_HEADERS, **(headers or {})}.items()
	})

# ------------------------------------------------------------
# STREAM PROTOCOL (no UI logic)
# ------------------------------------------------------------


class _DownloadProtocol(Protocol):
	def __init__(self, downloader):
		self.downloader = downloader
		self.recv = 0

	def dataReceived(self, data):
		if self.downloader._done:
			return

		self.recv += len(data)
		try:
			self.downloader.fd.write(data)
		except OSError as err:
			self.downloader._finalise(error=err)
			return

		self.downloader.progress = self.recv

		self.downloader._pendingProgress = (
			self.recv,
			self.downloader.totalSize
		)

		if not self.downloader._uiScheduled:
			self.downloader._uiScheduled = True
			reactor.callLater(0.2, self.downloader._flushUi)

	def connectionLost(self, reason):
		if self.downloader._done:
			return

		if reason.check(ResponseDone):
			self.downloader._finalise(success=True)
		else:
			self.downloader._finalise(error=reason)


# ------------------------------------------------------------
# DOWNLOADER
# ------------------------------------------------------------
class DownloadWithProgress:

	def __init__(self, url, outputFile, *args, **kwargs):
		""" url and outputFile should be str type """
		self.url = url
		self.outputFile = outputFile

		self.progress = 0
		self.totalSize = -1  # means size not set

		self.progressCallback = None
		self.endCallback = None
		self.errorCallback = None

		self.protocol = None
		self.fd = None
		self._done = False

		self._pendingProgress = None
		self._uiScheduled = False
		self._request = None

		# for speed/eta functions
		self._startTime = None

		# headers (stored as strings internally)
		self._rawHeaders = _normaliseHeaders(kwargs.get("headers", {}))
		userAgent = kwargs.get("userAgent")
		if userAgent:
			self._rawHeaders.setdefault("User-Agent", _normaliseHeaders({"User-Agent": userAgent})["User-Agent"])

		# connection timeout
		self._connectTimeout = int(kwargs.get("connectTimeout", 5))
		self._connectTimer = None

		self._agent = _makeAgent()

	def start(self):
		self.progress = 0
		self.totalSize = -1
		self._startTime = time()

		# NON-BLOCKING HEAD (hint only)
		deferToThread(self._getHeadSize).addCallback(self._gotHeadSize)

		self._startGet()
		return self

	def _getHeadSize(self):
		return get_content_length(self.url, self._rawHeaders, self._connectTimeout)

	def _gotHeadSize(self, size):
		if self._done:
			return
		# never override a known good value from GET
		if self.totalSize > 0:
			return
		if size and size > 0:
			self.totalSize = size
		else:
			self.totalSize = -1

	# --------------------------------------------------------
	# GET REQUEST
	# --------------------------------------------------------
	def _startGet(self):
		try:
			headers = _buildHeaders(headers=self._rawHeaders)  # userAgent is already passed by headers

			self._request = self._agent.request(
				b"GET",
				self.url.encode("utf-8"),
				headers,
				None
			)

			self._request.addCallbacks(self._responseReceived, self._requestFailed)

			# CONNECT TIMEOUT WATCHDOG
			if self._connectTimeout:
				self._connectTimer = reactor.callLater(self._connectTimeout, self._onConnectTimeout)

		except Exception as err:
			self._finalise(error=err)

	# --------------------------------------------------------
	# RESPONSE
	# --------------------------------------------------------
	def _responseReceived(self, response):
		self._cancelConnectionTimeout()

		if self._done:
			return

		# STRICT HTTP GATE
		if not (200 <= response.code < 300):  # if not 2XX code means request failed
			self._finalise(error=Exception(f"HTTP {response.code}"))
			return

		# content-length hint from server
		try:
			length = response.headers.getRawHeaders("content-length")
			if length:
				val = int(length[0])
				if val > 0:
					self.totalSize = val
		except Exception:
			pass

		try:  # catch any exception while trying to create the local file
			self.fd = open(self.outputFile, "wb")
		except Exception as err:
			self._finalise(error=err)
			return

		self.protocol = _DownloadProtocol(self)

		response.deliverBody(self.protocol)

	# --------------------------------------------------------
	# CONNECTION TIMEOUT HANDLING
	# --------------------------------------------------------
	def _cancelConnectionTimeout(self):
		if self._connectTimer and self._connectTimer.active():
			self._connectTimer.cancel()
			self._connectTimer = None

	def _onConnectTimeout(self):
		if self._done:
			return

		self._connectTimer = None

		# cancel request if still pending
		if self._request:
			try:
				self._request.cancel()
			except Exception:
				pass

		self._finalise(error=Exception("Connect timeout"))

	# --------------------------------------------------------
	# UI FLUSH
	# --------------------------------------------------------
	def _flushUi(self):
		self._uiScheduled = False

		if self._done:
			return

		if self._pendingProgress and callable(self.progressCallback):
			progress, total = self._pendingProgress

			if total <= 0:
				total = -1

			self.progressCallback(progress, total)

	# --------------------------------------------------------
	# ERROR HANDLING
	# --------------------------------------------------------
	def _requestFailed(self, failure):
		self._cancelConnectionTimeout()

		if self._done:
			return

		self._finalise(error=failure)

	# --------------------------------------------------------
	# CONTROL
	# --------------------------------------------------------
	def stop(self):
		self._finalise()

	# --------------------------------------------------------
	# SINGLE EXIT POINT
	# --------------------------------------------------------
	def _finalise(self, success=False, error=None):

		# Finalise download lifecycle exactly once.
		# Cleans up network/file resources and dispatches final callbacks.
		# if success=False and error=None means cancelled by stop()

		self._cancelConnectionTimeout()

		if self._done:
			return

		self._done = True

		# 1. stop network
		if self._request:
			try:
				# cancel request before response body starts
				self._request.cancel()
			except Exception:
				pass

		if self.protocol and (transport := getattr(self.protocol, "transport", None)):
			try:
				# abort active response body stream
				transport.stopProducing()
			except Exception:
				pass

		# 2. close file descriptor
		if self.fd:
			try:
				self.fd.close()
			except Exception:
				pass
			self.fd = None

		# 3. remove partial file
		if not success:
			try:
				unlink(self.outputFile)
			except OSError:
				pass

		# 4. callbacks ( no callback on cancelled (i.e. forced stop()) )
		if success:
			if callable(self.endCallback):
				self.endCallback(self.outputFile)

		elif error and callable(self.errorCallback):
			self.errorCallback(error)

	# --------------------------------------------------------
	# CALLBACKS
	# --------------------------------------------------------
	def addProgress(self, progressCallback):
		self.progressCallback = progressCallback
		return self

	def addEnd(self, endCallback):
		self.endCallback = endCallback
		return self

	def addError(self, errorCallback):
		self.errorCallback = errorCallback
		return self

	def setAgent(self, userAgent):
		self._rawHeaders["User-Agent"] = _normaliseHeaders({"User-Agent": userAgent})["User-Agent"]

	def addErrback(self, errorCallback):  # Temporary support for deprecated callbacks.
		print("[Downloader] Warning: DownloadWithProgress 'addErrback' is deprecated use 'addError' instead!")
		return self.addError(errorCallback)

	def addCallback(self, endCallback):  # Temporary support for deprecated callbacks.
		print("[Downloader] Warning: DownloadWithProgress 'addCallback' is deprecated use 'addEnd' instead!")
		return self.addEnd(endCallback)

	# --------------------------------------------------------
	# SPEED / ETA, for use by newer UI
	# --------------------------------------------------------
	def getSpeed(self):
		"""
		Returns current average download speed in bytes/sec.
		Returns 0 if not enough information is available.
		"""
		if not self._startTime:
			return 0

		elapsed = time() - self._startTime

		if elapsed <= 0:
			return 0

		return float(self.progress) / elapsed

	def getEta(self):
		"""
		Returns estimated seconds remaining.
		Returns -1 if total size is unknown.
		"""
		if self.totalSize <= 0:
			return -1

		speed = self.getSpeed()

		if speed <= 0:
			return -1

		remaining = self.totalSize - self.progress

		if remaining <= 0:
			return 0

		return int(remaining / speed)


# ------------------------------------------------------------
# COMPATIBILITY,
# Class names should start with a Capital letter, this
# catches old code until that code can be updated.
# ------------------------------------------------------------
class downloadWithProgress(DownloadWithProgress):
	pass
