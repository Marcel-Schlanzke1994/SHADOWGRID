from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import TypedDict


class LocaleManifest(TypedDict):
    sourceLocale: str
    requiredLocales: list[str]
    regionalOverlays: dict[str, list[str]]


class UnsupportedLocaleError(ValueError):
    """Raised instead of silently serving source-language content."""


LOCALES_ROOT = Path(__file__).resolve().parents[3] / "packages" / "i18n" / "locales"
EMAIL_CATALOG_KEYS = (
    "emailVerifySubject",
    "emailVerifyBody",
    "emailResetSubject",
    "emailResetBody",
)


@lru_cache(maxsize=1)
def localization_manifest() -> LocaleManifest:
    with (LOCALES_ROOT / "manifest.json").open(encoding="utf-8") as handle:
        return json.load(handle)  # type: ignore[no-any-return]


def normalize_locale(value: str, available: tuple[str, ...]) -> str:
    requested = value.strip().replace("_", "-").lower()
    exact = next((locale for locale in available if locale.lower() == requested), None)
    if exact is not None:
        return exact
    language = requested.split("-", maxsplit=1)[0]
    primary = next(
        (locale for locale in available if locale.lower().split("-", maxsplit=1)[0] == language),
        None,
    )
    if primary is None:
        raise UnsupportedLocaleError(f"unsupported locale: {value}")
    return primary


def normalize_account_locale(value: str) -> str:
    return normalize_locale(value, account_email_locales())


@lru_cache(maxsize=1)
def account_email_locales() -> tuple[str, ...]:
    available: list[str] = []
    for locale in localization_manifest()["requiredLocales"]:
        coverage_path = LOCALES_ROOT / locale / "coverage.json"
        with coverage_path.open(encoding="utf-8") as handle:
            coverage: dict[str, object] = json.load(handle)
        scopes = coverage.get("scopes")
        email_status = scopes.get("email") if isinstance(scopes, dict) else None
        if email_status == "in_game_approved" or (
            locale in {"en", "de"} and email_status == "human_translated"
        ):
            available.append(locale)
    return tuple(available)


@lru_cache(maxsize=36)
def load_auth_catalog(locale: str) -> dict[str, str]:
    normalized = normalize_account_locale(locale)
    path = LOCALES_ROOT / normalized / "auth.json"
    with path.open(encoding="utf-8") as handle:
        catalog: dict[str, str] = json.load(handle)
    missing = [key for key in EMAIL_CATALOG_KEYS if not catalog.get(key)]
    if missing:
        raise UnsupportedLocaleError(
            f"email catalog for {normalized} is incomplete: {','.join(missing)}"
        )
    return catalog
