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


class UpdateCheckResponse(BaseModel):
    status: int
    message: str
    current_version: str
    latest_version: str = ""
    update_available: bool = False
    package_url: str = ""
    manifest_url: str = ""
