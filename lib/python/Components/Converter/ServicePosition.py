from enigma import iPlayableService, iPlayableServicePtr

from Components.config import config
from Components.Converter.Converter import Converter
from Components.Converter.ConverterTimeHelpers import _fmt_m, _fmt_ms, _fmt_hm, _fmt_hms, _fmt_pct, _fmt_m_bare, _fmt_s, _join, CONFIG_TO_SKIN_FLAGS
from Components.Converter.Poll import Poll
from Components.Element import cached, ElementError


def _fmt_ticks_hms(x, duration=None):
	return "%d:%02d:%02d:%03d" % (x // 3600 // 90000, (x // 90000) % 3600 // 60, (x // 90000) % 60, (x % 90000) // 90)


def _fmt_ticks_ms(x, duration=None):
	return "%d:%02d:%03d" % (x // 60 // 90000, (x // 90000) % 60, (x % 90000) // 90)


class ServicePosition(Poll, Converter):
	TYPE_LENGTH = 0
	TYPE_POSITION = 1
	TYPE_REMAINING = 2
	TYPE_GAUGE = 3
	TYPE_SUMMARY = 4

	# These are prefixed with "VFD" if used in the context of Front Panel Display
	TYPES = {
		"Length": TYPE_LENGTH,
		"Position": TYPE_POSITION,
		"Remaining": TYPE_REMAINING,
		"Gauge": TYPE_GAUGE,
		"Summary": TYPE_SUMMARY,
	}

	# skin values -> formatter
	FMT_BY_DISPLAY = {"InMinutes": _fmt_m, "MinutesSeconds": _fmt_ms, "NoSeconds": _fmt_hm, "WithSeconds": _fmt_hms, "OnlyMinutes": _fmt_m_bare, "Percentage": _fmt_pct, }

	# self.fmt -> (formatter to use for Length, whether to prefix sign_l).
	# Keyed by the resolved formatter function itself (not the "display"
	# string that picked it), so this applies no matter which path landed
	# on that formatter - config-driven display, skin literal-name override,
	# or FMT_BY_SKIN_FLAGS - and is automatically skipped for detailed mode,
	# whose ticks formatters are never in this table.
	LENGTH_FORMAT_OVERRIDES = {
		_fmt_pct: (_fmt_hm, True),
		_fmt_m: (_fmt_m, False),
	}

	CONFIG_TO_SKIN_FLAGS = {
		"1": "InMinutes",
		"2": "MinutesSeconds",
		"3": "NoSeconds",
		"4": "WithSeconds",
		"5": "Percentage",
		"6": "OnlyMinutes",
	}

	# (showHours, showNoSeconds) skin flags -> formatter, used only when
	# swap_media_time_display is "0"/unset (Skin Setting mode), and no
	# other args found via the skin (see CONFIG_TO_SKIN_FLAGS values)
	FMT_BY_SKIN_FLAGS = {(True, True): _fmt_hm, (True, False): _fmt_hms, (False, True): _fmt_m, (False, False): _fmt_ms}

	# swap_time_remaining config value -> which pair(s) to show, for a
	# Position-type and a Remaining-type converter respectively. Remaining
	# shows nothing (blank) at swap 2/3; Position shows a combined pair -
	# matches the original exactly.
	PICKER_BY_SWAP_POSITION = {"0": "_pick_remaining_only", "1": "_pick_elapsed_only", "2": "_pick_both_elapsed_first", "3": "_pick_both_remaining_first"}
	PICKER_BY_SWAP_REMAINING = {"0": "_pick_remaining_only", "1": "_pick_elapsed_only", "2": "_pick_blank", "3": "_pick_blank"}

	def __init__(self, type):
		Poll.__init__(self)
		Converter.__init__(self, type)
		args = type.split(',')
		type = args.pop(0)

		self.negate = "Negate" in args
		self.detailed = "Detailed" in args
		showHours = "ShowHours" in args
		showNoSeconds = "ShowNoSeconds" in args

		self.is_vfd = bool(type and type.startswith("VFD"))
		if self.is_vfd:
			type = type[3:]  # now we have harvested VFD we discard it
			elapsed_time_positive = config.usage.elapsed_time_positive_vfd.value
			swap = config.usage.swap_time_remaining_on_vfd.value
			display = CONFIG_TO_SKIN_FLAGS.get(config.usage.swap_media_time_display_on_vfd.value)
		else:
			elapsed_time_positive = config.usage.elapsed_time_positive_osd.value
			swap = config.usage.swap_time_remaining_on_osd.value
			display = CONFIG_TO_SKIN_FLAGS.get(config.usage.swap_media_time_display_on_osd.value)

		# Note: if "display_from_config" is 0 ("Skin Setting") the value of "swap_time_remaining" will
		# be ignored. This was the original behaviour and has been retain here even though doing so
		# may be questionable.
		display_from_config = bool(display)
		if not display_from_config:  # inject skin display args; config takes priority over skin arguments
			for arg in args:
				if arg in CONFIG_TO_SKIN_FLAGS.values():
					display = arg
					break

		if type not in self.TYPES:
			raise ElementError(
				f"[ServicePosition] Error: unknown converter argument '{type}'. "
				f"Must be one of {'|'.join(sorted([y for x in self.TYPES for y in [x, "VFD" + x]]))}, "
				f"with optional arguments Negate|Detailed|ShowHours|ShowNoSeconds|{'|'.join(sorted(CONFIG_TO_SKIN_FLAGS.values()))}."
			)
		self.type = self.TYPES[type]

		# elapsed/remaining signs are purely config-driven (the original also
		# derived a sign from live Negate'd values for p/r, but always overwrote
		# it with this config-driven pair immediately afterwards - that live
		# computation was dead code, and has been removed from getText()).
		self.sign_p, self.sign_r = ("+", "-") if elapsed_time_positive else ("-", "+")

		# resolve display MODE and formatter, once. Formatters are plain
		# module-level functions (not bound methods), so later lookups
		# keyed by the formatter itself (LENGTH_FORMAT_OVERRIDES, in
		# getText) are safe and reliable - repeated access to a bound
		# method returns a new object each time in CPython, so that
		# wouldn't work if these were instance methods.
		# "self.detailed" is a special override. It can be used in combination
		# with "ShowHours". All other arguments (including from user config)
		# will be discarded.
		picker_name = None
		if self.detailed:
			self.fmt = _fmt_ticks_hms if showHours else _fmt_ticks_ms
		else:
			if display_from_config:
				# resolve which pair(s) to show, once - only meaningful for
				# Position/Remaining; Length/Gauge/Summary never use it. Pickers DO
				# need to be bound methods (they read self.sign_p/self.sign_r), so
				# they're resolved via getattr, unlike the formatters above.
				if self.type == self.TYPE_POSITION:
					picker_name = self.PICKER_BY_SWAP_POSITION.get(swap)
				elif self.type == self.TYPE_REMAINING:
					picker_name = self.PICKER_BY_SWAP_REMAINING.get(swap)
			if display in self.FMT_BY_DISPLAY:
				self.fmt = self.FMT_BY_DISPLAY[display]
			else:
				self.fmt = self.FMT_BY_SKIN_FLAGS[(showHours, showNoSeconds)]

		# Skin-Setting/detailed mode (no swap-driven picker resolved above):
		# Position always shows elapsed, Remaining always shows remaining -
		# same single-value-pair mechanism as the config-driven case above,
		# just fixed rather than swap-selected.
		if picker_name is None:
			if self.type == self.TYPE_POSITION:
				picker_name = "_pick_elapsed_only"
			elif self.type == self.TYPE_REMAINING:
				picker_name = "_pick_remaining_only"

		self.picker = getattr(self, picker_name) if picker_name else None

		if self.detailed:
			self.poll_interval = 100
		elif self.type == self.TYPE_LENGTH:
			self.poll_interval = 2000
		else:
			self.poll_interval = 500

		self.poll_enabled = True

	def getSeek(self):
		s = self.source.service
		if isinstance(s, iPlayableServicePtr):
			return s and s.seek()
		return None

	@cached
	def getPosition(self):
		seek = self.getSeek()
		if seek is None:
			return None
		pos = seek.getPlayPosition()
		if pos[0]:
			return 0
		return max(0, pos[1])  # seek.getPlayPosition() can return negative bogus values. Correct that.

	@cached
	def getLength(self):
		seek = self.getSeek()
		if seek is None:
			return None
		length = seek.getLength()
		if length[0]:
			return 0
		return length[1]

	@cached
	def getCutlist(self):
		service = self.source.service
		cue = service and isinstance(service, iPlayableServicePtr) and service.cueSheet()
		return cue and cue.getCutList()

	# --- pickers (which (sign, value) pairs to show) - instance methods
	# since they need self.sign_p/self.sign_r ---

	def _pick_remaining_only(self, remaining, elapsed):
		return [(self.sign_r, remaining)]

	def _pick_elapsed_only(self, remaining, elapsed):
		return [(self.sign_p, elapsed)]

	def _pick_both_elapsed_first(self, remaining, elapsed):
		return [(self.sign_p, elapsed), (self.sign_r, remaining)]

	def _pick_both_remaining_first(self, remaining, elapsed):
		return [(self.sign_r, remaining), (self.sign_p, elapsed)]

	def _pick_blank(self, remaining, elapsed):
		# display nothing, same as the original
		return None

	@cached
	def getText(self):
		seek = self.getSeek()
		if seek is None:
			return ""

		if self.type == self.TYPE_SUMMARY:
			s = self.position // 90000
			e = (self.length // 90000) - s
			return "%02d:%02d +%2dm" % (s // 60, s % 60, e // 60)

		if self.type == self.TYPE_GAUGE:
			return ""

		length = self.length
		p = self.position
		r = length - p

		if length < 0:
			return ""

		if not self.detailed:
			length //= 90000
			p //= 90000
			r //= 90000

		# sign_l was only populated in the original implementation when self.negate was
		# True and only for VFD. That behaviour persists here.
		sign_l = "-" if self.negate and self.is_vfd and length > 0 else ""

		if self.type == self.TYPE_LENGTH:
			fmt, include_sign = self.LENGTH_FORMAT_OVERRIDES.get(self.fmt, (self.fmt, True))
			sign = sign_l if include_sign else ""
			return sign + fmt(length)

		# self.type is TYPE_POSITION or TYPE_REMAINING here (TYPE_LENGTH/
		# GAUGE/SUMMARY already returned above); self.picker is always set
		# for those two types - see __init__.
		return _join(self.picker(r, p), self.fmt, length)

	# range/value are for the Progress renderer
	range = 10000

	@cached
	def getValue(self):
		pos = self.position
		length = self.length
		if pos is None or length is None or length <= 0:
			return None
		return pos * 10000 // length

	position = property(getPosition)
	length = property(getLength)
	cutlist = property(getCutlist)
	text = property(getText)
	value = property(getValue)

	def changed(self, what):
		cutlist_refresh = what[0] != self.CHANGED_SPECIFIC or what[1] in (iPlayableService.evCuesheetChanged,)
		time_refresh = what[0] == self.CHANGED_POLL or what[0] == self.CHANGED_SPECIFIC and what[1] in (iPlayableService.evCuesheetChanged,)

		if cutlist_refresh:
			if self.type == self.TYPE_GAUGE:
				self.downstream_elements.cutlist_changed()

		if time_refresh:
			self.downstream_elements.changed(what)
