"""Exceptions raised by the E-Control Tarifkalkulator API adapters.

The integration catches :class:`EControlError` in the coordinator and maps it
onto :class:`homeassistant.helpers.update_coordinator.UpdateFailed`, so the
HTTP details of the transport layer never leak into the Home Assistant core.
"""

from __future__ import annotations


class EControlError(Exception):
    """Base class for every error raised by this integration's API layer."""


class EControlConnectionError(EControlError):
    """The service could not be reached (DNS, TCP, TLS or timeout)."""


class EControlAuthError(EControlError):
    """The supplied credentials were rejected (HTTP 401/403)."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        """Initialise the error."""
        super().__init__(message)
        self.status = status


class EControlValidationError(EControlError):
    """The request was semantically rejected (HTTP 4xx).

    The E-Control gateway answers validation problems with an envelope such as::

        {
          "errCode": "SEAR_V_999",
          "status": 422,
          "errDescription": "Generic validation Error.",
          "payload": "[{\\"field\\":\\"comparisonOptions\\",
                       \\"errorKey\\":\\"VAL_ERR_004\\",
                       \\"message\\":\\"Required argument missing\\"}]",
          "uuid": "..."
        }

    :attr:`field_errors` exposes the decoded ``payload`` entries.
    """

    def __init__(
        self,
        message: str,
        *,
        err_code: str | None = None,
        status: int | None = None,
        field_errors: tuple[tuple[str, str], ...] = (),
    ) -> None:
        """Initialise the error."""
        super().__init__(message)
        self.err_code = err_code
        self.status = status
        self.field_errors = field_errors


class EControlApiError(EControlError):
    """The service answered with a server side error (HTTP 5xx).

    ``RCGATE_UNK01`` is the gateway's generic "unknown error" and is returned
    for several combinations of parameters that the backend does not support
    (for example the electricity feed-in comparison on some grid areas).
    """

    def __init__(
        self,
        message: str,
        *,
        err_code: str | None = None,
        status: int | None = None,
    ) -> None:
        """Initialise the error."""
        super().__init__(message)
        self.err_code = err_code
        self.status = status
