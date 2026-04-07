from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    db_host: str
    db_port: int = 3306
    db_user: str
    db_password: str
    db_name: str

    # WhatsApp
    wa_product_id: str
    wa_token: str
    wa_phone_id: str
    wa_base_url: str = "https://gate.whapi.cloud"

    # OpenAI
    openai_api_key: str

    # Google Drive
    google_service_account_json: str = "./google_service_account.json"
    google_drive_folder_id: str

    # App
    frontend_url: str = "*"

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
