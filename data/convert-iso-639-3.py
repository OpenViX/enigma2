import pickle
import sys
infilename = "iso-639-3.tab"
outfilename = "iso-639-3.pck"

if len(sys.argv) > 1:
	infilename = sys.argv[1]
if len(sys.argv) > 2:
	outfilename = sys.argv[2]

data = {}

with open(infilename, 'r') as f:
	f.readline()  # throw away header line
	for line in f:
		item = line.split('\t')
		name = (item[6],)
		for i in range(4):
			if item[i]:
				data[item[i]] = name

with open(outfilename, 'wb') as f:
	pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)
