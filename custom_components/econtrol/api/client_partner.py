"""Adapter for the documented partner interface of the tariff calculator.

E-Control hands out a username and password on request
(``tarifkalkulator@e-control.at``). The interface is documented at
https://api-dev.e-control.at/rc-doc/ which is itself protected by the same
credentials.

.. note::

   Unlike the public proxy, this interface could not be exercised during
   development, because the documentation and every resource answer with
   ``HTTP 401`` without an account. The implementation therefore reuses the
   resource paths of the public proxy, which the E-Control documentation
   describes as "the REST services of the Tarifkalkulator", and authenticates
   with HTTP Basic auth.

   Everything that could be verified from the outside is verified:
   ``/rc/1.0`` and ``/rc-doc`` require credentials, the development host is
   ``api-dev.e-control.at`` and the production host is ``api.e-control.at``.

   *Used at your own risk:* the acceptance of the E-Control terms of use
   ("Nutzungsbedingungen", especially point 3 "Nutzungsumfang") is the
   responsibility of the user. If the resource paths differ, the integration
   reports the API's own error message, and the ``public`` source can be used
   as a fallback.
"""

from __future__ import annotations

from typing import Any, ClassVar

import aiohttp

from . import constants as c
from .base import TarifkalkulatorClient


class PartnerTarifkalkulatorClient(TarifkalkulatorClient):
    """Client for the credential protected partner interface."""

    source: ClassVar[str] = "partner"

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        username: str,
        password: str,
        development: bool = False,
        base_url: str | None = None,
        locale: str = c.DEFAULT_LOCALE,
        timeout: int = c.DEFAULT_TIMEOUT,
    ) -> None:
        """Initialise the client."""
        super().__init__(session, locale=locale, timeout=timeout)
        self._username = username
        self._password = password
        self._base_url = base_url or (
            c.PARTNER_DEVELOPMENT_URL if development else c.PARTNER_PRODUCTION_URL
        )

    @property
    def base_url(self) -> str:
        """Return the configured partner base URL."""
        return self._base_url

    def _request_kwargs(self) -> dict[str, Any]:
        """Authenticate every request with HTTP Basic auth."""
        return {"auth": aiohttp.BasicAuth(self._username, self._password)}
