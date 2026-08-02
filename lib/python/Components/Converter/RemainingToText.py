from Components.Converter.Converter import Converter
from Components.Converter.Poll import Poll
from Components.Element import cached
from Components.config import config


def _fmt_m(value):
	return ngettext("%d Min", "%d Mins", value // 60) % (value // 60)


def _fmt_m_bare(value):
	return "%d" % (value // 60)


def _fmt_hms(value):
	return "%d:%02d:%02d" % (value // 3600, value % 3600 // 60, value % 60)


def _fmt_hm(value):
	return "%d:%02d" % (value // 3600, value % 3600 // 60)


def _fmt_s(value):
	return "%d " % value


def _fmt_ms(value):
	return "%d:%02d" % (value // 60, value % 60)


def _fmt_pct(value, duration):
	return "%d%%" % int((float(value) / float(duration)) * 100)


class RemainingToText(Poll, Converter):
	# These are prefixed with "VFD" if used in the context of Front Panel Display
	INTERVALS = {
		"InMinutes": None,
		"WithSeconds": 1000,
		"NoSeconds": 60 * 1000,
		"InSeconds": 1000,
		"Percentage": 60 * 1000,
		"MinutesSeconds": 1000,
		"OnlyMinutes": 60 * 1000,
	}

	CONFIG_TO_TYPE_MAP = {
		"1": "InMinutes",
		"2": "MinutesSeconds",
		"3": "NoSeconds",
		"4": "WithSeconds",
		"5": "Percentage",
		"6": "OnlyMinutes",
		# "InSeconds" is not currently a config option
	}

	FORMAT_MAP = {
		"InMinutes": _fmt_m,
		"MinutesSeconds": _fmt_ms,
		"NoSeconds": _fmt_hm,
		"WithSeconds": _fmt_hms,
		"OnlyMinutes": _fmt_m_bare,
		"InSeconds": _fmt_s,
		# self.formatter is not used for "Percentage"
	}

	def __init__(self, type):
		Poll.__init__(self)
		Converter.__init__(self, type)

		if type == "VFD":  # just in case anyone is using the old name
			type = "VFDInMinutes"

		if bool(type and type.startswith("VFD")):
			type = type[3:]  # now we have harvested VFD we discard it
			self.elapsed_time_positive = config.usage.elapsed_time_positive_vfd.value
			self.swap_time_remaining = config.usage.swap_time_remaining_on_vfd.value
			display = config.usage.swap_time_display_on_vfd.value
		else:
			self.elapsed_time_positive = config.usage.elapsed_time_positive_osd.value
			self.swap_time_remaining = config.usage.swap_time_remaining_on_osd.value
			display = config.usage.swap_time_display_on_osd.value

		if display in self.CONFIG_TO_TYPE_MAP:
			type = self.CONFIG_TO_TYPE_MAP[display]

		if type not in self.INTERVALS:
			print(
				f"[RemainingToText] Error: unknown converter argument '{type}'. "
				f"Must be one of {'|'.join(sorted([y for x in self.INTERVALS for y in [x, "VFD" + x]]))}."
			)
			type = "InMinutes"  # default fallback if type is unknown

		poll_interval = self.INTERVALS[type]

		if poll_interval:
			self.poll_interval = poll_interval
			self.poll_enabled = True

		self.is_percentage = type == "Percentage"
		self.formatter = self.FORMAT_MAP.get(type, _fmt_m)

		self.sign_elapsed, self.sign_remaining = (
			("+", "-") if self.elapsed_time_positive else ("-", "+")
		)

		self.picker = self._select_picker()

	def _select_picker(self):
		if self.swap_time_remaining == "1":
			return self._pick_elapsed

		if self.swap_time_remaining == "2":
			return self._pick_both_elapsed_first

		if self.swap_time_remaining == "3":
			return self._pick_both_remaining_first

		return self._pick_remaining

	def _pick_remaining(self, remaining, elapsed):
		return [(self.sign_remaining, remaining)]

	def _pick_elapsed(self, remaining, elapsed):
		return [(self.sign_elapsed, elapsed)]

	def _pick_both_elapsed_first(self, remaining, elapsed):
		return [(self.sign_elapsed, elapsed), (self.sign_remaining, remaining)]

	def _pick_both_remaining_first(self, remaining, elapsed):
		return [(self.sign_remaining, remaining), (self.sign_elapsed, elapsed)]

	def _join(self, pairs):
		if len(pairs) == 1:
			sign, value = pairs[0]
			return (sign or "") + self.formatter(value)

		(s1, v1), (s2, v2) = pairs
		return (s1 + self.formatter(v1) + "  " + s2 + self.formatter(v2))

	def _join_percentage(self, pairs, duration):
		if not duration:  # avoid divide by zero
			return ""
		if len(pairs) == 1:
			sign, value = pairs[0]
			return sign + _fmt_pct(value, duration)

		(s1, v1), (s2, v2) = pairs
		return (s1 + _fmt_pct(v1, duration) + "  " + s2 + _fmt_pct(v2, duration))

	@cached
	def getText(self):
		time = self.source.time

		if time is None:
			return ""

		duration, remaining, elapsed = time

		if remaining is None:
			if self.is_percentage:
				return ""

			return self.formatter(duration)

		if self.is_percentage and not duration:
			return ""

		pairs = self.picker(remaining, elapsed)

		if self.is_percentage:
			return self._join_percentage(pairs, duration)

		return self._join(pairs)

	text = property(getText)
