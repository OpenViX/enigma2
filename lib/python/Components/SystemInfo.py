from enigma import eDVBResourceManager, Misc_Options, eDVBCIInterfaces
from Tools.Directories import fileExists, fileCheck, pathExists, fileHas
from Tools.HardwareInfo import HardwareInfo
from Components.About import getChipSetString

from boxbranding import getMachineBuild, getBoxType, getBrandOEM

SystemInfo = { }

#FIXMEE...
def getNumVideoDecoders():
	idx = 0
	while fileExists("/dev/dvb/adapter0/video%d"% idx, 'f'):
		idx += 1
	return idx

def countFrontpanelLEDs():
	leds = 0
	if fileExists("/proc/stb/fp/led_set_pattern"):
		leds += 1
	while fileExists("/proc/stb/fp/led%d_pattern" % leds):
		leds += 1
	return leds

SystemInfo["CommonInterface"] = eDVBCIInterfaces.getInstance().getNumOfSlots()
SystemInfo["CommonInterfaceCIDelay"] = fileCheck("/proc/stb/tsmux/rmx_delay")
for cislot in range (0, SystemInfo["CommonInterface"]):
	SystemInfo["CI%dSupportsHighBitrates" % cislot] = fileCheck("/proc/stb/tsmux/ci%d_tsclk"  % cislot)
	SystemInfo["CI%dRelevantPidsRoutingSupport" % cislot] = fileCheck("/proc/stb/tsmux/ci%d_relevant_pids_routing"  % cislot)

SystemInfo["NumVideoDecoders"] = getNumVideoDecoders()
SystemInfo["PIPAvailable"] = SystemInfo["NumVideoDecoders"] > 1
SystemInfo["CanMeasureFrontendInputPower"] = eDVBResourceManager.getInstance().canMeasureFrontendInputPower()
SystemInfo["12V_Output"] = Misc_Options.getInstance().detected_12V_output()
SystemInfo["ZapMode"] = fileCheck("/proc/stb/video/zapmode") or fileCheck("/proc/stb/video/zapping_mode")
SystemInfo["NumFrontpanelLEDs"] = countFrontpanelLEDs()
SystemInfo["FrontpanelDisplay"] = fileExists("/dev/dbox/oled0") or fileExists("/dev/dbox/lcd0")
SystemInfo["OledDisplay"] = fileExists("/dev/dbox/oled0")
SystemInfo["LcdDisplay"] = fileExists("/dev/dbox/lcd0")
SystemInfo["DisplayLED"] = getBoxType() in ('gb800se', 'gb800solo', 'gbx1', 'gbx2', 'gbx3', 'gbx3h')
SystemInfo["LEDButtons"] = getBoxType() == 'vuultimo'
SystemInfo["DeepstandbySupport"] = HardwareInfo().has_deepstandby()
SystemInfo["Fan"] = fileCheck("/proc/stb/fp/fan")
SystemInfo["FanPWM"] = SystemInfo["Fan"] and fileCheck("/proc/stb/fp/fan_pwm")
SystemInfo["StandbyLED"] = fileCheck("/proc/stb/power/standbyled")
SystemInfo["WakeOnLAN"] = getBoxType() not in ('et8000', 'et10000') and fileCheck("/proc/stb/power/wol") or fileCheck("/proc/stb/fp/wol")
SystemInfo["HDMICEC"] = (fileExists("/dev/hdmi_cec") or fileExists("/dev/misc/hdmi_cec0")) and fileExists("/usr/lib/enigma2/python/Plugins/SystemPlugins/HdmiCEC/plugin.pyo")
SystemInfo["SABSetup"] = fileExists("/usr/lib/enigma2/python/Plugins/SystemPlugins/SABnzbd/plugin.pyo")
SystemInfo["Blindscan"] = fileExists("/usr/lib/enigma2/python/Plugins/SystemPlugins/Blindscan/plugin.pyo")
SystemInfo["Satfinder"] = fileExists("/usr/lib/enigma2/python/Plugins/SystemPlugins/Satfinder/plugin.pyo")
SystemInfo["HasExternalPIP"] = getMachineBuild() not in ('et9x00', 'et6x00', 'et5x00') and fileCheck("/proc/stb/vmpeg/1/external")
SystemInfo["VideoDestinationConfigurable"] = fileExists("/proc/stb/vmpeg/0/dst_left")
SystemInfo["hasPIPVisibleProc"] = fileCheck("/proc/stb/vmpeg/1/visible")
SystemInfo["VFD_scroll_repeats"] = getBoxType() not in ('et8500') and fileCheck("/proc/stb/lcd/scroll_repeats")
SystemInfo["VFD_scroll_delay"] = getBoxType() not in ('et8500') and fileCheck("/proc/stb/lcd/scroll_delay")
SystemInfo["VFD_initial_scroll_delay"] = getBoxType() not in ('et8500') and fileCheck("/proc/stb/lcd/initial_scroll_delay")
SystemInfo["VFD_final_scroll_delay"] = getBoxType() not in ('et8500') and fileCheck("/proc/stb/lcd/final_scroll_delay")
SystemInfo["LcdLiveTV"] = fileCheck("/proc/stb/fb/sd_detach") or fileCheck("/proc/stb/lcd/live_enable")
SystemInfo["LCDMiniTV"] = fileExists("/proc/stb/lcd/mode")
SystemInfo["LCDMiniTVPiP"] = SystemInfo["LCDMiniTV"] and getBoxType() != 'gb800ueplus'
SystemInfo["FastChannelChange"] = False
SystemInfo["3DMode"] = fileCheck("/proc/stb/fb/3dmode") or fileCheck("/proc/stb/fb/primary/3d")
SystemInfo["3DZNorm"] = fileCheck("/proc/stb/fb/znorm") or fileCheck("/proc/stb/fb/primary/zoffset")
SystemInfo["Blindscan_t2_available"] = fileCheck("/proc/stb/info/vumodel")
SystemInfo["HasForceLNBOn"] = fileCheck("/proc/stb/frontend/fbc/force_lnbon")
SystemInfo["HasForceToneburst"] = fileCheck("/proc/stb/frontend/fbc/force_toneburst")
SystemInfo["HasMMC"] = fileHas("/proc/cmdline", "root=/dev/mmcblk")
SystemInfo["HasTranscoding"] = pathExists("/proc/stb/encoder/0") or fileCheck("/dev/bcm_enc0")
SystemInfo["HasH265Encoder"] = fileHas("/proc/stb/encoder/0/vcodec_choices", "h265")
SystemInfo["CanNotDoSimultaneousTranscodeAndPIP"] = getBoxType() in ('vusolo4k','gbquad4k')
SystemInfo["hasXcoreVFD"] = getBoxType() in ('osmega','spycat4k','spycat4kmini','spycat4kcombo') and fileCheck("/sys/module/brcmstb_%s/parameters/pt6302_cgram" % getBoxType())
SystemInfo["HasHDMIin"] = getMachineBuild() in ('inihdp', 'hd2400', 'et10000', 'et13000', 'dm7080', 'dm820', 'dm900', 'vuultimo4k', 'vuuno4kse') or getBoxType() in ('gbquad4k')
SystemInfo["HasHDMI-CEC"] = fileExists("/usr/lib/enigma2/python/Plugins/SystemPlugins/HdmiCEC/plugin.pyo")
SystemInfo["HasInfoButton"] = getBrandOEM() in ('broadmedia', 'ceryon', 'dags', 'formuler', 'gfutures', 'gigablue', 'ini', 'octagon', 'odin', 'skylake', 'tiviar', 'xcore', 'xp', 'xtrend')
SystemInfo["Has24hz"] = fileCheck("/proc/stb/video/videomode_24hz")
SystemInfo["canMultiBoot"] = getMachineBuild() in ('hd51') and (1, 4) or getBoxType() in ('gbue4k', 'gbquad4k') and (3, 3)
SystemInfo["canMode12"] = getMachineBuild() in ('hd51') and ('440M@328M brcm_cma=192M@768M', '520M@248M brcm_cma=200M@768M')
SystemInfo["supportPcmMultichannel"] = fileCheck("/proc/stb/audio/multichannel_pcm")
SystemInfo["CanAACTranscode"] = fileExists("/proc/stb/audio/aac_transcode_choices") and fileCheck("/proc/stb/audio/aac_transcode")
SystemInfo["CanDownmixAC3"] = fileHas("/proc/stb/audio/ac3_choices", "downmix")
SystemInfo["CanDownmixDTS"] = fileHas("/proc/stb/audio/dts_choices", "downmix")
SystemInfo["CanDownmixAAC"] = fileHas("/proc/stb/audio/aac_choices", "downmix")
SystemInfo["Canaudiosource"] = fileCheck("/proc/stb/hdmi/audio_source")
SystemInfo["Can3DSurround"] = fileExists("/proc/stb/audio/3d_surround_choices") and fileCheck("/proc/stb/audio/3d_surround")
SystemInfo["Can3DSpeaker"] = fileExists("/proc/stb/audio/3d_surround_speaker_position_choices") and fileCheck("/proc/stb/audio/3d_surround_speaker_position")
SystemInfo["CanAutoVolume"] = fileExists("/proc/stb/audio/avl_choices") and fileCheck("/proc/stb/audio/avl")
SystemInfo["havecolorspace"] = fileCheck("/proc/stb/video/hdmi_colorspace")
SystemInfo["havecolorimetry"] = fileCheck("/proc/stb/video/hdmi_colorimetry")
SystemInfo["havehdmicolordepth"] = fileCheck("/proc/stb/video/hdmi_colordepth")
SystemInfo["Canedidchecking"] = fileCheck("/proc/stb/hdmi/bypass_edid_checking")
SystemInfo["haveboxmode"] = fileExists("/proc/stb/info/boxmode")
SystemInfo["HasScaler_sharpness"] = pathExists("/proc/stb/vmpeg/0/pep_scaler_sharpness")
# Machines that do not have component video (red, green and blue RCA sockets).
SystemInfo["no_YPbPr"] = getBoxType() in (
		'dm500hd',
		'dm500hdv2',
		'dm800',
		'e3hd',
		'ebox7358',
		'eboxlumi',
		'ebox5100',
		'enfinity',
		'et4x00',
		'formuler4turbo',
		'gbquad4k',
		'gbue4k',
		'gbx1',
		'gbx2',		
		'gbx3',
		'gbx3h',
		'iqonios300hd',
		'ixusszero',
		'mbmicro',
		'mbmicrov2',
		'mbtwinplus',
		'mutant11',
		'mutant51',
		'mutant500c',
		'mutant1200',
		'mutant1500',
		'odimm7',
		'optimussos1',
		'osmega',
		'osmini',
		'osminiplus',
		'osnino',
		'osninoplus',		
		'sf128',
		'sf138',
		'sf4008',
		'tm2t',
		'tmnano',
		'tmnano2super',
		'tmnano3t',
		'tmnanose',
		'tmnanosecombo',
		'tmnanoseplus',
		'tmnanosem2',
		'tmnanosem2plus',
		'tmnanom3',
		'tmsingle',
		'tmtwin4k',
		'uniboxhd1',
		'vusolo2',
		'vuzero4k',
		'vusolo4k',
		'vuuno4k',
		'vuuno4kse',
		'vuultimo4k',
		'xp1000'
	)
# Machines that have composite video (yellow RCA socket) but do not have Scart.
SystemInfo["yellow_RCA_no_scart"] = getBoxType() in (
		'formuler1',
		'formuler1tc',
		'formuler4turbo',
		'gb800ueplus',
		'gbultraue',
		'mbmicro',
		'mbmicrov2',
		'mbtwinplus',
		'mutant11',
		'mutant500c',
		'osmega',
		'osmini',
		'osminiplus',
		'sf138',
		'tmnano',
		'tmnanose',
		'tmnanosecombo',
		'tmnanosem2',
		'tmnanoseplus',
		'tmnanosem2plus',
		'tmnano2super',
		'tmnano3t',
		'xpeedlx3'
	)
# Machines that have neither yellow RCA nor Scart sockets
SystemInfo["no_yellow_RCA__no_scart"] = getBoxType() in (
		'et5x00',
		'et6x00',
		'gbquad',
		'gbquad4k',
		'gbue4k',
		'gbx1',
		'gbx2',		
		'gbx3',
		'gbx3h',
		'ixussone',
		'mutant51',
		'mutant1500',
		'osnino',
		'osninoplus',		
		'sf4008',
		'tmnano2t',
		'tmnanom3',
		'tmtwin4k',
		'vuzero4k',
		'vusolo4k',
		'vuuno4k',
		'vuuno4kse',
		'vuultimo4k'
	)
SystemInfo["Chipstring"] = getChipSetString() in ('5272s', '7251', '7251s', '7252', '7252s', '7366', '7376', '7444s', '72604') and (
	["720p", "1080p", "2160p", "1080i", "576p", "576i", "480p", "480i"], {"720p", "1080p", "2160p", "1080i"}) or getChipSetString() in (
	'7241', '7356', '73565', '7358', '7362', '73625', '7424', '7425', '7552') and (
	["720p", "1080p", "1080i", "576p", "576i", "480p", "480i"], {"720p", "1080p", "1080i"})
