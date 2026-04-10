"""Core DR sync logic for Key Vault secret replication.

This module is intentionally SDK-light so it can be tested locally without Azure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Protocol


class SecretClientProtocol(Protocol):
    """Protocol for source/destination secret clients."""

    def get_secret(self, name: str) -> str: ...

    def set_secret(self, name: str, value: str) -> None: ...

    def begin_delete_secret(self, name: str) -> None: ...


@dataclass
class ParsedEvent:
    """Normalized event model used by SyncEngine."""

    event_type: str
    secret_name: str


class InMemorySecretClient:
    """Simple dictionary-backed secret store for local tests."""

    def __init__(self, initial: Dict[str, str] | None = None) -> None:
        self._store: Dict[str, str] = initial.copy() if initial else {}

    def get_secret(self, name: str) -> str:
        if name not in self._store:
            raise KeyError(f"Secret '{name}' not found")
        return self._store[name]

    def set_secret(self, name: str, value: str) -> None:
        self._store[name] = value

    def begin_delete_secret(self, name: str) -> None:
        self._store.pop(name, None)

    @property
    def store(self) -> Dict[str, str]:
        return self._store


class SyncEngine:
    """Executes DR sync actions based on Key Vault event type."""

    EVENT_SECRET_CREATED = "Microsoft.KeyVault.SecretNewVersionCreated"
    EVENT_SECRET_DELETED = "Microsoft.KeyVault.SecretDeleted"

    def __init__(self, source_client: SecretClientProtocol, destination_client: SecretClientProtocol) -> None:
        self.source_client = source_client
        self.destination_client = destination_client

    def process(self, event: ParsedEvent) -> str:
        if event.event_type == self.EVENT_SECRET_CREATED:
            value = self.source_client.get_secret(event.secret_name)
            self.destination_client.set_secret(event.secret_name, value)
            return f"Synced secret '{event.secret_name}' to DR vault"

        if event.event_type == self.EVENT_SECRET_DELETED:
            self.destination_client.begin_delete_secret(event.secret_name)
            return f"Deleted secret '{event.secret_name}' from DR vault"

        return f"Ignored unsupported event type '{event.event_type}'"


def extract_secret_name(subject: str) -> str:
    """Extract secret name from Event Grid subject path.

    Example subject:
    /subscriptions/.../providers/Microsoft.KeyVault/vaults/mykv/secrets/my-secret
    """

    marker = "/secrets/"
    if marker not in subject:
        raise ValueError(f"Cannot parse secret name from subject: {subject}")
    return subject.split(marker, maxsplit=1)[1]


def parse_eventgrid_records(records: List[dict]) -> List[ParsedEvent]:
    """Convert raw Event Grid records into ParsedEvent list."""

    parsed: List[ParsedEvent] = []
    for event in records:
        event_type = event.get("eventType", "")
        subject = event.get("subject", "")

        if event_type == "Microsoft.EventGrid.SubscriptionValidationEvent":
            parsed.append(ParsedEvent(event_type=event_type, secret_name=""))
            continue

        secret_name = extract_secret_name(subject)
        parsed.append(ParsedEvent(event_type=event_type, secret_name=secret_name))

    return parsed
