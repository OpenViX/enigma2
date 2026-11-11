#include <lib/base/wrappers.h>
#include <lib/base/ebase.h>
#include <lib/service/listboxservicetpl.h>
#include <lib/service/service.h>
#include <lib/service/event.h>
#include <lib/gdi/font.h>
#include <lib/gdi/epng.h>
#include <lib/nav/core.h>
#include <lib/python/python.h>
#include <algorithm>
#include <lib/gdi/pixmapcache.h>
#include <chrono>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <deque>
#include <vector>
#include <set>
#include <utility>
#include <time.h>
#include <stdio.h>

DEFINE_REF(eListboxServiceTemplateContent);

static const char *const s_builtin_flags[] = {
	"playable", "marker", "directory", "group", "stream", "event", "nextevent", "crypted",
	"recorded", "fallback", "unavail", "catchup", "backup", "sd", "hd", "uhd", "hasnumber", "haspicon"
};

/* ---- helpers to read the python description (borrowed references only) ---- */

static PyObject *dictGet(PyObject *d, const char *key)
{
	return d && PyDict_Check(d) ? PyDict_GetItemString(d, key) : NULL;
}

static int pyInt(PyObject *d, const char *key, int def)
{
	PyObject *o = dictGet(d, key);
	if (o && PyLong_Check(o))
		return (int)PyLong_AsLong(o);
	return def;
}

static std::string pyStr(PyObject *d, const char *key)
{
	PyObject *o = dictGet(d, key);
	if (o && PyUnicode_Check(o))
	{
		const char *s = PyUnicode_AsUTF8(o);
		if (s)
			return s;
	}
	return "";
}

static std::string trim(const std::string &s)
{
	size_t b = s.find_first_not_of(" \t");
	if (b == std::string::npos)
		return "";
	size_t e = s.find_last_not_of(" \t");
	return s.substr(b, e - b + 1);
}

eListboxServiceTemplateContent::eListboxServiceTemplateContent()
	:m_cur_index(-1), m_span_width(0), m_flags(0), m_gen(1), m_rec_time(0), m_prefetch_last(-1), m_prefetch_dir(0)
{
	for (int i = 0; i < fontGroups; ++i)
		m_font_delta[i] = 0;
}

// defined in lib/gdi/epng.cpp
bool svgRasterizeToBuffer(const char *filename, int width, std::vector<unsigned char> &buf, int &w, int &h);
ePtr<gPixmap> svgBufferToCachedPixmap(const char *filename, const std::vector<unsigned char> &buf, int w, int h);

struct TplPrefetch: public sigc::trackable
{
	struct Job { eServiceReference ref; std::string file; int width; };
	struct Result { eServiceReference ref; std::string file; int w, h; bool ok; std::vector<unsigned char> buf; };

	eListboxServiceTemplateContent *owner;
	ePtr<eTimer> timer;
	// SVG picons are rasterised here, off the UI thread: one takes 5-25 ms and a few in a row delayed key repeats by ~90 ms.
	std::mutex mtx;
	std::condition_variable cv;
	std::deque<Job> jobs;
	std::deque<Result> results;
	std::set<eServiceReference> pending; // main thread only: queued or being rasterised
	bool stop;
	bool started;
	std::thread th;

	TplPrefetch(eListboxServiceTemplateContent *o): owner(o), stop(false), started(false)
	{
		timer = eTimer::create(eApp);
		CONNECT(timer->timeout, TplPrefetch::tick);
	}
	~TplPrefetch()
	{
		if (started)
		{
			{
				std::lock_guard<std::mutex> l(mtx);
				stop = true;
			}
			cv.notify_all();
			th.join();
		}
	}
	void tick() { owner->prefetchTick(); }

	void work()
	{
		for (;;)
		{
			Job j;
			{
				std::unique_lock<std::mutex> l(mtx);
				cv.wait(l, [this] { return stop || !jobs.empty(); });
				if (stop)
					return;
				j = jobs.front();
				jobs.pop_front();
			}
			Result r;
			r.ref = j.ref;
			r.file = j.file;
			r.w = r.h = 0;
			r.ok = svgRasterizeToBuffer(j.file.c_str(), j.width, r.buf, r.w, r.h);
			std::lock_guard<std::mutex> l(mtx);
			results.push_back(std::move(r));
		}
	}
	size_t queued()
	{
		std::lock_guard<std::mutex> l(mtx);
		return jobs.size();
	}
	void enqueue(const eServiceReference &ref, const std::string &file, int width)
	{
		if (!started)
		{
			started = true;
			th = std::thread(&TplPrefetch::work, this);
		}
		{
			std::lock_guard<std::mutex> l(mtx);
			Job j;
			j.ref = ref;
			j.file = file;
			j.width = width;
			jobs.push_back(j);
		}
		pending.insert(ref);
		cv.notify_one();
	}
	bool popResult(Result &r)
	{
		std::lock_guard<std::mutex> l(mtx);
		if (results.empty())
			return false;
		r = std::move(results.front());
		results.pop_front();
		return true;
	}
};

// Row picon, through m_picon_cache (the read-ahead fills it): without it every row rebuild decodes the PNG and re-uploads
// its texture, which made fast paging crawl.
void eListboxServiceTemplateContent::picon(const eServiceReference &ref, int width, ePtr<gPixmap> &pixmap, bool &isSVG)
{
	getPiconPixmap(ref, width, pixmap, isSVG);
}

void eListboxServiceTemplateContent::prefetchKick()
{
	if (m_cur_index < 0)
		return;
	if (m_cursor_number != m_prefetch_last)
	{
		if (m_prefetch_last >= 0)
			m_prefetch_dir = m_cursor_number > m_prefetch_last ? 1 : -1;
		m_prefetch_last = m_cursor_number;
	}
	if (!m_prefetch)
		m_prefetch = std::make_shared<TplPrefetch>(this);
	TplPrefetch *p = (TplPrefetch*)m_prefetch.get();
	if (!p->timer->isActive())
		p->timer->start(15, true);
}

void eListboxServiceTemplateContent::prefetchTick()
{
	if (!m_prefetch)
		return;
	TplPrefetch *pf = (TplPrefetch*)m_prefetch.get();
	const int H = m_itemheight;
	// Finished rasterisations: wrap them (cheap) and file them in m_picon_cache.
	{
		TplPrefetch::Result r;
		for (int drained = 0; drained < 4 && pf->popResult(r); ++drained)
		{
			if (m_picon_cache.find(r.ref) == m_picon_cache.end())
			{
				ePtr<gPixmap> keep; // PixmapCache only holds weakly, keep alive until the cache entry has taken it
				if (r.ok)
					keep = svgBufferToCachedPixmap(r.file.c_str(), r.buf, r.w, r.h);
				PiconCacheEntry entry;
				entry.isSVG = true;
				entry.pixmap = keep;
				m_picon_cache[r.ref] = entry;
			}
			pf->pending.erase(r.ref);
		}
	}
	if (m_cur_index < 0 || !cursorValid())
	{
		if (!pf->pending.empty())
			pf->timer->start(20, true);
		return;
	}
	const bool usePicon = m_templates[m_cur_index].usesPicon && PyCallable_Check(m_GetPiconNameFunc);
	// Before the cursor has ever moved (fresh start, skin change) the direction is unknown: warm both sides, so the
	// first pages scrolled are as warm as later ones (cold picon disk reads, EPG lookups and SVG rasterising were
	// the hiccups of the first scroll).
	const int ahead = std::max(3 * m_size_visible, 30);
	int loaded = 0;
	const auto t0 = std::chrono::steady_clock::now();
	bool more = false;
	const int ndirs = m_prefetch_dir ? 1 : 2;
	for (int d = 0; d < ndirs && !more; ++d)
	{
		const int dir = m_prefetch_dir ? m_prefetch_dir : (d == 0 ? 1 : -1);
		list::iterator it = m_cursor;
		for (int n = 0; n < ahead; ++n)
		{
			if (dir > 0)
			{
				if (it == m_list.end() || ++it == m_list.end())
					break;
			}
			else
			{
				if (it == m_list.begin())
					break;
				--it;
			}
			const eServiceReference &ref = *it;
			if (ref.flags & (eServiceReference::isMarker | eServiceReference::isDirectory))
				continue;
			// EPG lookup of the row, so building it later is a cache hit (time-boxed, UI thread)
			std::map<eServiceReference, EventCacheEntry>::iterator ev = m_event_cache.find(ref);
			if (ev == m_event_cache.end() || time(0) >= ev->second.validUntil)
			{
				if (loaded > 0 && std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count() > 4.0)
				{
					more = true;
					break;
				}
				ePtr<iStaticServiceInformation> info;
				m_service_center->info(ref, info);
				ePtr<eServiceEvent> e1, e2;
				getCachedEvent(ref, info, time(0), e1, e2); // caches "no event" too, so it is not retried every tick
				++loaded;
			}
			if (!usePicon || m_picon_cache.find(ref) != m_picon_cache.end() || pf->pending.count(ref))
				continue;
			const std::string file = getPiconFilename(ref);
			if (file.size() <= 4 || file.compare(file.size() - 4, 4, ".svg") != 0)
			{
				// PNG etc.: cheap, decode a few per tick on the UI thread
				if (loaded >= 3 || (loaded > 0 && std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count() > 4.0))
				{
					more = true;
					break;
				}
				ePtr<gPixmap> pix;
				bool svg = false;
				getPiconPixmap(ref, H * 5 / 3, pix, svg);
				++loaded;
				continue;
			}
			char cachefile[file.size() + 10];
			sprintf(cachefile, "%s%d", file.c_str(), 0);
			if (PixmapCache::Get(file.c_str(), cachefile))
				continue; // already loaded, a row load will pick it up
			if (pf->queued() >= 16)
			{
				more = true;
				break;
			}
			pf->enqueue(ref, file, H * 5 / 3);
		}
	}
	// Bound the cache (CPU pixmaps and, through them, GPU textures): keep only rows near the cursor, trimmed a few per
	// tick since dropping ~100 pixmaps at once queues ~100 GL texture deletions that stall a frame.
	if (m_picon_cache.size() > 400)
	{
		std::set<eServiceReference> window;
		list::iterator a = m_cursor, b = m_cursor;
		for (int n = 0; n < 120; ++n)
		{
			if (a != m_list.begin()) --a;
			if (b != m_list.end()) ++b;
		}
		for (list::iterator k = a; k != b && k != m_list.end(); ++k)
			window.insert(*k);
		int dropped = 0;
		for (std::map<eServiceReference, PiconCacheEntry>::iterator f = m_picon_cache.begin();
			f != m_picon_cache.end() && dropped < 6; )
		{
			if (window.find(f->first) == window.end())
			{
				m_picon_cache.erase(f++);
				++dropped;
			}
			else
				++f;
		}
		if (dropped >= 6)
			more = true;
	}
	if (more || !pf->pending.empty())
		pf->timer->start(more ? 25 : 20, true);
}

/* ---------------------------------- compiling ---------------------------------- */

void eListboxServiceTemplateContent::clearTemplates()
{
	m_templates.clear();
	m_styles.clear();
	m_cur_index = -1;
	m_current.clear();
	m_rows.clear();
	++m_gen;
}

int eListboxServiceTemplateContent::styleIndex(const std::string &name)
{
	if (name.empty())
		return -1;
	for (size_t i = 0; i < m_styles.size(); ++i)
		if (m_styles[i].name == name)
			return (int)i;
	eDebug("[eListboxServiceTemplateContent] unknown style '%s'", name.c_str());
	return -1;
}

int eListboxServiceTemplateContent::setStyle(ePyObject dict)
{
	PyObject *d = dict;
	if (!d || !PyDict_Check(d))
		return -1;
	static const char *const keys[cCount] = {
		"fg", "fgSelected", "fgFallback", "fgSelectedFallback", "fgNotAvail",
		"fgRecorded", "fgMarked", "fgMarkedSelected", "border", "borderSelected"
	};
	Style st;
	st.name = pyStr(d, "name");
	for (int i = 0; i < cCount; ++i)
	{
		PyObject *o = dictGet(d, keys[i]);
		st.set[i] = o && PyLong_Check(o);
		st.c[i] = gRGB(st.set[i] ? (unsigned int)PyLong_AsUnsignedLongMask(o) : 0);
	}
	++m_gen;
	for (size_t i = 0; i < m_styles.size(); ++i)
	{
		if (m_styles[i].name == st.name)
		{
			m_styles[i] = st;
			return (int)i;
		}
	}
	m_styles.push_back(st);
	return (int)m_styles.size() - 1;
}

bool eListboxServiceTemplateContent::parseCondition(const std::string &cond, uint64_t &req, uint64_t &forbid)
{
	req = forbid = 0;
	size_t pos = 0;
	bool ok = true;
	while (pos <= cond.size())
	{
		size_t comma = cond.find(',', pos);
		std::string tok = trim(cond.substr(pos, comma == std::string::npos ? std::string::npos : comma - pos));
		pos = comma == std::string::npos ? cond.size() + 1 : comma + 1;
		if (tok.empty())
			continue;
		bool neg = false;
		if (tok[0] == '!')
		{
			neg = true;
			tok = trim(tok.substr(1));
		}
		int bit = -1;
		for (int i = 0; i < sBuiltin; ++i)
			if (tok == s_builtin_flags[i])
				bit = i;
		if (bit < 0 && tok.compare(0, 4, "cfg.") == 0)
		{
			std::map<std::string, int>::iterator it = m_flag_bits.find(tok);
			if (it == m_flag_bits.end())
			{
				if (m_flag_bits.size() >= 32)
				{
					eDebug("[eListboxServiceTemplateContent] too many cfg flags, ignoring '%s'", tok.c_str());
					ok = false;
					continue;
				}
				it = m_flag_bits.insert(std::make_pair(tok, sCfgBase + (int)m_flag_bits.size())).first;
			}
			bit = it->second;
		}
		if (bit < 0)
		{
			eDebug("[eListboxServiceTemplateContent] unknown condition '%s'", tok.c_str());
			ok = false;
			continue;
		}
		if (neg)
			forbid |= (uint64_t)1 << bit;
		else
			req |= (uint64_t)1 << bit;
	}
	return ok;
}

void eListboxServiceTemplateContent::parseTokens(const std::string &text, std::vector<Token> &out)
{
	static const struct { const char *name; int kind; } names[] = {
		{"number", tokNumber}, {"name", tokName}, {"event", tokEvent}, {"next", tokNext},
		{"remaining", tokRemaining}, {"percent", tokPercent}, {"start", tokStart},
		{"end", tokEnd}, {"duration", tokDuration}
	};
	std::string lit;
	size_t i = 0;
	while (i < text.size())
	{
		if (text[i] == '{')
		{
			size_t close = text.find('}', i);
			if (close != std::string::npos)
			{
				std::string n = text.substr(i + 1, close - i - 1);
				std::string suffix;
				size_t bar = n.find('|');
				if (bar != std::string::npos)
				{
					suffix = n.substr(bar + 1);
					n = n.substr(0, bar);
				}
				int kind = -1;
				for (size_t k = 0; k < sizeof(names) / sizeof(names[0]); ++k)
					if (n == names[k].name)
						kind = names[k].kind;
				if (kind >= 0)
				{
					if (!lit.empty())
					{
						Token t;
						t.kind = tokLiteral;
						t.lit = lit;
						out.push_back(t);
						lit.clear();
					}
					Token t;
					t.kind = kind;
					t.lit = suffix;
					out.push_back(t);
					i = close + 1;
					continue;
				}
			}
		}
		lit += text[i++];
	}
	if (!lit.empty())
	{
		Token t;
		t.kind = tokLiteral;
		t.lit = lit;
		out.push_back(t);
	}
}

int eListboxServiceTemplateContent::addTemplate(ePyObject dict)
{
	PyObject *d = dict;
	if (!d || !PyDict_Check(d))
		return -1;
	static const struct { const char *name; int type; } types[] = {
		{"text", itText}, {"number", itText}, {"picon", itPicon}, {"servicetype", itServiceType},
		{"crypto", itCrypto}, {"record", itRecord}, {"resolution", itResolution}, {"backup", itBackup},
		{"catchup", itCatchup}, {"kind", itKind}, {"progress", itProgress}, {"line", itLine}, {"rect", itRect}, {"spacer", itSpacer}, {"pixmap", itPixmap}
	};

	Template t;
	t.name = pyStr(d, "name");
	t.itemHeight = pyInt(d, "itemHeight", 0); // 0: the itemHeight of the widget
	t.large = pyInt(d, "large", 0) != 0;
	std::string layout = pyStr(d, "layout");
	t.orientation = layout == "grid" ? (int)eListbox::orGrid : layout == "horizontal" ? (int)eListbox::orHorizontal : (int)eListbox::orVertical;
	t.itemWidth = pyInt(d, "itemWidth", 0);
	t.spacingX = pyInt(d, "spacingX", -1);
	t.spacingY = pyInt(d, "spacingY", -1);
	t.selectionZoom = pyInt(d, "selectionZoom", -2);
	t.carousel = pyInt(d, "carousel", -2);
	t.carouselZoom = pyInt(d, "carouselZoom", -2);
	t.carouselFocus = pyInt(d, "carouselFocus", -2);
	t.carouselCenterWidth = pyInt(d, "carouselCenterWidth", -2);
	t.carouselCenterHeight = pyInt(d, "carouselCenterHeight", -2);
	t.usesNext = t.timeDependent = t.usesPicon = false;
	{
		const std::string spanMarkers = pyStr(d, "spanMarkers");
		t.spanMarkers = spanMarkers == "1" || spanMarkers == "true" || spanMarkers == "yes";
		t.markerHeight = pyInt(d, "markerHeight", 0);
	}
	t.usedBits = 0;

	PyObject *rows = dictGet(d, "rows");
	if (rows && PyList_Check(rows))
	{
		for (Py_ssize_t r = 0; r < PyList_Size(rows); ++r)
		{
			PyObject *rd = PyList_GetItem(rows, r);
			Row row;
			std::string kind = pyStr(rd, "for");
			row.kind = kind == "marker" ? rowMarker : kind == "directory" ? rowDirectory : rowService;
			row.height = pyInt(rd, "height", 0);
			row.weight = std::max(1, pyInt(rd, "weight", 1));
			row.gap = pyInt(rd, "gap", 0);
			row.padLeft = pyInt(rd, "padLeft", 0);
			row.padRight = pyInt(rd, "padRight", 0);
			row.padTop = pyInt(rd, "padTop", 0);
			row.padBottom = pyInt(rd, "padBottom", 0);
			std::string rowAlign = pyStr(rd, "align");
			row.align = rowAlign == "center" ? 1 : rowAlign == "right" ? 2 : 0;
			parseCondition(pyStr(rd, "visible"), row.req, row.forbid);
			t.usedBits |= row.req | row.forbid;
			PyObject *stacks = dictGet(rd, "stacks");
			for (Py_ssize_t i = 0; stacks && PyList_Check(stacks) && i < PyList_Size(stacks); ++i)
			{
				PyObject *sd = PyList_GetItem(stacks, i);
				Stack st;
				st.horizontal = pyStr(sd, "layout") != "vertical";
				st.spacing = pyInt(sd, "spacing", 0);
				st.absolute = false;
				PyObject *spos = dictGet(sd, "pos");
				if (spos && PyList_Check(spos) && PyList_Size(spos) == 4)
				{
					int v[4];
					for (int k = 0; k < 4; ++k)
						v[k] = (int)PyLong_AsLong(PyList_GetItem(spos, k));
					st.absolute = true;
					st.rect = eRect(v[0], v[1], v[2], v[3]);
				}
				parseCondition(pyStr(sd, "visible"), st.req, st.forbid);
				t.usedBits |= st.req | st.forbid;
				row.stacks.push_back(st);
			}
			PyObject *items = dictGet(rd, "items");
			for (Py_ssize_t i = 0; items && PyList_Check(items) && i < PyList_Size(items); ++i)
			{
				PyObject *id = PyList_GetItem(items, i);
				Item it;
				std::string type = pyStr(id, "type");
				it.type = -1;
				for (size_t k = 0; k < sizeof(types) / sizeof(types[0]); ++k)
					if (type == types[k].name)
						it.type = types[k].type;
				if (it.type < 0)
				{
					eDebug("[eListboxServiceTemplateContent] template '%s': unknown item type '%s'", t.name.c_str(), type.c_str());
					continue;
				}
				parseCondition(pyStr(id, "visible"), it.req, it.forbid);
				t.usedBits |= it.req | it.forbid;
				it.wmode = pyInt(id, "wmode", wAuto);
				it.param = pyStr(id, "param");
				it.width = pyInt(id, "width", 0);
				it.weight = std::max(1, pyInt(id, "weight", 1));
				it.minw = pyInt(id, "min", 0);
				it.height = pyInt(id, "height", 0);
				it.margin = pyInt(id, "margin", 0);
				it.lineH = pyInt(id, "lineHeight", 0);
				std::string align = pyStr(id, "align");
				it.align = align == "center" ? 1 : align == "right" ? 2 : align == "left" ? 0 : -1;
				std::string valign = pyStr(id, "valign");
				it.valign = valign == "top" ? 0 : valign == "bottom" ? 2 : 1;
				it.absolute = false;
				PyObject *pos = dictGet(id, "pos");
				if (pos && PyList_Check(pos) && PyList_Size(pos) == 4)
				{
					int v[4];
					for (int k = 0; k < 4; ++k)
						v[k] = (int)PyLong_AsLong(PyList_GetItem(pos, k));
					it.absolute = true;
					it.absRect = eRect(v[0], v[1], v[2], v[3]);
				}
				parseTokens(pyStr(id, "text"), it.tokens);
				for (size_t k = 0; k < it.tokens.size(); ++k)
				{
					int tk = it.tokens[k].kind;
					if (tk == tokNext)
						t.usesNext = true;
					if (tk == tokRemaining || tk == tokPercent)
						t.timeDependent = true;
				}
				if (it.type == itProgress)
					t.timeDependent = true;
				if (it.type == itPicon)
					t.usesPicon = true;
				it.family = pyStr(id, "font");
				it.fontSize = pyInt(id, "fontSize", 20);
				it.fontGroup = std::min(std::max(pyInt(id, "fontGroup", 0), 0), (int)fontGroups - 1);
				it.style = styleIndex(pyStr(id, "style"));
				it.ellipsis = pyInt(id, "ellipsis", 1) != 0;
				it.reserve = pyInt(id, "reserve", 0) != 0;
				it.keepAspect = pyInt(id, "keepAspect", 1) != 0;
				it.border = pyInt(id, "border", -1);
				static const char *const colKeys[4] = { "color", "colorSelected", "borderColor", "borderColorSelected" };
				for (int k = 0; k < 4; ++k)
				{
					PyObject *o = dictGet(id, colKeys[k]);
					const bool set = o && PyLong_Check(o);
					const gRGB c(set ? (unsigned int)PyLong_AsUnsignedLongMask(o) : 0);
					if (k < 2)
					{
						it.colSet[k] = set;
						it.col[k] = c;
					}
					else
					{
						it.bcolSet[k - 2] = set;
						it.bcol[k - 2] = c;
					}
				}
				it.radius = pyInt(id, "radius", 0);
				it.edges = pyInt(id, "edges", 15);
				it.z = pyInt(id, "z", 0);
				it.src = pyStr(id, "src");
				it.srcSel = pyStr(id, "srcSelected");
				it.isSvg = false;
				it.stackId = pyInt(id, "stack", -1);
				if (it.stackId >= (int)row.stacks.size())
					it.stackId = -1;
				std::string stackAlign = pyStr(id, "stackAlign");
				it.stackAlign = (stackAlign == "right" || stackAlign == "bottom") ? 1 : stackAlign == "center" ? 2 : 0;
				std::string stackCross = pyStr(id, "stackCross");
				it.stackCross = (stackCross == "top" || stackCross == "left") ? 0 : stackCross == "center" ? 1 : (stackCross == "bottom" || stackCross == "right") ? 2 : -1;
				it.stackFill = pyInt(id, "stackFill", 0) != 0;
				if (it.stackId >= 0)
					it.absolute = false; // a stack member is placed by its stack
				row.items.push_back(it);
			}
			t.rows.push_back(row);
		}
	}

	for (size_t i = 0; i < m_templates.size(); ++i)
	{
		if (m_templates[i].name == t.name)
		{
			m_templates[i] = t;
			if ((int)i == m_cur_index)
				setTemplate(t.name);
			return (int)i;
		}
	}
	m_templates.push_back(t);
	return (int)m_templates.size() - 1;
}

void eListboxServiceTemplateContent::rebuildFonts()
{
	for (size_t t = 0; t < m_templates.size(); ++t)
		for (size_t r = 0; r < m_templates[t].rows.size(); ++r)
			for (size_t i = 0; i < m_templates[t].rows[r].items.size(); ++i)
			{
				Item &it = m_templates[t].rows[r].items[i];
				it.font = new gFont(it.family.empty() ? "Regular" : it.family, std::max(1, it.fontSize + m_font_delta[it.fontGroup]));
			}
}

// static images of the template's pixmap items, loaded when the template becomes current
void eListboxServiceTemplateContent::loadPixmaps(Template &t)
{
	for (size_t r = 0; r < t.rows.size(); ++r)
		for (size_t i = 0; i < t.rows[r].items.size(); ++i)
		{
			Item &it = t.rows[r].items[i];
			if (it.type != itPixmap)
				continue;
			// svg files are rendered at the size the item asks for
			const int w = it.wmode == wFixed ? it.width : 0;
			const int h = it.height;
			it.isSvg = it.src.size() > 4 && it.src.compare(it.src.size() - 4, 4, ".svg") == 0;
			const std::string *files[2] = { &it.src, &it.srcSel };
			Ref<gPixmap> *dest[2] = { &it.pix, &it.pixSel };
			for (int k = 0; k < 2; ++k)
			{
				if (files[k]->empty() || (gPixmap*)*dest[k])
					continue;
				ePtr<gPixmap> pm;
				if (loadImage(pm, files[k]->c_str(), 0, w, h) == 0 && pm)
					*dest[k] = (gPixmap*)pm;
				else
					eDebug("[eListboxServiceTemplateContent] cannot load '%s'", files[k]->c_str());
			}
		}
}

bool eListboxServiceTemplateContent::setTemplate(const std::string &name)
{
	for (size_t i = 0; i < m_templates.size(); ++i)
	{
		if (m_templates[i].name == name)
		{
			m_cur_index = (int)i;
			m_current = name;
			m_has_next_event = m_templates[i].usesNext;
			// list, horizontal list or grid: the listbox needs the geometry of the cell
			if (m_listbox)
			{
				m_listbox->setOrientation(getOrientation());
				if (getItemWidth() > 0) // not set in the template: the itemWidth of the widget stays
					m_listbox->setItemWidth(getItemWidth());
				m_listbox->applyContentSpacing();
			}
			m_event_cache.clear();
			m_rows.clear();
			rebuildFonts();
			loadPixmaps(m_templates[i]);
			++m_gen;
			if (m_listbox)
				m_listbox->invalidate();
			return true;
		}
	}
	return false;
}

int eListboxServiceTemplateContent::getTemplateItemHeight(const std::string &name)
{
	for (size_t i = 0; i < m_templates.size(); ++i)
		if (m_templates[i].name == name)
			return m_templates[i].itemHeight;
	return 0;
}

int eListboxServiceTemplateContent::getTemplateOrientation(const std::string &name)
{
	for (size_t i = 0; i < m_templates.size(); ++i)
		if (m_templates[i].name == name)
			return m_templates[i].orientation;
	return eListbox::orVertical;
}

int eListboxServiceTemplateContent::getTemplateItemWidth(const std::string &name)
{
	for (size_t i = 0; i < m_templates.size(); ++i)
		if (m_templates[i].name == name)
			return m_templates[i].itemWidth;
	return 0;
}

int eListboxServiceTemplateContent::getTemplateRows(const std::string &name)
{
	for (size_t i = 0; i < m_templates.size(); ++i)
	{
		if (m_templates[i].name == name)
		{
			int n = 0;
			for (size_t r = 0; r < m_templates[i].rows.size(); ++r)
				if (m_templates[i].rows[r].kind == rowService)
					++n;
			return n;
		}
	}
	return 0;
}

void eListboxServiceTemplateContent::setFlag(const std::string &name, bool on)
{
	std::string key = name;
	std::map<std::string, int>::iterator it = m_flag_bits.find(key);
	if (it == m_flag_bits.end())
	{
		if (m_flag_bits.size() >= 32)
			return;
		it = m_flag_bits.insert(std::make_pair(key, sCfgBase + (int)m_flag_bits.size())).first;
	}
	uint64_t bit = (uint64_t)1 << it->second;
	uint64_t nf = on ? (m_flags | bit) : (m_flags & ~bit);
	if (nf != m_flags)
	{
		m_flags = nf;
		++m_gen;
	}
}

void eListboxServiceTemplateContent::setParam(const std::string &name, int value)
{
	std::map<std::string, int>::iterator it = m_params.find(name);
	if (it == m_params.end() || it->second != value)
	{
		m_params[name] = value;
		++m_gen;
	}
}

void eListboxServiceTemplateContent::setFontDelta(int group, int delta)
{
	if (group < 0 || group >= fontGroups || m_font_delta[group] == delta)
		return;
	m_font_delta[group] = delta;
	rebuildFonts();
	++m_gen;
}

void eListboxServiceTemplateContent::invalidateRows()
{
	m_rows.clear();
	++m_gen;
	if (m_listbox)
		m_listbox->invalidate();
}

void eListboxServiceTemplateContent::setSize(const eSize &size)
{
	// eListbox::updateScrollBar() calls this on every selection move with an unchanged size,
	// only a real change may throw the cached rows away
	// (a zoomed paint temporarily enlarges the cell: that has its own row cache, see prepareZoomTemplate())
	eSize cell = size;
	// A horizontal list gives its cell the height of the whole widget. The tile of a template is as high as its
	// itemHeight, so that is the cell (background, selection, zoom): a cell as high as the widget leaves the zoom no
	// room to grow and paints the rounded background taller than the tile.
	if (m_zoom == 100 && !m_cell_override && m_cur_index >= 0 && m_templates[m_cur_index].orientation == (int)eListbox::orHorizontal &&
		m_itemheight > 0 && cell.height() > m_itemheight)
		cell = eSize(cell.width(), m_itemheight);
	const bool changed = !(m_itemsize == cell);
	eListboxServiceContent::setSize(cell);
	if (changed && m_zoom == 100 && !m_cell_override)
		++m_gen;
}

static inline int zoomScale(int v, int pct)
{
	return pct == 100 ? v : (v * pct + (v < 0 ? -50 : 50)) / 100;
}

void eListboxServiceTemplateContent::prepareZoomTemplate()
{
	if (m_zoom_tpl_idx == m_cur_index && m_zoom_tpl_zoom == m_zoom && m_zoom_tpl_gen == m_gen)
		return;
	m_zoom_tpl = m_templates[m_cur_index];
	const int z = m_zoom;
	Template &t = m_zoom_tpl;
	t.itemHeight = zoomScale(t.itemHeight, z);
	t.itemWidth = zoomScale(t.itemWidth, z);
	t.markerHeight = zoomScale(t.markerHeight, z);
	for (size_t r = 0; r < t.rows.size(); ++r)
	{
		Row &row = t.rows[r];
		row.height = zoomScale(row.height, z);
		row.gap = zoomScale(row.gap, z);
		row.padLeft = zoomScale(row.padLeft, z);
		row.padRight = zoomScale(row.padRight, z);
		row.padTop = zoomScale(row.padTop, z);
		row.padBottom = zoomScale(row.padBottom, z);
		for (size_t s = 0; s < row.stacks.size(); ++s)
		{
			Stack &st = row.stacks[s];
			st.spacing = zoomScale(st.spacing, z);
			if (st.absolute)
				st.rect = eRect(zoomScale(st.rect.x(), z), zoomScale(st.rect.y(), z), zoomScale(st.rect.width(), z), zoomScale(st.rect.height(), z));
		}
		for (size_t i = 0; i < row.items.size(); ++i)
		{
			Item &it = row.items[i];
			if (it.wmode == wFixed)
				it.width = zoomScale(it.width, z);
			it.minw = zoomScale(it.minw, z);
			it.height = zoomScale(it.height, z);
			it.margin = zoomScale(it.margin, z);
			it.lineH = zoomScale(it.lineH, z);
			if (it.absolute)
				it.absRect = eRect(zoomScale(it.absRect.x(), z), zoomScale(it.absRect.y(), z), zoomScale(it.absRect.width(), z), zoomScale(it.absRect.height(), z));
			if (it.border > 0)
				it.border = std::max(1, zoomScale(it.border, z));
			it.radius = zoomScale(it.radius, z);
			it.font = new gFont(it.family.empty() ? "Regular" : it.family, std::max(1, zoomScale(it.fontSize + m_font_delta[it.fontGroup], z)));
		}
	}
	m_zoom_rows.clear();
	m_zoom_tpl_idx = m_cur_index;
	m_zoom_tpl_zoom = m_zoom;
	m_zoom_tpl_gen = m_gen;
}

/* ---------------------------------- row building ---------------------------------- */

bool eListboxServiceTemplateContent::isRecordedCached(const eServiceReference &ref, time_t now)
{
	if (ref.flags & eServiceReference::isGroup)
		return checkServiceIsRecorded(ref);
	if (now != m_rec_time)
	{
		m_rec_refs.clear();
		eNavigation *nav = eNavigation::getInstance();
		if (nav)
		{
			std::map<ePtr<iRecordableService>, eServiceReference, std::less<iRecordableService*> > rec = nav->getRecordingsServices();
			for (std::map<ePtr<iRecordableService>, eServiceReference, std::less<iRecordableService*> >::iterator it = rec.begin(); it != rec.end(); ++it)
				m_rec_refs.insert(it->second);
		}
		m_rec_time = now;
	}
	return m_rec_refs.count(ref) != 0;
}

std::string eListboxServiceTemplateContent::tokenText(int kind, const eServiceReference &ref, const std::string &name, eServiceEvent *evt, eServiceEvent *next, time_t now)
{
	char buf[32];
	switch (kind)
	{
	case tokNumber:
		if (m_chanel_number_visible && ref.getChannelNum() > 0)
		{
			snprintf(buf, sizeof(buf), "%d", ref.getChannelNum());
			return buf;
		}
		return "";
	case tokName:
		return name;
	case tokEvent:
	case tokNext:
	{
		eServiceEvent *e = kind == tokEvent ? evt : next;
		if (!e)
			return "";
		std::string s = e->getEventName();
		std::replace(s.begin(), s.end(), '\n', ' ');
		return s;
	}
	case tokRemaining:
	{
		if (!evt || evt->getDuration() <= 0)
			return "";
		long left = (long)(evt->getBeginTime() + evt->getDuration() - now);
		std::string fmt = "%s" + (m_text_time.empty() ? std::string("%d min") : m_text_time);
		snprintf(buf, sizeof(buf), fmt.c_str(), left == 0 ? "" : "+", (int)(left / 60));
		return buf;
	}
	case tokDuration:
	{
		if (!evt || evt->getDuration() <= 0)
			return "";
		std::string fmt = m_text_time.empty() ? std::string("%d min") : m_text_time;
		snprintf(buf, sizeof(buf), fmt.c_str(), (int)(evt->getDuration() / 60));
		return buf;
	}
	case tokPercent:
	{
		if (!evt || evt->getDuration() <= 0)
			return "";
		int p = (int)(100 * (now - evt->getBeginTime()) / evt->getDuration());
		snprintf(buf, sizeof(buf), "%d %%", std::min(std::max(p, 0), 100));
		return buf;
	}
	case tokStart:
	case tokEnd:
	{
		if (!evt)
			return "";
		time_t t = kind == tokStart ? evt->getBeginTime() : evt->getBeginTime() + evt->getDuration();
		struct tm tmv;
		localtime_r(&t, &tmv);
		strftime(buf, sizeof(buf), "%H:%M", &tmv);
		return buf;
	}
	}
	return "";
}

void eListboxServiceTemplateContent::buildRow(const Template &tpl, const eServiceReference &ref, iStaticServiceInformation *info, int dyn, time_t now, RowCache &out)
{
	out.ops.clear();
	out.ops.reserve(24);
	out.dynState = dyn;
	const int W = m_itemsize.width();
	const int H = m_itemheight;
	const int ellipsisFlag = ellipsisEnabled() ? gPainter::RT_ELLIPSIS : 0;

	const bool isMarker = ref.flags & eServiceReference::isMarker;
	const bool isDir = ref.flags & eServiceReference::isDirectory;
	const bool playable = !(isMarker || isDir);

	std::string name = "<N/A>";
	if (info)
		info->getName(ref, name);

	ePtr<eServiceEvent> evt, evt_next;
	bool hasEvent = playable && info && getCachedEvent(ref, info, now, evt, evt_next);
	if (hasEvent && evt->getEventName().empty())
		hasEvent = false;
	bool hasNext = hasEvent && evt_next && !evt_next->getEventName().empty();

	out.validUntil = now + 60;
	if (hasEvent && evt->getBeginTime() > 0 && evt->getDuration() > 0)
	{
		time_t end = evt->getBeginTime() + evt->getDuration();
		if (end > now)
			out.validUntil = end;
		if (tpl.timeDependent)
			out.validUntil = std::min(out.validUntil, now + 30);
	}

	const uint64_t refBits = ((uint64_t)1 << sCatchup) | ((uint64_t)1 << sBackup);
	std::string refStr;
	if (tpl.usedBits & refBits)
		refStr = ref.toString();
	uint64_t st = 0;
	#define SETBIT(b, cond) do { if (cond) st |= (uint64_t)1 << (b); } while (0)
	SETBIT(sPlayable, playable);
	SETBIT(sMarker, isMarker);
	SETBIT(sDirectory, isDir);
	SETBIT(sGroup, ref.flags & eServiceReference::isGroup);
	SETBIT(sStream, ref.path.find("://") != std::string::npos);
	SETBIT(sEvent, hasEvent);
	SETBIT(sNextEvent, hasNext);
	SETBIT(sCrypted, playable && (tpl.usedBits & ((uint64_t)1 << sCrypted)) && info && info->isCrypted());
	SETBIT(sRecorded, dyn & dynRecorded);
	SETBIT(sFallback, dyn & dynFallback);
	SETBIT(sUnavail, dyn & dynUnavail);
	SETBIT(sCatchup, playable && refStr.find("catchupdays=") != std::string::npos);
	SETBIT(sBackup, playable && refStr.find("&backupref=") != std::string::npos);
	const int stype = ref.data[0];
	const bool uhd = playable && (stype == 0x1f || stype == 0x20);
	const bool hd = playable && (stype == 0x19 || stype == 0x11);
	SETBIT(sUHD, uhd);
	SETBIT(sHD, hd);
	SETBIT(sSD, playable && !uhd && !hd);
	SETBIT(sHasNumber, playable && m_chanel_number_visible && ref.getChannelNum() > 0);

	ePtr<gPixmap> piconPix;
	bool piconSVG = false;
	if (tpl.usesPicon && playable && PyCallable_Check(m_GetPiconNameFunc))
	{
		picon(ref, H * 5 / 3, piconPix, piconSVG);
		SETBIT(sHasPicon, piconPix);
	}
	#undef SETBIT
	const uint64_t fl = st | m_flags;

	// service type icon, as in the legacy renderer
	const int orbpos = ref.getUnsignedData(4) >> 16;
	ePtr<gPixmap> &typePix =
		(ref.flags & eServiceReference::isGroup) ? m_pixmaps[picServiceGroup] :
		(ref.path.find("://") != std::string::npos) ? m_pixmaps[picStream] :
		(orbpos == 0xFFFF) ? m_pixmaps[picDVB_C] :
		(orbpos == 0xEEEE) ? m_pixmaps[picDVB_T] : m_pixmaps[picDVB_S];
	ePtr<gPixmap> &resPix = uhd ? m_pixmaps[pic4K] : hd ? m_pixmaps[picHD] : m_pixmaps[picSD];

	// pick the rows for this kind of entry, markers/folders without own rows fall back to the service rows
	int wantKind = isMarker ? rowMarker : isDir ? rowDirectory : rowService;
	std::vector<const Row *> rows;
	for (size_t i = 0; i < tpl.rows.size(); ++i)
		if (tpl.rows[i].kind == wantKind && (fl & tpl.rows[i].req) == tpl.rows[i].req && !(fl & tpl.rows[i].forbid))
			rows.push_back(&tpl.rows[i]);
	if (rows.empty() && wantKind != rowService)
		for (size_t i = 0; i < tpl.rows.size(); ++i)
			if (tpl.rows[i].kind == rowService && (fl & tpl.rows[i].req) == tpl.rows[i].req && !(fl & tpl.rows[i].forbid))
				rows.push_back(&tpl.rows[i]);
	if (rows.empty())
		return;

	// vertical distribution
	int fixedSum = 0, totalWeight = 0;
	for (size_t i = 0; i < rows.size(); ++i)
	{
		if (rows[i]->height > 0)
			fixedSum += rows[i]->height;
		else
			totalWeight += rows[i]->weight;
	}
	const int rem = std::max(0, H - fixedSum);

	struct Slot
	{
		const Item *it;
		int w;
		int mode;
		bool shrunk;
		std::string text;
		ePtr<gPixmap> pix, pixSel;
		ePtr<eTextPara> para;
		bool svg;
		int vaOv, haOv; // vertical / horizontal alignment forced by a stack (-1: the item's own)
	};

	// turns one laid out slot into a display list operation
	auto emit = [&](Slot &s, int x, int ty, int w, int h)
	{
		const Item &it = *s.it;
		// lineHeight: the item lives in a band of that height (e.g. the height of the text line next to it).
		// The band is placed in the row by valign and the item is centred inside it, so icons, bars and
		// text with the same lineHeight and valign stay level with each other.
		int va = s.vaOv >= 0 ? s.vaOv : it.valign;
		const int al = s.haOv >= 0 ? s.haOv : it.align;
		if (it.lineH > 0 && it.lineH < h)
		{
			ty += va == 0 ? 0 : va == 2 ? h - it.lineH : (h - it.lineH) / 2;
			h = it.lineH;
			va = 1;
		}
		// offset of something `space` pixels smaller than the row, as the item wants it placed
		auto vpos = [&](int space) { return va == 0 ? 0 : va == 2 ? space : space / 2; };
		Op op;
		op.kind = opFill;
		op.style = it.style;
		op.flags = 0;
		op.border = 0;
		op.begin = 0;
		op.duration = 0;
		op.z = it.z;
		op.radius = 0;
		op.edges = 0;
		for (int k = 0; k < 2; ++k)
			op.colSet[k] = op.bcolSet[k] = false;
		switch (it.type)
		{
		case itText:
		{
			ePtr<eTextPara> para = s.para;
			if (!para || s.mode != wAuto || s.shrunk || it.absolute)
			{
				para = new eTextPara(eRect(0, 0, std::max(w, 1), h));
				para->setFont(it.font);
				para->renderString(s.text.c_str(), it.ellipsis ? ellipsisFlag : 0);
			}
			eRect bb = para->getBoundBox();
			int px = x;
			if (al == 1)
				px = x + (w - bb.width()) / 2;
			else if (al == 2)
				px = x + w - bb.width();
			op.kind = opText;
			op.para = para;
			op.rect = eRect(px, ty + vpos(h - bb.height()), bb.width(), bb.height());
			out.ops.push_back(op);
			break;
		}
		case itPicon:
			if (!s.pix)
				break;
		{
			op.pixmap = s.pix;
			// the picon is fitted into its box: full row height minus margin, or `height` placed by valign
			const int boxH = it.height > 0 ? std::min(it.height, h) : h - 2 * it.margin;
			op.rect = eRect(x, ty + (it.height > 0 ? vpos(h - boxH) : it.margin), w, boxH);
			int flags = gPainter::BT_ALPHABLEND;
			if (al == -1 || al == 1) // centred unless told otherwise
				flags |= gPainter::BT_HALIGN_CENTER;
			else if (al == 2)
				flags |= gPainter::BT_HALIGN_RIGHT;
			flags |= va == 1 ? gPainter::BT_VALIGN_CENTER : va == 2 ? gPainter::BT_VALIGN_BOTTOM : 0;
			// a rasterised svg is blitted 1:1; one larger than the box (it is rendered for the cell height,
			// not for this box) is scaled down to fit like any other picon instead of being cropped
			const eSize pps = s.pix->size();
			if (s.svg && pps.width() <= w && pps.height() <= boxH)
				op.kind = opBlitSVG;
			else
			{
				op.kind = opBlitScale;
				flags |= gPainter::BT_KEEP_ASPECT_RATIO;
			}
			op.flags = flags;
		}
			out.ops.push_back(op);
			break;
		case itServiceType:
		case itCrypto:
		case itRecord:
		case itResolution:
		case itBackup:
		case itCatchup:
		case itKind:
		{
			if (!s.pix)
				break;
			op.pixmap = s.pix;
			eSize ps = s.pix->size();
			if (ps.height() > h || (it.absolute && ps.width() > w))
			{
				op.kind = opBlitScale;
				op.flags = gPainter::BT_ALPHABLEND | gPainter::BT_KEEP_ASPECT_RATIO | gPainter::BT_HALIGN_CENTER | gPainter::BT_VALIGN_CENTER;
				op.rect = eRect(x, ty, w, h);
			}
			else
			{
				int ox = x;
				if (al == 1)
					ox = x + (w - ps.width()) / 2;
				else if (al == 2)
					ox = x + w - ps.width();
				op.kind = opBlit;
				op.rect = eRect(ox, ty + vpos(h - ps.height()), ps.width(), ps.height());
			}
			out.ops.push_back(op);
			break;
		}
		case itProgress:
		{
			if (!evt)
				break;
			int b = it.border >= 0 ? it.border : m_progressbar_border_width;
			int ph = it.height > 0 ? it.height : m_progressbar_height + 2 * b;
			op.kind = opProgress;
			op.border = b;
			op.begin = evt->getBeginTime();
			op.duration = evt->getDuration();
			op.rect = eRect(x, ty + vpos(h - ph), w, ph);
			out.ops.push_back(op);
			break;
		}
		case itLine:
		{
			int th = it.height > 0 ? it.height : 2;
			op.kind = opFill;
			op.rect = eRect(x, ty + vpos(h - th), w, th);
			out.ops.push_back(op);
			break;
		}
		case itRect:
		{
			const int rh = it.height > 0 ? std::min(it.height, h) : h;
			op.kind = opRect;
			op.rect = eRect(x, ty + vpos(h - rh), w, rh);
			op.radius = it.radius;
			op.edges = it.edges;
			op.border = it.border > 0 ? it.border : 0;
			for (int k = 0; k < 2; ++k)
			{
				op.colSet[k] = it.colSet[k];
				op.col[k] = it.col[k];
				op.bcolSet[k] = it.bcolSet[k];
				op.bcol[k] = it.bcol[k];
			}
			out.ops.push_back(op);
			break;
		}
		case itPixmap:
		{
			if (!s.pix)
				break;
			op.pixmap = s.pix;
			op.pixmapSel = s.pixSel;
			eSize ps = s.pix->size();
			if (it.wmode == wAuto && it.height <= 0 && !it.absolute && ps.height() <= h)
			{
				// content sized: natural size, placed by align / valign
				int ox = x;
				if (al == 1)
					ox = x + (w - ps.width()) / 2;
				else if (al == 2)
					ox = x + w - ps.width();
				op.kind = opBlit;
				op.rect = eRect(ox, ty + vpos(h - ps.height()), ps.width(), ps.height());
			}
			else
			{
				// fitted into the item box (width x height or row height), centred unless told otherwise
				const int bh = it.height > 0 ? std::min(it.height, h) : h;
				op.rect = eRect(x, ty + vpos(h - bh), w, bh);
				int flags = gPainter::BT_ALPHABLEND;
				if (al == -1 || al == 1)
					flags |= gPainter::BT_HALIGN_CENTER;
				else if (al == 2)
					flags |= gPainter::BT_HALIGN_RIGHT;
				flags |= va == 1 ? gPainter::BT_VALIGN_CENTER : va == 2 ? gPainter::BT_VALIGN_BOTTOM : 0;
				if (it.isSvg)
					op.kind = opBlitSVG;
				else
				{
					op.kind = opBlitScale;
					if (it.keepAspect)
						flags |= gPainter::BT_KEEP_ASPECT_RATIO;
				}
				op.flags = flags;
			}
			out.ops.push_back(op);
			break;
		}
		}
	};

	// builds the slot of one item (what it shows and how wide it is); false when the item has nothing to show
	auto buildSlot = [&](const Item &it, int rowH, Slot &s) -> bool
	{
		s.it = &it;
		s.vaOv = s.haOv = -1;
		s.w = 0;
		s.svg = false;
		s.shrunk = false;
		// width="@param": a fixed width taken from a runtime parameter, content sized while it is unset
		int fixedW = it.width;
		s.mode = it.wmode;
		if (s.mode == wParam)
		{
			std::map<std::string, int>::iterator pi = m_params.find(it.param);
			int v = pi != m_params.end() ? pi->second : 0;
			s.mode = v > 0 ? wFixed : wAuto;
			fixedW = v;
		}
		switch (it.type)
		{
		case itText:
		{
			for (size_t k = 0; k < it.tokens.size(); ++k)
			{
				const Token &tk = it.tokens[k];
				if (tk.kind == tokLiteral)
					s.text += tk.lit;
				else
				{
					std::string v = tokenText(tk.kind, ref, name, evt, evt_next, now);
					if (!v.empty())
						s.text += v + tk.lit; // lit is the optional "|suffix" of the token
				}
			}
			if (s.text.empty())
				return false;
			if (s.mode == wAuto && !it.absolute)
			{
				s.para = new eTextPara(eRect(0, 0, 4096, rowH));
				s.para->setFont(it.font);
				s.para->renderString(s.text.c_str());
				s.w = s.para->getBoundBox().width();
			}
			else
				s.w = s.mode == wFixed ? fixedW : 0;
			break;
		}
		case itPicon:
			s.pix = piconPix;
			s.svg = piconSVG;
			if (!s.pix && !it.reserve)
				return false;
			s.w = s.mode == wFixed ? fixedW : s.mode == wAuto ? H * 5 / 3 : 0;
			break;
		case itServiceType:
		case itCrypto:
		case itRecord:
		case itResolution:
		case itBackup:
		case itCatchup:
		case itKind:
		{
			if (it.type == itServiceType)
				s.pix = playable ? typePix : ePtr<gPixmap>();
			else if (it.type == itCrypto)
				s.pix = m_pixmaps[picCrypto];
			else if (it.type == itRecord)
				s.pix = m_pixmaps[picRecord];
			else if (it.type == itResolution)
				s.pix = playable ? resPix : ePtr<gPixmap>();
			else if (it.type == itBackup)
				s.pix = m_pixmaps[picBackup];
			else if (it.type == itCatchup)
				s.pix = m_pixmaps[picCatchup];
			else
				s.pix = isMarker ? m_pixmaps[picMarker] : isDir ? m_pixmaps[picFolder] : ePtr<gPixmap>();
			if (!s.pix)
				return false;
			if (s.mode == wFixed)
				s.w = fixedW;
			else if (s.mode == wAuto)
			{
				eSize ps = s.pix->size();
				s.w = (ps.height() > rowH && ps.height() > 0) ? ps.width() * rowH / ps.height() : ps.width();
			}
			break;
		}
		case itPixmap:
		{
			s.pix = it.pix;
			s.pixSel = it.pixSel;
			if (!s.pix)
				return false;
			if (s.mode == wFixed)
				s.w = fixedW;
			else if (s.mode == wAuto)
			{
				eSize ps = s.pix->size();
				const int bh = it.height > 0 ? std::min(it.height, rowH) : (ps.height() > rowH ? rowH : ps.height());
				s.w = ps.height() > 0 ? ps.width() * bh / ps.height() : ps.width();
			}
			break;
		}
		case itProgress:
			if (!hasEvent)
				return false;
			s.w = s.mode == wFixed ? fixedW : 0;
			break;
		case itLine:
		case itRect:
		case itSpacer:
			s.w = s.mode == wFixed ? fixedW : 0;
			break;
		}
		return true;
	};

	int y0 = 0;
	for (size_t ri = 0; ri < rows.size(); ++ri)
	{
		const Row &row = *rows[ri];
		const int rowH = row.height > 0 ? row.height : (totalWeight ? rem * row.weight / totalWeight : 0);
		std::vector<Slot> flow, overlays;
		flow.reserve(row.items.size());

		for (size_t ii = 0; ii < row.items.size(); ++ii)
		{
			const Item &it = row.items[ii];
			if (it.stackId >= 0 || (fl & it.req) != it.req || (fl & it.forbid))
				continue;
			Slot s;
			if (!buildSlot(it, rowH, s))
				continue;
			if (it.absolute)
				overlays.push_back(std::move(s));
			else
				flow.push_back(std::move(s));
		}

		// horizontal distribution: fixed/auto first, flex items share what is left
		int used = 0, totalFlexWeight = 0;
		for (size_t i = 0; i < flow.size(); ++i)
		{
			used += flow[i].w;
			if (flow[i].mode == wFlex)
				totalFlexWeight += flow[i].it->weight;
		}
		if (!flow.empty())
			used += row.gap * (int)(flow.size() - 1);
		const int freeSpace = W - row.padLeft - row.padRight - used;
		for (size_t i = 0; i < flow.size(); ++i)
		{
			if (flow[i].mode == wFlex)
			{
				int share = (freeSpace > 0 && totalFlexWeight) ? freeSpace * flow[i].it->weight / totalFlexWeight : 0;
				flow[i].w = std::max(share, flow[i].it->minw);
			}
		}
		// content sized text that still does not fit gives way (widest first) and is elided
		int overflow = -(W - row.padLeft - row.padRight - used);
		for (size_t i = 0; i < flow.size(); ++i)
			if (flow[i].mode == wFlex)
				overflow += flow[i].w;
		while (overflow > 0)
		{
			int widest = -1;
			for (size_t i = 0; i < flow.size(); ++i)
			{
				const Item &fi = *flow[i].it;
				const int floorW = std::max(fi.minw, 24);
				if (fi.type == itText && flow[i].mode == wAuto && fi.ellipsis && flow[i].w > floorW && (widest < 0 || flow[i].w > flow[widest].w))
					widest = (int)i;
			}
			if (widest < 0)
				break;
			const int floorW = std::max(flow[widest].it->minw, 24);
			const int cut = std::min(overflow, flow[widest].w - floorW);
			flow[widest].w -= cut;
			flow[widest].shrunk = true;
			overflow -= cut;
		}
		int x = row.padLeft;
		if (row.align)
		{
			// the items do not fill the row (no `*` item): centre or right align the group
			int total = flow.empty() ? 0 : row.gap * (int)(flow.size() - 1);
			for (size_t i = 0; i < flow.size(); ++i)
				total += flow[i].w;
			const int spare = W - row.padLeft - row.padRight - total;
			if (spare > 0)
				x += row.align == 1 ? spare / 2 : spare;
		}
		for (size_t i = 0; i < flow.size(); ++i)
		{
			emit(flow[i], x, y0 + row.padTop, flow[i].w, std::max(0, rowH - row.padTop - row.padBottom));
			x += flow[i].w + row.gap;
		}
		// absolute items are positioned relative to the whole cell, whatever row they are declared in
		for (size_t i = 0; i < overlays.size(); ++i)
		{
			const eRect &a = overlays[i].it->absRect;
			emit(overlays[i], a.left(), a.top(), a.width(), a.height());
		}
		// stacks: groups of items laid out along one axis like an eStack. Members are placed from the start
		// or the end (stackAlign) or centred, with `spacing` between them; members without any size take no
		// space; one member can fill what the others leave over (stackFill, or a width of "*"). The box is
		// the row's content area, or the `pos` rect of the stack (relative to the whole cell).
		for (size_t si = 0; si < row.stacks.size(); ++si)
		{
			const Stack &st = row.stacks[si];
			if ((fl & st.req) != st.req || (fl & st.forbid))
				continue;
			int sx, sy, sw, sh;
			if (st.absolute)
			{
				sx = st.rect.left();
				sy = st.rect.top();
				sw = st.rect.width();
				sh = st.rect.height();
			}
			else
			{
				sx = row.padLeft;
				sy = y0 + row.padTop;
				sw = std::max(0, W - row.padLeft - row.padRight);
				sh = std::max(0, rowH - row.padTop - row.padBottom);
			}
			std::vector<Slot> kids;
			for (size_t ii = 0; ii < row.items.size(); ++ii)
			{
				const Item &it = row.items[ii];
				if (it.stackId != (int)si || (fl & it.req) != it.req || (fl & it.forbid))
					continue;
				Slot k;
				if (buildSlot(it, sh, k))
					kids.push_back(std::move(k));
			}
			// size of every member along the stack
			std::vector<int> len(kids.size(), 0);
			std::vector<char> skip(kids.size(), 0), fill(kids.size(), 0);
			int used = 0, count = 0, fillIdx = -1;
			for (size_t i = 0; i < kids.size(); ++i)
			{
				Slot &k = kids[i];
				const Item &it = *k.it;
				fill[i] = it.stackFill || k.mode == wFlex;
				if (st.horizontal)
					len[i] = k.w;
				else
					switch (it.type)
					{
					case itText:
					{
						ePtr<eTextPara> p = k.para;
						if (!p)
						{
							p = new eTextPara(eRect(0, 0, 4096, std::max(sh, 1)));
							p->setFont(it.font);
							p->renderString(k.text.c_str());
						}
						len[i] = p->getBoundBox().height();
						break;
					}
					case itPicon:
					case itRect:
					case itSpacer:
						len[i] = it.height;
						break;
					case itProgress:
						len[i] = it.height > 0 ? it.height : m_progressbar_height + 2 * (it.border >= 0 ? it.border : m_progressbar_border_width);
						break;
					case itLine:
						len[i] = it.height > 0 ? it.height : 2;
						break;
					default:
						len[i] = k.pix ? k.pix->size().height() : 0;
						break;
					}
				if (fill[i])
				{
					if (fillIdx >= 0)
					{
						skip[i] = 1; // only the first member fills
						continue;
					}
					fillIdx = (int)i;
				}
				else if (len[i] <= 0)
				{
					skip[i] = 1;
					continue;
				}
				if (it.stackAlign == 2)
					continue; // centred members do not count for the fill
				count++;
				if ((int)i != fillIdx)
					used += len[i];
			}
			const int total = st.horizontal ? sw : sh;
			if (fillIdx >= 0)
			{
				len[fillIdx] = std::max(0, total - used - st.spacing * (count - 1));
				kids[fillIdx].mode = wFlex; // makes the text lay itself out for the width it got
			}
			// placement along the stack
			int startPos = 0, endPos = total, startCount = 0, endCount = 0;
			for (size_t i = 0; i < kids.size(); ++i)
			{
				if (skip[i])
					continue;
				Slot &k = kids[i];
				const Item &it = *k.it;
				int p;
				if (it.stackAlign == 1)
				{
					p = endPos - len[i];
					endPos -= len[i];
					if (endCount > 0)
					{
						p -= st.spacing;
						endPos -= st.spacing;
					}
					endCount++;
				}
				else if (it.stackAlign == 2)
					p = (total - len[i]) / 2;
				else
				{
					p = startPos;
					startPos += len[i];
					if (startCount > 0)
					{
						startPos += st.spacing;
						p += st.spacing;
					}
					startCount++;
				}
				if (st.horizontal)
				{
					if (it.stackCross >= 0)
						k.vaOv = it.stackCross;
					emit(k, sx + p, sy, len[i], sh);
				}
				else
				{
					if (it.stackCross >= 0)
						k.haOv = it.stackCross;
					emit(k, sx, sy + p, sw, len[i]);
				}
			}
		}
		y0 += rowH;
	}

	// items with a `z` are drawn in that order (negative: behind the others), equal z keeps the template order
	bool layered = false;
	for (size_t i = 0; i < out.ops.size(); ++i)
		if (out.ops[i].z)
			layered = true;
	if (layered)
		std::stable_sort(out.ops.begin(), out.ops.end(), [](const Op &a, const Op &b) { return a.z < b.z; });
}

/* ---------------------------------- painting ---------------------------------- */

bool eListboxServiceTemplateContent::resolveColor(const Style &st, int selected, int marked, int dyn, bool border, gRGB &out) const
{
	if (border)
	{
		int i = selected ? cBorderSel : cBorder;
		if (!st.set[i])
			i = cBorder;
		if (!st.set[i])
			return false;
		out = st.c[i];
		return true;
	}
	if (marked == 2)
	{
		if (!st.set[cMarkedSel])
			return false;
		out = st.c[cMarkedSel];
		return true;
	}
	if (marked == 1)
	{
		if (!st.set[cMarked])
			return false;
		out = st.c[cMarked];
		return true;
	}
	bool have = false;
	int i = selected ? cFgSel : cFg;
	if (st.set[i])
	{
		out = st.c[i];
		have = true;
	}
	if (dyn & dynFallback)
	{
		i = selected ? cFgSelFallback : cFgFallback;
		if (st.set[i])
		{
			out = st.c[i];
			have = true;
		}
	}
	if ((dyn & dynUnavail) && st.set[cNotAvail])
	{
		out = st.c[cNotAvail];
		have = true;
	}
	if ((dyn & dynRecorded) && m_record_indicator_mode == 3 && st.set[cRecorded])
	{
		out = st.c[cRecorded];
		have = true;
	}
	return have;
}

void eListboxServiceTemplateContent::paintOps(gPainter &painter, eWindowStyle &style, const ePoint &offset, int selected, int marked, const RowCache &rc, time_t now)
{
	bool dirty = false; // painter colours differ from the row's base colours

	auto setStyleColor = [&](int si, bool border)
	{
		gRGB c;
		if (si >= 0 && si < (int)m_styles.size() && resolveColor(m_styles[si], selected, marked, rc.dynState, border, c))
		{
			painter.setForegroundColor(c);
			dirty = true;
		}
		else if (border)
		{
			painter.setForegroundColor(gRGB(0xdfdfdf));
			dirty = true;
		}
		else if (dirty)
		{
			applyBaseColors(painter, style, selected, marked);
			dirty = false;
		}
	};

	for (size_t i = 0; i < rc.ops.size(); ++i)
	{
		const Op &op = rc.ops[i];
		eRect r(op.rect.left() + offset.x(), op.rect.top() + offset.y(), op.rect.width(), op.rect.height());
		// static pixmaps may have an own image for the selected row
		gPixmap *pm = (selected && op.pixmapSel) ? (gPixmap*)op.pixmapSel : (gPixmap*)op.pixmap;
		switch (op.kind)
		{
		case opText:
			setStyleColor(op.style, false);
			painter.renderPara(op.para, ePoint(r.left(), r.top()));
			break;
		case opBlit:
			painter.clip(r);
			painter.blit(pm, ePoint(r.left(), r.top()), r, gPainter::BT_ALPHABLEND);
			painter.clippop();
			break;
		case opBlitScale:
			painter.clip(r);
			painter.blitScale(pm, r, r, op.flags);
			painter.clippop();
			break;
		case opBlitSVG:
			painter.clip(r);
			painter.blit(pm, r, eRect(), op.flags);
			painter.clippop();
			break;
		case opFill:
			setStyleColor(op.style, false);
			painter.fill(r);
			break;
		case opRect:
		{
			// own colour of the item first (the selected one falls back to the normal one), else the style
			const int ci = selected ? 1 : 0;
			gRGB fill, frame;
			bool hasFill = false, hasFrame = false;
			if (op.colSet[ci])
			{
				fill = op.col[ci];
				hasFill = true;
			}
			else if (op.colSet[0])
			{
				fill = op.col[0];
				hasFill = true;
			}
			else if (op.style >= 0 && op.style < (int)m_styles.size())
				hasFill = resolveColor(m_styles[op.style], selected, marked, rc.dynState, false, fill);
			if (op.bcolSet[ci])
			{
				frame = op.bcol[ci];
				hasFrame = true;
			}
			else if (op.bcolSet[0])
			{
				frame = op.bcol[0];
				hasFrame = true;
			}
			else if (op.style >= 0 && op.style < (int)m_styles.size())
				hasFrame = resolveColor(m_styles[op.style], selected, marked, rc.dynState, true, frame);
			if (op.radius <= 0 && op.border <= 0)
			{
				// plain filled rectangle
				if (hasFill)
				{
					painter.setForegroundColor(fill);
					dirty = true;
				}
				else
					setStyleColor(op.style, false);
				painter.fill(r);
			}
			else if (op.radius <= 0 && !hasFill)
			{
				// square frame without fill
				const int b = op.border;
				painter.setForegroundColor(hasFrame ? frame : gRGB(0xdfdfdf));
				dirty = true;
				painter.fill(eRect(r.left(), r.top(), r.width(), b));
				painter.fill(eRect(r.left(), r.top() + r.height() - b, r.width(), b));
				painter.fill(eRect(r.left(), r.top() + b, b, std::max(0, r.height() - 2 * b)));
				painter.fill(eRect(r.left() + r.width() - b, r.top() + b, b, std::max(0, r.height() - 2 * b)));
			}
			else
			{
				// rounded and/or bordered: the rectangle is filled with the background colour
				painter.setBackgroundColor(hasFill ? fill : gRGB(0xff000000));
				if (op.border > 0)
					painter.setBorder(hasFrame ? frame : (hasFill ? fill : gRGB(0xdfdfdf)), op.border);
				if (op.radius > 0)
					painter.setRadius(op.radius, op.edges);
				painter.drawRectangle(r);
				if (op.border > 0)
					painter.setBorder(gRGB(0u), 0);
				dirty = true;
			}
			break;
		}
		case opProgress:
		{
			const int b = op.border;
			const int pbw = std::max(0, r.width() - 2 * b);
			const int ph = std::max(0, r.height() - 2 * b);
			int done = op.duration > 0 ? (int)((long long)pbw * (now - op.begin) / op.duration) : 0;
			done = std::min(std::max(done, 0), pbw);
			eRect fillRect(r.left() + b, r.top() + b, done, ph);
			ePtr<gPixmap> &bar = m_pixmaps[picServiceEventProgressbar];
			if (bar)
			{
				painter.clip(fillRect);
				painter.blit(bar, ePoint(fillRect.left(), fillRect.top()), fillRect, gPainter::BT_ALPHABLEND);
				painter.clippop();
			}
			else
			{
				setStyleColor(op.style, false);
				painter.fill(fillRect);
			}
			setStyleColor(op.style, true);
			if (b)
			{
				painter.fill(eRect(r.left(), r.top(), pbw + 2 * b, b));
				painter.fill(eRect(r.left(), r.top() + b + ph, pbw + 2 * b, b));
				painter.fill(eRect(r.left(), r.top() + b, b, ph));
				painter.fill(eRect(r.left() + b + pbw, r.top() + b, b, ph));
			}
			else
				painter.fill(eRect(r.left() + done, r.top(), pbw - done, ph));
			break;
		}
		}
	}
}

int eListboxServiceTemplateContent::getItemWidth()
{
	return (m_cur_index >= 0 && m_templates[m_cur_index].orientation != eListbox::orVertical) ? m_templates[m_cur_index].itemWidth : -1;
}

void eListboxServiceTemplateContent::getListboxOverrides(eListboxOverrides &ov)
{
	if (m_cur_index < 0)
		return;
	const Template &t = m_templates[m_cur_index];
	ov.selectionZoom = t.selectionZoom;
	ov.carousel = t.carousel;
	ov.carouselZoom = t.carouselZoom;
	ov.carouselFocus = t.carouselFocus;
	ov.carouselCenterWidth = t.carouselCenterWidth;
	ov.carouselCenterHeight = t.carouselCenterHeight;
}

bool eListboxServiceTemplateContent::getItemSpacing(int &x, int &y)
{
	if (m_cur_index < 0)
		return false;
	x = m_templates[m_cur_index].spacingX;
	y = m_templates[m_cur_index].spacingY;
	return x >= 0 || y >= 0;
}

int eListboxServiceTemplateContent::getOrientation()
{
	return m_cur_index >= 0 ? m_templates[m_cur_index].orientation : (int)eListbox::orVertical;
}

// grid: tells the listbox which entries are rows of their own (markers, when the template asks for it)
bool eListboxServiceTemplateContent::gridSpanList(std::vector<char> &out)
{
	out.clear();
	if (m_cur_index < 0 || !m_templates[m_cur_index].spanMarkers || m_span_width <= 0)
		return false;
	bool any = false;
	for (list::iterator i(m_list.begin()); i != m_list.end(); ++i)
	{
		const bool marker = (i->flags & eServiceReference::isMarker) != 0;
		out.push_back(marker ? 1 : 0);
		any = any || marker;
	}
	return any;
}

// vertical list: a marker is as high as markerHeight says instead of a normal row
bool eListboxServiceTemplateContent::entryHeightList(std::vector<int> &out)
{
	out.clear();
	if (m_cur_index < 0 || m_templates[m_cur_index].orientation != (int)eListbox::orVertical || m_templates[m_cur_index].markerHeight <= 0)
		return false;
	const int height = m_templates[m_cur_index].markerHeight;
	bool any = false;
	for (list::iterator i(m_list.begin()); i != m_list.end(); ++i)
	{
		const bool marker = (i->flags & eServiceReference::isMarker) != 0;
		out.push_back(marker ? height : 0);
		any = any || marker;
	}
	return any;
}

void eListboxServiceTemplateContent::setSpanWidth(int width)
{
	m_span_width = width;
}

int eListboxServiceTemplateContent::gridSpanHeight()
{
	return (m_cur_index >= 0 && m_templates[m_cur_index].spanMarkers) ? m_templates[m_cur_index].markerHeight : 0;
}

void eListboxServiceTemplateContent::paint(gPainter &painter, eWindowStyle &style, const ePoint &offset, int selected)
{
	eServiceListPaintTimer profileTimer(eServiceListPaintTimer::statTemplate);
	// a marker of a grid that spans is as wide as the whole grid: lay it out and paint it with that width
	const eSize cellSize = m_itemsize;
	const int cellHeight = m_itemheight;
	if (m_span_width > 0 && m_cur_index >= 0 && m_templates[m_cur_index].spanMarkers && m_templates[m_cur_index].orientation == (int)eListbox::orGrid &&
		cursorValid() && ((*m_cursor).flags & eServiceReference::isMarker))
	{
		const int markerHeight = m_templates[m_cur_index].markerHeight;
		m_itemheight = markerHeight > 0 ? markerHeight : cellHeight;
		m_itemsize = eSize(m_span_width, m_itemheight);
	}
	else if (m_cur_index >= 0 && m_templates[m_cur_index].orientation == (int)eListbox::orVertical && m_templates[m_cur_index].markerHeight > 0 &&
		cursorValid() && ((*m_cursor).flags & eServiceReference::isMarker))
	{
		// vertical list: a marker has a height of its own
		m_itemheight = m_templates[m_cur_index].markerHeight;
		m_itemsize = eSize(cellSize.width(), m_itemheight);
	}
	painter.clip(eRect(offset, m_itemsize));

	const int marked = getMarkedState(selected);
	paintBackground(painter, style, offset, selected, marked);

	if (cursorValid() && m_cur_index >= 0)
	{
		const bool zoomed = m_zoom != 100;
		if (!zoomed && m_cell_override && m_itemsize.height() == cellSize.height() && m_itemheight == cellHeight)
			m_itemheight = m_itemsize.height(); // the focused carousel slot has a size of its own, lay the rows out in it
		if (zoomed)
		{
			prepareZoomTemplate();
			if (m_itemsize.height() == cellSize.height() && m_itemheight == cellHeight) // not a marker with a height of its own
				m_itemheight = m_itemsize.height();
		}
		const Template &tpl = zoomed ? m_zoom_tpl : m_templates[m_cur_index];
		std::map<eServiceReference, RowCache> &rowCache = zoomed ? m_zoom_rows : m_rows;
		paintSelection(painter, style, offset, selected, tpl.large);

		const eServiceReference ref = *m_cursor;
		if (selected)
			prefetchKick();
		const time_t now = time(0);
		ePtr<iStaticServiceInformation> info;
		m_service_center->info(ref, info);
		const bool playable = !(ref.flags & (eServiceReference::isMarker | eServiceReference::isDirectory));

		int dyn = 0;
		if (playable && isRecordedCached(ref, now))
			dyn |= dynRecorded;
		if (!marked && playable && info && m_is_playable_ignore.valid())
		{
			int v = info->isPlayable(ref, m_is_playable_ignore);
			if (v == 0)
				dyn |= dynUnavail;
			else if (v == 2)
				dyn |= dynFallback;
		}

		std::map<eServiceReference, RowCache>::iterator it = rowCache.find(ref);
		if (it == rowCache.end() || it->second.gen != m_gen || it->second.dyn != dyn ||
			it->second.width != m_itemsize.width() || it->second.height != m_itemheight || now >= it->second.validUntil)
		{
			if (rowCache.size() > 256)
				rowCache.clear();
			RowCache &rc = rowCache[ref];
			rc.gen = m_gen;
			rc.dyn = dyn;
			rc.width = m_itemsize.width();
			rc.height = m_itemheight;
			profileTimer.setMiss();
			{
				eServiceListPaintTimer buildTimer(eServiceListPaintTimer::statTemplateBuild);
				buildRow(tpl, ref, info, dyn, now, rc);
			}
			it = rowCache.find(ref);
		}
		paintOps(painter, style, offset, selected, marked, it->second, now);
	}
	painter.clippop();
	m_itemsize = cellSize;
	m_itemheight = cellHeight;
}
