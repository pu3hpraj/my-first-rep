"""Azure Functions HTTP webhook for Event Grid -> Key Vault DR sync.

This file can be deployed as an Azure Function. Local unit tests focus on dr_sync/sync_engine.py.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import azure.functions as func

from dr_sync.sync_engine import ParsedEvent, SyncEngine, parse_eventgrid_records

try:
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient
except ImportError:  # pragma: no cover - only needed in Azure runtime/local with full deps
    DefaultAzureCredential = None
    SecretClient = None


class AzureSecretClient:
    """Adapter around azure.keyvault.secrets.SecretClient."""

    def __init__(self, vault_url: str) -> None:
        if DefaultAzureCredential is None or SecretClient is None:
            raise RuntimeError("Azure SDK packages are not installed. See requirements.txt")
        credential = DefaultAzureCredential()
        self._client = SecretClient(vault_url=vault_url, credential=credential)

    def get_secret(self, name: str) -> str:
        return self._client.get_secret(name).value

    def set_secret(self, name: str, value: str) -> None:
        self._client.set_secret(name, value)

    def begin_delete_secret(self, name: str) -> None:
        poller = self._client.begin_delete_secret(name)
        poller.wait()


def _build_engine_from_env() -> SyncEngine:
    source_vault_url = os.environ["SOURCE_VAULT_URL"]
    destination_vault_url = os.environ["DESTINATION_VAULT_URL"]

    source_client = AzureSecretClient(source_vault_url)
    destination_client = AzureSecretClient(destination_vault_url)

    return SyncEngine(source_client=source_client, destination_client=destination_client)


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Received Event Grid webhook request")

    try:
        body: Any = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON payload", status_code=400)

    if not isinstance(body, list):
        return func.HttpResponse("Expected Event Grid array payload", status_code=400)

    parsed_events = parse_eventgrid_records(body)

    # Handle Event Grid validation handshake
    if len(body) == 1 and body[0].get("eventType") == "Microsoft.EventGrid.SubscriptionValidationEvent":
        validation_code = body[0].get("data", {}).get("validationCode")
        return func.HttpResponse(
            json.dumps({"validationResponse": validation_code}),
            status_code=200,
            mimetype="application/json",
        )

    engine = _build_engine_from_env()
    results: list[str] = []

    for event in parsed_events:
        if event.event_type == "Microsoft.EventGrid.SubscriptionValidationEvent":
            continue

        result = engine.process(ParsedEvent(event_type=event.event_type, secret_name=event.secret_name))
        logging.info(result)
        results.append(result)

    return func.HttpResponse(json.dumps({"results": results}), status_code=200, mimetype="application/json")
