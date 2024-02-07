#include <lib/base/eerror.h>
#include <lib/base/estring.h>
#include <lib/service/service.h>
#include <lib/base/init_num.h>
#include <lib/base/init.h>
#include <lib/dvb/idvb.h>

static std::string encode(const std::string s)
{
	std::string res;

	res.reserve(s.size());
	for (std::string::const_iterator it = s.begin(); it != s.end(); ++it)
	{
		const unsigned char c = *it;
		if ((c == ':') || (c < 32) || (c == '%'))
		{
			res += "%";
			char hex[8];
			snprintf(hex, 8, "%02x", c);
			res += hex;
		} else
			res += c;
	}
	return res;
}

RESULT eServiceReference::parseNameAndProviderFromName(std::string &sourceName, std::string& name, std::string& prov) {
	prov = "";
	if (!sourceName.empty()) {
		std::vector<std::string> name_split = split(sourceName, "•");
		name = name_split[0];
		if (name_split.size() > 1) {
			prov = name_split[1];
		}
	}
	return 0;
}

void eServiceReference::eServiceReferenceBase(const std::string &string)
{
	const char *c = string.c_str();
	int pathl = 0;

	number = 0;

	if (string.empty())
	{
		type = idInvalid;
		return;
	}

	if (isalpha(*c))
	{
		eDebug("[eServiceReference] May be unencoded URL: %s", c);
		const char *colon = strchr(c, ':');
		if ((colon) && !strncmp(colon, "://", 3))
		{
			type = idServiceMP3;
			memset(data, 0, sizeof(data));
			/* Allow space separated name */
			const char *space = strchr(colon, ' ');
			if (space)
			{
				path.assign(c, space - c);
				name = space + 1;
			}
			else
			{
				path = string;
				name = string;
			}

			std::string res_name = "";
			std::string res_provider = "";
			eServiceReference::parseNameAndProviderFromName(name, res_name, res_provider);
			name = res_name;
			prov = res_provider;

			eDebug("[eServiceReference] URL=%s name=%s", path.c_str(), name.c_str());
			return;
		}
	}

	int ret = sscanf(c, "%d:%d:%x:%x:%x:%x:%x:%x:%x:%x:%n", &type, &flags, &data[0], &data[1], &data[2], &data[3], &data[4], &data[5], &data[6], &data[7], &pathl);
	if (ret < 8 )
	{
		memset(data, 0, sizeof(data));
		ret = sscanf(c, "%d:%d:%x:%x:%x:%x:%n", &type, &flags, &data[0], &data[1], &data[2], &data[3], &pathl);
		eDebug("[eServiceReference] find old format eServiceReference string");
		if (ret < 2)
			type = idInvalid;
	}

	if (pathl)
	{
		const char *pathstr = c + pathl;
		const char *namestr = strchr(pathstr, ':');
		if (namestr)
		{
			if (!strncmp(namestr, "://", 3))
			{
				/*
				 * The path is a url (e.g. "http://...")
				 * We can expect more colons to be present
				 * in a url, so instead of a colon, we look
				 * for a space instead as url delimiter,
				 * after which a name may be present.
				 */
				namestr = strchr(namestr, ' ');
				if (namestr)
				{
					path.assign(pathstr, namestr - pathstr);
					if (*(namestr + 1))
						name = namestr + 1;
				}
			}
			else
			{
				if (pathstr != namestr)
					path.assign(pathstr, namestr-pathstr);
				if (*(namestr+1))
					name=namestr+1;
			}
		}
		else
		{
			path=pathstr;
		}
	}

	path = urlDecode(path);
	name = urlDecode(name);

	std::string res_name = "";
	std::string res_provider = "";
	eServiceReference::parseNameAndProviderFromName(name, res_name, res_provider);
	name = res_name;
	prov = res_provider;
}

eServiceReference::eServiceReference(const std::string &string)
{
	/* eDebug("[eServiceReference][std]"); */
	eServiceReferenceBase(string);
}

eServiceReference::eServiceReference(const char* string2)
{
	std::string string(string2);
	/* eDebug("[eServiceReference][char]"); */
	eServiceReferenceBase(string);
}

std::string eServiceReference::toString() const
{
	std::string ret;
	ret.reserve((6 * sizeof(data)/sizeof(*data)) + 8 + path.length() + name.length()); /* Estimate required space */

	ret += getNum(type);
	ret += ':';
	ret += getNum(flags);
	for (unsigned int i = 0; i < sizeof(data)/sizeof(*data); ++i)
	{
		ret += ':';
		ret += getNum(data[i], 0x10);
	}
	ret += ':';
	ret += encode(path); /* we absolutely have a problem when the path contains a ':' (for example: http://). we need an encoding here. */
	if (!name.empty())
	{
		ret += ':';
		ret += encode(name);
	}
	return ret;
}

std::string eServiceReference::toCompareString() const
{
	std::string ret;
	ret.reserve((6 * sizeof(data)/sizeof(*data)) + 8 + path.length()); /* Estimate required space */

	ret += getNum(type);
	ret += ":0";
	for (unsigned int i=0; i<sizeof(data)/sizeof(*data); ++i)
	{
		ret += ':';
		ret += getNum(data[i], 0x10);
	}
	ret += ':';
	ret += encode(path);
	return ret;
}

eServiceCenter *eServiceCenter::instance;

eServiceCenter::eServiceCenter()
{
	if (!instance)
	{
		eDebug("[eServiceCenter] settings instance.");
		instance = this;
	}
}

eServiceCenter::~eServiceCenter()
{
	if (instance == this)
	{
		eDebug("[eServiceCenter] clear instance");
		instance = 0;
	}
}

DEFINE_REF(eServiceCenter);

RESULT eServiceCenter::play(const eServiceReference &ref, ePtr<iPlayableService> &ptr)
{
	std::map<int,ePtr<iServiceHandler> >::iterator i = handler.find(ref.type);
	if (i == handler.end())
	{
		ptr = nullptr;
		return -1;
	}
	return i->second->play(ref, ptr);
}

RESULT eServiceCenter::record(const eServiceReference &ref, ePtr<iRecordableService> &ptr)
{
	std::map<int,ePtr<iServiceHandler> >::iterator i = handler.find(ref.type);
	if (i == handler.end())
	{
		ptr = nullptr;
		return -1;
	}
	return i->second->record(ref, ptr);
}

RESULT eServiceCenter::list(const eServiceReference &ref, ePtr<iListableService> &ptr)
{
	std::map<int,ePtr<iServiceHandler> >::iterator i = handler.find(ref.type);
	if (i == handler.end())
	{
		ptr = nullptr;
		return -1;
	}
	return i->second->list(ref, ptr);
}

RESULT eServiceCenter::info(const eServiceReference &ref, ePtr<iStaticServiceInformation> &ptr)
{
	std::map<int,ePtr<iServiceHandler> >::iterator i = handler.find(ref.type);
	if (i == handler.end())
	{
		ptr = nullptr;
		return -1;
	}
	return i->second->info(ref, ptr);
}

RESULT eServiceCenter::offlineOperations(const eServiceReference &ref, ePtr<iServiceOfflineOperations> &ptr)
{
	std::map<int,ePtr<iServiceHandler> >::iterator i = handler.find(ref.type);
	if (i == handler.end())
	{
		ptr = nullptr;
		return -1;
	}
	return i->second->offlineOperations(ref, ptr);
}

RESULT eServiceCenter::addServiceFactory(int id, iServiceHandler *hnd, std::list<std::string> &extensions)
{
	handler.insert(std::pair<int,ePtr<iServiceHandler> >(id, hnd));
	for (std::list<std::string>::const_iterator eit(extensions.begin()); eit != extensions.end(); ++eit)
	{
		extensions_r[*eit] = id;
	}
	return 0;
}

RESULT eServiceCenter::removeServiceFactory(int id)
{
	for (std::map<std::string, int>::iterator sit(extensions_r.begin()); sit != extensions_r.end(); )
	{
		if (sit->second == id)
		{
			extensions_r.erase(sit++);
		}
		else
		{
			++sit;
		}
	}
	handler.erase(id);
	return 0;
}

RESULT eServiceCenter::addFactoryExtension(int id, const char *extension)
{
	extensions_r[extension] = id;
	return 0;
}

RESULT eServiceCenter::removeFactoryExtension(int id, const char *extension)
{
	std::map<std::string,int>::iterator what = extensions_r.find(extension);
	if (what == extensions_r.end())
		return -1; // not found
	extensions_r.erase(what);
	return 0;
}

int eServiceCenter::getServiceTypeForExtension(const char *str)
{
	return getServiceTypeForExtension(std::string(str));
}

int eServiceCenter::getServiceTypeForExtension(const std::string &str)
{
	std::map<std::string,int>::const_iterator what = extensions_r.find(str);
	if (what == extensions_r.end())
		return -1; // not found
	return what->second;
}

	/* default handlers */
RESULT iServiceHandler::info(const eServiceReference &, ePtr<iStaticServiceInformation> &ptr)
{
	ptr = nullptr;
	return -1;
}

#include <lib/service/event.h>

RESULT iStaticServiceInformation::getEvent(const eServiceReference &ref, ePtr<eServiceEvent> &evt, time_t start_time)
{
	evt = 0;
	return -1;
}

int iStaticServiceInformation::getLength(const eServiceReference &ref)
{
	return -1;
}

int iStaticServiceInformation::isPlayable(const eServiceReference &ref, const eServiceReference &ignore, bool simulate)
{
	return 0;
}

RESULT iServiceInformation::getEvent(ePtr<eServiceEvent> &evt, int m_nownext)
{
	evt = 0;
	return -1;
}

int iStaticServiceInformation::getInfo(const eServiceReference &ref, int w)
{
	return -1;
}

std::string iStaticServiceInformation::getInfoString(const eServiceReference &ref, int w)
{
	return "";
}

ePtr<iServiceInfoContainer> iStaticServiceInformation::getInfoObject(int w)
{
	ePtr<iServiceInfoContainer> retval;
	return retval;
}

ePtr<iDVBTransponderData> iStaticServiceInformation::getTransponderData(const eServiceReference &ref)
{
	ePtr<iDVBTransponderData> retval;
	return retval;
}

long long iStaticServiceInformation::getFileSize(const eServiceReference &ref)
{
	return 0;
}

bool iStaticServiceInformation::isCrypted()
{
	return false;
}

int iStaticServiceInformation::setInfo(const eServiceReference &ref, int w, int v)
{
	return -1;
}

int iStaticServiceInformation::setInfoString(const eServiceReference &ref, int w, const char *v)
{
	return -1;
}

int iServiceInformation::getInfo(int w)
{
	return -1;
}

std::string iServiceInformation::getInfoString(int w)
{
	return "";
}

ePtr<iServiceInfoContainer> iServiceInformation::getInfoObject(int w)
{
	ePtr<iServiceInfoContainer> retval;
	return retval;
}

ePtr<iDVBTransponderData> iServiceInformation::getTransponderData()
{
	ePtr<iDVBTransponderData> retval;
	return retval;
}

void iServiceInformation::getCaIds(std::vector<int> &caids, std::vector<int> &ecmpids, std::vector<std::string> &ecmdatabytes)
{
}

long long iServiceInformation::getFileSize()
{
	return 0;
}

int iServiceInformation::setInfo(int w, int v)
{
	return -1;
}

int iServiceInformation::setInfoString(int w, const char *v)
{
	return -1;
}

eAutoInitPtr<eServiceCenter> init_eServiceCenter(eAutoInitNumbers::service, "eServiceCenter");
