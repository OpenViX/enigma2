#ifndef __dvbcsaengine_h
#define __dvbcsaengine_h

#include <lib/base/object.h>
#include <vector>
#include <atomic>
#include <stdint.h>

// Forward declarations for libdvbcsa
struct dvbcsa_bs_key_s;
typedef struct dvbcsa_bs_key_s dvbcsa_bs_key_t;

struct dvbcsa_bs_batch_s {
	unsigned char *data;
	unsigned int len;
};
typedef struct dvbcsa_bs_batch_s dvbcsa_bs_batch_s;

// Function pointer types for dlopen API
typedef dvbcsa_bs_key_t *(*dvbcsa_bs_key_alloc_f)(void);
typedef void (*dvbcsa_bs_key_free_f)(dvbcsa_bs_key_t *);
typedef void (*dvbcsa_bs_key_set_ecm_f)(uint8_t ecm_mode, const uint8_t *cw, dvbcsa_bs_key_t *);
typedef unsigned char (*dvbcsa_get_ecm_table_f)(void);
typedef size_t (*dvbcsa_bs_batch_size_f)(void);
typedef void (*dvbcsa_bs_decrypt_f)(const dvbcsa_bs_key_t *key, dvbcsa_bs_batch_s *pcks, int maxlen);

// Global dlopen API structure
struct csa_dlopen_api
{
	void *handle;
	bool tried;
	bool available;
	dvbcsa_bs_key_alloc_f    key_alloc;
	dvbcsa_bs_key_free_f     key_free;
	dvbcsa_bs_key_set_ecm_f  key_set_ecm;
	dvbcsa_get_ecm_table_f   get_ecm_table;
	dvbcsa_bs_batch_size_f   batch_size;
	dvbcsa_bs_decrypt_f      decrypt;
};

// Global API instance (defined in csaengine.cpp)
extern csa_dlopen_api g_csa_api;

// Load libdvbcsa dynamically (call once at startup)
bool csa_load_library();

/**
 * eDVBCSAEngine - Low-Level CSA Descrambler
 *
 * Thread-safe wrapper around libdvbcsa using a ring of key slots.
 * setKey() from CWHandler thread and descramble() from recorder thread
 * can run concurrently without locks.
 *
 * Each parity (even/odd) has KEY_SLOTS key slots, and the slot of key
 * generation g is g % KEY_SLOTS. setKey() writes the slot of the next
 * generation, then publishes that generation. descramble() snapshots the
 * generation once per call and resolves slots from it, so it never touches
 * the one being written.
 */
class eDVBCSAEngine
{
	DECLARE_REF(eDVBCSAEngine);

public:
	eDVBCSAEngine();
	~eDVBCSAEngine();

	// Initialization
	bool init();

	// Static helpers
	static bool isAvailable() { csa_load_library(); return g_csa_api.available; }
	static int getBatchSize();
	static std::string getLibraryName();
	static std::string getLibraryPath();
	static std::string getLibraryVersion();

	// Key Management (thread-safe, called from CWHandler thread)
	void setKey(int parity, uint8_t ecm_mode, const uint8_t* cw);
	void clearKeys();

	// Descrambling (called from recorder thread)
	void descramble(unsigned char* packets, int len);

	// Status
	bool hasEvenKey() const { return m_key_even_set; }
	bool hasOddKey() const { return m_key_odd_set; }
	bool hasAnyKey() const { return hasEvenKey() || hasOddKey(); }
	int getBatchSizeInstance() const { return m_batch_size; }

private:
	/* Key slots per parity. A run may still be using the generation before
	 * the current one, so two slots are in reach of descramble() and the
	 * third is what setKey() writes: nothing is written while it is read. */
	static const int KEY_SLOTS = 3;

	dvbcsa_bs_key_t* m_key_even[KEY_SLOTS];
	dvbcsa_bs_key_t* m_key_odd[KEY_SLOTS];
	std::atomic<bool> m_key_even_set{false};
	std::atomic<bool> m_key_odd_set{false};
	// Slot for generation g is g % KEY_SLOTS: setKey() writes the next slot
	// and publishes the generation that names it.
	std::atomic<uint32_t> m_gen_even{0};
	std::atomic<uint32_t> m_gen_odd{0};
	/* Last control word written per parity, so a repeat does not spend a
	 * generation. CWHandler thread only, like setKey() itself. */
	uint8_t m_last_cw[2][8]{};
	uint8_t m_last_ecm_mode[2]{0, 0};
	bool m_last_cw_set[2]{false, false};
	// A parity run is one crypto period. Recorder thread only, which is the
	// only caller of descramble().
	int m_last_parity{-1};        // Parity of the previous packet
	uint32_t m_bound_gen[2]{0, 0};  // Key generation bound to the run, [0]=even
	uint32_t m_prev_run_gen[2]{0, 0};  // What the previous run of that parity bound
	bool m_run_suspect{false};    // Bound key may predate this period
	bool m_probe_armed{false};    // Confirm the bound key at the next PES start
	int m_batch_size;
	unsigned int m_bad_packets{0};  // Log rate limit only, races are harmless
	unsigned int m_expired_keys{0};  // Log rate limit only, races are harmless
	unsigned int m_dead_keys{0};  // Log rate limit only, races are harmless

	// Pre-allocated batch arrays
	std::vector<dvbcsa_bs_batch_s> m_batch_even;
	std::vector<dvbcsa_bs_batch_s> m_batch_odd;

	// TS Packet Helpers
	static bool isPacketValid(const unsigned char* pkt);
	static unsigned char getScrambledBits(const unsigned char* pkt);
	static int getPayloadOffset(const unsigned char* pkt);
	static void clearTSC(unsigned char* pkt);
	static void setNullPacket(unsigned char* pkt);
	void logBadPacket(const char* reason, const unsigned char* pkt, int offset, int len);
	bool probeKey(const dvbcsa_bs_key_t* key, const unsigned char* pkt, int offset) const;
};

#endif // __dvbcsaengine_h
