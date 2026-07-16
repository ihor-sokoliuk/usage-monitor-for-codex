"""Windows kill-on-close Job containment for the Codex provider child."""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging

__all__ = ['assign_kill_on_close_job', 'close_job_handle']

log = logging.getLogger(__name__)
_JOB_KILL_ON_CLOSE = 0x00002000


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    class _BASIC(ctypes.Structure):
        _fields_ = [
            ('PerProcessUserTimeLimit', ctypes.c_int64),
            ('PerJobUserTimeLimit', ctypes.c_int64),
            ('LimitFlags', ctypes.wintypes.DWORD),
            ('MinimumWorkingSetSize', ctypes.c_size_t),
            ('MaximumWorkingSetSize', ctypes.c_size_t),
            ('ActiveProcessLimit', ctypes.wintypes.DWORD),
            ('Affinity', ctypes.c_size_t),
            ('PriorityClass', ctypes.wintypes.DWORD),
            ('SchedulingClass', ctypes.wintypes.DWORD),
        ]

    class _COUNTERS(ctypes.Structure):
        _fields_ = [
            ('ReadOperationCount', ctypes.c_uint64),
            ('WriteOperationCount', ctypes.c_uint64),
            ('OtherOperationCount', ctypes.c_uint64),
            ('ReadTransferCount', ctypes.c_uint64),
            ('WriteTransferCount', ctypes.c_uint64),
            ('OtherTransferCount', ctypes.c_uint64),
        ]

    _fields_ = [
        ('BasicLimitInformation', _BASIC),
        ('IoInfo', _COUNTERS),
        ('ProcessMemoryLimit', ctypes.c_size_t),
        ('JobMemoryLimit', ctypes.c_size_t),
        ('PeakProcessMemoryUsed', ctypes.c_size_t),
        ('PeakJobMemoryUsed', ctypes.c_size_t),
    ]


# Without explicit signatures, ctypes truncates HANDLEs to c_int on 64-bit
# Windows and can corrupt the process or Job-object handles.
_kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
_kernel32.CreateJobObjectW.argtypes = [ctypes.wintypes.LPVOID, ctypes.wintypes.LPCWSTR]
_kernel32.CreateJobObjectW.restype = ctypes.wintypes.HANDLE
_kernel32.SetInformationJobObject.argtypes = [ctypes.wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, ctypes.wintypes.DWORD]
_kernel32.SetInformationJobObject.restype = ctypes.wintypes.BOOL
_kernel32.AssignProcessToJobObject.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.HANDLE]
_kernel32.AssignProcessToJobObject.restype = ctypes.wintypes.BOOL
_kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
_kernel32.CloseHandle.restype = ctypes.wintypes.BOOL


def assign_kill_on_close_job(process_handle: int) -> int:
    """Create a kill-on-close Job object and assign the child to it."""
    job = _kernel32.CreateJobObjectW(None, None)
    if not job:
        raise OSError(f'CreateJobObjectW failed ({ctypes.get_last_error()})')

    information = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    information.BasicLimitInformation.LimitFlags = _JOB_KILL_ON_CLOSE
    job_object_extended_limit_information = 9
    configured = _kernel32.SetInformationJobObject(
        job,
        job_object_extended_limit_information,
        ctypes.byref(information),
        ctypes.sizeof(information),
    )
    if not configured:
        error_code = ctypes.get_last_error()
        _kernel32.CloseHandle(job)
        raise OSError(f'SetInformationJobObject failed ({error_code})')

    if not _kernel32.AssignProcessToJobObject(job, process_handle):
        error_code = ctypes.get_last_error()
        _kernel32.CloseHandle(job)
        raise OSError(f'AssignProcessToJobObject failed ({error_code})')

    return int(job)


def close_job_handle(job: int) -> None:
    if not _kernel32.CloseHandle(job):
        log.warning('CloseHandle(job) failed with error %s', ctypes.get_last_error())

