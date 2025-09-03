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
			'polarization': 1,
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

    "Koreasat-6": {
        "service_provider": "SKYNZ",

        "transponder": {
            'orbital_position': 1600,     # 160.0°E (Koreasat-6)
            'inversion': 2,               # Auto
            'symbol_rate': 30000000,      # 30000 ks/s
            'namespace': 104857600,
            'system': 1,                  # DVB-S2
            'modulation': 1,              # QPSK (set 2 if 8PSK ever required)
            'polarization': 0,            # 0=H, 1=V
            'original_network_id': 169,   # ONID seen on K6 Sky NZ mux
            'fec_inner': 7,               # 
            'frequency': 12530000,        # Hz
            'flags': 0,
            'transport_stream_id': 3,     # TS3 carries IEPG
            'dvb_type': 'dvbs2',
            'pilot': 2,                   # Auto
            'rolloff': 0,                 # 0.35
            'services': {},
        },

        "service": {
            'service_name': 'TS3 IEPG Data Service',
            'namespace': 104857600,
            'service_line': 'p:SKYNZ',
            'service_provider': 'SKYNZ',
            'original_network_id': 169,
            'flags': 0,
            'service_id': 9003,           # IEPG SID
            'service_type': 1,
            'transport_stream_id': 3,
            'service_cachedpids': [],
            'service_capids': None,
        },
    },
	}
