def _fmt_m(value, duration=None):
	return ngettext("%d Min", "%d Mins", value // 60) % (value // 60)


def _fmt_m_bare(value, duration=None):
	return "%d" % (value // 60)


def _fmt_hms(value, duration=None):
	return "%d:%02d:%02d" % (value // 3600, value % 3600 // 60, value % 60)


def _fmt_hm(value, duration=None):
	return "%d:%02d" % (value // 3600, value % 3600 // 60)


def _fmt_s(value, duration=None):
	return "%d" % value


def _fmt_ms(value, duration=None):
	return "%d:%02d" % (value // 60, value % 60)


def _fmt_pct(value, duration):
	if not duration:  # avoid divide by zero
		return None
	return f"{int(round(value * 100 / duration))}%"


def _join(pairs, fmt, duration=None):
	if not pairs:
		return ""
	if len(pairs) == 1:
		sign, value = pairs[0]
		text = fmt(value, duration)
		return "" if text is None else sign + text
	(s1, v1), (s2, v2) = pairs
	t1, t2 = fmt(v1, duration), fmt(v2, duration)
	if t1 is None or t2 is None:
		return ""
	return s1 + t1 + "  " + s2 + t2

# Numeric "swap_media_time_display_*" configuration values mapped to the
# equivalent skin display arguments.
CONFIG_TO_SKIN_FLAGS = {
	"1": "InMinutes",
	"2": "MinutesSeconds",
	"3": "NoSeconds",
	"4": "WithSeconds",
	"5": "Percentage",
	"6": "OnlyMinutes",
}