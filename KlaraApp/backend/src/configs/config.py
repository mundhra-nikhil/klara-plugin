from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
import json


class Settings(BaseSettings):
    # Application
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Azure AD
    azure_ad_tenant_id: str = ""
    azure_ad_client_id: str = ""
    azure_ad_client_secret: str = ""
    azure_ad_authority: str = ""

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-4"
    # Vision-capable deployment (gpt-4o) used for rendered-layout rules. Same
    # resource/key as the text deployment — only the model differs.
    azure_openai_vision_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-02-15-preview"

    # Azure Blob Storage
    azure_storage_connection_string: str = ""
    azure_storage_container_prefix: str = "grss-docs"

    # Microsoft Graph Integration
    microsoft_tenant_id: str = ""
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_redirect_uri: str = "http://localhost:3000/auth/microsoft/callback"
    microsoft_authority: str = "https://login.microsoftonline.com/common"

    # Claude via AWS Bedrock (primary QC analysis engine).
    # When aws_access_key_id + aws_secret_access_key are set, the QC engine
    # routes analysis to Claude on Bedrock instead of the Azure OpenAI path.
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""
    aws_region: str = "us-east-1"
    anthropic_model: str = "global.anthropic.claude-sonnet-4-6"

    # CORS
    cors_origins: str = '["http://localhost:5173"]'

    # Feature Flags
    enable_word_online: bool = False
    enable_sharepoint: bool = False
    enable_word_comments: bool = False
    enable_track_changes: bool = False

    @property
    def cors_origin_list(self) -> List[str]:
        return json.loads(self.cors_origins)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


settings = Settings()
