import { zodResolver } from "@hookform/resolvers/zod";
import { createIdempotencyKey } from "@shadowgrid/api-client";
import { translateGameValue } from "@shadowgrid/i18n";
import type {
  Profile,
  WorldEventDefinition,
  WorldEventInstance,
  WorldEventPreview,
} from "@shadowgrid/shared-types";
import {
  worldEventPlanSchema,
  type WorldEventPlanInput,
} from "@shadowgrid/validation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { client } from "../auth";
import { ConfirmDialog, Field, Panel, StateView, Status } from "../components";
import { formatDate } from "../format";

const scopeTypes = [
  "world",
  "city",
  "district",
  "industry",
  "company",
] as const;

const humanize = translateGameValue;

export function WorldEventsAdmin() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [pendingPlan, setPendingPlan] = useState<WorldEventPlanInput | null>(
    null,
  );
  const [preview, setPreview] = useState<WorldEventPreview | null>(null);
  const [message, setMessage] = useState("");
  const profile = useQuery({
    queryKey: ["profile"],
    queryFn: () => client.get<Profile>("/profiles/me"),
  });
  const definitions = useQuery({
    queryKey: ["admin-world-event-definitions"],
    queryFn: () =>
      client.get<WorldEventDefinition[]>("/admin/world-events/definitions"),
  });
  const instances = useQuery({
    queryKey: ["world-events"],
    queryFn: () => client.get<WorldEventInstance[]>("/world-events/current"),
  });
  const initialValues = useMemo<WorldEventPlanInput | undefined>(() => {
    const firstDefinition = definitions.data?.[0];
    if (!firstDefinition) {
      return undefined;
    }
    return {
      event_key: firstDefinition.event_key,
      scope_type: firstDefinition.default_scope_type,
      starts_at: new Date(Date.now() + 60_000).toISOString().slice(0, 16),
      duration_minutes: firstDefinition.default_duration_minutes,
    };
  }, [definitions.data]);
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<WorldEventPlanInput>({
    resolver: zodResolver(worldEventPlanSchema),
    values: initialValues,
  });
  const scopeType = watch("scope_type");
  const planPayload = (value: WorldEventPlanInput) => {
    const effectOverrides = Object.fromEntries(
      [
        ["revenue_multiplier_bps", value.revenue_multiplier_bps],
        ["cost_multiplier_bps", value.cost_multiplier_bps],
        ["demand_multiplier_bps", value.demand_multiplier_bps],
      ].filter((entry): entry is [string, number] => entry[1] !== undefined),
    );
    return {
      world_id: profile.data?.world_id,
      event_key: value.event_key,
      scope_type: value.scope_type,
      scope_id: value.scope_type === "world" ? undefined : value.scope_id,
      starts_at: new Date(value.starts_at).toISOString(),
      duration_minutes: value.duration_minutes,
      effect_overrides: effectOverrides,
    };
  };
  const previewMutation = useMutation({
    mutationFn: (value: WorldEventPlanInput) =>
      client.post<WorldEventPreview>(
        "/admin/world-events/preview",
        planPayload(value),
      ),
    onSuccess: (value) => setPreview(value),
  });
  const activateMutation = useMutation({
    mutationFn: (value: WorldEventPlanInput) =>
      client.post<WorldEventInstance>(
        "/admin/world-events/activate",
        planPayload(value),
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setMessage(t("eventActivatedSuccess"));
      setPreview(null);
      setPendingPlan(null);
      await queryClient.invalidateQueries({ queryKey: ["world-events"] });
    },
  });
  const endMutation = useMutation({
    mutationFn: (instanceId: string) =>
      client.post<WorldEventInstance>(
        `/admin/world-events/${instanceId}/end`,
        { reason: "Ended by local administrator." },
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setMessage(t("eventEndedSuccess"));
      await queryClient.invalidateQueries({ queryKey: ["world-events"] });
    },
  });
  const onPreview = (value: WorldEventPlanInput) => {
    setPendingPlan(value);
    previewMutation.mutate(value);
  };
  const error =
    profile.error ??
    definitions.error ??
    instances.error ??
    previewMutation.error ??
    activateMutation.error ??
    endMutation.error;

  return (
    <Panel title={t("eventAdminTitle")}>
      {message && (
        <p className="notice notice--success" role="status">
          {message}
        </p>
      )}
      <StateView
        loading={
          profile.isLoading || definitions.isLoading || instances.isLoading
        }
        error={error}
        empty={!definitions.data?.length}
      >
        <p>{t("eventAdminDescription")}</p>
        <form onSubmit={handleSubmit(onPreview)}>
          <Field label={t("eventDefinition")} error={errors.event_key?.message}>
            <select {...register("event_key")}>
              {definitions.data
                ?.filter((item) => item.enabled)
                .map((item) => (
                  <option key={item.id} value={item.event_key}>
                    {item.title} ·{" "}
                    {t("versionValue", { version: item.version })}
                  </option>
                ))}
            </select>
          </Field>
          <Field label={t("eventScope")} error={errors.scope_type?.message}>
            <select {...register("scope_type")}>
              {scopeTypes.map((item) => (
                <option key={item} value={item}>
                  {humanize(item)}
                </option>
              ))}
            </select>
          </Field>
          {scopeType !== "world" && (
            <Field
              label={t("eventScopeId")}
              hint={t("eventScopeIdHint")}
              error={errors.scope_id?.message}
            >
              <input {...register("scope_id")} />
            </Field>
          )}
          <Field label={t("eventStarts")} error={errors.starts_at?.message}>
            <input type="datetime-local" {...register("starts_at")} />
          </Field>
          <Field
            label={t("eventDuration")}
            error={errors.duration_minutes?.message}
          >
            <input
              type="number"
              min={1}
              max={43_200}
              {...register("duration_minutes", { valueAsNumber: true })}
            />
          </Field>
          {(
            [
              ["revenue_multiplier_bps", t("eventRevenueMultiplier")],
              ["cost_multiplier_bps", t("eventCostMultiplier")],
              ["demand_multiplier_bps", t("eventDemandMultiplier")],
            ] as const
          ).map(([name, label]) => (
            <Field key={name} label={label} error={errors[name]?.message}>
              <input
                type="number"
                min={2_500}
                max={30_000}
                placeholder={t("eventTemplateDefault")}
                {...register(name, {
                  setValueAs: (value: string) =>
                    value === "" ? undefined : Number(value),
                })}
              />
            </Field>
          ))}
          <button
            className="button"
            disabled={previewMutation.isPending || !profile.data}
          >
            {t("eventPreview")}
          </button>
        </form>

        <h3>{t("eventFeed")}</h3>
        {!instances.data?.length ? (
          <StateView empty>{t("eventFeedEmpty")}</StateView>
        ) : (
          <div className="stack">
            {instances.data?.map((instance) => (
              <div className="list-row" key={instance.id}>
                <span>
                  <strong>{instance.title}</strong>
                  <small>
                    {humanize(instance.scope_type)} ·{" "}
                    {formatDate(instance.starts_at, i18n.language)} →{" "}
                    {formatDate(instance.ends_at, i18n.language)}
                  </small>
                </span>
                <Status value={instance.status} />
                {["scheduled", "active"].includes(instance.status) && (
                  <button
                    className="button button--small button--danger"
                    disabled={endMutation.isPending}
                    onClick={() => endMutation.mutate(instance.id)}
                  >
                    {t("eventEnd")}
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </StateView>
      {preview && pendingPlan && (
        <ConfirmDialog
          title={t("eventConfirmActivation")}
          description={
            <div>
              <p>
                <strong>{preview.title}</strong>
              </p>
              <p>{preview.description}</p>
              <p>
                {humanize(preview.scope_type)} ·{" "}
                {t("eventAffectedCompanies", {
                  count: preview.affected_companies,
                })}
              </p>
              <p>
                {formatDate(preview.starts_at, i18n.language)} →{" "}
                {formatDate(preview.ends_at, i18n.language)}
              </p>
            </div>
          }
          confirmLabel={t("eventActivate")}
          cancelLabel={t("cancel")}
          pending={activateMutation.isPending}
          onCancel={() => {
            setPreview(null);
            setPendingPlan(null);
          }}
          onConfirm={() => activateMutation.mutate(pendingPlan)}
        />
      )}
    </Panel>
  );
}
