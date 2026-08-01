import { useEffect, useRef } from "react";
import {
  ActivityIndicator,
  ScrollView,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { zodResolver } from "@hookform/resolvers/zod";
import { createIdempotencyKey } from "@shadowgrid/api-client";
import { i18n as shadowgridI18n, translateGameValue } from "@shadowgrid/i18n";
import type {
  AdaptiveHelpOffer,
  DoctrineCatalogItem,
  DoctrineState,
  EngagementGoal,
  EngagementGoalWindow,
  EngagementSettings,
  MasteryProgress,
  Mentorship,
  OpenPlan,
  Profile,
  ReturnBriefing,
} from "@shadowgrid/shared-types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Controller, useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";
import { api } from "../../src/api";
import { colors, styles } from "../../src/theme";

const planSchema = z.object({
  title: z.string().trim().min(2).max(140),
  next_step: z.string().trim().min(2).max(280),
});
type PlanInput = z.infer<typeof planSchema>;

const mentorshipSchema = z.object({
  mentee_profile_id: z.string().uuid(),
});
type MentorshipInput = z.infer<typeof mentorshipSchema>;

const goalCategoryKey = {
  economic: "engagementCategoryEconomic",
  social: "engagementCategorySocial",
  exploration: "engagementCategoryExploration",
  risk: "engagementCategoryRisk",
  long_term: "engagementCategoryLongTerm",
  season: "engagementCategorySeason",
} as const;

function ErrorNotice() {
  const { t } = useTranslation(undefined, { i18n: shadowgridI18n });
  return (
    <Text accessibilityRole="alert" style={styles.text}>
      {t("offlineBody")}
    </Text>
  );
}

export default function Engagement() {
  const { t } = useTranslation(undefined, { i18n: shadowgridI18n });
  const queryClient = useQueryClient();
  const initializeKey = useRef(createIdempotencyKey());
  const initialize = useMutation({
    mutationFn: () =>
      api.post<EngagementGoalWindow>(
        "/engagement/initialize",
        {},
        initializeKey.current,
      ),
  });
  useEffect(() => {
    initialize.mutate();
    // The stable idempotency key makes this bootstrap safe under StrictMode.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const goals = useQuery({
    queryKey: ["engagement-goals"],
    queryFn: () => api.get<EngagementGoalWindow>("/engagement/goals/current"),
    enabled: initialize.isSuccess,
  });
  const plans = useQuery({
    queryKey: ["engagement-open-plans"],
    queryFn: () => api.get<OpenPlan[]>("/engagement/open-plans"),
    enabled: initialize.isSuccess,
  });
  const settings = useQuery({
    queryKey: ["engagement-settings"],
    queryFn: () => api.get<EngagementSettings>("/engagement/settings"),
    enabled: initialize.isSuccess,
  });
  const profile = useQuery({
    queryKey: ["profile"],
    queryFn: () => api.get<Profile>("/profiles/me"),
  });
  const doctrines = useQuery({
    queryKey: ["engagement-doctrines"],
    queryFn: () => api.get<DoctrineCatalogItem[]>("/engagement/doctrines"),
    enabled: initialize.isSuccess,
  });
  const doctrine = useQuery({
    queryKey: ["engagement-doctrine"],
    queryFn: () => api.get<DoctrineState | null>("/engagement/doctrine"),
    enabled: initialize.isSuccess,
  });
  const mastery = useQuery({
    queryKey: ["engagement-mastery"],
    queryFn: () => api.get<MasteryProgress[]>("/engagement/mastery"),
    enabled: initialize.isSuccess,
  });
  const helpOffers = useQuery({
    queryKey: ["engagement-adaptive-help"],
    queryFn: () => api.get<AdaptiveHelpOffer[]>("/engagement/adaptive-help"),
    enabled: initialize.isSuccess,
  });
  const mentorships = useQuery({
    queryKey: ["engagement-mentorships"],
    queryFn: () => api.get<Mentorship[]>("/engagement/mentorships"),
    enabled: initialize.isSuccess,
  });
  const chooseDoctrine = useMutation({
    mutationFn: (doctrineKey: DoctrineCatalogItem["key"]) =>
      api.put<DoctrineState>(
        "/engagement/doctrine",
        { doctrine_key: doctrineKey },
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["engagement-doctrine"],
      });
      await queryClient.invalidateQueries({ queryKey: ["engagement-goals"] });
    },
  });
  const respondHelp = useMutation({
    mutationFn: ({
      id,
      status,
    }: {
      id: string;
      status: "accepted" | "dismissed";
    }) =>
      api.patch<AdaptiveHelpOffer>(`/engagement/adaptive-help/${id}`, {
        status,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["engagement-adaptive-help"],
      });
    },
  });
  const choose = useMutation({
    mutationFn: (goalId: string) =>
      api.post<EngagementGoal>(
        `/engagement/goals/${goalId}/select`,
        {},
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["engagement-goals"] });
      await queryClient.invalidateQueries({
        queryKey: ["engagement-command-center"],
      });
    },
  });
  const updatePlan = useMutation({
    mutationFn: (id: string) =>
      api.patch<OpenPlan>(
        `/engagement/open-plans/${id}`,
        { status: "completed" },
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["engagement-open-plans"],
      });
      await queryClient.invalidateQueries({
        queryKey: ["engagement-command-center"],
      });
    },
  });
  const planForm = useForm<PlanInput>({
    resolver: zodResolver(planSchema),
    defaultValues: { title: "", next_step: "" },
  });
  const addPlan = useMutation({
    mutationFn: (value: PlanInput) =>
      api.post<OpenPlan>(
        "/engagement/open-plans",
        {
          ...value,
          category: "strategic",
          target_path: "/engagement",
          priority: 50,
        },
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      planForm.reset();
      await queryClient.invalidateQueries({
        queryKey: ["engagement-open-plans"],
      });
    },
  });
  const mentorshipForm = useForm<MentorshipInput>({
    resolver: zodResolver(mentorshipSchema),
    defaultValues: { mentee_profile_id: "" },
  });
  const createMentorship = useMutation({
    mutationFn: (value: MentorshipInput) =>
      api.post<Mentorship>(
        "/engagement/mentorships",
        value,
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      mentorshipForm.reset();
      await queryClient.invalidateQueries({
        queryKey: ["engagement-mentorships"],
      });
    },
  });
  const answerMentorship = useMutation({
    mutationFn: ({ id, accept }: { id: string; accept: boolean }) =>
      api.post<Mentorship>(`/engagement/mentorships/${id}/answer`, { accept }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["engagement-mentorships"],
      });
    },
  });
  const briefing = useMutation({
    mutationFn: () => api.post<ReturnBriefing>("/engagement/return-briefings"),
  });
  const toggleHelp = useMutation({
    mutationFn: (current: EngagementSettings) =>
      api.put<EngagementSettings>("/engagement/settings", {
        adaptive_help_enabled: !current.adaptive_help_enabled,
        session_summary_enabled: current.session_summary_enabled,
        ranking_visible: current.ranking_visible,
        information_density: current.information_density,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["engagement-settings"],
      });
    },
  });
  const hasError =
    initialize.isError ||
    goals.isError ||
    plans.isError ||
    settings.isError ||
    doctrines.isError ||
    doctrine.isError ||
    mastery.isError ||
    helpOffers.isError ||
    mentorships.isError;
  const loading = initialize.isPending || goals.isLoading;
  return (
    <ScrollView contentContainerStyle={styles.screen}>
      <Text accessibilityRole="header" style={styles.title}>
        {t("engagementTitle")}
      </Text>
      <Text style={styles.subtitle}>{t("engagementDescription")}</Text>
      {loading && <ActivityIndicator color={colors.gold} />}
      {hasError && <ErrorNotice />}

      <View style={styles.list}>
        <Text accessibilityRole="header" style={styles.sectionTitle}>
          {t("engagementDoctrineTitle")}
        </Text>
        <Text style={styles.muted}>{t("engagementDoctrineDescription")}</Text>
        {doctrines.data?.map((item) => (
          <View style={styles.card} key={item.key}>
            <Text style={styles.cardTitle}>{t(item.title_key)}</Text>
            <Text style={styles.text}>{t(item.description_key)}</Text>
            <Text style={styles.muted}>
              {t("engagementDoctrineNoEconomicBonus")}
            </Text>
            <TouchableOpacity
              accessibilityRole="button"
              disabled={
                chooseDoctrine.isPending ||
                doctrine.data?.doctrine_key === item.key
              }
              onPress={() => chooseDoctrine.mutate(item.key)}
              style={styles.secondaryButton}
            >
              <Text style={styles.secondaryButtonText}>
                {doctrine.data?.doctrine_key === item.key
                  ? t("engagementDoctrineSelected")
                  : t("engagementDoctrineChoose")}
              </Text>
            </TouchableOpacity>
          </View>
        ))}
      </View>

      <View style={styles.list}>
        <Text accessibilityRole="header" style={styles.sectionTitle}>
          {t("engagementMasteryTitle")}
        </Text>
        {mastery.data?.map((item) => (
          <View style={styles.card} key={item.id}>
            <Text style={styles.cardTitle}>
              {translateGameValue(item.area_key)}
            </Text>
            <Text style={styles.value}>
              {t("engagementMasteryLevel", {
                level: item.level,
                points: item.points,
              })}
            </Text>
            <Text style={styles.muted}>
              {t("engagementMasteryDiversity", {
                count: item.distinct_decisions_json.length,
              })}
            </Text>
          </View>
        ))}
      </View>

      {helpOffers.data && helpOffers.data.length > 0 && (
        <View style={styles.list}>
          <Text accessibilityRole="header" style={styles.sectionTitle}>
            {t("engagementAdaptiveHelpTitle")}
          </Text>
          {helpOffers.data.map((offer) => (
            <View style={styles.card} key={offer.id}>
              <Text style={styles.cardTitle}>{t(offer.explanation_key)}</Text>
              <Text style={styles.text}>{t(offer.suggestion_key)}</Text>
              <View style={styles.row}>
                <TouchableOpacity
                  accessibilityRole="button"
                  onPress={() =>
                    respondHelp.mutate({ id: offer.id, status: "accepted" })
                  }
                  style={styles.button}
                >
                  <Text style={styles.buttonText}>
                    {t("engagementHelpAccept")}
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity
                  accessibilityRole="button"
                  onPress={() =>
                    respondHelp.mutate({ id: offer.id, status: "dismissed" })
                  }
                  style={styles.secondaryButton}
                >
                  <Text style={styles.secondaryButtonText}>
                    {t("engagementHelpDismiss")}
                  </Text>
                </TouchableOpacity>
              </View>
            </View>
          ))}
        </View>
      )}

      {goals.data && (
        <View style={styles.list}>
          <Text accessibilityRole="header" style={styles.sectionTitle}>
            {t("engagementGoalsTitle")}
          </Text>
          <Text style={styles.muted}>
            {t("engagementGoalsChoice", {
              selected: goals.data.selected_count,
              maximum: goals.data.max_choices,
            })}
          </Text>
          {goals.data.goals.map((goal) => {
            const progress = Math.min(
              100,
              Math.round((goal.progress_value * 100) / goal.target_value),
            );
            return (
              <View style={styles.card} key={goal.id}>
                <Text style={styles.muted}>
                  {t(goalCategoryKey[goal.category])}
                </Text>
                <Text style={styles.cardTitle}>{t(goal.title_key)}</Text>
                <Text style={styles.text}>{t(goal.description_key)}</Text>
                <View
                  accessibilityRole="progressbar"
                  accessibilityValue={{ now: progress, min: 0, max: 100 }}
                  style={styles.progressTrack}
                >
                  <View
                    style={[styles.progressValue, { width: `${progress}%` }]}
                  />
                </View>
                <Text style={styles.muted}>
                  {t("engagementGoalProgress", {
                    current: goal.progress_value,
                    target: goal.target_value,
                  })}
                </Text>
                {goal.status === "offered" && (
                  <TouchableOpacity
                    accessibilityRole="button"
                    disabled={choose.isPending}
                    onPress={() => choose.mutate(goal.id)}
                    style={styles.button}
                  >
                    <Text style={styles.buttonText}>
                      {t("engagementChooseGoal")}
                    </Text>
                  </TouchableOpacity>
                )}
              </View>
            );
          })}
        </View>
      )}

      <View style={styles.list}>
        <Text accessibilityRole="header" style={styles.sectionTitle}>
          {t("engagementOpenPlansTitle")}
        </Text>
        {plans.data?.length === 0 && (
          <Text style={styles.muted}>{t("empty")}</Text>
        )}
        {plans.data?.map((plan) => (
          <View style={styles.card} key={plan.id}>
            <Text style={styles.cardTitle}>{plan.title}</Text>
            <Text style={styles.text}>{plan.next_step}</Text>
            {plan.status === "active" && (
              <TouchableOpacity
                accessibilityRole="button"
                disabled={updatePlan.isPending}
                onPress={() => updatePlan.mutate(plan.id)}
                style={styles.secondaryButton}
              >
                <Text style={styles.secondaryButtonText}>
                  {t("engagementCompletePlan")}
                </Text>
              </TouchableOpacity>
            )}
          </View>
        ))}
        <Controller
          control={planForm.control}
          name="title"
          render={({ field: { onBlur, onChange, value } }) => (
            <TextInput
              accessibilityLabel={t("engagementPlanTitle")}
              onBlur={onBlur}
              onChangeText={onChange}
              placeholder={t("engagementPlanTitle")}
              placeholderTextColor={colors.muted}
              style={styles.input}
              value={value}
            />
          )}
        />
        <Controller
          control={planForm.control}
          name="next_step"
          render={({ field: { onBlur, onChange, value } }) => (
            <TextInput
              accessibilityLabel={t("engagementNextStep")}
              multiline
              onBlur={onBlur}
              onChangeText={onChange}
              placeholder={t("engagementNextStep")}
              placeholderTextColor={colors.muted}
              style={styles.input}
              value={value}
            />
          )}
        />
        {(planForm.formState.errors.title ||
          planForm.formState.errors.next_step ||
          addPlan.isError) && (
          <Text style={styles.text}>{t("errorTitle")}</Text>
        )}
        <TouchableOpacity
          accessibilityRole="button"
          disabled={addPlan.isPending}
          onPress={planForm.handleSubmit((value) => addPlan.mutate(value))}
          style={styles.button}
        >
          <Text style={styles.buttonText}>{t("engagementAddPlan")}</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>{t("engagementReturnTitle")}</Text>
        <Text style={styles.text}>{t("engagementReturnDescription")}</Text>
        {briefing.data && (
          <Text accessibilityLiveRegion="polite" style={styles.text}>
            {t("engagementWorldChanges", {
              count: briefing.data.world_changes_json.length,
            })}{" "}
            {t("engagementCompanyChanges", {
              count: briefing.data.company_changes_json.length,
            })}
          </Text>
        )}
        <TouchableOpacity
          accessibilityRole="button"
          disabled={briefing.isPending}
          onPress={() => briefing.mutate()}
          style={styles.secondaryButton}
        >
          <Text style={styles.secondaryButtonText}>
            {t("engagementCreateBriefing")}
          </Text>
        </TouchableOpacity>
      </View>

      <View style={styles.list}>
        <Text accessibilityRole="header" style={styles.sectionTitle}>
          {t("engagementMentoringTitle")}
        </Text>
        <Text style={styles.muted}>{t("engagementMentoringDescription")}</Text>
        {mentorships.data?.map((mentorship) => {
          const currentIsMentee =
            mentorship.mentee_profile_id === profile.data?.id;
          return (
            <View style={styles.card} key={mentorship.id}>
              <Text style={styles.cardTitle}>
                {currentIsMentee
                  ? t("engagementYourMentor")
                  : t("engagementYourMentee")}
              </Text>
              <Text style={styles.muted}>
                {currentIsMentee
                  ? mentorship.mentor_profile_id
                  : mentorship.mentee_profile_id}
              </Text>
              <Text style={styles.text}>
                {t("engagementMentoringMilestones", {
                  count: mentorship.milestones.length,
                })}
              </Text>
              {currentIsMentee && mentorship.status === "proposed" && (
                <View style={styles.row}>
                  <TouchableOpacity
                    accessibilityRole="button"
                    onPress={() =>
                      answerMentorship.mutate({
                        id: mentorship.id,
                        accept: true,
                      })
                    }
                    style={styles.button}
                  >
                    <Text style={styles.buttonText}>
                      {t("engagementMentoringAccept")}
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    accessibilityRole="button"
                    onPress={() =>
                      answerMentorship.mutate({
                        id: mentorship.id,
                        accept: false,
                      })
                    }
                    style={styles.secondaryButton}
                  >
                    <Text style={styles.secondaryButtonText}>
                      {t("engagementMentoringDecline")}
                    </Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>
          );
        })}
        <Controller
          control={mentorshipForm.control}
          name="mentee_profile_id"
          render={({ field: { onBlur, onChange, value } }) => (
            <TextInput
              accessibilityLabel={t("engagementMenteeProfile")}
              autoCapitalize="none"
              onBlur={onBlur}
              onChangeText={onChange}
              placeholder={t("engagementMenteeProfile")}
              placeholderTextColor={colors.muted}
              style={styles.input}
              value={value}
            />
          )}
        />
        {mentorshipForm.formState.errors.mentee_profile_id && (
          <Text accessibilityRole="alert" style={styles.text}>
            {t("errorTitle")}
          </Text>
        )}
        <TouchableOpacity
          accessibilityRole="button"
          disabled={createMentorship.isPending}
          onPress={mentorshipForm.handleSubmit((value) =>
            createMentorship.mutate(value),
          )}
          style={styles.button}
        >
          <Text style={styles.buttonText}>{t("engagementOfferMentoring")}</Text>
        </TouchableOpacity>
      </View>

      {settings.data && (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>
            {t("engagementExperienceSettings")}
          </Text>
          <TouchableOpacity
            accessibilityRole="switch"
            accessibilityState={{
              checked: settings.data.adaptive_help_enabled,
            }}
            disabled={toggleHelp.isPending}
            onPress={() => toggleHelp.mutate(settings.data)}
            style={styles.secondaryButton}
          >
            <Text style={styles.secondaryButtonText}>
              {t("engagementAdaptiveHelp")}:{" "}
              {settings.data.adaptive_help_enabled ? "✓" : "—"}
            </Text>
          </TouchableOpacity>
        </View>
      )}
    </ScrollView>
  );
}
