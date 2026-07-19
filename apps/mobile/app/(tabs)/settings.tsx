import { ScrollView, Text, TouchableOpacity } from "react-native";
import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import { i18n as shadowgridI18n } from "@shadowgrid/i18n";
import { signOut } from "../../src/api";
import { styles } from "../../src/theme";

export default function Settings() {
  const { t, i18n } = useTranslation(undefined, { i18n: shadowgridI18n });
  const toggle = () =>
    void i18n.changeLanguage(i18n.language.startsWith("de") ? "en" : "de");
  const logout = async () => {
    await signOut();
    router.replace("/login");
  };
  return (
    <ScrollView contentContainerStyle={styles.screen}>
      <Text accessibilityRole="header" style={styles.title}>
        {t("settingsTitle")}
      </Text>
      <TouchableOpacity style={styles.button} onPress={toggle}>
        <Text style={styles.buttonText}>
          {t("language")}: {i18n.language}
        </Text>
      </TouchableOpacity>
      <TouchableOpacity style={styles.button} onPress={() => void logout()}>
        <Text style={styles.buttonText}>{t("signOut")}</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}
