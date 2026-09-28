"""Fail-closed InvenTree REST read adapter and disabled draft-write boundary."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

from procurement import BuildNeed, PartSupply, PlanLine, Quote, Snapshot


class AdapterError(RuntimeError):
    """The remote data or adapter contract cannot be used safely."""


class PermissionDenied(AdapterError):
    """The authenticated user lacks a required InvenTree read permission."""


class TransportFailure(AdapterError):
    """A request result is unknown; callers must not infer success or retry writes."""


class WriteDisabled(AdapterError):
    """Purchase order writes are disabled until durable recovery is implemented."""


class JsonTransport(Protocol):
    """Minimal GET-only transport, replaceable by an in-process test double."""

    def get_json(self, url: str) -> object: ...


class UrllibJsonTransport:
    """HTTP GET transport; no POST method exists on this class."""

    def __init__(self, token: str, timeout: float = 10.0):
        if not token or timeout <= 0:
            raise ValueError("A token and positive timeout are required")
        self.token = token
        self.timeout = timeout

    def get_json(self, url: str) -> object:
        request = Request(url, headers={"Authorization": f"Token {self.token}", "Accept": "application/json"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code in (401, 403):
                raise PermissionDenied(f"InvenTree denied GET ({error.code})") from error
            raise AdapterError(f"InvenTree GET failed ({error.code})") from error
        except (URLError, TimeoutError) as error:
            raise TransportFailure("InvenTree GET result is unknown") from error
        except (ValueError, UnicodeError) as error:
            raise AdapterError("InvenTree returned invalid JSON") from error


Record = dict[str, object]
SupplyResolver = Callable[[int, Record, Record, tuple[Record, ...], tuple[BuildNeed, ...]], PartSupply]
QuoteResolver = Callable[[Record, tuple[Record, ...], Decimal], Quote | None]


def _record(value: object, context: str) -> Record:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise AdapterError(f"{context} must be a JSON object")
    return value


def _positive_id(value: object, context: str) -> int:
    if isinstance(value, bool):
        raise AdapterError(f"{context} must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise AdapterError(f"{context} must be a positive integer") from error
    if number <= 0 or str(number) != str(value):
        raise AdapterError(f"{context} must be a positive integer")
    return number


def _decimal(value: object, context: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise AdapterError(f"{context} must be numeric")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise AdapterError(f"{context} must be numeric") from error
    if not number.is_finite() or number < 0:
        raise AdapterError(f"{context} must be finite and nonnegative")
    return number


@dataclass(frozen=True)
class DraftRequests:
    """Pure request data, never sent by this adapter."""

    order: Record
    lines: tuple[Record, ...]


def format_draft_requests(reference: str, supplier_id: int, lines: tuple[PlanLine, ...]) -> DraftRequests:
    """Format source-checked InvenTree PO and PO-line POST bodies without sending them."""
    if not reference.strip() or not lines:
        raise AdapterError("A validated reference and at least one line are required")
    supplier_id = _positive_id(supplier_id, "supplier_id")
    requests: list[Record] = []
    for line in lines:
        if line.supplier_id != supplier_id or line.quantity <= 0 or line.unit_price < 0 or not line.currency:
            raise AdapterError("Draft line supplier, quantity, price, or currency is invalid")
        requests.append({
            "part": line.supplier_part_id,
            "quantity": str(line.quantity),
            "purchase_price": str(line.unit_price),
            "purchase_price_currency": line.currency,
            "merge_items": False,
            "auto_pricing": False,
        })
    return DraftRequests({"reference": reference, "supplier": supplier_id}, tuple(requests))


class InvenTreeReadAdapter:
    """Fetch normalized snapshot inputs; all procurement write methods fail closed.

    Supply and quote resolvers must supply independently verified allocation,
    expiry, quote tier, and ordering-multiple evidence. Raw REST values alone do
    not prove these quantities for a cross-build purchase plan.
    """

    def __init__(
        self,
        base_url: str,
        transport: JsonTransport,
        supply_resolver: SupplyResolver,
        quote_resolver: QuoteResolver,
    ):
        parsed = urlsplit(base_url)
        if (parsed.scheme not in ("http", "https") or not parsed.netloc or
                parsed.path not in ("", "/") or parsed.query or parsed.fragment or
                parsed.username or parsed.password):
            raise ValueError("base_url must be an HTTP(S) origin")
        self.base_url = f"{parsed.scheme}://{parsed.netloc}"
        self.transport = transport
        self.supply_resolver = supply_resolver
        self.quote_resolver = quote_resolver

    def _url(self, path: str, params: dict[str, str] | None = None) -> str:
        url = self.base_url + path
        return url + ("?" + urlencode(params) if params else "")

    def _get(self, path: str) -> Record:
        return _record(self.transport.get_json(self._url(path)), path)

    def _list(self, path: str, params: dict[str, str]) -> tuple[Record, ...]:
        url = self._url(path, params)
        visited: set[str] = set()
        rows: list[Record] = []
        while url is not None:
            if url in visited or len(visited) >= 100:
                raise AdapterError("Pagination loop or excessive page count")
            visited.add(url)
            payload = self.transport.get_json(url)
            if isinstance(payload, list):
                page, next_url = payload, None
            else:
                envelope = _record(payload, path)
                page, next_url = envelope.get("results"), envelope.get("next")
            if not isinstance(page, list):
                raise AdapterError(f"{path} did not return a list")
            rows.extend(_record(item, path) for item in page)
            if next_url is None:
                url = None
            elif isinstance(next_url, str) and next_url:
                candidate = urljoin(url, next_url)
                parsed = urlsplit(candidate)
                if f"{parsed.scheme}://{parsed.netloc}" != self.base_url or parsed.path != path:
                    raise AdapterError("Pagination target changed origin or endpoint")
                query = parse_qs(parsed.query)
                if any(query.get(key) != [value] for key, value in params.items()):
                    raise AdapterError("Pagination target changed the requested filters")
                url = candidate
            else:
                raise AdapterError("Invalid pagination next link")
        return tuple(rows)

    def _needs(self, build_ids: tuple[int, ...]) -> tuple[BuildNeed, ...]:
        needs: list[BuildNeed] = []
        seen: set[int] = set()
        for build_id in build_ids:
            build = self._get(f"/api/build/{build_id}/")
            if _positive_id(build.get("pk"), "build pk") != build_id:
                raise AdapterError("Build detail has a mismatched ID")
            for row in self._list("/api/build/line/", {"build": str(build_id)}):
                line_id = _positive_id(row.get("pk"), "build line pk")
                if line_id in seen or _positive_id(row.get("build"), "build") != build_id:
                    raise AdapterError("Duplicate or mismatched build line")
                seen.add(line_id)
                required = _decimal(row.get("quantity"), "quantity")
                consumed = _decimal(row.get("consumed"), "consumed")
                allocated = _decimal(row.get("allocated"), "allocated")
                if consumed + allocated > required:
                    raise AdapterError("Consumed plus allocated exceeds line quantity")
                needs.append(BuildNeed(build_id, line_id, _positive_id(row.get("part"), "part"),
                                       required - consumed - allocated))
        return tuple(needs)

    def _part_inputs(self, part_id: int, needs: tuple[BuildNeed, ...]) -> tuple[PartSupply, tuple[Quote, ...]]:
        detail = self._get(f"/api/part/{part_id}/")
        if _positive_id(detail.get("pk"), "part pk") != part_id:
            raise AdapterError("Part detail has a mismatched ID")
        requirements = self._get(f"/api/part/{part_id}/requirements/")
        stock = self._list("/api/stock/", {"part": str(part_id), "include_variants": "false"})
        if any(_positive_id(item.get("part"), "stock part") != part_id for item in stock):
            raise AdapterError("Stock row has a mismatched part")
        related_needs = tuple(line for line in needs if line.part_id == part_id)
        supply = self.supply_resolver(part_id, detail, requirements, stock, related_needs)
        if (not isinstance(supply, PartSupply) or supply.part_id != part_id or
                not isinstance(supply.free_stock, Decimal) or not isinstance(supply.incoming, Decimal)):
            raise AdapterError("Supply resolver returned invalid shared supply")
        _decimal(supply.free_stock, "free_stock")
        _decimal(supply.incoming, "incoming")
        quotes: list[Quote] = []
        supplier_parts = self._list("/api/company/part/", {
            "part": str(part_id), "active": "true", "supplier_active": "true"
        })
        shortage = max(Decimal(0), sum((need.outstanding for need in related_needs), Decimal(0))
                       - supply.free_stock - supply.incoming)
        for supplier_part in supplier_parts:
            supplier_part_id = _positive_id(supplier_part.get("pk"), "supplier part pk")
            if _positive_id(supplier_part.get("part"), "supplier part base part") != part_id:
                raise AdapterError("Supplier part has a mismatched base part")
            breaks = self._list("/api/company/price-break/", {"part": str(supplier_part_id)})
            if any(_positive_id(item.get("part"), "price break part") != supplier_part_id for item in breaks):
                raise AdapterError("Price break has a mismatched supplier part")
            quote = self.quote_resolver(supplier_part, breaks, shortage)
            if quote is None:
                continue
            if not isinstance(quote, Quote) or not isinstance(quote.unit_price, Decimal):
                raise AdapterError("Quote resolver returned invalid quote")
            _decimal(quote.unit_price, "quote unit price")
            _decimal(quote.order_multiple, "quote order multiple")
            pack = _decimal(supplier_part.get("pack_quantity_native"), "pack_quantity_native")
            if (quote.supplier_part_id != supplier_part_id or quote.part_id != part_id or
                    quote.supplier_id != _positive_id(supplier_part.get("supplier"), "supplier") or
                    quote.stock_units_per_order_unit != pack or pack <= 0 or
                    quote.order_multiple <= 0 or not isinstance(quote.valid_until, date) or
                    not quote.source):
                raise AdapterError("Quote resolver returned mismatched supplier or pack conversion")
            if not any(_decimal(item.get("price"), "price break price") == quote.unit_price and
                       item.get("price_currency") == quote.currency for item in breaks):
                raise AdapterError("Quote price and currency do not match a REST price break")
            quotes.append(quote)
        return supply, tuple(quotes)

    def read_snapshot(self, build_ids: tuple[int, ...]) -> Snapshot:
        if not build_ids or len(build_ids) != len(set(build_ids)):
            raise AdapterError("Select unique build IDs")
        checked_ids = tuple(_positive_id(value, "build_id") for value in build_ids)
        needs = self._needs(checked_ids)
        supplies: list[PartSupply] = []
        quotes: list[Quote] = []
        for part_id in sorted({need.part_id for need in needs}):
            supply, part_quotes = self._part_inputs(part_id, needs)
            supplies.append(supply)
            quotes.extend(part_quotes)
        return Snapshot(needs, tuple(supplies), tuple(quotes))

    def find_complete_pending_order(self, idempotency_key: str) -> str | None:
        raise WriteDisabled("Draft lookup and durable recovery are not implemented")

    def create_pending_order(self, supplier_id: int, lines: tuple[PlanLine, ...], idempotency_key: str) -> str:
        raise WriteDisabled("PO creation is disabled until idempotency and line recovery are implemented")
