#ifndef __lib_base_httpstream_h
#define __lib_base_httpstream_h

#include <string>
#include <pthread.h>
#include <lib/base/ebase.h>
#include <lib/base/itssource.h>
#include <lib/base/thread.h>

class eHttpStream: public iTsSource, public sigc::trackable, public eThread
{
	DECLARE_REF(eHttpStream);

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
	bool isStreamRelay;

	int openUrl(const std::string &url, std::string &newurl);
	void thread();
	ssize_t httpChunkedRead(void *buf, size_t count);
	ssize_t syncNextRead(void *buf, ssize_t count);

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
	ssize_t readFromRing(void *buf, size_t count);
	void detectStreamRelay(const std::string &url);
	ssize_t socketRead(void *buf, size_t count);
	void fillRingBuffer();


	/* iTsSource */
	ssize_t read(off_t offset, void *buf, size_t count);
	off_t length();
	off_t offset();
	int valid();
	bool isStream() { return true; };

public:
	eHttpStream();
	~eHttpStream();
	int open(const char *url);
	int close();
};

#endif
