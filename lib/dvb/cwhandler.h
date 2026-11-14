#ifndef __dvbcwhandler_h
#define __dvbcwhandler_h

#include <lib/dvb/csaengine.h>
#include <map>
#include <mutex>
#include <atomic>  // for m_running
#include <vector>
#include <pthread.h>
#include <stdint.h>

/**
 * eDVBCWHandler - Socketpair proxy for MainLoop-independent CW delivery
 *
 * Sits between softcam socket and ePMTClient:
 * - Takes ownership of the original softcam fd
 * - Creates a socketpair, gives one end to ePMTClient
 * - Runs a poll() loop in a dedicated thread
 * - Forwards ALL data bidirectionally (ePMTClient sees no difference)
 * - Additionally intercepts CA_SET_DESCR packets and calls setKey() directly
 *
 * This ensures CW delivery continues even when the MainLoop is blocked.
 * The MainLoop still receives all packets (including CWs) for signal handling,
 * but setKey() is ONLY called from this thread, never from the MainLoop.
 */
class eDVBCWHandler
{
public:
	static eDVBCWHandler* getInstance();

	/**
	 * Register a CSA engine for direct CW delivery
	 * Called from CSASession::onCwReceived() on first CW (MainLoop context)
	 * @param serviceId Softcam's internal service ID (from CA_SET_DESCR msgid)
	 * @param engine The CSA engine to set keys on
	 * @param ecm_mode Current ecm_mode for key setting
	 */
	void registerEngine(uint32_t serviceId, eDVBCSAEngine* engine, uint8_t ecm_mode);

	/**
	 * Unregister a specific engine (called from CSASession destructor)
	 * Uses engine pointer to identify which registration to remove,
	 * so Live and Timeshift sessions don't interfere with each other.
	 */
	void unregisterEngine(uint32_t serviceId, eDVBCSAEngine* engine);

	/**
	 * Update ecm_mode for a specific registered engine
	 * Called from CSASession when ecm_mode changes
	 */
	void updateEcmMode(uint32_t serviceId, eDVBCSAEngine* engine, uint8_t ecm_mode);

	/**
	 * Take ownership of a softcam connection fd
	 * Creates socketpair, starts proxying
	 * @param softcam_fd The accepted socket fd from the softcam
	 * @return The fd for ePMTClient to use (socketpair end), or -1 on error
	 */
	int addConnection(int softcam_fd);

	/**
	 * Remove a connection (called when ePMTClient disconnects)
	 * @param client_fd The fd that was given to ePMTClient
	 */
	void removeConnection(int client_fd);

private:
	eDVBCWHandler();
	~eDVBCWHandler();

	static eDVBCWHandler* instance;

	// Engine registry (all access protected by m_targets_mutex)
	// Multiple engines can be registered per serviceId (e.g. Live + Timeshift)
	struct CwTarget {
		eDVBCSAEngine* engine;
		uint8_t ecm_mode;
	};
	std::multimap<uint32_t, CwTarget> m_targets;
	std::mutex m_targets_mutex;

	// Connection tracking
	// Only the proxy thread closes the fds and erases entries, so an fd it
	// polled stays valid (and is never reused) until it has finished with it.
	struct Connection {
		int id;
		int softcam_fd;   // Original softcam socket
		int proxy_fd;     // Our end of socketpair (proxy_fd ↔ client_fd)
		int client_fd;    // ePMTClient's end of socketpair
		bool remove;      // close at the top of the next round
		std::vector<uint8_t> cw_rest;     // start of a CW message cut off by the last read
		std::vector<uint8_t> to_client;   // softcam data ePMTClient has not taken yet
		std::vector<uint8_t> to_softcam;  // CAPMT data the softcam has not taken yet
	};
	std::vector<Connection> m_connections;
	std::mutex m_connections_mutex;
	int m_next_id = 1;
	// A peer that takes nothing for this long is gone: drop the connection
	static const size_t MAX_PENDING = 4 * 1024 * 1024;

	// Pipe for waking up poll() when connections change
	int m_wake_pipe[2];

	// Thread
	std::atomic<bool> m_running;
	pthread_t m_thread;
	static void* threadFunc(void* arg);
	void threadLoop();

	// Protocol parsing for CW interception
	void processCwFromRawPacket(Connection& conn, const uint8_t* data, int len);
	static bool flushPending(int fd, std::vector<uint8_t>& pending);
	static void closeConnection(Connection& conn);
};

#endif // __dvbcwhandler_h
