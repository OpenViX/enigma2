from os import unlink
import requests
from twisted.internet import reactor
from urllib.request import urlopen, Request
from boxbranding import getMachineBrand, getMachineName
from enigma import eTimer


class DownloadWithProgress:
	def __init__(self, url, outputFile, *args, **kwargs):
		self.url = url
		self.outputFile = outputFile
		self.userAgent = "%s %s Enigma2 HbbTV/1.1.1 (+PVR+RTSP+DL;OpenViX;;;)" % (getMachineBrand(), getMachineName())
		# self.agent = "Mozilla/5.0 (Windows; U; Windows NT 5.1; en; rv:1.9.1.5) Gecko/20091102 Firefox/3.5.5"
		self.totalSize = 0
		self.progress = 0
		self.progressCallback = None
		self.endCallback = None
		self.errorCallback = None
		self.stopFlag = False
		self.timer = eTimer()
		self.timer.callback.append(self.reportProgress)
		self.requestHeader = {"User-agent": self.userAgent}
		self.userHeader = kwargs.get('headers', None)
		if self.userHeader is not None:
			self.requestHeader = self.requestHeader | self.userHeader

	def start(self):
		try:
			request = Request(self.url, None, self.requestHeader)
		except OSError as err:
			if self.errorCallback:
				self.errorCallback(err)
			return self
		feedFile = urlopen(request)
		metaData = feedFile.headers
		self.totalSize = int(metaData.get("Content-Length", 0))
		# Set the transfer block size to a minimum of 1K and a maximum of 1% of the file size (or 128KB if the size is unknown) else use 64K.
		self.blockSize = max(min(self.totalSize // 100, 1024), 131071) if self.totalSize else 65536
		reactor.callInThread(self.run)
		return self

	def run(self):
		# requests.Response object = requests.get(url, params=None, allow_redirects=True, auth=None, cert=None, cookies=None, headers=None, proxies=None, stream=False, timeout=None, verify=True)
		response = requests.get(self.url, headers=self.requestHeader, stream=True)  # Streaming, so we can iterate over the response.
		try:
			with open(self.outputFile, "wb") as fd:
				for buffer in response.iter_content(self.blockSize):
					if self.stopFlag:
						response.close()
						fd.close()
						unlink(self.outputFile)
						return True
					self.progress += len(buffer)
					if self.progressCallback:
						self.timer.start(0, True)
					fd.write(buffer)
			if self.endCallback:
				self.endCallback(self.outputFile)
		except OSError as err:
			if self.errorCallback:
				self.errorCallback(err)
		return False

	def stop(self):
		self.stopFlag = True

	def reportProgress(self):
		self.progressCallback(self.progress, self.totalSize)

	def addProgress(self, progressCallback):
		self.progressCallback = progressCallback

	def addEnd(self, endCallback):
		self.endCallback = endCallback

	def addError(self, errorCallback):
		self.errorCallback = errorCallback

	def setAgent(self, userAgent):
		self.userAgent = userAgent

	def addErrback(self, errorCallback):  # Temporary supprt for deprecated callbacks.
		print("[Downloader] Warning: DownloadWithProgress 'addErrback' is deprecated use 'addError' instead!")
		self.errorCallback = errorCallback
		return self

	def addCallback(self, endCallback):  # Temporary supprt for deprecated callbacks.
		print("[Downloader] Warning: DownloadWithProgress 'addCallback' is deprecated use 'addEnd' instead!")
		self.endCallback = endCallback
		return self


class downloadWithProgress(DownloadWithProgress):  # Class names should start with a Capital letter, this catches old code until that code can be updated.
	pass
