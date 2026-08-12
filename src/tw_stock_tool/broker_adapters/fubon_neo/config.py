"""Closed configuration for the reviewed Fubon Neo TEST environment."""

from collections.abc import Mapping
from dataclasses import InitVar, dataclass, field
from enum import StrEnum
from hashlib import sha256
from hmac import compare_digest, digest
import json
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
FUBON_NEO_CATALOG_SCHEMA_VERSION = "twse-tpex-security-identity-projection-v1"
FUBON_NEO_CATALOG_SOURCE_VERSION = "sanitized-recorded-2025-01-02-v1"
FUBON_NEO_TWSE_CATALOG_ENDPOINT = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
FUBON_NEO_TPEX_CATALOG_ENDPOINT = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
FUBON_NEO_CATALOG_EVIDENCE_SHA256 = "833b4f4fb5bb415f4958bae8238ff9366fdacde8a5cd41a90bc657947c313041"
FUBON_NEO_CATALOG_MEMBERSHIP_SHA256 = "d830211790360006b7c01f9e88698d459296ad342666d5afb7e0eaddb5304713"
_CATALOG_AUTHORITY = object()


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
        if type(self.environment) is not BrokerEnvironment or self.environment is not BrokerEnvironment.SANDBOX or self.endpoint != FUBON_NEO_TEST_ENDPOINT:
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


@dataclass(frozen=True, slots=True)
class FubonNeoReadConnectionIdentity:
    """Immutable provenance asserted by the provider session wrapper."""

    broker_id: str
    environment: BrokerEnvironment
    endpoint: str
    sdk_version: str
    provider_contract_version: str
    product_scope: str


FUBON_NEO_TEST_CONNECTION_IDENTITY = FubonNeoReadConnectionIdentity(
    broker_id=FUBON_NEO_BROKER_ID,
    environment=BrokerEnvironment.SANDBOX,
    endpoint=FUBON_NEO_TEST_ENDPOINT,
    sdk_version=FUBON_NEO_SDK_VERSION,
    provider_contract_version=FUBON_NEO_SOURCE_VERSION,
    product_scope=FUBON_NEO_MARKET,
)


class FubonNeoInstrumentMarket(StrEnum):
    TAIEX = "TAIEX"
    TAISDAQ = "TAISDAQ"


@dataclass(frozen=True, slots=True)
class FubonNeoInstrumentCatalog:
    """Immutable classification built only from the reviewed catalog evidence."""

    source_version: str
    evidence_sha256: str
    membership_sha256: str
    taiex_symbols: tuple[str, ...]
    taisdaq_symbols: tuple[str, ...]
    _authority: InitVar[object]

    def __post_init__(self, _authority: object) -> None:
        if _authority is not _CATALOG_AUTHORITY:
            raise FubonNeoReadError(
                FubonNeoErrorCode.INSTRUMENT_CLASSIFICATION_UNTRUSTED,
                "instrument catalogs must be built from reviewed evidence",
            )
        if self.source_version != FUBON_NEO_CATALOG_SOURCE_VERSION or self.evidence_sha256 != FUBON_NEO_CATALOG_EVIDENCE_SHA256 or self.membership_sha256 != FUBON_NEO_CATALOG_MEMBERSHIP_SHA256:
            raise FubonNeoReadError(
                FubonNeoErrorCode.INSTRUMENT_CLASSIFICATION_UNTRUSTED,
                "instrument catalog provenance does not match the reviewed evidence",
            )
        if type(self.taiex_symbols) is not tuple or type(self.taisdaq_symbols) is not tuple:
            raise FubonNeoReadError(
                FubonNeoErrorCode.INSTRUMENT_CLASSIFICATION_UNTRUSTED,
                "instrument classifications must be immutable tuples",
            )
        all_symbols = self.taiex_symbols + self.taisdaq_symbols
        if self.taiex_symbols != tuple(sorted(self.taiex_symbols)) or self.taisdaq_symbols != tuple(sorted(self.taisdaq_symbols)):
            raise FubonNeoReadError(
                FubonNeoErrorCode.INSTRUMENT_CLASSIFICATION_UNTRUSTED,
                "instrument classifications must be canonically ordered",
            )
        if any(type(symbol) is not str or len(symbol) != 4 or not symbol.isascii() or not symbol.isdigit() for symbol in all_symbols) or len(set(all_symbols)) != len(all_symbols):
            raise FubonNeoReadError(
                FubonNeoErrorCode.INSTRUMENT_CLASSIFICATION_UNTRUSTED,
                "instrument classifications are malformed or ambiguous",
            )
        membership = {"TAIEX": list(self.taiex_symbols), "TAISDAQ": list(self.taisdaq_symbols)}
        if _catalog_digest(membership) != self.membership_sha256:
            raise FubonNeoReadError(
                FubonNeoErrorCode.INSTRUMENT_CLASSIFICATION_UNTRUSTED,
                "instrument catalog membership does not match its reviewed digest",
            )

    def market_for(self, broker_symbol: str) -> FubonNeoInstrumentMarket | None:
        if broker_symbol in self.taiex_symbols:
            return FubonNeoInstrumentMarket.TAIEX
        if broker_symbol in self.taisdaq_symbols:
            return FubonNeoInstrumentMarket.TAISDAQ
        return None


def _catalog_digest(value: object) -> str:
    try:
        canonical = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise FubonNeoReadError(
            FubonNeoErrorCode.INSTRUMENT_CLASSIFICATION_UNTRUSTED,
            "instrument catalog evidence is not canonical JSON",
        ) from exc
    return sha256(canonical).hexdigest()


def _catalog_symbols(
    records: object,
    *,
    code_field: str,
    name_field: str,
) -> tuple[str, ...]:
    if type(records) is not list:
        raise FubonNeoReadError(
            FubonNeoErrorCode.INSTRUMENT_CLASSIFICATION_UNTRUSTED,
            "instrument catalog records must be an official-shaped list",
        )
    symbols: list[str] = []
    for record in records:
        if type(record) is not dict or set(record) != {code_field, name_field}:
            raise FubonNeoReadError(
                FubonNeoErrorCode.INSTRUMENT_CLASSIFICATION_UNTRUSTED,
                "instrument catalog records do not match the reviewed projection",
            )
        symbol = record[code_field]
        name = record[name_field]
        if type(symbol) is not str or len(symbol) != 4 or not symbol.isascii() or not symbol.isdigit() or type(name) is not str or not name.strip() or name != name.strip():
            raise FubonNeoReadError(
                FubonNeoErrorCode.INSTRUMENT_CLASSIFICATION_UNTRUSTED,
                "instrument catalog record identity is malformed",
            )
        symbols.append(symbol)
    return tuple(sorted(symbols))


def build_reviewed_instrument_catalog(
    evidence: Mapping[str, object],
) -> FubonNeoInstrumentCatalog:
    """Verify retained official-shaped evidence and build its closed catalog."""

    if type(evidence) is not dict or _catalog_digest(evidence) != FUBON_NEO_CATALOG_EVIDENCE_SHA256:
        raise FubonNeoReadError(
            FubonNeoErrorCode.INSTRUMENT_CLASSIFICATION_UNTRUSTED,
            "instrument catalog evidence does not match the reviewed digest",
        )
    expected_keys = {
        "schema_version",
        "source_version",
        "twse_endpoint",
        "tpex_endpoint",
        "twse",
        "tpex",
    }
    if (
        set(evidence) != expected_keys
        or evidence["schema_version"] != FUBON_NEO_CATALOG_SCHEMA_VERSION
        or evidence["source_version"] != FUBON_NEO_CATALOG_SOURCE_VERSION
        or evidence["twse_endpoint"] != FUBON_NEO_TWSE_CATALOG_ENDPOINT
        or evidence["tpex_endpoint"] != FUBON_NEO_TPEX_CATALOG_ENDPOINT
    ):
        raise FubonNeoReadError(
            FubonNeoErrorCode.INSTRUMENT_CLASSIFICATION_UNTRUSTED,
            "instrument catalog evidence provenance is not reviewed",
        )
    taiex_symbols = _catalog_symbols(
        evidence["twse"],
        code_field="Code",
        name_field="Name",
    )
    taisdaq_symbols = _catalog_symbols(
        evidence["tpex"],
        code_field="SecuritiesCompanyCode",
        name_field="CompanyName",
    )
    membership = {"TAIEX": list(taiex_symbols), "TAISDAQ": list(taisdaq_symbols)}
    membership_sha256 = _catalog_digest(membership)
    if membership_sha256 != FUBON_NEO_CATALOG_MEMBERSHIP_SHA256:
        raise FubonNeoReadError(
            FubonNeoErrorCode.INSTRUMENT_CLASSIFICATION_UNTRUSTED,
            "instrument catalog membership does not match the reviewed digest",
        )
    return FubonNeoInstrumentCatalog(
        source_version=FUBON_NEO_CATALOG_SOURCE_VERSION,
        evidence_sha256=FUBON_NEO_CATALOG_EVIDENCE_SHA256,
        membership_sha256=membership_sha256,
        taiex_symbols=taiex_symbols,
        taisdaq_symbols=taisdaq_symbols,
        _authority=_CATALOG_AUTHORITY,
    )


__all__ = [
    "FUBON_NEO_BROKER_ID",
    "FUBON_NEO_CATALOG_EVIDENCE_SHA256",
    "FUBON_NEO_CATALOG_MEMBERSHIP_SHA256",
    "FUBON_NEO_CATALOG_SCHEMA_VERSION",
    "FUBON_NEO_CATALOG_SOURCE_VERSION",
    "FUBON_NEO_CURRENCY",
    "FUBON_NEO_MARKET",
    "FUBON_NEO_SDK_VERSION",
    "FUBON_NEO_SOURCE_VERSION",
    "FUBON_NEO_TEST_CONNECTION_IDENTITY",
    "FUBON_NEO_TEST_ENDPOINT",
    "FUBON_NEO_TPEX_CATALOG_ENDPOINT",
    "FUBON_NEO_TWSE_CATALOG_ENDPOINT",
    "FubonNeoInstrumentCatalog",
    "FubonNeoInstrumentMarket",
    "FubonNeoReadConnectionIdentity",
    "FubonNeoTestConfig",
    "build_reviewed_instrument_catalog",
]
