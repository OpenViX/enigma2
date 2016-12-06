from enigma import eDVBVolumecontrol, eTimer
from Tools.Profile import profile
from Screens.Volume import Volume
from Screens.Mute import Mute
from GlobalActions import globalActionMap
from config import config, ConfigSubsection, ConfigInteger

profile("VolumeControl")
#TODO .. move this to a own .py file
class VolumeControl:
	instance = None
	"""Volume control, handles volUp, volDown, volMute actions and display
	a corresponding dialog"""
	def __init__(self, session):
		global globalActionMap
		globalActionMap.actions["volumeUp"]=self.volUp
		globalActionMap.actions["volumeDown"]=self.volDown
		globalActionMap.actions["volumeMute"]=self.volMute

		assert not VolumeControl.instance, "only one VolumeControl instance is allowed!"
		VolumeControl.instance = self

		config.audio = ConfigSubsection()
		config.audio.volume = ConfigInteger(default = 100, limits = (0, 100))

		self.volumeDialog = session.instantiateDialog(Volume)
		self.volumeDialog.setAnimationMode(0)
		self.muteDialog = session.instantiateDialog(Mute)
		self.muteDialog.setAnimationMode(0)

		self.hideVolTimer = eTimer()
		self.hideVolTimer.callback.append(self.volHide)

		vol = config.audio.volume.value
		self.volumeDialog.setValue(vol)
		self.volctrl = eDVBVolumecontrol.getInstance()
		self.volctrl.setVolume(vol, vol)

	def volSave(self):
		if self.volctrl.isMuted():
			config.audio.volume.value = 0
		else:
			config.audio.volume.value = self.volctrl.getVolume()
		config.audio.volume.save()

	def volUp(self):
		self.setVolume(+1)

	def volDown(self):
		self.setVolume(-1)

	def setVolume(self, direction):
		oldvol = self.volctrl.getVolume()
		if direction > 0:
			self.volctrl.volumeUp()
		else:
			self.volctrl.volumeDown()
		is_muted = self.volctrl.isMuted()
		vol = self.volctrl.getVolume()
		self.volumeDialog.show()
		if is_muted:
			self.volMute() # unmute
		elif not vol:
			self.volMute(False, True) # mute but dont show mute symbol
		if self.volctrl.isMuted():
			self.volumeDialog.setValue(0)
		else:
			self.volumeDialog.setValue(self.volctrl.getVolume())
		self.volSave()
		self.hideVolTimer.start(3000, True)

	def volHide(self):
		self.volumeDialog.hide()
		self.muteDialog.hide()

	def showMute(self):
		if self.volctrl.isMuted():
			self.muteDialog.show()
			self.hideVolTimer.start(3000, True)

	def volMute(self, showMuteSymbol=True, force=False):
		vol = self.volctrl.getVolume()
		if vol or force:
			self.volctrl.volumeToggleMute()
			if self.volctrl.isMuted():
				if showMuteSymbol:
					self.showMute()
					self.volumeDialog.hide()
				self.volumeDialog.setValue(0)
			else:
				self.muteDialog.hide()
				self.volumeDialog.setValue(vol)
				self.volumeDialog.show()
				self.hideVolTimer.start(3000, True)
