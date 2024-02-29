#ifndef __picload_h__
#define __picload_h__

#include <lib/gdi/gpixmap.h>
#include <lib/gdi/picexif.h>
#include <lib/base/thread.h>
#include <lib/python/python.h>
#include <lib/base/message.h>
#include <lib/base/ebase.h>

#ifndef SWIG
struct Cfilepara
{
	char *file;
	unsigned char *pic_buffer;
	gRGB *palette;
	int palette_size;
	int bits;
	int id;
	int max_x;
	int max_y;
	int ox;
	int oy;
	std::string picinfo;
	bool callback;

	Cfilepara(const char *mfile, int mid, std::string size):
		file(strdup(mfile)),
		pic_buffer(NULL),
		palette(NULL),
		palette_size(0),
		bits(24),
		id(mid),
		picinfo(""),
		callback(true)
	{
		if (is_valid_utf8(mfile))
			picinfo += std::string(mfile) + "\n" + size + "\n";
		else
			picinfo += "\n" + size + "\n";
	}

	~Cfilepara()
	{
		if (pic_buffer != NULL)	delete [] pic_buffer;
		if (palette != NULL) delete [] palette;
		free(file);
	}

	void addExifInfo(std::string val) { picinfo += val + "\n"; }
	bool is_valid_utf8(const char * string)
	{
		if (!string)
			return true;
		const unsigned char * bytes = (const unsigned char *)string;
		unsigned int cp;
		int num;
		while (*bytes != 0x00)
		{
			if ((*bytes & 0x80) == 0x00)
			{
				// U+0000 to U+007F
				cp = (*bytes & 0x7F);
				num = 1;
			}
			else if ((*bytes & 0xE0) == 0xC0)
			{
				// U+0080 to U+07FF
				cp = (*bytes & 0x1F);
				num = 2;
			}
			else if ((*bytes & 0xF0) == 0xE0)
			{
				// U+0800 to U+FFFF
				cp = (*bytes & 0x0F);
				num = 3;
			}
			else if ((*bytes & 0xF8) == 0xF0)
			{
				// U+10000 to U+10FFFF
				cp = (*bytes & 0x07);
				num = 4;
			}
			else
				return false;
			bytes += 1;
			for (int i = 1; i < num; ++i)
			{
				if ((*bytes & 0xC0) != 0x80)
					return false;
				cp = (cp << 6) | (*bytes & 0x3F);
				bytes += 1;
			}
			if ((cp > 0x10FFFF) ||
				((cp >= 0xD800) && (cp <= 0xDFFF)) ||
				((cp <= 0x007F) && (num != 1)) ||
				((cp >= 0x0080) && (cp <= 0x07FF) && (num != 2)) ||
				((cp >= 0x0800) && (cp <= 0xFFFF) && (num != 3)) ||
				((cp >= 0x10000) && (cp <= 0x1FFFFF) && (num != 4)))
				return false;
		}
		return true;
	}
};
#endif

class ePicLoad: public eMainloop, public eThread, public sigc::trackable, public iObject
{
	DECLARE_REF(ePicLoad);

	void decodePic();
	void decodeThumb();

	Cfilepara *m_filepara;
	Cexif *m_exif;
	bool threadrunning;

	struct PConf
	{
		int max_x;
		int max_y;
		double aspect_ratio;
		int background;
		bool resizetype;
		bool usecache;
		bool auto_orientation;
		int thumbnailsize;
		int test;
		PConf();
	} m_conf;

	struct Message
	{
		int type;
		enum
		{
			decode_Pic,
			decode_Thumb,
			decode_finished,
			quit
		};
		Message(int type=0)
			:type(type) {}
	};
	eFixedMessagePump<Message> msg_thread, msg_main;

	void gotMessage(const Message &message);
	void thread();
	int startThread(int what, const char *file, int x, int y, bool async=true);
	void thread_finished();
	bool getExif(const char *filename, int fileType=F_JPEG, int Thumb=0);
	int getFileType(const char * file);
public:
	void waitFinished();
	PSignal1<void, const char*> PictureData;

	ePicLoad();
	~ePicLoad();

#ifdef SWIG
%typemap(in) (const char *filename) {
	if (PyBytes_Check($input)) {
		$1 = PyBytes_AsString($input);
	} else {
		$1 = PyBytes_AsString(PyUnicode_AsEncodedString($input, "utf-8", "surrogateescape"));
	}
}
#endif
	RESULT startDecode(const char *filename, int x=0, int y=0, bool async=true);
	RESULT getThumbnail(const char *filename, int x=0, int y=0, bool async=true);
	RESULT setPara(PyObject *val);
	RESULT setPara(int width, int height, double aspectRatio, int as, bool useCache, int resizeType, const char *bg_str, bool auto_orientation);
	PyObject *getInfo(const char *filename);
	SWIG_VOID(int) getData(ePtr<gPixmap> &SWIG_OUTPUT);
};

//for old plugins
SWIG_VOID(int) loadPic(ePtr<gPixmap> &SWIG_OUTPUT, std::string filename, int x, int y, int aspect, int resize_mode=0, int rotate=0, int background=0, std::string cachefile="");

#endif // __picload_h__
