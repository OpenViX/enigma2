#pragma once

#include <cstring>

#ifdef HAVE_GLES3
#include <GLES3/gl3.h>
#else
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
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

    inline bool isGLES3() { return version >= 3; }

    // Uploads `size` bytes into whatever GL_ARRAY_BUFFER is currently bound
    // (every call site here binds its own m_vbo right before calling this).
    // Prefers glMapBufferRange()'s GL_MAP_INVALIDATE_BUFFER_BIT - confirmed
    // available on this hardware's actual driver (core GLES3, and this box's
    // GL_EXTENSIONS also lists GL_OES_mapbuffer - see gEGLDC::tryInitEGL()'s
    // startup log dump) - over glBufferSubData(). glBufferSubData() copies
    // into whatever physical storage the buffer already has, which the
    // driver must either block on (if the GPU is still reading last frame's
    // contents from it) or silently race; GL_MAP_INVALIDATE_BUFFER_BIT tells
    // the driver this call doesn't care about the buffer's previous contents
    // at all, so it's free to hand back a *different* backing allocation
    // instead of waiting - the same write-during-GPU-read hazard class as
    // the font atlas texture upload stall already fixed elsewhere, just on
    // the vertex-buffer side. GLES2 has no core glMapBufferRange, so it
    // keeps using glBufferSubData() (this path is only ever a single small
    // quad there, not worth chasing via GL_OES_mapbuffer's whole-buffer-only
    // semantics).
    inline void uploadDynamicVBO(GLsizeiptr size, const void* data)
    {
#if defined(HAVE_GLES3)
        if (isGLES3()) {
            void* ptr = glMapBufferRange(GL_ARRAY_BUFFER, 0, size, GL_MAP_WRITE_BIT | GL_MAP_INVALIDATE_BUFFER_BIT);
            if (ptr) {
                memcpy(ptr, data, (size_t)size);
                glUnmapBuffer(GL_ARRAY_BUFFER);
                return;
            }
            // Map can legally fail (e.g. GL_OUT_OF_MEMORY) - fall back below.
        }
#endif
        glBufferSubData(GL_ARRAY_BUFFER, 0, size, data);
    }
}
