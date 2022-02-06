#
# Genre types taken from DVB standards documentation
#
# some broadcaster do define other types so this list
# may grow or be replaced..
#


class GenresETSI:
	maintype = (
		_("Reserved"),
		_("Drama and Films"),
		_("News/Current Affairs/Social"),
		_("Show/Game Show/Leisure hobbies"),
		_("Sports"),
		_("Children/Youth/Education/Science"),
		_("Music/Ballet/Dance"),
		_("Arts/Culture (without music)")
	)

	subtype = {
		# Movie/Drama
		1: (
			_("movie (general)"),
			_("detective/thriller"),
			_("adventure/western/war"),
			_("science fiction/fantasy/horror"),
			_("comedy"),
			_("soap/melodrama/folkloric"),
			_("romance"),
			_("serious/classical/religious/historical drama"),
			_("adult movie")
		),
		# News/Current Affairs
		2: (
			_("news/current affairs (general)"),
			_("news/weather report"),
			_("news magazine"),
			_("documentary"),
			_("discussion/interview/debate"),
			_("social/political issues/economics (general)"),
			_("magazines/reports/documentary"),
			_("economics/social advisory"),
			_("remarkable people")
		),
		# Show/Game show
		3: (
			_("show/game show (general)"),
			_("game show/quiz/contest"),
			_("variety show"),
			_("talk show"),
			_("leisure hobbies (general)"),
			_("tourism/travel"),
			_("handicraft"),
			_("motoring"),
			_("fitness and health"),
			_("cooking"),
			_("advertisement/shopping")
		),
		# Sports
		4: (
			_("sports (general)"),
			_("special events"),
			_("sports magazine"),
			_("football/soccer"),
			_("tennis/squash"),
			_("team sports/excluding football"),
			_("athletics"),
			_("motor sport"),
			_("water sport"),
			_("winter sport"),
			_("equestrian"),
			_("martial sports"),
			_("local sports")
		),
		# Children/Youth
		5: (
			_("childrens's youth program (general)"),
			_("pre-school children's program"),
			_("entertainment (6-14 year old)"),
			_("entertainment (10-16 year old)"),
			_("information/education/school program"),
			_("cartoon/puppets"),
			_("educational/science/factual topics (general)"),
			_("nature/animals/environment"),
			_("technology/natural sciences"),
			_("medicine/physiology/psychology"),
			_("foreign countries/expeditions"),
			_("social/spiritual sciences"),
			_("further education"),
			_("languages")
		),
		# Music/Ballet/Dance
		6: (
			_("music/ballet/dance (general)"),
			_("rock/pop"),
			_("serious music/classic music"),
			_("folk/traditional music"),
			_("jazz"),
			_("musical/opera"),
			_("ballet")
		),
		# Arts/Culture
		7: (
			_("arts/culture (without music, general)"),
			_("performing arts"),
			_("fine arts"),
			_("religion"),
			_("popular culture/traditional arts"),
			_("literature"),
			_("film/cinema"),
			_("experimental film/video"),
			_("broadcasting/press"),
			_("new media"),
			_("arts/culture magazine"),
			_("fashion")
		),
		# Social/Political/Economics
		8: (
			_("social/political issues/economics (general)"),
			_("magazines/reports/documentary"),
			_("economics/social advisory"),
			_("remarkable people")
		),
		# Education/Science/...
		9: (
			_("education/science/factual topics (general)"),
			_("nature/animals/environment"),
			_("technology/natural science"),
			_("medicine/physiology/psychology"),
			_("foreign countries/expeditions"),
			_("social/spiritual science"),
			_("further education"),
			_("languages")
		),

		# Leisure hobies
		10: (
			_("leisure hobbies (general)"),
			_("tourism/travel"),
			_("handicraft"),
			_("motoring"),
			_("fitness & health"),
			_("cooking"),
			_("advertisement/shopping"),
			_("gardening")
		),
		# Other
		11: (
			_("original language"),
			_("black & white"),
			_("unpublished"),
			_("live broadcast")
		),
	}


class GenresAUS:
	maintype = (
		_("Undefined"),
		_("Movie"),
		_("News"),
		_("Entertainment"),
		_("Sport"),
		_("Childrens"),
		_("Music"),
		_("Arts/Culture"),
		_("Current Affairs"),
		_("Education/Information"),
		_("Infotainment"),
		_("Special"),
		_("Comedy"),
		_("Drama"),
		_("Documentary"),
	)

	subtype = {
		# Movie/Drama
		1: (
			_("movie (general)"),
		),
		# News
		2: (
			_("news (general)"),
		),
		# Entertainment
		3: (
			_("entertainment (general)"),
		),
		# Sport
		4: (
			_("sport (general)"),
		),
		# Childrens
		5: (
			_("childrens (general)"),
		),
		# Music
		6: (
			_("music (general)"),
		),
		# Arts/Culture
		7: (
			_("arts/culture (general)"),
		),
		# Current Affairs
		8: (
			_("current affairs (general)"),
		),
		# Education/Information
		9: (
			_("education/information (general)"),
		),
		# Infotainment
		10: (
			_("infotainment (general)"),
		),
		# Special
		11: (
			_("special (general)"),
		),
		# Comedy
		12: (
			_("comedy (general)"),
		),
		# Drama
		13: (
			_("drama (general)"),
		),
		# Documentary
		14: (
			_("documentary (general)"),
		),
	}


def __getGenreStringMain(hn, ln, genres):
	# if hn == 0:
	# 	return _("Undefined content")
	if hn == 15:
		return _("User defined")
	if 0 < hn < len(genres.maintype):
		return genres.maintype[hn]
	# return _("Reserved") + " " + str(hn)
	return ""


def __getGenreStringSub(hn, ln, genres):
	# if hn == 0:
	# 	return _("Undefined content") + " " + str(ln)
	if hn == 15:
		return _("User defined") + " " + str(ln)
	if 0 < hn < len(genres.maintype):
		if ln == 15:
			return _("User defined")
		if ln < len(genres.subtype[hn]):
			return genres.subtype[hn][ln]
	# 	return _("Reserved") " " + str(ln)
	# return _("Reserved") + " " + str(hn) + "," + str(ln)
	return ""


countries = {
	"AUS": (__getGenreStringMain, __getGenreStringMain, GenresAUS()),
}

defaultGenre = GenresETSI()
defaultCountryInfo = (__getGenreStringMain, __getGenreStringSub, defaultGenre)

# Backwards compatibility - use deprecated

maintype = defaultGenre.maintype
subtype = defaultGenre.subtype


def getGenreStringMain(hn, ln, country=None):
	countryInfo = countries.get(country, defaultCountryInfo)
	return countryInfo[0](hn, ln, countryInfo[2])


def getGenreStringSub(hn, ln, country=None):
	countryInfo = countries.get(country, defaultCountryInfo)
	return countryInfo[1](hn, ln, countryInfo[2])


def getGenreStringLong(hn, ln, country=None):
	# if hn == 0:
	# 	return _("Undefined content") + " " + str(ln)
	if hn == 15:
		return _("User defined") + " " + str(ln)
	main = getGenreStringMain(hn, ln, country=country)
	sub = getGenreStringSub(hn, ln)
	if main and main != sub:
		return main + ": " + sub
	else:
		return main
# 	return _("Reserved") + " " + str(hn) + "," + str(ln)

#
# The End
#
