#include <cstdio>

#include <lib/base/httpstream.h>
#include <lib/base/eerror.h>
#include <lib/base/wrappers.h>
#include <lib/base/nconfig.h> // access to python config

DEFINE_REF(eHttpStream);

eHttpStream::eHttpStream()
{
	streamSocket = -1;
	connectionStatus = FAILED;
	isChunked = false;
	currentChunkSize = 0;
	partialPktSz = 0;
	tmpBufSize = 32;
	tmpBuf = (char*)malloc(tmpBufSize);
	isStreamRelay = false;
	if (eConfigManager::getConfigBoolValue("config.usage.remote_fallback_enabled", false))
		startDelay = 500000;
	else
	{
		int delay = eConfigManager::getConfigIntValue("config.usage.http_startdelay");
		startDelay = delay * 1000;
	}

}

eHttpStream::~eHttpStream()
{
	if (!isStreamRelay)
	{
		threadAbort = true;
		pthread_cond_broadcast(&ringNotFull);
		pthread_cond_broadcast(&ringNotEmpty);
	}
	abort_badly();
	kill();
	free(tmpBuf);
	if (!isStreamRelay)
	{
		free(ringBuf);
		pthread_mutex_destroy(&ringMutex);
		pthread_cond_destroy(&ringNotEmpty);
		pthread_cond_destroy(&ringNotFull);
	}
	close();
}

int eHttpStream::openUrl(const std::string &url, std::string &newurl)
{
	int port;
	std::string hostname;
	std::string uri = url;
	std::string request;
	size_t buflen = 1024;
	char *linebuf = NULL;
	int result;
	char proto[100];
	int statuscode = 0;
	char statusmsg[100];
	bool playlist = false;
	bool contenttypeparsed = false;

	close();

	std::string user_agent = "HbbTV/1.1.1 (+PVR+RTSP+DL; Sonic; TV44; 1.32.455; 2.002) Bee/3.5";
	std::string extra_headers = "";
	size_t pos = uri.find('#');
	if (pos != std::string::npos)
	{
		extra_headers = uri.substr(pos + 1);
		uri = uri.substr(0, pos);

		pos = extra_headers.find("User-Agent=");
		if (pos != std::string::npos)
		{
			size_t hpos_start = pos + 11;
			size_t hpos_end = extra_headers.find('&', hpos_start);
			if (hpos_end != std::string::npos)
				user_agent = extra_headers.substr(hpos_start, hpos_end - hpos_start);
			else
				user_agent = extra_headers.substr(hpos_start);
		}
	}

	int pathindex = uri.find("/", 7);
	if (pathindex > 0)
	{
		hostname = uri.substr(7, pathindex - 7);
		uri = uri.substr(pathindex, uri.length() - pathindex);
	}
	else
	{
		hostname = uri.substr(7, uri.length() - 7);
		uri = "/";
	}
	int authenticationindex = hostname.find("@");
	if (authenticationindex > 0)
	{
		authorizationData = base64encode(hostname.substr(0, authenticationindex));
		hostname = hostname.substr(authenticationindex + 1);
	}
	int customportindex = hostname.find(":");
	if (customportindex > 0)
	{
		port = atoi(hostname.substr(customportindex + 1, hostname.length() - customportindex - 1).c_str());
		hostname = hostname.substr(0, customportindex);
	}
	else if (customportindex == 0)
	{
		port = atoi(hostname.substr(1, hostname.length() - 1).c_str());
		hostname = "localhost";
	}
	else
	{
		port = 80;
	}

	streamSocket = Connect(hostname.c_str(), port, 10);
	if (streamSocket < 0)
		goto error;

	request = "GET ";
	request.append(uri).append(" HTTP/1.1\r\n");
	request.append("Host: ").append(hostname).append("\r\n");
	request.append("User-Agent: ").append(user_agent).append("\r\n");
	if (authorizationData != "")
	{
		request.append("Authorization: Basic ").append(authorizationData).append("\r\n");
	}

	pos = 0;
	while (pos != std::string::npos && !extra_headers.empty())
	{
		std::string name, value;
		size_t start = pos;
		size_t len = std::string::npos;
		pos = extra_headers.find('=', pos);
		if (pos != std::string::npos)
		{
			len = pos - start;
			pos++;
			name = extra_headers.substr(start, len);
			start = pos;
			len = std::string::npos;
			pos = extra_headers.find('&', pos);
			if (pos != std::string::npos)
			{
				len = pos - start;
				pos++;
			}
			value = extra_headers.substr(start, len);
		}
		if (!name.empty() && !value.empty())
		{
			if (name.compare("User-Agent") == 0)
				continue;
			eDebug("[eHttpStream] setting extra-header '%s:%s'", name.c_str(), value.c_str());
			request.append(name).append(": ").append(value).append("\r\n");
		}
		else
		{
			eDebug("[eHttpStream] Invalid header format %s", extra_headers.c_str());
			break;
		}
	}

	request.append("Accept: */*\r\n");
	request.append("Connection: close\r\n");
	request.append("\r\n");

	writeAll(streamSocket, request.c_str(), request.length());

	linebuf = (char*)malloc(buflen);

	result = readLine(streamSocket, &linebuf, &buflen);
	if (result <= 0)
		goto error;

	result = sscanf(linebuf, "%99s %d %99s", proto, &statuscode, statusmsg);
	eDebug("[eHttpStream] %s: http result code: %d", __func__, result);
	eDebug("[eHttpStream] %s: http response code: %d", __func__, statuscode);
	if (statuscode != 301)
		if (result != 3 || (statuscode != 200 && statuscode != 206 && statuscode != 302))
		{
			eDebug("[eHttpStream] %s: wrong http response code: %d", __func__, statuscode);
			goto error;
		}

	while (1)
	{
		result = readLine(streamSocket, &linebuf, &buflen);
		if (!contenttypeparsed)
		{
			char contenttype[33];
			if (sscanf(linebuf, "Content-Type: %32s", contenttype) == 1)
			{
				contenttypeparsed = true;
				if (!strcasecmp(contenttype, "application/text")
				|| !strcasecmp(contenttype, "audio/x-mpegurl")
				|| !strcasecmp(contenttype, "audio/mpegurl")
				|| !strcasecmp(contenttype, "application/m3u"))
				{
					/* assume we'll get a playlist, some text file containing a stream url */
					playlist = true;
				}
				continue;
			}
		}
		if (playlist && !strncasecmp(linebuf, "http://", 7))
		{
			newurl = linebuf;
			eDebug("[eHttpStream] %s: playlist entry: %s", __func__, newurl.c_str());
			break;
		}
		if (((statuscode == 301) || (statuscode == 302) || (statuscode == 303) || (statuscode == 307) || (statuscode == 308)) &&
				strncasecmp(linebuf, "location: ", 10) == 0)
		{
			newurl = &linebuf[10];
			if (!extra_headers.empty())
				newurl.append("#").append(extra_headers);
			eDebug("[eHttpStream] %s: redirecting to: %s", __func__, newurl.c_str());
			break;
		}

		if (((statuscode == 200) || (statuscode == 206)) && !strncasecmp(linebuf, "transfer-encoding: chunked", strlen("transfer-encoding: chunked")))
		{
			isChunked = true;
		}
		if (!playlist && result == 0)
			break;
		if (result < 0)
			break;
	}

	free(linebuf);
	return 0;
error:
	eDebug("[eHttpStream] %s failed", __func__);
	free(linebuf);
	close();
	return -1;
}

int eHttpStream::open(const char *url)
{
	streamUrl = url;
	detectStreamRelay(streamUrl);
	/*
	 * We're in gui thread context here, and establishing
	 * a connection might block for up to 10 seconds.
	 * Spawn a new thread to establish the connection.
	 */
	connectionStatus = BUSY;
	eDebug("[eHttpStream] Start thread");
	run();
	return 0;
}

void eHttpStream::thread()
{
	hasStarted();
	usleep(startDelay); // wait up to half a second
	std::string currenturl, newurl;
	currenturl = streamUrl;
	for (unsigned int i = 0; i < 5; i++)
	{
		if (openUrl(currenturl, newurl) < 0)
		{
			eDebug("[eHttpStream] Thread end NO connection");
			connectionStatus = FAILED;
			if (!isStreamRelay)
			{
				pthread_mutex_lock(&ringMutex);
				ringEof = true;
				pthread_cond_broadcast(&ringNotEmpty);
				pthread_mutex_unlock(&ringMutex);
			}
			return;
		}
		if (newurl == "")
		{
			/* connection established — start filling the buffer - if not stream relay implement ring buffer*/
			eDebug("[eHttpStream] Thread - connection established, filling buffer");
			connectionStatus = CONNECTED;
			if (!isStreamRelay)
				fillRingBuffer();
			return;
		}
		/* follow redirect / playlist */
		close();
		currenturl = newurl;
		newurl = "";
	}
	/* too many redirect / playlist levels */
	eDebug("[eHttpStream] thread end NO connection");
	connectionStatus = FAILED;
	if (!isStreamRelay)
	{
		pthread_mutex_lock(&ringMutex);
		ringEof = true;
		pthread_cond_broadcast(&ringNotEmpty);
		pthread_mutex_unlock(&ringMutex);
	}
	return;
}

int eHttpStream::close()
{
	int retval = -1;
	if (streamSocket >= 0)
	{
		retval = ::close(streamSocket);
		streamSocket = -1;
	}
	return retval;
}

ssize_t eHttpStream::syncNextRead(void *buf, ssize_t length)
{
	unsigned char *b = (unsigned char*)buf;
	unsigned char *e = b + length;
	partialPktSz = 0;

	if (*(char*)buf != 0x47)
	{
		// the current read is not aligned
		// get the head position of the last packet
		// so we'll try to align the next read
		while (e != b && *e != 0x47) e--;
	}
	else
	{
		// the current read is aligned
		// get the last incomplete packet position
		e -= length % packetSize;
	}

	if (e != b && e != (b + length))
	{
		partialPktSz = (b + length) - e;
		// if the last packet is read partially save it to align the next read
		if (partialPktSz > 0 && partialPktSz < packetSize)
		{
			memcpy(partialPkt, e, partialPktSz);
		}
	}
	return (length - partialPktSz);
}

ssize_t eHttpStream::httpChunkedRead(void *buf, size_t count)
{
	ssize_t ret = -1;
	size_t total_read = partialPktSz;

	// write partial packet from the previous read
	if (partialPktSz > 0)
	{
		memcpy(buf, partialPkt, partialPktSz);
		partialPktSz = 0;
	}

	if (!isChunked)
	{
		ret = timedRead(streamSocket,((char*)buf) + total_read , count - total_read, 5000, 100);
		if (ret > 0)
		{
			ret += total_read;
			ret = syncNextRead(buf, ret);
		}
	}
	else
	{
		while (total_read < count)
		{
			if (0 == currentChunkSize)
			{
				do
				{
					ret = readLine(streamSocket, &tmpBuf, &tmpBufSize);
					if (ret < 0) return -1;
				} while (!*tmpBuf && ret > 0); /* skip CR LF from last chunk */
				if (ret == 0)
					break;
				currentChunkSize = strtol(tmpBuf, NULL, 16);
				if (currentChunkSize == 0) return -1;
			}

			size_t to_read = count - total_read;
			if (currentChunkSize < to_read)
				to_read = currentChunkSize;

			// do not wait too long if we have something in the buffer already
			ret = timedRead(streamSocket, ((char*)buf) + total_read, to_read, ((total_read)? 100 : 5000), 100);
			if (ret <= 0)
				break;
			currentChunkSize -= ret;
			total_read += ret;
		}
		if (total_read > 0)
		{
			ret = syncNextRead(buf, total_read);
		}
	}
	return ret;
}

ssize_t eHttpStream::read(off_t offset, void *buf, size_t count)
{
	if (connectionStatus == BUSY)
		return 0;
	else if (connectionStatus == FAILED)
		return -1;
	if (isStreamRelay)
		return httpChunkedRead(buf, count);
	else
	{
		unsigned char *b = (unsigned char*)buf;
		size_t pre = partialPktSz;
		if (pre > 0)
		{
			/* prepend the partial TS packet saved from the previous read */
			memcpy(b, partialPkt, pre);
			partialPktSz = 0;
		}
		ssize_t got = readFromRing(b + pre, count - pre);
		if (got <= 0)
			return got;
		return syncNextRead(buf, (ssize_t)(got + pre));
	}
}

int eHttpStream::valid()
{
	if (isStreamRelay)
	{
		if (connectionStatus == BUSY)
			return 0;
		return streamSocket >= 0;
	}
	else
	{
		if (connectionStatus == FAILED)
			return -1;
		else
		{
			pthread_mutex_lock(&ringMutex);
			int ok = (ringFill > 0 || (!ringEof && streamSocket >= 0)) ? 1 : 0;
			pthread_mutex_unlock(&ringMutex);
			return ok;
		}
	}
}

off_t eHttpStream::length()
{
	return (off_t)-1;
}

off_t eHttpStream::offset()
{
	return 0;
}

/* socketRead — reads raw bytes from the socket, transparently handling chunked
 * transfer encoding.  No TS-packet alignment is applied here. */
ssize_t eHttpStream::socketRead(void *buf, size_t count)
{
	if (!isChunked)
		return timedRead(streamSocket, buf, count, 5000, 100);

	size_t total_read = 0;
	while (total_read < count)
	{
		if (currentChunkSize == 0)
		{
			ssize_t r;
			do {
				r = readLine(streamSocket, &tmpBuf, &tmpBufSize);
				if (r < 0) return (total_read > 0) ? (ssize_t)total_read : -1;
			} while (!*tmpBuf && r > 0); /* skip blank lines between chunks */
			if (r == 0) break;
			currentChunkSize = strtol(tmpBuf, NULL, 16);
			if (currentChunkSize == 0) return (total_read > 0) ? (ssize_t)total_read : -1;
		}

		size_t to_read = count - total_read;
		if (currentChunkSize < to_read) to_read = currentChunkSize;

		ssize_t r = timedRead(streamSocket, ((char*)buf) + total_read, to_read,
		                      total_read ? 100 : 5000, 100);
		if (r <= 0) break;
		currentChunkSize -= (size_t)r;
		total_read += (size_t)r;
	}
	return (total_read > 0) ? (ssize_t)total_read : -1;
}

/* fillRingBuffer — producer loop: runs inside the streaming thread and pumps
 * decoded HTTP data into the ring buffer until EOF, error, or abort. */
void eHttpStream::fillRingBuffer()
{
	const size_t chunk = 65536; /* 64 KB at a time from the socket */
	unsigned char *tmp = (unsigned char*)malloc(chunk);
	if (tmp)
	{
		while (!threadAbort)
		{
			ssize_t got = socketRead(tmp, chunk);
			if (got <= 0) break;

			size_t written = 0;
			while (written < (size_t)got && !threadAbort)
			{
				pthread_mutex_lock(&ringMutex);
				while (ringFill == ringBufSize && !threadAbort)
					pthread_cond_wait(&ringNotFull, &ringMutex);

				if (threadAbort)
				{
					pthread_mutex_unlock(&ringMutex);
					break;
				}

				size_t space    = ringBufSize - ringFill;
				size_t to_write = (size_t)got - written;
				if (to_write > space) to_write = space;

				/* copy into ring buffer, handling wrap-around */
				size_t first = ringBufSize - ringHead;
				if (to_write <= first)
				{
					memcpy(ringBuf + ringHead, tmp + written, to_write);
				}
				else
				{
					memcpy(ringBuf + ringHead, tmp + written, first);
					memcpy(ringBuf, tmp + written + first, to_write - first);
				}
				ringHead  = (ringHead + to_write) % ringBufSize;
				ringFill += to_write;
				written  += to_write;

				pthread_cond_signal(&ringNotEmpty);
				pthread_mutex_unlock(&ringMutex);
			}
		}
		free(tmp);
	}

	/* signal EOF to any blocked reader */
	pthread_mutex_lock(&ringMutex);
	ringEof = true;
	pthread_cond_broadcast(&ringNotEmpty);
	pthread_mutex_unlock(&ringMutex);
}

/* readFromRing — consumer: copies up to count bytes out of the ring buffer,
 * blocking until data is available or EOF/abort is signalled. */
ssize_t eHttpStream::readFromRing(void *buf, size_t count)
{
	pthread_mutex_lock(&ringMutex);
	while (ringFill == 0 && !ringEof && !threadAbort)
		pthread_cond_wait(&ringNotEmpty, &ringMutex);

	if (ringFill == 0)
	{
		pthread_mutex_unlock(&ringMutex);
		return -1;
	}

	size_t to_read = count;
	if (to_read > ringFill) to_read = ringFill;

	/* copy from ring buffer, handling wrap-around */
	size_t first = ringBufSize - ringTail;
	if (to_read <= first)
	{
		memcpy(buf, ringBuf + ringTail, to_read);
	}
	else
	{
		memcpy(buf, ringBuf + ringTail, first);
		memcpy((char*)buf + first, ringBuf, to_read - first);
	}
	ringTail  = (ringTail + to_read) % ringBufSize;
	ringFill -= to_read;

	pthread_cond_signal(&ringNotFull);
	pthread_mutex_unlock(&ringMutex);
	return (ssize_t)to_read;
}


/* detectStreamRelay — check if the URL is a stream relay (localhost/loopback) */
void eHttpStream::detectStreamRelay(const std::string &url)
{
	isStreamRelay = (url.find("0.0.0.0:") != std::string::npos ||
	                 url.find("127.0.0.1:") != std::string::npos ||
	                 url.find("localhost:") != std::string::npos);
	if (isStreamRelay)
	{
		eDebug("[eHttpStream] Stream Relay detected - ring buffer disabled");
	}
	else
	{
		/* Ring buffer — default 2 MB, tunable via config.usage.http_buffersize (KB) */
		int bufKB = eConfigManager::getConfigIntValue("config.usage.http_buffersize");
		ringBufSize = (bufKB > 0 ? (size_t)bufKB : 2048) * 1024;
		ringBuf = (unsigned char*)malloc(ringBufSize);
		ringHead = 0;
		ringTail = 0;
		ringFill = 0;
		ringEof = false;
		threadAbort = false;
		pthread_mutex_init(&ringMutex, NULL);
		pthread_cond_init(&ringNotEmpty, NULL);
		pthread_cond_init(&ringNotFull, NULL);
	}
}
