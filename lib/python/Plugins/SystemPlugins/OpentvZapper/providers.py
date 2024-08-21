from enigma import eDVBFrontendParametersSatellite


providers = {
	"Astra 28.2": {
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
		}
	}
