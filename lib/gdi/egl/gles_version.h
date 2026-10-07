#pragma once

#include <cstring>
#include <string>

#ifdef HAVE_GLES3
#include <GLES3/gl3.h>
#else
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>

// Single-channel texture enums are core GLES3 only, but the shared upload
// code names them in isGLES3() ? GL_R8/GL_RED : GL_LUMINANCE expressions that
// still have to compile (never execute) in a GLES2-only build. Values per the
// Khronos headers.
#ifndef GL_RED
#define GL_RED 0x1903
#endif
#ifndef GL_R8
#define GL_R8 0x8229
#endif
#endif

// gles_version.h
// Runtime GLES version singleton.
// Set exactly once by gEGLDC::initEGL() after the EGL context is created.
// All shader and atlas files read isGLES3() to select their code paths.

namespace gles
{
    // 2 = OpenGL ES 2.0, 3 = OpenGL ES 3.0
    // 0 means not yet initialised (context not created).
    extern int version;

    // True if this platform's actual display scanout reads back a render
    // target's colors in the opposite R/B order from what GL writes - see
    // gshader.cpp's fragment shader for the ground-truth test that proved
    // this true on Dreambox's VC5/BEGL pixmap-surface scanout. Every shader
    // that outputs a solid/blended color (gshader.cpp, gadvanced_shader.cpp,
    // gtext_shader.cpp) and every texture upload that claims GL_RGBA for
    // data that's actually BGRA in memory (gtexture_manager.cpp, gegldc.cpp's
    // text-overlay compositing) deliberately pre-swaps to cancel that out -
    // correct ONLY on a backend where the scanout quirk is actually present.
    // Set once by gEGLDC::initEGL() from the window provider (see
    // INativeWindowProvider::needsRenderTargetRBSwap()) - NOT assumed true
    // by default, since it's a Dreambox-specific hardware quirk, not a
    // general EGL/GLES behavior.
    extern bool needsRBSwap;

    inline bool isGLES3() { return version >= 3; }

    // Driver-reported version strings (eglQueryString(EGL_VERSION) and
    // glGetString(GL_VERSION)), e.g. "1.4" / "OpenGL ES 3.0 Mesa 23.1".
    // Empty until the context is created; exposed to Python through
    // getEGLVersionString() / getGLESVersionString() (main/enigma.cpp).
    extern std::string eglVersionString;
    extern std::string glesVersionString;

    // How per-draw vertex data reaches the GPU - see setVertexData().
    // Set once by gEGLDC::initEGL() (ENIGMA_EGL_CLIENT_ARRAYS=0 turns it off).
    extern bool clientArrays;

    // One interleaved float attribute of a shader's vertex layout.
    struct VertexAttrib {
        GLuint index;
        GLint size;       // floats
        int offset;       // floats from the start of a vertex
    };

    // Supplies `bytes` of interleaved float vertex data (stride_floats per
    // vertex) for the draw call(s) that follow; endVertexData() after them.
    //
    // Default (clientArrays): client-side arrays - no buffer object at all;
    // the driver copies the data into its own streaming memory at draw time.
    // Every shader here used to re-upload one small VBO many times per frame
    // instead, and on gbquad4kpro's Broadcom driver EVERY way of modifying a
    // buffer the current frame already drew from waits for the GPU:
    // ENIGMA_EGL_PROFILE showed text VBO uploads at ~1ms/frame with an idle
    // GPU but up to 19-21ms while it was busy - identically for
    // glMapBufferRange(INVALIDATE) and for glBufferData() orphaning - and the
    // frame's ~240-1400 other draws slowed from 9ms to 40-240ms the same way.
    // Client arrays never touch a buffer the GPU might still be reading.
    //
    // Core in GLES2, and in GLES3 as long as vertex array object 0 is bound
    // (client pointers are invalid with any other VAO), hence the explicit
    // glBindVertexArray(0) below.
    inline void setVertexData(GLuint vao, GLuint vbo, const float* data, GLsizeiptr bytes, int stride_floats, const VertexAttrib* attribs, int count)
    {
        const GLsizei stride = stride_floats * (GLsizei)sizeof(float);
        if (clientArrays) {
#if defined(HAVE_GLES3)
            if (isGLES3())
                glBindVertexArray(0);
#endif
            glBindBuffer(GL_ARRAY_BUFFER, 0);
            for (int i = 0; i < count; ++i) {
                glVertexAttribPointer(attribs[i].index, attribs[i].size, GL_FLOAT, GL_FALSE, stride, data + attribs[i].offset);
                glEnableVertexAttribArray(attribs[i].index);
            }
            return;
        }

        // Buffer-object path, kept as the ENIGMA_EGL_CLIENT_ARRAYS=0 fallback.
#if defined(HAVE_GLES3)
        if (isGLES3()) {
            // The VAO holds the attribute layout (set up once in each
            // shader's init()); GL_ARRAY_BUFFER is NOT VAO state, so it must
            // be bound here or the upload lands in another shader's buffer.
            glBindVertexArray(vao);
            glBindBuffer(GL_ARRAY_BUFFER, vbo);
        } else
#endif
        {
            glBindBuffer(GL_ARRAY_BUFFER, vbo);
            for (int i = 0; i < count; ++i) {
                glVertexAttribPointer(attribs[i].index, attribs[i].size, GL_FLOAT, GL_FALSE, stride, (const void*)(attribs[i].offset * sizeof(float)));
                glEnableVertexAttribArray(attribs[i].index);
            }
        }
        glBufferData(GL_ARRAY_BUFFER, bytes, data, GL_STREAM_DRAW);
    }

    inline void endVertexData(const VertexAttrib* attribs, int count)
    {
#if defined(HAVE_GLES3)
        if (isGLES3() && !clientArrays) {
            glBindVertexArray(0);
            return;
        }
#endif
        // Client pointers must not outlive the data they point into, and
        // GLES2 re-specifies its layout per draw anyway.
        for (int i = 0; i < count; ++i)
            glDisableVertexAttribArray(attribs[i].index);
    }
}
