"""Windows Job containment and native exit verification for provider children."""
from __future__ import annotations

import ctypes
import ctypes.wintypes

__all__ = [
    'assign_kill_on_close_job', 'close_job_handle', 'job_process_ids',
    'open_job_process', 'terminate_job', 'wait_process_handle',
]

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
_kernel32.WaitForSingleObject.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.DWORD]
_kernel32.WaitForSingleObject.restype = ctypes.wintypes.DWORD
_kernel32.TerminateJobObject.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.UINT]
_kernel32.TerminateJobObject.restype = ctypes.wintypes.BOOL
_kernel32.QueryInformationJobObject.argtypes = [
    ctypes.wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, ctypes.wintypes.DWORD, ctypes.POINTER(ctypes.wintypes.DWORD),
]
_kernel32.QueryInformationJobObject.restype = ctypes.wintypes.BOOL
_kernel32.OpenProcess.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.BOOL, ctypes.wintypes.DWORD]
_kernel32.OpenProcess.restype = ctypes.wintypes.HANDLE
_kernel32.IsProcessInJob.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.HANDLE, ctypes.POINTER(ctypes.wintypes.BOOL)]
_kernel32.IsProcessInJob.restype = ctypes.wintypes.BOOL


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
        raise OSError(f'CloseHandle(job) failed ({ctypes.get_last_error()})')


def wait_process_handle(handle: int, timeout: float) -> bool:
    """Wait for kernel process completion independently of a cached exit code."""
    result = _kernel32.WaitForSingleObject(handle, max(0, int(timeout * 1000)))
    if result == 0:
        return True
    if result == 258:  # WAIT_TIMEOUT
        return False
    raise OSError(f'process handle wait failed ({ctypes.get_last_error()})')


def terminate_job(job: int) -> None:
    """Request termination while retaining the Job handle for exit verification."""
    if not _kernel32.TerminateJobObject(job, 1):
        raise OSError(f'TerminateJobObject failed ({ctypes.get_last_error()})')


def job_process_ids(job: int) -> list[int]:
    """Read a complete, bounded snapshot of the Job and its nested processes."""
    capacity = 16
    while capacity <= 4096:
        header_size = 2 * ctypes.sizeof(ctypes.wintypes.DWORD)
        buffer = ctypes.create_string_buffer(header_size + capacity * ctypes.sizeof(ctypes.c_size_t))
        success = _kernel32.QueryInformationJobObject(job, 3, buffer, len(buffer), None)
        assigned, returned = (ctypes.wintypes.DWORD * 2).from_buffer(buffer)
        if success and returned <= assigned <= capacity:
            values = (ctypes.c_size_t * returned).from_buffer(buffer, header_size)
            if returned == assigned:
                return list(values)
        elif not success and ctypes.get_last_error() != 234:  # ERROR_MORE_DATA
            raise OSError(f'QueryInformationJobObject failed ({ctypes.get_last_error()})')
        capacity = max(capacity * 2, assigned)
    raise OSError('Job process list exceeds shutdown tracking limit')


def open_job_process(job: int, pid: int) -> int | None:
    """Retain a member's wait handle, rejecting a PID reused outside the Job."""
    handle = _kernel32.OpenProcess(0x00101000, False, pid)  # SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        error_code = ctypes.get_last_error()
        if error_code == 87:  # ERROR_INVALID_PARAMETER: process no longer exists
            return None
        raise OSError(f'OpenProcess(job member) failed ({error_code})')
    belongs = ctypes.wintypes.BOOL()
    if not _kernel32.IsProcessInJob(handle, job, ctypes.byref(belongs)):
        error_code = ctypes.get_last_error()
        _kernel32.CloseHandle(handle)
        raise OSError(f'IsProcessInJob failed ({error_code})')
    if not belongs.value:
        _kernel32.CloseHandle(handle)
        return None
    return int(handle)

