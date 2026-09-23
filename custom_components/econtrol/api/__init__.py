"""API layer of the E-Control Tarifkalkulator integration.

The package exposes a small factory instead of the concrete clients, so the
coordinator never needs to know which data source it talks to.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import aiohttp

from ..const import (
    CONF_PASSWORD,
    CONF_SOURCE,
    CONF_URL,
    CONF_USERNAME,
    SOURCE_PARTNER,
)
from .base import TarifkalkulatorClient
from .client_partner import PartnerTarifkalkulatorClient
from .client_public import PublicTarifkalkulatorClient
from .constants import DEFAULT_LOCALE, DEFAULT_TIMEOUT, PARTNER_DEVELOPMENT_URL
from .errors import (
    EControlApiError,
    EControlAuthError,
    EControlConnectionError,
    EControlError,
    EControlValidationError,
)
from .models import GridOperator, Offer, ProductOption, RateRequest, RateResult

__all__ = [
    "EControlApiError",
    "EControlAuthError",
    "EControlConnectionError",
    "EControlError",
    "EControlValidationError",
    "GridOperator",
    "Offer",
    "PartnerTarifkalkulatorClient",
    "ProductOption",
    "PublicTarifkalkulatorClient",
    "RateRequest",
    "RateResult",
    "TarifkalkulatorClient",
    "create_client",
]


def create_client(
    session: aiohttp.ClientSession, config: Mapping[str, Any]
) -> TarifkalkulatorClient:
    """Build the adapter for the configured data source.

    :param session: the Home Assistant managed aiohttp session.
    :param config: the config entry data (and options).
    """
    source = config.get(CONF_SOURCE)
    if source == SOURCE_PARTNER:
        url = config.get(CONF_URL)
        return PartnerTarifkalkulatorClient(
            session,
            username=str(config.get(CONF_USERNAME, "")),
            password=str(config.get(CONF_PASSWORD, "")),
            base_url=str(url) if url else None,
            development=url == PARTNER_DEVELOPMENT_URL,
        )
    return PublicTarifkalkulatorClient(
        session,
        locale=DEFAULT_LOCALE,
        timeout=DEFAULT_TIMEOUT,
    )
