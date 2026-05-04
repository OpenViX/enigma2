#ifndef __lib_base_httpsstream_h
#define __lib_base_httpsstream_h

#include <string>
#include <pthread.h>
#include <lib/base/ebase.h>
#include <lib/base/itssource.h>
#include <lib/base/thread.h>

#include <openssl/ssl.h>
#include <openssl/err.h>

class eHttpsStream: public iTsSource, public sigc::trackable, public eThread
{
	DECLARE_REF(eHttpsStream);

	int streamSocket;
	enum { BUSY, CONNECTED, FAILED } connectionStatus;
	bool isChunked;
	size_t currentChunkSize;
	std::string streamUrl;
	std::string authorizationData;
	char partialPkt[192];
	size_t partialPktSz;
	char* tmpBuf;
	size_t tmpBufSize;
	int startDelay;

	/* Ring buffer for pre-fetched stream data */
	unsigned char *ringBuf;
	size_t ringBufSize;
	size_t ringHead;		/* producer write position */
	size_t ringTail;		/* consumer read position  */
	size_t ringFill;		/* bytes currently buffered */
	pthread_mutex_t ringMutex;
	pthread_cond_t  ringNotEmpty;	/* signalled when data is added */
	pthread_cond_t  ringNotFull;	/* signalled when space is freed */
	bool ringEof;
	volatile bool threadAbort;

	int openUrl(const std::string &url, std::string &newurl);
	void thread();
	ssize_t sslRead(void *buf, size_t count);
	void fillRingBuffer();
	ssize_t readFromRing(void *buf, size_t count);
	ssize_t syncNextRead(void *buf, ssize_t count);

	/* iTsSource */
	ssize_t read(off_t offset, void *buf, size_t count);
	off_t length();
	off_t offset();
	int valid();
	bool isStream() { return true; };

	/* OpenSSL More Info https://wiki.openssl.org/index.php/SSL/TLS_Client */
	SSL_CTX *ctx;
	SSL *ssl;
	SSL_CTX* initCTX();
	void showCerts(SSL *ssl);
	ssize_t SSL_writeAll(SSL *ssl, const void *buf, size_t count);
	ssize_t SSL_singleRead(SSL *ssl, void *buf, size_t count);
	ssize_t SSL_readLine(SSL *ssl, char** buffer, size_t* bufsize);
public:
	eHttpsStream();
	~eHttpsStream();
	int open(const char *url);
	int close();
};

#endif
