from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    upstage_api_key: str = Field(alias="UPSTAGE_API_KEY")
    upstage_base_url: AnyHttpUrl = Field(default="https://api.upstage.ai/v1", alias="UPSTAGE_BASE_URL")
    upstage_model: str = Field(default="solar-pro3", alias="UPSTAGE_MODEL")
    pathsdog_mcp_url: AnyHttpUrl = Field(default="https://jobs.pathsdog.com/mcp", alias="PATHSDOG_MCP_URL")
    ai_server_host: str = Field(default="0.0.0.0", alias="AI_SERVER_HOST")
    ai_server_port: int = Field(default=8000, alias="AI_SERVER_PORT")
