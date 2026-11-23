// XboxCompat common tracing. Header-only, no CRT-heavy dependencies.
// Enable by setting environment variable XBOXCOMPAT_LOG to a file path.
// Every shim logs each call it receives, so the first run of the real game is a call trace, not guesswork.
#pragma once
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdarg.h>

namespace xc {

inline void log(const char* module, const char* fmt, ...)
{
    char path[MAX_PATH];
    DWORD n = GetEnvironmentVariableA("XBOXCOMPAT_LOG", path, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) return;

    char line[1024];
    int off = _snprintf_s(line, sizeof(line), _TRUNCATE, "[%lu:%lu] %s: ",
                          GetCurrentProcessId(), GetCurrentThreadId(), module);
    if (off < 0) off = 0;
    va_list ap;
    va_start(ap, fmt);
    int m = _vsnprintf_s(line + off, sizeof(line) - off - 2, _TRUNCATE, fmt, ap);
    va_end(ap);
    if (m < 0) m = (int)(sizeof(line) - off - 2);
    size_t len = (size_t)off + (size_t)m;
    line[len++] = '\n';

    HANDLE h = CreateFileA(path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr,
                           OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return;
    DWORD w = 0;
    WriteFile(h, line, (DWORD)len, &w, nullptr);
    CloseHandle(h);
}

} // namespace xc
