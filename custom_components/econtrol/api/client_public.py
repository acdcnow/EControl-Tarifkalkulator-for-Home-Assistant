"""Adapter for the public tariff calculator REST proxy.

This adapter talks to the very same REST services that the public calculator
at https://www.e-control.at/tarifkalkulator uses. Those services are reachable
**without any account**: a plain request without cookies or credentials answers
with ``HTTP 200`` for the resources this integration needs.

It is therefore an *unofficial* interface: it is not covered by the documented
partner interface and it may change whenever E-Control updates the frontend.
See the project wiki for the verification log.
"""

from __future__ import annotations

from typing import ClassVar

from . import constants as c
from .base import TarifkalkulatorClient


class PublicTarifkalkulatorClient(TarifkalkulatorClient):
    """Client for ``https://www.e-control.at/o/rc-public-rest``."""

    source: ClassVar[str] = "public"

    @property
    def base_url(self) -> str:
        """Return the public REST proxy base URL."""
        return c.PUBLIC_BASE_URL
