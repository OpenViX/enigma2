from enigma import eDVBFrontendParametersSatellite


providers = {
	"Astra 28.2": {
		"service_provider": "BSkyB",
		"transponder": {
			'orbital_position': 282,
			'inversion': 2,
			'symbol_rate': 27500000,
			'namespace': 18481152,
			'system': 0,
			'polarization': 1,				# 0=H, 1=V
			'original_network_id': 2,
			'fec_inner': 2,
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
		"service_provider": "SKYNZ",
		"transponder": {
			'orbital_position': 1600,		# 160.0°E (Koreasat-6)
			'inversion': 2,					# Auto
			'symbol_rate': 30000000,		# 30000 ks/s
			'namespace': 104857600,
			'system': 1,					# DVB-S2
			'polarization': 0,				# 0=H, 1=V
			'original_network_id': 169,		# ONID seen on K6 Sky NZ mux
			'fec_inner': 7,					# 
			'frequency': 12530000,			# Hz
			'flags': 0,
			'transport_stream_id': 3,		# TS3 carries IEPG
			'modulation': 1,				# 
			'dvb_type': 'dvbs2',
			'pilot': 2,						# 2=Auto,1=off,1=on
			'rolloff': 0,					# 0=0.35,1=0.25,2=0.20,3=auto
			'services': {},
		},

		"service": {
			'service_name': 'TS3 IEPG Data Service',
			'namespace': 104857600,
			'original_network_id': 169,
			'flags': 0,
			'service_id': 9003,				# IEPG SID
			'transport_stream_id': 3,
			'service_provider': 'SKYNZ',
			'service_line': 'p:SKYNZ',
			'service_cachedpids': [],
			'service_capids': None,
			'service_type': 1,
		},
	},
	"Hotbird 13.0": {
		"service_provider": "Sky Italia",
		"transponder": {
			'orbital_position': 130,		# 13.0°E
			'inversion': 2,					# Auto
			'symbol_rate': 29900000,		#
			'namespace': 8519680,
			'system': 1,					# DVB-S2 assumed
			'polarization': 1,				# 0=H, 1=V
			'original_network_id': 318,	# NID
			'fec_inner': 3,					#
			'frequency': 11766000,			# Example freq, replace with real
			'flags': 0,
			'transport_stream_id': 5200,	# TSID
			'modulation': 1,				# QPSK
			'dvb_type': 'dvbs2',
			'pilot': 1,						# 2=Auto,1=off,1=on
			'rolloff': 2,					# 0=0.35,1=0.25,2=0.20,3=auto
			'services': {},
		},
		"service": {
			'service_name': 'Sky Italia OpenTV EPG',
			'namespace': 8519680,
			'original_network_id': 64511,
			'flags': 0,
			'service_id': 3635,				# SID
			'transport_stream_id': 5200,
			'service_cachedpids': [],
			'service_capids': None,
			'service_type': 1,
		},
	},
}
