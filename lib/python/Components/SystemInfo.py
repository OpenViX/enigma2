from enigma import Misc_Options, eDVBCIInterfaces, eDVBResourceManager
from Tools.Directories import SCOPE_PLUGINS, SCOPE_SKIN, fileCheck, fileExists, fileHas, pathExists, resolveFilename
from Tools.HardwareInfo import HardwareInfo
from boxbranding import getBoxType, getMachineBuild, getBrandOEM, getMachineMtdRoot

SystemInfo = {}
SystemInfo["HasRootSubdir"] = False	# This needs to be here so it can be reset by getMultibootslots!
SystemInfo["RecoveryMode"] = False or fileCheck("/proc/stb/fp/boot_mode")	# This needs to be here so it can be reset by getMultibootslots!
from Tools.Multiboot import getMBbootdevice, getMultibootslots  # This import needs to be here to avoid a SystemInfo load loop!

def getNumVideoDecoders():
	number_of_video_decoders = 0
	while fileExists("/dev/dvb/adapter0/video%d" % (number_of_video_decoders), 'f'):
		number_of_video_decoders += 1
	return number_of_video_decoders

def countFrontpanelLEDs():
	number_of_leds = fileExists("/proc/stb/fp/led_set_pattern") and 1 or 0
	while fileExists("/proc/stb/fp/led%d_pattern" % number_of_leds):
		number_of_leds += 1
	return number_of_leds

def getHasTuners():
	if fileExists("/proc/bus/nim_sockets"):
		nimfile = open("/proc/bus/nim_sockets")
		data = nimfile.read().strip()
		nimfile.close()
		return len(data) > 0
	return False

SystemInfo["CommonInterface"] = eDVBCIInterfaces.getInstance().getNumOfSlots()
SystemInfo["CommonInterfaceCIDelay"] = fileCheck("/proc/stb/tsmux/rmx_delay")
for cislot in range(0, SystemInfo["CommonInterface"]):
	SystemInfo["CI%dSupportsHighBitrates" % cislot] = fileCheck("/proc/stb/tsmux/ci%d_tsclk" % cislot)
	SystemInfo["CI%dRelevantPidsRoutingSupport" % cislot] = fileCheck("/proc/stb/tsmux/ci%d_relevant_pids_routing" % cislot)

SystemInfo["NumVideoDecoders"] = getNumVideoDecoders()
SystemInfo["PIPAvailable"] = SystemInfo["NumVideoDecoders"] > 1
SystemInfo["CanMeasureFrontendInputPower"] = eDVBResourceManager.getInstance().canMeasureFrontendInputPower()
SystemInfo["12V_Output"] = Misc_Options.getInstance().detected_12V_output()
SystemInfo["ZapMode"] = fileCheck("/proc/stb/video/zapmode") or fileCheck("/proc/stb/video/zapping_mode")
SystemInfo["NumFrontpanelLEDs"] = countFrontpanelLEDs()
SystemInfo["FrontpanelDisplay"] = fileExists("/dev/dbox/oled0") or fileExists("/dev/dbox/lcd0")
SystemInfo["LCDsymbol_circle_recording"] = fileCheck("/proc/stb/lcd/symbol_circle") or getBoxType() in ("hd51", "vs1500") and fileCheck("/proc/stb/lcd/symbol_recording")
SystemInfo["LCDsymbol_timeshift"] = fileCheck("/proc/stb/lcd/symbol_timeshift")
SystemInfo["LCDshow_symbols"] = (getBoxType().startswith("et9") or getBoxType() in ("hd51", "vs1500")) and fileCheck("/proc/stb/lcd/show_symbols")
SystemInfo["LCDsymbol_hdd"] = getBoxType() in ("hd51", "vs1500") and fileCheck("/proc/stb/lcd/symbol_hdd")
SystemInfo["DeepstandbySupport"] = getBoxType() != "dm800"
SystemInfo["OledDisplay"] = fileExists(resolveFilename(SCOPE_SKIN, 'display/lcd_skin/skin_lcd_default.xml'))
SystemInfo["GBWOL"] = fileExists("/usr/bin/gigablue_wol")
SystemInfo["Fan"] = fileCheck("/proc/stb/fp/fan")
SystemInfo["FanPWM"] = SystemInfo["Fan"] and fileCheck("/proc/stb/fp/fan_pwm")
SystemInfo["PowerLED"] = fileCheck("/proc/stb/power/powerled")
SystemInfo["StandbyLED"] = fileCheck("/proc/stb/power/standbyled")
SystemInfo["SuspendLED"] = fileCheck("/proc/stb/power/suspendled")
SystemInfo["Display"] = SystemInfo["FrontpanelDisplay"] or SystemInfo["StandbyLED"]
SystemInfo["LedPowerColor"] = fileCheck("/proc/stb/fp/ledpowercolor")
SystemInfo["LedStandbyColor"] = fileCheck("/proc/stb/fp/ledstandbycolor")
SystemInfo["LedSuspendColor"] = fileCheck("/proc/stb/fp/ledsuspendledcolor")
SystemInfo["Power4x7On"] = fileCheck("/proc/stb/fp/power4x7on")
SystemInfo["Power4x7Standby"] = fileCheck("/proc/stb/fp/power4x7standby")
SystemInfo["Power4x7Suspend"] = fileCheck("/proc/stb/fp/power4x7suspend")
SystemInfo["PowerOffDisplay"] = getBoxType() not in ('formuler1', ) and fileCheck("/proc/stb/power/vfd") or fileCheck("/proc/stb/lcd/vfd")
SystemInfo["WakeOnLAN"] = getBoxType() not in ('et8000', )and fileCheck("/proc/stb/power/wol") or fileCheck("/proc/stb/fp/wol")
SystemInfo["HasExternalPIP"] = getMachineBuild() not in ('et9x00', 'et6x00', 'et5x00') and fileCheck("/proc/stb/vmpeg/1/external")
SystemInfo["VideoDestinationConfigurable"] = fileExists("/proc/stb/vmpeg/0/dst_left")
SystemInfo["hasPIPVisibleProc"] = fileCheck("/proc/stb/vmpeg/1/visible")
SystemInfo["hasTuners"] = getHasTuners() or fileCheck("/usr/lib/enigma2/python/Plugins/SystemPlugins/SatipClient/plugin.pyo")
SystemInfo["hasGBIpboxClient"] = fileExists(resolveFilename(SCOPE_PLUGINS, "Extensions/GBIpboxClient/plugin.pyo"))

#if getBoxType() in ('gbquadplus', ):
#	SystemInfo["WakeOnLAN"] = False
#else:
SystemInfo["WakeOnLAN"] = fileCheck("/proc/stb/fp/wol")

SystemInfo["VFD_scroll_repeats"] = fileCheck("/proc/stb/lcd/scroll_repeats")
SystemInfo["VFD_scroll_delay"] = fileCheck("/proc/stb/lcd/scroll_delay")
SystemInfo["VFD_initial_scroll_delay"] = fileCheck("/proc/stb/lcd/initial_scroll_delay")
SystemInfo["VFD_final_scroll_delay"] = fileCheck("/proc/stb/lcd/final_scroll_delay")
SystemInfo["LcdLiveTV"] = fileCheck("/proc/stb/fb/sd_detach") or fileCheck("/proc/stb/lcd/live_enable")
SystemInfo["LcdLiveTVMode"] = fileCheck("/proc/stb/lcd/mode")
SystemInfo["LcdLiveDecoder"] = fileCheck("/proc/stb/lcd/live_decoder")
SystemInfo["3DMode"] = fileCheck("/proc/stb/fb/primary/3d")
SystemInfo["Blindscan_t2_available"] = fileCheck("/proc/stb/info/vumodel")
SystemInfo["Bootvideo"] = fileCheck("/usr/bin/bootvideo")
SystemInfo["hasOSDAnimation"] = fileCheck("/proc/stb/fb/animation_mode")
SystemInfo["RcTypeChangable"] = pathExists('/proc/stb/ir/rc/type')
SystemInfo["HasFullHDSkinSupport"] = getBoxType() not in ('gb800solo', 'gb800se', 'gb800ue')
SystemInfo["HasBypassEdidChecking"] = fileCheck("/proc/stb/hdmi/bypass_edid_checking")
SystemInfo["HasColorspace"] = fileCheck("/proc/stb/video/hdmi_colorspace")
SystemInfo["HasColorspaceSimple"] = SystemInfo["HasColorspace"] and getBoxType() in ('vusolo4k', )
SystemInfo["HasMultichannelPCM"] = fileCheck("/proc/stb/audio/multichannel_pcm")
SystemInfo["CanNotDoSimultaneousTranscodeAndPIP"] = getBoxType() in ('vusolo4k') or getMachineBuild() in ('gb7252', 'gb72604')
SystemInfo["HasColordepth"] = fileCheck("/proc/stb/video/hdmi_colordepth")
SystemInfo["HasFrontDisplayPicon"] = getBoxType() in ("vusolo4k", "et8500")
SystemInfo["Has24hz"] = fileCheck("/proc/stb/video/videomode_24hz")
SystemInfo["Has2160p"] = fileHas("/proc/stb/video/videomode_preferred", "2160p50")
SystemInfo["HasHDMIpreemphasis"] = fileCheck("/proc/stb/hdmi/preemphasis")
SystemInfo["HasColorimetry"] = fileCheck("/proc/stb/video/hdmi_colorimetry")
SystemInfo["HasHDMI-CEC"] = HardwareInfo().has_hdmi() and fileExists(resolveFilename(SCOPE_PLUGINS, "SystemPlugins/HdmiCEC/plugin.pyo")) and (fileExists("/dev/cec0") or fileExists("/dev/hdmi_cec") or fileExists("/dev/misc/hdmi_cec0"))
SystemInfo["HasHdrType"] = fileCheck("/proc/stb/video/hdmi_hdrtype")
SystemInfo["HasYPbPr"] = getMachineBuild() in ('gb7356', 'gb7325') or getBoxType() in ('gbultraue', 'gbultraueh', 'gb800ueplus', 'gb800seplus')
SystemInfo["HasScart"] = getMachineBuild() in ('gb7325', )
SystemInfo["HasSVideo"] = getMachineBuild() in ('dummy', )
SystemInfo["HasComposite"] = getMachineBuild() in ('gb7356', 'gb7358', 'gb7325') or getBoxType() in ('gbultraue', 'gbultraueh')
SystemInfo["HasAutoVolume"] = fileExists("/proc/stb/audio/avl_choices") and fileCheck("/proc/stb/audio/avl")
SystemInfo["HasAutoVolumeLevel"] = fileExists("/proc/stb/audio/autovolumelevel_choices") and fileCheck("/proc/stb/audio/autovolumelevel")
SystemInfo["Has3DSurround"] = fileExists("/proc/stb/audio/3d_surround_choices") and fileCheck("/proc/stb/audio/3d_surround")
SystemInfo["Has3DSpeaker"] = fileExists("/proc/stb/audio/3d_surround_speaker_position_choices") and fileCheck("/proc/stb/audio/3d_surround_speaker_position")
SystemInfo["Has3DSurroundSpeaker"] = fileExists("/proc/stb/audio/3dsurround_choices") and fileCheck("/proc/stb/audio/3dsurround")
SystemInfo["Has3DSurroundSoftLimiter"] = fileExists("/proc/stb/audio/3dsurround_softlimiter_choices") and fileCheck("/proc/stb/audio/3dsurround_softlimiter")
SystemInfo["HasHDMI-In"] = getBoxType() in ('gbquad4k', )
SystemInfo["hasXcoreVFD"] = fileCheck("/sys/module/brcmstb_%s/parameters/pt6302_cgram" % getBoxType())
SystemInfo["CanDownmixWMApro"] = fileExists("/proc/stb/audio/wmapro_choices") or fileExists("/proc/stb/audio/wmapro")
SystemInfo["CanAACTranscode"] = fileExists("/proc/stb/audio/aac_transcode_choices") or fileExists("/proc/stb/audio/aac_transcode")
SystemInfo["HDRSupport"] = fileExists("/proc/stb/hdmi/hlg_support_choices") or fileExists("/proc/stb/hdmi/hlg_support")
SystemInfo["CanDownmixAC3"] = fileHas("/proc/stb/audio/ac3_choices", "downmix")
SystemInfo["CanDownmixAC3Plus"] = fileHas("/proc/stb/audio/ac3plus_choices", "downmix")
SystemInfo["CanDownmixDTS"] = fileHas("/proc/stb/audio/dts_choices", "downmix")
SystemInfo["CanDownmixDTSHD"] = fileHas("/proc/stb/audio/dtshd_choices", "downmix")
SystemInfo["CanDownmixAAC"] = fileHas("/proc/stb/audio/aac_choices", "downmix")
SystemInfo["CanDownmixAACPlus"] = fileHas("/proc/stb/audio/aacplus_choices", "downmix")
SystemInfo["HDMIAudioSource"] = fileCheck("/proc/stb/hdmi/audio_source")
SystemInfo["MBbootdevice"] = getMBbootdevice()
SystemInfo["canMultiBoot"] = getMultibootslots()
SystemInfo["canMode12"] = getMachineBuild() in ('hd51','vs1500','h7') and ('brcm_cma=440M@328M brcm_cma=192M@768M', 'brcm_cma=520M@248M brcm_cma=200M@768M')
SystemInfo["HAScmdline"] = fileCheck("/boot/cmdline.txt")
SystemInfo["HasMMC"] = fileHas("/proc/cmdline", "root=/dev/mmcblk") or SystemInfo["canMultiBoot"] and fileHas("/proc/cmdline", "root=/dev/sda")
SystemInfo["HasSDmmc"] = SystemInfo["canMultiBoot"] and "sd" in SystemInfo["canMultiBoot"][2] and "mmcblk" in getMachineMtdRoot()
SystemInfo["canRecovery"] = getMachineBuild() in ('gbmv200',) and ('usb_update.bin','none')
SystemInfo["FbcTunerPowerAlwaysOn"] = getBoxType() in ('vusolo4k', 'vuduo4k', 'vuultimo4k') or getMachineBuild() in ('gb7252')
