import { useState, type ChangeEvent } from "react";
import { useTranslation } from "react-i18next";
import {
  localeMetadata,
  selectableLocales,
  setLocale,
  type Locale,
} from "@shadowgrid/i18n";
import { client, useAuth } from "./auth";

interface LanguageSelectorProps {
  className?: string;
  compact?: boolean;
  id: string;
}

export function LanguageSelector({
  className = "",
  compact = false,
  id,
}: LanguageSelectorProps) {
  const { t, i18n } = useTranslation();
  const authenticated = useAuth((state) => state.status === "authenticated");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const selectedLocale =
    selectableLocales.find((locale) => locale === i18n.language) ?? "en";

  const changeLanguage = async (event: ChangeEvent<HTMLSelectElement>) => {
    const locale = event.currentTarget.value as Locale;
    setBusy(true);
    setFailed(false);
    try {
      await setLocale(locale);
      if (authenticated)
        await client.patch("/auth/me/locale", {
          locale,
        });
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className={`language-selector${compact ? " language-selector--compact" : ""}${className ? ` ${className}` : ""}`}
      data-language-selector
    >
      <span className="language-selector__glyph" aria-hidden="true">
        <svg viewBox="0 0 24 24" focusable="false">
          <circle cx="12" cy="12" r="8.5" />
          <path d="M3.8 12h16.4M12 3.5c2.5 2.5 3.7 5.3 3.7 8.5S14.5 18 12 20.5M12 3.5C9.5 6 8.3 8.8 8.3 12s1.2 6 3.7 8.5" />
        </svg>
      </span>
      <label className={compact ? "sr-only" : "language-selector__label"} htmlFor={id}>
        {t("language")}
      </label>
      <select
        id={id}
        aria-label={t("language")}
        aria-busy={busy}
        disabled={busy}
        value={selectedLocale}
        onChange={(event) => void changeLanguage(event)}
      >
        {selectableLocales.map((locale) => (
          <option value={locale} key={locale}>
            {locale in localeMetadata
              ? localeMetadata[locale as keyof typeof localeMetadata].name
              : locale} {`(${locale})`}
          </option>
        ))}
      </select>
      {failed && (
        <span className="sr-only" role="alert">
          {t("errorTitle")}
        </span>
      )}
    </div>
  );
}
