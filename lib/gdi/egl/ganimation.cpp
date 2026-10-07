#include <lib/gdi/egl/ganimation.h>

#include <algorithm>
#include <atomic>

namespace ganim {

namespace {

std::atomic<int> s_preset{0};
std::atomic<int> s_speed{20};

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

} // namespace ganim
