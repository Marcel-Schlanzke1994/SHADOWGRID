import { zodResolver } from "@hookform/resolvers/zod";
import { createIdempotencyKey } from "@shadowgrid/api-client";
import { translateGameValue } from "@shadowgrid/i18n";
import type {
  IntelligenceOffer,
  IntelligenceOperation,
  IntelligenceReport,
  Profile,
  PvpTarget,
  Specialist,
  StrategicAction,
  StrategicEffect,
} from "@shadowgrid/shared-types";
import {
  intelligenceOfferSchema,
  intelligenceOperationSchema,
  strategicActionSchema,
  type IntelligenceOfferInput,
  type IntelligenceOperationInput,
  type StrategicActionInput,
} from "@shadowgrid/validation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
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

const eligibleRoles = new Set([
  "technology_expert",
  "market_analyst",
  "compliance_officer",
  "diplomat",
]);

const informationTypes = ["public", "analyzed", "covert"] as const;
const categories = [
  "economy",
  "companies",
  "exchange",
  "cartel",
  "territory",
  "specialists",
  "reputation",
] as const;
const actionTypes = [
  "delay_project",
  "weaken_reputation",
  "raise_operating_cost",
  "make_information_unreliable",
  "stress_specialist",
] as const;
const profileActionTypes = new Set([
  "weaken_reputation",
  "make_information_unreliable",
]);

const humanize = translateGameValue;

function OperationForm({
  targets,
  specialists,
  pending,
  onSubmit,
}: {
  targets: PvpTarget[];
  specialists: Specialist[];
  pending: boolean;
  onSubmit: (value: IntelligenceOperationInput) => void;
}) {
  const { t } = useTranslation();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<IntelligenceOperationInput>({
    resolver: zodResolver(intelligenceOperationSchema),
    defaultValues: {
      target_profile_id: targets[0]?.profile_id ?? "",
      specialist_id: specialists[0]?.id ?? "",
      information_type: "analyzed",
      category: "economy",
    },
  });
  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <Field label={t("intelTarget")} error={errors.target_profile_id?.message}>
        <select {...register("target_profile_id")}>
          {targets.map((target) => (
            <option key={target.profile_id} value={target.profile_id}>
              {target.codename} · {humanize(target.protection_status)}
            </option>
          ))}
        </select>
      </Field>
      <Field label={t("intelSpecialist")} error={errors.specialist_id?.message}>
        <select {...register("specialist_id")}>
          {specialists.map((specialist) => (
            <option key={specialist.id} value={specialist.id}>
              {specialist.name} · {humanize(specialist.role)} ·{" "}
              {t("specialistEnergyValue", { value: specialist.energy })}
            </option>
          ))}
        </select>
      </Field>
      <Field
        label={t("intelInformationType")}
        error={errors.information_type?.message}
      >
        <select {...register("information_type")}>
          {informationTypes.map((item) => (
            <option key={item} value={item}>
              {humanize(item)}
            </option>
          ))}
        </select>
      </Field>
      <Field label={t("intelCategory")} error={errors.category?.message}>
        <select {...register("category")}>
          {categories.map((item) => (
            <option key={item} value={item}>
              {humanize(item)}
            </option>
          ))}
        </select>
      </Field>
      <button
        className="button"
        disabled={pending || !targets.length || !specialists.length}
      >
        {t("intelLaunch")}
      </button>
    </form>
  );
}

function StrategicActionForm({
  targets,
  specialists,
  pending,
  onSubmit,
}: {
  targets: PvpTarget[];
  specialists: Specialist[];
  pending: boolean;
  onSubmit: (value: StrategicActionInput) => void;
}) {
  const { t } = useTranslation();
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<StrategicActionInput>({
    resolver: zodResolver(strategicActionSchema),
    defaultValues: {
      target_profile_id: targets[0]?.profile_id ?? "",
      specialist_id: specialists[0]?.id ?? "",
      action_type: "make_information_unreliable",
    },
  });
  const actionType = watch("action_type");
  const needsAsset = !profileActionTypes.has(actionType);
  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <Field label={t("intelTarget")} error={errors.target_profile_id?.message}>
        <select {...register("target_profile_id")}>
          {targets.map((target) => (
            <option key={target.profile_id} value={target.profile_id}>
              {target.codename}
            </option>
          ))}
        </select>
      </Field>
      <Field label={t("intelSpecialist")} error={errors.specialist_id?.message}>
        <select {...register("specialist_id")}>
          {specialists.map((specialist) => (
            <option key={specialist.id} value={specialist.id}>
              {specialist.name} · {humanize(specialist.role)}
            </option>
          ))}
        </select>
      </Field>
      <Field
        label={t("strategicActionType")}
        error={errors.action_type?.message}
      >
        <select {...register("action_type")}>
          {actionTypes.map((item) => (
            <option key={item} value={item}>
              {humanize(item)}
            </option>
          ))}
        </select>
      </Field>
      {needsAsset && (
        <Field
          label={t("strategicAssetId")}
          hint={t("strategicAssetIdHint")}
          error={errors.target_id?.message}
        >
          <input {...register("target_id")} />
        </Field>
      )}
      <button
        className="button"
        disabled={pending || !targets.length || !specialists.length}
      >
        {t("strategicLaunch")}
      </button>
    </form>
  );
}

function ReportOfferForm({
  pending,
  onSubmit,
}: {
  pending: boolean;
  onSubmit: (value: IntelligenceOfferInput) => void;
}) {
  const { t } = useTranslation();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<IntelligenceOfferInput>({
    resolver: zodResolver(intelligenceOfferSchema),
    defaultValues: { price_cents: 100_000, expires_in_hours: 12 },
  });
  return (
    <form className="compact-form" onSubmit={handleSubmit(onSubmit)}>
      <Field label={t("intelOfferPrice")} error={errors.price_cents?.message}>
        <input
          type="number"
          min={1}
          step={1}
          {...register("price_cents", { valueAsNumber: true })}
        />
      </Field>
      <Field
        label={t("intelOfferHours")}
        error={errors.expires_in_hours?.message}
      >
        <input
          type="number"
          min={1}
          max={168}
          {...register("expires_in_hours", { valueAsNumber: true })}
        />
      </Field>
      <button className="button button--small" disabled={pending}>
        {t("intelSell")}
      </button>
    </form>
  );
}

export function IntelligencePage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [pendingOffer, setPendingOffer] = useState<IntelligenceOffer | null>(
    null,
  );
  const [successMessage, setSuccessMessage] = useState("");
  const profile = useQuery({
    queryKey: ["profile"],
    queryFn: () => client.get<Profile>("/profiles/me"),
  });
  const targets = useQuery({
    queryKey: ["pvp-targets"],
    queryFn: () => client.get<PvpTarget[]>("/pvp/targets"),
  });
  const specialists = useQuery({
    queryKey: ["specialists"],
    queryFn: () => client.get<Specialist[]>("/specialists"),
  });
  const reports = useQuery({
    queryKey: ["intelligence-reports"],
    queryFn: () => client.get<IntelligenceReport[]>("/intelligence/reports"),
  });
  const operations = useQuery({
    queryKey: ["intelligence-operations"],
    queryFn: () =>
      client.get<IntelligenceOperation[]>("/intelligence/operations"),
  });
  const offers = useQuery({
    queryKey: ["intelligence-offers"],
    queryFn: () => client.get<IntelligenceOffer[]>("/intelligence/offers"),
  });
  const actions = useQuery({
    queryKey: ["strategic-actions"],
    queryFn: () => client.get<StrategicAction[]>("/strategic-actions/me"),
  });
  const effects = useQuery({
    queryKey: ["strategic-effects"],
    queryFn: () =>
      client.get<StrategicEffect[]>("/strategic-actions/effects/me"),
  });
  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["intelligence-reports"] }),
      queryClient.invalidateQueries({ queryKey: ["intelligence-operations"] }),
      queryClient.invalidateQueries({ queryKey: ["intelligence-offers"] }),
      queryClient.invalidateQueries({ queryKey: ["strategic-actions"] }),
      queryClient.invalidateQueries({ queryKey: ["strategic-effects"] }),
      queryClient.invalidateQueries({ queryKey: ["specialists"] }),
      queryClient.invalidateQueries({ queryKey: ["resources"] }),
    ]);
  };
  const operationMutation = useMutation({
    mutationFn: (value: IntelligenceOperationInput) =>
      client.post<IntelligenceOperation>(
        "/intelligence/operations",
        value,
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setSuccessMessage(t("intelOperationSuccess"));
      await invalidate();
    },
  });
  const strategicMutation = useMutation({
    mutationFn: (value: StrategicActionInput) => {
      const targetId = profileActionTypes.has(value.action_type)
        ? value.target_profile_id
        : value.target_id;
      return client.post<StrategicAction>(
        "/strategic-actions",
        { ...value, target_id: targetId },
        createIdempotencyKey(),
      );
    },
    onSuccess: async () => {
      setSuccessMessage(t("strategicActionSuccess"));
      await invalidate();
    },
  });
  const sellMutation = useMutation({
    mutationFn: ({
      reportId,
      value,
    }: {
      reportId: string;
      value: IntelligenceOfferInput;
    }) =>
      client.post<IntelligenceOffer>(
        `/intelligence/reports/${reportId}/sell`,
        value,
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setSuccessMessage(t("intelOfferSuccess"));
      await invalidate();
    },
  });
  const buyMutation = useMutation({
    mutationFn: (offerId: string) =>
      client.post<IntelligenceReport>(
        `/intelligence/offers/${offerId}/buy`,
        undefined,
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setPendingOffer(null);
      setSuccessMessage(t("intelPurchaseSuccess"));
      await invalidate();
    },
  });
  const eligibleSpecialists =
    specialists.data?.filter(
      (item) =>
        eligibleRoles.has(item.role) &&
        ["hired", "assigned"].includes(item.status) &&
        item.energy >= 8,
    ) ?? [];
  const queryError =
    profile.error ??
    targets.error ??
    specialists.error ??
    reports.error ??
    operations.error ??
    offers.error ??
    actions.error ??
    effects.error;
  const mutationError =
    operationMutation.error ??
    strategicMutation.error ??
    sellMutation.error ??
    buyMutation.error;
  const loading =
    profile.isLoading ||
    targets.isLoading ||
    specialists.isLoading ||
    reports.isLoading ||
    operations.isLoading ||
    offers.isLoading ||
    actions.isLoading ||
    effects.isLoading;

  return (
    <div className="page page--intelligence">
      <header className="page-header">
        <h1>{t("intelPhaseTitle")}</h1>
        <p>{t("intelPhaseDescription")}</p>
      </header>
      {successMessage && (
        <p className="notice notice--success" role="status">
          {successMessage}
        </p>
      )}
      {mutationError && <StateView error={mutationError}>{null}</StateView>}
      <StateView loading={loading} error={queryError}>
        <div className="two-column">
          <Panel title={t("intelOperationPanel")}>
            {!targets.data?.length || !eligibleSpecialists.length ? (
              <StateView empty>{t("intelPrerequisitesEmpty")}</StateView>
            ) : (
              <OperationForm
                targets={targets.data}
                specialists={eligibleSpecialists}
                pending={operationMutation.isPending}
                onSubmit={(value) => operationMutation.mutate(value)}
              />
            )}
          </Panel>
          <Panel title={t("strategicActionPanel")}>
            {!targets.data?.length || !eligibleSpecialists.length ? (
              <StateView empty>{t("intelPrerequisitesEmpty")}</StateView>
            ) : (
              <StrategicActionForm
                targets={targets.data}
                specialists={eligibleSpecialists}
                pending={strategicMutation.isPending}
                onSubmit={(value) => strategicMutation.mutate(value)}
              />
            )}
          </Panel>
        </div>

        <Panel title={t("intelReports")}>
          {!reports.data?.length ? (
            <StateView empty>{t("intelReportsEmpty")}</StateView>
          ) : (
            <div className="card-grid">
              {reports.data.map((report) => (
                <article className="subcard" key={report.id}>
                  <div className="button-row">
                    <Status
                      value={
                        report.is_expired ? "expired" : report.information_type
                      }
                      uncertain={report.confidence_bps < 7_000}
                    />
                    <Status value={humanize(report.category)} />
                  </div>
                  <h3>{humanize(report.category)}</h3>
                  <p>{report.statement}</p>
                  <Progress
                    label={t("intelConfidence", {
                      value: report.confidence_bps / 100,
                    })}
                    value={report.confidence_bps / 100}
                  />
                  <dl className="definition-list">
                    <div>
                      <dt>{t("intelSource")}</dt>
                      <dd>{humanize(report.source_category)}</dd>
                    </div>
                    <div>
                      <dt>{t("intelAge")}</dt>
                      <dd>
                        {t("hoursValue", {
                          count: Math.floor(report.age_seconds / 3600),
                        })}
                      </dd>
                    </div>
                    <div>
                      <dt>{t("intelExpires")}</dt>
                      <dd>{formatDate(report.expires_at, i18n.language)}</dd>
                    </div>
                  </dl>
                  {report.tradable && !report.is_expired && (
                    <ReportOfferForm
                      pending={sellMutation.isPending}
                      onSubmit={(value) =>
                        sellMutation.mutate({ reportId: report.id, value })
                      }
                    />
                  )}
                </article>
              ))}
            </div>
          )}
        </Panel>

        <Panel title={t("intelMarket")}>
          {!offers.data?.some((offer) => offer.status === "open") ? (
            <StateView empty>{t("intelMarketEmpty")}</StateView>
          ) : (
            <div
              className="table-wrap"
              tabIndex={0}
              role="region"
              aria-label={t("intelMarket")}
            >
              <table>
                <thead>
                  <tr>
                    <th>{t("intelCategory")}</th>
                    <th>{t("intelConfidenceLabel")}</th>
                    <th>{t("intelOfferPrice")}</th>
                    <th>{t("intelExpires")}</th>
                    <th>{t("actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {offers.data
                    .filter((offer) => offer.status === "open")
                    .map((offer) => (
                      <tr key={offer.id}>
                        <td>{humanize(offer.category)}</td>
                        <td>{offer.confidence_bps / 100}%</td>
                        <td>{formatCents(offer.price_cents, i18n.language)}</td>
                        <td>{formatDate(offer.expires_at, i18n.language)}</td>
                        <td>
                          {offer.seller_profile_id === profile.data?.id ? (
                            <Status value={t("intelMyOffer")} />
                          ) : (
                            <button
                              className="button button--small"
                              onClick={() => setPendingOffer(offer)}
                            >
                              {t("intelBuy")}
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <div className="two-column">
          <Panel title={t("intelOperationHistory")}>
            {!operations.data?.length ? (
              <StateView empty>{t("intelOperationsEmpty")}</StateView>
            ) : (
              <ul className="timeline">
                {operations.data.map((operation) => (
                  <li key={operation.id}>
                    <Status
                      value={operation.outcome}
                      uncertain={operation.outcome !== "success"}
                    />
                    <strong>{humanize(operation.category)}</strong>
                    <small>
                      {formatDate(operation.created_at, i18n.language)} ·{" "}
                      {operation.detected
                        ? t("intelDetected")
                        : t("intelUndetected")}
                    </small>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          <Panel title={t("strategicHistory")}>
            {!actions.data?.length ? (
              <StateView empty>{t("strategicHistoryEmpty")}</StateView>
            ) : (
              <ul className="timeline">
                {actions.data.map((action) => (
                  <li key={action.id}>
                    <Status
                      value={action.outcome}
                      uncertain={action.outcome !== "success"}
                    />
                    <strong>{humanize(action.action_type)}</strong>
                    <small>
                      {formatDate(action.created_at, i18n.language)}
                    </small>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>

        <Panel title={t("strategicEffects")}>
          {!effects.data?.length ? (
            <StateView empty>{t("strategicEffectsEmpty")}</StateView>
          ) : (
            <div className="metric-grid">
              {effects.data.map((effect) => (
                <div key={effect.id}>
                  <Metric
                    label={humanize(effect.effect_type)}
                    value={formatNumber(effect.magnitude, i18n.language)}
                  />
                  <small>
                    {t("intelUntil", {
                      date: formatDate(effect.ends_at, i18n.language),
                    })}
                  </small>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </StateView>
      {pendingOffer && (
        <ConfirmDialog
          title={t("intelConfirmPurchase")}
          description={t("intelConfirmPurchaseBody", {
            amount: formatCents(pendingOffer.price_cents, i18n.language),
          })}
          confirmLabel={t("confirm")}
          cancelLabel={t("cancel")}
          pending={buyMutation.isPending}
          onCancel={() => setPendingOffer(null)}
          onConfirm={() => buyMutation.mutate(pendingOffer.id)}
        />
      )}
    </div>
  );
}
