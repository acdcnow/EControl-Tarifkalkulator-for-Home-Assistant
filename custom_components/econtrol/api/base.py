"""Transport layer shared by every E-Control Tarifkalkulator adapter.

The concrete adapters only differ in their base URL and their authentication,
so all HTTP handling, error mapping and response parsing lives here.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any, ClassVar, Final

import aiohttp

from . import constants as c
from .errors import (
    EControlApiError,
    EControlAuthError,
    EControlConnectionError,
    EControlError,
    EControlValidationError,
)
from .models import GridOperator, ProductOption, RateRequest, RateResult
from ..const import EnergyType, api_value

_LOGGER = logging.getLogger(__name__)

_AUTH_STATUSES: Final = frozenset({401, 403})
_JSON_CONTENT_TYPES: Final = ("application/json", "text/json", "text/plain")


class TarifkalkulatorClient(ABC):
    """Base class of the tariff calculator adapters.

    Subclasses provide :attr:`base_url` (and optionally authentication) and
    inherit the full, verified request/response handling.
    """

    #: Identifier of the data source, matches ``CONF_SOURCE`` values.
    source: ClassVar[str]

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        locale: str = c.DEFAULT_LOCALE,
        timeout: int = c.DEFAULT_TIMEOUT,
    ) -> None:
        """Initialise the client with a Home Assistant managed session."""
        self._session = session
        self._locale = locale
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    # ------------------------------------------------------------------
    # Subclass hooks
    # ------------------------------------------------------------------
    @property
    @abstractmethod
    def base_url(self) -> str:
        """Return the API base URL without a trailing slash."""

    def _request_kwargs(self) -> dict[str, Any]:
        """Return extra keyword arguments for every request (for example auth)."""
        return {}

    @property
    def _headers(self) -> dict[str, str]:
        """Return the headers sent with every request."""
        return {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "User-Agent": c.USER_AGENT,
        }

    def _params(self, **extra: Any) -> dict[str, Any]:
        """Return the query parameters of a request."""
        return {c.QUERY_LOCALE: self._locale, **extra}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def async_get_grid_operator(
        self, *, zip_code: str, energy_type: str
    ) -> GridOperator | None:
        """Resolve the grid operator of a postal code and energy type.

        The public interface answers with ``{"isZipCodeValid": true,
        "gridOperators": [...]}``. A postal code that serves several operators
        returns several entries; the first one is used and the ambiguity is
        logged, because the calculator frontend does the same.
        """
        payload = await self._async_request(
            "GET",
            c.PATH_GRID_OPERATORS,
            params=self._params(
                **{
                    c.QUERY_ZIP_CODE: str(zip_code),
                    c.QUERY_ENERGY_TYPE: api_value(energy_type),
                }
            ),
        )
        data = payload if isinstance(payload, dict) else {}
        entries = data.get(c.RESP_GRID_OPERATORS)
        operators = [
            operator
            for operator in (
                GridOperator.from_api(entry)
                for entry in (entries if isinstance(entries, list) else [])
            )
            if operator is not None
        ]
        if not operators:
            if data.get(c.RESP_IS_ZIP_CODE_VALID) is False:
                _LOGGER.debug(
                    "Postal code %s is not served for %s", zip_code, energy_type
                )
            return None
        if len(operators) > 1:
            _LOGGER.info(
                "Postal code %s is served by %d grid operators for %s; using %s",
                zip_code,
                len(operators),
                energy_type,
                operators[0].name,
            )
        return operators[0]

    async def async_get_products(
        self, request: RateRequest, *, brand_id: int
    ) -> tuple[ProductOption, ...]:
        """Return the products a brand offers for the request's energy type.

        The comparison product is mandatory for a rate request, so this is used
        to find a sensible default (``defaultId``) and to populate the product
        selector of the options flow.
        """
        payload = await self._async_request(
            "POST",
            c.PATH_PRODUCTS.format(
                brand_id=brand_id, segment=self.segment_for(request.energy_type)
            ),
            params=self._params(**{c.QUERY_INCLUDE_SMART_METER: "false"}),
            body=request.to_body(with_comparison=False),
        )
        data = payload if isinstance(payload, dict) else {}
        raw_products = data.get(c.RESP_PRODUCT_DATA)
        default_id = data.get(c.RESP_DEFAULT_ID)
        default_id = default_id if isinstance(default_id, int) else None
        return tuple(
            product
            for product in (
                ProductOption.from_api(entry, default_id=default_id)
                for entry in (raw_products if isinstance(raw_products, list) else [])
            )
            if product is not None
        )

    async def async_get_rates(self, request: RateRequest) -> RateResult:
        """Run a tariff comparison and return the parsed result."""
        payload = await self._async_request(
            "POST",
            c.PATH_RATE.format(energy_type=request.api_energy_type),
            params=self._params(**{c.QUERY_SMART_METER: "false"}),
            body=request.to_body(with_comparison=True),
        )
        return RateResult.from_api(
            payload,
            energy_type=request.energy_type,
            grid_operator_id=request.grid_operator_id,
            grid_area_id=request.grid_area_id,
            consumption_kwh=request.consumption_kwh,
            fetched_at=datetime.now(tz=UTC),
        )

    async def async_validate(
        self, *, zip_code: str, energy_type: str
    ) -> GridOperator | None:
        """Check that the endpoint answers and that the credentials work.

        Raises an :class:`EControlError` subclass when the request fails, so a
        config flow can translate the failure into a form error.
        """
        await self._async_get(c.PATH_UI_CONFIGURATION)
        return await self.async_get_grid_operator(
            zip_code=zip_code, energy_type=energy_type
        )

    async def async_close(self) -> None:
        """Release resources. The session belongs to Home Assistant and is kept."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def segment_for(energy_type: str) -> str:
        """Map an energy type onto its resource segment.

        ``power`` and ``power_feed_in`` share the ``power`` segment; only the
        ``energyType`` field of the body and the rate path differ.
        """
        return "gas" if energy_type == EnergyType.GAS else "power"

    # ------------------------------------------------------------------
    # HTTP core
    # ------------------------------------------------------------------
    async def _async_get(self, path: str) -> Any:
        """Perform a GET request."""
        return await self._async_request("GET", path, params=self._params())

    async def _async_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        """Perform a request and return the decoded JSON payload.

        Every transport and protocol error is translated into an
        :class:`EControlError` subclass.
        """
        url = f"{self.base_url}{path}"
        kwargs: dict[str, Any] = {
            "params": params,
            "headers": self._headers,
            "timeout": self._timeout,
            **self._request_kwargs(),
        }
        if body is not None:
            kwargs["json"] = body

        try:
            async with self._session.request(method, url, **kwargs) as response:
                text = await response.text()
                if response.status in _AUTH_STATUSES:
                    raise EControlAuthError(
                        f"Authentication failed with HTTP {response.status}",
                        status=response.status,
                    )
                if response.status >= 400:
                    self._raise_for_error(response.status, text)
                return self._decode(response.status, text)
        except EControlError:
            raise
        except aiohttp.ClientError as err:
            raise EControlConnectionError(f"Cannot reach {url}: {err}") from err
        except TimeoutError as err:
            raise EControlConnectionError(f"Timeout while calling {url}") from err

    @staticmethod
    def _decode(status: int, text: str) -> Any:
        """Decode a JSON response body."""
        if not text.strip():
            return {}
        try:
            return json.loads(text)
        except ValueError as err:
            raise EControlApiError(
                f"Response is not valid JSON (HTTP {status})", status=status
            ) from err

    @staticmethod
    def _raise_for_error(status: int, text: str) -> None:
        """Translate an HTTP error into the matching exception."""
        err_code: str | None = None
        description: str | None = None
        field_errors: tuple[tuple[str, str], ...] = ()

        try:
            envelope = json.loads(text)
        except ValueError:
            envelope = None

        if isinstance(envelope, dict):
            raw_code = envelope.get(c.RESP_ERR_CODE)
            raw_description = envelope.get(c.RESP_ERR_DESCRIPTION)
            err_code = raw_code if isinstance(raw_code, str) else None
            description = raw_description if isinstance(raw_description, str) else None
            field_errors = TarifkalkulatorClient._parse_field_errors(
                envelope.get(c.RESP_PAYLOAD)
            )

        message = description or f"HTTP {status}"
        if err_code:
            message = f"{message} ({err_code})"

        if status < 500:
            details = ", ".join(f"{field}: {text}" for field, text in field_errors)
            if details:
                message = f"{message} - {details}"
            raise EControlValidationError(
                message,
                err_code=err_code,
                status=status,
                field_errors=field_errors,
            )

        raise EControlApiError(message, err_code=err_code, status=status)

    @staticmethod
    def _parse_field_errors(payload: Any) -> tuple[tuple[str, str], ...]:
        """Decode the ``payload`` field of a validation error envelope.

        The gateway nests a JSON encoded list inside a string::

            "[{\\"field\\":\\"comparisonOptions.brandId\\",
               \\"message\\":\\"Required argument missing\\"}]"
        """
        if not isinstance(payload, str) or not payload.strip():
            return ()
        try:
            decoded = json.loads(payload)
        except ValueError:
            return ()
        if not isinstance(decoded, list):
            return ()
        errors: list[tuple[str, str]] = []
        for entry in decoded:
            if not isinstance(entry, dict):
                continue
            field = entry.get(c.ERR_FIELD)
            message = entry.get(c.ERR_MESSAGE)
            errors.append((str(field or "?"), str(message or "invalid")))
        return tuple(errors)
