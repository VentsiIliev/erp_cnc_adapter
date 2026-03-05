"""Job Monitor - Tracks running jobs and detects completion."""

import asyncio
import logging
from typing import Optional, Callable
import httpx

from src.cnc.cnc_client_protocol import CncClientProtocol

logger = logging.getLogger(__name__)


# CNC_IE_* interpreter execution states
STATE_RUNNING_JOB = 6
STATE_READY = 2
STATE_IDLE = 1
STATE_ABORTED = 5
STATE_EXECUTION_ERROR = 3
STATE_PAUSED_JOB = 12


class JobMonitor:
    """Monitor job execution and detect when a job completes."""

    def __init__(
        self,
        cnc_client: CncClientProtocol,
        poll_interval: float = 1.0,
        on_job_finished: Optional[Callable[[dict], None]] = None,
        report_url: Optional[str] = None,
    ):
        """
        Initialize the job monitor.

        Args:
            cnc_client: CNC client instance to query status
            poll_interval: How often to check status (seconds)
            on_job_finished: Optional callback when job finishes (receives job info dict)
            report_url: Optional URL to report job completion (e.g., http://pl.skycode.com/actions/cnc_job_done.php)
        """
        self._client = cnc_client
        self._poll_interval = poll_interval
        self._on_job_finished = on_job_finished
        self._report_url = report_url
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._was_running = False
        self._current_job_name = ""
        self._job_info = {}  # Stores job_number, step, machine_number
        self._last_report_status = None  # Stores last report result: {"success": bool, "timestamp": str, "error": str}

    @property
    def is_monitoring(self) -> bool:
        """Check if monitor is currently running."""
        return self._monitoring

    def set_job_info(self, job_number: str, step: str, machine_number: str) -> None:
        """
        Set job identification info to be displayed when job finishes.

        Args:
            job_number: 12-digit job number
            step: Step number
            machine_number: Machine identifier (e.g., CNC1)
        """
        self._job_info = {
            "job_number": job_number,
            "step": step,
            "machine_number": machine_number,
        }
        logger.debug("Job info set: Machine=%s, Job=%s, Step=%s", machine_number, job_number, step)

    async def start_monitoring(self) -> None:
        """Start monitoring job status."""
        if self._monitoring:
            logger.warning("Job monitor already running")
            return

        logger.info("Starting job monitor (poll interval: %.1fs)", self._poll_interval)
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop_monitoring(self) -> None:
        """Stop monitoring job status."""
        if not self._monitoring:
            return

        logger.info("Stopping job monitor")
        self._monitoring = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None

        self._reset_state()

    def _reset_state(self) -> None:
        """Reset monitoring state."""
        self._was_running = False
        self._current_job_name = ""

    def _log_job_started(self, job_name: str, job_status: dict) -> None:
        """
        Log job start event.

        Override this method to customize how job start is logged or reported.

        Args:
            job_name: Name of the job file
            job_status: Complete job status dictionary at start
        """
        logger.info("Job started: %s", job_name)

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        try:
            while self._monitoring:
                try:
                    await self._check_status()
                except Exception as e:
                    logger.error("Error checking job status: %s", e)

                await asyncio.sleep(self._poll_interval)
        except asyncio.CancelledError:
            logger.debug("Job monitor loop cancelled")
            raise

    async def _check_status(self) -> None:
        """Check current job status and detect completion."""
        try:
            # Get current state
            state = self._client.get_state()
            job_status = self._client.get_job_status()

            job_name = job_status.get("jobName", "")
            do_repeat = job_status.get("doRepeatJob", 0)
            repeats_set = job_status.get("nrOfJobRepeatsSet", 0)
            repeats_actual = job_status.get("nrOfRepeatsActual", 0)

            self._current_job_name = job_name

            # Detect job running
            if state == STATE_RUNNING_JOB:
                if not self._was_running:
                    self._log_job_started(job_name, job_status)
                    self._was_running = True
                else:
                    # Log progress periodically
                    progress_pct = job_status.get("jobProgressPercentage", 0.0)
                    logger.debug("Job running: %.1f%% complete", progress_pct)

            # Detect job completion
            elif self._was_running and state in (STATE_READY, STATE_IDLE):
                # Job transitioned from running to ready/idle
                # Check if this is truly finished or if repeat is pending
                if do_repeat and repeats_actual > 0:
                    # Still repeating
                    current_repeat = repeats_set - repeats_actual + 1
                    logger.info("Job repeat %d of %d completed, continuing...",
                               current_repeat - 1, repeats_set)
                else:
                    # Job truly finished (no more repeats)
                    await self._handle_job_finished(state, job_status)
                    self._was_running = False

            # Detect job aborted or error
            elif self._was_running and state in (STATE_ABORTED, STATE_EXECUTION_ERROR):
                state_text = "ABORTED" if state == STATE_ABORTED else "ERROR"
                logger.warning("Job %s: %s", state_text, job_name)
                await self._handle_job_finished(state, job_status, failed=True)
                self._was_running = False


        except Exception as e:
            logger.error("Error in _check_status: %s", e)

    async def _handle_job_finished(
        self,
        state: int,
        job_status: dict,
        failed: bool = False
    ) -> None:
        """Handle job completion."""
        # Log the job completion
        self._log_job_finished(state, job_status, failed)

        # Send job done report if URL is configured and job succeeded
        if not failed and self._report_url and self._job_info:
            await self._send_job_done_report()

        # Call user callback if provided
        if self._on_job_finished:
            try:
                if asyncio.iscoroutinefunction(self._on_job_finished):
                    await self._on_job_finished(job_status)
                else:
                    self._on_job_finished(job_status)
            except Exception as e:
                logger.error("Error in job finished callback: %s", e)

    async def _send_job_done_report(self) -> None:
        """
        Send job completion report to configured URL.

        Sends GET request with parameters:
        - m: machine number (e.g., cnc1)
        - c: job number (12 digits)
        - s: step number

        Example: /actions/cnc_job_done.php?m=cnc1&c=000000000000&s=1
        """
        from datetime import datetime

        try:
            machine = self._job_info.get("machine_number", "").lower()
            job_number = self._job_info.get("job_number", "")
            step = self._job_info.get("step", "")

            if not all([machine, job_number, step]):
                error_msg = f"Incomplete job info: machine={machine}, job={job_number}, step={step}"
                logger.warning(error_msg)
                self._last_report_status = {
                    "success": False,
                    "timestamp": datetime.now().isoformat(),
                    "error": error_msg,
                    "url": self._report_url,
                }
                return

            # Build URL with parameters
            params = {
                "m": machine,
                "c": job_number,
                "s": step,
            }

            logger.info("Sending job done report: %s?m=%s&c=%s&s=%s",
                       self._report_url, machine, job_number, step)

            # Send HTTP GET request with timeout and follow redirects (for HTTP -> HTTPS)
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(self._report_url, params=params)

                if response.status_code == 200:
                    logger.info("✓ Job done report sent successfully (status: %d)", response.status_code)
                    self._last_report_status = {
                        "success": True,
                        "timestamp": datetime.now().isoformat(),
                        "status_code": response.status_code,
                        "url": self._report_url,
                        "machine": machine,
                        "job_number": job_number,
                        "step": step,
                    }
                else:
                    error_msg = f"HTTP {response.status_code}"
                    logger.warning("Job done report returned status: %d", response.status_code)
                    self._last_report_status = {
                        "success": False,
                        "timestamp": datetime.now().isoformat(),
                        "error": error_msg,
                        "status_code": response.status_code,
                        "url": self._report_url,
                    }

        except httpx.TimeoutException:
            error_msg = "Timeout sending request"
            logger.error("Timeout sending job done report to %s", self._report_url)
            self._last_report_status = {
                "success": False,
                "timestamp": datetime.now().isoformat(),
                "error": error_msg,
                "url": self._report_url,
            }
        except httpx.RequestError as e:
            error_msg = str(e)
            logger.error("Error sending job done report: %s", e)
            self._last_report_status = {
                "success": False,
                "timestamp": datetime.now().isoformat(),
                "error": error_msg,
                "url": self._report_url,
            }
        except Exception as e:
            error_msg = str(e)
            logger.error("Unexpected error sending job done report: %s", e)
            self._last_report_status = {
                "success": False,
                "timestamp": datetime.now().isoformat(),
                "error": error_msg,
                "url": self._report_url,
            }

    def _log_job_finished(
        self,
        state: int,
        job_status: dict,
        failed: bool = False
    ) -> None:
        """
        Log job completion details.

        Override this method to customize how job completion is logged or reported.

        Args:
            state: CNC state code
            job_status: Complete job status dictionary
            failed: True if job failed/aborted, False if completed successfully
        """
        job_name = job_status.get("jobName", "")
        actual_time = job_status.get("jobActualRunningTimeSeconds", 0.0)
        estimated_time = job_status.get("jobEstimatedTimeSeconds", 0.0)
        do_repeat = job_status.get("doRepeatJob", 0)
        repeats_set = job_status.get("nrOfJobRepeatsSet", 0)

        if failed:
            state_text = "FAILED" if state == STATE_EXECUTION_ERROR else "ABORTED"
            logger.error("═" * 80)
            logger.error("JOB %s: %s", state_text, job_name)
            if self._job_info:
                logger.error("Machine: %s | Job: %s | Step: %s",
                           self._job_info.get("machine_number", "N/A"),
                           self._job_info.get("job_number", "N/A"),
                           self._job_info.get("step", "N/A"))
            logger.error("═" * 80)
        else:
            logger.info("═" * 80)
            logger.info("JOB FINISHED: %s", job_name)
            if self._job_info:
                logger.info("Machine: %s | Job: %s | Step: %s",
                           self._job_info.get("machine_number", "N/A"),
                           self._job_info.get("job_number", "N/A"),
                           self._job_info.get("step", "N/A"))
            logger.info("═" * 80)
            logger.info("Actual run time: %.2f seconds", actual_time)
            logger.info("Estimated time: %.2f seconds", estimated_time)

            if do_repeat and repeats_set > 1:
                logger.info("Total repeats: %d times", repeats_set)

            time_diff = actual_time - estimated_time
            if abs(time_diff) > 1.0:
                logger.info("Time difference: %.2f seconds (%+.1f%%)",
                           time_diff,
                           (time_diff / estimated_time * 100) if estimated_time > 0 else 0)


    def get_current_status(self) -> dict:
        """Get current monitoring status."""
        return {
            "monitoring": self._monitoring,
            "was_running": self._was_running,
            "current_job": self._current_job_name,
            "job_info": self._job_info,
            "last_report_status": self._last_report_status,
        }

