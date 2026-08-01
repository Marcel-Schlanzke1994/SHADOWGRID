import { ScrollView, Text, View } from "react-native";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  formatCurrency,
  i18n as shadowgridI18n,
  translateGameValue,
} from "@shadowgrid/i18n";
import type { Business } from "@shadowgrid/shared-types";
import { api } from "../../src/api";
import { styles } from "../../src/theme";

export default function Businesses() {
  const { t, i18n } = useTranslation(undefined, { i18n: shadowgridI18n });
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
            {translateGameValue(item.business_type)} · {t("level")} {item.level}
          </Text>
          <Text style={styles.value}>
            {formatCurrency(item.revenue - item.operating_cost, i18n.language)}
          </Text>
          <Text style={styles.text}>
            {t("compliance")}: {item.compliance}/100
          </Text>
        </View>
      ))}
    </ScrollView>
  );
}
