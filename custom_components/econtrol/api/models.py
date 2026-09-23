"""Typed view over the E-Control Tarifkalkulator API payloads.

The API answers with loosely typed JSON: monetary values are transported as
strings of *cents* with six decimals (``"115455.360000"`` means EUR 1154.55),
timestamps are epoch milliseconds and optional fields are frequently ``null``.

Every parser in this module is deliberately tolerant: an unexpected or missing
value yields ``None`` instead of raising, so one malformed offer cannot make
the whole comparison unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Final, Self

from . import constants as c
from ..const import (
    ATTR_ANNUAL_COST,
    ATTR_BRAND,
    ATTR_EXTRA_COST,
    ATTR_FLAGS,
    ATTR_PRICE_GUARANTEE,
    ATTR_PRICE_GUARANTEE_UNTIL,
    ATTR_PRICE_PER_KWH,
    ATTR_PRODUCT,
    ATTR_SAVING,
    ATTR_SUPPLIER,
    ATTR_SWITCH_LINK,
    PRODUCT_TYPE_FEED_IN,
    PRODUCT_TYPE_MAIN,
    SEARCH_PRICE_MODEL_CLASSIC,
    EnergyType,
    PriceView,
    ReferencePeriod,
    api_value,
)

_ZERO: Final = Decimal(0)
_CENTS: Final = Decimal(100)


# --------------------------------------------------------------------------
# Primitive coercion helpers
# --------------------------------------------------------------------------
def as_str(value: Any) -> str | None:
    """Return ``value`` as a stripped string, or ``None`` when empty."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def as_int(value: Any) -> int | None:
    """Return ``value`` as an integer, or ``None`` when it is not numeric."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def as_bool(value: Any) -> bool:
    """Return ``value`` as a boolean, accepting the strings ``true``/``false``."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes"}


def as_decimal(value: Any) -> Decimal | None:
    """Return ``value`` as a :class:`~decimal.Decimal`, or ``None``."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError):
        return None


def as_cents(value: Any) -> Decimal | None:
    """Convert a cents value from the wire format into euro."""
    amount = as_decimal(value)
    if amount is None:
        return None
    return (amount / _CENTS).quantize(Decimal("0.01"))


def as_datetime(value: Any) -> datetime | None:
    """Convert epoch milliseconds (or an ISO 8601 string) into a datetime."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip().isdigit():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    millis = as_int(value)
    if millis is None:
        return None
    try:
        return datetime.fromtimestamp(millis / 1000, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


def _object(value: Any) -> dict[str, Any]:
    """Return ``value`` as a dictionary, or an empty dictionary."""
    return value if isinstance(value, dict) else {}


def _objects(value: Any) -> list[dict[str, Any]]:
    """Return ``value`` as a list of dictionaries, or an empty list."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


# --------------------------------------------------------------------------
# Response models
# --------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class GridOperator:
    """A grid operator as returned for a postal code and an energy type."""

    operator_id: int
    name: str
    grid_area_id: int
    energy_type: str
    brand_id: int | None

    @classmethod
    def from_api(cls, payload: Any) -> Self | None:
        """Build a grid operator from one ``gridOperators`` entry."""
        data = _object(payload)
        operator_id = as_int(data.get(c.RESP_ID))
        grid_area_id = as_int(data.get(c.RESP_GRID_AREA_ID))
        if operator_id is None or grid_area_id is None:
            return None
        return cls(
            operator_id=operator_id,
            name=as_str(data.get(c.RESP_NAME)) or str(operator_id),
            grid_area_id=grid_area_id,
            energy_type=as_str(data.get(c.RESP_ENERGY_TYPE)) or "",
            brand_id=as_int(data.get(c.RESP_BRAND_HOME)),
        )

    @staticmethod
    def business_brand_id(payload: Any) -> int | None:
        """Return the business brand of a ``gridOperators`` entry."""
        return as_int(_object(payload).get(c.RESP_BRAND_BUSINESS))


@dataclass(frozen=True, slots=True)
class ProductOption:
    """One selectable product of a brand (used for the own-product comparison)."""

    product_id: int
    association_id: int | None
    name: str
    is_default: bool = False

    @classmethod
    def from_api(cls, payload: Any, *, default_id: int | None) -> Self | None:
        """Build a product option from one ``productData`` entry."""
        data = _object(payload)
        product_id = as_int(data.get(c.RESP_MAIN_ID))
        if product_id is None:
            return None
        return cls(
            product_id=product_id,
            association_id=as_int(data.get(c.RESP_MAIN_ASSOCIATION_ID)),
            name=as_str(data.get(c.RESP_NAME)) or str(product_id),
            is_default=default_id is not None and product_id == default_id,
        )


@dataclass(frozen=True, slots=True)
class Offer:
    """A single tariff offer of a rate comparison."""

    product_id: int | None
    association_id: int | None
    product_type: str | None
    product_name: str
    brand_id: int | None
    brand_name: str
    supplier_name: str | None
    annual_cost: Decimal | None
    saving: Decimal
    extra_cost: Decimal
    energy_price_ct_per_kwh: Decimal | None
    total_price_ct_per_kwh: Decimal | None
    base_rate_eur: Decimal | None
    is_current_product: bool
    price_guarantee_months: int | None
    price_guarantee_until: datetime | None
    price_guarantee_type: str | None
    last_price_change: datetime | None
    switch_url: str | None
    flags: tuple[str, ...]
    flag_labels: tuple[str, ...]
    renewable_share: Decimal | None
    is_online_only: bool

    @classmethod
    def from_api(cls, payload: Any) -> Self | None:
        """Build an offer from one ``ratedProducts`` entry."""
        data = _object(payload)
        annual_cost = as_cents(data.get(c.RESP_ANNUAL_GROSS_RATE))
        if annual_cost is None:
            return None

        contract = _object(data.get(c.RESP_CONTRACT_TERM_INFO))
        change_link = _object(data.get(c.RESP_CHANGE_LINK))

        properties = _objects(data.get(c.RESP_PRODUCT_PROPERTIES))
        flags = tuple(
            flag
            for flag in (as_str(item.get(c.RESP_PROP_NAME)) for item in properties)
            if flag
        )
        labels = tuple(
            label
            for label in (
                as_str(item.get(c.RESP_DEFAULT_PROP_NAME)) for item in properties
            )
            if label
        )

        energy_sources = _object(data.get(c.RESP_ENERGY_SOURCES))
        # ``energySources`` is a mapping of origin to percentage, e.g.
        # {"RENEWABLE": 100.00, "FOSSIL": 0, "NUCLEAR_ENERGY": 0}.
        renewable_share = as_decimal(energy_sources.get(c.RESP_RENEWABLE))

        return cls(
            product_id=as_int(data.get(c.RESP_PRODUCT_ID)),
            association_id=as_int(data.get(c.RESP_ASSOCIATION_ID)),
            product_type=as_str(data.get(c.RESP_PRODUCT_TYPE)),
            product_name=as_str(data.get(c.RESP_PRODUCT_NAME)) or "",
            brand_id=as_int(data.get(c.RESP_BRAND_ID)),
            brand_name=(as_str(data.get(c.RESP_BRAND_NAME)) or "").strip(),
            supplier_name=as_str(data.get(c.RESP_SUPPLIER_NAME)),
            annual_cost=annual_cost,
            saving=as_cents(data.get(c.RESP_ANNUAL_SAVING)) or _ZERO,
            extra_cost=as_cents(data.get(c.RESP_ANNUAL_RISING)) or _ZERO,
            energy_price_ct_per_kwh=as_decimal(
                data.get(c.RESP_AVERAGE_ENERGY_PRICE_CT_KWH)
            ),
            total_price_ct_per_kwh=as_decimal(
                data.get(c.RESP_AVERAGE_TOTAL_PRICE_CT_KWH)
            ),
            base_rate_eur=as_cents(data.get(c.RESP_BASE_RATE_WITH_TAX)),
            is_current_product=as_bool(data.get(c.RESP_COMPARISON)),
            price_guarantee_months=as_int(contract.get(c.RESP_PRICE_GUARANTEE_MONTHS)),
            price_guarantee_until=as_datetime(contract.get(c.RESP_PRICE_GUARANTEE_UNTIL)),
            price_guarantee_type=as_str(contract.get(c.RESP_PRICE_GUARANTEE_TYPE)),
            last_price_change=as_datetime(contract.get(c.RESP_LAST_DATE_CHANGE)),
            switch_url=as_str(change_link.get(c.RESP_LINK)),
            flags=flags,
            flag_labels=labels,
            renewable_share=renewable_share,
            is_online_only=(
                as_str(data.get(c.RESP_VERSION_STATE)) == "ONLINE"
                or "ONLINE_PRODUCT" in flags
            ),
        )

    @property
    def display_name(self) -> str:
        """Return a human readable ``"<brand> <product>"`` label."""
        if self.brand_name and self.product_name:
            return f"{self.brand_name} {self.product_name}"
        return self.brand_name or self.product_name

    def price_per_kwh(self, consumption_kwh: int | None) -> Decimal | None:
        """Return the all-in price in ct/kWh for a consumption.

        The interface only reports yearly totals (``priceView`` is fixed to
        ``EUR_PER_YEAR``) which means the frontend's "Cent / kWh" column is a
        pure client side division. This mirrors that calculation so the
        integration can expose the same number.
        """
        if not consumption_kwh or self.annual_cost is None:
            return None
        per_kwh = (self.annual_cost * _CENTS / Decimal(consumption_kwh)).quantize(
            Decimal("0.01")
        )
        return per_kwh

    def to_attributes(self, *, consumption_kwh: int | None = None) -> dict[str, Any]:
        """Return a JSON serialisable representation to expose as attributes."""
        attributes: dict[str, Any] = {
            ATTR_BRAND: self.brand_name or None,
            ATTR_PRODUCT: self.product_name or None,
            ATTR_ANNUAL_COST: float(self.annual_cost) if self.annual_cost else None,
            ATTR_SAVING: float(self.saving),
            ATTR_EXTRA_COST: float(self.extra_cost),
        }
        per_kwh = self.price_per_kwh(consumption_kwh)
        if per_kwh is not None:
            attributes[ATTR_PRICE_PER_KWH] = float(per_kwh)
        if self.supplier_name:
            attributes[ATTR_SUPPLIER] = self.supplier_name
        if self.price_guarantee_months:
            attributes[ATTR_PRICE_GUARANTEE] = self.price_guarantee_months
        if self.price_guarantee_until:
            attributes[ATTR_PRICE_GUARANTEE_UNTIL] = self.price_guarantee_until.isoformat()
        if self.switch_url:
            attributes[ATTR_SWITCH_LINK] = self.switch_url
        if self.flag_labels:
            attributes[ATTR_FLAGS] = list(self.flag_labels)
        if self.renewable_share is not None:
            attributes["renewable_share"] = float(self.renewable_share)
        if self.is_current_product:
            attributes["is_current_product"] = True
        if self.product_type:
            attributes["product_type"] = self.product_type
        return attributes


@dataclass(frozen=True, slots=True)
class RateResult:
    """The complete result of one tariff comparison."""

    energy_type: str
    grid_operator_name: str | None
    grid_operator_id: int | None
    grid_area_id: int | None
    consumption_kwh: int | None
    max_saving: Decimal | None
    range_from: Decimal | None
    range_to: Decimal | None
    offers: tuple[Offer, ...]
    fetched_at: datetime

    @classmethod
    def from_api(
        cls,
        payload: Any,
        *,
        energy_type: str,
        grid_operator_id: int | None,
        grid_area_id: int | None,
        consumption_kwh: int | None,
        fetched_at: datetime,
    ) -> Self:
        """Build a rate result from a ``/rate-calculator/.../rate`` response."""
        data = _object(payload)
        rate_range = _object(data.get(c.RESP_ANNUAL_RATE_RANGE))

        offers = [
            offer
            for offer in (
                Offer.from_api(entry)
                for entry in _objects(data.get(c.RESP_RATED_PRODUCTS))
            )
            if offer is not None
        ]
        offers.sort(key=lambda offer: (offer.annual_cost is None, offer.annual_cost))

        return cls(
            energy_type=energy_type,
            grid_operator_name=as_str(data.get(c.RESP_GRID_OPERATOR_NAME)),
            grid_operator_id=grid_operator_id,
            grid_area_id=grid_area_id,
            consumption_kwh=consumption_kwh,
            max_saving=as_cents(data.get(c.RESP_MAX_SAVING)),
            range_from=as_cents(rate_range.get(c.RESP_RANGE_FROM)),
            range_to=as_cents(rate_range.get(c.RESP_RANGE_TO)),
            offers=tuple(offers),
            fetched_at=fetched_at,
        )

    @property
    def payable_offers(self) -> tuple[Offer, ...]:
        """Return the offers that carry a usable price.

        A few products are announced without a calculable price (the frontend
        shows ``0,00`` and "Komplexe Preisgestaltung" for them). They would
        otherwise win every "cheapest" comparison with EUR 0.
        """
        return tuple(
            offer
            for offer in self.offers
            if offer.annual_cost is not None and offer.annual_cost > _ZERO
        )

    @property
    def cheapest(self) -> Offer | None:
        """Return the cheapest offer with a usable price."""
        offers = self.payable_offers
        return offers[0] if offers else None

    @property
    def own_product(self) -> Offer | None:
        """Return the offer that represents the configured own product."""
        for offer in self.offers:
            if offer.is_current_product:
                return offer
        return None

    @property
    def priced_offer_count(self) -> int:
        """Return how many offers carry a usable price."""
        return len(self.payable_offers)


@dataclass(frozen=True, slots=True)
class RateRequest:
    """A fully resolved tariff comparison request.

    The interface requires a comparison product for every call, even when the
    caller is not interested in a comparison: the ``comparisonOptions`` object
    and its ``brandId``/``mainProductId``/``mainProductAssociationId`` fields
    are mandatory and missing values are rejected with ``HTTP 422``.
    """

    customer_group: str
    energy_type: str
    zip_code: int
    grid_operator_id: int
    grid_area_id: int
    consumption_kwh: int
    brand_id: int | None = None
    product_id: int | None = None
    product_association_id: int | None = None
    product_name: str | None = None
    additional_product_id: int | None = None
    additional_product_association_id: int | None = None
    feed_in_product_id: int | None = None
    feed_in_product_association_id: int | None = None
    include_switching_discounts: bool = True
    reference_period: str = ReferencePeriod.ONE_YEAR
    include_smart_meter: bool = False
    move_home: bool = False
    manual_entry: bool = False

    @property
    def is_feed_in(self) -> bool:
        """Return whether this request compares a feed-in tariff."""
        return self.energy_type == EnergyType.POWER_FEED_IN

    @property
    def api_energy_type(self) -> str:
        """Return the energy type as expected by the REST interface."""
        return api_value(self.energy_type)

    def to_body(self, *, with_comparison: bool = True) -> dict[str, Any]:
        """Build the JSON body of a rate or product search request.

        :param with_comparison: ``True`` for ``.../rate``, ``False`` for the
            product search, which uses the identical body without
            ``comparisonOptions``.
        """
        first_meter_options: dict[str, Any] = {
            c.BODY_PRODUCT_TYPE: api_value(
                PRODUCT_TYPE_FEED_IN if self.is_feed_in else PRODUCT_TYPE_MAIN
            ),
            c.BODY_SMART_METER_OPTIONS: {
                c.BODY_SMART_METER_SEARCH: self.include_smart_meter,
                c.BODY_LOAD_PROFILE_UPLOAD: False,
                c.BODY_CONSUMPTION_TYPE: None,
                c.BODY_CALCULATED_VALUES: None,
                c.BODY_DETAILED_VALUES: None,
                c.BODY_LAST_UPLOAD_DATE: None,
                c.BODY_RATE_ZONING_TYPES: None,
            },
        }
        if self.is_feed_in:
            first_meter_options[c.BODY_ANNUAL_CONSUMPTION] = self.consumption_kwh
            first_meter_options[c.BODY_ENERGY_OUTPUT] = None
        else:
            first_meter_options[c.BODY_STANDARD_CONSUMPTION] = self.consumption_kwh

        body: dict[str, Any] = {
            c.BODY_CUSTOMER_GROUP: api_value(self.customer_group),
            c.BODY_ENERGY_TYPE: self.api_energy_type,
            c.BODY_ZIP_CODE: self.zip_code,
            c.BODY_GRID_OPERATOR_ID: self.grid_operator_id,
            c.BODY_GRID_AREA_ID: self.grid_area_id,
            c.BODY_MOVE_HOME: self.move_home,
            c.BODY_INCLUDE_SWITCHING_DISCOUNTS: self.include_switching_discounts,
            c.BODY_FIRST_METER_OPTIONS: first_meter_options,
        }
        if with_comparison:
            body[c.BODY_COMPARISON_OPTIONS] = {
                c.BODY_BRAND_ID: self.brand_id,
                c.BODY_MAIN_PRODUCT_ID: self.product_id,
                c.BODY_MAIN_PRODUCT_ASSOCIATION_ID: self.product_association_id,
                c.BODY_ADDITIONAL_PRODUCT_ID: self.additional_product_id,
                c.BODY_ADDITIONAL_PRODUCT_ASSOCIATION_ID: (
                    self.additional_product_association_id
                ),
                c.BODY_FEED_IN_PRODUCT_ID: self.feed_in_product_id,
                c.BODY_FEED_IN_PRODUCT_ASSOCIATION_ID: (
                    self.feed_in_product_association_id
                ),
                c.BODY_PRODUCT_NAME: self.product_name,
                c.BODY_MANUAL_ENTRY: self.manual_entry,
                c.BODY_MAIN_BASE_RATE: None,
                c.BODY_MAIN_ENERGY_RATE: None,
            }
        body[c.BODY_MEMBERSHIP] = None
        body[c.BODY_REQUIREMENTS] = []
        body[c.BODY_PRICE_VIEW] = api_value(PriceView.EUR_PER_YEAR)
        body[c.BODY_REFERENCE_PERIOD] = api_value(self.reference_period)
        body[c.BODY_SEARCH_PRICE_MODEL] = api_value(SEARCH_PRICE_MODEL_CLASSIC)
        return body

