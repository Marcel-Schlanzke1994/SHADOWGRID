import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  ScrollView,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { createIdempotencyKey } from "@shadowgrid/api-client";
import { router } from "expo-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { formatNumber, i18n as shadowgridI18n } from "@shadowgrid/i18n";
import type {
  EngagementCommandCenter,
  EngagementGoalWindow,
  PlayerSession,
  Profile,
  SessionSummary,
} from "@shadowgrid/shared-types";
import { api } from "../../src/api";
import { colors, styles } from "../../src/theme";

export default function Dashboard() {
  const { t, i18n } = useTranslation(undefined, { i18n: shadowgridI18n });
  const query = useQuery({
    queryKey: ["profile"],
    queryFn: () => api.get<Profile>("/profiles/me"),
  });
  const initializeKey = useRef(createIdempotencyKey());
  const initializationStarted = useRef(false);
  const initialize = useMutation({
    mutationFn: () =>
      api.post<EngagementGoalWindow>(
        "/engagement/initialize",
        {},
        initializeKey.current,
      ),
  });
  useEffect(() => {
    if (query.data && !initializationStarted.current) {
      initializationStarted.current = true;
      initialize.mutate();
    }
    // The ref and idempotency key make the profile-dependent bootstrap one-shot.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.data]);
  const commandCenter = useQuery({
    queryKey: ["engagement-command-center"],
    queryFn: () =>
      api.get<EngagementCommandCenter>("/engagement/command-center"),
    enabled: initialize.isSuccess,
  });
  const sessionKey = useRef(`mobile:${createIdempotencyKey()}`);
  const session = useQuery({
    queryKey: ["engagement-session", sessionKey.current],
    queryFn: () =>
      api.post<PlayerSession>("/engagement/sessions", {
        client_session_key: sessionKey.current,
      }),
    enabled: initialize.isSuccess,
    refetchOnWindowFocus: false,
  });
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const finishSession = useMutation({
    mutationFn: (sessionId: string) =>
      api.post<SessionSummary>(`/engagement/sessions/${sessionId}/finish`, {
        decision_keys: [],
      }),
    onSuccess: setSummary,
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
      {(initialize.isPending || commandCenter.isLoading) && (
        <ActivityIndicator color={colors.gold} />
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
                {formatNumber(Number(value), i18n.language, 0)}
              </Text>
            </View>
          ))}
        </View>
      )}
      {commandCenter.data && (
        <View style={styles.list}>
          <Text accessibilityRole="header" style={styles.sectionTitle}>
            {t("engagementCommandOpportunities")}
          </Text>
          {commandCenter.data.opportunities.length === 0 && (
            <Text style={styles.muted}>{t("empty")}</Text>
          )}
          {commandCenter.data.opportunities.map((opportunity) => (
            <View
              style={styles.card}
              key={`${opportunity.source_type}-${opportunity.source_id}`}
            >
              <Text style={styles.muted}>
                {t(
                  opportunity.category === "urgent"
                    ? "engagementOpportunityUrgent"
                    : opportunity.category === "strategic"
                      ? "engagementOpportunityStrategic"
                      : "engagementOpportunityDiscoverable",
                )}
              </Text>
              <Text style={styles.cardTitle}>
                {opportunity.source_type === "plan"
                  ? opportunity.title
                  : t(opportunity.title)}
              </Text>
              <Text style={styles.text}>
                {opportunity.source_type === "plan"
                  ? opportunity.detail
                  : t(opportunity.detail)}
              </Text>
            </View>
          ))}
          <TouchableOpacity
            accessibilityRole="button"
            onPress={() => router.push("/engagement")}
            style={styles.secondaryButton}
          >
            <Text style={styles.secondaryButtonText}>
              {t("engagementManagePlans")}
            </Text>
          </TouchableOpacity>
        </View>
      )}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>{t("engagementSessionTitle")}</Text>
        {!summary && session.data && (
          <>
            <Text style={styles.text}>{t("engagementSessionDescription")}</Text>
            <TouchableOpacity
              accessibilityRole="button"
              disabled={finishSession.isPending}
              onPress={() => finishSession.mutate(session.data.id)}
              style={styles.button}
            >
              <Text style={styles.buttonText}>
                {t("engagementFinishSession")}
              </Text>
            </TouchableOpacity>
          </>
        )}
        {summary && (
          <View accessibilityLiveRegion="polite" style={styles.list}>
            <Text style={styles.text}>{t("engagementNaturalBreak")}</Text>
            <Text style={styles.muted}>
              {t("engagementSessionDuration", {
                minutes: Math.max(1, Math.round(summary.duration_seconds / 60)),
              })}
            </Text>
            <Text style={styles.text}>{t("engagementNoAutomaticMission")}</Text>
          </View>
        )}
      </View>
    </ScrollView>
  );
}
