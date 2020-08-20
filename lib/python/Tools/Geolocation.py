from json import loads
from urllib2 import URLError, urlopen

# Data available from http://ip-api.com/json/:
#
# 	Name		Description				Example			Type
# 	--------------	--------------------------------------	----------------------	------
# 	status		"success" or "fail"			success			string
# 	message		Included only when status is fail. Can
# 			be one of the following: private range,
# 			reserved range, invalid query		invalid query		string
# 	continent	Continent name				North America		string
# 	continentCode	Two-letter continent code		NA			string
# 	country		Country name				United States		string
# 	countryCode	Two-letter country code
# 			ISO 3166-1 alpha-2			US			string
# 	region		Region/state short code (FIPS or ISO)	CA or 10		string
# 	regionName	Region/state				California		string
# 	city		City					Mountain View		string
# 	district	District (subdivision of city)		Old Farm District	string
# 	zip		Zip code				94043			string
# 	lat		Latitude				37.4192			float
# 	lon		Longitude				-122.0574		float
# 	timezone	City timezone				America/Los_Angeles	string
# 	offset		Timezone UTC DST offset in seconds	-25200			int
# 	currency	National currency			USD			string
# 	isp		ISP name				Google			string
# 	org		Organization name			Google			string
# 	as		AS number and organization, separated
# 			by space (RIR). Empty for IP blocks
# 			not being announced in BGP tables.	AS15169 Google Inc.	string
# 	asname		AS name (RIR). Empty for IP blocks not
# 			being announced in BGP tables.		GOOGLE			string
# 	reverse		Reverse DNS of the IP			wi-in-f94.1e100.net	string
# 			(Warning: Requesting this field can delay response!)
# 	mobile		Mobile (cellular) connection		true			bool
# 	proxy		Proxy, VPN or Tor exit address		true			bool
# 	hosting		Hosting, colocated or data center	true			bool
# 	query		IP used for the query			173.194.67.94		string

geolocationFields = {
	"country": 0x00000001,
	"countryCode": 0x00000002,
	"region": 0x00000004,
	"regionName": 0x00000008,
	"city": 0x00000010,
	"zip": 0x00000020,
	"lat": 0x00000040,
	"lon": 0x00000080,
	"timezone": 0x00000100,
	"isp": 0x00000200,
	"org": 0x00000400,
	"as": 0x00000800,
	"reverse": 0x00001000,
	"query": 0x00002000,
	"status": 0x00004000,
	"message": 0x00008000,
	"mobile": 0x00010000,
	"proxy": 0x00020000,
	# "": 0x00040000,
	"district": 0x00080000,
	"continent": 0x00100000,
	"continentCode": 0x00200000,
	"asname": 0x00400000,
	"currency": 0x00800000,
	"hosting": 0x01000000,
	"offset": 0x02000000
}


class Geolocation:
	def __init__(self):
		self.geolocation = {}
		# self.getGeolocationData(fields=None)

	def getGeolocationData(self, fields=None):
		fields = self.fieldsToNumber(fields)
		try:
			response = urlopen("http://ip-api.com/json/?fields=%s" % fields, data=None, timeout=10).read()
			# print("[Geolocation] DEBUG: '%s'." % str(response))
			if response:
				geolocation = loads(response)
			status = geolocation.get("status", None)
			if status and status == "success":
				print("[Geolocation] Geolocation data retreived.")
				for key in geolocation:
					self.geolocation[key] = geolocation[key]
				return self.geolocation
			else:
				print("[Geolocation] Error: Geolocation lookup returned a '%s' status!  Message '%s' returned." % (status, geolocation.get("message", None)))
		except URLError as err:
			if hasattr(err, 'code'):
				print("[Geolocation] Error: Geolocation data not available! (Code: %s)" % err.code)
			if hasattr(err, 'reason'):
				print("[Geolocation] Error: Geolocation data not available! (Reason: %s)" % err.reason)
		except ValueError:
			print("[Geolocation] Error: Geolocation data returned can not be processed!")
		except Exception:
			print("[Geolocation] Error: Geolocation network connection failed!")
		return {}

	def fieldsToNumber(self, fields):
		if fields is None:
			fields = [x for x in geolocationFields]
		elif isinstance(fields, str):
			fields = [x.strip() for x in fields.split(",")]
		if isinstance(fields, int):
			number = fields
		else:
			number = 0
			for field in fields:
				value = geolocationFields.get(field, 0)
				if value:
					number |= value
				else:
					print("[Geolocation] Warning: Ignoring invalid geolocation field '%s'!" % field)
		# print("[Geolocation] DEBUG: Fields='%s' -> Number=%d." % (fields, number))
		return number

	def clearGeolocationData(self):
		self.geolocation = {}


geolocation = Geolocation()
