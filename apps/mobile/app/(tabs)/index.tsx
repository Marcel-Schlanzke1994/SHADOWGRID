import { ScrollView, Text, View } from "react-native";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { i18n as shadowgridI18n } from "@shadowgrid/i18n";
import type { Profile } from "@shadowgrid/shared-types";
import { api } from "../../src/api";
import { styles } from "../../src/theme";

export default function Dashboard() {
  const { t } = useTranslation(undefined, { i18n: shadowgridI18n });
  const query = useQuery({
    queryKey: ["profile"],
    queryFn: () => api.get<Profile>("/profiles/me"),
  });
  const p = query.data;
  return (
    <ScrollView contentContainerStyle={styles.screen}>
      <Text accessibilityRole="header" style={styles.title}>
        {t("commandTitle")}
      </Text>
      <Text style={styles.subtitle}>{t("commandSubtitle")}</Text>
      {query.isError && (
        <Text accessibilityRole="alert" style={styles.text}>
          {t("offlineBody")}
        </Text>
      )}
      {p && (
        <View style={styles.list}>
          {[
            [t("cash"), p.resources.cash],
            [t("capital"), p.resources.capital],
            [t("influence"), p.resources.influence],
            [t("intelligence"), p.resources.intelligence],
            [t("pressure"), p.investigation_pressure],
            [t("stability"), p.stability],
          ].map(([label, value]) => (
            <View style={styles.card} key={String(label)}>
              <Text style={styles.muted}>{label}</Text>
              <Text style={styles.value}>
                {new Intl.NumberFormat(undefined, {
                  maximumFractionDigits: 0,
                }).format(Number(value))}
              </Text>
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
}
