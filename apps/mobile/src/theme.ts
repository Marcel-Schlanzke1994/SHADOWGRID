import { StyleSheet } from "react-native";

export const colors = {
  background: "#080a0d",
  surface: "#11151b",
  elevated: "#181e27",
  text: "#f3f0e7",
  muted: "#b9bec8",
  gold: "#f1cd79",
  border: "#384250",
  danger: "#ff626d",
};
export const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background, padding: 16, gap: 12 },
  title: { color: colors.text, fontSize: 30, fontWeight: "800" },
  subtitle: { color: colors.muted, fontSize: 16, lineHeight: 24 },
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: 16,
    gap: 8,
  },
  cardTitle: { color: colors.text, fontSize: 18, fontWeight: "700" },
  value: { color: colors.gold, fontSize: 22, fontWeight: "700" },
  text: { color: colors.text },
  muted: { color: colors.muted },
  input: {
    minHeight: 48,
    color: colors.text,
    backgroundColor: "#090c10",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    padding: 12,
  },
  button: {
    minHeight: 48,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 8,
    backgroundColor: colors.gold,
    padding: 12,
  },
  buttonText: { color: colors.background, fontWeight: "800" },
  list: { gap: 10, paddingBottom: 32 },
});
