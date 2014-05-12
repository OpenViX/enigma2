#include <sys/select.h>
#include <unistd.h>
#include <string.h>
#include <openssl/evp.h>
#include <sys/types.h>
#include <pwd.h>
#include <shadow.h>
#include <crypt.h>

#include <lib/base/eerror.h>
#include <lib/base/init.h>
#include <lib/base/init_num.h>
#include <lib/base/wrappers.h>
#include <lib/base/nconfig.h>

#include <lib/dvb/streamserver.h>

eStreamClient::eStreamClient(eStreamServer *handler, int socket)
 : parent(handler), streamFd(socket)
{
	running = false;
}

eStreamClient::~eStreamClient()
{
	rsn->stop();
	stop();
	if (streamFd >= 0) ::close(streamFd);
}

void eStreamClient::start()
{
	rsn = eSocketNotifier::create(eApp, streamFd, eSocketNotifier::Read);
	CONNECT(rsn->activated, eStreamClient::notifier);
}

void eStreamClient::notifier(int what)
{
	if (what & eSocketNotifier::Read)
	{
		char buf[512];
		int len;
		if ((len = singleRead(streamFd, buf, sizeof(buf))) <= 0)
		{
			rsn->stop();
			stop();
			parent->connectionLost(this);
			return;
		}
		request.append(buf, len);
		if (!running)
		{
			if (request.find('\n') != std::string::npos)
			{
				if (request.substr(0, 5) == "GET /")
				{
					size_t pos;
					if (eConfigManager::getConfigBoolValue("config.OpenWebif.auth_for_streaming"))
					{
						bool authenticated = false;
						if ((pos = request.find("Authorization: Basic ")) != std::string::npos)
						{
							std::string authentication, username, password;
							std::string hash = request.substr(pos + 21);
							pos = hash.find('\r');
							hash = hash.substr(0, pos);
							hash += "\n";
							{
								char *in, *out;
								in = strdup(hash.c_str());
								out = (char*)calloc(1, hash.size());
								if (in && out)
								{
									BIO *b64, *bmem;
									b64 = BIO_new(BIO_f_base64());
									bmem = BIO_new_mem_buf(in, hash.size());
									bmem = BIO_push(b64, bmem);
									BIO_read(bmem, out, hash.size());
									BIO_free_all(bmem);
									authentication.append(out, hash.size());
								}
								free(in);
								free(out);
							}
							pos = authentication.find(':');
							if (pos != std::string::npos)
							{
								char *buffer = (char*)malloc(4096);
								if (buffer)
								{
									struct passwd pwd;
									struct passwd *pwdresult = NULL;
									std::string crypt;
									username = authentication.substr(0, pos);
									password = authentication.substr(pos + 1);
									getpwnam_r(username.c_str(), &pwd, buffer, 4096, &pwdresult);
									if (pwdresult)
									{
										struct crypt_data cryptdata;
										crypt = pwd.pw_passwd;
										if (crypt == "*" || crypt == "x")
										{
											struct spwd spwd;
											struct spwd *spwdresult = NULL;
											getspnam_r(username.c_str(), &spwd, buffer, 4096, &spwdresult);
											if (spwdresult)
											{
												crypt = spwd.sp_pwdp;
											}
										}
										authenticated = crypt_r(password.c_str(), crypt.c_str(), &cryptdata) == crypt;
									}
									free(buffer);
								}
							}
						}
						if (!authenticated)
						{
							const char *reply = "HTTP/1.0 401 Authorization Required\r\nWWW-Authenticate: Basic realm=\"streamserver\"\r\n\r\n";
							writeAll(streamFd, reply, strlen(reply));
							rsn->stop();
							parent->connectionLost(this);
							return;
						}
					}
					pos = request.find(' ', 5);
					if (pos != std::string::npos)
					{
						std::string serviceref = urlDecode(request.substr(5, pos - 5));
						if (!serviceref.empty())
						{
							const char *reply = "HTTP/1.0 200 OK\r\nConnection: Close\r\nContent-Type: video/mpeg\r\nServer: streamserver\r\n\r\n";
							writeAll(streamFd, reply, strlen(reply));
							if (eDVBServiceStream::start(serviceref.c_str(), streamFd) >= 0)
							{
								running = true;
							}
						}
					}
				}
				if (!running)
				{
					const char *reply = "HTTP/1.0 400 Bad Request\r\n\r\n";
					writeAll(streamFd, reply, strlen(reply));
					rsn->stop();
					parent->connectionLost(this);
					return;
				}
				request.clear();
			}
		}
	}
}

void eStreamClient::streamStopped()
{
	rsn->stop();
	parent->connectionLost(this);
}

void eStreamClient::tuneFailed()
{
	rsn->stop();
	parent->connectionLost(this);
}

DEFINE_REF(eStreamServer);

eStreamServer::eStreamServer()
 : eServerSocket(8001, eApp)
{
}

eStreamServer::~eStreamServer()
{
	for (eSmartPtrList<eStreamClient>::iterator it = clients.begin(); it != clients.end(); )
	{
		it = clients.erase(it);
	}
}

void eStreamServer::newConnection(int socket)
{
	ePtr<eStreamClient> client = new eStreamClient(this, socket);
	clients.push_back(client);
	client->start();
}

void eStreamServer::connectionLost(eStreamClient *client)
{
	eSmartPtrList<eStreamClient>::iterator it = std::find(clients.begin(), clients.end(), client );
	if (it != clients.end())
	{
		clients.erase(it);
	}
}

eAutoInitPtr<eStreamServer> init_eStreamServer(eAutoInitNumbers::dvb + 1, "Stream server");
