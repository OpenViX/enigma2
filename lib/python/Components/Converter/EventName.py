from enigma import eEPGCache

from Components.Converter.Converter import Converter
from Components.Element import cached
from Components.Converter.genre import getGenreStringSub, getGenreStringLong
from Components.config import config
from Tools.Directories import resolveFilename, SCOPE_CURRENT_SKIN
from time import time, localtime, mktime, strftime


class ETSIClassifications(dict):
	#            0         1         2          3        4         5          6         7         8         9        10        11        12        13        14        15
	COLORS = (0x000000, 0x00A822, 0x00A822, 0x00A822, 0x007DCA, 0x007DCA, 0x007DCA, 0xFF7900, 0xFF7900, 0xFF7900, 0xFF5594, 0xFF5594, 0xFF5594, 0xD70723, 0xD70723, 0xD70723)

	def shortRating(self, age):
		if age == 0:
			return _("All ages")
		elif age <= 15:
			age += 3
			return " %d+" % age

	def longRating(self, age):
		if age == 0:
			return _("Rating undefined")
		elif age <= 15:
			age += 3
			return _("Minimum age %d years") % age

	def imageRating(self, age):
		if age == 0:
			return "ratings/ETSI-ALL.png"
		elif age <= 15:
			age += 3
			return "ratings/ETSI-%d.png" % age

	def colorRating(self, age):
		return self.COLORS[age]

	def __init__(self):
		self.update([(i, (self.shortRating(c), self.longRating(c), self.imageRating(c), self.colorRating(i))) for i, c in enumerate(range(0, 16))])


class AusClassifications(dict):
	# In Australia "Not Classified" (NC) is to be displayed as an empty string.
	#            0   1   2    3    4    5    6    7    8     9     10   11   12    13    14    15
	SHORTTEXT = ("", "", "P", "P", "C", "C", "G", "G", "PG", "PG", "M", "M", "MA", "MA", "AV", "R")
	LONGTEXT = {
		"": _("Not Classified"),
		"P": _("Preschool"),
		"C": _("Children"),
		"G": _("General"),
		"PG": _("Parental Guidance Recommended"),
		"M": _("Mature Audience 15+"),
		"MA": _("Mature Adult Audience 15+"),
		"AV": _("Adult Audience, Strong Violence 15+"),
		"R": _("Restricted 18+")
	}
	IMAGES = {
		"": "ratings/blank.png",
		"P": "ratings/AUS-P.png",
		"C": "ratings/AUS-C.png",
		"G": "ratings/AUS-G.png",
		"PG": "ratings/AUS-PG.png",
		"M": "ratings/AUS-M.png",
		"MA": "ratings/AUS-MA.png",
		"AV": "ratings/AUS-AV.png",
		"R": "ratings/AUS-R.png"
	}

	#            0         1         2          3        4         5          6         7         8         9        10        11        12        13        14        15
	COLORS = (0x000000, 0x00A822, 0x00A822, 0x00A822, 0x007DCA, 0x007DCA, 0x007DCA, 0xFF7900, 0xFF7900, 0xFF7900, 0xFF5594, 0xFF5594, 0xFF5594, 0xD70723, 0xD70723, 0xD70723)

	def __init__(self):
		self.update([(i, (c, self.LONGTEXT[c], self.IMAGES[c], self.COLORS[i])) for i, c in enumerate(self.SHORTTEXT)])


class GBrClassifications(dict):
	# British Board of Film Classification
	#            0   1   2    3    4    5    6     7     8     9     10    11    12    13    14    15
	SHORTTEXT = ("", "", "", "U", "U", "U", "PG", "PG", "PG", "12", "12", "12", "15", "15", "15", "18")
	LONGTEXT = {
		"": _("Not Classified"),
		"U": _("U - Suitable for all"),
		"PG": _("PG - Parental Guidance"),
		"12": _("Suitable for ages 12+"),
		"15": _("Suitable for ages 15+"),
		"18": _("Suitable only for Adults")
	}
	IMAGES = {
		"": "ratings/blank.png",
		"U": "ratings/GBR-U.png",
		"PG": "ratings/GBR-PG.png",
		"12": "ratings/GBR-12.png",
		"15": "ratings/GBR-15.png",
		"18": "ratings/GBR-18.png"
	}

	#            0         1         2          3        4         5          6         7         8         9        10        11        12        13        14        15
	COLORS = (0x000000, 0x000000, 0x000000, 0x00A822, 0x00A822, 0x00A822, 0xFAB800, 0xFAB800, 0xFAB800, 0xFF7900, 0xFF7900, 0xFF7900, 0xFF5594, 0xFF5594, 0xFF5594, 0xD70723)

	def __init__(self):
		self.update([(i, (c, self.LONGTEXT[c], self.IMAGES[c], self.COLORS[i])) for i, c in enumerate(self.SHORTTEXT)])


class ItaClassifications(dict):
	# The classifications used by Sky Italia
	#            0   1   2    3    4    5    6     7     8     9     10    11    12    13    14    15
	SHORTTEXT = ("", "", "", "T", "T", "T", "BA", "BA", "BA", "12", "12", "12", "14", "14", "14", "18")
	LONGTEXT = {
		"": _("Non Classificato"),
		"T": _("Per Tutti"),
		"BA": _("Bambini Accompagnati"),
		"12": _("Dai 12 anni in su"),
		"14": _("Dai 14 anni in su"),
		"18": _("Dai 18 anni in su")
	}
	IMAGES = {
		"": "ratings/blank.png",
		"T": "ratings/ITA-T.png",
		"BA": "ratings/ITA-BA.png",
		"12": "ratings/ITA-12.png",
		"14": "ratings/ITA-14.png",
		"18": "ratings/ITA-18.png"
	}

	#            0         1         2          3        4         5          6         7         8         9        10        11        12        13        14        15
	COLORS = (0x000000, 0x00A822, 0x00A822, 0x00A822, 0x007DCA, 0x007DCA, 0x007DCA, 0xFF7900, 0xFF7900, 0xFF7900, 0xFF5594, 0xFF5594, 0xFF5594, 0xD70723, 0xD70723, 0xD70723)

	def __init__(self):
		self.update([(i, (c, self.LONGTEXT[c], self.IMAGES[c], self.COLORS[i])) for i, c in enumerate(self.SHORTTEXT)])


# Each country classification object in the map tuple must be an object that
# supports obj.get(key[, default]). It need not actually be a dict object.
#
# The other element is how the rating number should be formatted if there
# is no match in the classification object.
#
# If there is no matching country then the default ETSI should be selected.

countries = {
	"ETSI": (ETSIClassifications(), lambda age: (_("bc%d") % age, _("Rating defined by broadcaster - %d") % age, "ratings/ETSI-na.png", 0x222222)),
	"AUS": (AusClassifications(), lambda age: (_("BC%d") % age, _("Rating defined by broadcaster - %d") % age, "ratings/AUS-na.png", 0x222222)),
	"GBR": (GBrClassifications(), lambda age: (_("BC%d") % age, _("Rating defined by broadcaster - %d") % age, "ratings/GBR-na.png", 0x222222)),
	"ITA": (ItaClassifications(), lambda age: (_("BC%d") % age, _("Rating defined by broadcaster - %d") % age, "ratings/ITA-na.png", 0x222222))
}


# OpenTV country codes: epgchanneldata.cpp
# eEPGChannelData::getOpenTvParentalRating
opentv_countries = {
	"OT1": "GBR",
	"OT2": "ITA",
	"OT3": "AUS",
	"OT4": "NZL",
	"OTV": "ETSI"
}


class EventName(Converter):
	NAME = 0
	SHORT_DESCRIPTION = 1
	EXTENDED_DESCRIPTION = 2
	FULL_DESCRIPTION = 3
	ID = 4
	NAME_NOW = 5
	NAME_NEXT = 6
	NAME_NEXT2 = 7
	GENRE = 8
	RATING = 9
	SRATING = 10
	PDC = 11
	PDCTIME = 12
	PDCTIMESHORT = 13
	ISRUNNINGSTATUS = 14
	GENRELIST = 15

	NEXT_DESCRIPTION = 21
	THIRD_NAME = 22
	THIRD_NAME2 = 23
	THIRD_DESCRIPTION = 24

	RAWRATING = 31
	RATINGCOUNTRY = 32
	RATINGICON = 33

	FORMAT_STRING = 34

	RATINGTEXTANDCOLOR = 40

	KEYWORDS = {
		# Arguments...
		"Name": ("type", NAME),
		"Description": ("type", SHORT_DESCRIPTION),
		"ShortDescription": ("type", SHORT_DESCRIPTION),  # added for consistency with MovieInfo
		"ExtendedDescription": ("type", EXTENDED_DESCRIPTION),
		"FullDescription": ("type", FULL_DESCRIPTION),
		"ID": ("type", ID),
		"NowName": ("type", NAME_NOW),
		"NameNow": ("type", NAME_NOW),
		"NextName": ("type", NAME_NEXT),
		"NameNext": ("type", NAME_NEXT),
		"NextNameOnly": ("type", NAME_NEXT2),
		"NameNextOnly": ("type", NAME_NEXT2),
		"Genre": ("type", GENRE),
		"GenreList": ("type", GENRELIST),
		"Rating": ("type", RATING),
		"SmallRating": ("type", SRATING),
		"Pdc": ("type", PDC),
		"PdcTime": ("type", PDCTIME),
		"PdcTimeShort": ("type", PDCTIMESHORT),
		"IsRunningStatus": ("type", ISRUNNINGSTATUS),
		"NextDescription": ("type", NEXT_DESCRIPTION),
		"ThirdName": ("type", THIRD_NAME),
		"ThirdNameOnly": ("type", THIRD_NAME2),
		"ThirdDescription": ("type", THIRD_DESCRIPTION),
		"RawRating": ("type", RAWRATING),
		"RatingTextAndColor": ("type", RATINGTEXTANDCOLOR),
		"RatingCountry": ("type", RATINGCOUNTRY),
		"RatingIcon": ("type", RATINGICON),
		# Options...
		"Separated": ("separator", "\n\n"),
		"NotSeparated": ("separator", "\n"),
		"SeparatorSlash": ("separator", "/"),
		"SeparatorComma": ("separator", ", "),
		"Trimmed": ("trim", True),
		"NotTrimmed": ("trim", False)
	}

	# Maps each type to the name of the method that produces its text.
	HANDLERS = {
		NAME: "textName",
		SHORT_DESCRIPTION: "textShortDescription",
		EXTENDED_DESCRIPTION: "textExtendedDescription",
		FULL_DESCRIPTION: "textFullDescription",
		ID: "textID",
		NAME_NOW: "textNameNow",
		NAME_NEXT: "textNameNext",
		NAME_NEXT2: "textNameNextOnly",
		NEXT_DESCRIPTION: "textNextDescription",
		THIRD_NAME: "textThirdName",
		THIRD_NAME2: "textThirdNameOnly",
		THIRD_DESCRIPTION: "textThirdDescription",
		GENRE: "textGenre",
		GENRELIST: "textGenreList",
		RATING: "textRatingLong",
		SRATING: "textRatingShort",
		RATINGICON: "textRatingIcon",
		PDC: "textPdc",
		PDCTIME: "textPdcTime",
		PDCTIMESHORT: "textPdcTimeShort",
		ISRUNNINGSTATUS: "textRunningStatus",
		RAWRATING: "textRawRating",
		RATINGCOUNTRY: "textRatingCountry",
		RATINGTEXTANDCOLOR: "textRatingTextAndColor",
		FORMAT_STRING: "textFormatString"
	}

	# Maps each format-string token to the name of the method that produces its text.
	FORMAT_TOKENS = {
		"NAME": "formatName",
		"STARTTIME": "formatStartTime",
		"ENDTIME": "formatEndTime",
		"TIMERANGE": "formatTimeRange",
		"DURATION": "formatDuration"
	}

	# The tokens that need the event's begin and end times.
	FORMAT_TIME_TOKENS = frozenset(("STARTTIME", "ENDTIME", "TIMERANGE", "DURATION"))

	RATSHORT = 0
	RATLONG = 1
	RATICON = 2
	RATCOLOR = 3

	RATNORMAL = 0
	RATDEFAULT = 1

	def __init__(self, type):
		Converter.__init__(self, type)
		self.epgcache = eEPGCache.getInstance()

		self.type = self.NAME
		self.separator = None
		self.trim = False

		args = [(arg.strip() if i or arg.strip() in self.KEYWORDS else arg) for i, arg in enumerate(type.split(","))]
		self.parts = args

		if len(self.parts) > 1 and self.parts[0] not in self.KEYWORDS:
			self.type = self.FORMAT_STRING
			self.separator = self.parts[0]
			# Compile the tokens into bound handlers once. Unknown tokens were always ignored, so they are dropped here.
			self.formatParts = tuple(getattr(self, self.FORMAT_TOKENS[part]) for part in self.parts[1:] if part in self.FORMAT_TOKENS)
			self.formatNeedsTimes = any(part in self.FORMAT_TIME_TOKENS for part in self.parts[1:])
		else:
			self.formatParts = ()
			self.formatNeedsTimes = False
			for arg in args:
				name, value = self.KEYWORDS.get(arg, ("Error", None))
				if name == "Error":
					print("[EventName] ERROR: Unexpected / Invalid argument token '%s'!" % arg)
				else:
					setattr(self, name, value)
			if self.separator is None:
				default_sep = "SeparatorComma" if self.type == self.GENRELIST else "NotSeparated"
				self.separator = self.KEYWORDS[default_sep][1]

		# Choose the trim function and the handler once, so getText never has to work out the type again.
		self.trimText = self.trimStrip if self.trim else str
		self.handler = getattr(self, self.HANDLERS.get(self.type, "textEmpty"))

	@staticmethod
	def trimStrip(text):
		return str(text).strip()

	def formatDescription(self, description, extended):
		description = self.trimText(description)
		extended = self.trimText(extended)
		if description[0:20] == extended[0:20]:
			return extended
		if description and extended:
			description += self.separator
		return description + extended

	@cached
	def getBoolean(self):
		event = self.source.event
		if event:
			if self.type == self.NAME:
				return bool(self.getText())
			if self.type == self.PDC and event.getPdcPil():
				return True
		return False

	boolean = property(getBoolean)

	@cached
	def getText(self):
		event = self.source.event
		if event is None:
			return ""
		return self.handler(event) or ""

	text = property(getText)

	# ---- Simple event fields ----

	def textEmpty(self, event):
		return ""

	def textName(self, event):
		return self.trimText(event.getEventName())

	def textShortDescription(self, event):
		return self.trimText(event.getShortDescription())

	def textExtendedDescription(self, event):
		return self.trimText(event.getExtendedDescription() or event.getShortDescription())

	def textFullDescription(self, event):
		return self.formatDescription(event.getShortDescription(), event.getExtendedDescription())

	def textID(self, event):
		return self.trimText(event.getEventId())

	def textNameNow(self, event):
		return pgettext("now/next: 'now' event label", "Now") + ": " + self.trimText(event.getEventName())

	# ---- Ratings ----

	def getRatingEntry(self, event, useConfigCountry=True):
		rating = event.getParentalData()
		if not rating:
			return None
		age = rating.getRating()
		country = rating.getCountryCode().upper()
		country = opentv_countries.get(country, country)
		c = countries.get(country, countries["ETSI"])
		if useConfigCountry and config.misc.epgratingcountry.value:
			c = countries[config.misc.epgratingcountry.value]
		return c[self.RATNORMAL].get(age, c[self.RATDEFAULT](age))

	def textRatingLong(self, event):
		entry = self.getRatingEntry(event)
		return self.trimText(entry[self.RATLONG]) if entry else ""

	def textRatingShort(self, event):
		entry = self.getRatingEntry(event)
		return self.trimText(entry[self.RATSHORT]) if entry else ""

	def textRatingIcon(self, event):
		entry = self.getRatingEntry(event)
		return resolveFilename(SCOPE_CURRENT_SKIN, entry[self.RATICON]) if entry else ""

	def textRatingTextAndColor(self, event):
		entry = self.getRatingEntry(event, useConfigCountry=False)  # Matches the original behaviour.
		if not entry:
			return ""
		return f"{entry[self.RATSHORT].strip().replace('+', '')};#{entry[self.RATCOLOR]:08X}"

	def textRawRating(self, event):
		rating = event.getParentalData()
		return "%d" % rating.getRating() if rating else ""

	def textRatingCountry(self, event):
		rating = event.getParentalData()
		return rating.getCountryCode().upper() if rating else ""

	# ---- Genres ----

	def genreText(self, event, firstOnly):
		if not config.usage.show_genre_info.value:
			return ""
		genres = event.getGenreDataList()
		if not genres:
			return ""
		if firstOnly:
			genres = genres[0:1]
		rating = event.getParentalData()
		country = rating.getCountryCode().upper() if rating else "ETSI"
		if country in opentv_countries:
			country = opentv_countries[country] + "OpenTV"
			lookup = getGenreStringLong
		else:
			if config.misc.epggenrecountry.value:
				country = config.misc.epggenrecountry.value
			lookup = getGenreStringSub
		texts = (self.trimText(lookup(genre[0], genre[1], country=country)) for genre in genres)
		return self.separator.join(text for text in texts if text)

	def textGenre(self, event):
		return self.genreText(event, True)

	def textGenreList(self, event):
		return self.genreText(event, False)

	# ---- PDC ----

	def textPdc(self, event):
		return _("PDC") if event.getPdcPil() else ""

	def pdcStart(self, event):
		pil = event.getPdcPil()
		if not pil:
			return None
		begin = localtime(event.getBeginTime())
		return localtime(mktime([begin.tm_year, (pil & 0x7800) >> 11, (pil & 0xF8000) >> 15, (pil & 0x7C0) >> 6, (pil & 0x3F), 0, begin.tm_wday, begin.tm_yday, begin.tm_isdst]))

	def textPdcTime(self, event):
		start = self.pdcStart(event)
		return strftime(config.usage.date.short.value + " " + config.usage.time.short.value, start) if start else ""

	def textPdcTimeShort(self, event):
		start = self.pdcStart(event)
		return strftime(config.usage.time.short.value, start) if start else ""

	def textRunningStatus(self, event):
		if not event.getPdcPil():
			return ""
		running_status = event.getRunningStatus()
		if running_status == 1:
			return _("Not running")
		if running_status == 2:
			return _("Starts in a few seconds")
		if running_status == 3:
			return _("Pausing")
		if running_status == 4:
			return _("Running")
		if running_status == 5:
			return _("Service off-air")
		if running_status in (6, 7):
			return _("Reserved for future use")
		return _("Undefined")

	# ---- Next / third events ----

	def getLaterEvent(self, index):
		reference = self.source.service
		if reference and self.source.info and self.epgcache:
			events = self.epgcache.lookupEvent(["ITSECX", (reference.toString(), 1, -1, 1440)])  # Search next 24 hours.
			if events and len(events) > index:
				return events[index]
		return None

	def laterName(self, index, label=None):
		try:
			ev = self.getLaterEvent(index)
			if ev and ev[1]:
				name = self.trimText(ev[1])
				return label + ": " + name if label else name
		except Exception:
			pass
		return ""

	def laterDescription(self, index):
		try:
			ev = self.getLaterEvent(index)
			if ev and (ev[2] or ev[3]):
				return self.formatDescription(ev[2], ev[3])
		except Exception:
			pass
		return ""

	def textNameNext(self, event):
		return self.laterName(1, pgettext("now/next: 'next' event label", "Next"))

	def textNameNextOnly(self, event):
		return self.laterName(1)

	def textNextDescription(self, event):
		return self.laterDescription(1)

	def textThirdName(self, event):
		return self.laterName(2, pgettext("third event: 'third' event label", "Later"))

	def textThirdNameOnly(self, event):
		return self.laterName(2)

	def textThirdDescription(self, event):
		return self.laterDescription(2)

	# ---- Format string ----

	def textFormatString(self, event):
		if self.formatNeedsTimes:
			begin = event.getBeginTime()
			end = begin + event.getDuration()
		else:
			begin = end = None  # No time-based token was requested.
		res_str = ""
		for handler in self.formatParts:
			value = handler(event, begin, end)
			if value:
				res_str = self.appendToStringWithSeparator(res_str, value)
		return res_str

	# Each handler computes only what its own token needs.

	@staticmethod
	def clockText(timestamp):
		t = localtime(timestamp)
		return "%2d:%02d" % (t.tm_hour, t.tm_min)

	def formatName(self, event, begin, end):
		return self.trimText(event.getEventName())

	def formatStartTime(self, event, begin, end):
		return self.clockText(begin)

	def formatEndTime(self, event, begin, end):
		return self.clockText(end)

	def formatTimeRange(self, event, begin, end):
		return "%s - %s" % (self.clockText(begin), self.clockText(end))

	def formatDuration(self, event, begin, end):
		now = int(time())
		if begin <= now <= end:
			return "+%d min" % ((end - now) / 60)
		return "%d min" % ((end - begin) / 60)
