import { useState } from "react";
import {
  I18nManager,
  ScrollView,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import {
  i18n as shadowgridI18n,
  isRtlLocale,
  localeMetadata,
  selectableLocales,
  setLocale,
  type Locale,
} from "@shadowgrid/i18n";
import { signOut } from "../../src/api";
import { styles } from "../../src/theme";

const localeName = (locale: Locale): string => {
  if (locale === "en-XA") return "English — expanded pseudo-locale";
  if (locale === "ar-XB") return "العربية — RTL pseudo-locale";
  return locale in localeMetadata
    ? localeMetadata[locale as keyof typeof localeMetadata].name
    : locale;
};

export default function Settings() {
  const { t, i18n } = useTranslation(undefined, { i18n: shadowgridI18n });
  const [restartRequired, setRestartRequired] = useState(false);
  const selectLanguage = async (locale: Locale): Promise<void> => {
    const rtl = isRtlLocale(locale);
    await setLocale(locale);
    if (I18nManager.isRTL !== rtl) {
      I18nManager.allowRTL(true);
      I18nManager.forceRTL(rtl);
      setRestartRequired(true);
    }
  };
  const logout = async () => {
    await signOut();
    router.replace("/login");
  };
  return (
    <ScrollView contentContainerStyle={styles.screen}>
      <Text accessibilityRole="header" style={styles.title}>
        {t("settingsTitle")}
      </Text>
      <Text accessibilityRole="header" style={styles.sectionTitle}>
        {t("language")}
      </Text>
      <View style={styles.list} accessibilityRole="radiogroup">
        {selectableLocales.map((locale) => (
          <TouchableOpacity
            accessibilityRole="radio"
            accessibilityState={{ selected: i18n.language === locale }}
            key={locale}
            onPress={() => void selectLanguage(locale)}
            style={styles.button}
          >
            <Text style={styles.buttonText}>
              {localeName(locale)} ({locale})
            </Text>
          </TouchableOpacity>
        ))}
      </View>
      {restartRequired && (
        <Text style={styles.muted}>{t("languageRestartRequired")}</Text>
      )}
      <TouchableOpacity style={styles.button} onPress={() => void logout()}>
        <Text style={styles.buttonText}>{t("signOut")}</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}
