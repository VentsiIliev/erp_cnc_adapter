import glob
import os
from pydantic import BaseModel, Field
import logging
from pathlib import Path
import getpass

_logger = logging.getLogger(__name__)

class LoadJobRequest(BaseModel):
    job_number: str = Field(..., min_length=12, max_length=12, pattern=r"^\d{12}$")
    step: str = Field(..., pattern=r"^\d+$")
    base_dir: str = Field(default=r"\\192.168.2.11\Production\CNC\Mills")

    model_config = {"populate_by_name": True}

    @property
    def job_dir(self) -> str:
        """Construct the job directory path."""
        return os.path.join(self.base_dir, self.job_number)

    def find_nc_file(self) -> str:
        pattern_nc = os.path.join(self.job_dir, f"Setup_{self.step}*.nc")
        pattern_cnc = os.path.join(self.job_dir, f"Setup_{self.step}*.cnc")

        _logger.info(f"Running as Windows user: {getpass.getuser()}")
        _logger.info(f"Base dir: {self.base_dir}")
        _logger.info(f"Job number: {self.job_number}")
        _logger.info(f"Step: {self.step}")
        _logger.info(f"Job dir: {self.job_dir}")
        _logger.info(f"Finding NC file: {pattern_nc}")
        _logger.info(f"Finding CNC file: {pattern_cnc}")

        # Keep glob first so your existing tests/mocks still work
        matches = list(set(glob.glob(pattern_nc) + glob.glob(pattern_cnc)))

        if matches:
            _logger.info(f"Matching files from glob: {matches}")

            if len(matches) > 1:
                raise ValueError(
                    f"Multiple files found matching Setup_{self.step}*: {matches}"
                )

            return matches[0]

        # Real filesystem diagnostics if glob found nothing
        _logger.warning("glob found no matches. Checking directory manually.")

        if not os.path.isdir(self.job_dir):
            raise FileNotFoundError(
                f"Job directory does not exist or is not accessible: {self.job_dir}"
            )

        try:
            files = os.listdir(self.job_dir)
        except PermissionError as e:
            raise PermissionError(
                f"No permission to access job directory: {self.job_dir}"
            ) from e
        except OSError as e:
            raise OSError(
                f"Could not read job directory: {self.job_dir}. Error: {e}"
            ) from e

        _logger.info(f"Files found in job directory: {files}")

        prefix = f"setup_{self.step}".lower()

        matches = [
            os.path.join(self.job_dir, file_name)
            for file_name in files
            if file_name.lower().startswith(prefix)
               and file_name.lower().endswith((".nc", ".cnc"))
        ]

        _logger.info(f"Matching .nc/.cnc files from manual scan: {matches}")

        if not matches:
            raise FileNotFoundError(
                f"No .nc/.cnc file found matching Setup_{self.step}* "
                f"in {self.job_dir}. Files found: {files}"
            )

        if len(matches) > 1:
            raise ValueError(
                f"Multiple files found matching Setup_{self.step}*: {matches}"
            )

        return matches[0]
class JobStatusResponse(BaseModel):
    # Core status fields
    state: int
    stateText: str

    # Job identification
    jobName: str = ""
    jobLoadCounter: int = 0

    # Commented out - not currently used in API response
    # numLinesInJob: int = 0
    # numLinesInMacro: int = 0
    # numLinesInUserMacro: int = 0
    # numBytesInJob: int = 0
    # isLongJob: int = 0
    # isSuperLongJob: int = 0
    # jobIsRendered: int = 0

    # Progress and timing fields with explicit units
    totalJobLengthMm: float = 0.0              # Total toolpath length (millimeters)
    jobProgressMm: float = 0.0                 # Distance traveled (millimeters)
    jobActualRunningTimeSeconds: float = 0.0   # Elapsed time (seconds)
    jobRemainingRunningTimeSeconds: float = 0.0  # Estimated remaining (seconds)
    jobEstimatedTimeSeconds: float = 0.0       # Total estimated time (seconds)

    # Computed progress percentage (calculated by API layer)
    jobProgressPercentage: float = 0.0         # Completion percentage (always 0-100, clamped)

    # Commented out - collision and rendering fields
    # TCACollision: int = 0
    # MCACollision: int = 0
    # xCollision: int = 0
    # yCollision: int = 0
    # zCollision: int = 0
    # jobRenderLine: int = 0
    # jobRenderProgressPercentage: float = 0.0

    # Commented out - interpreter/executor position fields
    # curIpLine: int = 0
    # curIpLineText: str = ""
    # curExLine: int = 0
    # lastKnownExecutedLineNumber: int = 0
    # lastKnownToolChangeLineNumber: int = 0

    # Repeat mode fields (from CNC)
    doRepeatJob: int = 0             # Boolean: 1 = repeat enabled, 0 = disabled
    nrOfJobRepeatsSet: int = 0       # Total repeats configured (e.g., 3 means run 3 times)
    nrOfRepeatsActual: int = 0       # REMAINING repeats - countdown (decrements after each run)

    # Computed field (calculated by API layer for convenience)
    currentRepeat: int = 0           # Current iteration number (1-based, e.g., "on repeat 2 of 3")

    # Commented out - extra line and turning fields
    # extraLineWhenEndOfJob: str = ""
    # stockDiameterTurning: float = 0.0
    # stockLengthTurning: float = 0.0
    # stockZAtWorkOffset: int = 0



class LoadJobResponse(BaseModel):
    status: int
    message: str
    file_name: str = Field(alias="fileName")

    model_config = {"populate_by_name": True}


class RunJobResponse(BaseModel):
    status: int
    message: str

class JogCommandRequest(BaseModel):
    axis: str = Field(..., pattern=r"^[XYZABCxyzabc]$")
    direction: int = Field(..., ge=-1, le=1)
    step: float = Field(default=1.0, gt=0)
    velocity_factor: float = Field(default=0.25, ge=0.01, le=1.0)
    continuous: bool = False


class MoveCommandRequest(BaseModel):
    axis: str = Field(..., pattern=r"^[XYZABCxyzabc]$")
    position: float
    velocity_factor: float = Field(default=0.25, ge=0.01, le=1.0)


class ZeroAxisRequest(BaseModel):
    axis: str = Field(..., pattern=r"^[XYZABCxyzabc]$")


class SetWorkCoordinateRequest(BaseModel):
    axis: str = Field(..., pattern=r"^[XYZABCxyzabc]$")
    value: float


class AxisPosition(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    a: float = 0.0
    b: float = 0.0
    c: float = 0.0


class CncPositionResponse(BaseModel):
    status: int
    message: str
    work: AxisPosition = Field(default_factory=AxisPosition)
    machine: AxisPosition = Field(default_factory=AxisPosition)


class CncPhysicalButtonStatusResponse(BaseModel):
    status: int
    message: str
    run_input: bool = Field(alias="runInput")
    pause_input: bool = Field(alias="pauseInput")
    run_raw: int = Field(alias="runRaw")
    pause_raw: int = Field(alias="pauseRaw")
    run_logical: int = Field(default=0, alias="runLogical")
    pause_logical: int = Field(default=0, alias="pauseLogical")
    feed_hold_active: bool = Field(alias="feedHoldActive")
    safety_input_value: int = Field(alias="safetyInputValue")
    motion_enabled: bool = Field(alias="motionEnabled")

    model_config = {"populate_by_name": True}


class CncHomedResponse(BaseModel):
    status: int
    message: str
    all_axes_homed: bool = Field(alias="allAxesHomed")

    model_config = {"populate_by_name": True}


class CncMotionResponse(BaseModel):
    status: int
    message: str
    command: str
    dry_run: bool = Field(alias="dryRun")
    axis: str | None = None
    direction: int | None = None
    step: float | None = None
    position: float | None = None
    velocity_factor: float | None = Field(default=None, alias="velocityFactor")
    continuous: bool | None = None

    model_config = {"populate_by_name": True}
