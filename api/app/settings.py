from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_version: str = "0.1.0"
    api_key: str = ""
    asr_backend: str = "mock"
    bind_host: str = "127.0.0.1"
    bind_port: int = 18741
    max_upload_mb: int = 12
    max_duration_sec: int = 60
    rate_limit_max: int = 30
    rate_limit_window_sec: int = 600
    cors_origins: str = "https://1404kingstreet.com,http://127.0.0.1:18741,http://localhost:18741"
    presets_dir: str = "../schemas/presets"
    inventory_path: str = "../schemas/gilaki_inventory.json"
    allosaurus_lang: str = "ipa"

    @property
    def cors_origin_list(self) -> list[str]:
        return [part.strip() for part in self.cors_origins.split(",") if part.strip()]


settings = Settings()
