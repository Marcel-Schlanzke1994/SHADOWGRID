import { ScrollView, Text, View } from "react-native";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { i18n as shadowgridI18n } from "@shadowgrid/i18n";
import type { Organization } from "@shadowgrid/shared-types";
import { api } from "../../src/api";
import { styles } from "../../src/theme";

export default function Organizations() {
  const { t } = useTranslation(undefined, { i18n: shadowgridI18n });
  const query = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api.get<Organization[]>("/organizations"),
  });
  return (
    <ScrollView contentContainerStyle={styles.screen}>
      <Text accessibilityRole="header" style={styles.title}>
        {t("organizationTitle")}
      </Text>
      {query.data?.map((item) => (
        <View style={styles.card} key={item.id}>
          <Text style={styles.cardTitle}>{item.name}</Text>
          <Text style={styles.muted}>
            {item.tag} · {item.archetype.replaceAll("_", " ")}
          </Text>
          <Text style={styles.text}>
            {t("members", { count: item.member_count })}
          </Text>
          <Text style={styles.text}>
            {t("stability")}: {item.stability}/100
          </Text>
        </View>
      ))}
    </ScrollView>
  );
}
