from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "3wagent"
    default_jurisdictions: tuple[str, ...] = ("US", "HK", "SG")
    llm_provider: str = "openai"
    llm_api_key: str | None = None
    llm_model: str = "gpt5.5"
    llm_base_url: str | None = None
    llm_temperature: float = 0.1

    openai_api_key: str | None = Field(default=None, exclude=True)
    openai_model: str | None = Field(default=None, exclude=True)
    openai_base_url: str | None = Field(default=None, exclude=True)
    openai_temperature: float | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def apply_legacy_openai_env(self) -> "Settings":
        if self.openai_api_key and not self.llm_api_key:
            self.llm_api_key = self.openai_api_key
        if self.openai_model and self.llm_model == "gpt5.5":
            self.llm_model = self.openai_model
        if self.openai_base_url and not self.llm_base_url:
            self.llm_base_url = self.openai_base_url
        if self.openai_temperature is not None and self.llm_temperature == 0.1:
            self.llm_temperature = self.openai_temperature
        return self


settings = Settings()
