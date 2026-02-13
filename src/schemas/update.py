from pydantic import BaseModel


class BackupInfo(BaseModel):
    filename: str
    timestamp: str
    size_mb: float


class UpdateResponse(BaseModel):
    status: int
    message: str
    version_info: str = ""


class RollbackResponse(BaseModel):
    status: int
    message: str


class BackupListResponse(BaseModel):
    status: int
    message: str
    backups: list[BackupInfo] = []
