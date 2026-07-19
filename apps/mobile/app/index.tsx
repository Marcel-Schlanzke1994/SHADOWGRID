import { useEffect } from "react";
import { ActivityIndicator, View } from "react-native";
import { router } from "expo-router";
import { restoreSession } from "../src/api";
import { colors } from "../src/theme";

export default function Index() {
  useEffect(() => {
    void restoreSession().then((ok) =>
      router.replace(ok ? "/(tabs)" : "/login"),
    );
  }, []);
  return (
    <View
      style={{
        flex: 1,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: colors.background,
      }}
    >
      <ActivityIndicator color={colors.gold} size="large" />
    </View>
  );
}
