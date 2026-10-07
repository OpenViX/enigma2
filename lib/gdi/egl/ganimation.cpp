#include <lib/gdi/egl/ganimation.h>

#include <algorithm>
#include <atomic>
#include <cctype>
#include <cmath>
#include <cstdlib>
#include <mutex>

namespace ganim {

namespace {

std::atomic<int> s_preset{0};
std::atomic<int> s_speed{20};
std::atomic<bool> s_lists{false};

// name, alpha, scale x, scale y, anchor, translate x, translate y, stripes, overshoot, ms
const Preset kPresets[] = {
	{nullptr, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, false, false, 0}, // 0: disabled
	{"simplefade", 0, 1, 1, 1, 1, 1, 0.5f, 0.5f, 0, 0, 0, 0, false, false, 300},
	{"simplezoom", 0, 1, 0.6f, 1, 0.6f, 1, 0.5f, 0.5f, 0, 0, 0, 0, false, false, 300},
	{"growdrop", 0, 1, 1, 1, 0.1f, 1, 0.5f, 0.0f, 0, 0, 0, 0, false, false, 350},
	{"growfromleft", 0, 1, 0.1f, 1, 1, 1, 0.0f, 0.5f, 0, 0, 0, 0, false, false, 350},
	{"extrudefromleft", 0, 1, 0.6f, 1, 1, 1, 0.0f, 0.5f, -0.4f, 0, 0, 0, false, false, 350},
	{"popup", 0, 1, 0.8f, 1, 0.8f, 1, 0.5f, 0.5f, 0, 0, 0, 0, false, true, 300},
	{"slidedrop", 0, 1, 1, 1, 1, 1, 0.5f, 0.5f, 0, 0, -0.3f, 0, false, false, 300},
	{"slidefromleft", 0, 1, 1, 1, 1, 1, 0.5f, 0.5f, -0.3f, 0, 0, 0, false, false, 300},
	{"slidelefttoright", 1, 1, 1, 1, 1, 1, 0.5f, 0.5f, -1, 0, 0, 0, false, false, 350},
	{"sliderighttoleft", 1, 1, 1, 1, 1, 1, 0.5f, 0.5f, 1, 0, 0, 0, false, false, 350},
	{"slidetoptobottom", 1, 1, 1, 1, 1, 1, 0.5f, 0.5f, 0, 0, -1, 0, false, false, 350},
	{"zoomfromleft", 0, 1, 0.1f, 1, 0.1f, 1, 0.0f, 0.5f, 0, 0, 0, 0, false, false, 350},
	{"zoomfromright", 0, 1, 0.1f, 1, 0.1f, 1, 1.0f, 0.5f, 0, 0, 0, 0, false, false, 350},
	{"stripes", 1, 1, 1, 1, 1, 1, 0.5f, 0.5f, 0, 0, 0, 0, true, false, 500},
};

const int kPresetCount = sizeof(kPresets) / sizeof(kPresets[0]);

float lerp(float a, float b, float t) {
	return a + (b - a) * t;
}

float easeOutCubic(float t) {
	const float u = 1.0f - t;
	return 1.0f - u * u * u;
}

float easeInCubic(float t) {
	return t * t * t;
}

float easeOutBack(float t) {
	const float c1 = 1.70158f;
	const float c3 = c1 + 1.0f;
	const float u = t - 1.0f;
	return 1.0f + c3 * u * u * u + c1 * u * u;
}

} // namespace

const Preset* getPreset(int index) {
	if (index <= 0 || index >= kPresetCount)
		return nullptr;
	return &kPresets[index];
}

void setPreset(int index) {
	s_preset.store(index);
}

void setSpeed(int speed) {
	s_speed.store(speed);
}

int currentPreset() {
	return s_preset.load();
}

int currentSpeed() {
	return s_speed.load();
}

void setListsEnabled(bool enabled) {
	s_lists.store(enabled);
}

bool listsEnabled() {
	return s_lists.load();
}

int listDurationMs(int speed) {
	// Same speed scale as durationMs(): 15..30, 20 is the default and higher is faster.
	const int s = std::max(5, std::min(60, speed));
	return std::max(80, 260 * 20 / s);
}

float listAmountAt(float t) {
	return easeOutCubic(std::max(0.0f, std::min(1.0f, t)));
}

int durationMs(const Preset& preset, int speed) {
	// AnimationSetup's speed runs 15..30 with 20 as the default: higher is faster.
	const int s = std::max(5, std::min(60, speed));
	return std::max(60, preset.base_ms * 20 / s);
}

float amountAt(const Preset& preset, bool show, float t) {
	t = std::max(0.0f, std::min(1.0f, t));
	if (show)
		return preset.overshoot ? easeOutBack(t) : easeOutCubic(t);
	return 1.0f - easeInCubic(t);
}

Transform evaluate(const Preset& preset, float amount) {
	Transform tr;
	tr.alpha = std::max(0.0f, std::min(1.0f, lerp(preset.a0, preset.a1, amount)));
	tr.sx = lerp(preset.sx0, preset.sx1, amount);
	tr.sy = lerp(preset.sy0, preset.sy1, amount);
	tr.ax = preset.ax;
	tr.ay = preset.ay;
	tr.tx = lerp(preset.tx0, preset.tx1, amount);
	tr.ty = lerp(preset.ty0, preset.ty1, amount);
	return tr;
}

void destRect(const Transform& tr, float x, float y, float w, float h, float out[4]) {
	const float cx = x + tr.ax * w;
	const float cy = y + tr.ay * h;
	out[0] = cx + (x - cx) * tr.sx + tr.tx * w;
	out[1] = cy + (y - cy) * tr.sy + tr.ty * h;
	out[2] = cx + (x + w - cx) * tr.sx + tr.tx * w;
	out[3] = cy + (y + h - cy) * tr.sy + tr.ty * h;
}

// ---------------------------------------------------------------------------------------
// Kodi style control animations
// ---------------------------------------------------------------------------------------

bool Xf::identity() const {
	return alpha >= 0.9999f && std::fabs(sx - 1.0f) < 0.0001f && std::fabs(sy - 1.0f) < 0.0001f && std::fabs(tx) < 0.01f && std::fabs(ty) < 0.01f;
}

float Animation::durationMs() const {
	float d = 0;
	for (const Effect& e : effects)
		d = std::max(d, e.delay_ms + e.time_ms);
	return d;
}

namespace {

// The "in" curve of each tween, t in 0..1. Out and in-out are derived from it (see tweenValue()).
float tweenIn(Tween tween, float t) {
	switch (tween) {
		case Tween::Quadratic:
			return t * t;
		case Tween::Cubic:
			return t * t * t;
		case Tween::Sine:
			return 1.0f - std::cos(t * 1.57079632679f);
		case Tween::Back: {
			const float s = 1.70158f;
			return t * t * ((s + 1.0f) * t - s);
		}
		case Tween::Circle:
			return 1.0f - std::sqrt(std::max(0.0f, 1.0f - t * t));
		case Tween::Bounce: {
			// 1 - bounceOut(1 - t)
			float u = 1.0f - t;
			float v;
			if (u < 1.0f / 2.75f)
				v = 7.5625f * u * u;
			else if (u < 2.0f / 2.75f) {
				u -= 1.5f / 2.75f;
				v = 7.5625f * u * u + 0.75f;
			} else if (u < 2.5f / 2.75f) {
				u -= 2.25f / 2.75f;
				v = 7.5625f * u * u + 0.9375f;
			} else {
				u -= 2.625f / 2.75f;
				v = 7.5625f * u * u + 0.984375f;
			}
			return 1.0f - v;
		}
		case Tween::Elastic: {
			if (t <= 0.0f)
				return 0.0f;
			if (t >= 1.0f)
				return 1.0f;
			const float p = 0.3f;
			return -std::pow(2.0f, 10.0f * (t - 1.0f)) * std::sin(((t - 1.0f) - p / 4.0f) * 6.28318530718f / p);
		}
		case Tween::Linear:
		default:
			return t;
	}
}

float clamp01(float v) {
	return std::max(0.0f, std::min(1.0f, v));
}

std::vector<std::string> splitString(const std::string& s, char sep) {
	std::vector<std::string> out;
	size_t start = 0;
	for (;;) {
		const size_t pos = s.find(sep, start);
		if (pos == std::string::npos) {
			out.push_back(s.substr(start));
			break;
		}
		out.push_back(s.substr(start, pos - start));
		start = pos + 1;
	}
	return out;
}

std::string trim(const std::string& s) {
	size_t b = 0, e = s.size();
	while (b < e && std::isspace((unsigned char)s[b]))
		++b;
	while (e > b && std::isspace((unsigned char)s[e - 1]))
		--e;
	return s.substr(b, e - b);
}

std::string lower(std::string s) {
	for (char& c : s)
		c = (char)std::tolower((unsigned char)c);
	return s;
}

// "10", "10,20" or "x,y,w,h" -> up to 4 numbers
int parseFloats(const std::string& s, float* out) {
	int n = 0;
	for (const std::string& part : splitString(s, ',')) {
		if (n >= 4)
			break;
		const std::string p = trim(part);
		if (p.empty())
			continue;
		char* end = nullptr;
		const float v = std::strtof(p.c_str(), &end);
		if (end == p.c_str())
			continue;
		out[n++] = v;
	}
	return n;
}

bool isInType(const std::string& type) {
	return type == "windowopen" || type == "visible" || type == "focus" || type == "conditional";
}

Tween tweenFromName(const std::string& n) {
	if (n == "quadratic")
		return Tween::Quadratic;
	if (n == "cubic")
		return Tween::Cubic;
	if (n == "sine")
		return Tween::Sine;
	if (n == "back")
		return Tween::Back;
	if (n == "circle")
		return Tween::Circle;
	if (n == "bounce")
		return Tween::Bounce;
	if (n == "elastic")
		return Tween::Elastic;
	return Tween::Linear;
}

Easing easingFromName(const std::string& n) {
	if (n == "in")
		return Easing::In;
	if (n == "inout")
		return Easing::InOut;
	return Easing::Out;
}

// Applies `e` (a transform of its own) after `r`: x'' = e(r(x)).
void compose(Xf& r, float esx, float esy, float etx, float ety) {
	r.sx *= esx;
	r.sy *= esy;
	r.tx = esx * r.tx + etx;
	r.ty = esy * r.ty + ety;
}

} // namespace

float tweenValue(Tween tween, Easing easing, float t) {
	t = clamp01(t);
	switch (easing) {
		case Easing::In:
			return tweenIn(tween, t);
		case Easing::InOut:
			if (t < 0.5f)
				return tweenIn(tween, 2.0f * t) * 0.5f;
			return 1.0f - tweenIn(tween, 2.0f * (1.0f - t)) * 0.5f;
		case Easing::Out:
		default:
			return 1.0f - tweenIn(tween, 1.0f - t);
	}
}

bool parseAnimation(const std::string& type, const std::string& spec, Animation& out) {
	out.effects.clear();
	const std::string atype = lower(trim(type));
	for (const std::string& raw : splitString(spec, ';')) {
		const std::vector<std::string> tokens = splitString(raw, '|');
		if (tokens.empty())
			continue;
		const std::string name = lower(trim(tokens[0]));
		Effect e;
		if (name == "fade")
			e.type = EffType::Fade;
		else if (name == "slide")
			e.type = EffType::Slide;
		else if (name == "zoom")
			e.type = EffType::Zoom;
		else if (name == "rotate" || name == "rotatex" || name == "rotatey")
			e.type = EffType::Rotate; // accepted, not drawn
		else
			continue;

		// Kodi defaults: fade in types 0 -> 100, the others 100 -> 0; zoom 100 -> 100
		if (e.type == EffType::Fade) {
			e.s[0] = isInType(atype) ? 0.0f : 100.0f;
			e.e[0] = isInType(atype) ? 100.0f : 0.0f;
			e.s_count = e.e_count = 1;
		} else if (e.type == EffType::Zoom) {
			e.s[0] = e.e[0] = 100.0f;
			e.s_count = e.e_count = 1;
		}

		for (size_t i = 1; i < tokens.size(); ++i) {
			const size_t eq = tokens[i].find('=');
			if (eq == std::string::npos)
				continue;
			const std::string key = lower(trim(tokens[i].substr(0, eq)));
			const std::string value = trim(tokens[i].substr(eq + 1));
			if (key == "start") {
				e.s_count = parseFloats(value, e.s);
			} else if (key == "end") {
				e.e_count = parseFloats(value, e.e);
			} else if (key == "time") {
				e.time_ms = std::max(0.0f, (float)std::atof(value.c_str()));
			} else if (key == "delay") {
				e.delay_ms = std::max(0.0f, (float)std::atof(value.c_str()));
			} else if (key == "tween") {
				e.tween = tweenFromName(lower(value));
			} else if (key == "easing") {
				e.easing = easingFromName(lower(value));
			} else if (key == "center") {
				float c[4];
				if (lower(value) != "auto" && parseFloats(value, c) >= 2) {
					e.center_auto = false;
					e.cx = c[0];
					e.cy = c[1];
				}
			}
		}
		out.effects.push_back(e);
	}
	return !out.effects.empty();
}

namespace {
std::mutex s_registry_mutex;
std::vector<std::shared_ptr<const Animation>> s_registry; // id - 1
std::vector<std::string> s_registry_keys;
} // namespace

int registerAnimation(const char* type, const char* spec) {
	if (!type || !spec || !*spec)
		return 0;
	const std::string key = std::string(type) + "#" + spec;
	std::lock_guard<std::mutex> lock(s_registry_mutex);
	for (size_t i = 0; i < s_registry_keys.size(); ++i)
		if (s_registry_keys[i] == key)
			return (int)i + 1;
	Animation anim;
	if (!parseAnimation(type, spec, anim))
		return 0;
	s_registry.push_back(std::make_shared<const Animation>(anim));
	s_registry_keys.push_back(key);
	return (int)s_registry.size();
}

std::shared_ptr<const Animation> getAnimation(int id) {
	std::lock_guard<std::mutex> lock(s_registry_mutex);
	if (id <= 0 || id > (int)s_registry.size())
		return nullptr;
	return s_registry[id - 1];
}

Xf evaluateAnimation(const Animation& anim, float elapsed_ms, float x, float y, float w, float h) {
	Xf r;
	for (const Effect& e : anim.effects) {
		float amount;
		if (elapsed_ms < e.delay_ms)
			amount = 0.0f;
		else if (e.time_ms <= 0.0f)
			amount = 1.0f;
		else
			amount = clamp01((elapsed_ms - e.delay_ms) / e.time_ms);
		const float k = tweenValue(e.tween, e.easing, amount); // may leave 0..1 (back, elastic)
		auto lerpv = [k](float a, float b) { return a + (b - a) * k; };

		switch (e.type) {
			case EffType::Fade:
				r.alpha *= clamp01(lerpv(e.s[0], e.e[0]) / 100.0f);
				break;
			case EffType::Slide: {
				const float sx0 = e.s_count > 0 ? e.s[0] : 0.0f, sy0 = e.s_count > 1 ? e.s[1] : 0.0f;
				const float ex0 = e.e_count > 0 ? e.e[0] : 0.0f, ey0 = e.e_count > 1 ? e.e[1] : 0.0f;
				compose(r, 1.0f, 1.0f, lerpv(sx0, ex0), lerpv(sy0, ey0));
				break;
			}
			case EffType::Zoom: {
				float zx, zy, add_x, add_y; // x'' = zx * x + add_x
				if (e.s_count >= 4 && e.e_count >= 4 && w > 0.0f && h > 0.0f) {
					const float rx = lerpv(e.s[0], e.e[0]), ry = lerpv(e.s[1], e.e[1]);
					const float rw = lerpv(e.s[2], e.e[2]), rh = lerpv(e.s[3], e.e[3]);
					zx = rw / w;
					zy = rh / h;
					add_x = x * (1.0f - zx) + rx;
					add_y = y * (1.0f - zy) + ry;
				} else {
					zx = lerpv(e.s[0], e.e[0]) / 100.0f;
					zy = (e.s_count >= 2 && e.e_count >= 2) ? lerpv(e.s[1], e.e[1]) / 100.0f : zx;
					const float cx = e.center_auto ? x + w * 0.5f : x + e.cx;
					const float cy = e.center_auto ? y + h * 0.5f : y + e.cy;
					add_x = cx * (1.0f - zx);
					add_y = cy * (1.0f - zy);
				}
				compose(r, zx, zy, add_x, add_y);
				break;
			}
			case EffType::Rotate:
			default:
				break;
		}
	}
	return r;
}

} // namespace ganim
