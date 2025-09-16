from enigma import eDVBFrontendParametersSatellite


providers = {
	"Astra 28.2": {
		"transponder": {
			'orbital_position': 282,
			'inversion': eDVBFrontendParametersSatellite.Inversion_Unknown,
			'symbol_rate': 27500000,
			'namespace': 18481152,
			'system': eDVBFrontendParametersSatellite.System_DVB_S,
			'polarization': eDVBFrontendParametersSatellite.Polarisation_Vertical,
			'original_network_id': 2,
			'fec_inner': eDVBFrontendParametersSatellite.FEC_2_3,
			'frequency': 11778000,
			'flags': 0,
			'transport_stream_id': 2004,
			'modulation': eDVBFrontendParametersSatellite.Modulation_QPSK,
			},

		"service": {
			'service_name': 'IEPG data 1',
			'namespace': 18481152,
			'original_network_id': 2,
			'flags': 0,
			'service_id': 4189,
			'service_type': 1,
			'transport_stream_id': 2004,
			'service_provider': 'BSkyB',
			'service_cachedpids': [(1, 0x0288), (3, 0x1ffe)],
			'service_capids': None,
			},
		},

	"Koreasat-6 160 NZ": {
		"transponder": {
			'orbital_position': 1600,		# 160.0°E
			'inversion': 2,					# 0=Off, 1=On, 2=Auto
			'symbol_rate': 30000000,		# ks/s
			'namespace': 104857600,
			'system': 1,					# 0 = DVB-S, 1 = DVB-S2
			'polarization': 0,				# 0 = H, 1 = V
			'original_network_id': 169,
			'fec_inner': 7,					# 0=Auto, 1=1/2, 2=2/3, 3=3/4, 4=5/6, 5=7/8, 6=8/9, 7=3/5, 8=4/5, 9=9/10, 10=6/7, 15=None
			'frequency': 12530000,			# Hz
			'flags': 0,
			'transport_stream_id': 3,
			'modulation': 1,				# 0=Auto, 1=QPSK, 2=8PSK, 3=16APSK, 4=32APSK, 5=BPSK
			'dvb_type': 'dvbs2',
			'pilot': 2,						# 0=Off, 1=On, 2=Auto
			'rolloff': 0,					# 0=0.35, 1=0.25, 2=0.20, 3=Auto
			'services': {},
		},

		"service": {
			'service_name': 'TS3 IEPG Data Service',
			'namespace': 104857600,
			'original_network_id': 169,
			'flags': 0,
			'service_id': 9003,
			'transport_stream_id': 3,
			'service_type': 1,
			'service_provider': 'SKYNZ',
			'service_line': 'p:SKYNZ',
			'service_cachedpids': None,
			'service_capids': None,
		},
	}
}
