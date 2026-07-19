import { ScrollView, Text, View } from "react-native";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { i18n as shadowgridI18n } from "@shadowgrid/i18n";
import type { Operation } from "@shadowgrid/shared-types";
import { api } from "../../src/api";
import { styles } from "../../src/theme";

export default function Operations() {
  const { t } = useTranslation(undefined, { i18n: shadowgridI18n });
  const query = useQuery({
    queryKey: ["operations"],
    queryFn: () => api.get<Operation[]>("/operations"),
    refetchInterval: 15000,
  });
  return (
    <ScrollView contentContainerStyle={styles.screen}>
      <Text accessibilityRole="header" style={styles.title}>
        {t("operationsTitle")}
      </Text>
      <Text style={styles.subtitle}>{t("noExactChance")}</Text>
      {query.data?.map((item) => (
        <View style={styles.card} key={item.id}>
          <Text style={styles.cardTitle}>{item.target}</Text>
          <Text style={styles.muted}>
            {item.operation_type.replaceAll("_", " ")}
          </Text>
          <Text style={styles.text}>
            {t("status")}: {item.result ?? item.status}
          </Text>
        </View>
      ))}
    </ScrollView>
  );
}
