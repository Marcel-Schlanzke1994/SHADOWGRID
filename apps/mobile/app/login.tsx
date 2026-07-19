import { useState } from "react";
import { Text, TextInput, TouchableOpacity, View } from "react-native";
import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import { i18n as shadowgridI18n } from "@shadowgrid/i18n";
import { signIn } from "../src/api";
import { colors, styles } from "../src/theme";

export default function Login() {
  const { t } = useTranslation(undefined, { i18n: shadowgridI18n });
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const submit = async () => {
    setError("");
    try {
      await signIn(email, password);
      router.replace("/(tabs)");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("errorTitle"));
    }
  };
  return (
    <View style={[styles.screen, { justifyContent: "center" }]}>
      <Text style={{ color: colors.gold, letterSpacing: 3 }}>
        {t("appName")}
      </Text>
      <Text accessibilityRole="header" style={styles.title}>
        {t("authWelcome")}
      </Text>
      <Text style={styles.subtitle}>{t("fictionalNotice")}</Text>
      <TextInput
        accessibilityLabel={t("email")}
        autoCapitalize="none"
        autoComplete="email"
        keyboardType="email-address"
        value={email}
        onChangeText={setEmail}
        style={styles.input}
      />
      <TextInput
        accessibilityLabel={t("password")}
        autoComplete="current-password"
        secureTextEntry
        value={password}
        onChangeText={setPassword}
        style={styles.input}
      />
      {error ? (
        <Text accessibilityRole="alert" style={{ color: colors.danger }}>
          {error}
        </Text>
      ) : null}
      <TouchableOpacity
        accessibilityRole="button"
        style={styles.button}
        onPress={() => void submit()}
      >
        <Text style={styles.buttonText}>{t("signIn")}</Text>
      </TouchableOpacity>
    </View>
  );
}
