from Components.Converter.Converter import Converter
from Components.Converter.ConverterTimeHelpers import _fmt_m, _fmt_ms, _fmt_hm, _fmt_hms, _fmt_pct, _fmt_m_bare, _fmt_s, _join, CONFIG_TO_SKIN_FLAGS
from Components.Converter.Poll import Poll
from Components.Element import cached
from Components.config import config


class RemainingToText(Poll, Converter):
	# These are prefixed with "VFD" if used in the context of Front Panel Display
	POLL_INTERVALS = {
		"InMinutes": None,
		"WithSeconds": 1000,
		"NoSeconds": 60 * 1000,
		"InSeconds": 1000,
		"Percentage": 60 * 1000,
		"MinutesSeconds": 1000,
		"OnlyMinutes": 60 * 1000,
	}

	FORMAT_MAP = {
		"InMinutes": _fmt_m,
		"MinutesSeconds": _fmt_ms,
		"NoSeconds": _fmt_hm,
		"WithSeconds": _fmt_hms,
		"OnlyMinutes": _fmt_m_bare,
		"InSeconds": _fmt_s,
		"Percentage": _fmt_pct,
	}

	def __init__(self, type):
		Poll.__init__(self)
		Converter.__init__(self, type)

		if type == "VFD":  # just in case anyone is using the old name
			type = "VFDInMinutes"

		if bool(type and type.startswith("VFD")):
			type = type[3:]  # now we have harvested VFD we discard it
			elapsed_time_positive = config.usage.elapsed_time_positive_vfd.value
			swap_time_remaining = config.usage.swap_time_remaining_on_vfd.value
			display = config.usage.swap_time_display_on_vfd.value
		else:
			elapsed_time_positive = config.usage.elapsed_time_positive_osd.value
			swap_time_remaining = config.usage.swap_time_remaining_on_osd.value
			display = config.usage.swap_time_display_on_osd.value

		if display in CONFIG_TO_SKIN_FLAGS:
			type = CONFIG_TO_SKIN_FLAGS[display]

		if type not in self.POLL_INTERVALS:
			print(
				f"[RemainingToText] Error: unknown converter argument '{type}'. "
				f"Must be one of {'|'.join(sorted([y for x in self.POLL_INTERVALS for y in [x, "VFD" + x]]))}."
			)
			type = "InMinutes"  # default fallback if type is unknown

		poll_interval = self.POLL_INTERVALS[type]

		if poll_interval:
			self.poll_interval = poll_interval
			self.poll_enabled = True

		self.fmt = self.FORMAT_MAP.get(type, _fmt_m)

		self.sign_elapsed, self.sign_remaining = (
			("+", "-") if elapsed_time_positive else ("-", "+")
		)

		self.picker = {
			"0": self._pick_remaining,
			"1": self._pick_elapsed,
			"2": self._pick_both_elapsed_first,
			"3": self._pick_both_remaining_first,
		}.get(swap_time_remaining, self._pick_remaining)

	def _pick_remaining(self, remaining, elapsed):
		return [(self.sign_remaining, remaining)]

	def _pick_elapsed(self, remaining, elapsed):
		return [(self.sign_elapsed, elapsed)]

	def _pick_both_elapsed_first(self, remaining, elapsed):
		return [(self.sign_elapsed, elapsed), (self.sign_remaining, remaining)]

	def _pick_both_remaining_first(self, remaining, elapsed):
		return [(self.sign_remaining, remaining), (self.sign_elapsed, elapsed)]

	@cached
	def getText(self):
		time = self.source.time

		if time is None:
			return ""

		duration, remaining, elapsed = time

		if remaining is None:
			return "" if self.fmt is _fmt_pct else self.fmt(duration)

		pairs = self.picker(remaining, elapsed)

		return _join(pairs, self.fmt, duration)

	text = property(getText)
