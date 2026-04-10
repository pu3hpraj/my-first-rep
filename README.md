# Azure Key Vault DR Sync (Event Grid + Azure Functions) - Safe Test Blueprint

This repository gives you a **safe way to learn and test** your DR sync design before touching your company Azure subscription.

## 1) What you are building

Your proposed event flow is correct:

1. Source Key Vault secret changes (`Create/Update/Delete`).
2. Event Grid emits events such as:
   - `Microsoft.KeyVault.SecretNewVersionCreated`
   - `Microsoft.KeyVault.SecretDeleted`
3. Event Grid pushes events to an Azure Function HTTP webhook.
4. Function parses payload and decides:
   - New version -> fetch from source KV and write to destination KV
   - Deleted -> delete from destination KV
5. Function logs success/failure and returns HTTP status.

## 2) How to test safely (without company account)

Use one of these options:

- **Best option**: personal Azure subscription (Free Trial / Pay-As-You-Go) in an isolated tenant.
- Create only two vaults (`kv-dev-src`, `kv-qa-dr`) and one Function App.
- Set budget alerts + low-cost SKU to cap risk.

## 3) Environment strategy (your dev -> qa DR mapping)

In your first phase:

- `dev` vault = source (primary)
- `qa` vault = destination (DR target for testing)

Later, scale with config:

- `dev -> qa`
- `stage -> prod-dr` (or any mapping you need)

## 4) Local testing in this repo

This repo includes a Python sync engine with two backends:

- `InMemorySecretClient` for safe local tests (no Azure needed).
- `AzureSecretClient` wrapper for real Azure Key Vault SDK when ready.

### Run local unit tests

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

## 5) Optional live test in personal Azure

1. Deploy Azure Function with HTTP trigger.
2. Add Event Grid subscription on source Key Vault to function webhook.
3. Set environment variables in Function App:
   - `SOURCE_VAULT_URL`
   - `DESTINATION_VAULT_URL`
4. Assign Managed Identity access to both vaults.
5. Create/update/delete a secret in source and validate destination behavior.

## 6) Event types handled

- `Microsoft.KeyVault.SecretNewVersionCreated` -> sync secret
- `Microsoft.KeyVault.SecretDeleted` -> delete secret
- `EventGrid.SubscriptionValidationEvent` -> handshake response

## 7) Security notes

- Do not log secret values.
- Use Managed Identity rather than client secrets.
- Restrict Event Grid endpoint with function keys and network controls.

