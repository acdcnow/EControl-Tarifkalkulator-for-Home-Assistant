"""Constants for the E-Control Tarifkalkulator integration.

The values in this module are the single source of truth for the integration.
They are derived from the public E-Control tariff calculator REST interface
(``https://www.e-control.at/o/rc-public-rest``) and from the partner interface
(``https://api.e-control.at/rc/1.0``); see the project wiki for the full
protocol documentation.

Nothing in here may contain Home Assistant runtime objects.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

DOMAIN: Final = "econtrol"

# --------------------------------------------------------------------------
# Configuration keys
# --------------------------------------------------------------------------
CONF_SOURCE: Final = "source"
CONF_ZIP_CODE: Final = "zip_code"
CONF_CUSTOMER_GROUP: Final = "customer_group"
CONF_ENERGY_TYPES: Final = "energy_types"
CONF_ENERGY_TYPE: Final = "energy_type"
CONF_ENERGY_TYPE_OPTION: Final = "energy_type_option"
CONF_CONSUMPTION: Final = "consumption"
CONF_SWITCHING_DISCOUNTS: Final = "include_switching_discounts"
CONF_REFERENCE_PERIOD: Final = "reference_period"
CONF_BRAND_ID: Final = "brand_id"
CONF_BRAND_NAME: Final = "brand_name"
CONF_PRODUCT_ID: Final = "product_id"
CONF_PRODUCT_ASSOCIATION_ID: Final = "product_association_id"
CONF_PRODUCT_NAME: Final = "product_name"
CONF_OFFER_COUNT: Final = "offer_count"
CONF_SCAN_INTERVAL_HOURS: Final = "scan_interval_hours"
CONF_PASSWORD: Final = "password"
CONF_USERNAME: Final = "username"
CONF_URL: Final = "url"

# --------------------------------------------------------------------------
# Data sources
# --------------------------------------------------------------------------
SOURCE_PUBLIC: Final = "public"
SOURCE_PARTNER: Final = "partner"
SOURCES: Final = (SOURCE_PUBLIC, SOURCE_PARTNER)

# --------------------------------------------------------------------------
# Customer groups
# --------------------------------------------------------------------------
#: Internal values are lower case, because they double as Home Assistant
#: translation keys (``selector.customer_group.options.home``). The REST
#: interface is fed with the upper case form through :func:`api_value`.
CUSTOMER_GROUP_HOME: Final = "home"
CUSTOMER_GROUP_BUSINESS: Final = "business"
CUSTOMER_GROUPS: Final = (CUSTOMER_GROUP_HOME, CUSTOMER_GROUP_BUSINESS)


def api_value(value: str) -> str:
    """Return the upper case form of an internal enum value.

    Every value of :class:`EnergyType`, of :class:`ReferencePeriod`, of
    :class:`PriceView`, of the customer groups and of the product types is a
    lower case identifier that is safe to use as a Home Assistant translation
    key. The REST interface expects the upper case spelling (``power`` ->
    ``POWER``, ``power_feed_in`` -> ``POWER_FEED_IN``), so every value that
    leaves the integration goes through this single mapping function.
    """
    return str(value).upper()


class EnergyType(StrEnum):
    """The energy type of a tariff comparison.

    ``api_value()`` of these values is used as the ``energyType`` field of the
    API requests and as part of the
    ``/rate-calculator/energy-type/<value>/rate`` resource path.
    """

    POWER = "power"
    """Electricity consumption (Strom Bezug)."""

    POWER_FEED_IN = "power_feed_in"
    """Electricity feed-in (Strom Einspeisung).

    .. warning::

       The public interface exposes the feed-in comparison through the
       electricity endpoints with ``firstMeterOptions.productType = FEED_IN``
       and ``firstMeterOptions.annualConsumption``. On the reference grid area
       the public endpoint answered ``500 RCGATE_UNK01`` for this combination,
       so treat this category as **experimental**.
    """

    GAS = "gas"
    """Gas consumption (Gas)."""


ENERGY_TYPES: Final = (
    EnergyType.POWER,
    EnergyType.POWER_FEED_IN,
    EnergyType.GAS,
)

#: Human readable labels used for the Home Assistant device names.
#: Device names are not translated by Home Assistant, so they are kept here in
#: the language of the primary audience of the integration.
ENERGY_TYPE_LABELS: Final = {
    EnergyType.POWER: "Strom Bezug",
    EnergyType.POWER_FEED_IN: "Strom Einspeisung",
    EnergyType.GAS: "Gas",
}

#: Product types understood by ``firstMeterOptions.productType``.
PRODUCT_TYPE_MAIN: Final = "main"
PRODUCT_TYPE_FEED_IN: Final = "feed_in"


class PriceView(StrEnum):
    """How the total costs are expressed by the API.

    ``eur_per_year`` is the only value that the REST interface accepts for
    ``/rate-calculator/energy-type/*/rate``; ``CENT_PER_KWH`` is answered with
    ``HTTP 500``. The frontend's "Cent / kWh" tab is a pure client side
    recalculation, which this integration mirrors instead.
    """

    EUR_PER_YEAR = "eur_per_year"


class ReferencePeriod(StrEnum):
    """The period the total costs are projected onto."""

    ONE_YEAR = "one_year"
    TWO_YEARS = "two_years"
    THREE_YEARS = "three_years"


REFERENCE_PERIODS: Final = (
    ReferencePeriod.ONE_YEAR,
    ReferencePeriod.TWO_YEARS,
    ReferencePeriod.THREE_YEARS,
)

SEARCH_PRICE_MODEL_CLASSIC: Final = "classic"

# --------------------------------------------------------------------------
# Defaults and limits
# --------------------------------------------------------------------------
DEFAULT_NAME: Final = "E-Control"
DEFAULT_SOURCE: Final = SOURCE_PUBLIC
DEFAULT_CUSTOMER_GROUP: Final = CUSTOMER_GROUP_HOME
DEFAULT_REFERENCE_PERIOD: Final = ReferencePeriod.ONE_YEAR
DEFAULT_SWITCHING_DISCOUNTS: Final = True
DEFAULT_SCAN_INTERVAL_HOURS: Final = 24
DEFAULT_OFFER_COUNT: Final = 10

#: Consumption bounds mirrored from the calculator's own client side
#: validation ("Der Verbrauch ... muss groesser 0 kWh und kleiner gleich
#: 100.000 kWh sein.").
MIN_CONSUMPTION: Final = 1
MAX_CONSUMPTION: Final = 100_000

MIN_SCAN_INTERVAL_HOURS: Final = 1
MAX_SCAN_INTERVAL_HOURS: Final = 168

MIN_OFFER_COUNT: Final = 1
MAX_OFFER_COUNT: Final = 50

#: The API transports every monetary value as a string of *cents* with six
#: decimal places, e.g. ``"115455.360000"`` for EUR 1154.55.
CENTS_PER_EURO: Final = 100

# --------------------------------------------------------------------------
# Diagnostic attributes
# --------------------------------------------------------------------------
ATTR_OFFERS: Final = "offers"
ATTR_OFFER_COUNT: Final = "offer_count"
ATTR_GRID_OPERATOR: Final = "grid_operator"
ATTR_GRID_OPERATOR_ID: Final = "grid_operator_id"
ATTR_GRID_AREA_ID: Final = "grid_area_id"
ATTR_ZIP_CODE: Final = "zip_code"
ATTR_CUSTOMER_GROUP: Final = "customer_group"
ATTR_ENERGY_TYPE: Final = "energy_type"
ATTR_SOURCE: Final = "source"
ATTR_CONSUMPTION: Final = "consumption_kwh"
ATTR_REFERENCE_PERIOD: Final = "reference_period"
ATTR_SWITCHING_DISCOUNTS: Final = "include_switching_discounts"
ATTR_BRAND: Final = "brand"
ATTR_PRODUCT: Final = "product"
ATTR_ANNUAL_COST: Final = "annual_cost_eur"
ATTR_PRICE_PER_KWH: Final = "price_ct_per_kwh"
ATTR_SAVING: Final = "saving_eur"
ATTR_EXTRA_COST: Final = "extra_cost_eur"
ATTR_PRICE_GUARANTEE: Final = "price_guarantee_months"
ATTR_PRICE_GUARANTEE_UNTIL: Final = "price_guarantee_until"
ATTR_SWITCH_LINK: Final = "switch_url"
ATTR_SUPPLIER: Final = "supplier"
ATTR_FLAGS: Final = "flags"
ATTR_LAST_SUCCESSFUL_UPDATE: Final = "last_successful_update"
ATTR_FAILED_REASON: Final = "failed_reason"
