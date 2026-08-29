"""Configuración del backend, vía variables de entorno / .env."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "mysql+pymysql://root:@localhost:3306/sismed_red"

    # Último recurso si el header del DBF no trae un codepage legible
    # (ver app/etl/dbf_reader.py — normalmente se autodetecta del header).
    dbf_encodings: tuple[str, ...] = ("cp1252", "cp850", "latin-1")


@lru_cache
def get_settings() -> Settings:
    return Settings()
