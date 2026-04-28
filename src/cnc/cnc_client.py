import ctypes
import logging
import struct
import sys
from ctypes import POINTER, WinDLL, c_char_p, c_int, c_uint, c_wchar_p

from cncapi.python.cncstructs import CNC_JOB_STATUS
from src.core.config import Settings

logger = logging.getLogger(__name__)

# CNC_RC_* return codes from cncenums.py
CNC_RC_OK = 0
CNC_RC_ALREADY_RUNS = 6
CNC_RC_ALREADY_CONNECTED = 7
CNC_RC_ERR_SERVER_NOT_RUNNING = 22
CNC_RC_ERR_NOT_CONNECTED = 24


class CncClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._connected = False
        self._load_job_func = None
        self._dll = self._load_dll()
        self._configure_prototypes()

    # -- public properties ---------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._connected

    # -- lifecycle -----------------------------------------------------------

    def connect(self) -> int:
        logger.info("Connecting to CNC...")
        result = self._dll.CncConnectServer(
            self._settings.ini_path.encode("ascii")
        )

        # If connect fails, clean up a possible stale connection
        # from a previous session and retry once.
        if result not in (CNC_RC_OK, CNC_RC_ALREADY_RUNS, CNC_RC_ALREADY_CONNECTED):
            logger.warning(
                "CNC connect returned %d, retrying after disconnect...", result,
            )
            try:
                self._dll.CncDisConnectServer()
            except OSError:
                pass
            result = self._dll.CncConnectServer(
                self._settings.ini_path.encode("ascii")
            )

        if result == CNC_RC_OK:
            logger.info("CNC connected successfully")
            self._connected = True
            self._reset_if_powerup()
        elif result in (CNC_RC_ALREADY_RUNS, CNC_RC_ALREADY_CONNECTED):
            logger.info("CNC already running/connected (code %d)", result)
            self._connected = True
            self._reset_if_powerup()
        elif result == CNC_RC_ERR_SERVER_NOT_RUNNING:
            logger.warning(
                "CNC server not running (code %d) — "
                "is the CNC software started?",
                result,
            )
        else:
            logger.warning("CNC connect returned code %d", result)
        return result

    def disconnect(self) -> None:
        if not self._connected:
            logger.debug("CNC already disconnected, skipping...")
            return

        logger.info("Disconnecting from CNC...")
        try:
            result = self._dll.CncDisConnectServer()
            self._connected = False
            if result == CNC_RC_OK:
                logger.info("CNC disconnected successfully")
            else:
                logger.warning("CNC disconnect returned code %d", result)
        except Exception as e:
            logger.error("Error during CNC disconnect: %s", e)
            self._connected = False

    def is_server_connected(self) -> bool:
        """Check if the CNC server is actually alive.

        CncIsServerConnected() only reads a cached shared-memory flag
        that stays True after the server exits.  We also verify that
        the CncServer.exe process is still running.
        """
        try:
            if self._dll.CncIsServerConnected() != 1:
                return False
        except OSError:
            return False
        return self.is_server_process_alive()

    @staticmethod
    def is_server_process_alive() -> bool:
        """Check if CncServer.exe is running via Win32 snapshot."""
        TH32CS_SNAPPROCESS = 0x00000002
        kernel32 = ctypes.windll.kernel32

        class PROCESSENTRY32(ctypes.Structure):
            _fields_ = [
                ("dwSize", ctypes.c_ulong),
                ("cntUsage", ctypes.c_ulong),
                ("th32ProcessID", ctypes.c_ulong),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", ctypes.c_ulong),
                ("cntThreads", ctypes.c_ulong),
                ("th32ParentProcessID", ctypes.c_ulong),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", ctypes.c_ulong),
                ("szExeFile", ctypes.c_char * 260),
            ]

        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snap == -1:
            return False

        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        try:
            if not kernel32.Process32First(snap, ctypes.byref(entry)):
                return False
            while True:
                name = entry.szExeFile.decode("utf-8", errors="ignore").lower()
                if name == "cncserver.exe":
                    return True
                if not kernel32.Process32Next(snap, ctypes.byref(entry)):
                    return False
        finally:
            kernel32.CloseHandle(snap)

    # -- operations ----------------------------------------------------------

    def get_state(self) -> int:
        """Return the interpreter execution state (CNC_IE_* enum, 0-23)."""
        return self._dll.CncGetState()

    def get_job_status(self) -> dict:
        """Return all fields from CNC_JOB_STATUS as a dict."""
        ptr = self._dll.CncGetJobStatus()
        s = ptr.contents

        # Get job name and log for debugging
        job_name = s.jobName if s.jobName else ""
        # logger.debug("jobName from structure: '%s' (len=%d)", job_name, len(job_name))

        return {
            "jobName": job_name,
            "jobLoadCounter": s.jobLoadCounter,
            # "numLinesInJob": s.numLinesInjob,
            # "numLinesInMacro": s.numLinesInMacro,
            # "numLinesInUserMacro": s.numLinesInUserMacro,
            # "numBytesInJob": s.numBytesInJob,
            # "isLongJob": s.isLongJob,
            # "isSuperLongJob": s.isSuperLongJob,
            # "jobIsRendered": s.jobIsRendered,
            "totalJobLengthMm": s.totalJobLength,
            "jobProgressMm": s.jobProgress,
            "jobActualRunningTimeSeconds": s.jobActualRunningTime,
            "jobRemainingRunningTimeSeconds": s.jobRemainingRunningTime,
            "jobEstimatedTimeSeconds": s.jobEstimatedTime,
            # "TCACollision": s.TCACollision,
            # "MCACollision": s.MCACollision,
            # "xCollision": s.xCollision,
            # "yCollision": s.yCollision,
            # "zCollision": s.zCollision,
            # "jobRenderLine": s.jobRenderLine,
            # "jobRenderProgressPercentage": s.jobRenderProgressPercentage,
            # "curIpLine": s.curIpLine,
            # "curIpLineText": s.curIpLineText.decode("ascii", errors="replace").rstrip('\x00'),
            # "curExLine": s.curExLine,
            # "lastKnownExecutedLineNumber": s.lastKnownExcutedLineNumber,
            # "lastKnownToolChangeLineNumber": s.lastKnownToolChangeLineNumber,
            "doRepeatJob": s.doRepeatJob,
            "nrOfJobRepeatsSet": s.nrOfJobRepeatsSet,
            "nrOfRepeatsActual": s.nrOfRepeatsActual,
            # "extraLineWhenEndOfJob": s.extraLineWhenEndOfJob.decode(
            #     "ascii", errors="replace"
            # ),
            # "stockDiameterTurning": s.stockDiameterTurning,
            # "stockLengthTurning": s.stockLengthTurning,
            # "stockZAtWorkOffset": s.stockZAtworkOffset,
        }

    def load_job(self, file_name: str) -> int:
        """Load a job into the CNC interpreter.

        Note: the EdingCNC GUI does not refresh its G-code panel or
        toolpath when a job is loaded via the API.  The job *is* loaded
        on the server and can be executed with Start.
        """
        if self._load_job_func is None:
            raise NotImplementedError(
                "LoadJob function not found in DLL"
            )

        result = self._load_job_func(file_name)
        logger.info("CncLoadJob('%s') returned %d", file_name, result)

        if result == CNC_RC_OK:
            # Switch GUI to Auto/Program view
            CNC_UIOACTION_TO_AUTO_MENU = 12
            try:
                self._dll.CncSendToGUI(
                    c_int(CNC_UIOACTION_TO_AUTO_MENU),
                    c_int(0), c_int(0),
                )
            except Exception as e:
                logger.warning("CncSendToGUI failed: %s", e)

            try:
                self._dll.CncSendUserMessage(
                    b"ERP-Adapter", b"", c_int(0),
                    c_int(0), c_int(CNC_RC_OK),
                    f"Job loaded: {file_name}".encode("utf-8"),
                )
            except Exception as e:
                logger.warning("CncSendUserMessage failed: %s", e)

        return result

    def set_job_quantity(self, quantity: int) -> int:
        """Set the number of times the job should repeat.

        Args:
            quantity: Number of times to repeat the job (1-9999)
                     1 = run once (no repeat)
                     2 = run twice (repeat once)
                     etc.

        Returns:
            CNC_RC_OK (0) on success, error code otherwise
        """
        try:
            # CncSetExtraJobOptions(extraLine, doRepeat, numberOfRepeats)
            # doRepeat: 1 = enable repeat, 0 = disable
            # numberOfRepeats: total number of executions
            do_repeat = 1 if quantity > 1 else 0
            if do_repeat == 1:
                extra_line = b"M02"  # M02 = end of program, so repeat starts over
            else:
                extra_line = b""  # no extra line needed when not repeating
            result = self._dll.CncSetExtraJobOptions(
                extra_line,  # extraLine - no extra G-code line
                c_int(do_repeat),
                c_uint(quantity)
            )
            logger.info("CncSetExtraJobOptions(doRepeat=%d, qty=%d) returned %d",
                       do_repeat, quantity, result)
            return result
        except Exception as e:
            logger.error("Failed to set job quantity: %s", e)
            return -1

    def render_job(self) -> int:
        """Start rendering the loaded job so the CNC computes toolpath data.

        Rendering populates totalJobLength, jobProgress, time estimates,
        and other fields in CNC_JOB_STATUS. Runs asynchronously — poll
        jobIsRendered in job status to know when it completes.

        Returns:
            CNC_RC_OK (0) on success, error code otherwise
        """
        try:
            result = self._dll.CncStartRenderGraph(
                c_int(0),  # outLines: 0 = don't push to graph FIFO
                c_int(0),  # contour: 0 = full render
            )
            logger.info("CncStartRenderGraph() returned %d", result)
            return result
        except Exception as e:
            logger.error("Failed to start render: %s", e)
            return -1

    def run_job(self) -> int:
        """Start (or resume) execution of the loaded job."""
        result = self._dll.CncRunOrResumeJob()
        logger.info("CncRunOrResumeJob() returned %d", result)
        return result

    # -- private helpers -----------------------------------------------------

    def _reset_if_powerup(self) -> None:
        """If CNC is stuck in Power-up state after (re)connect, reset to Ready."""
        state = self._dll.CncGetState()
        if state == 0:  # CNC_IE_POWERUP_STATE
            logger.info("CNC in Power-up state, sending CncReset to reach Ready...")
            try:
                rc = self._dll.CncReset()
                logger.info("CncReset() returned %d", rc)
            except Exception as e:
                logger.warning("CncReset failed: %s", e)

    def _load_dll(self) -> WinDLL:
        python_bits = struct.calcsize("P") * 8
        logger.info("Python %s, architecture %d-bit", sys.version, python_bits)

        try:
            dll = WinDLL(self._settings.dll_path)
            logger.info("CNC DLL loaded: %s", self._settings.dll_path)
            return dll
        except OSError as exc:
            if "193" in str(exc):
                logger.critical(
                    "DLL architecture mismatch — Python is %d-bit but DLL is 32-bit. "
                    "Install 32-bit Python to fix this.",
                    python_bits,
                )
            else:
                logger.critical("Failed to load DLL: %s", exc)
            sys.exit(1)

    def _configure_prototypes(self) -> None:
        logger.info("Checking available DLL functions...")

        for name, argtypes, restype in [
            ("CncConnectServer", [c_char_p], c_int),
            ("CncDisConnectServer", None, c_int),
            ("CncGetState", None, c_int),
            ("CncIsServerConnected", None, c_int),
            ("CncGetJobStatus", None, POINTER(CNC_JOB_STATUS)),
            ("CncSendToGUI", [c_int, c_int, c_int], c_int),
            ("CncSendUserMessage", [c_char_p, c_char_p, c_int, c_int, c_int, c_char_p], None),
            ("CncRunOrResumeJob", None, c_int),
            ("CncReset", None, c_int),
            ("CncSetExtraJobOptions", [c_char_p, c_int, c_uint], c_int),
            ("CncStartRenderGraph", [c_int, c_int], c_int),
        ]:
            try:
                func = getattr(self._dll, name)
                if argtypes is not None:
                    func.argtypes = argtypes
                func.restype = restype
                logger.info("%s found", name)
            except AttributeError:
                logger.warning("%s not found", name)

        # Search for LoadJob under several possible export names
        for candidate in [
            "CncLoadJobW",
            "CncLoadJobA",
            "CncLoadJob",
            "CncJobLoad",
            "LoadJob",
        ]:
            try:
                func = getattr(self._dll, candidate)
                func.argtypes = [c_wchar_p]
                func.restype = c_int
                self._load_job_func = func
                logger.info("%s found", candidate)
                break
            except AttributeError:
                pass

        if self._load_job_func is None:
            logger.warning("LoadJob function NOT FOUND in DLL")
