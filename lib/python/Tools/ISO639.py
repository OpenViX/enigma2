from sys import version_info

if version_info >= (3, 0):
	import pickle
else:
	import cPickle as pickle
import enigma
with open(enigma.eEnv.resolve("${datadir}/enigma2/iso-639-3.pck"), 'rb') as f:
	if version_info >= (3, 0):
		LanguageCodes = pickle.load(f, encoding='utf-8')
	else:
		LanguageCodes = pickle.load(f)
