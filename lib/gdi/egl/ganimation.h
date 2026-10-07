#pragma once

// Window show/hide animation presets for the EGL backend (Layer A of doc/ANIMATIONS.md).
//
// Pure math, no GL: a preset says how a window's snapshot is faded, scaled and moved over
// time; gEGLDC (gegldc.cpp) turns that into quads. The two settings below are written from
// the Python main thread (AnimationSetup via setAnimation_current/speed) and read on gRC's
// render thread, hence atomics.

namespace ganim {

// How a snapshot is drawn at one instant. Scale is about the anchor point (fractions of
// the window rect), the translation is in fractions of the window size.
struct Transform {
	float alpha;
	float sx, sy;
	float ax, ay;
	float tx, ty;
};

struct Preset {
	const char* name;
	float a0, a1;
	float sx0, sx1, sy0, sy1;
	float ax, ay;
	float tx0, tx1, ty0, ty1;
	bool stripes; // drawn as horizontal stripes sweeping in, transform ignored
	bool overshoot; // show eases out with a small overshoot
	int base_ms; // duration at the default speed
};

// Index 0 (and anything out of range) means "no animation". The numbering is the one
// AnimationSetup uses (1 simple fade ... 14 stripes).
const Preset* getPreset(int index);

void setPreset(int index);
void setSpeed(int speed);
int currentPreset();
int currentSpeed();

int durationMs(const Preset& preset, int speed);

// 0..1 timeline position -> how far the window is "in" (show: 0 -> 1, hide: 1 -> 0).
float amountAt(const Preset& preset, bool show, float t);

Transform evaluate(const Preset& preset, float amount);

// Destination rectangle (x0, y0, x1, y1) of a window rect (x, y, w, h) under a transform.
void destRect(const Transform& tr, float x, float y, float w, float h, float out[4]);

} // namespace ganim
