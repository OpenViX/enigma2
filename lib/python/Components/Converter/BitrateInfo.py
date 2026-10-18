# -*- coding: utf-8 -*-
#
# BitrateInfo converter: exposes the current video / audio bitrate of the playing service.
#
# The service itself measures the bitrate (iServiceInformation.sVideoBitrate / sAudioBitrate),
# for DVB and servicemp3 / IPTV alike. This converter polls those values every second:
#   - a negative value means "nothing to measure (yet)" and is ignored
#   - readings below MIN_VALID_KBPS are dropped as gaps in the data
#   - the last 10 valid readings are averaged
#   - the last feasible value stays on screen until a new valid one arrives
#     (it only becomes 0 on a new zap)
#
# One measurement is shared by all widgets using this converter.
#
# Usage in a skin:
#   <widget source="session.CurrentService" render="Label" ...>
#       <convert type="BitrateInfo">Video</convert>
#   </widget>
#
# Types: Video      -> "12345 kbit/s"
#        Audio      -> "256 kbit/s"
#        Both       -> "V: 12345 kbit/s  A: 256 kbit/s"
#        VideoValue -> "12345"        (no unit)
#        AudioValue -> "256"

from enigma import eTimer, iServiceInformation

import NavigationInstance
from Components.Converter.Converter import Converter
from Components.Element import cached

# readings below this (kbit/s) are treated as gaps in the data, not as the real rate
MIN_VALID_KBPS = 100


class BitrateEngine:
	def __init__(self):
		self.users = []
		self.running = False
		self.sref = None
		self.pollHist = [[], []]
		self.vcur = 0
		self.acur = 0
		self.pollTimer = eTimer()
		self.pollTimer.callback.append(self.pollService)

	def attach(self, user):
		if user not in self.users:
			self.users.append(user)

	def detach(self, user):
		if user in self.users:
			self.users.remove(user)
		if not self.users:
			self.stop()

	def notify(self):
		for user in self.users[:]:
			user.refresh()

	def getService(self):
		nav = NavigationInstance.instance
		return nav and nav.getCurrentService()

	def update(self):
		# called whenever the service or its info changed: restart when the service differs
		if not self.users:
			return
		service = self.getService()
		if not service:
			self.stop()
			return
		sref = service.info().getInfoString(iServiceInformation.sServiceref)
		if self.running and sref == self.sref:
			return
		self.stop()
		self.sref = sref
		self.running = True
		self.pollHist = [[], []]
		self.pollTimer.start(1000, False)

	def stop(self):
		self.pollTimer.stop()
		self.running = False
		self.sref = None
		if self.vcur or self.acur:
			self.vcur = self.acur = 0
			self.notify()

	def pollService(self):
		service = self.getService()
		if not service:
			return
		info = service.info()
		v = info.getInfo(iServiceInformation.sVideoBitrate)
		a = info.getInfo(iServiceInformation.sAudioBitrate)
		if v < 0 and a < 0:
			return
		# Readings below MIN_VALID_KBPS are gaps, not a rate: leave them out and average the
		# last 10 valid readings. When nothing valid arrives the last feasible value stays on
		# screen (it only becomes 0 on a new zap).
		smooth = []
		for idx, val in enumerate((v, a)):
			hist = self.pollHist[idx]
			if val >= MIN_VALID_KBPS:
				hist.append(val)
				del hist[:-10]
			smooth.append(sum(hist) // len(hist) if hist else 0)
		self.vcur, self.acur = smooth
		self.notify()


engine = BitrateEngine()


class BitrateInfo(Converter):
	VIDEO = 0
	AUDIO = 1
	BOTH = 2
	VIDEO_VALUE = 3
	AUDIO_VALUE = 4

	def __init__(self, type):
		Converter.__init__(self, type)
		self.type = {
			"Video": self.VIDEO,
			"Audio": self.AUDIO,
			"VideoValue": self.VIDEO_VALUE,
			"AudioValue": self.AUDIO_VALUE,
		}.get(type, self.BOTH)

	def refresh(self):
		Converter.changed(self, (self.CHANGED_POLL,))

	@cached
	def getText(self):
		video, audio = engine.vcur, engine.acur
		if self.type == self.VIDEO:
			return "%d kbit/s" % video
		if self.type == self.AUDIO:
			return "%d kbit/s" % audio
		if self.type == self.VIDEO_VALUE:
			return "%d" % video
		if self.type == self.AUDIO_VALUE:
			return "%d" % audio
		return "V: %d kbit/s  A: %d kbit/s" % (video, audio)

	text = property(getText)

	@cached
	def getBoolean(self):
		video, audio = engine.vcur, engine.acur
		if self.type in (self.VIDEO, self.VIDEO_VALUE):
			return video > 0
		elif self.type in (self.AUDIO, self.AUDIO_VALUE):
			return audio > 0
		else:
			return video > 0 or audio > 0

	boolean = property(getBoolean)

	def changed(self, what):
		if what[0] == self.CHANGED_CLEAR:
			engine.detach(self)
		elif what[0] != self.CHANGED_POLL and not self.suspended:
			engine.attach(self)
			engine.update()
		Converter.changed(self, what)

	def doSuspend(self, suspended):
		if suspended:
			engine.detach(self)
		else:
			engine.attach(self)
			engine.update()

	def destroy(self):
		engine.detach(self)
		Converter.destroy(self)