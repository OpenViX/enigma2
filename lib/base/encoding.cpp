#include <cstdio>
#include <cstdlib>
#include <lib/base/cfile.h>
#include <lib/base/encoding.h>
#include <lib/base/eerror.h>
#include <lib/base/eenv.h>

eDVBTextEncodingHandler encodingHandler;  // the one and only instance

inline char toupper(char c)
{
	switch (c)
	{
		case 'a' ... 'z':
			return c-32;
	}
	return c;
}
inline char * strlower(char * src,char *outs)
{
	for(int i=0;src[i];i++)
		switch(src[i]){
			case 'A' ... 'Z':
				outs[i]=src[i]+32;
			default:
				outs[i]=src[i];
		}
	return outs;
}
eDVBTextEncodingHandler::eDVBTextEncodingHandler()
{
	std::string file = eEnv::resolve("${sysconfdir}/enigma2/encoding.conf");
	if (::access(file.c_str(), R_OK) < 0)
	{
		/* no personalized encoding.conf, fallback to the system default */
		file = eEnv::resolve("${datadir}/enigma2/encoding.conf");
	}
	CFile f(file.c_str(), "rt");
	if (f)
	{
		char *line = (char*) malloc(256);
		size_t bufsize=256;
		char countrycode[256];
		char codetemp[256],lowerline[256];
		while( getline(&line, &bufsize, f) != -1 )
		{
			if ( line[0] == '#' )
				continue;
			for(int i=0;line[i];i++){
				if(line[i] == '#'){
					line[i]=0;
					break;
				}
			}

			int tsid, onid, encoding;
//			if ( (sscanf( line, "0x%x 0x%x ISO8859-%d", &tsid, &onid, &encoding ) == 3 )
//					||(sscanf( line, "%d %d ISO8859-%d", &tsid, &onid, &encoding ) == 3 ) )
// 				m_TransponderDefaultMapping[(tsid<<16)|onid]=encoding;
			if ( (sscanf( strlower(line,lowerline), "0x%x 0x%x iso8859-%d", &tsid, &onid, &encoding ) == 3 )
				||(sscanf( strlower(line,lowerline), "%d %d iso8859-%d", &tsid, &onid, &encoding ) == 3 ) )
				m_TransponderDefaultMapping[(tsid<<16)|onid]=encoding;
//			else if ( sscanf( line, "%s ISO8859-%d", countrycode, &encoding ) == 2 )
			else if ( ((sscanf( strlower(line,lowerline), "0x%x 0x%x gb%d", &tsid, &onid, &encoding ) == 3 )
					&& encoding == 18030)
				||((sscanf( strlower(line,lowerline), "%d %d gb%d", &tsid, &onid, &encoding ) == 3 )
					&& encoding == 18030)
			   	||((sscanf( strlower(line,lowerline), "0x%x 0x%x gb%d", &tsid, &onid, &encoding ) == 3 )
					&& encoding == 2312)
				||((sscanf( strlower(line,lowerline), "%d %d gb%d", &tsid, &onid, &encoding ) == 3 )
					&& encoding == 2312)
			   	||((sscanf( strlower(line,lowerline), "0x%x 0x%x cp%d", &tsid, &onid, &encoding ) == 3 )
					&& encoding == 936)
				||((sscanf( strlower(line,lowerline), "%d %d cp%d", &tsid, &onid, &encoding ) == 3 )
					&& encoding == 936)
				 )
				m_TransponderDefaultMapping[(tsid<<16)|onid]=GB18030_ENCODING;
			else if ( ((sscanf( strlower(line,lowerline), "0x%x 0x%x big%d", &tsid, &onid, &encoding ) == 3 ) 
					&& encoding == 5)
				||((sscanf( strlower(line,lowerline), "%d %d big%d", &tsid, &onid, &encoding ) == 3 )
					&& encoding == 5)
			   	||((sscanf( strlower(line,lowerline), "0x%x 0x%x cp%d", &tsid, &onid, &encoding ) == 3 )
					&& encoding == 950)
				||((sscanf( strlower(line,lowerline), "%d %d cp%d", &tsid, &onid, &encoding ) == 3 )
					&& encoding == 950)
				 )
				m_TransponderDefaultMapping[(tsid<<16)|onid]=BIG5_ENCODING;
			else if ( ((sscanf( strlower(line,lowerline), "0x%x 0x%x %s", &tsid, &onid, codetemp ) == 3 ) 
						&& strncasecmp(codetemp, "utf16be",7)==0)
					||((sscanf( strlower(line,lowerline), "%d %d %s", &tsid, &onid, codetemp ) == 3 )
						&& strncasecmp(codetemp, "utf16be",7)==0)
				 )
				m_TransponderDefaultMapping[(tsid<<16)|onid]=UTF16BE_ENCODING;
			else if ( ((sscanf( strlower(line,lowerline), "0x%x 0x%x %s", &tsid, &onid, codetemp ) == 3 ) 
						&& strncasecmp(codetemp, "utf16le",7)==0)
					||((sscanf( strlower(line,lowerline), "%d %d %s", &tsid, &onid, codetemp ) == 3 )
						&& strncasecmp(codetemp, "utf16le",7)==0)
				 )
				m_TransponderDefaultMapping[(tsid<<16)|onid]=UTF16LE_ENCODING;
			else if ( sscanf( strlower(line,lowerline), "%s iso8859-%d", countrycode, &encoding ) == 2 )
			{
				m_CountryCodeDefaultMapping[countrycode]=encoding;
				countrycode[0]=toupper(countrycode[0]);
				countrycode[1]=toupper(countrycode[1]);
				countrycode[2]=toupper(countrycode[2]);
				m_CountryCodeDefaultMapping[countrycode]=encoding;
			}
//			else if ( (sscanf( line, "0x%x 0x%x ISO%d", &tsid, &onid, &encoding ) == 3 && encoding == 6937 )
//					||(sscanf( line, "%d %d ISO%d", &tsid, &onid, &encoding ) == 3 && encoding == 6937 ) )
			else if ( (sscanf( strlower(line,lowerline), "%s gb%d", countrycode, &encoding ) == 2 && encoding == 18030)
				  ||(sscanf( strlower(line,lowerline), "%s gb%d", countrycode, &encoding ) == 2 && encoding == 2312)
				  ||(sscanf( strlower(line,lowerline), "%s cp%d", countrycode, &encoding ) == 2 && encoding == 936))
			{
				m_CountryCodeDefaultMapping[countrycode]=GB18030_ENCODING;
				countrycode[0]=toupper(countrycode[0]);
				countrycode[1]=toupper(countrycode[1]);
				countrycode[2]=toupper(countrycode[2]);
				m_CountryCodeDefaultMapping[countrycode]=GB18030_ENCODING;
			}
			else if ( (sscanf( strlower(line,lowerline), "%s big%d", countrycode, &encoding ) == 2 && encoding ==5)
				||(sscanf( strlower(line,lowerline), "%s cp%d", countrycode, &encoding ) == 2 && encoding == 950))
			{
				m_CountryCodeDefaultMapping[countrycode]=BIG5_ENCODING;
				countrycode[0]=toupper(countrycode[0]);
				countrycode[1]=toupper(countrycode[1]);
				countrycode[2]=toupper(countrycode[2]);
				m_CountryCodeDefaultMapping[countrycode]=BIG5_ENCODING;
			}
			else if ( sscanf( strlower(line,lowerline), "%s %s", countrycode, codetemp ) == 2 && 
				  (strncasecmp(codetemp, "utf16be",7)==0 || strncasecmp(codetemp, "unicode",7)==0) )
			{
				m_CountryCodeDefaultMapping[countrycode]=UTF16BE_ENCODING;
				countrycode[0]=toupper(countrycode[0]);
				countrycode[1]=toupper(countrycode[1]);
				countrycode[2]=toupper(countrycode[2]);
				m_CountryCodeDefaultMapping[countrycode]=UTF16BE_ENCODING;
			}
			else if ( sscanf( strlower(line,lowerline), "%s %s", countrycode, codetemp ) == 2 && 
				  strncasecmp(codetemp, "utf16le",7)==0)
			{
				m_CountryCodeDefaultMapping[countrycode]=UTF16LE_ENCODING;
				countrycode[0]=toupper(countrycode[0]);
				countrycode[1]=toupper(countrycode[1]);
				countrycode[2]=toupper(countrycode[2]);
				m_CountryCodeDefaultMapping[countrycode]=UTF16LE_ENCODING;
			}
			else if ( (sscanf( strlower(line,lowerline), "0x%x 0x%x iso%d", &tsid, &onid, &encoding ) == 3 && encoding == 6937 )
				||(sscanf( line, "%d %d iso%d", &tsid, &onid, &encoding ) == 3 && encoding == 6937 ) )
				m_TransponderDefaultMapping[(tsid<<16)|onid]=0;
//			else if ( sscanf( line, "%s ISO%d", countrycode, &encoding ) == 2 && encoding == 6937 )
			else if ( sscanf( strlower(line,lowerline), "%s iso%d", countrycode, &encoding ) == 2 && encoding == 6937 )
			{
				m_CountryCodeDefaultMapping[countrycode]=0;
				countrycode[0]=toupper(countrycode[0]);
				countrycode[1]=toupper(countrycode[1]);
				countrycode[2]=toupper(countrycode[2]);
				m_CountryCodeDefaultMapping[countrycode]=0;
			}
			else if ( (sscanf( line, "0x%x 0x%x", &tsid, &onid ) == 2 )
					||(sscanf( line, "%d %d", &tsid, &onid ) == 2 ) )
				m_TransponderUseTwoCharMapping.insert((tsid<<16)|onid);
			else
				eDebug("encoding.conf: couldn't parse %s", line);
		}
		free(line);
	}
	else
		eDebug("[eDVBTextEncodingHandler] couldn't open %s !", file.c_str());
}

void eDVBTextEncodingHandler::getTransponderDefaultMapping(int tsidonid, int &table)
{
	std::map<int, int>::iterator it =
		m_TransponderDefaultMapping.find(tsidonid);
	if ( it != m_TransponderDefaultMapping.end() )
		table = it->second;
}

bool eDVBTextEncodingHandler::getTransponderUseTwoCharMapping(int tsidonid)
{
	return m_TransponderUseTwoCharMapping.find(tsidonid) != m_TransponderUseTwoCharMapping.end();
}

int eDVBTextEncodingHandler::getCountryCodeDefaultMapping( const std::string &country_code )
{
	std::map<std::string, int>::iterator it =
		m_CountryCodeDefaultMapping.find(country_code);
	if ( it != m_CountryCodeDefaultMapping.end() )
		return it->second;
	return 1;  // ISO8859-1 / Latin1
}
