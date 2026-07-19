import { ScrollView, Text, View } from "react-native";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { i18n as shadowgridI18n } from "@shadowgrid/i18n";
import type { Business } from "@shadowgrid/shared-types";
import { api } from "../../src/api";
import { styles } from "../../src/theme";

export default function Businesses() {
  const { t } = useTranslation(undefined, { i18n: shadowgridI18n });
  const query = useQuery({
    queryKey: ["businesses"],
    queryFn: () => api.get<Business[]>("/businesses"),
  });
  return (
    <ScrollView contentContainerStyle={styles.screen}>
      <Text accessibilityRole="header" style={styles.title}>
        {t("businessesTitle")}
      </Text>
      {query.data?.map((item) => (
        <View style={styles.card} key={item.id}>
          <Text style={styles.cardTitle}>{item.name}</Text>
          <Text style={styles.muted}>
            {item.business_type.replaceAll("_", " ")} · {t("level")}{" "}
            {item.level}
          </Text>
          <Text style={styles.value}>
            {new Intl.NumberFormat(undefined, {
              style: "currency",
              currency: "EUR",
              maximumFractionDigits: 0,
            }).format(item.revenue - item.operating_cost)}
          </Text>
          <Text style={styles.text}>
            {t("compliance")}: {item.compliance}/100
          </Text>
        </View>
      ))}
    </ScrollView>
  );
}
