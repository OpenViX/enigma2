from config import config
from enigma import eRect
from Epg.EpgListSingle import EPGListSingle

# keep const value for backward compatibility
EPG_TYPE_SINGLE = 0
EPG_TYPE_MULTI = 1
EPG_TYPE_SIMILAR = 2
EPG_TYPE_ENHANCED = 3
EPG_TYPE_INFOBAR = 4
EPG_TYPE_GRAPH = 5
EPG_TYPE_INFOBARGRAPH = 7

# keep for backward compatibility, some plugins import this
class Rect:
	def __init__(self, x, y, width, height):
		self.x = x
		self.y = y
		self.w = width
		self.h = height

	def left(self):
		return self.x

	def top(self):
		return self.y

	def height(self):
		return self.h

	def width(self):
		return self.w

class EPGList(EPGListSingle):
	def __init__(self, type = EPG_TYPE_SINGLE, selChangedCB = None, timer = None, time_epoch = 120, overjump_empty = False, graphic = False):
		if type != EPG_TYPE_SINGLE:
			print "[EPGList] Warning: EPGList does not support", {'infobar':'EPG_TYPE_INFOBAR','enhanced':'EPG_TYPE_ENHANCED','graph':'EPG_TYPE_GRAPH','infobargraph':'EPG_TYPE_INFOBARGRAPH','multi':'EPG_TYPE_MULTI', None: 'EPGtype == None'}.get(type, type)
			print "          attempting to continue in single EPG mode"
		EPGListSingle.__init__(self, config.epgselection.enhanced_itemsperpage, config.epgselection.enhanced_eventfs, selChangedCB, timer)

	# for backwards compatibility
	def buildSingleEntry(self, service, eventId, beginTime, duration, eventName):
		return EPGListSingle.buildEntry(self, service, eventId, beginTime, duration, eventName)

	def recalcEntrySize(self):
		EPGListSingle.recalcEntrySize(self)

	# these properties are expected to be Rect not eRect
	@property
	def weekday_rect(self):
		r = self._weekday_rect
		return Rect(r.left(), r.top(), r.width(), r.height())

	@weekday_rect.setter
	def weekday_rect(self, r):
		_weekday_rect = eRect(r.x, r.y, r.w, r.h)

	@property
	def descr_rect(self):
		r = self._descr_rect
		return Rect(r.left(), r.top(), r.width(), r.height())

	@descr_rect.setter
	def descr_rect(self, r):
		_descr_rect = eRect(r.x, r.y, r.w, r.h)

	@property
	def datetime_rect(self):
		r = self._datetime_rect
		return Rect(r.left(), r.top(), r.width(), r.height())

	@datetime_rect.setter
	def datetime_rect(self, r):
		_datetime_rect = eRect(r.x, r.y, r.w, r.h)
