import unittest

from dr_sync.sync_engine import (
    InMemorySecretClient,
    ParsedEvent,
    SyncEngine,
    extract_secret_name,
    parse_eventgrid_records,
)


class SyncEngineTests(unittest.TestCase):
    def test_sync_on_new_version_created(self):
        source = InMemorySecretClient({"db-password": "super-secret-v2"})
        destination = InMemorySecretClient({"db-password": "old"})
        engine = SyncEngine(source, destination)

        msg = engine.process(
            ParsedEvent(
                event_type="Microsoft.KeyVault.SecretNewVersionCreated",
                secret_name="db-password",
            )
        )

        self.assertEqual(destination.store["db-password"], "super-secret-v2")
        self.assertIn("Synced secret", msg)

    def test_delete_on_secret_deleted(self):
        source = InMemorySecretClient({"unused": "x"})
        destination = InMemorySecretClient({"db-password": "secret"})
        engine = SyncEngine(source, destination)

        msg = engine.process(
            ParsedEvent(
                event_type="Microsoft.KeyVault.SecretDeleted",
                secret_name="db-password",
            )
        )

        self.assertNotIn("db-password", destination.store)
        self.assertIn("Deleted secret", msg)

    def test_unsupported_event_is_ignored(self):
        source = InMemorySecretClient({"s": "1"})
        destination = InMemorySecretClient()
        engine = SyncEngine(source, destination)

        msg = engine.process(ParsedEvent(event_type="Unknown.EventType", secret_name="s"))

        self.assertIn("Ignored unsupported event", msg)

    def test_extract_secret_name(self):
        subject = "/subscriptions/abc/resourceGroups/rg/providers/Microsoft.KeyVault/vaults/kv-dev/secrets/api-key"
        name = extract_secret_name(subject)
        self.assertEqual(name, "api-key")

    def test_parse_eventgrid_records(self):
        events = [
            {
                "eventType": "Microsoft.KeyVault.SecretNewVersionCreated",
                "subject": "/subscriptions/x/providers/Microsoft.KeyVault/vaults/a/secrets/one",
            },
            {
                "eventType": "Microsoft.KeyVault.SecretDeleted",
                "subject": "/subscriptions/x/providers/Microsoft.KeyVault/vaults/a/secrets/two",
            },
        ]

        parsed = parse_eventgrid_records(events)

        self.assertEqual(parsed[0].secret_name, "one")
        self.assertEqual(parsed[1].secret_name, "two")


if __name__ == "__main__":
    unittest.main()
