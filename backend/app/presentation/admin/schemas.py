from pydantic import BaseModel

from app.application.admin.get_server_status import ServerStatusResult


class ServerStatusResponse(BaseModel):
    db_connected: bool
    redis_connected: bool
    active_users: int
    active_tenants: int
    online_now: int
    online_now_note: str = "только этот воркер, не вся платформа"

    @classmethod
    def from_result(cls, result: ServerStatusResult) -> "ServerStatusResponse":
        return cls(
            db_connected=result.db_connected,
            redis_connected=result.redis_connected,
            active_users=result.active_users,
            active_tenants=result.active_tenants,
            online_now=result.online_now,
        )


class ErrorLogEntryResponse(BaseModel):
    timestamp: str
    method: str
    path: str
    error_type: str
    message: str


class ErrorLogResponse(BaseModel):
    errors: list[ErrorLogEntryResponse]
