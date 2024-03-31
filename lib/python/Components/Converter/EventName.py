from enigma import eEPGCache

from Components.Converter.Converter import Converter
from Components.Element import cached
from Components.Converter.genre import getGenreStringSub, getGenreStringLong
from Components.config import config
from Tools.Directories import resolveFilename, SCOPE_CURRENT_SKIN
from time import time, localtime, mktime, strftime


class ETSIClassifications(dict):
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

	def __init__(self):
		self.update([(i, (self.shortRating(c), self.longRating(c), self.imageRating(c))) for i, c in enumerate(range(0, 16))])


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

	def __init__(self):
		self.update([(i, (c, self.LONGTEXT[c], self.IMAGES[c])) for i, c in enumerate(self.SHORTTEXT)])


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

	def __init__(self):
		self.update([(i, (c, self.LONGTEXT[c], self.IMAGES[c])) for i, c in enumerate(self.SHORTTEXT)])


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

	def __init__(self):
		self.update([(i, (c, self.LONGTEXT[c], self.IMAGES[c])) for i, c in enumerate(self.SHORTTEXT)])


# Each country classification object in the map tuple must be an object that
# supports obj.get(key[, default]). It need not actually be a dict object.
#
# The other element is how the rating number should be formatted if there
# is no match in the classification object.
#
# If there is no matching country then the default ETSI should be selected.

countries = {
	"ETSI": (ETSIClassifications(), lambda age: (_("bc%d") % age, _("Rating defined by broadcaster - %d") % age, "ratings/ETSI-na.png")),
	"AUS": (AusClassifications(), lambda age: (_("BC%d") % age, _("Rating defined by broadcaster - %d") % age, "ratings/AUS-na.png")),
	"GBR": (GBrClassifications(), lambda age: (_("BC%d") % age, _("Rating defined by broadcaster - %d") % age, "ratings/GBR-na.png")),
	"ITA": (ItaClassifications(), lambda age: (_("BC%d") % age, _("Rating defined by broadcaster - %d") % age, "ratings/ITA-na.png"))
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

	RATSHORT = 0
	RATLONG = 1
	RATICON = 2

	RATNORMAL = 0
	RATDEFAULT = 1

	def __init__(self, type):
		Converter.__init__(self, type)
		self.epgcache = eEPGCache.getInstance()

		self.type = self.NAME
		self.separator = None
		self.trim = False

		parse = ","
		type.replace(";", parse)  # Some builds use ";" as a separator, most use ",".
		args = [(arg.strip() if i or arg.strip() in self.KEYWORDS else arg) for i, arg in enumerate(type.split(parse))]
		self.parts = args

		if len(self.parts) > 1 and self.parts[0] not in self.KEYWORDS:
			self.type = self.FORMAT_STRING
			self.separator = self.parts[0]
		else:
			for arg in args:
				name, value = self.KEYWORDS.get(arg, ("Error", None))
				if name == "Error":
					print("[EventName] ERROR: Unexpected / Invalid argument token '%s'!" % arg)
				else:
					setattr(self, name, value)
			if self.separator is None:
				default_sep = "SeparatorComma" if self.type == self.GENRELIST else "NotSeparated"
				self.separator = self.KEYWORDS[default_sep][1]

	def trimText(self, text):
		if self.trim:
			return str(text).strip()
		else:
			return str(text)

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

		if self.type == self.NAME:
			return self.trimText(event.getEventName())
		elif self.type in (self.RATING, self.SRATING, self.RATINGICON):
			rating = event.getParentalData()
			if rating:
				age = rating.getRating()
				country = rating.getCountryCode().upper()
				if country in opentv_countries:
					country = opentv_countries[country]
				if country in countries:
					c = countries[country]
				else:
					c = countries["ETSI"]
				if config.misc.epgratingcountry.value:
					c = countries[config.misc.epgratingcountry.value]
				rating = c[self.RATNORMAL].get(age, c[self.RATDEFAULT](age))
				if rating:
					if self.type == self.RATING:
						return self.trimText(rating[self.RATLONG])
					elif self.type == self.SRATING:
						return self.trimText(rating[self.RATSHORT])
					return resolveFilename(SCOPE_CURRENT_SKIN, rating[self.RATICON])
		elif self.type in (self.GENRE, self.GENRELIST):
			if not config.usage.show_genre_info.value:
				return ""
			genres = event.getGenreDataList()
			if genres:
				if self.type == self.GENRE:
					genres = genres[0:1]
				rating = event.getParentalData()
				if rating:
					country = rating.getCountryCode().upper()
				else:
					country = "ETSI"
				if country in opentv_countries:
					country = opentv_countries[country] + "OpenTV"
					return self.separator.join((genretext for genretext in (self.trimText(getGenreStringLong(genre[0], genre[1], country=country)) for genre in genres) if genretext))
				else:
					if config.misc.epggenrecountry.value:
						country = config.misc.epggenrecountry.value
					return self.separator.join((genretext for genretext in (self.trimText(getGenreStringSub(genre[0], genre[1], country=country)) for genre in genres) if genretext))
		elif self.type == self.NAME_NOW:
			return pgettext("now/next: 'now' event label", "Now") + ": " + self.trimText(event.getEventName())
		elif self.type == self.SHORT_DESCRIPTION:
			return self.trimText(event.getShortDescription())
		elif self.type == self.EXTENDED_DESCRIPTION:
			return self.trimText(event.getExtendedDescription() or event.getShortDescription())
		elif self.type == self.FULL_DESCRIPTION:
			return self.formatDescription(event.getShortDescription(), event.getExtendedDescription())
		elif self.type == self.ID:
			return self.trimText(event.getEventId())
		elif self.type == self.PDC:
			if event.getPdcPil():
				return _("PDC")
		elif self.type in (self.PDCTIME, self.PDCTIMESHORT):
			pil = event.getPdcPil()
			if pil:
				begin = localtime(event.getBeginTime())
				start = localtime(mktime([begin.tm_year, (pil & 0x7800) >> 11, (pil & 0xF8000) >> 15, (pil & 0x7C0) >> 6, (pil & 0x3F), 0, begin.tm_wday, begin.tm_yday, begin.tm_isdst]))
				if self.type == self.PDCTIMESHORT:
					return strftime(config.usage.time.short.value, start)
				return strftime(config.usage.date.short.value + " " + config.usage.time.short.value, start)
		elif self.type == self.ISRUNNINGSTATUS:
			if event.getPdcPil():
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
		elif self.type in (self.NAME_NEXT, self.NAME_NEXT2) or (self.type >= self.NEXT_DESCRIPTION and not self.type == self.FORMAT_STRING and not self.type == self.RAWRATING):
			try:
				reference = self.source.service
				info = reference and self.source.info
				if info:
					test = ["ITSECX", (reference.toString(), 1, -1, 1440)]  # Search next 24 hours
					self.list = [] if self.epgcache is None else self.epgcache.lookupEvent(test)
					if self.list:
						if self.type == self.NAME_NEXT and self.list[1][1]:
							return pgettext("now/next: 'next' event label", "Next") + ": " + self.trimText(self.list[1][1])
						elif self.type == self.NAME_NEXT2 and self.list[1][1]:
							return self.trimText(self.list[1][1])
						elif self.type == self.NEXT_DESCRIPTION and (self.list[1][2] or self.list[1][3]):
							return self.formatDescription(self.list[1][2], self.list[1][3])
						if self.type == self.THIRD_NAME and self.list[2][1]:
							return pgettext("third event: 'third' event label", "Later") + ": " + self.trimText(self.list[2][1])
						elif self.type == self.THIRD_NAME2 and self.list[2][1]:
							return self.trimText(self.list[2][1])
						elif self.type == self.THIRD_DESCRIPTION and (self.list[2][2] or self.list[2][3]):
							return self.formatDescription(self.list[2][2], self.list[2][3])
			except:
				# Failed to return any EPG data.
				if self.type == self.NAME_NEXT:
					return pgettext("now/next: 'next' event label", "Next") + ": " + self.trimText(event.getEventName())
		elif self.type == self.RAWRATING:
			rating = event.getParentalData()
			if rating:
				return "%d" % rating.getRating()
		elif self.type == self.RATINGCOUNTRY:
			rating = event.getParentalData()
			if rating:
				return rating.getCountryCode().upper()
		elif self.type == self.FORMAT_STRING:
			begin = event.getBeginTime()
			end = begin + event.getDuration()
			now = int(time())
			t_start = localtime(begin)
			t_end = localtime(end)
			if begin <= now <= end:
				duration = end - now
				duration_str = "+%d min" % (duration / 60)
			else:
				duration = event.getDuration()
				duration_str = "%d min" % (duration / 60)
			start_time_str = "%2d:%02d" % (t_start.tm_hour, t_start.tm_min)
			end_time_str = "%2d:%02d" % (t_end.tm_hour, t_end.tm_min)
			name = self.trimText(event.getEventName())
			res_str = ""
			for x in self.parts[1:]:
				if x == "NAME" and name:
					res_str = self.appendToStringWithSeparator(res_str, name)
				if x == "STARTTIME" and start_time_str:
					res_str = self.appendToStringWithSeparator(res_str, start_time_str)
				if x == "ENDTIME" and end_time_str:
					res_str = self.appendToStringWithSeparator(res_str, end_time_str)
				if x == "TIMERANGE" and start_time_str and end_time_str:
					res_str = self.appendToStringWithSeparator(res_str, "%s - %s" % (start_time_str, end_time_str))
				if x == "DURATION" and duration_str:
					res_str = self.appendToStringWithSeparator(res_str, duration_str)
			return res_str
		return ""

	text = property(getText)
