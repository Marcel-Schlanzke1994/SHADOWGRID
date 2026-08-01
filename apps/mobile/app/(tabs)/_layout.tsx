import { Tabs } from "expo-router";
import { useTranslation } from "react-i18next";
import { StyleSheet, View } from "react-native";
import { i18n as shadowgridI18n } from "@shadowgrid/i18n";
import { colors } from "../../src/theme";

function DockGlyph({
  focused,
  variant,
}: {
  focused: boolean;
  variant: number;
}) {
  const accent = focused ? colors.goldStrong : colors.muted;
  const technical = focused ? colors.cyan : colors.border;
  return (
    <View style={dockStyles.glyph} accessibilityElementsHidden>
      <View
        style={[
          dockStyles.glyphFrame,
          { borderColor: variant % 2 === 0 ? accent : technical },
          focused && dockStyles.glyphFrameFocused,
        ]}
      />
      <View style={[dockStyles.glyphCore, { backgroundColor: accent }]} />
      <View
        style={[
          dockStyles.glyphSignal,
          variant % 3 === 0 ? dockStyles.glyphSignalWide : null,
          { backgroundColor: technical },
        ]}
      />
    </View>
  );
}

const icon = (variant: number) =>
  function PremiumTabGlyph({ focused }: { focused: boolean }) {
    return <DockGlyph focused={focused} variant={variant} />;
  };

export default function TabsLayout() {
  const { t } = useTranslation(undefined, { i18n: shadowgridI18n });
  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: colors.carbon },
        headerTintColor: colors.text,
        headerShadowVisible: false,
        headerTitleStyle: {
          fontWeight: "800",
          letterSpacing: 0.8,
        },
        tabBarStyle: {
          position: "absolute",
          right: 10,
          bottom: 10,
          left: 10,
          height: 78,
          borderTopWidth: 1,
          borderWidth: 1,
          borderColor: colors.border,
          borderTopLeftRadius: 3,
          borderTopRightRadius: 18,
          borderBottomRightRadius: 3,
          borderBottomLeftRadius: 18,
          backgroundColor: colors.carbon,
          paddingTop: 8,
          paddingBottom: 7,
          shadowColor: "#000000",
          shadowOffset: { width: 0, height: 18 },
          shadowOpacity: 0.65,
          shadowRadius: 28,
          elevation: 18,
        },
        tabBarItemStyle: {
          minHeight: 58,
          borderRadius: 2,
        },
        tabBarLabelStyle: {
          fontSize: 9,
          fontWeight: "800",
          letterSpacing: 0.25,
          marginTop: 2,
        },
        tabBarActiveBackgroundColor: colors.surface,
        tabBarActiveTintColor: colors.goldStrong,
        tabBarInactiveTintColor: colors.muted,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{ title: t("navCommand"), tabBarIcon: icon(0) }}
      />
      <Tabs.Screen
        name="engagement"
        options={{ title: t("navEngagement"), tabBarIcon: icon(1) }}
      />
      <Tabs.Screen
        name="legacy"
        options={{ title: t("navLegacy"), tabBarIcon: icon(2) }}
      />
      <Tabs.Screen
        name="businesses"
        options={{ title: t("navBusinesses"), tabBarIcon: icon(3) }}
      />
      <Tabs.Screen
        name="operations"
        options={{ title: t("navOperations"), tabBarIcon: icon(4) }}
      />
      <Tabs.Screen
        name="multiplayer"
        options={{ title: t("navPvp"), tabBarIcon: icon(5) }}
      />
      <Tabs.Screen
        name="organization"
        options={{ title: t("navOrganization"), tabBarIcon: icon(6) }}
      />
      <Tabs.Screen
        name="settings"
        options={{ title: t("navSettings"), tabBarIcon: icon(7) }}
      />
    </Tabs>
  );
}

const dockStyles = StyleSheet.create({
  glyph: {
    width: 25,
    height: 20,
    alignItems: "center",
    justifyContent: "center",
  },
  glyphFrame: {
    position: "absolute",
    width: 20,
    height: 14,
    borderWidth: 1,
    borderTopLeftRadius: 1,
    borderTopRightRadius: 5,
    borderBottomRightRadius: 1,
    borderBottomLeftRadius: 5,
    transform: [{ skewX: "-7deg" }],
  },
  glyphFrameFocused: {
    borderWidth: 2,
    shadowColor: colors.cyan,
    shadowOpacity: 0.75,
    shadowRadius: 6,
  },
  glyphCore: {
    width: 4,
    height: 4,
    borderRadius: 1,
  },
  glyphSignal: {
    position: "absolute",
    right: 0,
    bottom: 0,
    width: 5,
    height: 1,
  },
  glyphSignalWide: {
    width: 9,
  },
});
