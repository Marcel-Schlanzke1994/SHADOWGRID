import { useEffect, useRef, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { createIdempotencyKey } from "@shadowgrid/api-client";
import type {
  AdaptiveHelpOffer,
  DoctrineCatalogItem,
  DoctrineKey,
  DoctrineState,
  EngagementGoal,
  EngagementGoalWindow,
  EngagementSettings,
  MasteryProgress,
  Mentorship,
  NotificationPreference,
  OpenPlan,
  OutcomeReport,
  PersonalSuccessChain,
  Profile,
  ReturnBriefing,
} from "@shadowgrid/shared-types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";
import { client } from "../auth";
import { Field, Panel, Progress, StateView, Status } from "../components";
import { formatDate } from "../format";

const openPlanSchema = z.object({
  category: z.enum(["urgent", "strategic", "discoverable"]),
  title: z.string().trim().min(2).max(140),
  next_step: z.string().trim().min(2).max(280),
  target_path: z
    .string()
    .regex(/^\/[A-Za-z0-9/_-]*$/)
    .max(180),
  priority: z.coerce.number().int().min(0).max(100),
});
type OpenPlanInput = z.infer<typeof openPlanSchema>;

const preferenceSchema = z.object({
  live_enabled: z.boolean(),
  digest_frequency: z.enum(["immediate", "daily", "weekly", "off"]),
  quiet_start_minute: z.coerce.number().int().min(0).max(1439),
  quiet_end_minute: z.coerce.number().int().min(0).max(1439),
  timezone: z.string().min(3).max(64),
});
type PreferenceInput = z.infer<typeof preferenceSchema>;

const settingsSchema = z.object({
  adaptive_help_enabled: z.boolean(),
  session_summary_enabled: z.boolean(),
  ranking_visible: z.boolean(),
  information_density: z.enum(["compact", "standard", "detailed"]),
});
type SettingsInput = z.infer<typeof settingsSchema>;

const mentorshipSchema = z.object({
  mentee_profile_id: z.string().uuid(),
});
type MentorshipInput = z.infer<typeof mentorshipSchema>;

const masteryLabelKeys = {
  company_management: "engagementMasteryCompanyManagement",
  market_analysis: "engagementMasteryMarketAnalysis",
  capital_markets: "engagementMasteryCapitalMarkets",
  contract_management: "engagementMasteryContractManagement",
  people_leadership: "engagementMasteryPeopleLeadership",
  real_estate: "engagementMasteryRealEstate",
  cartel_leadership: "engagementMasteryCartelLeadership",
  diplomacy: "engagementMasteryDiplomacy",
  intelligence: "engagementMasteryIntelligence",
  risk_management: "engagementMasteryRiskManagement",
  season_strategy: "engagementMasterySeasonStrategy",
} as const;

function PreferenceEditor({
  preference,
}: {
  preference: NotificationPreference;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const form = useForm<PreferenceInput>({
    resolver: zodResolver(preferenceSchema),
    defaultValues: preference,
  });
  const update = useMutation({
    mutationFn: (body: PreferenceInput) =>
      client.put<NotificationPreference>(
        `/engagement/notification-preferences/${preference.category}`,
        body,
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["engagement-notification-preferences"],
      });
    },
  });
  const critical = preference.category === "critical";
  const categoryKey = {
    critical: "engagementNotificationCritical",
    strategic: "engagementNotificationStrategic",
    social: "engagementNotificationSocial",
    summary: "engagementNotificationSummary",
  }[preference.category];
  return (
    <form
      className="engagement-preference"
      onSubmit={form.handleSubmit((value) => update.mutate(value))}
    >
      <h3>{t(categoryKey)}</h3>
      <label className="check-row">
        <input
          type="checkbox"
          disabled={critical}
          {...form.register("live_enabled")}
        />
        {t("engagementLiveUpdates")}
      </label>
      <Field label={t("engagementDigest")}>
        <select disabled={critical} {...form.register("digest_frequency")}>
          <option value="immediate">{t("engagementDigestImmediate")}</option>
          <option value="daily">{t("engagementDigestDaily")}</option>
          <option value="weekly">{t("engagementDigestWeekly")}</option>
          <option value="off">{t("engagementDigestOff")}</option>
        </select>
      </Field>
      <div className="form-grid">
        <Field label={t("engagementQuietStart")}>
          <input type="number" {...form.register("quiet_start_minute")} />
        </Field>
        <Field label={t("engagementQuietEnd")}>
          <input type="number" {...form.register("quiet_end_minute")} />
        </Field>
      </div>
      <Field label={t("engagementTimezone")}>
        <input {...form.register("timezone")} />
      </Field>
      {critical && <small>{t("engagementCriticalAlwaysOn")}</small>}
      {update.error && <StateView error={update.error}>{null}</StateView>}
      <button className="button button--secondary" disabled={update.isPending}>
        {t("save")}
      </button>
    </form>
  );
}

function SettingsEditor({ settings }: { settings: EngagementSettings }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const form = useForm<SettingsInput>({
    resolver: zodResolver(settingsSchema),
    defaultValues: settings,
  });
  const update = useMutation({
    mutationFn: (body: SettingsInput) =>
      client.put<EngagementSettings>("/engagement/settings", body),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["engagement-settings"],
      });
    },
  });
  return (
    <form onSubmit={form.handleSubmit((value) => update.mutate(value))}>
      <label className="check-row">
        <input type="checkbox" {...form.register("adaptive_help_enabled")} />
        {t("engagementAdaptiveHelp")}
      </label>
      <label className="check-row">
        <input type="checkbox" {...form.register("session_summary_enabled")} />
        {t("engagementSessionSummaries")}
      </label>
      <label className="check-row">
        <input type="checkbox" {...form.register("ranking_visible")} />
        {t("engagementRankingsVisible")}
      </label>
      <Field label={t("engagementInformationDensity")}>
        <select {...form.register("information_density")}>
          <option value="compact">{t("engagementDensityCompact")}</option>
          <option value="standard">{t("engagementDensityStandard")}</option>
          <option value="detailed">{t("engagementDensityDetailed")}</option>
        </select>
      </Field>
      {update.error && <StateView error={update.error}>{null}</StateView>}
      <button className="button" disabled={update.isPending}>
        {t("save")}
      </button>
    </form>
  );
}

function GoalCard({
  goal,
  offeredGoals,
  onSelect,
  onSwap,
  pending,
}: {
  goal: EngagementGoal;
  offeredGoals: EngagementGoal[];
  onSelect: (goalId: string) => void;
  onSwap: (goalId: string, replacementId: string) => void;
  pending: boolean;
}) {
  const { t, i18n } = useTranslation();
  const [replacementId, setReplacementId] = useState(offeredGoals[0]?.id ?? "");
  const percentage = Math.round(
    (goal.progress_value * 100) / goal.target_value,
  );
  const categoryKey = {
    economic: "engagementCategoryEconomic",
    social: "engagementCategorySocial",
    exploration: "engagementCategoryExploration",
    risk: "engagementCategoryRisk",
    long_term: "engagementCategoryLongTerm",
    season: "engagementCategorySeason",
  }[goal.category];
  return (
    <article className="card engagement-goal">
      <div className="list-row">
        <div>
          <small>{t(categoryKey)}</small>
          <h3>{t(goal.title_key)}</h3>
        </div>
        <Status value={goal.status} />
      </div>
      <p>{t(goal.description_key)}</p>
      <Progress
        label={t("engagementGoalProgress", {
          current: goal.progress_value,
          target: goal.target_value,
        })}
        value={percentage}
      />
      <small>
        {t("engagementCatchUpUntil", {
          date: formatDate(goal.catch_up_until, i18n.language),
        })}
      </small>
      {goal.status === "offered" && (
        <button
          className="button"
          disabled={pending}
          onClick={() => onSelect(goal.id)}
        >
          {t("engagementChooseGoal")}
        </button>
      )}
      {goal.status === "active" && offeredGoals.length > 0 && (
        <div className="inline-form">
          <label>
            <span>{t("engagementReplacementGoal")}</span>
            <select
              value={replacementId}
              onChange={(event) => setReplacementId(event.target.value)}
            >
              {offeredGoals.map((item) => (
                <option value={item.id} key={item.id}>
                  {t(item.title_key)}
                </option>
              ))}
            </select>
          </label>
          <button
            className="button button--ghost"
            disabled={pending || !replacementId}
            onClick={() => onSwap(goal.id, replacementId)}
          >
            {t("engagementSwapGoal")}
          </button>
        </div>
      )}
    </article>
  );
}

export function EngagementPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const initializeKey = useRef(createIdempotencyKey());
  const initialize = useMutation({
    mutationFn: () =>
      client.post<EngagementGoalWindow>(
        "/engagement/initialize",
        {},
        initializeKey.current,
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["engagement-goals"] });
    },
  });
  useEffect(() => {
    initialize.mutate();
    // A stable idempotency key makes the one-time bootstrap safe under StrictMode.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const goals = useQuery({
    queryKey: ["engagement-goals"],
    queryFn: () =>
      client.get<EngagementGoalWindow>("/engagement/goals/current"),
    enabled: initialize.isSuccess,
  });
  const plans = useQuery({
    queryKey: ["engagement-open-plans"],
    queryFn: () => client.get<OpenPlan[]>("/engagement/open-plans"),
    enabled: initialize.isSuccess,
  });
  const preferences = useQuery({
    queryKey: ["engagement-notification-preferences"],
    queryFn: () =>
      client.get<NotificationPreference[]>(
        "/engagement/notification-preferences",
      ),
    enabled: initialize.isSuccess,
  });
  const settings = useQuery({
    queryKey: ["engagement-settings"],
    queryFn: () => client.get<EngagementSettings>("/engagement/settings"),
    enabled: initialize.isSuccess,
  });
  const profile = useQuery({
    queryKey: ["profile"],
    queryFn: () => client.get<Profile>("/profiles/me"),
  });
  const doctrines = useQuery({
    queryKey: ["engagement-doctrines"],
    queryFn: () => client.get<DoctrineCatalogItem[]>("/engagement/doctrines"),
    enabled: initialize.isSuccess,
  });
  const doctrine = useQuery({
    queryKey: ["engagement-doctrine"],
    queryFn: () => client.get<DoctrineState | null>("/engagement/doctrine"),
    enabled: initialize.isSuccess,
  });
  const mastery = useQuery({
    queryKey: ["engagement-mastery"],
    queryFn: () => client.get<MasteryProgress[]>("/engagement/mastery"),
    enabled: initialize.isSuccess,
  });
  const outcomeReports = useQuery({
    queryKey: ["engagement-outcome-reports"],
    queryFn: () => client.get<OutcomeReport[]>("/engagement/outcome-reports"),
    enabled: initialize.isSuccess,
  });
  const helpOffers = useQuery({
    queryKey: ["engagement-adaptive-help"],
    queryFn: () => client.get<AdaptiveHelpOffer[]>("/engagement/adaptive-help"),
    enabled: initialize.isSuccess,
  });
  const chain = useQuery({
    queryKey: ["engagement-success-chain"],
    queryFn: () =>
      client.get<PersonalSuccessChain>("/engagement/success-chain"),
    enabled: initialize.isSuccess,
  });
  const mentorships = useQuery({
    queryKey: ["engagement-mentorships"],
    queryFn: () => client.get<Mentorship[]>("/engagement/mentorships"),
    enabled: initialize.isSuccess,
  });
  const selectDoctrine = useMutation({
    mutationFn: (doctrineKey: DoctrineKey) =>
      client.put<DoctrineState>(
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
      client.patch<AdaptiveHelpOffer>(`/engagement/adaptive-help/${id}`, {
        status,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["engagement-adaptive-help"],
      });
    },
  });
  const mentorshipForm = useForm<MentorshipInput>({
    resolver: zodResolver(mentorshipSchema),
    defaultValues: { mentee_profile_id: "" },
  });
  const createMentorship = useMutation({
    mutationFn: (body: MentorshipInput) =>
      client.post<Mentorship>(
        "/engagement/mentorships",
        body,
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
      client.post<Mentorship>(`/engagement/mentorships/${id}/answer`, {
        accept,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["engagement-mentorships"],
      });
    },
  });
  const refreshMentorship = useMutation({
    mutationFn: (id: string) =>
      client.post<Mentorship>(`/engagement/mentorships/${id}/refresh`, {
        positive_feedback: true,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["engagement-mentorships"],
      });
      await queryClient.invalidateQueries({ queryKey: ["engagement-mastery"] });
    },
  });
  const choose = useMutation({
    mutationFn: (goalId: string) =>
      client.post<EngagementGoal>(
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
  const swap = useMutation({
    mutationFn: ({
      goalId,
      replacementId,
    }: {
      goalId: string;
      replacementId: string;
    }) =>
      client.post<EngagementGoal>(
        `/engagement/goals/${goalId}/swap`,
        { replacement_goal_id: replacementId },
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["engagement-goals"] });
      await queryClient.invalidateQueries({
        queryKey: ["engagement-command-center"],
      });
    },
  });
  const planForm = useForm<OpenPlanInput>({
    resolver: zodResolver(openPlanSchema),
    defaultValues: {
      category: "strategic",
      title: "",
      next_step: "",
      target_path: "/command",
      priority: 50,
    },
  });
  const addPlan = useMutation({
    mutationFn: (body: OpenPlanInput) =>
      client.post<OpenPlan>(
        "/engagement/open-plans",
        body,
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      planForm.reset();
      await queryClient.invalidateQueries({
        queryKey: ["engagement-open-plans"],
      });
      await queryClient.invalidateQueries({
        queryKey: ["engagement-command-center"],
      });
    },
  });
  const updatePlan = useMutation({
    mutationFn: ({
      id,
      status,
    }: {
      id: string;
      status: "completed" | "archived";
    }) =>
      client.patch<OpenPlan>(
        `/engagement/open-plans/${id}`,
        { status },
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
  const briefing = useMutation({
    mutationFn: () =>
      client.post<ReturnBriefing>("/engagement/return-briefings"),
  });
  const acknowledge = useMutation({
    mutationFn: (id: string) =>
      client.post<ReturnBriefing>(
        `/engagement/return-briefings/${id}/acknowledge`,
      ),
    onSuccess: () => briefing.reset(),
  });
  const offeredGoals =
    goals.data?.goals.filter((item) => item.status === "offered") ?? [];
  return (
    <div className="page">
      <header className="page-header">
        <p className="eyebrow">{t("engagementEyebrow")}</p>
        <h1>{t("engagementTitle")}</h1>
        <p>{t("engagementDescription")}</p>
      </header>
      <div className="two-column">
        <Panel title={t("engagementDoctrineTitle")}>
          <StateView
            loading={doctrines.isLoading || doctrine.isLoading}
            error={doctrines.error ?? doctrine.error ?? selectDoctrine.error}
            empty={doctrines.data?.length === 0}
          >
            <p>{t("engagementDoctrineDescription")}</p>
            <div className="card-grid">
              {doctrines.data?.map((item) => (
                <article className="card" key={item.key}>
                  <h3>{t(item.title_key)}</h3>
                  <p>{t(item.description_key)}</p>
                  <small>{t("engagementDoctrineNoEconomicBonus")}</small>
                  <button
                    className="button button--secondary"
                    disabled={
                      selectDoctrine.isPending ||
                      doctrine.data?.doctrine_key === item.key
                    }
                    onClick={() => selectDoctrine.mutate(item.key)}
                  >
                    {doctrine.data?.doctrine_key === item.key
                      ? t("engagementDoctrineSelected")
                      : t("engagementDoctrineChoose")}
                  </button>
                </article>
              ))}
            </div>
          </StateView>
        </Panel>
        <Panel title={t("engagementSuccessChainTitle")}>
          <StateView loading={chain.isLoading} error={chain.error}>
            {chain.data && (
              <>
                <p>{t("engagementSuccessChainDescription")}</p>
                <Progress
                  label={t("engagementSuccessChainProgress", {
                    current: chain.data.completed_steps,
                    total: chain.data.total_steps,
                  })}
                  value={
                    (chain.data.completed_steps * 100) / chain.data.total_steps
                  }
                />
                <Status value={chain.data.status} />
              </>
            )}
          </StateView>
        </Panel>
      </div>
      <StateView
        loading={initialize.isPending || goals.isLoading}
        error={initialize.error ?? goals.error}
      >
        {goals.data && (
          <Panel title={t("engagementGoalsTitle")}>
            <p>
              {t("engagementGoalsChoice", {
                selected: goals.data.selected_count,
                maximum: goals.data.max_choices,
              })}
            </p>
            <div className="card-grid">
              {goals.data.goals.map((goal) => (
                <GoalCard
                  key={goal.id}
                  goal={goal}
                  offeredGoals={offeredGoals.filter(
                    (item) => item.id !== goal.id,
                  )}
                  onSelect={(id) => choose.mutate(id)}
                  onSwap={(goalId, replacementId) =>
                    swap.mutate({ goalId, replacementId })
                  }
                  pending={choose.isPending || swap.isPending}
                />
              ))}
            </div>
            {(choose.error || swap.error) && (
              <StateView error={choose.error ?? swap.error}>{null}</StateView>
            )}
          </Panel>
        )}
      </StateView>

      <Panel title={t("engagementMasteryTitle")}>
        <StateView loading={mastery.isLoading} error={mastery.error}>
          <div className="mastery-grid">
            {mastery.data?.map((item) => (
              <article className="card" key={item.id}>
                <h3>{t(masteryLabelKeys[item.area_key])}</h3>
                <Progress
                  label={t("engagementMasteryLevel", {
                    level: item.level,
                    points: item.points,
                  })}
                  value={item.level * 10}
                />
                <small>
                  {t("engagementMasteryDiversity", {
                    count: item.distinct_decisions_json.length,
                  })}
                </small>
              </article>
            ))}
          </div>
        </StateView>
      </Panel>

      <div className="two-column">
        <Panel title={t("engagementAdaptiveHelpTitle")}>
          <StateView
            loading={helpOffers.isLoading}
            error={helpOffers.error ?? respondHelp.error}
            empty={helpOffers.data?.length === 0}
          >
            {helpOffers.data?.map((offer) => (
              <article className="card" key={offer.id}>
                <h3>{t(offer.explanation_key)}</h3>
                <p>{t(offer.suggestion_key)}</p>
                <div className="button-row">
                  <button
                    className="button"
                    onClick={() =>
                      respondHelp.mutate({ id: offer.id, status: "accepted" })
                    }
                  >
                    {t("engagementHelpAccept")}
                  </button>
                  <button
                    className="button button--ghost"
                    onClick={() =>
                      respondHelp.mutate({ id: offer.id, status: "dismissed" })
                    }
                  >
                    {t("engagementHelpDismiss")}
                  </button>
                </div>
              </article>
            ))}
          </StateView>
        </Panel>
        <Panel title={t("engagementOutcomeReportsTitle")}>
          <StateView
            loading={outcomeReports.isLoading}
            error={outcomeReports.error}
            empty={outcomeReports.data?.length === 0}
          >
            {outcomeReports.data?.map((report) => (
              <details className="card" key={report.id}>
                <summary>{t(report.title_key)}</summary>
                <h4>{t("engagementOutcomeControllable")}</h4>
                <ul>
                  {report.controllable_factors_json.map((key) => (
                    <li key={key}>{t(key)}</li>
                  ))}
                </ul>
                <h4>{t("engagementOutcomeExternal")}</h4>
                <ul>
                  {report.external_factors_json.map((key) => (
                    <li key={key}>{t(key)}</li>
                  ))}
                </ul>
              </details>
            ))}
          </StateView>
        </Panel>
      </div>

      <div className="two-column">
        <Panel title={t("engagementOpenPlansTitle")}>
          <StateView
            loading={plans.isLoading}
            error={plans.error ?? updatePlan.error}
            empty={plans.data?.length === 0}
          >
            {plans.data?.map((plan) => (
              <div className="list-row" key={plan.id}>
                <span>
                  <strong>{plan.title}</strong>
                  <small>{plan.next_step}</small>
                </span>
                <Status value={plan.status} />
                {plan.status === "active" && (
                  <span className="button-row">
                    <button
                      className="button button--secondary"
                      onClick={() =>
                        updatePlan.mutate({ id: plan.id, status: "completed" })
                      }
                    >
                      {t("engagementCompletePlan")}
                    </button>
                    <button
                      className="button button--ghost"
                      onClick={() =>
                        updatePlan.mutate({ id: plan.id, status: "archived" })
                      }
                    >
                      {t("engagementArchivePlan")}
                    </button>
                  </span>
                )}
              </div>
            ))}
          </StateView>
        </Panel>
        <Panel title={t("engagementAddPlanTitle")}>
          <form
            onSubmit={planForm.handleSubmit((value) => addPlan.mutate(value))}
          >
            <Field label={t("engagementPlanCategory")}>
              <select {...planForm.register("category")}>
                <option value="urgent">
                  {t("engagementOpportunityUrgent")}
                </option>
                <option value="strategic">
                  {t("engagementOpportunityStrategic")}
                </option>
                <option value="discoverable">
                  {t("engagementOpportunityDiscoverable")}
                </option>
              </select>
            </Field>
            <Field label={t("engagementPlanTitle")}>
              <input {...planForm.register("title")} />
            </Field>
            <Field label={t("engagementNextStep")}>
              <textarea {...planForm.register("next_step")} />
            </Field>
            <Field label={t("engagementTargetPath")}>
              <input {...planForm.register("target_path")} />
            </Field>
            <Field label={t("engagementPriority")}>
              <input type="number" {...planForm.register("priority")} />
            </Field>
            {addPlan.error && (
              <StateView error={addPlan.error}>{null}</StateView>
            )}
            <button className="button" disabled={addPlan.isPending}>
              {t("engagementAddPlan")}
            </button>
          </form>
        </Panel>
      </div>

      <Panel title={t("engagementReturnTitle")}>
        <p>{t("engagementReturnDescription")}</p>
        {!briefing.data && (
          <button
            className="button"
            onClick={() => briefing.mutate()}
            disabled={briefing.isPending}
          >
            {t("engagementCreateBriefing")}
          </button>
        )}
        {briefing.error && <StateView error={briefing.error}>{null}</StateView>}
        {briefing.data && (
          <div className="return-briefing" aria-live="polite">
            <p>
              {t("engagementChangesSince", {
                date: formatDate(briefing.data.since_at, i18n.language),
              })}
            </p>
            <ul>
              <li>
                {t("engagementWorldChanges", {
                  count: briefing.data.world_changes_json.length,
                })}
              </li>
              <li>
                {t("engagementCompanyChanges", {
                  count: briefing.data.company_changes_json.length,
                })}
              </li>
              <li>
                {t("engagementAvailableContent", {
                  count: briefing.data.available_content_json.length,
                })}
              </li>
            </ul>
            <h3>{t("engagementEntryPoints")}</h3>
            <ul>
              {briefing.data.entry_points_json.map((item) => (
                <li key={`${item.source_type}-${item.source_id}`}>
                  {t(item.title)}
                </li>
              ))}
            </ul>
            <button
              className="button button--secondary"
              onClick={() => acknowledge.mutate(briefing.data.id)}
            >
              {t("engagementBriefingUnderstood")}
            </button>
          </div>
        )}
      </Panel>

      <Panel title={t("engagementMentoringTitle")}>
        <p>{t("engagementMentoringDescription")}</p>
        <div className="two-column">
          <form
            onSubmit={mentorshipForm.handleSubmit((value) =>
              createMentorship.mutate(value),
            )}
          >
            <Field
              label={t("engagementMenteeProfile")}
              error={mentorshipForm.formState.errors.mentee_profile_id?.message}
            >
              <input {...mentorshipForm.register("mentee_profile_id")} />
            </Field>
            {createMentorship.error && (
              <StateView error={createMentorship.error}>{null}</StateView>
            )}
            <button className="button" disabled={createMentorship.isPending}>
              {t("engagementOfferMentoring")}
            </button>
          </form>
          <StateView
            loading={mentorships.isLoading || profile.isLoading}
            error={
              mentorships.error ??
              profile.error ??
              answerMentorship.error ??
              refreshMentorship.error
            }
            empty={mentorships.data?.length === 0}
          >
            {mentorships.data?.map((mentorship) => {
              const currentIsMentee =
                mentorship.mentee_profile_id === profile.data?.id;
              return (
                <article className="card" key={mentorship.id}>
                  <div className="list-row">
                    <strong>
                      {currentIsMentee
                        ? t("engagementYourMentor")
                        : t("engagementYourMentee")}
                    </strong>
                    <Status value={mentorship.status} />
                  </div>
                  <small>
                    {currentIsMentee
                      ? mentorship.mentor_profile_id
                      : mentorship.mentee_profile_id}
                  </small>
                  <Progress
                    label={t("engagementMentoringMilestones", {
                      count: mentorship.milestones.length,
                    })}
                    value={(mentorship.milestones.length * 100) / 3}
                  />
                  {currentIsMentee && mentorship.status === "proposed" && (
                    <div className="button-row">
                      <button
                        className="button"
                        onClick={() =>
                          answerMentorship.mutate({
                            id: mentorship.id,
                            accept: true,
                          })
                        }
                      >
                        {t("engagementMentoringAccept")}
                      </button>
                      <button
                        className="button button--ghost"
                        onClick={() =>
                          answerMentorship.mutate({
                            id: mentorship.id,
                            accept: false,
                          })
                        }
                      >
                        {t("engagementMentoringDecline")}
                      </button>
                    </div>
                  )}
                  {currentIsMentee && mentorship.status === "active" && (
                    <button
                      className="button button--secondary"
                      onClick={() => refreshMentorship.mutate(mentorship.id)}
                    >
                      {t("engagementMentoringPositiveFeedback")}
                    </button>
                  )}
                </article>
              );
            })}
          </StateView>
        </div>
      </Panel>

      <Panel title={t("engagementNotificationSettings")}>
        <StateView loading={preferences.isLoading} error={preferences.error}>
          <div className="card-grid">
            {preferences.data?.map((preference) => (
              <PreferenceEditor preference={preference} key={preference.id} />
            ))}
          </div>
        </StateView>
      </Panel>
      <Panel title={t("engagementExperienceSettings")}>
        <StateView loading={settings.isLoading} error={settings.error}>
          {settings.data && <SettingsEditor settings={settings.data} />}
        </StateView>
      </Panel>
    </div>
  );
}
