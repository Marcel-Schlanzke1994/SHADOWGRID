import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createIdempotencyKey } from "@shadowgrid/api-client";
import { organizationArchetypes } from "@shadowgrid/game-config";
import { translateGameValue } from "@shadowgrid/i18n";
import type {
  Cartel,
  CartelActivity,
  CartelChronicleEntry,
  CartelDelegation,
  CartelExpense,
  CartelInvitation,
  CartelMember,
  CartelMembershipPause,
  CartelProject,
  CartelRanking,
  CartelTreasury,
  District,
  DistrictCartelInfluence,
} from "@shadowgrid/shared-types";
import {
  cartelContributionSchema,
  cartelCreateSchema,
  cartelExpenseSchema,
  cartelInvitationSchema,
  cartelProjectSchema,
  cartelTreasuryDepositSchema,
  type CartelContributionInput,
  type CartelCreateInput,
  type CartelExpenseInput,
  type CartelInvitationInput,
  type CartelProjectInput,
  type CartelTreasuryDepositInput,
} from "@shadowgrid/validation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { z } from "zod";
import { client } from "../auth";
import {
  ConfirmDialog,
  Field,
  Metric,
  Panel,
  Progress,
  StateView,
  Status,
} from "../components";
import { formatCents, formatDate, formatNumber } from "../format";

const humanize = translateGameValue;

const assignableRoles = [
  "member",
  "finance_lead",
  "diplomat",
  "strategist",
  "intelligence_officer",
  "economic_analyst",
  "intelligence_coordinator",
  "project_manager",
  "trainer",
  "archivist",
  "event_planner",
] as const;

const delegationSchema = z.object({
  delegate_profile_id: z.string().uuid(),
  role_key: z.enum([
    "economic_analyst",
    "diplomat",
    "intelligence_coordinator",
    "project_manager",
    "trainer",
    "archivist",
    "event_planner",
  ]),
  duration_days: z.number().int().min(1).max(30),
});
type DelegationInput = z.infer<typeof delegationSchema>;

const pauseSchema = z.object({
  duration_days: z.number().int().min(1).max(180),
  private_reason: z.string().trim().max(240),
});
type PauseInput = z.infer<typeof pauseSchema>;

const financeRoles = new Set(["leader", "director", "deputy", "finance_lead"]);
const projectRoles = new Set([
  "leader",
  "director",
  "deputy",
  "strategist",
  "district_lead",
]);

type PendingAction =
  | { kind: "approve"; expense: CartelExpense }
  | { kind: "transfer"; member: CartelMember }
  | { kind: "leave" }
  | { kind: "dissolve" };

function CartelCreateForm({
  pending,
  onSubmit,
}: {
  pending: boolean;
  onSubmit: (value: CartelCreateInput) => void;
}) {
  const { t } = useTranslation();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CartelCreateInput>({
    resolver: zodResolver(cartelCreateSchema),
    defaultValues: {
      name: "",
      tag: "",
      archetype: "business_consortium",
      description: "",
      governance_model: "directorate",
    },
  });
  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <Field label={t("cartelName")} error={errors.name?.message}>
        <input {...register("name")} />
      </Field>
      <Field label={t("cartelTag")} error={errors.tag?.message}>
        <input {...register("tag")} maxLength={8} />
      </Field>
      <Field label={t("archetype")} error={errors.archetype?.message}>
        <select {...register("archetype")}>
          {organizationArchetypes.map((item) => (
            <option key={item} value={item}>
              {humanize(item)}
            </option>
          ))}
        </select>
      </Field>
      <Field
        label={t("cartelGovernance")}
        error={errors.governance_model?.message}
      >
        <select {...register("governance_model")}>
          {["directorate", "council", "federation", "collective"].map(
            (item) => (
              <option key={item} value={item}>
                {humanize(item)}
              </option>
            ),
          )}
        </select>
      </Field>
      <Field label={t("description")} error={errors.description?.message}>
        <textarea {...register("description")} maxLength={500} />
      </Field>
      <button className="button" disabled={pending}>
        {t("cartelCreate")}
      </button>
    </form>
  );
}

function InvitationForm({
  pending,
  onSubmit,
}: {
  pending: boolean;
  onSubmit: (value: CartelInvitationInput) => void;
}) {
  const { t } = useTranslation();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CartelInvitationInput>({
    resolver: zodResolver(cartelInvitationSchema),
    defaultValues: { email: "" },
  });
  return (
    <form
      onSubmit={handleSubmit((value) => {
        onSubmit(value);
        reset();
      })}
    >
      <Field label={t("inviteEmail")} error={errors.email?.message}>
        <input type="email" {...register("email")} />
      </Field>
      <button className="button" disabled={pending}>
        {t("invite")}
      </button>
    </form>
  );
}

function DepositForm({
  pending,
  onSubmit,
}: {
  pending: boolean;
  onSubmit: (value: CartelTreasuryDepositInput) => void;
}) {
  const { t } = useTranslation();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CartelTreasuryDepositInput>({
    resolver: zodResolver(cartelTreasuryDepositSchema),
    defaultValues: { amount_cents: 100_000 },
  });
  return (
    <form
      onSubmit={handleSubmit((value) => {
        onSubmit(value);
        reset();
      })}
    >
      <Field
        label={t("cartelAmountCents")}
        hint={t("cartelCentsHint")}
        error={errors.amount_cents?.message}
      >
        <input
          type="number"
          min={1}
          step={1}
          {...register("amount_cents", { valueAsNumber: true })}
        />
      </Field>
      <button className="button" disabled={pending}>
        {t("cartelDeposit")}
      </button>
    </form>
  );
}

function ExpenseForm({
  pending,
  onSubmit,
}: {
  pending: boolean;
  onSubmit: (value: CartelExpenseInput) => void;
}) {
  const { t } = useTranslation();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CartelExpenseInput>({
    resolver: zodResolver(cartelExpenseSchema),
    defaultValues: { amount_cents: 100_000, purpose: "" },
  });
  return (
    <form
      onSubmit={handleSubmit((value) => {
        onSubmit(value);
        reset();
      })}
    >
      <Field label={t("cartelExpensePurpose")} error={errors.purpose?.message}>
        <input {...register("purpose")} maxLength={240} />
      </Field>
      <Field
        label={t("cartelAmountCents")}
        hint={t("cartelCentsHint")}
        error={errors.amount_cents?.message}
      >
        <input
          type="number"
          min={1}
          step={1}
          {...register("amount_cents", { valueAsNumber: true })}
        />
      </Field>
      <button className="button" disabled={pending}>
        {t("cartelExpenseRequest")}
      </button>
    </form>
  );
}

function ProjectForm({
  districts,
  pending,
  onSubmit,
}: {
  districts: District[];
  pending: boolean;
  onSubmit: (value: CartelProjectInput) => void;
}) {
  const { t } = useTranslation();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CartelProjectInput>({
    resolver: zodResolver(cartelProjectSchema),
    defaultValues: {
      project_type: "logistics_hub",
      district_id: districts[0]?.id ?? "",
    },
  });
  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <Field
        label={t("cartelProjectType")}
        error={errors.project_type?.message}
      >
        <select {...register("project_type")}>
          {[
            "logistics_hub",
            "technology_center",
            "media_campaign",
            "compliance_network",
            "trade_center",
          ].map((item) => (
            <option key={item} value={item}>
              {humanize(item)}
            </option>
          ))}
        </select>
      </Field>
      <Field label={t("district")} error={errors.district_id?.message}>
        <select {...register("district_id")}>
          {districts.map((district) => (
            <option key={district.id} value={district.id}>
              {district.name}
            </option>
          ))}
        </select>
      </Field>
      <button className="button" disabled={pending || districts.length === 0}>
        {t("cartelProjectStart")}
      </button>
    </form>
  );
}

function ContributionForm({
  project,
  pending,
  onSubmit,
}: {
  project: CartelProject;
  pending: boolean;
  onSubmit: (value: CartelContributionInput) => void;
}) {
  const { t } = useTranslation();
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<CartelContributionInput>({
    resolver: zodResolver(cartelContributionSchema),
    defaultValues: { resource_type: "cash", amount_units: 1 },
  });
  const resource = watch("resource_type");
  const remaining = {
    cash: project.required_cash_cents - project.contributed_cash_cents,
    influence: project.required_influence - project.contributed_influence,
    intelligence:
      project.required_intelligence - project.contributed_intelligence,
  }[resource];
  return (
    <form className="inline-form" onSubmit={handleSubmit(onSubmit)}>
      <Field
        label={t("cartelContributionResource")}
        error={errors.resource_type?.message}
      >
        <select {...register("resource_type")}>
          {(["cash", "influence", "intelligence"] as const).map((item) => (
            <option key={item} value={item}>
              {humanize(item)}
            </option>
          ))}
        </select>
      </Field>
      <Field
        label={t("cartelContributionAmount")}
        hint={t("cartelRemaining", { value: remaining })}
        error={errors.amount_units?.message}
      >
        <input
          type="number"
          min={1}
          max={Math.max(1, remaining)}
          {...register("amount_units", { valueAsNumber: true })}
        />
      </Field>
      <button
        className="button button--small"
        disabled={pending || remaining <= 0}
      >
        {t("cartelContribute")}
      </button>
    </form>
  );
}

function DelegationForm({
  members,
  pending,
  onSubmit,
}: {
  members: CartelMember[];
  pending: boolean;
  onSubmit: (value: DelegationInput) => void;
}) {
  const { t } = useTranslation();
  const form = useForm<DelegationInput>({
    resolver: zodResolver(delegationSchema),
    defaultValues: {
      delegate_profile_id: members[0]?.profile_id ?? "",
      role_key: "project_manager",
      duration_days: 7,
    },
  });
  return (
    <form onSubmit={form.handleSubmit(onSubmit)}>
      <Field
        label={t("engagementDelegateMember")}
        error={form.formState.errors.delegate_profile_id?.message}
      >
        <select {...form.register("delegate_profile_id")}>
          {members.map((member) => (
            <option key={member.profile_id} value={member.profile_id}>
              {member.codename}
            </option>
          ))}
        </select>
      </Field>
      <Field
        label={t("engagementDelegationRole")}
        error={form.formState.errors.role_key?.message}
      >
        <select {...form.register("role_key")}>
          {delegationSchema.shape.role_key.options.map((role) => (
            <option key={role} value={role}>
              {humanize(role)}
            </option>
          ))}
        </select>
      </Field>
      <Field
        label={t("engagementDelegationDays")}
        error={form.formState.errors.duration_days?.message}
      >
        <input
          type="number"
          min={1}
          max={30}
          {...form.register("duration_days", { valueAsNumber: true })}
        />
      </Field>
      <button className="button" disabled={pending || members.length === 0}>
        {t("engagementCreateDelegation")}
      </button>
    </form>
  );
}

function PauseForm({
  pending,
  onSubmit,
}: {
  pending: boolean;
  onSubmit: (value: PauseInput) => void;
}) {
  const { t } = useTranslation();
  const form = useForm<PauseInput>({
    resolver: zodResolver(pauseSchema),
    defaultValues: { duration_days: 14, private_reason: "" },
  });
  return (
    <form onSubmit={form.handleSubmit(onSubmit)}>
      <Field
        label={t("engagementPauseDays")}
        error={form.formState.errors.duration_days?.message}
      >
        <input
          type="number"
          min={1}
          max={180}
          {...form.register("duration_days", { valueAsNumber: true })}
        />
      </Field>
      <Field
        label={t("engagementPausePrivateReason")}
        hint={t("engagementPausePrivateHint")}
        error={form.formState.errors.private_reason?.message}
      >
        <textarea {...form.register("private_reason")} maxLength={240} />
      </Field>
      <button className="button button--secondary" disabled={pending}>
        {t("engagementStartPause")}
      </button>
    </form>
  );
}

export function CartelsPage() {
  const { t, i18n } = useTranslation();
  const { cartelId } = useParams();
  const queryClient = useQueryClient();
  const [success, setSuccess] = useState("");
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(
    null,
  );
  const cartels = useQuery({
    queryKey: ["cartels"],
    queryFn: () => client.get<Cartel[]>("/cartels"),
  });
  const invitations = useQuery({
    queryKey: ["cartels", "invitations"],
    queryFn: () => client.get<CartelInvitation[]>("/cartels/invitations/me"),
  });
  const rankings = useQuery({
    queryKey: ["cartels", "rankings"],
    queryFn: () => client.get<CartelRanking[]>("/leaderboards/cartels/current"),
  });
  const districts = useQuery({
    queryKey: ["districts"],
    queryFn: () => client.get<District[]>("/districts"),
  });
  const selected =
    cartels.data?.find((item) => item.id === cartelId) ??
    cartels.data?.find((item) => item.my_role) ??
    cartels.data?.[0];
  const selectedId = selected?.id ?? "";
  const isMember = Boolean(selected?.my_role);

  const members = useQuery({
    queryKey: ["cartels", selectedId, "members"],
    queryFn: () => client.get<CartelMember[]>(`/cartels/${selectedId}/members`),
    enabled: Boolean(selectedId && isMember),
  });
  const treasury = useQuery({
    queryKey: ["cartels", selectedId, "treasury"],
    queryFn: () =>
      client.get<CartelTreasury>(`/cartels/${selectedId}/treasury`),
    enabled: Boolean(selectedId && isMember),
  });
  const expenses = useQuery({
    queryKey: ["cartels", selectedId, "expenses"],
    queryFn: () =>
      client.get<CartelExpense[]>(`/cartels/${selectedId}/treasury/expenses`),
    enabled: Boolean(selectedId && isMember),
  });
  const projects = useQuery({
    queryKey: ["cartels", selectedId, "projects"],
    queryFn: () =>
      client.get<CartelProject[]>(`/cartels/${selectedId}/projects`),
    enabled: Boolean(selectedId && isMember),
  });
  const activity = useQuery({
    queryKey: ["cartels", selectedId, "activity"],
    queryFn: () =>
      client.get<CartelActivity[]>(`/cartels/${selectedId}/activity`),
    enabled: Boolean(selectedId && isMember),
  });
  const influence = useQuery({
    queryKey: ["cartels", selected?.city_id, "influence"],
    queryFn: () =>
      client.get<DistrictCartelInfluence[]>(
        `/influence/cities/${selected?.city_id}`,
      ),
    enabled: Boolean(selected?.city_id && isMember),
  });
  const delegations = useQuery({
    queryKey: ["cartels", selectedId, "delegations"],
    queryFn: () =>
      client.get<CartelDelegation[]>(
        `/engagement/social/cartels/${selectedId}/delegations`,
      ),
    enabled: Boolean(selectedId && isMember),
  });
  const membershipPause = useQuery({
    queryKey: ["cartels", selectedId, "pause"],
    queryFn: () =>
      client.get<CartelMembershipPause | null>(
        `/engagement/social/cartels/${selectedId}/pause`,
      ),
    enabled: Boolean(selectedId && isMember),
  });
  const chronicle = useQuery({
    queryKey: ["cartels", selectedId, "chronicle"],
    queryFn: () =>
      client.get<CartelChronicleEntry[]>(
        `/engagement/social/cartels/${selectedId}/chronicle`,
      ),
    enabled: Boolean(selectedId && isMember),
  });

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["cartels"] }),
      queryClient.invalidateQueries({ queryKey: ["districts"] }),
    ]);
  };
  const refreshSelected = async () => {
    await queryClient.invalidateQueries({
      queryKey: ["cartels", selectedId],
    });
    await queryClient.invalidateQueries({ queryKey: ["cartels"] });
  };
  const create = useMutation({
    mutationFn: (value: CartelCreateInput) =>
      client.post<Cartel>("/cartels", value, createIdempotencyKey()),
    onSuccess: async () => {
      setSuccess(t("cartelCreatedSuccess"));
      await refresh();
    },
  });
  const invite = useMutation({
    mutationFn: (value: CartelInvitationInput) =>
      client.post<CartelInvitation>(
        `/cartels/${selectedId}/invitations`,
        value,
        createIdempotencyKey(),
      ),
    onSuccess: () => setSuccess(t("cartelInvitationSuccess")),
  });
  const join = useMutation({
    mutationFn: (invitation: CartelInvitation) =>
      client.post<Cartel>(
        `/cartels/${invitation.organization_id}/join`,
        { invitation_id: invitation.id },
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setSuccess(t("cartelJoinedSuccess"));
      await queryClient.invalidateQueries({
        queryKey: ["cartels", "invitations"],
      });
      await refresh();
    },
  });
  const updateRole = useMutation({
    mutationFn: ({ profileId, role }: { profileId: string; role: string }) =>
      client.patch<CartelMember>(
        `/cartels/${selectedId}/members/${profileId}`,
        { role },
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setSuccess(t("cartelRoleSuccess"));
      await refreshSelected();
    },
  });
  const deposit = useMutation({
    mutationFn: (value: CartelTreasuryDepositInput) =>
      client.post<CartelTreasury>(
        `/cartels/${selectedId}/treasury/deposit`,
        value,
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setSuccess(t("cartelDepositSuccess"));
      await refreshSelected();
    },
  });
  const expense = useMutation({
    mutationFn: (value: CartelExpenseInput) =>
      client.post<CartelExpense>(
        `/cartels/${selectedId}/treasury/expenses`,
        value,
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setSuccess(t("cartelExpenseSuccess"));
      await refreshSelected();
    },
  });
  const project = useMutation({
    mutationFn: (value: CartelProjectInput) =>
      client.post<CartelProject>(
        `/cartels/${selectedId}/projects`,
        value,
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setSuccess(t("cartelProjectSuccess"));
      await refreshSelected();
    },
  });
  const contribution = useMutation({
    mutationFn: ({
      projectId,
      value,
    }: {
      projectId: string;
      value: CartelContributionInput;
    }) =>
      client.post<CartelProject>(
        `/cartels/${selectedId}/projects/${projectId}/contribute`,
        value,
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setSuccess(t("cartelContributionSuccess"));
      await refreshSelected();
    },
  });
  const createDelegation = useMutation({
    mutationFn: (value: DelegationInput) =>
      client.post<CartelDelegation>(
        `/engagement/social/cartels/${selectedId}/delegations`,
        value,
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setSuccess(t("engagementDelegationSuccess"));
      await queryClient.invalidateQueries({
        queryKey: ["cartels", selectedId, "delegations"],
      });
      await queryClient.invalidateQueries({
        queryKey: ["cartels", selectedId, "chronicle"],
      });
    },
  });
  const startPause = useMutation({
    mutationFn: (value: PauseInput) =>
      client.post<CartelMembershipPause>(
        `/engagement/social/cartels/${selectedId}/pause`,
        value,
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setSuccess(t("engagementPauseSuccess"));
      await queryClient.invalidateQueries({
        queryKey: ["cartels", selectedId, "pause"],
      });
    },
  });
  const resumePause = useMutation({
    mutationFn: () =>
      client.post<CartelMembershipPause>(
        `/engagement/social/cartels/${selectedId}/resume`,
      ),
    onSuccess: async () => {
      setSuccess(t("engagementResumeSuccess"));
      await queryClient.invalidateQueries({
        queryKey: ["cartels", selectedId, "pause"],
      });
    },
  });
  const action = useMutation({
    mutationFn: async (pending: PendingAction) => {
      if (pending.kind === "approve") {
        return client.post(
          `/cartels/${selectedId}/treasury/expenses/${pending.expense.id}/approve`,
          undefined,
          createIdempotencyKey(),
        );
      }
      if (pending.kind === "transfer") {
        return client.post(
          `/cartels/${selectedId}/leadership-transfer`,
          { target_profile_id: pending.member.profile_id },
          createIdempotencyKey(),
        );
      }
      if (pending.kind === "leave") {
        return client.post(
          `/cartels/${selectedId}/leave`,
          undefined,
          createIdempotencyKey(),
        );
      }
      return client.delete(`/cartels/${selectedId}`, createIdempotencyKey());
    },
    onSuccess: async () => {
      setSuccess(t("cartelActionSuccess"));
      setPendingAction(null);
      await refresh();
    },
  });
  const error =
    cartels.error ??
    invitations.error ??
    rankings.error ??
    districts.error ??
    members.error ??
    treasury.error ??
    expenses.error ??
    projects.error ??
    activity.error ??
    influence.error ??
    delegations.error ??
    membershipPause.error ??
    chronicle.error ??
    create.error ??
    invite.error ??
    join.error ??
    updateRole.error ??
    deposit.error ??
    expense.error ??
    project.error ??
    contribution.error ??
    createDelegation.error ??
    startPause.error ??
    resumePause.error ??
    action.error;

  return (
    <div className="page page--cartels">
      <header className="page-header">
        <h1>{t("cartelTitle")}</h1>
        <p>{t("cartelSubtitle")}</p>
      </header>
      {success && (
        <p className="state state--success" role="status">
          {success}
        </p>
      )}
      <StateView
        loading={cartels.isLoading || invitations.isLoading}
        error={error}
        onRetry={() => void refresh()}
      >
        <div className="content-grid">
          <Panel title={t("cartelOverview")}>
            <StateView empty={!cartels.data?.length}>
              <div className="card-grid">
                {cartels.data?.map((cartel) => (
                  <Link
                    className="data-card"
                    key={cartel.id}
                    to={`/cartels/${cartel.id}`}
                  >
                    <span className="eyebrow">{cartel.tag}</span>
                    <h3>{cartel.name}</h3>
                    <p>{cartel.description || t("cartelNoDescription")}</p>
                    <div>
                      <Status value={cartel.my_role ?? "public"} />
                      <span>
                        {t("members", { count: cartel.member_count })}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            </StateView>
          </Panel>

          {invitations.data && invitations.data.length > 0 && (
            <Panel title={t("cartelInvitations")}>
              <div className="list-stack">
                {invitations.data.map((invitation) => (
                  <div className="list-row" key={invitation.id}>
                    <span>
                      <strong>
                        {invitation.cartel_tag} · {invitation.cartel_name}
                      </strong>
                      <small>
                        {t("expires", {
                          date: formatDate(
                            invitation.expires_at,
                            i18n.language,
                          ),
                        })}
                      </small>
                    </span>
                    <button
                      className="button button--small"
                      disabled={join.isPending}
                      onClick={() => join.mutate(invitation)}
                    >
                      {t("cartelJoin")}
                    </button>
                  </div>
                ))}
              </div>
            </Panel>
          )}

          {selected && (
            <Panel title={`${selected.tag} · ${selected.name}`}>
              <Progress label={t("stability")} value={selected.stability} />
              <div className="metric-grid metric-grid--compact">
                <Metric
                  label={t("treasury")}
                  value={formatCents(
                    treasury.data?.balance_cents ??
                      selected.treasury_balance_cents,
                    i18n.language,
                  )}
                />
                <Metric
                  label={t("members", { count: selected.member_count })}
                  value={formatNumber(selected.member_count, i18n.language)}
                />
                <Metric
                  label={t("cartelMyRole")}
                  value={humanize(selected.my_role ?? "public")}
                />
              </div>
              {selected.my_role && (
                <div className="button-row">
                  {selected.my_role !== "leader" &&
                    selected.my_role !== "director" && (
                      <button
                        className="button button--ghost"
                        onClick={() => setPendingAction({ kind: "leave" })}
                      >
                        {t("cartelLeave")}
                      </button>
                    )}
                  {(selected.my_role === "leader" ||
                    selected.my_role === "director") && (
                    <button
                      className="button button--danger"
                      onClick={() => setPendingAction({ kind: "dissolve" })}
                    >
                      {t("cartelDissolve")}
                    </button>
                  )}
                </div>
              )}
            </Panel>
          )}

          {selected?.my_role && (
            <>
              <Panel title={t("organizationMembers")}>
                <StateView
                  loading={members.isLoading}
                  empty={!members.data?.length}
                >
                  <div className="list-stack">
                    {members.data?.map((member) => (
                      <div className="list-row" key={member.profile_id}>
                        <span>
                          <strong>{member.codename}</strong>
                          <small>
                            {humanize(member.role)} · {humanize(member.status)}
                          </small>
                        </span>
                        {(selected.my_role === "leader" ||
                          selected.my_role === "director") &&
                          member.role !== "leader" &&
                          member.role !== "director" &&
                          member.status === "active" && (
                            <div className="button-row">
                              <label
                                className="sr-only"
                                htmlFor={`role-${member.profile_id}`}
                              >
                                {t("changeRole")}
                              </label>
                              <select
                                id={`role-${member.profile_id}`}
                                value={
                                  assignableRoles.includes(
                                    member.role as (typeof assignableRoles)[number],
                                  )
                                    ? member.role
                                    : "member"
                                }
                                onChange={(event) =>
                                  updateRole.mutate({
                                    profileId: member.profile_id,
                                    role: event.target.value,
                                  })
                                }
                              >
                                {assignableRoles.map((role) => (
                                  <option value={role} key={role}>
                                    {humanize(role)}
                                  </option>
                                ))}
                              </select>
                              <button
                                className="button button--small button--ghost"
                                onClick={() =>
                                  setPendingAction({ kind: "transfer", member })
                                }
                              >
                                {t("cartelTransferLeader")}
                              </button>
                            </div>
                          )}
                      </div>
                    ))}
                  </div>
                </StateView>
                {(selected.my_role === "leader" ||
                  selected.my_role === "director" ||
                  selected.my_role === "deputy") && (
                  <InvitationForm
                    pending={invite.isPending}
                    onSubmit={(value) => invite.mutate(value)}
                  />
                )}
              </Panel>

              <Panel title={t("treasury")}>
                {treasury.data && (
                  <>
                    <div className="metric-grid metric-grid--compact">
                      <Metric
                        label={t("cash")}
                        value={formatCents(
                          treasury.data.balance_cents,
                          i18n.language,
                        )}
                      />
                      <Metric
                        label={t("cartelApprovalThreshold")}
                        value={formatCents(
                          treasury.data.approval_threshold_cents,
                          i18n.language,
                        )}
                      />
                      <Metric
                        label={t("cartelSpendLimit")}
                        value={formatCents(
                          treasury.data.single_spend_limit_cents,
                          i18n.language,
                        )}
                      />
                    </div>
                    <DepositForm
                      pending={deposit.isPending}
                      onSubmit={(value) => deposit.mutate(value)}
                    />
                  </>
                )}
                {financeRoles.has(selected.my_role) && (
                  <ExpenseForm
                    pending={expense.isPending}
                    onSubmit={(value) => expense.mutate(value)}
                  />
                )}
                <h3>{t("cartelExpenses")}</h3>
                <StateView empty={!expenses.data?.length}>
                  <div className="list-stack">
                    {expenses.data?.map((item) => (
                      <div className="list-row" key={item.id}>
                        <span>
                          <strong>
                            {formatCents(item.amount_cents, i18n.language)} ·{" "}
                            {item.purpose}
                          </strong>
                          <small>
                            {formatDate(item.requested_at, i18n.language)}
                          </small>
                        </span>
                        <div className="button-row">
                          <Status value={item.status} />
                          {item.status === "pending" &&
                            selected.my_role !== null &&
                            financeRoles.has(selected.my_role) && (
                              <button
                                className="button button--small"
                                onClick={() =>
                                  setPendingAction({
                                    kind: "approve",
                                    expense: item,
                                  })
                                }
                              >
                                {t("cartelApprove")}
                              </button>
                            )}
                        </div>
                      </div>
                    ))}
                  </div>
                </StateView>
              </Panel>

              <Panel title={t("cartelProjects")}>
                {projectRoles.has(selected.my_role) && districts.data && (
                  <ProjectForm
                    districts={districts.data}
                    pending={project.isPending}
                    onSubmit={(value) => project.mutate(value)}
                  />
                )}
                <StateView
                  loading={projects.isLoading}
                  empty={!projects.data?.length}
                >
                  <div className="list-stack">
                    {projects.data?.map((item) => (
                      <article className="data-card" key={item.id}>
                        <span className="eyebrow">
                          {humanize(item.project_type)}
                        </span>
                        <h3>{item.title}</h3>
                        <Progress
                          label={t("cartelProjectProgress")}
                          value={item.progress_bps / 100}
                        />
                        <div className="metric-grid metric-grid--compact">
                          <Metric
                            label={t("cash")}
                            value={`${formatCents(
                              item.contributed_cash_cents,
                              i18n.language,
                            )} / ${formatCents(
                              item.required_cash_cents,
                              i18n.language,
                            )}`}
                          />
                          <Metric
                            label={t("influence")}
                            value={`${item.contributed_influence} / ${item.required_influence}`}
                          />
                          <Metric
                            label={t("intelligence")}
                            value={`${item.contributed_intelligence} / ${item.required_intelligence}`}
                          />
                        </div>
                        <Status value={item.status} />
                        {item.status === "active" && (
                          <ContributionForm
                            project={item}
                            pending={contribution.isPending}
                            onSubmit={(value) =>
                              contribution.mutate({
                                projectId: item.id,
                                value,
                              })
                            }
                          />
                        )}
                      </article>
                    ))}
                  </div>
                </StateView>
              </Panel>

              <Panel title={t("cartelDistrictInfluence")}>
                <StateView
                  loading={influence.isLoading}
                  empty={!influence.data?.length}
                >
                  <div className="card-grid">
                    {influence.data?.map((district) => (
                      <article className="data-card" key={district.district_id}>
                        <span className="eyebrow">
                          <Status value={district.status} />
                        </span>
                        <h3>{district.district_name}</h3>
                        <p>
                          {district.controlling_cartel_name ??
                            t("cartelNoController")}
                        </p>
                        <strong>
                          {t("cartelInfluencePoints", {
                            value: district.top_points,
                          })}
                        </strong>
                      </article>
                    ))}
                  </div>
                </StateView>
              </Panel>

              <Panel title={t("cartelActivity")}>
                <StateView
                  loading={activity.isLoading}
                  empty={!activity.data?.length}
                >
                  <div className="list-stack">
                    {activity.data?.map((item) => (
                      <div className="list-row" key={item.id}>
                        <strong>{humanize(item.action)}</strong>
                        <time dateTime={item.created_at}>
                          {formatDate(item.created_at, i18n.language)}
                        </time>
                      </div>
                    ))}
                  </div>
                </StateView>
              </Panel>

              <Panel title={t("engagementAsyncCollaborationTitle")}>
                <p>{t("engagementAsyncCollaborationDescription")}</p>
                <div className="two-column">
                  <div>
                    <h3>{t("engagementDelegationsTitle")}</h3>
                    <StateView
                      loading={delegations.isLoading}
                      empty={!delegations.data?.length}
                    >
                      {delegations.data?.map((delegation) => (
                        <div className="list-row" key={delegation.id}>
                          <span>
                            <strong>{humanize(delegation.role_key)}</strong>
                            <small>
                              {t("engagementDelegationUntil", {
                                date: formatDate(
                                  delegation.expires_at,
                                  i18n.language,
                                ),
                              })}
                            </small>
                          </span>
                          <Status value={delegation.status} />
                        </div>
                      ))}
                    </StateView>
                    {members.data && (
                      <DelegationForm
                        members={members.data.filter(
                          (member) => member.status === "active",
                        )}
                        pending={createDelegation.isPending}
                        onSubmit={(value) => createDelegation.mutate(value)}
                      />
                    )}
                  </div>
                  <div>
                    <h3>{t("engagementSocialPauseTitle")}</h3>
                    <p>{t("engagementSocialPauseDescription")}</p>
                    {membershipPause.data ? (
                      <div className="card">
                        <Status value={membershipPause.data.status} />
                        <p>
                          {t("engagementPauseUntil", {
                            date: formatDate(
                              membershipPause.data.planned_until,
                              i18n.language,
                            ),
                          })}
                        </p>
                        <button
                          className="button button--secondary"
                          disabled={resumePause.isPending}
                          onClick={() => resumePause.mutate()}
                        >
                          {t("engagementResumeNow")}
                        </button>
                      </div>
                    ) : (
                      <PauseForm
                        pending={startPause.isPending}
                        onSubmit={(value) => startPause.mutate(value)}
                      />
                    )}
                  </div>
                </div>
              </Panel>

              <Panel title={t("engagementCartelChronicleTitle")}>
                <StateView
                  loading={chronicle.isLoading}
                  empty={!chronicle.data?.length}
                >
                  <ol className="list-stack">
                    {chronicle.data?.map((entry) => (
                      <li className="list-row" key={entry.id}>
                        <span>
                          <strong>{t(entry.title_key)}</strong>
                          <small>{t(entry.body_key)}</small>
                        </span>
                        <time dateTime={entry.created_at}>
                          {formatDate(entry.created_at, i18n.language)}
                        </time>
                      </li>
                    ))}
                  </ol>
                </StateView>
              </Panel>
            </>
          )}

          <Panel title={t("cartelLeaderboard")}>
            <StateView
              loading={rankings.isLoading}
              empty={!rankings.data?.length}
            >
              <div className="table-wrap" tabIndex={0}>
                <table>
                  <thead>
                    <tr>
                      <th>{t("rank")}</th>
                      <th>{t("cartelTitleSingle")}</th>
                      <th>{t("score")}</th>
                      <th>{t("influence")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rankings.data?.map((item) => (
                      <tr key={item.cartel_id}>
                        <td>{item.rank}</td>
                        <td>
                          {item.tag} · {item.name}
                        </td>
                        <td>{formatNumber(item.score, i18n.language)}</td>
                        <td>{formatNumber(item.influence, i18n.language)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </StateView>
          </Panel>

          {!cartels.data?.some((item) => item.my_role) && (
            <Panel title={t("cartelCreate")}>
              <CartelCreateForm
                pending={create.isPending}
                onSubmit={(value) => create.mutate(value)}
              />
            </Panel>
          )}
        </div>
      </StateView>
      {pendingAction && (
        <ConfirmDialog
          title={t("cartelConfirmTitle")}
          description={
            pendingAction.kind === "approve"
              ? t("cartelConfirmExpense", {
                  amount: formatCents(
                    pendingAction.expense.amount_cents,
                    i18n.language,
                  ),
                })
              : pendingAction.kind === "transfer"
                ? t("cartelConfirmTransfer", {
                    name: pendingAction.member.codename,
                  })
                : pendingAction.kind === "leave"
                  ? t("cartelConfirmLeave")
                  : t("cartelConfirmDissolve")
          }
          confirmLabel={t("confirm")}
          cancelLabel={t("cancel")}
          pending={action.isPending}
          onCancel={() => setPendingAction(null)}
          onConfirm={() => action.mutate(pendingAction)}
        />
      )}
    </div>
  );
}
