import glob
import os
from pydantic import BaseModel, Field


class LoadJobRequest(BaseModel):
    job_number: str = Field(..., min_length=12, max_length=12, pattern=r'^\d{12}$')
    step: str = Field(..., pattern=r'^\d+$')
    base_dir: str = Field(default=r"\\192.168.2.11\Production\CNC\Mills")

    model_config = {"populate_by_name": True}

    @property
    def job_dir(self) -> str:
        """Construct the job directory path."""
        return os.path.join(self.base_dir, self.job_number)

    def find_nc_file(self) -> str:
        """Find the .nc or .cnc file that starts with Setup_{step} in the job directory.

        Returns:
            Full path to the .nc or .cnc file

        Raises:
            FileNotFoundError: If no matching file is found
            ValueError: If multiple matching files are found
        """
        # Try both .nc and .cnc extensions, use set to deduplicate
        pattern_nc = os.path.join(self.job_dir, f"Setup_{self.step}*.nc")
        pattern_cnc = os.path.join(self.job_dir, f"Setup_{self.step}*.cnc")

        # Combine and deduplicate results
        matches = list(set(glob.glob(pattern_nc) + glob.glob(pattern_cnc)))

        if not matches:
            raise FileNotFoundError(
                f"No .nc/.cnc file found matching Setup_{self.step}*.nc or Setup_{self.step}*.cnc in {self.job_dir}"
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
