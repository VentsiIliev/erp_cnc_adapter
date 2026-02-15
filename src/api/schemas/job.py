from pydantic import BaseModel, Field, field_validator


class LoadJobRequest(BaseModel):
    file_name: str = Field(..., alias="fileName", min_length=1)

    model_config = {"populate_by_name": True}

    @field_validator("file_name")
    @classmethod
    def normalize_slashes(cls, v: str) -> str:
        return v.replace("/", "\\")


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
