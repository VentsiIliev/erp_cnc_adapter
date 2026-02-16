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
        """Find the .nc file that starts with Setup_{step} in the job directory.

        Returns:
            Full path to the .nc file

        Raises:
            FileNotFoundError: If no matching file is found
            ValueError: If multiple matching files are found
        """
        pattern = os.path.join(self.job_dir, f"Setup_{self.step}*.nc")
        matches = glob.glob(pattern)

        if not matches:
            raise FileNotFoundError(
                f"No .nc file found matching Setup_{self.step}*.nc in {self.job_dir}"
            )

        if len(matches) > 1:
            raise ValueError(
                f"Multiple .nc files found matching Setup_{self.step}*.nc: {matches}"
            )

        return matches[0]


class JobStatusResponse(BaseModel):
    state: int
    stateText: str
    jobName: str = ""
    jobLoadCounter: int = 0
    numLinesInJob: int = 0
    numLinesInMacro: int = 0
    numLinesInUserMacro: int = 0
    isLongJob: int = 0
    isSuperLongJob: int = 0
    jobIsRendered: int = 0
    totalJobLength: float = 0.0
    jobProgress: float = 0.0
    jobActualRunningTime: float = 0.0
    jobRemainingRunningTime: float = 0.0
    jobEstimatedTime: float = 0.0
    TCACollision: int = 0
    MCACollision: int = 0
    xCollision: int = 0
    yCollision: int = 0
    zCollision: int = 0
    jobRenderLine: int = 0
    jobRenderProgressPercentage: float = 0.0
    curIpLine: int = 0
    curExLine: int = 0
    lastKnownExecutedLineNumber: int = 0
    lastKnownToolChangeLineNumber: int = 0
    doRepeatJob: int = 0
    nrOfJobRepeatsSet: int = 0
    nrOfRepeatsActual: int = 0
    extraLineWhenEndOfJob: str = ""
    stockDiameterTurning: float = 0.0
    stockLengthTurning: float = 0.0
    stockZAtWorkOffset: int = 0


class LoadJobResponse(BaseModel):
    status: int
    message: str
    file_name: str = Field(alias="fileName")

    model_config = {"populate_by_name": True}


class RunJobResponse(BaseModel):
    status: int
    message: str
