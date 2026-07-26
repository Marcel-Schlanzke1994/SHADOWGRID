import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { createIdempotencyKey } from "@shadowgrid/api-client";
import type {
  Alliance,
  CartelWar,
  ChatChannel,
  ChatMessage,
  DirectMessage,
  District,
  MarketOffer,
  Organization,
  PvpOperation,
  PvpPreview,
  PvpReport,
  PvpTarget,
  Territory,
} from "@shadowgrid/shared-types";
import { client } from "../auth";
import {
  Field,
  Metric,
  Panel,
  Progress,
  StateView,
  Status,
} from "../components";
import { formatCurrency, formatDate, formatNumber } from "../format";

const humanize = (value: string) =>
  value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

const operationTypes = [
  "intelligence_probe",
  "market_pressure",
  "influence_campaign",
  "abstract_disruption",
  "strategic_confrontation",
] as const;

export function PvpPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [targetId, setTargetId] = useState("");
  const [operationType, setOperationType] =
    useState<(typeof operationTypes)[number]>("intelligence_probe");
  const [reportId, setReportId] = useState<string | null>(null);
  const targets = useQuery({
    queryKey: ["pvp-targets"],
    queryFn: () => client.get<PvpTarget[]>("/pvp/targets"),
  });
  const operations = useQuery({
    queryKey: ["pvp-operations"],
    queryFn: () => client.get<PvpOperation[]>("/pvp/operations"),
  });
  useEffect(() => {
    if (!targetId && targets.data?.[0]) setTargetId(targets.data[0].profile_id);
  }, [targetId, targets.data]);
  const preview = useMutation({
    mutationFn: () =>
      client.post<PvpPreview>("/pvp/preview", {
        defender_profile_id: targetId,
        operation_type: operationType,
        risk_posture: "balanced",
      }),
  });
  const launch = useMutation({
    mutationFn: () =>
      client.post<PvpOperation>(
        "/pvp/operations",
        {
          defender_profile_id: targetId,
          operation_type: operationType,
          risk_posture: "balanced",
        },
        createIdempotencyKey(),
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["pvp-operations"] }),
  });
  const defend = useMutation({
    mutationFn: (id: string) =>
      client.post<PvpOperation>(`/pvp/operations/${id}/defend`, {
        action_type: "secure_information",
        commitment: { posture: "standard" },
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["pvp-operations"] }),
  });
  const report = useQuery({
    queryKey: ["pvp-report", reportId],
    queryFn: () => client.get<PvpReport>(`/pvp/reports/${reportId}`),
    enabled: Boolean(reportId),
  });
  const error =
    targets.error ??
    operations.error ??
    preview.error ??
    launch.error ??
    defend.error;
  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("pvpTitle")}</h1>
        <p>{t("pvpDescription")}</p>
      </header>
      <StateView
        loading={targets.isLoading || operations.isLoading}
        error={error}
      >
        <div className="content-grid">
          <Panel title={t("pvpTargets")}>
            <div className="card-grid">
              {targets.data?.map((target) => (
                <button
                  className="data-card data-card--button"
                  key={target.profile_id}
                  onClick={() => setTargetId(target.profile_id)}
                  aria-pressed={targetId === target.profile_id}
                >
                  <span className="eyebrow">
                    {target.cartel_name ?? t("independent")}
                  </span>
                  <h3>{target.codename}</h3>
                  <Status value={target.protection_status} />
                  <span>{humanize(target.estimated_strength)}</span>
                </button>
              ))}
            </div>
          </Panel>
          <Panel title={t("pvpPlan")}>
            <Field label={t("target")}>
              <select
                value={targetId}
                onChange={(event) => setTargetId(event.target.value)}
              >
                {targets.data?.map((target) => (
                  <option value={target.profile_id} key={target.profile_id}>
                    {target.codename}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t("operationType")}>
              <select
                value={operationType}
                onChange={(event) =>
                  setOperationType(
                    event.target.value as (typeof operationTypes)[number],
                  )
                }
              >
                {operationTypes.map((item) => (
                  <option value={item} key={item}>
                    {humanize(item)}
                  </option>
                ))}
              </select>
            </Field>
            <div className="button-row">
              <button
                className="button button--ghost"
                onClick={() => preview.mutate()}
              >
                {t("preview")}
              </button>
              <button
                className="button"
                disabled={!preview.data?.can_launch}
                onClick={() => {
                  if (window.confirm(t("confirmPvpLaunch"))) launch.mutate();
                }}
              >
                {t("launch")}
              </button>
            </div>
            {preview.data && (
              <div className="metric-grid metric-grid--compact">
                <Metric
                  label={t("cash")}
                  value={formatCurrency(
                    preview.data.estimated_cost_cash,
                    i18n.language,
                  )}
                />
                <Metric
                  label={t("influence")}
                  value={preview.data.estimated_cost_influence}
                />
                <Metric
                  label={t("duration")}
                  value={`${preview.data.estimated_minutes} min`}
                />
                <Metric
                  label={t("chanceBand")}
                  value={humanize(preview.data.estimated_success_band)}
                />
                {!preview.data.can_launch && (
                  <p className="notice notice--warning">
                    {preview.data.reasons.map(humanize).join(" · ")}
                  </p>
                )}
              </div>
            )}
          </Panel>
          <Panel title={t("pvpOperations")}>
            <div className="list-stack">
              {operations.data?.map((operation) => (
                <div className="list-row" key={operation.id}>
                  <span>
                    <strong>{humanize(operation.operation_type)}</strong>
                    <small>
                      {humanize(operation.my_side)} ·{" "}
                      {formatDate(operation.resolves_at, i18n.language)}
                    </small>
                  </span>
                  <div className="button-row">
                    <Status value={operation.status} />
                    {operation.my_side === "defender" &&
                      !operation.defense_submitted &&
                      ["warning", "running"].includes(operation.status) && (
                        <button
                          className="button button--small"
                          onClick={() => defend.mutate(operation.id)}
                        >
                          {t("defend")}
                        </button>
                      )}
                    {operation.my_report_id && (
                      <button
                        className="button button--small button--ghost"
                        onClick={() => setReportId(operation.my_report_id)}
                      >
                        {t("report")}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Panel>
          {report.data && (
            <Panel title={t("report")}>
              <Status value={report.data.perspective} />
              <p>{report.data.summary}</p>
              <pre className="report-json">
                {JSON.stringify(report.data.details_json, null, 2)}
              </pre>
            </Panel>
          )}
        </div>
      </StateView>
    </div>
  );
}

export function TerritoriesPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["territories"],
    queryFn: () => client.get<Territory[]>("/territories"),
  });
  const mutate = useMutation({
    mutationFn: ({
      districtId,
      action,
    }: {
      districtId: string;
      action: "claim" | "support";
    }) =>
      client.post(
        `/territories/${districtId}/${action}`,
        action === "claim"
          ? { claim_type: "influence" }
          : { contribution_type: "influence", amount: 10 },
        createIdempotencyKey(),
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["territories"] }),
  });
  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("territoriesTitle")}</h1>
        <p>{t("territoriesDescription")}</p>
      </header>
      <StateView loading={query.isLoading} error={query.error ?? mutate.error}>
        <div className="card-grid">
          {query.data?.map((territory) => {
            const myClaim = territory.active_claims[0];
            return (
              <Panel
                key={territory.district_id}
                title={territory.district_name}
              >
                <Status value={territory.status} />
                {myClaim && (
                  <Progress
                    label={t("claimStrength")}
                    value={myClaim.claim_strength}
                  />
                )}
                <div className="list-stack">
                  {territory.control_points.map((point) => (
                    <div className="list-row" key={point.id}>
                      <span>{humanize(point.point_type)}</span>
                      <Status value={point.status} />
                    </div>
                  ))}
                </div>
                <div className="button-row">
                  <button
                    className="button button--ghost"
                    onClick={() => {
                      if (window.confirm(t("confirmTerritoryClaim")))
                        mutate.mutate({
                          districtId: territory.district_id,
                          action: "claim",
                        });
                    }}
                  >
                    {t("claim")}
                  </button>
                  <button
                    className="button"
                    onClick={() =>
                      mutate.mutate({
                        districtId: territory.district_id,
                        action: "support",
                      })
                    }
                  >
                    {t("support")}
                  </button>
                </div>
              </Panel>
            );
          })}
        </div>
      </StateView>
    </div>
  );
}

export function WarsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [password, setPassword] = useState("");
  const wars = useQuery({
    queryKey: ["cartel-wars"],
    queryFn: () => client.get<CartelWar[]>("/cartel-wars"),
  });
  const organizations = useQuery({
    queryKey: ["organizations"],
    queryFn: () => client.get<Organization[]>("/organizations"),
  });
  const districts = useQuery({
    queryKey: ["districts"],
    queryFn: () => client.get<District[]>("/districts"),
  });
  const propose = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      client.post<CartelWar>("/cartel-wars/propose", body),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["cartel-wars"] }),
  });
  const declare = useMutation({
    mutationFn: (id: string) =>
      client.post<CartelWar>(`/cartel-wars/${id}/declare`, { password }),
    onSuccess: () => {
      setPassword("");
      void queryClient.invalidateQueries({ queryKey: ["cartel-wars"] });
    },
  });
  const join = useMutation({
    mutationFn: ({ id, side }: { id: string; side: string }) =>
      client.post(`/cartel-wars/${id}/join`, { side }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["cartel-wars"] }),
  });
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    propose.mutate({
      defender_cartel_id: data.get("defender"),
      war_type: "district_control",
      district_id: data.get("district") || null,
      declaration_reason: data.get("reason"),
      demand: data.get("demand"),
      peace_conditions: data.get("peace"),
    });
  };
  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("warsTitle")}</h1>
        <p>{t("warsDescription")}</p>
      </header>
      <StateView
        loading={
          wars.isLoading || organizations.isLoading || districts.isLoading
        }
        error={
          wars.error ??
          organizations.error ??
          districts.error ??
          propose.error ??
          declare.error ??
          join.error
        }
      >
        <div className="content-grid">
          <Panel>
            <div className="list-stack">
              {wars.data?.map((war) => (
                <div className="list-row" key={war.id}>
                  <span>
                    <strong>{humanize(war.war_type)}</strong>
                    <small>
                      {war.attacker_score} : {war.defender_score} ·{" "}
                      {humanize(war.my_side ?? "observer")}
                    </small>
                  </span>
                  <div className="button-row">
                    <Status value={war.war_status} />
                    {war.my_side === "attacker" &&
                      war.war_status === "ultimatum" && (
                        <button
                          className="button button--small"
                          disabled={!password}
                          onClick={() => declare.mutate(war.id)}
                        >
                          {t("declare")}
                        </button>
                      )}
                    {war.my_side &&
                      ["preparation", "active"].includes(war.war_status) && (
                        <button
                          className="button button--small button--ghost"
                          onClick={() =>
                            join.mutate({ id: war.id, side: war.my_side! })
                          }
                        >
                          {t("join")}
                        </button>
                      )}
                  </div>
                </div>
              ))}
            </div>
            <Field label={t("currentPassword")}>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
              />
            </Field>
          </Panel>
          <Panel title={t("warPropose")}>
            <form onSubmit={submit}>
              <Field label={t("recipient")}>
                <select name="defender" required>
                  {organizations.data
                    ?.filter((item) => !item.my_role)
                    .map((item) => (
                      <option value={item.id} key={item.id}>
                        {item.name}
                      </option>
                    ))}
                </select>
              </Field>
              <Field label={t("district")}>
                <select name="district">
                  {districts.data?.map((item) => (
                    <option value={item.id} key={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={t("reason")}>
                <textarea name="reason" minLength={10} required />
              </Field>
              <Field label={t("demand")}>
                <input name="demand" minLength={3} required />
              </Field>
              <Field label={t("peaceConditions")}>
                <input name="peace" minLength={3} required />
              </Field>
              <button className="button">{t("propose")}</button>
            </form>
          </Panel>
        </div>
      </StateView>
    </div>
  );
}

export function AlliancesPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const alliances = useQuery({
    queryKey: ["alliances"],
    queryFn: () => client.get<Alliance[]>("/alliances"),
  });
  const organizations = useQuery({
    queryKey: ["organizations"],
    queryFn: () => client.get<Organization[]>("/organizations"),
  });
  const create = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      client.post<Alliance>("/alliances", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alliances"] }),
  });
  const invite = useMutation({
    mutationFn: ({
      allianceId,
      cartelId,
    }: {
      allianceId: string;
      cartelId: string;
    }) =>
      client.post(`/alliances/${allianceId}/invite`, {
        cartel_id: cartelId,
        contribution_limit: 25,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alliances"] }),
  });
  const accept = useMutation({
    mutationFn: (id: string) => client.post(`/alliances/${id}/accept`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alliances"] }),
  });
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    create.mutate({
      name: data.get("name"),
      tag: data.get("tag"),
      charter: data.get("charter"),
      governance_model: "council",
    });
  };
  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("alliancesTitle")}</h1>
        <p>{t("alliancesDescription")}</p>
      </header>
      <StateView
        loading={alliances.isLoading || organizations.isLoading}
        error={
          alliances.error ??
          organizations.error ??
          create.error ??
          invite.error ??
          accept.error
        }
      >
        <div className="content-grid">
          <Panel>
            <div className="card-grid">
              {alliances.data?.map((alliance) => (
                <div className="data-card" key={alliance.id}>
                  <span className="eyebrow">{alliance.tag}</span>
                  <h3>{alliance.name}</h3>
                  <p>{alliance.charter}</p>
                  <span>{t("members", { count: alliance.member_count })}</span>
                  <Status value={alliance.my_role ?? "public"} />
                  {!alliance.my_role && (
                    <button
                      className="button button--small"
                      onClick={() => accept.mutate(alliance.id)}
                    >
                      {t("accept")}
                    </button>
                  )}
                  {alliance.my_role === "chair" && (
                    <select
                      aria-label={t("invite")}
                      defaultValue=""
                      onChange={(event) =>
                        event.target.value &&
                        invite.mutate({
                          allianceId: alliance.id,
                          cartelId: event.target.value,
                        })
                      }
                    >
                      <option value="">{t("invite")}</option>
                      {organizations.data
                        ?.filter((item) => !item.my_role)
                        .map((item) => (
                          <option value={item.id} key={item.id}>
                            {item.name}
                          </option>
                        ))}
                    </select>
                  )}
                </div>
              ))}
            </div>
          </Panel>
          <Panel title={t("allianceCreate")}>
            <form onSubmit={submit}>
              <Field label={t("organizationName")}>
                <input name="name" minLength={3} required />
              </Field>
              <Field label={t("organizationTag")}>
                <input name="tag" minLength={2} maxLength={12} required />
              </Field>
              <Field label={t("charter")}>
                <textarea name="charter" maxLength={1000} />
              </Field>
              <button className="button">{t("create")}</button>
            </form>
          </Panel>
        </div>
      </StateView>
    </div>
  );
}

export function CommunicationsPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [channelId, setChannelId] = useState("");
  const channels = useQuery({
    queryKey: ["chat-channels"],
    queryFn: () => client.get<ChatChannel[]>("/chat/channels"),
  });
  useEffect(() => {
    if (!channelId && channels.data?.[0]) setChannelId(channels.data[0].id);
  }, [channelId, channels.data]);
  const messages = useQuery({
    queryKey: ["chat-messages", channelId],
    queryFn: () =>
      client.get<ChatMessage[]>(`/chat/channels/${channelId}/messages`),
    enabled: Boolean(channelId),
  });
  const direct = useQuery({
    queryKey: ["direct-messages"],
    queryFn: () => client.get<DirectMessage[]>("/messages"),
  });
  const send = useMutation({
    mutationFn: (body: string) =>
      client.post<ChatMessage>(`/chat/channels/${channelId}/messages`, {
        body,
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["chat-messages", channelId] }),
  });
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const body = String(new FormData(form).get("body"));
    send.mutate(body, { onSuccess: () => form.reset() });
  };
  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("communicationsTitle")}</h1>
        <p>{t("communicationsDescription")}</p>
      </header>
      <StateView
        loading={channels.isLoading || direct.isLoading}
        error={channels.error ?? messages.error ?? direct.error ?? send.error}
      >
        <div className="content-grid">
          <Panel title={t("channels")}>
            <div className="button-row">
              {channels.data?.map((channel) => (
                <button
                  className={
                    channel.id === channelId ? "button" : "button button--ghost"
                  }
                  key={channel.id}
                  onClick={() => setChannelId(channel.id)}
                >
                  {channel.name}
                </button>
              ))}
            </div>
            <div className="message-list" aria-live="polite">
              {messages.data?.map((message) => (
                <article key={message.id}>
                  <strong>{message.sender_profile_id.slice(0, 8)}</strong>
                  <p>{message.body}</p>
                  <time>{formatDate(message.created_at, i18n.language)}</time>
                </article>
              ))}
            </div>
            <form onSubmit={submit}>
              <Field label={t("message")}>
                <textarea name="body" minLength={1} maxLength={1000} required />
              </Field>
              <button className="button">{t("send")}</button>
            </form>
          </Panel>
          <Panel title={t("directMessages")}>
            <div className="list-stack">
              {direct.data?.map((message) => (
                <div className="list-row" key={message.id}>
                  <span>
                    <strong>{message.sender_profile_id.slice(0, 8)}</strong>
                    <small>{message.body}</small>
                  </span>
                  <Status value={message.status} />
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </StateView>
    </div>
  );
}

export function MarketPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const offers = useQuery({
    queryKey: ["market-offers"],
    queryFn: () => client.get<MarketOffer[]>("/market/offers"),
  });
  const create = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      client.post<MarketOffer>("/market/offers", body, createIdempotencyKey()),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["market-offers"] }),
  });
  const accept = useMutation({
    mutationFn: (id: string) =>
      client.post(
        `/market/offers/${id}/accept`,
        undefined,
        createIdempotencyKey(),
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["market-offers"] }),
  });
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    create.mutate({
      resource_type: data.get("resource"),
      amount: Number(data.get("amount")),
      unit_price: Number(data.get("price")),
    });
  };
  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("marketTitle")}</h1>
        <p>{t("marketDescription")}</p>
      </header>
      <StateView
        loading={offers.isLoading}
        error={offers.error ?? create.error ?? accept.error}
      >
        <div className="content-grid">
          <Panel>
            <div className="list-stack">
              {offers.data?.map((offer) => (
                <div className="list-row" key={offer.id}>
                  <span>
                    <strong>
                      {humanize(offer.resource_type)} ×{" "}
                      {formatNumber(offer.amount, i18n.language)}
                    </strong>
                    <small>
                      {formatCurrency(offer.unit_price, i18n.language)} / unit
                    </small>
                  </span>
                  <button
                    className="button button--small"
                    onClick={() => accept.mutate(offer.id)}
                  >
                    {t("accept")}
                  </button>
                </div>
              ))}
            </div>
          </Panel>
          <Panel title={t("offerCreate")}>
            <form onSubmit={submit}>
              <Field label={t("resource")}>
                <select name="resource">
                  <option value="capital">{t("capital")}</option>
                  <option value="influence">{t("influence")}</option>
                  <option value="intelligence">{t("intelligence")}</option>
                  <option value="logistics_capacity">{t("logistics")}</option>
                  <option value="personnel_capacity">{t("personnel")}</option>
                </select>
              </Field>
              <Field label={t("amount")}>
                <input
                  name="amount"
                  type="number"
                  min="1"
                  max="1000"
                  required
                />
              </Field>
              <Field label={t("unitPrice")}>
                <input
                  name="price"
                  type="number"
                  min="1"
                  max="100000"
                  required
                />
              </Field>
              <button className="button">{t("create")}</button>
            </form>
          </Panel>
        </div>
      </StateView>
    </div>
  );
}
