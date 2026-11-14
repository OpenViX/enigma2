#include <lib/dvb/cwhandler.h>
#include <lib/base/eerror.h>

#include <unistd.h>
#include <string.h>
#include <poll.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <linux/dvb/ca.h>
#include <arpa/inet.h>

eDVBCWHandler* eDVBCWHandler::instance = nullptr;

eDVBCWHandler* eDVBCWHandler::getInstance()
{
	if (!instance)
		instance = new eDVBCWHandler();
	return instance;
}

eDVBCWHandler::eDVBCWHandler()
	: m_running(false)
	, m_thread(0)
{
	m_wake_pipe[0] = -1;
	m_wake_pipe[1] = -1;

	if (pipe2(m_wake_pipe, O_NONBLOCK | O_CLOEXEC) != 0)
	{
		eWarning("[eDVBCWHandler] Failed to create wake pipe: %m");
		return;
	}

	m_running = true;
	if (pthread_create(&m_thread, nullptr, threadFunc, this) != 0)
	{
		eWarning("[eDVBCWHandler] Failed to create thread: %m");
		m_running = false;
		return;
	}

	eDebug("[eDVBCWHandler] Started");
}

eDVBCWHandler::~eDVBCWHandler()
{
	m_running = false;

	// Wake up poll
	if (m_wake_pipe[1] >= 0)
	{
		char c = 'q';
		(void)::write(m_wake_pipe[1], &c, 1);
	}

	if (m_thread)
		pthread_join(m_thread, nullptr);

	// Close all connections
	{
		std::lock_guard<std::mutex> lock(m_connections_mutex);
		for (auto& conn : m_connections)
		{
			if (conn.softcam_fd >= 0) ::close(conn.softcam_fd);
			if (conn.proxy_fd >= 0) ::close(conn.proxy_fd);
			// client_fd is owned by ePMTClient
		}
		m_connections.clear();
	}

	if (m_wake_pipe[0] >= 0) ::close(m_wake_pipe[0]);
	if (m_wake_pipe[1] >= 0) ::close(m_wake_pipe[1]);

	eDebug("[eDVBCWHandler] Stopped");
}

void eDVBCWHandler::registerEngine(uint32_t serviceId, eDVBCSAEngine* engine, uint8_t ecm_mode)
{
	std::lock_guard<std::mutex> lock(m_targets_mutex);

	// Check if this exact engine is already registered for this serviceId
	auto range = m_targets.equal_range(serviceId);
	for (auto it = range.first; it != range.second; ++it)
	{
		if (it->second.engine == engine)
		{
			// Already registered - just update ecm_mode
			it->second.ecm_mode = ecm_mode;
			eDebug("[eDVBCWHandler] Registered engine for serviceId %u, ecm_mode=0x%02X", serviceId, ecm_mode);
			return;
		}
	}

	// New engine for this serviceId (e.g. Timeshift alongside Live)
	CwTarget target;
	target.engine = engine;
	target.ecm_mode = ecm_mode;
	m_targets.insert({serviceId, target});
	eDebug("[eDVBCWHandler] Registered engine for serviceId %u, ecm_mode=0x%02X", serviceId, ecm_mode);
}

void eDVBCWHandler::unregisterEngine(uint32_t serviceId, eDVBCSAEngine* engine)
{
	std::lock_guard<std::mutex> lock(m_targets_mutex);
	auto range = m_targets.equal_range(serviceId);
	for (auto it = range.first; it != range.second; ++it)
	{
		if (it->second.engine == engine)
		{
			m_targets.erase(it);
			eDebug("[eDVBCWHandler] Unregistered engine for serviceId %u", serviceId);
			return;
		}
	}
	eDebug("[eDVBCWHandler] Unregister: no engine found for serviceId %u", serviceId);
}

void eDVBCWHandler::updateEcmMode(uint32_t serviceId, eDVBCSAEngine* engine, uint8_t ecm_mode)
{
	std::lock_guard<std::mutex> lock(m_targets_mutex);
	auto range = m_targets.equal_range(serviceId);
	for (auto it = range.first; it != range.second; ++it)
	{
		if (it->second.engine == engine)
		{
			if (it->second.ecm_mode != ecm_mode)
			{
				eDebug("[eDVBCWHandler] Updated ecm_mode for serviceId %u to 0x%02X", serviceId, ecm_mode);
				it->second.ecm_mode = ecm_mode;
			}
			return;
		}
	}
}

int eDVBCWHandler::addConnection(int softcam_fd)
{
	int pair[2];
	if (socketpair(AF_UNIX, SOCK_STREAM | SOCK_NONBLOCK | SOCK_CLOEXEC, 0, pair) != 0)
	{
		eWarning("[eDVBCWHandler] socketpair failed: %m");
		return -1;
	}

	// Set softcam_fd to non-blocking for our poll loop
	int flags = fcntl(softcam_fd, F_GETFL, 0);
	if (flags >= 0)
		fcntl(softcam_fd, F_SETFL, flags | O_NONBLOCK);

	Connection conn;
	conn.softcam_fd = softcam_fd;
	conn.proxy_fd = pair[0];  // our end
	conn.client_fd = pair[1]; // ePMTClient's end
	conn.remove = false;

	{
		std::lock_guard<std::mutex> lock(m_connections_mutex);
		conn.id = m_next_id++;
		m_connections.push_back(std::move(conn));
	}

	// Wake up poll loop to pick up new connection
	char c = 'w';
	(void)::write(m_wake_pipe[1], &c, 1);

	eDebug("[eDVBCWHandler] Added connection: softcam_fd=%d, proxy_fd=%d, client_fd=%d", softcam_fd, pair[0], pair[1]);
	return pair[1]; // return the fd for ePMTClient
}

void eDVBCWHandler::removeConnection(int client_fd)
{
	// The proxy thread may be using these fds right now: only mark the
	// connection, the thread closes it.
	std::lock_guard<std::mutex> lock(m_connections_mutex);
	for (auto& conn : m_connections)
	{
		if (conn.client_fd == client_fd && !conn.remove)
		{
			eDebug("[eDVBCWHandler] Removing connection: softcam_fd=%d, client_fd=%d", conn.softcam_fd, client_fd);
			conn.remove = true;

			// Wake up poll loop
			char c = 'w';
			(void)::write(m_wake_pipe[1], &c, 1);
			return;
		}
	}
}

void eDVBCWHandler::closeConnection(Connection& conn)
{
	if (conn.softcam_fd >= 0)
		::close(conn.softcam_fd);
	if (conn.proxy_fd >= 0)
		::close(conn.proxy_fd);  // ePMTClient sees EOF on its end
	conn.softcam_fd = conn.proxy_fd = -1;
}

/* Write what is pending without blocking. False on a broken connection. */
bool eDVBCWHandler::flushPending(int fd, std::vector<uint8_t>& pending)
{
	size_t done = 0;
	while (done < pending.size())
	{
		ssize_t w = ::send(fd, pending.data() + done, pending.size() - done, MSG_NOSIGNAL);
		if (w > 0)
		{
			done += w;
			continue;
		}
		if (w < 0 && errno == EINTR)
			continue;
		if (w < 0 && (errno == EAGAIN || errno == EWOULDBLOCK))
			break;  // the rest goes when poll() reports POLLOUT
		pending.erase(pending.begin(), pending.begin() + done);
		return false;
	}
	pending.erase(pending.begin(), pending.begin() + done);
	return true;
}

void* eDVBCWHandler::threadFunc(void* arg)
{
	static_cast<eDVBCWHandler*>(arg)->threadLoop();
	return nullptr;
}

void eDVBCWHandler::threadLoop()
{
	char buf[4096];

	while (m_running)
	{
		std::vector<struct pollfd> pfds;
		std::vector<int> ids;

		// Wake pipe
		struct pollfd wpfd;
		wpfd.fd = m_wake_pipe[0];
		wpfd.events = POLLIN;
		wpfd.revents = 0;
		pfds.push_back(wpfd);

		{
			std::lock_guard<std::mutex> lock(m_connections_mutex);
			for (auto it = m_connections.begin(); it != m_connections.end();)
			{
				if (it->remove)
				{
					eDebug("[eDVBCWHandler] Closing connection: softcam_fd=%d, proxy_fd=%d", it->softcam_fd, it->proxy_fd);
					closeConnection(*it);
					it = m_connections.erase(it);
					continue;
				}

				// For each connection: poll softcam_fd and proxy_fd, for writing too
				// while something waits to go out
				struct pollfd pfd;
				pfd.fd = it->softcam_fd;
				pfd.events = POLLIN | (it->to_softcam.empty() ? 0 : POLLOUT);
				pfd.revents = 0;
				pfds.push_back(pfd);

				pfd.fd = it->proxy_fd;
				pfd.events = POLLIN | (it->to_client.empty() ? 0 : POLLOUT);
				pfd.revents = 0;
				pfds.push_back(pfd);

				ids.push_back(it->id);
				++it;
			}
		}

		int ret = poll(pfds.data(), pfds.size(), 1000);
		if (ret < 0)
		{
			if (errno == EINTR)
				continue;
			eWarning("[eDVBCWHandler] poll error: %m");
			break;
		}

		if (ret == 0)
			continue;

		// Check wake pipe
		if (pfds[0].revents & POLLIN)
		{
			// Drain pipe
			while (::read(m_wake_pipe[0], buf, sizeof(buf)) > 0);
		}

		std::lock_guard<std::mutex> lock(m_connections_mutex);
		for (size_t i = 0; i < ids.size(); i++)
		{
			// Entries are erased by this thread only, so it is still there
			Connection* conn = nullptr;
			for (auto& c : m_connections)
			{
				if (c.id == ids[i])
				{
					conn = &c;
					break;
				}
			}
			if (!conn || conn->remove)
				continue;

			const short softcam_ev = pfds[1 + i * 2].revents;
			const short proxy_ev = pfds[2 + i * 2].revents;
			bool lost = false;

			// Softcam → ePMTClient (and intercept CWs)
			if (softcam_ev & POLLIN)
			{
				ssize_t n = ::read(conn->softcam_fd, buf, sizeof(buf));
				if (n > 0)
				{
					processCwFromRawPacket(*conn, (const uint8_t*)buf, n);
					// Queued, never dropped: ePMTClient parses a byte stream
					conn->to_client.insert(conn->to_client.end(), buf, buf + n);
				}
				else if (n == 0)
				{
					eDebug("[eDVBCWHandler] Softcam EOF on fd %d", conn->softcam_fd);
					lost = true;
				}
				else if (errno != EINTR && errno != EAGAIN)
				{
					eDebug("[eDVBCWHandler] Softcam read error on fd %d: %m", conn->softcam_fd);
					lost = true;
				}
			}
			else if (softcam_ev & (POLLHUP | POLLERR | POLLNVAL))
			{
				eDebug("[eDVBCWHandler] Softcam disconnected on fd %d", conn->softcam_fd);
				lost = true;
			}

			// ePMTClient → softcam (CAPMT)
			if (!lost && (proxy_ev & POLLIN))
			{
				ssize_t n = ::read(conn->proxy_fd, buf, sizeof(buf));
				if (n > 0)
					conn->to_softcam.insert(conn->to_softcam.end(), buf, buf + n);
				else if (n == 0)
				{
					eDebug("[eDVBCWHandler] ePMTClient EOF on proxy_fd %d", conn->proxy_fd);
					lost = true;
				}
				else if (errno != EINTR && errno != EAGAIN)
				{
					eDebug("[eDVBCWHandler] ePMTClient read error on proxy_fd %d: %m", conn->proxy_fd);
					lost = true;
				}
			}
			else if (!lost && (proxy_ev & (POLLHUP | POLLERR | POLLNVAL)))
			{
				eDebug("[eDVBCWHandler] ePMTClient disconnected on proxy_fd %d", conn->proxy_fd);
				lost = true;
			}

			// Send what each side can take now, the rest on POLLOUT. Never wait
			// here: this thread is what delivers the CWs.
			if (!lost && !flushPending(conn->proxy_fd, conn->to_client))
			{
				eDebug("[eDVBCWHandler] write to ePMTClient failed on proxy_fd %d: %m", conn->proxy_fd);
				lost = true;
			}
			if (!lost && !flushPending(conn->softcam_fd, conn->to_softcam))
			{
				eDebug("[eDVBCWHandler] write to softcam failed on fd %d: %m", conn->softcam_fd);
				lost = true;
			}
			if (!lost && (conn->to_client.size() > MAX_PENDING || conn->to_softcam.size() > MAX_PENDING))
			{
				eWarning("[eDVBCWHandler] %s takes no data, closing connection (softcam_fd=%d)",
					conn->to_client.size() > MAX_PENDING ? "ePMTClient" : "softcam", conn->softcam_fd);
				lost = true;
			}

			if (lost)
				conn->remove = true;  // closed at the top of the next round
		}
	}
}

void eDVBCWHandler::processCwFromRawPacket(Connection& conn, const uint8_t* data, int len)
{
	/*
	 * Softcam Protocol 3 packet format:
	 * [0xA5] [msgid: 4 bytes] [tag: 4 bytes] [data...]
	 *
	 * CA_SET_DESCR tag: 0x40 0x10 0x6F 0x86
	 * CA_SET_DESCR data: 1 byte padding + ca_descr_t (16 bytes) = 17 bytes
	 *
	 * Total CA_SET_DESCR packet: 1 + 4 + 4 + 17 = 26 bytes
	 *
	 * ca_descr_t: { uint32_t index, uint32_t parity, uint8_t cw[8] }
	 *
	 * The socket is a byte stream: when more is queued than one read takes,
	 * a message can be cut between two reads. The start of a CW message cut
	 * off at the end is kept in conn.cw_rest and joined to the next read.
	 */
	static const uint8_t CW_TAG[] = { 0x40, 0x10, 0x6F, 0x86 };
	static const int CW_PACKET_SIZE = 26; // 0xA5 + 4 msgid + 4 tag + 17 data

	std::vector<uint8_t> joined;
	if (!conn.cw_rest.empty())
	{
		joined.swap(conn.cw_rest);
		joined.insert(joined.end(), data, data + len);
		data = joined.data();
		len = (int)joined.size();
	}

	int pos = 0;
	while (pos <= len - CW_PACKET_SIZE)
	{
		// Find next 0xA5 frame start
		if (data[pos] != 0xA5)
		{
			pos++;
			continue;
		}

		// Check if this is a CA_SET_DESCR packet
		// Tag is at offset 5 (after 0xA5 + 4 byte msgid)
		if (memcmp(&data[pos + 5], CW_TAG, 4) != 0)
		{
			// Not a CW packet - skip past this frame start
			pos++;
			continue;
		}

		// Extract serviceId from msgid (bytes 1-4, big-endian)
		uint32_t serviceId;
		memcpy(&serviceId, &data[pos + 1], 4);
		serviceId = ntohl(serviceId);

		// Extract ca_descr_t from data (offset 10 = 1+4+4+1 padding)
		ca_descr_t descr;
		memcpy(&descr, &data[pos + 10], sizeof(ca_descr_t));
		descr.index = ntohl(descr.index);
		descr.parity = ntohl(descr.parity);

		// Deliver CW to all engines registered for this serviceId (Live + Timeshift)
		{
			std::lock_guard<std::mutex> lock(m_targets_mutex);
			auto range = m_targets.equal_range(serviceId);
			for (auto it = range.first; it != range.second; ++it)
			{
				it->second.engine->setKey(descr.parity, it->second.ecm_mode, descr.cw);
				eDebug("[eDVBCWHandler] CW set: parity=%d, hasEven=%d, hasOdd=%d, CW=%02X",
					descr.parity, it->second.engine->hasEvenKey(), it->second.engine->hasOddKey(), descr.cw[0]);
			}
		}

		pos += CW_PACKET_SIZE;
	}

	// Every position before pos had a whole message's room. Keep a frame
	// start in the shorter tail for the next read.
	for (; pos < len; ++pos)
	{
		if (data[pos] == 0xA5)
		{
			conn.cw_rest.assign(data + pos, data + len);
			break;
		}
	}
}
