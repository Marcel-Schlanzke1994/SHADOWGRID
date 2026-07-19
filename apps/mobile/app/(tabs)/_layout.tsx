import { Tabs } from "expo-router";
import { useTranslation } from "react-i18next";
import { i18n as shadowgridI18n } from "@shadowgrid/i18n";
import { colors } from "../../src/theme";

export default function TabsLayout() {
  const { t } = useTranslation(undefined, { i18n: shadowgridI18n });
  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: colors.surface },
        headerTintColor: colors.text,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
        },
        tabBarActiveTintColor: colors.gold,
        tabBarInactiveTintColor: colors.muted,
      }}
    >
      <Tabs.Screen name="index" options={{ title: t("navCommand") }} />
      <Tabs.Screen name="businesses" options={{ title: t("navBusinesses") }} />
      <Tabs.Screen name="operations" options={{ title: t("navOperations") }} />
      <Tabs.Screen
        name="organization"
        options={{ title: t("navOrganization") }}
      />
      <Tabs.Screen name="settings" options={{ title: t("navSettings") }} />
    </Tabs>
  );
}
