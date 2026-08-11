"""Closed configuration for the reviewed Fubon Neo TEST environment."""

from dataclasses import InitVar, dataclass, field
from hmac import compare_digest, digest
from secrets import token_bytes

from tw_stock_tool.broker_safety import BrokerEnvironment

from tw_stock_tool.broker_adapters.fubon_neo.errors import (
    FubonNeoErrorCode,
    FubonNeoReadError,
)


FUBON_NEO_BROKER_ID = "FUBON_NEO"
FUBON_NEO_TEST_ENDPOINT = "wss://neoapitest.fbs.com.tw/TASP/XCPXWS"
FUBON_NEO_MARKET = "TW_SECURITIES"
FUBON_NEO_CURRENCY = "TWD"
FUBON_NEO_SDK_VERSION = "2.2.8"
FUBON_NEO_SOURCE_VERSION = "fubon-neo-2.2.8-test-readonly-v1"


def _exact_text(name: str, value: object) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise FubonNeoReadError(
            FubonNeoErrorCode.PROVIDER_RESPONSE_MALFORMED,
            f"{name} must be an exact non-empty string",
        )
    return value


@dataclass(frozen=True, slots=True)
class FubonNeoTestConfig:
    """Runtime account binding with no selectable non-TEST environment."""

    environment: BrokerEnvironment
    endpoint: str
    account_reference: str
    expected_account: InitVar[str]
    expected_branch: InitVar[str]
    _match_key: bytes = field(init=False, repr=False, compare=False)
    _account_digest: bytes = field(init=False, repr=False, compare=False)
    _branch_digest: bytes = field(init=False, repr=False, compare=False)

    def __post_init__(self, expected_account: str, expected_branch: str) -> None:
        if (
            type(self.environment) is not BrokerEnvironment
            or self.environment is not BrokerEnvironment.SANDBOX
            or self.endpoint != FUBON_NEO_TEST_ENDPOINT
        ):
            raise FubonNeoReadError(
                FubonNeoErrorCode.ENVIRONMENT_NOT_TEST,
                "the reviewed Fubon Neo TEST environment is required",
            )
        _exact_text("account_reference", self.account_reference)
        _exact_text("expected_account", expected_account)
        _exact_text("expected_branch", expected_branch)
        key = token_bytes(32)
        object.__setattr__(self, "_match_key", key)
        object.__setattr__(
            self,
            "_account_digest",
            digest(key, expected_account.encode("utf-8"), "sha256"),
        )
        object.__setattr__(
            self,
            "_branch_digest",
            digest(key, expected_branch.encode("utf-8"), "sha256"),
        )

    def matches_provider_account(self, account: object, branch: object) -> bool:
        if type(account) is not str or type(branch) is not str:
            return False
        return compare_digest(
            digest(self._match_key, account.encode("utf-8"), "sha256"),
            self._account_digest,
        ) and compare_digest(
            digest(self._match_key, branch.encode("utf-8"), "sha256"),
            self._branch_digest,
        )


__all__ = [
    "FUBON_NEO_BROKER_ID",
    "FUBON_NEO_CURRENCY",
    "FUBON_NEO_MARKET",
    "FUBON_NEO_SDK_VERSION",
    "FUBON_NEO_SOURCE_VERSION",
    "FUBON_NEO_TEST_ENDPOINT",
    "FubonNeoTestConfig",
]
