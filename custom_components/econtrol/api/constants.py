"""Wire level constants of the E-Control Tarifkalkulator REST interface.

All resource paths and JSON field names that this integration depends on live
here. They were established by observing the public tariff calculator
frontend and verified against the public REST proxy on 2026-09-23. See the
project wiki (Software Design Document, section "Interface contracts") for the
protocol documentation and the verification log.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------
# Base URLs
# --------------------------------------------------------------------------
#: Public REST proxy used by https://www.e-control.at/tarifkalkulator. It needs
#: no credentials and no session for the resources this integration uses.
PUBLIC_BASE_URL: Final = "https://www.e-control.at/o/rc-public-rest"

#: Documented partner interface (see https://www.e-control.at/webservice-information-zur-schnittstelle).
#: Access requires a username and password issued by tarifkalkulator@e-control.at.
PARTNER_PRODUCTION_URL: Final = "https://api.e-control.at/rc/1.0"
PARTNER_DEVELOPMENT_URL: Final = "https://api-dev.e-control.at/rc/1.0"

DEFAULT_LOCALE: Final = "de"
DEFAULT_TIMEOUT: Final = 30
USER_AGENT: Final = "Home-Assistant-E-Control-Tarifkalkulator/1.0"

# --------------------------------------------------------------------------
# Resource paths (relative to the base URL)
# --------------------------------------------------------------------------
PATH_UI_CONFIGURATION: Final = "/system-parameters/ui-configuration"

PATH_GRID_OPERATORS: Final = "/rate-calculator/grid-operators"
PATH_SEARCH_PARAMETERS: Final = "/rate-calculator/{segment}/search-parameters"
PATH_RATE: Final = "/rate-calculator/energy-type/{energy_type}/rate"

PATH_PRODUCTS: Final = "/brands/{brand_id}/products/{segment}/search"

# --------------------------------------------------------------------------
# Query parameters
# --------------------------------------------------------------------------
QUERY_LOCALE: Final = "locale"
QUERY_ZIP_CODE: Final = "zipCode"
QUERY_ENERGY_TYPE: Final = "energyType"
QUERY_SMART_METER: Final = "isSmartMeter"
QUERY_INCLUDE_SMART_METER: Final = "includeSmartMeter"

# --------------------------------------------------------------------------
# Request body field names
# --------------------------------------------------------------------------
BODY_CUSTOMER_GROUP: Final = "customerGroup"
BODY_ENERGY_TYPE: Final = "energyType"
BODY_ZIP_CODE: Final = "zipCode"
BODY_GRID_OPERATOR_ID: Final = "gridOperatorId"
BODY_GRID_AREA_ID: Final = "gridAreaId"
BODY_MOVE_HOME: Final = "moveHome"
BODY_INCLUDE_SWITCHING_DISCOUNTS: Final = "includeSwitchingDiscounts"
BODY_FIRST_METER_OPTIONS: Final = "firstMeterOptions"
BODY_SMART_METER_OPTIONS: Final = "smartMeterRequestOptions"
BODY_COMPARISON_OPTIONS: Final = "comparisonOptions"
BODY_MEMBERSHIP: Final = "membership"
BODY_REQUIREMENTS: Final = "requirements"
BODY_PRICE_VIEW: Final = "priceView"
BODY_REFERENCE_PERIOD: Final = "referencePeriod"
BODY_SEARCH_PRICE_MODEL: Final = "searchPriceModel"

BODY_PRODUCT_TYPE: Final = "productType"
BODY_STANDARD_CONSUMPTION: Final = "standardConsumption"
BODY_ANNUAL_CONSUMPTION: Final = "annualConsumption"
BODY_ENERGY_OUTPUT: Final = "energyOutput"

BODY_BRAND_ID: Final = "brandId"
BODY_MAIN_PRODUCT_ID: Final = "mainProductId"
BODY_MAIN_PRODUCT_ASSOCIATION_ID: Final = "mainProductAssociationId"
BODY_ADDITIONAL_PRODUCT_ID: Final = "additionalProductId"
BODY_ADDITIONAL_PRODUCT_ASSOCIATION_ID: Final = "additionalProductAssociationId"
BODY_FEED_IN_PRODUCT_ID: Final = "feedInProductId"
BODY_FEED_IN_PRODUCT_ASSOCIATION_ID: Final = "feedInProductAssociationId"
BODY_PRODUCT_NAME: Final = "productName"
BODY_MANUAL_ENTRY: Final = "manualEntry"
BODY_MAIN_BASE_RATE: Final = "mainBaseRate"
BODY_MAIN_ENERGY_RATE: Final = "mainEnergyRate"

BODY_SMART_METER_SEARCH: Final = "smartMeterSearch"
BODY_LOAD_PROFILE_UPLOAD: Final = "loadProfileUpload"
BODY_CONSUMPTION_TYPE: Final = "consumptionType"
BODY_CALCULATED_VALUES: Final = "calculatedValues"
BODY_DETAILED_VALUES: Final = "detailedValues"
BODY_LAST_UPLOAD_DATE: Final = "lastUploadDate"
BODY_RATE_ZONING_TYPES: Final = "rateZoningTypes"

# --------------------------------------------------------------------------
# Response field names
# --------------------------------------------------------------------------
RESP_GRID_OPERATORS: Final = "gridOperators"
RESP_IS_ZIP_CODE_VALID: Final = "isZipCodeValid"
RESP_ID: Final = "id"
RESP_NAME: Final = "name"
RESP_ENERGY_TYPE: Final = "energyType"
RESP_GRID_AREA_ID: Final = "gridAreaId"
RESP_BRAND_HOME: Final = "brandHome"
RESP_BRAND_BUSINESS: Final = "brandBusiness"

RESP_GRID_OPERATOR_NAME: Final = "gridOperatorName"
RESP_MAX_SAVING: Final = "maxSaving"
RESP_ANNUAL_RATE_RANGE: Final = "annualRateRange"
RESP_RATED_PRODUCTS: Final = "ratedProducts"
RESP_RANGE_FROM: Final = "from"
RESP_RANGE_TO: Final = "to"

RESP_DEFAULT_ID: Final = "defaultId"
RESP_PRODUCT_DATA: Final = "productData"
RESP_MAIN_ID: Final = "mainId"
RESP_MAIN_ASSOCIATION_ID: Final = "mainAssociationId"

RESP_PRODUCT_ID: Final = "id"
RESP_ASSOCIATION_ID: Final = "associationId"
RESP_PRODUCT_TYPE: Final = "productType"
RESP_PRODUCT_NAME: Final = "productName"
RESP_BRAND_ID: Final = "brandId"
RESP_BRAND_NAME: Final = "brandName"
RESP_SUPPLIER_NAME: Final = "supplierName"
RESP_ANNUAL_GROSS_RATE: Final = "annualGrossRate"
RESP_ANNUAL_SAVING: Final = "annualSaving"
RESP_ANNUAL_RISING: Final = "annualRising"
RESP_AVERAGE_TOTAL_PRICE_CT_KWH: Final = "averageTotalPriceInCentKWh"
RESP_AVERAGE_ENERGY_PRICE_CT_KWH: Final = "averageEnergyPriceInCentKWh"
RESP_BASE_RATE_WITH_TAX: Final = "baseRateWithTax"
RESP_COMPARISON: Final = "comparison"
RESP_CONTRACT_TERM_INFO: Final = "contractTermInfo"
RESP_CHANGE_LINK: Final = "changeLink"
RESP_PRODUCT_PROPERTIES: Final = "productProperties"
RESP_ENERGY_SOURCES: Final = "energySources"
RESP_VERSION_STATE: Final = "versionState"

RESP_PRICE_GUARANTEE_MONTHS: Final = "priceGuaranteeMonths"
RESP_PRICE_GUARANTEE_UNTIL: Final = "priceGuaranteeUntil"
RESP_PRICE_GUARANTEE_TYPE: Final = "priceGuaranteeType"
RESP_LAST_DATE_CHANGE: Final = "lastDateChange"
RESP_LINK: Final = "link"
RESP_PROP_NAME: Final = "propName"
RESP_DEFAULT_PROP_NAME: Final = "defaultPropName"
RESP_RENEWABLE: Final = "RENEWABLE"

# --------------------------------------------------------------------------
# Error envelope
# --------------------------------------------------------------------------
RESP_ERR_CODE: Final = "errCode"
RESP_ERR_DESCRIPTION: Final = "errDescription"
RESP_STATUS: Final = "status"
RESP_PAYLOAD: Final = "payload"

ERR_FIELD: Final = "field"
ERR_MESSAGE: Final = "message"

#: The gateway's generic server error. Unsupported parameter combinations are
#: reported this way instead of with a descriptive message.
ERR_RCGATE_UNK01: Final = "RCGATE_UNK01"
