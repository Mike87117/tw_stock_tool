"""Typed, sanitized failures for the Fubon Neo read boundary."""

from enum import StrEnum


class FubonNeoErrorCode(StrEnum):
    ENVIRONMENT_NOT_TEST = "ENVIRONMENT_NOT_TEST"
    OPTIONAL_DEPENDENCY_MISSING = "OPTIONAL_DEPENDENCY_MISSING"
    ACCOUNT_IDENTITY_MISMATCH = "ACCOUNT_IDENTITY_MISMATCH"
    PROVIDER_RESPONSE_MALFORMED = "PROVIDER_RESPONSE_MALFORMED"
    PROVIDER_READ_FAILED = "PROVIDER_READ_FAILED"
    PROVIDER_STATUS_UNKNOWN = "PROVIDER_STATUS_UNKNOWN"
    UNSUPPORTED_PROVIDER_RECORD = "UNSUPPORTED_PROVIDER_RECORD"
    AMBIGUOUS_PROVIDER_RECORDS = "AMBIGUOUS_PROVIDER_RECORDS"
    MANDATORY_ACCOUNT_FIELD_UNAVAILABLE = "MANDATORY_ACCOUNT_FIELD_UNAVAILABLE"


class FubonNeoReadError(RuntimeError):
    """A provider failure whose text never includes raw provider values."""

    def __init__(self, code: FubonNeoErrorCode, message: str) -> None:
        if type(code) is not FubonNeoErrorCode:
            raise TypeError("code must be an exact FubonNeoErrorCode")
        self.code = code
        super().__init__(f"{code.value}: {message}")


__all__ = ["FubonNeoErrorCode", "FubonNeoReadError"]
