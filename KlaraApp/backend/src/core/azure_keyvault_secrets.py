"""Azure Key Vault secrets integration."""

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from src.configs.config import settings
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()


_client = None


def get_keyvault_client(vault_url: str) -> SecretClient:
    """Get or create Azure Key Vault client."""
    global _client
    if _client is None:
        credential = DefaultAzureCredential()
        _client = SecretClient(vault_url=vault_url, credential=credential)
    return _client


async def get_secret(vault_url: str, secret_name: str) -> str:
    """Retrieve a secret from Azure Key Vault."""
    client = get_keyvault_client(vault_url)
    secret = client.get_secret(secret_name)
    return secret.value
