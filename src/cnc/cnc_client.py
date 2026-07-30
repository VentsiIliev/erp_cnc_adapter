import ctypes
import logging
import struct
import sys
import time
from ctypes import POINTER, WinDLL, byref, c_char_p, c_double, c_int, c_uint, c_void_p, c_wchar_p

from cncapi.python.cncstructs import CNC_CART_BOOL, CNC_CART_DOUBLE, CNC_CONTROLLER_STATUS, CNC_JOB_STATUS, CNC_LOG_MESSAGE, CNC_MOTION_STATUS, CNC_RUNNING_STATUS
from src.core.config import Settings

logger = logging.getLogger(__name__)

# CNC_RC_* return codes from cncenums.py
CNC_RC_OK = 0
CNC_RC_ALREADY_RUNS = 6
CNC_RC_ALREADY_CONNECTED = 7
CNC_RC_ERR_SERVER_NOT_RUNNING = 22
CNC_RC_ERR_NOT_CONNECTED = 24
CNC_IOID_RUN_IN = 31
CNC_IOID_PAUSE_IN = 32


class CncClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._connected = False
        self._load_job_func = None
        self._last_cnc_message = None
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
        elif result in (CNC_RC_ALREADY_RUNS, CNC_RC_ALREADY_CONNECTED):
            logger.info("CNC already running/connected (code %d)", result)
            self._connected = True
        elif result == CNC_RC_ERR_SERVER_NOT_RUNNING:
            logger.warning(
                "CNC server not running (code %d) - "
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

    def get_positions(self) -> dict:
        """Return current work and machine coordinates from the CNC DLL."""
        work = self._dll.CncGetWorkPosition()
        machine = self._dll.CncGetMachinePosition()
        return {
            "work": self._cart_to_dict(work),
            "machine": self._cart_to_dict(machine),
        }

    def get_physical_button_status(self) -> dict:
        """Return read-only physical run/pause input state for diagnostics."""
        run_logical = int(self._dll.CncGetInput(CNC_IOID_RUN_IN))
        pause_logical = int(self._dll.CncGetInput(CNC_IOID_PAUSE_IN))
        run_raw = int(self._dll.CncGetInputRaw(CNC_IOID_RUN_IN))
        pause_raw = int(self._dll.CncGetInputRaw(CNC_IOID_PAUSE_IN))
        return {
            # RUN appears to report the released/closed-circuit state on the tested setup.
            # Keep the API value as the DLL reports it; the jog pad indicator interprets transitions.
            "runInput": run_logical == 1,
            "pauseInput": pause_logical == 1,
            "runRaw": run_raw,
            "pauseRaw": pause_raw,
            "runLogical": run_logical,
            "pauseLogical": pause_logical,
        }

    def get_all_axes_homed(self) -> bool:
        """Return True when the CNC reports all axes are homed."""
        return self._dll.CncGetAllAxesHomed() == 1

    def is_motion_enabled(self) -> bool:
        """Return True when the controller reports motion/drives enabled."""
        status = self._dll.CncGetControllerStatus().contents
        return int(status.motionEnabled) == 1

    def get_last_cnc_message(self) -> str | None:
        """Return the last operator-facing CNC message captured from the DLL FIFO."""
        return getattr(self, "_last_cnc_message", None)

    def clear_cnc_messages(self) -> None:
        """Discard stale CNC FIFO messages before showing operator commands."""
        self._clear_cnc_messages()

    def poll_cnc_messages(self) -> list[str]:
        """Drain and return currently available operator-facing CNC FIFO messages."""
        return self._log_cnc_messages("from background message monitor")

    def home_all_axes_gui_sequence(self) -> int:
        """Request the Eding CNC GUI home sequence action."""
        CNC_UIOACTION_HOMESEQ = 37
        self._clear_cnc_messages()
        self._log_home_preflight()
        result = self._dll.CncSendToGUI(
            c_int(CNC_UIOACTION_HOMESEQ),
            c_int(0),
            c_int(0),
        )
        logger.info("CncSendToGUI(CNC_UIOACTION_HOMESEQ, 0, 0) returned %d", result)
        return result

    def home_all_axes_sequence(self) -> int:
        """Run the configured Eding CNC home_all macro without fallback."""
        command = "gosub home_all"
        self._clear_cnc_messages()
        self._log_home_preflight()
        result = self._dll.CncRunSingleLine(command.encode("ascii"))
        logger.info("CncRunSingleLine(%r) returned %d", command, result)
        if result != CNC_RC_OK:
            return result

        result = self._dll.CncWaitSingleLine(None, None)
        logger.info("CncWaitSingleLine() for %r returned %d", command, result)
        return result

    def _log_home_preflight(self) -> None:
        """Log CNC readiness details before attempting a home MDI command."""
        try:
            state = int(self._dll.CncGetState())
            state_text_raw = self._dll.CncGetStateText(c_int(state))
            if isinstance(state_text_raw, bytes):
                state_text = state_text_raw.decode("ascii", errors="replace")
            else:
                state_text = str(state_text_raw)
            logger.info("Home preflight: state=%s stateText=%s", state, state_text)
        except Exception as exc:
            logger.info("Home preflight: could not read CNC state: %s", exc)

        try:
            controller = self._dll.CncGetControllerStatus().contents
            logger.info(
                "Home preflight: motionEnabled=%s controllerErrorWord=%s",
                int(controller.motionEnabled),
                int(controller.errorWord),
            )
        except Exception as exc:
            logger.info("Home preflight: could not read controller status: %s", exc)

        try:
            motion = self._dll.CncGetMotionStatus().contents
            logger.info(
                "Home preflight: safeMode=%s safetyInputValue=%s feedHoldActive=%s",
                int(motion.safeMode),
                int(motion.safetyInputValue),
                int(motion.feedHoldActive),
            )
        except Exception as exc:
            logger.info("Home preflight: could not read motion status: %s", exc)

        try:
            start_allowed = c_int()
            rc = self._dll.CncCheckStartConditionOK(c_int(1), c_int(1), byref(start_allowed))
            logger.info(
                "Home preflight: CncCheckStartConditionOK(generateMessage=1, ignoreHoming=1) rc=%s startAllowed=%s",
                rc,
                start_allowed.value,
            )
        except Exception as exc:
            logger.info("Home preflight: could not check start condition: %s", exc)


    def _clear_cnc_messages(self) -> None:
        """Discard stale CNC FIFO messages before issuing a command we may report on."""
        self._last_cnc_message = None
        self._captured_cnc_messages = []
        try:
            for _ in range(20):
                message = CNC_LOG_MESSAGE()
                rc = self._dll.CncLogFifoGet(byref(message))
                if rc != CNC_RC_OK:
                    break
        except Exception as exc:
            logger.debug("Could not clear CNC log FIFO: %s", exc)

    def _wait_for_cnc_messages(
        self,
        context: str,
        timeout_seconds: float = 1.5,
        quiet_seconds: float = 0.25,
    ) -> bool:
        """Wait until CNC FIFO text stops arriving briefly after a command."""
        deadline = time.monotonic() + timeout_seconds
        quiet_deadline = None
        captured_any = False
        while True:
            if self._log_cnc_messages(context):
                captured_any = True
                quiet_deadline = time.monotonic() + quiet_seconds

            now = time.monotonic()
            if captured_any and quiet_deadline is not None and now >= quiet_deadline:
                return True
            if now >= deadline:
                return captured_any
            time.sleep(0.05)

    def _log_cnc_messages(self, context: str) -> list[str]:
        """Drain a few CNC server log FIFO messages for diagnostics."""
        captured_this_call: list[str] = []
        try:
            for _ in range(10):
                message = CNC_LOG_MESSAGE()
                rc = self._dll.CncLogFifoGet(byref(message))
                if rc != CNC_RC_OK:
                    break
                text = bytes(message.text).split(b"\0", 1)[0].decode("ascii", errors="replace").strip()
                if text:
                    captured_messages = getattr(self, "_captured_cnc_messages", [])
                    if not captured_messages or captured_messages[-1] != text:
                        captured_messages.append(text)
                    self._captured_cnc_messages = captured_messages
                    self._last_cnc_message = " | ".join(captured_messages)
                    captured_this_call.append(text)
                function_name = bytes(message.functionName).split(b"\0", 1)[0].decode("ascii", errors="replace")
                source_info = bytes(message.sourceInfo).split(b"\0", 1)[0].decode("ascii", errors="replace")
                logger.info(
                    "CNC log FIFO %s: code=%s errorClass=%s subCode=%s text=%r function=%r source=%r",
                    context,
                    int(message.code),
                    int(message.errorClass),
                    int(message.subCode),
                    text,
                    function_name,
                    source_info,
                )
        except Exception as exc:
            logger.info("CNC log FIFO %s: could not read messages: %s", context, exc)
        return captured_this_call

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
        and other fields in CNC_JOB_STATUS. Runs asynchronously - poll
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

    def pause_job(self) -> int:
        """Smooth-stop the current job using the CNC DLL pause function."""
        result = self._dll.CncPauseJob()
        logger.info("CncPauseJob() returned %d", result)
        return result

    def reset(self) -> int:
        """Recover the CNC from error states using the DLL reset function."""
        self._clear_cnc_messages()
        result = self._dll.CncReset()
        logger.info("CncReset() returned %d", result)
        return result

    def start_jog(
        self,
        axis: str,
        direction: int,
        step: float,
        velocity_factor: float,
        continuous: bool,
    ) -> int:
        """Start a continuous or fixed-step jog for one axis."""
        axis_index = self._axis_index(axis)
        signed_step = float(step) * (1 if direction >= 0 else -1)
        self._clear_cnc_messages()
        result = self._dll.CncStartJog2(
            c_int(axis_index),
            c_double(signed_step),
            c_double(float(velocity_factor)),
            c_int(1 if continuous else 0),
        )
        logger.info(
            "CncStartJog2(axis=%s/%d, step=%s, velocity_factor=%s, continuous=%s) returned %d",
            axis.upper(),
            axis_index,
            signed_step,
            velocity_factor,
            continuous,
            result,
        )
        return result

    def stop_jog(self, axis: str | None = None) -> int:
        """Stop jogging for one axis, or all cartesian axes when axis is omitted."""
        self._clear_cnc_messages()
        if axis:
            axis_index = self._axis_index(axis)
            result = self._dll.CncStopJog(c_int(axis_index))
            logger.info("CncStopJog(axis=%s/%d) returned %d", axis.upper(), axis_index, result)
            return result

        result = CNC_RC_OK
        for axis_name in "XYZABC":
            axis_index = self._axis_index(axis_name)
            axis_result = self._dll.CncStopJog(c_int(axis_index))
            logger.info("CncStopJog(axis=%s/%d) returned %d", axis_name, axis_index, axis_result)
            if axis_result != CNC_RC_OK and result == CNC_RC_OK:
                result = axis_result
        return result

    def move_to(self, axis: str, position: float, velocity_factor: float) -> int:
        """Move one axis to an absolute machine position."""
        axis_name = axis.lower()
        self._axis_index(axis_name)

        pos = CNC_CART_DOUBLE()
        move = CNC_CART_BOOL()
        setattr(pos, axis_name, float(position))
        setattr(move, axis_name, 1)

        self._clear_cnc_messages()
        result = self._dll.CncMoveTo(pos, move, c_double(float(velocity_factor)))
        logger.info(
            "CncMoveTo(axis=%s, position=%s, velocity_factor=%s) returned %d",
            axis.upper(),
            position,
            velocity_factor,
            result,
        )
        return result

    def zero_work_axis(self, axis: str) -> int:
        """Set the current position as work zero for one axis without using the GUI."""
        axis_name = axis.upper()
        self._axis_index(axis_name)
        coordinate_system = self._active_coordinate_system_number()
        command = f"G10 L20 P{coordinate_system} {axis_name}0"

        self._clear_cnc_messages()
        result = self._dll.CncRunSingleLine(command.encode("ascii"))
        logger.info("CncRunSingleLine(%r) returned %d", command, result)
        if result != CNC_RC_OK:
            return result

        result = self._dll.CncWaitSingleLine(None, None)
        logger.info("CncWaitSingleLine() returned %d", result)
        if result != CNC_RC_OK:
            return result

        result = self._dll.CncStoreIniFile(c_int(1))
        logger.info("CncStoreIniFile(saveFixtures=1) returned %d", result)
        return result

    def set_work_coordinate(self, axis: str, value: float) -> int:
        """Set the displayed work coordinate for one axis using G92."""
        axis_name = axis.upper()
        self._axis_index(axis_name)
        command = f"G92 {axis_name}{float(value):g}"

        self._clear_cnc_messages()
        result = self._dll.CncRunSingleLine(command.encode("ascii"))
        logger.info("CncRunSingleLine(%r) returned %d", command, result)
        if result != CNC_RC_OK:
            return result

        result = self._dll.CncWaitSingleLine(None, None)
        logger.info("CncWaitSingleLine() returned %d", result)
        if result != CNC_RC_OK:
            return result

        result = self._dll.CncStoreIniFile(c_int(1))
        logger.info("CncStoreIniFile(saveFixtures=1) returned %d", result)
        return result

    # -- private helpers -----------------------------------------------------

    @staticmethod
    def _cart_to_dict(position: CNC_CART_DOUBLE) -> dict[str, float]:
        return {
            "x": float(position.x),
            "y": float(position.y),
            "z": float(position.z),
            "a": float(position.a),
            "b": float(position.b),
            "c": float(position.c),
        }

    def _active_coordinate_system_number(self) -> int:
        """Return G10 P number for the active G54-G59.3 coordinate system."""
        try:
            status = self._dll.CncGetRunningStatus().contents
            current_g5x = int(status.activeOffsetAndPlane.currentG5X)
        except Exception as exc:
            logger.warning("Could not read active G5X coordinate system, using G54/P1: %s", exc)
            return 1

        if 0 <= current_g5x <= 8:
            return current_g5x + 1

        logger.warning("Unexpected active G5X index %s, using G54/P1", current_g5x)
        return 1

    @staticmethod
    def _axis_index(axis: str) -> int:
        axis_map = {"X": 0, "Y": 1, "Z": 2, "A": 3, "B": 4, "C": 5}
        axis_name = axis.upper()
        if axis_name not in axis_map:
            raise ValueError(f"Unsupported CNC axis: {axis}")
        return axis_map[axis_name]

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
                message = (
                    f"DLL architecture mismatch for '{self._settings.dll_path}'. "
                    f"Python is {python_bits}-bit and the CNC DLL is incompatible."
                )
                logger.critical(
                    "DLL architecture mismatch - Python is %d-bit but DLL is 32-bit. "
                    "Install 32-bit Python to fix this.",
                    python_bits,
                )
            else:
                message = f"Failed to load CNC DLL '{self._settings.dll_path}': {exc}"
                logger.critical("Failed to load DLL: %s", exc)
            raise RuntimeError(message) from exc

    def _configure_prototypes(self) -> None:
        logger.info("Checking available DLL functions...")

        for name, argtypes, restype in [
            ("CncConnectServer", [c_char_p], c_int),
            ("CncDisConnectServer", None, c_int),
            ("CncGetState", None, c_int),
            ("CncGetStateText", [c_int], c_char_p),
            ("CncIsServerConnected", None, c_int),
            ("CncGetJobStatus", None, POINTER(CNC_JOB_STATUS)),
            ("CncGetWorkPosition", None, CNC_CART_DOUBLE),
            ("CncGetMachinePosition", None, CNC_CART_DOUBLE),
            ("CncGetAllAxesHomed", None, c_int),
            ("CncGetRunningStatus", None, POINTER(CNC_RUNNING_STATUS)),
            ("CncGetMotionStatus", None, POINTER(CNC_MOTION_STATUS)),
            ("CncGetControllerStatus", None, POINTER(CNC_CONTROLLER_STATUS)),
            ("CncGetInput", [c_int], c_int),
            ("CncGetInputRaw", [c_int], c_int),
            ("CncRunSingleLine", [c_char_p], c_int),
            ("CncWaitSingleLine", [c_void_p, c_void_p], c_int),
            ("CncStoreIniFile", [c_int], c_int),
            ("CncSendToGUI", [c_int, c_int, c_int], c_int),
            ("CncSendUserMessage", [c_char_p, c_char_p, c_int, c_int, c_int, c_char_p], None),
            ("CncRunOrResumeJob", None, c_int),
            ("CncPauseJob", None, c_int),
            ("CncReset", None, c_int),
            ("CncSetExtraJobOptions", [c_char_p, c_int, c_uint], c_int),
            ("CncCheckStartConditionOK", [c_int, c_int, POINTER(c_int)], c_int),
            ("CncLogFifoGet", [POINTER(CNC_LOG_MESSAGE)], c_int),
            ("CncStartRenderGraph", [c_int, c_int], c_int),
            ("CncStartJog2", [c_int, c_double, c_double, c_int], c_int),
            ("CncStopJog", [c_int], c_int),
            ("CncMoveTo", [CNC_CART_DOUBLE, CNC_CART_BOOL, c_double], c_int),
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
