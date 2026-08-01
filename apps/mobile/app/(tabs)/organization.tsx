import { ScrollView, Text, TouchableOpacity, View } from "react-native";
import { createIdempotencyKey } from "@shadowgrid/api-client";
import { i18n as shadowgridI18n, translateGameValue } from "@shadowgrid/i18n";
import type {
  Cartel,
  CartelChronicleEntry,
  CartelDelegation,
  CartelMember,
  CartelMembershipPause,
  Profile,
} from "@shadowgrid/shared-types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../../src/api";
import { styles } from "../../src/theme";

export default function Organizations() {
  const { t } = useTranslation(undefined, { i18n: shadowgridI18n });
  const queryClient = useQueryClient();
  const cartels = useQuery({
    queryKey: ["cartels"],
    queryFn: () => api.get<Cartel[]>("/cartels"),
  });
  const selected = cartels.data?.find((item) => item.my_role);
  const cartelId = selected?.id ?? "";
  const profile = useQuery({
    queryKey: ["profile"],
    queryFn: () => api.get<Profile>("/profiles/me"),
  });
  const members = useQuery({
    queryKey: ["cartels", cartelId, "members"],
    queryFn: () => api.get<CartelMember[]>(`/cartels/${cartelId}/members`),
    enabled: Boolean(cartelId),
  });
  const delegations = useQuery({
    queryKey: ["cartels", cartelId, "delegations"],
    queryFn: () =>
      api.get<CartelDelegation[]>(
        `/engagement/social/cartels/${cartelId}/delegations`,
      ),
    enabled: Boolean(cartelId),
  });
  const membershipPause = useQuery({
    queryKey: ["cartels", cartelId, "pause"],
    queryFn: () =>
      api.get<CartelMembershipPause | null>(
        `/engagement/social/cartels/${cartelId}/pause`,
      ),
    enabled: Boolean(cartelId),
  });
  const chronicle = useQuery({
    queryKey: ["cartels", cartelId, "chronicle"],
    queryFn: () =>
      api.get<CartelChronicleEntry[]>(
        `/engagement/social/cartels/${cartelId}/chronicle`,
      ),
    enabled: Boolean(cartelId),
  });
  const delegate = useMutation({
    mutationFn: (profileId: string) =>
      api.post<CartelDelegation>(
        `/engagement/social/cartels/${cartelId}/delegations`,
        {
          delegate_profile_id: profileId,
          role_key: "project_manager",
          duration_days: 7,
        },
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["cartels", cartelId, "delegations"],
      });
      await queryClient.invalidateQueries({
        queryKey: ["cartels", cartelId, "chronicle"],
      });
    },
  });
  const pause = useMutation({
    mutationFn: () =>
      api.post<CartelMembershipPause>(
        `/engagement/social/cartels/${cartelId}/pause`,
        { duration_days: 14, private_reason: "" },
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["cartels", cartelId, "pause"],
      });
    },
  });
  const resume = useMutation({
    mutationFn: () =>
      api.post<CartelMembershipPause>(
        `/engagement/social/cartels/${cartelId}/resume`,
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["cartels", cartelId, "pause"],
      });
    },
  });
  const error =
    cartels.isError ||
    members.isError ||
    delegations.isError ||
    membershipPause.isError ||
    chronicle.isError ||
    profile.isError ||
    delegate.isError ||
    pause.isError ||
    resume.isError;
  return (
    <ScrollView contentContainerStyle={styles.screen}>
      <Text accessibilityRole="header" style={styles.title}>
        {t("organizationTitle")}
      </Text>
      {error && (
        <Text accessibilityRole="alert" style={styles.text}>
          {t("offlineBody")}
        </Text>
      )}
      {cartels.data?.map((item) => (
        <View style={styles.card} key={item.id}>
          <Text style={styles.cardTitle}>{item.name}</Text>
          <Text style={styles.muted}>
            {item.tag} · {translateGameValue(item.archetype)}
          </Text>
          <Text style={styles.text}>
            {t("members", { count: item.member_count })}
          </Text>
          <Text style={styles.text}>
            {t("stability")}: {item.stability}/100
          </Text>
        </View>
      ))}
      {!selected && <Text style={styles.muted}>{t("empty")}</Text>}
      {selected && (
        <>
          <Text accessibilityRole="header" style={styles.sectionTitle}>
            {t("engagementAsyncCollaborationTitle")}
          </Text>
          <Text style={styles.subtitle}>
            {t("engagementAsyncCollaborationDescription")}
          </Text>
          {membershipPause.data ? (
            <TouchableOpacity
              accessibilityRole="button"
              disabled={resume.isPending}
              onPress={() => resume.mutate()}
              style={styles.secondaryButton}
            >
              <Text style={styles.secondaryButtonText}>
                {t("engagementResumeNow")}
              </Text>
            </TouchableOpacity>
          ) : (
            <TouchableOpacity
              accessibilityRole="button"
              disabled={pause.isPending}
              onPress={() => pause.mutate()}
              style={styles.secondaryButton}
            >
              <Text style={styles.secondaryButtonText}>
                {t("engagementStartPause")}
              </Text>
            </TouchableOpacity>
          )}
          <Text accessibilityRole="header" style={styles.sectionTitle}>
            {t("engagementDelegationsTitle")}
          </Text>
          {delegations.data?.map((item) => (
            <View style={styles.card} key={item.id}>
              <Text style={styles.cardTitle}>
                {translateGameValue(item.role_key)}
              </Text>
              <Text style={styles.muted}>{item.status}</Text>
            </View>
          ))}
          {members.data
            ?.filter((member) => member.profile_id !== profile.data?.id)
            .map((member) => (
              <View style={styles.card} key={member.profile_id}>
                <Text style={styles.cardTitle}>{member.codename}</Text>
                <Text style={styles.muted}>
                  {translateGameValue(member.role)}
                </Text>
                <TouchableOpacity
                  accessibilityRole="button"
                  disabled={delegate.isPending}
                  onPress={() => delegate.mutate(member.profile_id)}
                  style={styles.button}
                >
                  <Text style={styles.buttonText}>
                    {t("engagementCreateDelegation")}
                  </Text>
                </TouchableOpacity>
              </View>
            ))}
          <Text accessibilityRole="header" style={styles.sectionTitle}>
            {t("engagementCartelChronicleTitle")}
          </Text>
          {chronicle.data?.map((entry) => (
            <View style={styles.card} key={entry.id}>
              <Text style={styles.cardTitle}>{t(entry.title_key)}</Text>
              <Text style={styles.text}>{t(entry.body_key)}</Text>
            </View>
          ))}
        </>
      )}
    </ScrollView>
  );
}
