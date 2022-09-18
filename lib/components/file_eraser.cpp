#include <lib/components/file_eraser.h>
#include <lib/base/ioprio.h>
#include <lib/base/eerror.h>
#include <lib/base/init.h>
#include <lib/base/init_num.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <stdio.h>

eBackgroundFileEraser *eBackgroundFileEraser::instance;

eBackgroundFileEraser::eBackgroundFileEraser():
	messages(this,1, "eBackgroundFileEraser"),
	stop_thread_timer(eTimer::create(this))
{
	if (!instance)
		instance=this;
	CONNECT(messages.recv_msg, eBackgroundFileEraser::gotMessage);
	CONNECT(stop_thread_timer->timeout, eBackgroundFileEraser::idle);
}

void eBackgroundFileEraser::idle()
{
	quit(0);
}

eBackgroundFileEraser::~eBackgroundFileEraser()
{
	messages.send(Message());
	if (instance==this)
		instance=0;
	// Wait for the thread to complete. Must do that here,
	// because in C++ the object will be demoted after this
	// returns.
	kill();
}

void eBackgroundFileEraser::thread()
{
	hasStarted();
	if (nice(5) == -1)
	{
		eDebug("[eBackgroundFileEraser] thread failed to modify scheduling priority (%m)");
	}
	setIoPrio(IOPRIO_CLASS_BE, 7);
	reset();
	runLoop();
	stop_thread_timer->stop();
}

void eBackgroundFileEraser::erase(const std::string& filename)
{
	if (!filename.empty())
	{
		std::string delname(filename);
		delname.append(".del");
		if (rename(filename.c_str(), delname.c_str())<0)
		{
			if (errno == ENOENT)		/* if rename fails with ENOENT (file doesn't exist), do nothing */
			{
				eDebug("[eBackgroundFileEraser] filename %s not found: %m", filename.c_str());
				return;
			} else
			{				/* if rename fails, try deleting the file itself without renaming. */
				eDebug("[eBackgroundFileEraser] Rename %s -> %s failed: %m", filename.c_str(), delname.c_str());
				delname = filename;
			}
		}
		messages.send(Message(delname));
		run();
	} else
	{
		eDebug("[eBackgroundFileEraser] empty filename (%m)");
	}
}

void eBackgroundFileEraser::erase(const char* filename2)
{
	std::string filename(filename2);
	erase(filename);
}

void eBackgroundFileEraser::gotMessage(const Message &msg )
{
	if (msg.filename.empty())
	{
		quit(0);
	}
	else
	{
		const char* c_filename = msg.filename.c_str();
		if ( ::remove(c_filename) < 0 )
		{			
			eDebug("[eBackgroundFileEraser] removing %s failed: %m", c_filename);

		} else
		{
			eDebug("[eBackgroundFileEraser] removing %s OK", c_filename);				
		}
		stop_thread_timer->start(1000, true); // stop thread in one seconds
	}
}


eAutoInitP0<eBackgroundFileEraser> init_eBackgroundFilEraser(eAutoInitNumbers::configuration+1, "Background File Eraser");
