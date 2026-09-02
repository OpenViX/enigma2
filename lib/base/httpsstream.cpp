#include <cstdio>

#include <lib/base/httpsstream.h>
#include <lib/base/eerror.h>
#include <lib/base/wrappers.h>
#include <lib/base/nconfig.h> // access to python config

// for shutdown
#include <sys/socket.h>

DEFINE_REF(eHttpsStream);

eHttpsStream::eHttpsStream()
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

	ctx = NULL;
	ssl = NULL;
}

eHttpsStream::~eHttpsStream()
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

int eHttpsStream::openUrl(const std::string &url, std::string &newurl)
{
	int retval;
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
	std::string PREFERRED_CIPHERS = "HIGH:!aNULL:!MD5:!RC4";
	const char *errstr = NULL;

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

	int pathindex = uri.find("/", 8);
	if (pathindex > 0)
	{
		hostname = uri.substr(8, pathindex - 8);
		uri = uri.substr(pathindex, uri.length() - pathindex);
	}
	else
	{
		hostname = uri.substr(8, uri.length() - 8);
		uri = "/";
	}
	int authenticationindex = hostname.find("@");
	if (authenticationindex > 0)
	{
		authorizationData =  base64encode(hostname.substr(0, authenticationindex));
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

	ctx = initCTX();
	if (!ctx)
	{
		eDebug("[eHttpsStream] initCTX failed");
		goto error;
	}

	streamSocket = Connect(hostname.c_str(), port, 10);
	if (streamSocket < 0)
	{
		eDebug("[eHttpsStream] Connect failed on %s", hostname.c_str());
		goto error;
	}

	ssl = SSL_new(ctx);		/* create new SSL connection state */
	if (!ssl)
	{
		eDebug("[eHttpsStream] SSL_new failed");
		goto error;
	}

	/* set preffered ciphers */
	if (!SSL_set_cipher_list(ssl, PREFERRED_CIPHERS.c_str()))
	{
		eDebug("[eHttpsStream] SSL_set_cipher_list failed");
		goto error;
	}

	/* initialize TLS SNI extension when enabled */
#ifdef SSL_CTRL_SET_TLSEXT_HOSTNAME
	if (!SSL_set_tlsext_host_name(ssl, hostname.c_str()))
	{
		eDebug("[eHttpsStream] SSL_set_tlsext_host_name failed");
		goto error;
	}
#endif

	/* attach the socket descriptor */
	if (!SSL_set_fd(ssl, streamSocket))
	{
		eDebug("[eHttpsStream] SSL_set_fd failed");
		goto error;
	}

	retval = SSL_connect(ssl);
	if (retval <= 0)
	{
		errstr = ERR_reason_error_string(ERR_get_error());
		eDebug("[eHttpsStream] SSL handshake failed: %s", errstr != NULL ? errstr : "unknown SSL error");
		goto error;
	}

	/* TODO Enigma2 settings should allow self signed certificates or error ones */
	retval = SSL_get_verify_result(ssl);
	if (retval != X509_V_OK)
	{
		if (retval == X509_V_ERR_DEPTH_ZERO_SELF_SIGNED_CERT || retval == X509_V_ERR_SELF_SIGNED_CERT_IN_CHAIN)
		{
			eWarning("[eHttpsStream] Self Signed Certificate!");
		}
		else
		{
			eWarning("[eHttpsStream] Certificate verification Error %ld", SSL_get_verify_result(ssl));
		}
	}

	eDebug("[eHttpsStream] Connected with %s encryption", SSL_get_cipher(ssl));
	showCerts(ssl);

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
			eDebug("[eHttpsStream] setting extra-header '%s:%s'", name.c_str(), value.c_str());
			request.append(name).append(": ").append(value).append("\r\n");
		}
		else
		{
			eDebug("[eHttpsStream] Invalid header format %s", extra_headers.c_str());
			break;
		}
	}

	request.append("Accept: */*\r\n");
	request.append("Connection: close\r\n");
	request.append("\r\n");

	SSL_writeAll(ssl, request.c_str(), request.length());

	linebuf = (char*)malloc(buflen);

	result = SSL_readLine(ssl, &linebuf, &buflen);
	if (result <= 0)
		goto error;

	result = sscanf(linebuf, "%99s %d %99s", proto, &statuscode, statusmsg);
	if (result != 3 || (statuscode != 200 && statuscode != 206 && statuscode != 302))
	{
		eDebug("[eHttpsStream] %s: wrong http response code: %d", __func__, statuscode);
		goto error;
	}

	while (1)
	{
		result = SSL_readLine(ssl, &linebuf, &buflen);
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
		if (playlist && !strncasecmp(linebuf, "https://", 8))
		{
			newurl = linebuf;
			eDebug("[eHttpsStream] %s: playlist entry: %s", __func__, newurl.c_str());
			break;
		}
		if (((statuscode == 301) || (statuscode == 302) || (statuscode == 303) || (statuscode == 307) || (statuscode == 308)) &&
				strncasecmp(linebuf, "location: ", 10) == 0)
		{
			newurl = &linebuf[10];
			if (!extra_headers.empty())
				newurl.append("#").append(extra_headers);
			eDebug("[eHttpsStream] %s: redirecting to: %s", __func__, newurl.c_str());
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
	eDebug("[eHttpsStream] %s failed", __func__);
	free(linebuf);
	close();
	return -1;
}

int eHttpsStream::open(const char *url)
{
	streamUrl = url;
	detectStreamRelay(streamUrl);
	/*
	 * We're in gui thread context here, and establishing
	 * a connection might block for up to 10 seconds.
	 * Spawn a new thread to establish the connection.
	 */
	connectionStatus = BUSY;
	eDebug("[eHttpsStream] Start thread");
	run();
	return 0;
}

void eHttpsStream::thread()
{
	hasStarted();
	usleep(startDelay); // wait up to half a second
	std::string currenturl, newurl;
	currenturl = streamUrl;
	for (unsigned int i = 0; i < 5; i++)
	{
		if (openUrl(currenturl, newurl) < 0)
		{
			eDebug("[eHttpsStream] Thread end NO connection");
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
			/* connection established — start filling the ring buffer */
			eDebug("[eHttpsStream] Thread - connection established, filling buffer - ring buffer if not stream relay");
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
	eDebug("[eHttpsStream] thread end NO connection");
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

int eHttpsStream::close()
{
	int retval = -1;

	if (ssl)
	{
		if (!SSL_shutdown(ssl))	/* try to shutdown up to 2 times */
		{
			if (streamSocket >= 0)
			{
				/* send TCP FIN to force shutdown */
				shutdown(streamSocket, SHUT_WR);
			}
			SSL_shutdown(ssl);
		}
		SSL_free(ssl);			/* release connection state */
		ssl = NULL;
	}

	if (ctx)
	{
		SSL_CTX_free(ctx);		/* release context */
		ctx = NULL;
	}

	if (streamSocket >= 0)
	{
		retval = ::close(streamSocket);
		streamSocket = -1;
	}
	return retval;
}

ssize_t eHttpsStream::syncNextRead(void *buf, ssize_t length)
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

ssize_t eHttpsStream::httpChunkedRead(void *buf, size_t count)
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
		ret = SSL_singleRead(ssl,((char*)buf) + total_read , count - total_read);
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
					ret = SSL_readLine(ssl, &tmpBuf, &tmpBufSize);
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
			ret = SSL_singleRead(ssl, ((char*)buf) + total_read, to_read);
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

ssize_t eHttpsStream::read(off_t offset, void *buf, size_t count)
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

int eHttpsStream::valid()
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

off_t eHttpsStream::length()
{
	return (off_t)-1;
}

off_t eHttpsStream::offset()
{
	return 0;
}

SSL_CTX* eHttpsStream::initCTX()
{
	const SSL_METHOD *method = TLS_method();
	if (!method)
	{
		eDebug("[eHttpsStream] Failed to create TLS method");
		return NULL;
	}

	SSL_CTX *ctx = SSL_CTX_new(method);
	if (!ctx)
	{
		eDebug("[eHttpsStream] Failed to create SSL context");
		return NULL;
	}

	SSL_CTX_set_min_proto_version(ctx, TLS1_2_VERSION);
	SSL_CTX_set_options(ctx, SSL_OP_NO_COMPRESSION);

	SSL_CTX_set_default_verify_paths(ctx);
	if (!SSL_CTX_load_verify_locations(ctx, NULL, "/etc/ssl/certs"))
	{
		eDebug("[eHttpsStream] Warning: failed to load trust store from /etc/ssl/certs");
	}

	/* load client certificate and key if both files exist */
	FILE *fp = fopen("/etc/enigma2/certificate.pem", "r");
	if (fp)
	{
		fclose(fp);
		if (SSL_CTX_use_certificate_chain_file(ctx, "/etc/enigma2/certificate.pem") == 1)
		{
			if (SSL_CTX_use_PrivateKey_file(ctx, "/etc/enigma2/key.pem", SSL_FILETYPE_PEM) == 1)
			{
				if (SSL_CTX_check_private_key(ctx) == 1)
					eDebug("[eHttpsStream] Client certificate loaded");
				else
					eWarning("[eHttpsStream] Client certificate and private key do not match");
			}
			else
			{
				eWarning("[eHttpsStream] Failed to load client private key from /etc/enigma2/key.pem");
			}
		}
		else
		{
			eWarning("[eHttpsStream] Failed to load client certificate from /etc/enigma2/certificate.pem");
		}
	}

	return ctx;
}

void eHttpsStream::showCerts(SSL *ssl)
{
	X509 *cert;
	char *line;

	cert = SSL_get1_peer_certificate(ssl);	/* get the server's certificate */
	if (cert)
	{
		eDebug("[eHttpsStream] Show Server Sertificates");
		line = X509_NAME_oneline(X509_get_subject_name(cert), 0, 0);
		eDebug("[eHttpsStream] Subject: %s", line);
		free(line); /* free the malloc'ed string */
		line = X509_NAME_oneline(X509_get_issuer_name(cert), 0, 0);
		eDebug("[eHttpsStream] Issuer: %s", line);
		free(line); /* free the malloc'ed string */
		X509_free(cert); /* free the malloc'ed certificate copy */
	}
	else
	{
		eWarning("[eHttpsStream] No certificates!");
	}
}

ssize_t eHttpsStream::SSL_writeAll(SSL *ssl, const void *buf, size_t count)
{
	int retval;
	char *ptr = (char*)buf;
	size_t handledcount = 0;
	while (handledcount < count)
	{
		retval = SSL_write(ssl, &ptr[handledcount], count - handledcount);

		if (retval == 0) return -1;
		if (retval < 0)
		{
			if (errno == EINTR) continue;
			eDebug("[eHttpsStream] SSL_writeAll error: %m");
			return retval;
		}
		handledcount += retval;
	}
	return handledcount;
}

ssize_t eHttpsStream::SSL_singleRead(SSL *ssl, void *buf, size_t count)
{
	int retval;
	while (1)
	{
		retval = SSL_read(ssl, buf, count);
		if (retval < 0)
		{
			if (errno == EINTR) continue;
			eDebug("[eHttpsStream] singleRead error: %m");
		}
		return retval;
	}
}

ssize_t eHttpsStream::SSL_readLine(SSL *ssl, char** buffer, size_t* bufsize)
{
	size_t i = 0;
	int result;
	while (1)
	{
		if (i >= *bufsize)
		{
			char *newbuf = (char*)realloc(*buffer, (*bufsize)+1024);
			if (newbuf == NULL)
				return -ENOMEM;
			*buffer = newbuf;
			*bufsize = (*bufsize) + 1024;
		}
		result = SSL_singleRead(ssl, (*buffer) + i, 1);
		if (result <= 0 || (*buffer)[i] == '\n')
		{
			(*buffer)[i] = '\0';
			return result <= 0 ? -1 : i;
		}
		if ((*buffer)[i] != '\r') i++;
	}
	return -1;
}

/* sslRead — reads raw bytes via SSL, transparently handling chunked transfer
 * encoding.  No TS-packet alignment is applied here. */
ssize_t eHttpsStream::sslRead(void *buf, size_t count)
{
	if (!isChunked)
		return SSL_singleRead(ssl, buf, count);

	size_t total_read = 0;
	while (total_read < count)
	{
		if (currentChunkSize == 0)
		{
			ssize_t r;
			do {
				r = SSL_readLine(ssl, &tmpBuf, &tmpBufSize);
				if (r < 0) return (total_read > 0) ? (ssize_t)total_read : -1;
			} while (!*tmpBuf && r > 0); /* skip blank lines between chunks */
			if (r == 0) break;
			currentChunkSize = strtol(tmpBuf, NULL, 16);
			if (currentChunkSize == 0) return (total_read > 0) ? (ssize_t)total_read : -1;
		}

		size_t to_read = count - total_read;
		if (currentChunkSize < to_read) to_read = currentChunkSize;

		ssize_t r = SSL_singleRead(ssl, ((char*)buf) + total_read, to_read);
		if (r <= 0) break;
		currentChunkSize -= (size_t)r;
		total_read += (size_t)r;
	}
	return (total_read > 0) ? (ssize_t)total_read : -1;
}

/* fillRingBuffer — producer loop: runs inside the streaming thread and pumps
 * decrypted HTTPS data into the ring buffer until EOF, error, or abort. */
void eHttpsStream::fillRingBuffer()
{
	const size_t chunk = 65536; /* 64 KB at a time from SSL */
	unsigned char *tmp = (unsigned char*)malloc(chunk);
	if (tmp)
	{
		while (!threadAbort)
		{
			ssize_t got = sslRead(tmp, chunk);
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
ssize_t eHttpsStream::readFromRing(void *buf, size_t count)
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
void eHttpsStream::detectStreamRelay(const std::string &url)
{
	isStreamRelay = (url.find("0.0.0.0:") != std::string::npos ||
	                 url.find("127.0.0.1:") != std::string::npos ||
	                 url.find("localhost:") != std::string::npos);
	if (isStreamRelay)
	{
		eDebug("[eHttpsStream] Stream Relay detected - ring buffer disabled");
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
