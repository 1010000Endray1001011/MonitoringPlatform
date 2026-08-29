"""
Shared result shape for every notification provider — plain Python,
imported by both integrations/telegram and integrations/email so neither
has to import the other, and both hand back something apps.notifications
can treat identically regardless of which provider actually ran.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SendResult:
    success: bool
    # True only when retrying would be pointless — a bad chat_id, a
    # rejected email address, a malformed request. False (the default)
    # covers everything transient: a timeout, a 5xx, a dropped connection.
    permanent_error: bool = False
    error_message: str | None = None
    # Set only when the provider itself told us how long to wait (Telegram's
    # 429 responses carry this) — otherwise the caller picks its own backoff.
    retry_after: int | None = None
