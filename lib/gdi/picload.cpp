#define PNG_SKIP_SETJMP_CHECK
#include <png.h>
#include <fcntl.h>

#include <lib/base/cfile.h>
#include <lib/base/wrappers.h>
#include <lib/gdi/picload.h>

extern "C" {
#define HAVE_BOOLEAN
#define boolean int
#include <jpeglib.h>
#include <gif_lib.h>
}

#define NANOSVG_ALL_COLOR_KEYWORDS
#define NANOSVG_IMPLEMENTATION
#include <nanosvg.h>
#define NANOSVGRAST_IMPLEMENTATION
#include <nanosvgrast.h>

extern const uint32_t crc32_table[256];

DEFINE_REF(ePicLoad);

static std::string getSize(const char* file)
{
	struct stat64 s;
	if (stat64(file, &s) < 0)
		return "";
	return std::to_string((long)(s.st_size / 1024)) + " kB";
}

static unsigned char *color_resize(unsigned char * orgin, int ox, int oy, int dx, int dy)
{
	unsigned char* cr = new unsigned char[dx * dy * 3];
	if (cr == NULL)
	{
		eDebug("[ePicLoad] resize Error malloc");
		return orgin;
	}
	const int stride = 3 * dx;
	#pragma omp parallel for
	for (int j = 0; j < dy; j++)
	{
		unsigned char* p = cr + (j * stride);
		int ya = j * oy / dy;
		int yb = (j + 1) * oy / dy;
		if (yb >= oy)
			yb = oy - 1;
		for (int i = 0; i < dx; i++, p += 3)
		{
			int xa = i * ox / dx;
			int xb = (i + 1) * ox / dx;
			if (xb >= ox)
				xb = ox - 1;
			int r = 0;
			int g = 0;
			int b = 0;
			int sq = 0;
			for (int l = ya; l <= yb; l++)
			{
				const unsigned char* q = orgin + ((l * ox + xa) * 3);
				for (int k = xa; k <= xb; k++, q += 3, sq++)
				{
					r += q[0];
					g += q[1];
					b += q[2];
				}
			}
			p[0] = r / sq;
			p[1] = g / sq;
			p[2] = b / sq;
		}
	}
	delete [] orgin;
	return cr;
}

//---------------------------------------------------------------------------------------------

#define BMP_TORASTER_OFFSET 10
#define BMP_SIZE_OFFSET 18
#define BMP_BPP_OFFSET 28
#define BMP_RLE_OFFSET 30
#define BMP_COLOR_OFFSET 54

#define fill4B(a) ((4 - ((a) % 4 )) & 0x03)

struct color {
	unsigned char red;
	unsigned char green;
	unsigned char blue;
};

static void fetch_pallete(int fd, struct color pallete[], int count)
{
	unsigned char buff[4];
	lseek(fd, BMP_COLOR_OFFSET, SEEK_SET);
	for (int i = 0; i < count; i++)
	{
		if (read(fd, buff, 4) != 4) // failed to read rgb
		{
			break;
		}
		pallete[i].red = buff[2];
		pallete[i].green = buff[1];
		pallete[i].blue = buff[0];
	}
}

static unsigned char *bmp_load(const char *file,  int *x, int *y)
{
	unsigned char buff[4];
	struct color pallete[256];

	int fd = open(file, O_RDONLY);
	if (fd == -1) return NULL;
	if (lseek(fd, BMP_SIZE_OFFSET, SEEK_SET) == -1) return NULL;
	if (read(fd, buff, 4) != 4) // failed to read x
	{
		close(fd);
		return NULL;
	}
	*x = buff[0] + (buff[1] << 8) + (buff[2] << 16) + (buff[3] << 24);
	if (read(fd, buff, 4) != 4) // failed to read y
	{
		close(fd);
		return NULL;
	}
	*y = buff[0] + (buff[1] << 8) + (buff[2] << 16) + (buff[3] << 24);
	if (lseek(fd, BMP_TORASTER_OFFSET, SEEK_SET) == -1)
	{
		close(fd);
		return NULL;
	}
	if (read(fd, buff, 4) != 4) // failed to read raster
	{
		close(fd);
		return NULL;
	}
	int raster = buff[0] + (buff[1] << 8) + (buff[2] << 16) + (buff[3] << 24);
	if (lseek(fd, BMP_BPP_OFFSET, SEEK_SET) == -1)
	{
		close(fd);
		return NULL;
	}
	if (read(fd, buff, 2) != 2) // failed to read bpp
	{
		close(fd);
		return NULL;
	}
	int bpp = buff[0] + (buff[1] << 8);

	unsigned char *pic_buffer = new unsigned char[(*x) * (*y) * 3];
	unsigned char *wr_buffer = pic_buffer + (*x) * ((*y) - 1) * 3;

	switch (bpp)
	{
		case 4:
		{
			int skip = fill4B((*x) / 2 + (*x) % 2);
			fetch_pallete(fd, pallete, 16);
			lseek(fd, raster, SEEK_SET);
			unsigned char * tbuffer = new unsigned char[*x / 2 + 1];
			if (tbuffer == NULL)
				return NULL;
			for (int i = 0; i < *y; i++)
			{
				if (read(fd, tbuffer, (*x) / 2 + *x % 2) != ((*x) / 2 + *x % 2))
				{
					eDebug("[ePicLoad] failed to read %d bytes...", ((*x) / 2 + *x % 2));
				}
				int j;
				for (j = 0; j < (*x) / 2; j++)
				{
					unsigned char c1 = tbuffer[j] >> 4;
					unsigned char c2 = tbuffer[j] & 0x0f;
					*wr_buffer++ = pallete[c1].red;
					*wr_buffer++ = pallete[c1].green;
					*wr_buffer++ = pallete[c1].blue;
					*wr_buffer++ = pallete[c2].red;
					*wr_buffer++ = pallete[c2].green;
					*wr_buffer++ = pallete[c2].blue;
				}
				if ((*x) % 2)
				{
					unsigned char c1 = tbuffer[j] >> 4;
					*wr_buffer++ = pallete[c1].red;
					*wr_buffer++ = pallete[c1].green;
					*wr_buffer++ = pallete[c1].blue;
				}
				if (skip)
				{
					if (read(fd, buff, skip) != skip)
					{
						eDebug("[ePicLoad] failed to read %d bytes...", skip);
					}
				}
				wr_buffer -= (*x) * 6;
			}
			delete [] tbuffer;
			break;
		}
		case 8:
		{
			int skip = fill4B(*x);
			fetch_pallete(fd, pallete, 256);
			lseek(fd, raster, SEEK_SET);
			unsigned char * tbuffer = new unsigned char[*x];
			if (tbuffer == NULL)
				return NULL;
			for (int i = 0; i < *y; i++)
			{
				if (read(fd, tbuffer, *x) != *x)
				{
					eDebug("[ePicLoad] failed to read %d bytes...", *x);
				}
				for (int j = 0; j < *x; j++)
				{
					wr_buffer[j * 3] = pallete[tbuffer[j]].red;
					wr_buffer[j * 3 + 1] = pallete[tbuffer[j]].green;
					wr_buffer[j * 3 + 2] = pallete[tbuffer[j]].blue;
				}
				if (skip)
				{
					if (read(fd, buff, skip) != skip)
					{
						eDebug("[ePicLoad] failed to skip %d bytes...", skip);
					}
				}
				wr_buffer -= (*x) * 3;
			}
			delete [] tbuffer;
			break;
		}
		case 24:
		{
			int skip = fill4B((*x) * 3);
			lseek(fd, raster, SEEK_SET);
			for (int i = 0; i < (*y); i++)
			{
				if (read(fd, wr_buffer, (*x) * 3) != ((*x) * 3))
				{
					eDebug("[picload] failed to read %d bytes...", ((*x) * 3));
				}
				for (int j = 0; j < (*x) * 3 ; j = j + 3)
				{
					unsigned char c = wr_buffer[j];
					wr_buffer[j] = wr_buffer[j + 2];
					wr_buffer[j + 2] = c;
				}
				if (skip)
				{
					if (read(fd, buff, skip) != skip)
					{
						eDebug("[ePicLoad] failed to skip %d bytes...", skip);
					}
				}
				wr_buffer -= (*x) * 3;
			}
			break;
		}
		default:
			close(fd);
			return NULL;
	}

	close(fd);
	return(pic_buffer);
}

//---------------------------------------------------------------------

static void png_load(Cfilepara* filepara, int background, bool forceRGB=false)
{
	png_uint_32 width, height;
	unsigned int i;
	int bit_depth, color_type, interlace_type;
	png_byte *fbptr;
	CFile fh(filepara->file, "rb");
	if (!fh)
		return;

	png_structp png_ptr = png_create_read_struct(PNG_LIBPNG_VER_STRING, NULL, NULL, NULL);
	if (png_ptr == NULL)
		return;
	png_infop info_ptr = png_create_info_struct(png_ptr);
	if (info_ptr == NULL)
	{
		png_destroy_read_struct(&png_ptr, (png_infopp)NULL, (png_infopp)NULL);
		return;
	}

	if (setjmp(png_jmpbuf(png_ptr)))
	{
		png_destroy_read_struct(&png_ptr, &info_ptr, (png_infopp)NULL);
		return;
	}

	png_init_io(png_ptr, fh);

	png_read_info(png_ptr, info_ptr);
	png_get_IHDR(png_ptr, info_ptr, &width, &height, &bit_depth, &color_type, &interlace_type, NULL, NULL);

	if (!forceRGB && (color_type == PNG_COLOR_TYPE_GRAY || color_type & PNG_COLOR_MASK_PALETTE))
	{
		if (bit_depth < 8)
		{
			png_set_packing(png_ptr);
			bit_depth = 8;
		}
		unsigned char *pic_buffer = new unsigned char[height * width];
		filepara->ox = width;
		filepara->oy = height;
		filepara->pic_buffer = pic_buffer;
		filepara->bits = 8;

		png_bytep *rowptr=new png_bytep[height];
		for (unsigned int i=0; i!=height; i++)
		{
			rowptr[i]=(png_byte*)pic_buffer;
			pic_buffer += width;
		}
		png_read_rows(png_ptr, rowptr, 0, height);
		delete [] rowptr;

		if (png_get_valid(png_ptr, info_ptr, PNG_INFO_PLTE))
		{
			png_color *palette;
			int num_palette;
			png_get_PLTE(png_ptr, info_ptr, &palette, &num_palette);
			filepara->palette_size = num_palette;
			if (num_palette)
				filepara->palette = new gRGB[num_palette];
			for (int i=0; i<num_palette; i++)
			{
				filepara->palette[i].a=0;
				filepara->palette[i].r=palette[i].red;
				filepara->palette[i].g=palette[i].green;
				filepara->palette[i].b=palette[i].blue;
			}
			if (png_get_valid(png_ptr, info_ptr, PNG_INFO_tRNS))
			{
				png_byte *trans;
				png_get_tRNS(png_ptr, info_ptr, &trans, &num_palette, 0);
				for (int i=0; i<num_palette; i++)
					filepara->palette[i].a=255-trans[i];
			}
		}
	}
	else
	{
		if (bit_depth == 16)
			png_set_strip_16(png_ptr);
		if (color_type == PNG_COLOR_TYPE_GRAY || color_type == PNG_COLOR_TYPE_GRAY_ALPHA)
			png_set_gray_to_rgb(png_ptr);
		if (color_type & PNG_COLOR_MASK_PALETTE)
			png_set_palette_to_rgb(png_ptr);
		if (color_type & PNG_COLOR_MASK_ALPHA || png_get_valid(png_ptr, info_ptr, PNG_INFO_tRNS))
		{
			png_set_strip_alpha(png_ptr);
			png_color_16 bg;
			bg.red = (background >> 16) & 0xFF;
			bg.green = (background >> 8) & 0xFF;
			bg.blue = (background) & 0xFF;
			bg.gray = bg.green;
			bg.index = 0;
			png_set_background(png_ptr, &bg, PNG_BACKGROUND_GAMMA_SCREEN, 0, 1.0);
		}
		png_read_update_info(png_ptr, info_ptr);

		if (width * 3 != png_get_rowbytes(png_ptr, info_ptr))
		{
			eDebug("[ePicLoad] Error processing (did not get RGB data from PNG file)");
			png_destroy_read_struct(&png_ptr, &info_ptr, (png_infopp)NULL);
			return;
		}

		unsigned char *pic_buffer = new unsigned char[height * width * 3];
		filepara->ox = width;
		filepara->oy = height;
		filepara->pic_buffer = pic_buffer;

		int number_passes = png_set_interlace_handling(png_ptr);
		for(int pass = 0; pass < number_passes; pass++)
		{
			fbptr = (png_byte *)pic_buffer;
			for (i = 0; i < height; i++, fbptr += width * 3)
				png_read_row(png_ptr, fbptr, NULL);
		}
		png_read_end(png_ptr, info_ptr);
	}
	png_destroy_read_struct(&png_ptr, &info_ptr, (png_infopp)NULL);
}

//-------------------------------------------------------------------

struct r_jpeg_error_mgr
{
	struct jpeg_error_mgr pub;
	jmp_buf envbuffer;
};

void jpeg_cb_error_exit(j_common_ptr cinfo)
{
	struct r_jpeg_error_mgr *mptr;
	mptr = (struct r_jpeg_error_mgr *) cinfo->err;
	(*cinfo->err->output_message) (cinfo);
	longjmp(mptr->envbuffer, 1);
}

static unsigned char *jpeg_load(const char *file, int *ox, int *oy, unsigned int max_x, unsigned int max_y)
{
	struct jpeg_decompress_struct cinfo;
	struct jpeg_decompress_struct *ciptr = &cinfo;
	struct r_jpeg_error_mgr emgr;
	unsigned char *pic_buffer;
	CFile fh(file, "rb");

	pic_buffer = nullptr;

	if (!fh)
		return NULL;

	ciptr->err = jpeg_std_error(&emgr.pub);
	emgr.pub.error_exit = jpeg_cb_error_exit;
	if (setjmp(emgr.envbuffer) == 1)
	{
		jpeg_destroy_decompress(ciptr);
		return NULL;
	}

	jpeg_create_decompress(ciptr);
	jpeg_stdio_src(ciptr, fh);
	jpeg_read_header(ciptr, TRUE);
	ciptr->out_color_space = JCS_RGB;

	if (max_x == 0) max_x = 1280; // sensible default
	if (max_y == 0) max_y = 720;
	// define scale to always fit vertically or horizontally in all orientations
	ciptr->scale_denom = 8;
	unsigned int screenmax = max_x > max_y ? max_x : max_y;
	unsigned int imagemin  = ciptr->image_width < ciptr->image_height ? ciptr->image_width : ciptr->image_height;
	ciptr->scale_num = (ciptr->scale_denom * screenmax + imagemin -1) / imagemin;
	if (ciptr->scale_num < 1)  ciptr->scale_num = 1;
	if (ciptr->scale_num > 16) ciptr->scale_num = 16;

	jpeg_start_decompress(ciptr);

	*ox=ciptr->output_width;
	*oy=ciptr->output_height;
	//eDebug("[jpeg_load] ox=%d oy=%d w=%d (%d), h=%d (%d) scale=%d rec_outbuf_height=%d", ciptr->output_width, ciptr->output_height, ciptr->image_width, max_x, ciptr->image_height, max_y, ciptr->scale_num, ciptr->rec_outbuf_height);

	if(ciptr->output_components == 3)
	{
		unsigned int stride = ciptr->output_width * ciptr->output_components;
		pic_buffer = new unsigned char[ciptr->output_height * stride];
		unsigned char *bp = pic_buffer;

		while (ciptr->output_scanline < ciptr->output_height)
		{
			JDIMENSION lines = jpeg_read_scanlines(ciptr, &bp, ciptr->rec_outbuf_height);
			bp += stride * lines;
		}
	}
	jpeg_finish_decompress(ciptr);
	jpeg_destroy_decompress(ciptr);
	return(pic_buffer);
}


static int jpeg_save(const char * filename, int ox, int oy, unsigned char *pic_buffer)
{
	struct jpeg_compress_struct cinfo;
	struct jpeg_error_mgr jerr;
	JSAMPROW row_pointer[1];
	int row_stride;
	CFile outfile(filename, "wb");

	if (!outfile)
	{
		eDebug("[ePicLoad] jpeg can't write %s: %m", filename);
		return 1;
	}

	cinfo.err = jpeg_std_error(&jerr);
	jpeg_create_compress(&cinfo);

	eDebug("[ePicLoad] save Thumbnail... %s",filename);

	jpeg_stdio_dest(&cinfo, outfile);

	cinfo.image_width = ox;
	cinfo.image_height = oy;
	cinfo.input_components = 3;
	cinfo.in_color_space = JCS_RGB;
	jpeg_set_defaults(&cinfo);
	jpeg_set_quality(&cinfo, 70, TRUE );
	jpeg_start_compress(&cinfo, TRUE);
	row_stride = ox * 3;
	while (cinfo.next_scanline < cinfo.image_height)
	{
		row_pointer[0] = & pic_buffer[cinfo.next_scanline * row_stride];
		(void) jpeg_write_scanlines(&cinfo, row_pointer, 1);
	}
	jpeg_finish_compress(&cinfo);
	jpeg_destroy_compress(&cinfo);
	return 0;
}

//-------------------------------------------------------------------

inline void m_rend_gif_decodecolormap(unsigned char *cmb, unsigned char *rgbb, ColorMapObject *cm, int s, int l)
{
	GifColorType *cmentry;
	int i;
	for (i = 0; i < l; i++)
	{
		cmentry = &cm->Colors[cmb[i]];
		*(rgbb++) = cmentry->Red;
		*(rgbb++) = cmentry->Green;
		*(rgbb++) = cmentry->Blue;
	}
}

static void svg_load(Cfilepara* filepara, bool forceRGB = false)
{
	NSVGimage *image = nullptr;
	NSVGrasterizer *rast = nullptr;
	unsigned char *pic_buffer = nullptr;
	int w = 0;
	int h = 0;
	double xscale, yscale, scale;

	image = nsvgParseFromFile(filepara->file, "px", 96.0f);
	if (image == nullptr)
	{
		return;
	}

	rast = nsvgCreateRasterizer();
	if (rast == nullptr)
	{
		nsvgDelete(image);
		return;
	}

	xscale = ((double) filepara->max_x) / image->width;
	yscale = ((double) filepara->max_y) / image->height;
	scale =  xscale > yscale ? yscale : xscale;

	w = image->width*scale;
	h = image->height*scale;

	pic_buffer = (unsigned char*)malloc(w*h*4);
	if (pic_buffer == nullptr)
	{
		nsvgDeleteRasterizer(rast);
		nsvgDelete(image);
		return;
	}

	eDebug("[ePicLoad] svg_load max %dx%d from %dx%d scale %f new %dx%d", filepara->max_x, filepara->max_y, (int)image->width, (int)image->height, scale, w, h);
	// Rasterizes SVG image, returns RGBA image (non-premultiplied alpha)
	nsvgRasterize(rast, image, 0, 0, scale, pic_buffer, w, h, w*4);

	filepara->pic_buffer = pic_buffer;
	filepara->bits = 32;
	filepara->ox = w;
	filepara->oy = h;

	nsvgDeleteRasterizer(rast);
	nsvgDelete(image);

	if(forceRGB) // convert 32bit RGBA to 24bit RGB
	{
		unsigned char *pic_buffer2 = (unsigned char*)malloc(w*h*3); // 24bit RGB
		if (pic_buffer2 == nullptr)
		{
			return;
		}
		for (int i=0; i<w*h; i++)
		{
			pic_buffer2[3*i]   = pic_buffer[4*i];
			pic_buffer2[3*i+1] = pic_buffer[4*i+1];
			pic_buffer2[3*i+2] = pic_buffer[4*i+2];
		}
		filepara->bits = 24;
		filepara->pic_buffer = pic_buffer2;
		free(pic_buffer);
	}
}

static void gif_load(Cfilepara* filepara, bool forceRGB = false)
{
	unsigned char *pic_buffer = NULL;
	int px, py, i, j;
	unsigned char *slb=NULL;
	GifFileType *gft;
	GifRecordType rt;
	GifByteType *extension;
	ColorMapObject *cmap;
	int cmaps;
	int extcode;

#if GIFLIB_MAJOR > 5 || GIFLIB_MAJOR == 5 && GIFLIB_MINOR >= 1
	gft = DGifOpenFileName(filepara->file, &extcode);
#else
	gft = DGifOpenFileName(filepara->file);
#endif
	if (gft == NULL)
		return;
	do
	{
		if (DGifGetRecordType(gft, &rt) == GIF_ERROR)
			goto ERROR_R;
		switch(rt)
		{
			case IMAGE_DESC_RECORD_TYPE:
				if (DGifGetImageDesc(gft) == GIF_ERROR)
					goto ERROR_R;
				filepara->ox = px = gft->Image.Width;
				filepara->oy = py = gft->Image.Height;
				pic_buffer = new unsigned char[px * py];
				filepara->pic_buffer = pic_buffer;
				filepara->bits = 8;
				slb = pic_buffer;

				if (pic_buffer != NULL)
				{
					cmap = (gft->Image.ColorMap ? gft->Image.ColorMap : gft->SColorMap);
					cmaps = cmap->ColorCount;
					filepara->palette_size = cmaps;
					filepara->palette = new gRGB[cmaps];
					for (i = 0; i != cmaps; ++i)
					{
						filepara->palette[i].a = 0;
						filepara->palette[i].r = cmap->Colors[i].Red;
						filepara->palette[i].g = cmap->Colors[i].Green;
						filepara->palette[i].b = cmap->Colors[i].Blue;
					}

					if (!(gft->Image.Interlace))
					{
						for (i = 0; i < py; i++)
						{
							if (DGifGetLine(gft, slb, px) == GIF_ERROR)
								goto ERROR_R;
							slb += px;
						}
					}
					else
					{
						int IOffset[] = { 0, 4, 2, 1 }; // The way Interlaced image should.
						int IJumps[] = { 8, 8, 4, 2 };  // be read - offsets and jumps...
						for (j = 0; j < 4; j++)
						{
							for (i = IOffset[j]; i < py; i += IJumps[j])
							{
								if (DGifGetLine(gft, pic_buffer + i*px, px) == GIF_ERROR)
									goto ERROR_R;
							}
						}
					}
					if (forceRGB) {
						unsigned char *pic_buffer2 = new unsigned char[px * py * 3];
						if (pic_buffer2 != NULL) {
							unsigned char *slb2 = pic_buffer2;
							slb = pic_buffer;
							for (j = 0; j < py; j++) {
								for (i = 0; i < px; i++) {
									int c = *slb++;
									*slb2++ = filepara->palette[c].r;
									*slb2++ = filepara->palette[c].g;
									*slb2++ = filepara->palette[c].b;
								}
							}
							filepara->bits = 24;
							filepara->pic_buffer = pic_buffer2;
							delete [] pic_buffer;
							delete [] filepara->palette;
							filepara->palette = NULL;
						}
					}
				}
				break;
			case EXTENSION_RECORD_TYPE:
				if (DGifGetExtension(gft, &extcode, &extension) == GIF_ERROR)
					goto ERROR_R;
				while (extension != NULL)
					if (DGifGetExtensionNext(gft, &extension) == GIF_ERROR)
						goto ERROR_R;
				break;
			default:
				break;
		}
	}
	while (rt != TERMINATE_RECORD_TYPE);

#if GIFLIB_MAJOR > 5 || GIFLIB_MAJOR == 5 && GIFLIB_MINOR >= 1
	DGifCloseFile(gft, &extcode);
#else
	DGifCloseFile(gft);
#endif
	return;
ERROR_R:
	eDebug("[ePicLoad] <Error gif>");
#if GIFLIB_MAJOR > 5 || GIFLIB_MAJOR == 5 && GIFLIB_MINOR >= 1
	DGifCloseFile(gft, &extcode);
#else
	DGifCloseFile(gft);
#endif
}

//---------------------------------------------------------------------------------------------

ePicLoad::ePicLoad():
	m_filepara(NULL),
	m_exif(NULL),
	threadrunning(false),
	m_conf(),
	msg_thread(this,1),
	msg_main(eApp,1)
{
	CONNECT(msg_thread.recv_msg, ePicLoad::gotMessage);
	CONNECT(msg_main.recv_msg, ePicLoad::gotMessage);
}

ePicLoad::PConf::PConf():
	max_x(0),
	max_y(0),
	aspect_ratio(1.066400), //4:3
	background(0),
	resizetype(1),
	usecache(false),
	auto_orientation(false),
	thumbnailsize(180)
{
}

void ePicLoad::waitFinished()
{
	msg_thread.send(Message(Message::quit));
	kill();
}

ePicLoad::~ePicLoad()
{
	if (threadrunning)
		waitFinished();
	if (m_filepara != NULL)
		delete m_filepara;
	if (m_exif != NULL) {
		m_exif->ClearExif();
		delete m_exif;
	}
}

void ePicLoad::thread_finished()
{
	threadrunning = false;
}

void ePicLoad::thread()
{
	threadrunning = true;
	hasStarted();
	if (nice(4))
	{
		eDebug("[ePicLoad] thread failed to modify scheduling priority (%m)");
	}
	runLoop();
}

void ePicLoad::decodePic()
{
	eDebug("[ePicLoad] decode picture... %s", m_filepara->file);

	getExif(m_filepara->file, m_filepara->id);
	switch(m_filepara->id)
	{
		case F_PNG:	png_load(m_filepara, m_conf.background);
				break;
		case F_JPEG:	m_filepara->pic_buffer = jpeg_load(m_filepara->file, &m_filepara->ox, &m_filepara->oy, m_filepara->max_x, m_filepara->max_y);
				break;
		case F_BMP:	m_filepara->pic_buffer = bmp_load(m_filepara->file, &m_filepara->ox, &m_filepara->oy);
				break;
		case F_GIF:	gif_load(m_filepara);
				break;
		case F_SVG:	svg_load(m_filepara);
				break;
	}
}

void ePicLoad::decodeThumb()
{
	eDebug("[ePicLoad] get Thumbnail... %s", m_filepara->file);

	bool exif_thumbnail = false;
	bool cachefile_found = false;
	std::string cachefile = "";
	std::string cachedir = "/.Thumbnails";

	getExif(m_filepara->file, m_filepara->id, 1);
	if (m_exif && m_exif->m_exifinfo->IsExif)
	{
		if (m_exif->m_exifinfo->Thumnailstate == 2)
		{
			free(m_filepara->file);
			m_filepara->file = strdup(THUMBNAILTMPFILE);
			m_filepara->id = F_JPEG; // imbedded thumbnail seem to be jpeg
			exif_thumbnail = true;
			eDebug("[ePicLoad] decodeThumb: Exif Thumbnail found");
		}
		//else
		//	eDebug("[ePicLoad] decodeThumb: NO Exif Thumbnail found");
		m_filepara->addExifInfo(m_exif->m_exifinfo->CameraMake);
		m_filepara->addExifInfo(m_exif->m_exifinfo->CameraModel);
		m_filepara->addExifInfo(m_exif->m_exifinfo->DateTime);
		char buf[20];
		snprintf(buf, 20, "%d x %d", m_exif->m_exifinfo->Width, m_exif->m_exifinfo->Height);
		m_filepara->addExifInfo(buf);
	}
	else
		eDebug("[ePicLoad] decodeThumb: NO Exif info");

	if (!exif_thumbnail && m_conf.usecache)
	{
		if (FILE *f = fopen(m_filepara->file, "rb"))
		{
			int c;
			int count = 1024*100; // get checksum data out of max 100kB
			uint32_t crc32 = 0;
			char crcstr[9];
			*crcstr = 0;

			while (count-- > 0 && (c = getc(f)) != EOF)
				crc32 = crc32_table[((crc32) ^ (c)) & 0xFF] ^ ((crc32) >> 8);

			fclose(f);
			crc32 = ~crc32;
			sprintf(crcstr, "%08X", crc32);

			cachedir = m_filepara->file;
			size_t pos = cachedir.find_last_of("/");
			if (pos != std::string::npos)
				cachedir = cachedir.substr(0, pos) + "/.Thumbnails";

			cachefile = cachedir + std::string("/pc_") + crcstr;
			if (!access(cachefile.c_str(), R_OK))
			{
				cachefile_found = true;
				free(m_filepara->file);
				m_filepara->file = strdup(cachefile.c_str());
				m_filepara->id = F_JPEG;
				eDebug("[ePicLoad] Cache File %s found", cachefile.c_str());
			}
		}
	}

	switch (m_filepara->id)
	{
		case F_PNG:	png_load(m_filepara, m_conf.background, true);
				break;
		case F_JPEG:	m_filepara->pic_buffer = jpeg_load(m_filepara->file, &m_filepara->ox, &m_filepara->oy, m_filepara->max_x, m_filepara->max_y);
				break;
		case F_BMP:	m_filepara->pic_buffer = bmp_load(m_filepara->file, &m_filepara->ox, &m_filepara->oy);
				break;
		case F_GIF:	gif_load(m_filepara, true);
				break;
		case F_SVG:	svg_load(m_filepara, true);
				break;
	}
	//eDebug("[ePicLoad] getThumb picture loaded %s", m_filepara->file);

	if (exif_thumbnail)
		::unlink(THUMBNAILTMPFILE);

	if (m_filepara->pic_buffer != NULL)
	{
		// Save cachefile
		if (m_conf.usecache && !exif_thumbnail && !cachefile_found)
		{
			if (access(cachedir.c_str(), R_OK))
				::mkdir(cachedir.c_str(), 0755);

			// Resize for Thumbnail
			int imx, imy;
			if (m_filepara->ox <= m_filepara->oy)
			{
				imy = m_conf.thumbnailsize;
				imx = (int)( (m_conf.thumbnailsize * ((double)m_filepara->ox)) / ((double)m_filepara->oy) );
			}
			else
			{
				imx = m_conf.thumbnailsize;
				imy = (int)( (m_conf.thumbnailsize * ((double)m_filepara->oy)) / ((double)m_filepara->ox) );
			}

			// eDebug("[ePicLoad] getThumb resize from %dx%d to %dx%d", m_filepara->ox, m_filepara->oy, imx, imy);
			m_filepara->pic_buffer = color_resize(m_filepara->pic_buffer, m_filepara->ox, m_filepara->oy, imx, imy);
			m_filepara->ox = imx;
			m_filepara->oy = imy;

			if (jpeg_save(cachefile.c_str(), m_filepara->ox, m_filepara->oy, m_filepara->pic_buffer))
				eDebug("[ePicLoad] getThumb: error saving cachefile");
		}
	}
}

void ePicLoad::gotMessage(const Message &msg)
{
	switch (msg.type)
	{
		case Message::decode_Pic:
			decodePic();
			msg_main.send(Message(Message::decode_finished));
			break;
		case Message::decode_Thumb:
			decodeThumb();
			msg_main.send(Message(Message::decode_finished));
			break;
		case Message::quit: // called from decode thread
			eDebug("[ePicLoad] decode thread ... got quit msg");
			quit(0);
			break;
		case Message::decode_finished: // called from main thread
			//eDebug("[ePicLoad] decode finished... %s", m_filepara->file);
			if(m_filepara->callback)
				PictureData(m_filepara->picinfo.c_str());
			else
			{
				if(m_filepara != NULL)
				{
					delete m_filepara;
					m_filepara = NULL;
				}
				if (m_exif != NULL) {
					m_exif->ClearExif();
					delete m_exif;
					m_exif = NULL;
				}
			}
			break;
		default:
			eDebug("[ePicLoad] unhandled thread message");
	}
}

int ePicLoad::startThread(int what, const char *file, int x, int y, bool async)
{
	if(async && threadrunning && m_filepara != NULL)
	{
		eDebug("[ePicLoad] thread running");
		m_filepara->callback = false;
		return 1;
	}

	if(m_filepara != NULL)
	{
		delete m_filepara;
		m_filepara = NULL;
	}
	if (m_exif != NULL) {
		m_exif->ClearExif();
		delete m_exif;
		m_exif = NULL;
	}

	int file_id = getFileType(file);
	if(file_id < 0)
	{
		eDebug("[ePicLoad] <format not supported>");
		return 1;
	}

	m_filepara = new Cfilepara(file, file_id, getSize(file));
	m_filepara->max_x = x > 0 ? x : m_conf.max_x;
	m_filepara->max_y = x > 0 ? y : m_conf.max_y;

	if(m_filepara->max_x <= 0 || m_filepara->max_y <= 0)
	{
		delete m_filepara;
		m_filepara = NULL;
		eDebug("[ePicLoad] <error in Para>");
		return 1;
	}

	if (async) {
		if(what == 1)
			msg_thread.send(Message(Message::decode_Pic));
		else
			msg_thread.send(Message(Message::decode_Thumb));
		run();
	}
	else if (what == 1)
		decodePic();
	else
		decodeThumb();
	return 0;
}

RESULT ePicLoad::startDecode(const char *file, int x, int y, bool async)
{
	return startThread(1, file, x, y, async);
}

RESULT ePicLoad::getThumbnail(const char *file, int x, int y, bool async)
{
	return startThread(0, file, x, y, async);
}

PyObject *ePicLoad::getInfo(const char *filename)
{
	ePyObject list;

	// FIXME : m_filepara destroyed by getData. Need refactor this but plugins rely in it :(
	getExif(filename, m_filepara ? m_filepara->id : -1);
	if(m_exif && m_exif->m_exifinfo->IsExif)
	{
		char tmp[256];
		int pos = 0;
		list = PyList_New(23);
		PyList_SET_ITEM(list, pos++,  PyString_FromString(filename));
		PyList_SET_ITEM(list, pos++,  PyString_FromString(m_exif->m_exifinfo->Version));
		PyList_SET_ITEM(list, pos++,  PyString_FromString(m_exif->m_exifinfo->CameraMake));
		PyList_SET_ITEM(list, pos++,  PyString_FromString(m_exif->m_exifinfo->CameraModel));
		PyList_SET_ITEM(list, pos++,  PyString_FromString(m_exif->m_exifinfo->DateTime));
		PyList_SET_ITEM(list, pos++,  PyString_FromFormat("%d x %d", m_exif->m_exifinfo->Width, m_exif->m_exifinfo->Height));
		PyList_SET_ITEM(list, pos++,  PyString_FromString(m_exif->m_exifinfo->FlashUsed));
		PyList_SET_ITEM(list, pos++,  PyString_FromString(m_exif->m_exifinfo->Orientation));
		PyList_SET_ITEM(list, pos++,  PyString_FromString(m_exif->m_exifinfo->Comments));
		PyList_SET_ITEM(list, pos++,  PyString_FromString(m_exif->m_exifinfo->MeteringMode));
		PyList_SET_ITEM(list, pos++,  PyString_FromString(m_exif->m_exifinfo->ExposureProgram));
		PyList_SET_ITEM(list, pos++,  PyString_FromString(m_exif->m_exifinfo->LightSource));
		PyList_SET_ITEM(list, pos++,  PyString_FromFormat("%d", m_exif->m_exifinfo->CompressionLevel));
		PyList_SET_ITEM(list, pos++,  PyString_FromFormat("%d", m_exif->m_exifinfo->ISOequivalent));
		snprintf(tmp, sizeof(tmp) - 1, "%.2f", m_exif->m_exifinfo->Xresolution);
		PyList_SET_ITEM(list, pos++,  PyString_FromString(tmp));
		snprintf(tmp, sizeof(tmp) - 1, "%.2f", m_exif->m_exifinfo->Yresolution);
		PyList_SET_ITEM(list, pos++,  PyString_FromString(tmp));
		PyList_SET_ITEM(list, pos++,  PyString_FromString(m_exif->m_exifinfo->ResolutionUnit));
		snprintf(tmp, sizeof(tmp) - 1, "%.2f", m_exif->m_exifinfo->Brightness);
		PyList_SET_ITEM(list, pos++,  PyString_FromString(tmp));
		snprintf(tmp, sizeof(tmp) - 1, "%.5f sec.", m_exif->m_exifinfo->ExposureTime);
		PyList_SET_ITEM(list, pos++,  PyString_FromString(tmp));
		snprintf(tmp, sizeof(tmp) - 1, "%.5f", m_exif->m_exifinfo->ExposureBias);
		PyList_SET_ITEM(list, pos++,  PyString_FromString(tmp));
		snprintf(tmp, sizeof(tmp) - 1, "%.5f", m_exif->m_exifinfo->Distance);
		PyList_SET_ITEM(list, pos++,  PyString_FromString(tmp));
		snprintf(tmp, sizeof(tmp) - 1, "%.5f", m_exif->m_exifinfo->CCDWidth);
		PyList_SET_ITEM(list, pos++,  PyString_FromString(tmp));
		snprintf(tmp, sizeof(tmp) - 1, "%.2f", m_exif->m_exifinfo->ApertureFNumber);
		PyList_SET_ITEM(list, pos++,  PyString_FromString(tmp));
	}
	else
	{
		list = PyList_New(2);
		PyList_SET_ITEM(list, 0, PyString_FromString(filename));
		PyList_SET_ITEM(list, 1, PyString_FromString(m_exif->m_szLastError));
	}

	return list ? (PyObject*)list : (PyObject*)PyList_New(0);
}

bool ePicLoad::getExif(const char *filename, int fileType, int Thumb)
{
	if (!m_exif) {
		m_exif = new Cexif;
		if (fileType < 0)
			fileType = getFileType(filename);
		return m_exif->DecodeExif(filename, Thumb, fileType);
	}
	return true;
}

int ePicLoad::getData(ePtr<gPixmap> &result)
{
	result = 0;
	if (m_filepara == NULL)
	{
		eDebug("[ePicLoad] Weird situation, was not decoding anything!");
		return 1;
	}
	if(m_filepara->pic_buffer == NULL)
	{
		delete m_filepara;
		m_filepara = NULL;
		if (m_exif != NULL) {
			m_exif->ClearExif();
			delete m_exif;
			m_exif = NULL;
		}
		return 0;
	}

	result = new gPixmap(m_filepara->max_x, m_filepara->max_y, m_filepara->bits == 8 ? 8 : 32,
				NULL, m_filepara->bits == 8 ? gPixmap::accelAlways : gPixmap::accelAuto);
	gUnmanagedSurface *surface = result->surface;

	// original image    : ox, oy
	// surface size      : max_x, max_y
	// after aspect calc : scrx, scry
	// center image      : xoff, yoff
	int scrx, scry; // Aspect ratio calculation
	int orientation = m_conf.auto_orientation ? (m_exif && m_exif->m_exifinfo->Orient ? m_exif->m_exifinfo->Orient : 1) : 1;
	if ((m_conf.aspect_ratio > -0.1) && (m_conf.aspect_ratio < 0.1)) // do not keep aspect ratio but just fill the destination area
	{
		scrx = m_filepara->max_x;
		scry = m_filepara->max_y;
	}
	else if (orientation < 5) {
		if ((m_conf.aspect_ratio * m_filepara->oy * m_filepara->max_x / m_filepara->ox) <= m_filepara->max_y)
		{
			scrx = m_filepara->max_x;
			scry = (int)(m_conf.aspect_ratio * m_filepara->oy * m_filepara->max_x / m_filepara->ox);
		}
		else
		{
			scrx = (int)((1.0/m_conf.aspect_ratio) * m_filepara->ox * m_filepara->max_y / m_filepara->oy);
			scry = m_filepara->max_y;
		}
	}
	else {
		if ((m_conf.aspect_ratio * m_filepara->ox * m_filepara->max_x / m_filepara->oy) <= m_filepara->max_y)
		{
			scrx = m_filepara->max_x;
			scry = (int)(m_conf.aspect_ratio * m_filepara->ox * m_filepara->max_x / m_filepara->oy);
		}
		else
		{
			scrx = (int)((1.0/m_conf.aspect_ratio) * m_filepara->oy * m_filepara->max_y / m_filepara->ox);
			scry = m_filepara->max_y;
		}
	}
	float xscale = (float)(orientation < 5 ? m_filepara->ox : m_filepara->oy) / (float)scrx; // scale factor as result of screen and image size
	float yscale = (float)(orientation < 5 ? m_filepara->oy : m_filepara->ox) / (float)scry;
	int xoff = (m_filepara->max_x - scrx) / 2;  // borders as result of screen and image aspect
	int yoff = (m_filepara->max_y - scry) / 2;
	//eDebug("[getData] ox=%d oy=%d max_x=%d max_y=%d scrx=%d scry=%d xoff=%d yoff=%d xscale=%f yscale=%f aspect=%f bits=%d orientation=%d", m_filepara->ox, m_filepara->oy, m_filepara->max_x, m_filepara->max_y, scrx, scry, xoff, yoff, xscale, yscale, m_conf.aspect_ratio, m_filepara->bits, orientation);

	unsigned char *tmp_buffer = ((unsigned char *)(surface->data));
	unsigned char *origin = m_filepara->pic_buffer;
	if (m_filepara->bits == 8) {
		surface->clut.data = m_filepara->palette;
		surface->clut.colors = m_filepara->palette_size;
		m_filepara->palette = NULL; // transfer ownership
	}

	// fill borders with background color
	if (xoff != 0 || yoff != 0) {
		unsigned int background;
		if (m_filepara->bits == 8) {
			gRGB bg(m_conf.background);
			background = surface->clut.findColor(bg);
		}
		else {
			background = m_conf.background;
		}
		if (yoff != 0) {
			if (m_filepara->bits == 8)
			{
				unsigned char* row_buffer;
				row_buffer = (unsigned char *) tmp_buffer;
				for (int x = 0; x < m_filepara->max_x; ++x) // fill first line
					*row_buffer++ = background;
			}
			else
			{
				unsigned int* row_buffer;
				row_buffer = (unsigned int *) tmp_buffer;
				for (int x = 0; x < m_filepara->max_x; ++x) // fill first line
					*row_buffer++ = background;
			}
			int y;
			#pragma omp parallel for
			for (y = 1; y < yoff; ++y) // copy from first line
				memcpy(tmp_buffer + y*surface->stride, tmp_buffer,
					m_filepara->max_x * surface->bypp);
			#pragma omp parallel for
			for (y = yoff + scry; y < m_filepara->max_y; ++y)
				memcpy(tmp_buffer + y * surface->stride, tmp_buffer,
					m_filepara->max_x * surface->bypp);
		}
		if (xoff != 0) {
			if (m_filepara->bits == 8)
			{
				unsigned char* row_buffer = (unsigned char *) (tmp_buffer + yoff * surface->stride);
				int x;
				for (x = 0; x < xoff; ++x) // fill left side of first line
					*row_buffer++ = background;
				row_buffer += scrx;
				for (x = xoff + scrx; x < m_filepara->max_x; ++x) // fill right side of first line
					*row_buffer++ = background;
			}
			else {
				unsigned int* row_buffer = (unsigned int *) (tmp_buffer + yoff * surface->stride);
				int x;
				for (x = 0; x < xoff; ++x) // fill left side of first line
					*row_buffer++ = background;
				row_buffer += scrx;
				for (x = xoff + scrx; x < m_filepara->max_x; ++x) // fill right side of first line
					*row_buffer++ = background;
			}
			#pragma omp parallel for
			for (int y = yoff + 1; y < scry; ++y) { // copy from first line
				memcpy(tmp_buffer + y*surface->stride,
					tmp_buffer + yoff * surface->stride,
					xoff * surface->bypp);
				memcpy(tmp_buffer + y*surface->stride + (xoff + scrx) * surface->bypp,
					tmp_buffer + yoff * surface->stride + (xoff + scrx) * surface->bypp,
					(m_filepara->max_x - scrx - xoff) * surface->bypp);
			}
		}
		tmp_buffer += yoff * surface->stride + xoff * surface->bypp;
	}

	// Setup input image base pointers and x/y increment factors according to orientation
	//     1        2       3      4         5            6           7          8
	//
	//   888888  888888      88  88      8888888888  88                  88  8888888888
	//   88          88      88  88      88  88      88  88          88  88      88  88
	//   8888      8888    8888  8888    88          8888888888  8888888888          88
	//   88          88      88  88
	//   88          88  888888  888888
	//
	// ori  ori-1   yfax    xfac    origin
	// 0001 000      b * x   b      0
	// 0010 001      b * x  -b                                    b * (x - 1)
	// 0011 010     -b * x  -b      b * yscale * (sy - 1) * x  +  b * (x - 1)
	// 0100 011     -b * x   b      b * yscale * (sy - 1) * x
	// 0101 100      b       b * x  0
	// 0110 101      b      -b * x                              b * (y - 1) * x
	// 0111 110     -b      -b * x  b * yscale * (sy - 1)   +   b * (y - 1) * x
	// 1000 111     -b       b * x  b * yscale * (sy - 1)
	int bpp = m_filepara->bits / 8;
#if 0
	int iyfac = ((orientation-1) & 0x2) ? -bpp : bpp;
	int ixfac = (orientation & 0x2) ? -bpp : bpp;
	if (orientation < 5)
		iyfac *= m_filepara->ox;
	else
		ixfac *= m_filepara->ox;
	if (((orientation-1) & 0x6) == 2)
		origin += bpp * (int)(yscale * (scry - 1)) * m_filepara->ox;
	if (((orientation-1) & 0x6) == 6)
		origin += bpp * (int)(yscale * (scry - 1));
	if (((orientation) & 0x6) == 2)
		origin += bpp * (m_filepara->ox - 1);
	if (((orientation) & 0x6) == 6)
		origin += bpp * (m_filepara->oy - 1) * m_filepara->ox;
#else
	int ixfac;
	int iyfac;
	if (orientation < 5) {
		if (orientation == 1 || orientation == 2)
			iyfac = bpp * m_filepara->ox; // run y across rows
		else {
			origin += bpp * (int)(yscale * (scry - 1)) * m_filepara->ox;
			iyfac = -bpp * m_filepara->ox;
		}
		if (orientation == 2 || orientation == 3) {
			origin += bpp * (m_filepara->ox - 1);
			ixfac = -bpp;
		}
		else
			ixfac = bpp;
	}
	else {
		if (orientation == 5 || orientation == 6)
			iyfac = bpp;
		else {
			origin += bpp * (int)(yscale * (scry - 1));
			iyfac = -bpp ;
		}
		if (orientation == 6 || orientation == 7) {
			origin += bpp * (m_filepara->oy - 1) * m_filepara->ox;
			ixfac = -bpp * m_filepara->ox;
		}
		else
			ixfac = bpp * m_filepara->ox;
	}
#endif
	// Build output according to screen y by x loops
	// Fill surface with image data, resize and correct for orientation on the fly
	if (m_filepara->bits == 8)
	{
		#pragma omp parallel for
		for (int y = 0; y < scry; ++y) {
			const unsigned char *irow, *irowy = origin + iyfac * (int)(y * yscale);
			unsigned char *srow = tmp_buffer + surface->stride * y;
			float xind = 0.0;
			for (int x = 0; x < scrx; ++x) {
				irow = irowy + ixfac * (int)xind;
				*srow++ = *irow;
				xind += xscale;
			}
		}
	}
	else // 24-bit images
	{
		#pragma omp parallel for
		for (int y = 0; y < scry; ++y) {
			const unsigned char *irow, *irowy = origin + iyfac * (int)(yscale * y);
			unsigned char *srow = tmp_buffer + surface->stride * y;
			float xind = 0.0;

			if (m_conf.resizetype != 1) {
				// simple resizing
				for (int x = 0; x < scrx; ++x) {
					irow = irowy + ixfac * (int)xind;
					srow[2] = irow[0];
					srow[1] = irow[1];
					srow[0] = irow[2];
					srow[3] = 0xFF; // alpha
					srow += 4;
					xind += xscale;
				}
			}
			else {
				// color average resizing
				// determine block range for resize
				int yr = (int)((y+1) * yscale) - (int) (y * yscale);
				if (y + yr >= scry)
					yr = scry - y - 1;
				for (int x = 0; x < scrx; x++) {
					// determine x range for resize
					int xr = (int)(xind + xscale) - (int) xind;
					if (x + xr >= scrx)
						xr = scrx - x - 1;
					int r = 0;
					int g = 0;
					int b = 0;
					int sq = 0;
					irow = irowy + ixfac * (int)xind;
					// average over all pixels in x by y block
					for (int l = 0; l <= yr; l++) {
						for (int k = 0; k <= xr; k++) {
							r += irow[0];
							g += irow[1];
							b += irow[2];
							sq++;
							irow += ixfac;
						}
						irow -= (xr + 1) * ixfac; // go back to starting point of this subrow
						irow += iyfac;
					}
					srow[2] = r / sq;
					srow[1] = g / sq;
					srow[0] = b / sq;
					srow[3] = 0xFF; // alpha
					srow += 4;
					xind += xscale;
				}
			}
		}
	}

	delete m_filepara; // so caller can start a new decode in background
	m_filepara = NULL;
	if (m_exif) {
		m_exif->ClearExif();
		delete m_exif;
		m_exif = NULL;
	}

	return 0;
}

RESULT ePicLoad::setPara(PyObject *val)
{
	if (!PySequence_Check(val))
		return 0;
	if (PySequence_Size(val) < 7)
		return 0;
	else {
		ePyObject fast		= PySequence_Fast(val, "");
		int width		= PyInt_AsLong(PySequence_Fast_GET_ITEM(fast, 0));
		int height		= PyInt_AsLong(PySequence_Fast_GET_ITEM(fast, 1));
		double aspectRatio 	= PyInt_AsLong(PySequence_Fast_GET_ITEM(fast, 2));
		int as			= PyInt_AsLong(PySequence_Fast_GET_ITEM(fast, 3));
		bool useCache		= PyInt_AsLong(PySequence_Fast_GET_ITEM(fast, 4));
		int resizeType	        = PyInt_AsLong(PySequence_Fast_GET_ITEM(fast, 5));
		const char *bg_str	= PyString_AsString(PySequence_Fast_GET_ITEM(fast, 6));
		bool auto_orientation	= (PySequence_Size(val) > 7) ?
						PyInt_AsLong(PySequence_Fast_GET_ITEM(fast, 7)) :
						0;

		return setPara(width, height, aspectRatio, as, useCache, resizeType, bg_str, auto_orientation);
	}
	return 1;
}

RESULT ePicLoad::setPara(int width, int height, double aspectRatio, int as, bool useCache, int resizeType, const char *bg_str, bool auto_orientation)
{
	m_conf.max_x = width;
	m_conf.max_y = height;
	m_conf.aspect_ratio = as == 0 ? 0.0 : aspectRatio / as;
	m_conf.usecache	= useCache;
	m_conf.auto_orientation	= auto_orientation;
	m_conf.resizetype = resizeType;

	if(bg_str[0] == '#' && strlen(bg_str)==9)
		m_conf.background = strtoul(bg_str+1, NULL, 16) | 0xFF000000;
	eDebug("[ePicLoad] setPara max-X=%d max-Y=%d aspect_ratio=%lf cache=%d resize=%d bg=#%08X auto_orient=%d",
			m_conf.max_x, m_conf.max_y, m_conf.aspect_ratio,
			(int)m_conf.usecache, (int)m_conf.resizetype, m_conf.background, m_conf.auto_orientation);
	return 1;
}

int ePicLoad::getFileType(const char * file)
{
	unsigned char id[10];
	int fd = ::open(file, O_RDONLY);
	if (fd == -1)
		return -1;
	if (::read(fd, id, 10) != 10)
	{
		eDebug("[ePicLoad] getFileType failed to read magic num");
		close(fd);
		return -1;
	}
	::close(fd);

	if      (id[1] == 'P'  && id[2] == 'N'  && id[3] == 'G')			return F_PNG;
	else if (id[6] == 'J'  && id[7] == 'F'  && id[8] == 'I' && id[9] == 'F')	return F_JPEG;
	else if (id[0] == 0xff && id[1] == 0xd8 && id[2] == 0xff)			return F_JPEG;
	else if (id[0] == 'B'  && id[1] == 'M' )					return F_BMP;
	else if (id[0] == 'G'  && id[1] == 'I'  && id[2] == 'F')			return F_GIF;
	else if (id[0] == '<'  && id[1] == 's'  && id[2] == 'v' && id[3] == 'g')	return F_SVG;
	else if (endsWith(file, ".svg"))						return F_SVG;
	return -1;
}

//------------------------------------------------------------------------------------

//for old plugins
SWIG_VOID(int) loadPic(ePtr<gPixmap> &result, std::string filename, int x, int y, int aspect, int resize_mode, int rotate, int background, std::string cachefile)
{
	long asp1, asp2;
	result = 0;
	eDebug("[loadPic] deprecated loadPic function used!!! please use the non blocking version! you can see demo code in Pictureplayer plugin... this function is removed in the near future!");
	ePicLoad mPL;

	switch(aspect)
	{
		case 1:		asp1 = 16*576, asp2 = 9*720; break; //16:9
		case 2:		asp1 = 16*576, asp2 = 10*720; break; //16:10
		case 3:		asp1 = 5*576, asp2 = 4*720; break; //5:4
		default:	asp1 = 4*576, asp2 = 3*720; break; //4:3
	}

	ePyObject tuple = PyTuple_New(7);
	PyTuple_SET_ITEM(tuple, 0,  PyLong_FromLong(x));
	PyTuple_SET_ITEM(tuple, 1,  PyLong_FromLong(y));
	PyTuple_SET_ITEM(tuple, 2,  PyLong_FromLong(asp1));
	PyTuple_SET_ITEM(tuple, 3,  PyLong_FromLong(asp2));
	PyTuple_SET_ITEM(tuple, 4,  PyLong_FromLong(0));
	PyTuple_SET_ITEM(tuple, 5,  PyLong_FromLong(resize_mode));
	if(background)
		PyTuple_SET_ITEM(tuple, 6,  PyString_FromString("#ff000000"));
	else
		PyTuple_SET_ITEM(tuple, 6,  PyString_FromString("#00000000"));

	mPL.setPara(tuple);

	if(!mPL.startDecode(filename.c_str(), 0, 0, false))
		mPL.getData(result);

	return 0;
}
