from sys import maxsize

from enigma import eTimer, getDesktop, eActionMap, gFont, gRGB
from Components.Label import Label
from Components.config import config
from Screens.Screen import Screen
from skin import subtitleFonts, parseFont, getSkinFactor
import skin  # noqa: F401


class SubtitleDisplay(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		eActionMap.getInstance().bindAction('', -maxsize - 1, self.__keypress)

		self.subtitlesShown = False
		self['subtitles'] = Label()
		self['subtitles'].hide()

		self.onClose.append(self.__close)
		self.onLayoutFinish.append(self.__layoutFinished)

	def __close(self):
		eActionMap.getInstance().unbindAction('', self.__keypress)

	def __layoutFinished(self):
		# Not expecting skins to contain this element
		regular_font = subtitleFonts.get("Subtitle_Regular", {})
		label = self['subtitles']
		font_size = int(config.subtitles.subtitle_fontsize.value)
		font_face = regular_font.get("font_face", "Regular")
		font = parseFont(f"{font_face};{font_size * getSkinFactor()}")
		label.instance.setFont(font)
		label.instance.setZPosition(1)
		label.instance.setNoWrap(1)
		label.instance.setHAlign(1)
		label.instance.setVAlign(1)
		label.instance.setBackgroundColor(gRGB(0xff000000))
		foreColor_conf = config.subtitles.pango_subtitle_colors.value
		if foreColor_conf == "2":
			label.instance.setForegroundColor(gRGB(0x00ffff00))
		border_width = regular_font.get("borderWidth", 0)
		border_color = regular_font.get("borderColor", None)
		if border_width > 0 and border_color:
			label.instance.setBorderWidth(border_width)
			label.instance.setBorderColor(border_color)

	def __keypress(self, key, flag):
		# Releasing the subtitle button after a long press unintentionally pops up the subtitle dialog,
		# This blocks it without causing issues for anyone that sets the buttons up the other way round
		if self.subtitlesShown:
			# whilst the notification is shown any keydown event dismisses the notification
			if flag == 0:
				self.hideSubtitles()
			else:  # any key repeat or keyup event is discarded
				return 1

	def showSubtitles(self, subtitles):
		padding = (40, 10)
		label = self['subtitles']
		label.setText(subtitles)
		size = label.getSize()
		label.resize(size[0] + padding[0] * 2, size[1] + padding[1] * 2)
		label.move((getDesktop(0).size().width() - size[0] - padding[0]) // 2, getDesktop(0).size().height() - size[1] - padding[1] * 2 - 30)
		label.show()
		self.subtitlesShown = True
		self.show()

	def hideSubtitles(self):
		self.subtitlesShown = False
		self['subtitles'].hide()

	def hideScreen(self):
		self.hideSubtitles()
		self.hide()
