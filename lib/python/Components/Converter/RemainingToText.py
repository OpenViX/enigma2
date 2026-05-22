from Components.Converter.Converter import Converter
from Components.Converter.Poll import Poll
from Components.Element import cached
from Components.config import config


class RemainingToText(Poll, Converter):
	DEFAULT = 0
	WITH_SECONDS = 1
	NO_SECONDS = 2
	IN_SECONDS = 3
	PERCENTAGE = 4
	MINUTES_SECONDS = 5
	VFD = 6
	VFD_WITH_SECONDS = 7
	VFD_NO_SECONDS = 8
	VFD_IN_SECONDS = 9
	VFD_PERCENTAGE = 10
	VFD_MINUTES_SECONDS = 11

	TYPES = {
		"InMinutes": (DEFAULT, None),  # Mins
		"WithSeconds": (WITH_SECONDS, 1000),  # Hours Mins Secs
		"NoSeconds": (NO_SECONDS, 60 * 1000),  # Hours Mins
		"InSeconds": (IN_SECONDS, 1000),  # Secs
		"Percentage": (PERCENTAGE, 60 * 1000),  # percentage
		"MinutesSeconds": (MINUTES_SECONDS, 60 * 1000),  # Mins Secs
		"VFD": (VFD, None),  # Mins
		"VFDWithSeconds": (VFD_WITH_SECONDS, 1000),  # Hours Mins Secs
		"VFDNoSeconds": (VFD_NO_SECONDS, 60 * 1000),  # Hours Mins
		"VFDInSeconds": (VFD_IN_SECONDS, 1000),  # Secs
		"VFDPercentage": (VFD_PERCENTAGE, 60 * 1000),  # percentage
		"VFDMinutesSeconds": (VFD_MINUTES_SECONDS, 60 * 1000),  # Mins Secs
	}

	CONFIG_TO_TYPE_MAP = {
		"1": ("InMinutes", "VFD"),
		"2": ("MinutesSeconds", "VFDMinutesSeconds"),
		"3": ("NoSeconds", "VFDNoSeconds"),
		"4": ("WithSeconds", "VFDWithSeconds"),
		"5": ("Percentage", "VFDPercentage"),
	}

	def __init__(self, type):
		Poll.__init__(self)
		Converter.__init__(self, type)

		# if user setting > 0, inject setting into type here before we start
		if is_vfd := bool(type and type.startswith("VFD")):
			self.elapsed_time_positive = config.usage.elapsed_time_positive_vfd.value
			self.swap_time_remaining = config.usage.swap_time_remaining_on_vfd.value
			display = config.usage.swap_time_display_on_vfd.value
		else:
			self.elapsed_time_positive = config.usage.elapsed_time_positive_osd.value
			self.swap_time_remaining = config.usage.swap_time_remaining_on_osd.value
			display = config.usage.swap_time_display_on_osd.value

		if display in self.CONFIG_TO_TYPE_MAP:
			type = self.CONFIG_TO_TYPE_MAP[display][1 if is_vfd else 0]
		# end inject user setting

		if type not in self.TYPES:
			print(f"[RemainingToText] Error: unknown converter argument '{str(type)}'. Must be one of {"|".join(sorted(self.TYPES))}.")
			type = "InMinutes"
		self.type, poll_interval = self.TYPES[type]

		if poll_interval:
			self.poll_interval = poll_interval
			self.poll_enabled = True

	@cached
	def getText(self):
		time = self.source.time
		if time is None:
			return ""

		duration, remaining, elapsed = time

		sign_p, sign_r = ("+", "-") if self.elapsed_time_positive else ("-", "+")
		swap = self.swap_time_remaining

		def pick():
			if remaining is None:
				return [(None, duration)]

			if swap == "1":
				return [(sign_p, elapsed)]
			elif swap == "2":
				return [(sign_p, elapsed), (sign_r, remaining)]
			elif swap == "3":
				return [(sign_r, remaining), (sign_p, elapsed)]
			else:
				return [(sign_r, remaining)]

		def join(pairs, fmt):
			if len(pairs) == 1:
				sign, val = pairs[0]
				return (sign or "") + fmt(val)
			else:
				(s1, v1), (s2, v2) = pairs
				return s1 + fmt(v1) + "  " + s2 + fmt(v2)

		# formatters
		def fmt_m(x):
			return ngettext("%d Min", "%d Mins", x // 60) % (x // 60)

		def fmt_hms(x):
			return "%d:%02d:%02d" % (x // 3600, x % 3600 // 60, x % 60)

		def fmt_hm(x):
			return "%d:%02d" % (x // 3600, x % 3600 // 60)

		def fmt_s(x):
			return "%d " % x

		def fmt_ms(x):
			return "%d:%02d" % (x // 60, x % 60)

		def fmt_pct(x):
			return "%d%%" % int((float(x) / float(duration)) * 100)

		pairs = pick()

		if self.type in (self.DEFAULT, self.VFD):
			return join(pairs, fmt_m) if remaining is not None else fmt_m(duration)

		elif self.type in (self.WITH_SECONDS, self.VFD_WITH_SECONDS):
			return join(pairs, fmt_hms) if remaining is not None else fmt_hms(duration)

		elif self.type in (self.NO_SECONDS, self.VFD_NO_SECONDS):
			return join(pairs, fmt_hm) if remaining is not None else fmt_hm(duration)

		elif self.type in (self.IN_SECONDS, self.VFD_IN_SECONDS):
			return join(pairs, fmt_s) if remaining is not None else fmt_s(duration) + _("Mins")

		elif self.type in (self.MINUTES_SECONDS, self.VFD_MINUTES_SECONDS):
			return join(pairs, fmt_ms) if remaining is not None else fmt_ms(duration)

		elif self.type in (self.PERCENTAGE, self.VFD_PERCENTAGE):
			if remaining is not None and duration:
				if len(pairs) == 1:
					sign, val = pairs[0]
					return sign + fmt_pct(val)
				else:
					(s1, v1), (s2, v2) = pairs
					return s1 + fmt_pct(v1) + "  " + s2 + fmt_pct(v2)

		return ""

	text = property(getText)
