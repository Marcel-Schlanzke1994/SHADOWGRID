import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import cytoscape from "cytoscape";
import { ApiError, createIdempotencyKey } from "@shadowgrid/api-client";
import {
  companyIndustries,
  companyInvestmentTypes,
  operationTypes,
  organizationArchetypes,
} from "@shadowgrid/game-config";
import type {
  City,
  Company,
  CompanyDetail,
  CompanyEconomyReport,
  District,
  EconomyStatus,
  IntelReport,
  Operation,
  Profile,
  Specialist,
  SpecialistEffects,
  SpecialistMarketCandidate,
  SpecialistPayrollReport,
  WorldEventInstance,
} from "@shadowgrid/shared-types";
import { client } from "../auth";
import { GlobalBackdrop, GlobalDayNightBackdrop } from "../GlobalBackdrop";
import {
  ConfirmDialog,
  Field,
  Metric,
  Panel,
  Progress,
  StateView,
  Status,
} from "../components";
import {
  formatCents,
  formatCurrency,
  formatDate,
  formatNumber,
} from "../format";

const humanize = (value: string) =>
  value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const useProfile = () =>
  useQuery({
    queryKey: ["profile"],
    queryFn: () => client.get<Profile>("/profiles/me"),
  });
const useDistricts = () =>
  useQuery({
    queryKey: ["districts"],
    queryFn: () => client.get<District[]>("/districts"),
  });

function EconomyReportChart({
  reports,
  title,
  locale,
}: {
  reports: CompanyEconomyReport[];
  title: string;
  locale: string;
}) {
  const { t } = useTranslation();
  const chartId = useId();
  const chronological = [...reports].reverse();
  const width = 640;
  const height = 220;
  const inset = 24;
  const values = chronological.flatMap((report) => [
    report.revenue_cents,
    report.cost_cents,
    report.profit_cents,
  ]);
  const minimum = Math.min(0, ...values);
  const maximum = Math.max(1, ...values);
  const range = Math.max(1, maximum - minimum);
  const x = (index: number) =>
    chronological.length === 1
      ? width / 2
      : inset +
        (index * (width - inset * 2)) / Math.max(1, chronological.length - 1);
  const y = (value: number) =>
    inset + ((maximum - value) * (height - inset * 2)) / range;
  const points = (field: "revenue_cents" | "cost_cents" | "profit_cents") =>
    chronological
      .map((report, index) => `${x(index)},${y(report[field])}`)
      .join(" ");
  return (
    <figure className="economy-chart">
      <figcaption id={`${chartId}-title`}>{title}</figcaption>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-labelledby={`${chartId}-title ${chartId}-description`}
      >
        <desc id={`${chartId}-description`}>
          {chronological
            .map(
              (report) =>
                `${formatDate(report.created_at, locale)}: ${t(
                  "revenue",
                )} ${formatCents(report.revenue_cents, locale)}, ${t(
                  "cost",
                )} ${formatCents(report.cost_cents, locale)}, ${t(
                  "companyProfit",
                )} ${formatCents(report.profit_cents, locale)}`,
            )
            .join(". ")}
        </desc>
        <line
          className="economy-chart__axis"
          x1={inset}
          x2={width - inset}
          y1={y(0)}
          y2={y(0)}
        />
        <polyline
          className="economy-chart__line economy-chart__line--revenue"
          points={points("revenue_cents")}
        />
        <polyline
          className="economy-chart__line economy-chart__line--cost"
          points={points("cost_cents")}
        />
        <polyline
          className="economy-chart__line economy-chart__line--profit"
          points={points("profit_cents")}
        />
      </svg>
      <div className="economy-chart__legend" aria-hidden="true">
        <span className="economy-chart__legend-revenue">● {t("revenue")}</span>
        <span className="economy-chart__legend-cost">● {t("cost")}</span>
        <span className="economy-chart__legend-profit">
          ● {t("companyProfit")}
        </span>
      </div>
    </figure>
  );
}

export function WorldPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const cities = useQuery({
    queryKey: ["world-cities"],
    queryFn: () => client.get<City[]>("/world/cities"),
  });
  const [cityId, setCityId] = useState("");
  useEffect(() => {
    if (!cityId && cities.data?.[0]) setCityId(cities.data[0].id);
  }, [cityId, cities.data]);
  const districts = useQuery({
    queryKey: ["city-districts", cityId],
    queryFn: () => client.get<District[]>(`/world/cities/${cityId}/districts`),
    enabled: Boolean(cityId),
  });
  const join = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      client.post<Profile>(
        "/players/me/select-city",
        body,
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries();
      navigate("/tutorial");
    },
  });
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    join.mutate({
      city_id: cityId,
      codename: data.get("codename"),
      archetype: data.get("archetype"),
      home_district_id: data.get("district"),
    });
  };
  return (
    <main className="centered-page centered-page--worlds">
      <div className="public-brand">
        <img
          className="brand__logo"
          src="/assets/branding/shadowgrid-logo-horizontal-dark.svg"
          alt={t("appName")}
        />
      </div>
      <GlobalBackdrop
        desktopAssetId="global-world-selection-desktop-v1"
        mobileAssetId="global-world-selection-mobile-v1"
        variant="world"
      />
      <Panel className="wide-card">
        <h1>{t("worldsTitle")}</h1>
        <StateView
          loading={cities.isLoading || districts.isLoading || join.isPending}
          error={cities.error ?? districts.error ?? join.error}
          empty={cities.data?.length === 0}
        >
          <form onSubmit={submit}>
            <Field label={t("worldsTitle")}>
              <select
                id="field-choose-a-city"
                value={cityId}
                onChange={(event) => setCityId(event.target.value)}
              >
                {cities.data?.map((city) => (
                  <option value={city.id} key={city.id}>
                    {city.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t("codename")}>
              <input
                id="field-codename"
                name="codename"
                minLength={2}
                maxLength={40}
                required
              />
            </Field>
            <Field label={t("archetype")}>
              <select id="field-organization-approach" name="archetype">
                {organizationArchetypes.map((item) => (
                  <option key={item} value={item}>
                    {humanize(item)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t("homeDistrict")}>
              <select id="field-starting-district" name="district" required>
                {districts.data?.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </Field>
            <button className="button">{t("joinWorld")}</button>
          </form>
        </StateView>
      </Panel>
    </main>
  );
}

export function TutorialPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const profile = useProfile();
  const mutation = useMutation({
    mutationFn: (step: number) =>
      client.patch<Profile>("/profiles/me/tutorial", { step }),
    onSuccess: async (value) => {
      queryClient.setQueryData(["profile"], value);
      if (value.tutorial_step >= 7) navigate("/command");
    },
  });
  if (
    profile.error instanceof ApiError &&
    profile.error.code === "world.not_joined"
  )
    return <Navigate to="/worlds" replace />;
  const step = profile.data?.tutorial_step ?? 0;
  const steps = [
    t("tutorialChooseApproach"),
    t("tutorialReviewBusiness"),
    t("tutorialMeetSpecialists"),
    t("tutorialInspectDistricts"),
    t("tutorialReviewIntel"),
    t("tutorialCompareRisk"),
    t("tutorialOpenInvestigation"),
  ];
  return (
    <main className="centered-page">
      <Panel className="wide-card">
        <p className="eyebrow">{t("onboardingEyebrow")}</p>
        <h1>{t("tutorialTitle")}</h1>
        <StateView
          loading={profile.isLoading || mutation.isPending}
          error={profile.error ?? mutation.error}
        >
          <Progress
            label={t("tutorialProgress", {
              current: Math.min(7, step + 1),
              total: 7,
            })}
            value={(step / 7) * 100}
          />
          <div className="tutorial-step">
            <span className="tutorial-step__number">
              {String(Math.min(7, step + 1)).padStart(2, "0")}
            </span>
            <p>{steps[Math.min(step, 6)]}</p>
          </div>
          <button
            className="button"
            onClick={() => mutation.mutate(Math.min(7, step + 1))}
          >
            {t("tutorialNext")}
          </button>
        </StateView>
      </Panel>
    </main>
  );
}

export function DashboardPage() {
  const { t, i18n } = useTranslation();
  const profile = useProfile();
  const operations = useQuery({
    queryKey: ["operations"],
    queryFn: () => client.get<Operation[]>("/operations"),
    enabled: Boolean(profile.data),
  });
  const events = useQuery({
    queryKey: ["events"],
    queryFn: () => client.get<WorldEventInstance[]>("/world-events"),
    enabled: Boolean(profile.data),
  });
  if (
    profile.error instanceof ApiError &&
    profile.error.code === "world.not_joined"
  )
    return <Navigate to="/worlds" replace />;
  const p = profile.data;
  return (
    <div className="page page--command">
      <GlobalDayNightBackdrop
        dayAssetId="global-command-center-day-v1"
        nightAssetId="global-command-center-night-v1"
        variant="command"
      />
      <header className="page-header">
        <p className="eyebrow">{t("liveStateEyebrow")}</p>
        <h1>{t("commandTitle")}</h1>
        <p>{t("commandSubtitle")}</p>
      </header>
      {events.data
        ?.filter((event) => event.status === "active")
        .map((event) => (
          <section
            className="notice notice--warning"
            aria-label={t("eventActiveBanner")}
            key={event.id}
          >
            <strong>{event.title}</strong>
            <span>{event.description}</span>
            <small>
              {t("eventActiveUntil", {
                date: formatDate(event.ends_at, i18n.language),
              })}
            </small>
          </section>
        ))}
      <StateView loading={profile.isLoading} error={profile.error}>
        {p && (
          <>
            <div className="metric-grid">
              <Metric
                label={t("cash")}
                value={formatCurrency(p.resources.cash, i18n.language)}
              />
              <Metric
                label={t("capital")}
                value={formatCurrency(p.resources.capital, i18n.language)}
              />
              <Metric
                label={t("influence")}
                value={formatNumber(p.resources.influence, i18n.language)}
              />
              <Metric
                label={t("intelligence")}
                value={formatNumber(p.resources.intelligence, i18n.language)}
              />
              <Metric
                label={t("pressure")}
                value={`${p.investigation_pressure}/100`}
                tone={p.investigation_pressure > 59 ? "warning" : "default"}
              />
              <Metric
                label={t("stability")}
                value={`${p.stability}/100`}
                tone={p.stability > 65 ? "good" : "warning"}
              />
            </div>
            <div className="dashboard-grid">
              <Panel title={t("operationsTitle")}>
                <StateView
                  loading={operations.isLoading}
                  error={operations.error}
                  empty={!operations.data?.length}
                >
                  {operations.data?.slice(0, 3).map((item) => (
                    <Link
                      className="list-row"
                      to={`/operations/${item.id}`}
                      key={item.id}
                    >
                      <span>
                        <strong>{humanize(item.operation_type)}</strong>
                        <small>{item.target}</small>
                      </span>
                      <Status value={item.status} />
                    </Link>
                  ))}
                  <Link className="text-link" to="/operations">
                    {t("operationPlan")} →
                  </Link>
                </StateView>
              </Panel>
              <Panel title={t("newsTitle")}>
                <StateView
                  loading={events.isLoading}
                  error={events.error}
                  empty={!events.data?.length}
                >
                  {events.data?.slice(0, 3).map((item) => (
                    <div className="list-row" key={item.id}>
                      <span>
                        <strong>{item.title}</strong>
                        <small>
                          {formatDate(item.starts_at, i18n.language)}
                        </small>
                      </span>
                      <Status value={item.status} />
                    </div>
                  ))}
                </StateView>
              </Panel>
              <Panel title={t("resourcesTitle")}>
                <Progress label={t("loyalty")} value={p.loyalty} />
                <Progress label={t("legitimacy")} value={p.legitimacy} />
                <Progress label={t("stability")} value={p.stability} />
                <Progress
                  label={t("pressure")}
                  value={p.investigation_pressure}
                />
                <small>
                  {t("protectedUntil", {
                    date: formatDate(p.protected_until, i18n.language),
                  })}
                </small>
              </Panel>
            </div>
          </>
        )}
      </StateView>
    </div>
  );
}

export function CityPage() {
  const { t } = useTranslation();
  const { districtId } = useParams();
  const districts = useDistricts();
  const [layer, setLayer] = useState<
    "economic_activity" | "authority_presence" | "social_stability"
  >("economic_activity");
  const selected = districts.data?.find((item) => item.id === districtId);
  const color = (value: number) =>
    `hsl(${38 + value * 0.08} 55% ${16 + value * 0.22}%)`;
  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("cityTitle")}</h1>
        <p>{t("citySubtitle")}</p>
      </header>
      <StateView loading={districts.isLoading} error={districts.error}>
        <div className="layer-switch" role="group" aria-label={t("cityTitle")}>
          <button
            aria-pressed={layer === "economic_activity"}
            onClick={() => setLayer("economic_activity")}
          >
            {t("layerEconomic")}
          </button>
          <button
            aria-pressed={layer === "authority_presence"}
            onClick={() => setLayer("authority_presence")}
          >
            {t("layerAuthority")}
          </button>
          <button
            aria-pressed={layer === "social_stability"}
            onClick={() => setLayer("social_stability")}
          >
            {t("layerSocial")}
          </button>
        </div>
        <div className="city-layout">
          <Panel>
            <svg
              className="city-map"
              viewBox="0 0 100 100"
              role="group"
              aria-labelledby="map-title map-desc"
            >
              <title id="map-title">{t("cityTitle")}</title>
              <desc id="map-desc">{t("citySubtitle")}</desc>
              {districts.data?.map((district) => (
                <Link
                  to={`/city/${district.id}`}
                  key={district.id}
                  aria-label={`${district.name}: ${district[layer]}`}
                >
                  <polygon
                    points={district.map_points}
                    fill={color(district[layer])}
                    className={
                      selected?.id === district.id
                        ? "district-shape district-shape--selected"
                        : "district-shape"
                    }
                  />
                  <text x={district.map_x} y={district.map_y}>
                    {district.name.split(" ")[0]}
                  </text>
                </Link>
              ))}
            </svg>
          </Panel>
          {selected && (
            <Panel title={selected.name}>
              <div className="metric-grid metric-grid--compact">
                <Metric label={t("prosperity")} value={selected.prosperity} />
                <Metric label={t("employment")} value={selected.employment} />
                <Metric label={t("safety")} value={selected.safety} />
                <Metric
                  label={t("authority")}
                  value={selected.authority_presence}
                />
                <Metric
                  label={t("digital")}
                  value={selected.digital_infrastructure}
                />
                <Metric label={t("trust")} value={selected.public_trust} />
              </div>
            </Panel>
          )}
        </div>
        <details className="panel">
          <summary>{t("districtTable")}</summary>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t("homeDistrict")}</th>
                  <th>{t("prosperity")}</th>
                  <th>{t("safety")}</th>
                  <th>{t("authority")}</th>
                  <th>{t("activity")}</th>
                  <th>{t("stability")}</th>
                </tr>
              </thead>
              <tbody>
                {districts.data?.map((district) => (
                  <tr key={district.id}>
                    <th>
                      <Link to={`/city/${district.id}`}>{district.name}</Link>
                    </th>
                    <td>{district.prosperity}</td>
                    <td>{district.safety}</td>
                    <td>{district.authority_presence}</td>
                    <td>{district.economic_activity}</td>
                    <td>{district.social_stability}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </StateView>
    </div>
  );
}

export function BusinessesPage() {
  const { t, i18n } = useTranslation();
  const { companyId, businessId } = useParams();
  const selectedId = companyId ?? businessId;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const districts = useDistricts();
  const config = useQuery({
    queryKey: ["company-config"],
    queryFn: () =>
      client.get<{
        founding_cost_cents: number;
        industries: Record<string, { enterprise_value_cents: number }>;
        investments: Record<
          string,
          { cost_cents: number; metric: string; increase: number }
        >;
      }>("/companies/config"),
  });
  const query = useQuery({
    queryKey: ["companies"],
    queryFn: () => client.get<Company[]>("/companies"),
  });
  const detail = useQuery({
    queryKey: ["companies", selectedId],
    queryFn: () => client.get<CompanyDetail>(`/companies/${selectedId}`),
    enabled: Boolean(selectedId),
  });
  const economyStatus = useQuery({
    queryKey: ["economy-status"],
    queryFn: () => client.get<EconomyStatus>("/economy/status"),
  });
  const competitors = useQuery({
    queryKey: ["economy-competitors"],
    queryFn: () => client.get<Company[]>("/economy/competitors"),
  });
  const economyReports = useQuery({
    queryKey: ["companies", selectedId, "economy-reports"],
    queryFn: () =>
      client.get<CompanyEconomyReport[]>(
        `/companies/${selectedId}/economy-reports`,
      ),
    enabled: Boolean(selectedId),
  });
  const [pendingAction, setPendingAction] = useState<
    | {
        kind: "create";
        payload: { name: string; industry: string; district_id: string };
        costCents: number;
      }
    | {
        kind: "invest";
        companyId: string;
        investmentType: string;
        costCents: number;
      }
    | null
  >(null);
  const [successMessage, setSuccessMessage] = useState("");
  const create = useMutation({
    mutationFn: (body: {
      name: string;
      industry: string;
      district_id: string;
    }) => client.post<Company>("/companies", body, createIdempotencyKey()),
    onSuccess: async (company) => {
      setPendingAction(null);
      setSuccessMessage(t("companyCreated"));
      await queryClient.invalidateQueries({ queryKey: ["companies"] });
      navigate(`/companies/${company.id}`);
    },
    onError: () => setPendingAction(null),
  });
  const invest = useMutation({
    mutationFn: ({
      companyId: targetCompanyId,
      investmentType,
    }: {
      companyId: string;
      investmentType: string;
    }) =>
      client.post<Company>(
        `/companies/${targetCompanyId}/investments`,
        { investment_type: investmentType },
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setPendingAction(null);
      setSuccessMessage(t("companyInvested"));
      await queryClient.invalidateQueries({ queryKey: ["companies"] });
    },
    onError: () => setPendingAction(null),
  });
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setSuccessMessage("");
    setPendingAction({
      kind: "create",
      payload: {
        industry: String(data.get("industry")),
        district_id: String(data.get("district")),
        name: String(data.get("name")),
      },
      costCents: config.data?.founding_cost_cents ?? 0,
    });
  };
  const selected =
    detail.data ?? query.data?.find((item) => item.id === selectedId);
  const latestEconomyReport = economyReports.data?.[0];
  const confirmAction = () => {
    if (pendingAction?.kind === "create") {
      create.mutate(pendingAction.payload);
    } else if (pendingAction?.kind === "invest") {
      invest.mutate({
        companyId: pendingAction.companyId,
        investmentType: pendingAction.investmentType,
      });
    }
  };
  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("businessesTitle")}</h1>
        <Link to="/facilities" className="text-link">
          {t("facilitiesTitle")} →
        </Link>
      </header>
      <StateView
        loading={
          query.isLoading ||
          districts.isLoading ||
          config.isLoading ||
          economyStatus.isLoading ||
          competitors.isLoading ||
          (Boolean(selectedId) &&
            (detail.isLoading || economyReports.isLoading))
        }
        error={
          query.error ??
          districts.error ??
          config.error ??
          economyStatus.error ??
          competitors.error ??
          detail.error ??
          economyReports.error ??
          create.error ??
          invest.error
        }
      >
        {successMessage && (
          <p className="state-success" role="status">
            {successMessage}
          </p>
        )}
        <section
          className="economy-status"
          aria-labelledby="economy-status-title"
        >
          <div>
            <span className="eyebrow" id="economy-status-title">
              {t("economyStatus")}
            </span>
            <strong>
              {economyStatus.data?.last_tick
                ? formatDate(
                    economyStatus.data.last_tick.period_end,
                    i18n.language,
                  )
                : t("noEconomyTick")}
            </strong>
          </div>
          <div>
            <span>{t("nextEconomyTick")}</span>
            <strong>
              {economyStatus.data
                ? formatDate(
                    economyStatus.data.next_scheduled_at,
                    i18n.language,
                  )
                : "—"}
            </strong>
          </div>
        </section>
        <div className="content-grid">
          <Panel>
            {query.data?.length === 0 && (
              <div className="state">
                <p>{t("companiesEmpty")}</p>
              </div>
            )}
            <div className="card-grid">
              {query.data?.map((item) => (
                <Link
                  className={`data-card ${selected?.id === item.id ? "data-card--selected" : ""}`}
                  to={`/companies/${item.id}`}
                  key={item.id}
                >
                  <span className="eyebrow">{humanize(item.industry)}</span>
                  <h3>{item.name}</h3>
                  <div>
                    <span>
                      {formatCents(item.account_balance_cents, i18n.language)}
                    </span>
                    <Status value={item.status} />
                  </div>
                  <strong>
                    {formatCents(item.profit_cents, i18n.language)}
                  </strong>
                </Link>
              ))}
            </div>
            <h2>{t("localCompetitors")}</h2>
            {competitors.data?.length === 0 && (
              <p className="state">{t("localCompetitorsEmpty")}</p>
            )}
            <div className="card-grid">
              {competitors.data?.map((item) => (
                <article className="data-card" key={item.id}>
                  <span className="eyebrow">{humanize(item.industry)}</span>
                  <h3>{item.name}</h3>
                  <Status value={t("localSimulation")} />
                  <strong>{item.market_share_bps / 100}%</strong>
                </article>
              ))}
            </div>
          </Panel>
          {selected && (
            <Panel title={selected.name}>
              <div className="metric-grid">
                <Metric
                  label={t("companyAccount")}
                  value={formatCents(
                    selected.account_balance_cents,
                    i18n.language,
                  )}
                />
                <Metric
                  label={t("companyValue")}
                  value={formatCents(
                    selected.enterprise_value_cents,
                    i18n.language,
                  )}
                />
                <Metric
                  label={t("companyProfit")}
                  value={formatCents(selected.profit_cents, i18n.language)}
                />
              </div>
              <Progress label={t("capacity")} value={selected.capacity / 100} />
              <Progress label={t("quality")} value={selected.quality / 100} />
              <Progress
                label={t("compliance")}
                value={selected.compliance_bps / 100}
              />
              <Progress
                label={t("innovation")}
                value={selected.innovation_bps / 100}
              />
              <Progress
                label={t("marketShare")}
                value={selected.market_share_bps / 100}
              />
              <p>
                {t("ownership")}:{" "}
                {formatNumber(
                  detail.data
                    ? detail.data.ownership.reduce(
                        (total, owner) => total + owner.ownership_bps,
                        0,
                      ) / 100
                    : 100,
                  i18n.language,
                )}
                %
              </p>
              <h3>{t("companyInvestments")}</h3>
              <div className="button-row">
                {companyInvestmentTypes.map((investmentType) => {
                  const investment = config.data?.investments[investmentType];
                  return (
                    <button
                      className="button button--ghost"
                      type="button"
                      disabled={!investment || invest.isPending}
                      key={investmentType}
                      onClick={() => {
                        if (!investment) return;
                        setSuccessMessage("");
                        setPendingAction({
                          kind: "invest",
                          companyId: selected.id,
                          investmentType,
                          costCents: investment.cost_cents,
                        });
                      }}
                    >
                      {humanize(investmentType)} ·{" "}
                      {investment
                        ? formatCents(investment.cost_cents, i18n.language)
                        : "—"}
                    </button>
                  );
                })}
              </div>
              <h3>{t("economyReports")}</h3>
              {economyReports.data?.length === 0 && (
                <p className="state">{t("economyReportsEmpty")}</p>
              )}
              {economyReports.data && economyReports.data.length > 0 && (
                <>
                  <EconomyReportChart
                    reports={economyReports.data}
                    title={t("economyChart")}
                    locale={i18n.language}
                  />
                  <div
                    className="table-wrap"
                    tabIndex={0}
                    aria-label={t("economyReports")}
                  >
                    <table>
                      <thead>
                        <tr>
                          <th>{t("tickPeriod")}</th>
                          <th>{t("revenue")}</th>
                          <th>{t("cost")}</th>
                          <th>{t("companyProfit")}</th>
                          <th>{t("marketShare")}</th>
                          <th>{t("allocatedDemand")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {economyReports.data.map((report) => (
                          <tr key={report.id}>
                            <td>
                              {formatDate(report.created_at, i18n.language)}
                            </td>
                            <td>
                              {formatCents(report.revenue_cents, i18n.language)}
                            </td>
                            <td>
                              {formatCents(report.cost_cents, i18n.language)}
                            </td>
                            <td>
                              {formatCents(report.profit_cents, i18n.language)}
                            </td>
                            <td>{report.market_share_bps / 100}%</td>
                            <td>
                              {formatNumber(
                                report.allocated_units,
                                i18n.language,
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {latestEconomyReport && (
                    <details>
                      <summary>{t("economyCalculationDetails")}</summary>
                      <dl className="detail-list">
                        <div>
                          <dt>{t("attractiveness")}</dt>
                          <dd>
                            {formatNumber(
                              latestEconomyReport.attractiveness_points,
                              i18n.language,
                            )}
                          </dd>
                        </div>
                        <div>
                          <dt>{t("debtIncrease")}</dt>
                          <dd>
                            {formatCents(
                              latestEconomyReport.debt_delta_cents,
                              i18n.language,
                            )}
                          </dd>
                        </div>
                      </dl>
                    </details>
                  )}
                </>
              )}
              {detail.data && detail.data.metrics_history.length > 0 && (
                <details>
                  <summary>{t("companyHistory")}</summary>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>{t("version")}</th>
                          <th>{t("status")}</th>
                          <th>{t("companyAccount")}</th>
                          <th>{t("capacity")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.data.metrics_history.map((metric) => (
                          <tr key={metric.id}>
                            <td>{metric.version}</td>
                            <td>{humanize(metric.reason)}</td>
                            <td>
                              {formatCents(
                                metric.account_balance_cents,
                                i18n.language,
                              )}
                            </td>
                            <td>{metric.capacity / 100}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              )}
            </Panel>
          )}
          <Panel title={t("companyFound")}>
            <form onSubmit={submit}>
              <Field label={t("businessType")}>
                <select id="field-business-type" name="industry">
                  {(config.data
                    ? Object.keys(config.data.industries)
                    : [...companyIndustries]
                  ).map((item) => (
                    <option key={item} value={item}>
                      {humanize(item)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={t("homeDistrict")}>
                <select id="field-starting-district" name="district">
                  {districts.data?.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={t("businessName")}>
                <input
                  id="field-business-name"
                  name="name"
                  minLength={2}
                  required
                />
              </Field>
              <p>
                {t("companyFoundingCost")}:{" "}
                {config.data
                  ? formatCents(config.data.founding_cost_cents, i18n.language)
                  : "—"}
              </p>
              <button
                className="button"
                disabled={!config.data || create.isPending}
              >
                {t("companyFound")}
              </button>
            </form>
          </Panel>
        </div>
      </StateView>
      {pendingAction && (
        <ConfirmDialog
          title={t(
            pendingAction.kind === "create"
              ? "confirmCompanyFounding"
              : "confirmCompanyInvestment",
          )}
          description={t("confirmCompanyCost", {
            cost: formatCents(pendingAction.costCents, i18n.language),
          })}
          confirmLabel={t(
            pendingAction.kind === "create" ? "companyFound" : "invest",
          )}
          cancelLabel={t("cancel")}
          pending={create.isPending || invest.isPending}
          onCancel={() => setPendingAction(null)}
          onConfirm={confirmAction}
        />
      )}
    </div>
  );
}

export function FacilitiesPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["facilities"],
    queryFn: () =>
      client.get<
        Array<{
          id: string;
          facility_type: string;
          level: number;
          status: string;
          finishes_at: string | null;
        }>
      >("/facilities"),
  });
  const build = useMutation({
    mutationFn: (facility_type: string) =>
      client.post("/facilities", { facility_type }, createIdempotencyKey()),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["facilities"] }),
  });
  const options = [
    "finance_office",
    "intelligence_center",
    "logistics_center",
    "personnel_academy",
    "compliance_office",
  ];
  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("facilitiesTitle")}</h1>
      </header>
      <StateView loading={query.isLoading} error={query.error ?? build.error}>
        <div className="card-grid">
          {query.data?.map((item) => (
            <Panel key={item.id}>
              <h2>{humanize(item.facility_type)}</h2>
              <p>
                {t("level")} {item.level}
              </p>
              <Status value={item.status} />
            </Panel>
          ))}
        </div>
        <Panel title={t("buildOrUpgrade")}>
          <div className="button-row">
            {options.map((item) => (
              <button
                className="button button--ghost"
                key={item}
                onClick={() => build.mutate(item)}
              >
                {humanize(item)}
              </button>
            ))}
          </div>
        </Panel>
      </StateView>
    </div>
  );
}

export function SpecialistsPage() {
  const { t, i18n } = useTranslation();
  const { specialistId } = useParams();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["specialists"],
    queryFn: () => client.get<Specialist[]>("/specialists"),
  });
  const market = useQuery({
    queryKey: ["specialist-market"],
    queryFn: () =>
      client.get<SpecialistMarketCandidate[]>("/specialist-market"),
  });
  const companies = useQuery({
    queryKey: ["companies"],
    queryFn: () => client.get<Company[]>("/companies"),
  });
  const [companyId, setCompanyId] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [pendingAction, setPendingAction] = useState<
    | { kind: "hire"; candidate: SpecialistMarketCandidate }
    | { kind: "release"; specialist: Specialist }
    | null
  >(null);
  useEffect(() => {
    if (!companyId && companies.data?.[0]) {
      setCompanyId(companies.data[0].id);
    }
  }, [companies.data, companyId]);
  const selected = query.data?.find((item) => item.id === specialistId);
  const effects = useQuery({
    queryKey: [
      "companies",
      selected?.employer_company_id,
      "specialist-effects",
    ],
    queryFn: () =>
      client.get<SpecialistEffects>(
        `/companies/${selected?.employer_company_id}/specialist-effects`,
      ),
    enabled: Boolean(selected?.employer_company_id),
  });
  const payroll = useQuery({
    queryKey: ["specialists", specialistId, "payroll"],
    queryFn: () =>
      client.get<SpecialistPayrollReport[]>(
        `/specialists/${specialistId}/payroll-reports`,
      ),
    enabled: Boolean(specialistId),
  });
  const hire = useMutation({
    mutationFn: ({
      candidateId,
      targetCompanyId,
    }: {
      candidateId: string;
      targetCompanyId: string;
    }) =>
      client.post<Specialist>(
        `/specialist-market/${candidateId}/hire`,
        { company_id: targetCompanyId },
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setPendingAction(null);
      setSuccessMessage(t("specialistHired"));
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["specialists"] }),
        queryClient.invalidateQueries({ queryKey: ["specialist-market"] }),
      ]);
    },
    onError: () => setPendingAction(null),
  });
  const assign = useMutation({
    mutationFn: ({
      targetSpecialistId,
      targetCompanyId,
    }: {
      targetSpecialistId: string;
      targetCompanyId: string;
    }) =>
      client.post<Specialist>(
        `/specialists/${targetSpecialistId}/assign`,
        { company_id: targetCompanyId },
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setSuccessMessage(t("specialistAssigned"));
      await queryClient.invalidateQueries({ queryKey: ["specialists"] });
    },
  });
  const release = useMutation({
    mutationFn: (targetSpecialistId: string) =>
      client.post<Specialist>(
        `/specialists/${targetSpecialistId}/release`,
        undefined,
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setPendingAction(null);
      setSuccessMessage(t("specialistReleased"));
      await queryClient.invalidateQueries({ queryKey: ["specialists"] });
    },
    onError: () => setPendingAction(null),
  });
  const confirmAction = () => {
    if (pendingAction?.kind === "hire" && companyId) {
      hire.mutate({
        candidateId: pendingAction.candidate.id,
        targetCompanyId: companyId,
      });
    } else if (pendingAction?.kind === "release") {
      release.mutate(pendingAction.specialist.id);
    }
  };
  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("specialistsTitle")}</h1>
      </header>
      <StateView
        loading={
          query.isLoading ||
          market.isLoading ||
          companies.isLoading ||
          (Boolean(specialistId) &&
            (payroll.isLoading ||
              (Boolean(selected?.employer_company_id) && effects.isLoading)))
        }
        error={
          query.error ??
          market.error ??
          companies.error ??
          effects.error ??
          payroll.error ??
          hire.error ??
          assign.error ??
          release.error
        }
      >
        {successMessage && (
          <p className="state-success" role="status">
            {successMessage}
          </p>
        )}
        <div className="content-grid">
          <Panel>
            <h2>{t("hiredSpecialists")}</h2>
            {query.data?.length === 0 && (
              <p className="state">{t("hiredSpecialistsEmpty")}</p>
            )}
            <div className="card-grid">
              {query.data?.map((item) => (
                <Link
                  className="data-card"
                  to={`/specialists/${item.id}`}
                  key={item.id}
                >
                  <span className="eyebrow">{humanize(item.role)}</span>
                  <h3>{item.name}</h3>
                  <Status value={item.status} />
                  <strong>
                    {t("level")} {item.level}
                  </strong>
                </Link>
              ))}
            </div>
          </Panel>
          {selected && (
            <Panel title={selected.name}>
              <Progress label={t("competence")} value={selected.competence} />
              <Progress label={t("loyalty")} value={selected.loyalty} />
              <Progress label={t("energy")} value={selected.energy} />
              <Progress label={t("ambition")} value={selected.ambition} />
              <Progress label={t("stress")} value={selected.stress} />
              <Progress label={t("exposure")} value={selected.exposure} />
              <p>
                {t("salary")}:{" "}
                {formatCents(selected.salary_cents, i18n.language)}
              </p>
              <h3>{t("skills")}</h3>
              <dl className="detail-list">
                {Object.entries(selected.skills_json).map(([skill, value]) => (
                  <div key={skill}>
                    <dt>{humanize(skill)}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
              <Field label={t("employer")}>
                <select
                  id="field-specialist-company"
                  value={companyId}
                  onChange={(event) => setCompanyId(event.target.value)}
                >
                  {companies.data?.map((company) => (
                    <option key={company.id} value={company.id}>
                      {company.name}
                    </option>
                  ))}
                </select>
              </Field>
              <div className="button-row">
                <button
                  className="button button--ghost"
                  type="button"
                  disabled={!companyId || assign.isPending}
                  onClick={() =>
                    assign.mutate({
                      targetSpecialistId: selected.id,
                      targetCompanyId: companyId,
                    })
                  }
                >
                  {t("assign")}
                </button>
                <button
                  className="button button--danger"
                  type="button"
                  disabled={release.isPending}
                  onClick={() =>
                    setPendingAction({ kind: "release", specialist: selected })
                  }
                >
                  {t("release")}
                </button>
              </div>
              {effects.data && (
                <>
                  <h3>{t("companyEffects")}</h3>
                  <dl className="detail-list">
                    <div>
                      <dt>{t("capacity")}</dt>
                      <dd>+{effects.data.capacity_bonus_units}</dd>
                    </div>
                    <div>
                      <dt>{t("revenue")}</dt>
                      <dd>+{effects.data.revenue_bonus_bps / 100}%</dd>
                    </div>
                    <div>
                      <dt>{t("cost")}</dt>
                      <dd>−{effects.data.cost_reduction_bps / 100}%</dd>
                    </div>
                    <div>
                      <dt>{t("attractiveness")}</dt>
                      <dd>+{effects.data.attractiveness_bonus_points}</dd>
                    </div>
                  </dl>
                </>
              )}
              <h3>{t("payrollHistory")}</h3>
              {payroll.data?.length === 0 && (
                <p className="state">{t("payrollHistoryEmpty")}</p>
              )}
              {payroll.data && payroll.data.length > 0 && (
                <div
                  className="table-wrap"
                  tabIndex={0}
                  aria-label={t("payrollHistory")}
                >
                  <table>
                    <thead>
                      <tr>
                        <th>{t("tickPeriod")}</th>
                        <th>{t("salary")}</th>
                        <th>{t("paid")}</th>
                        <th>{t("loyalty")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {payroll.data.map((report) => (
                        <tr key={report.id}>
                          <td>
                            {formatDate(report.created_at, i18n.language)}
                          </td>
                          <td>
                            {formatCents(
                              report.salary_due_cents,
                              i18n.language,
                            )}
                          </td>
                          <td>
                            {formatCents(
                              report.salary_paid_cents,
                              i18n.language,
                            )}
                          </td>
                          <td>
                            {report.loyalty_before} → {report.loyalty_after}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Panel>
          )}
          <Panel title={t("specialistMarket")}>
            {companies.data?.length === 0 && (
              <p className="state">{t("specialistCompanyRequired")}</p>
            )}
            {market.data?.length === 0 && (
              <p className="state">{t("specialistMarketEmpty")}</p>
            )}
            <Field label={t("employer")}>
              <select
                id="field-market-company"
                value={companyId}
                onChange={(event) => setCompanyId(event.target.value)}
              >
                {companies.data?.map((company) => (
                  <option key={company.id} value={company.id}>
                    {company.name}
                  </option>
                ))}
              </select>
            </Field>
            <div className="card-grid">
              {market.data?.map((candidate) => (
                <article className="data-card" key={candidate.id}>
                  <span className="eyebrow">{humanize(candidate.role)}</span>
                  <h3>{candidate.name}</h3>
                  <p>
                    {t("level")} {candidate.level} · {t("loyalty")}{" "}
                    {candidate.loyalty} · {t("energy")} {candidate.energy}
                  </p>
                  <strong>
                    {formatCents(candidate.salary_cents, i18n.language)}
                  </strong>
                  <button
                    className="button button--ghost"
                    type="button"
                    disabled={!companyId || hire.isPending}
                    onClick={() =>
                      setPendingAction({ kind: "hire", candidate })
                    }
                  >
                    {t("hire")}
                  </button>
                </article>
              ))}
            </div>
          </Panel>
        </div>
      </StateView>
      {pendingAction && (
        <ConfirmDialog
          title={t(
            pendingAction.kind === "hire"
              ? "confirmSpecialistHire"
              : "confirmSpecialistRelease",
          )}
          description={
            pendingAction.kind === "hire"
              ? t("confirmSpecialistSalary", {
                  salary: formatCents(
                    pendingAction.candidate.salary_cents,
                    i18n.language,
                  ),
                })
              : t("confirmSpecialistReleaseDescription")
          }
          confirmLabel={t(pendingAction.kind === "hire" ? "hire" : "release")}
          cancelLabel={t("cancel")}
          pending={hire.isPending || release.isPending}
          onCancel={() => setPendingAction(null)}
          onConfirm={confirmAction}
        />
      )}
    </div>
  );
}

export function OperationsPage() {
  const { t, i18n } = useTranslation();
  const { operationId } = useParams();
  const queryClient = useQueryClient();
  const districts = useDistricts();
  const specialists = useQuery({
    queryKey: ["specialists"],
    queryFn: () => client.get<Specialist[]>("/specialists"),
  });
  const query = useQuery({
    queryKey: ["operations"],
    queryFn: () => client.get<Operation[]>("/operations"),
    refetchInterval: 15_000,
  });
  const start = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      client.post<Operation>("/operations", body, createIdempotencyKey()),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["operations"] }),
  });
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    start.mutate({
      operation_type: data.get("type"),
      district_id: data.get("district"),
      specialist_id: data.get("specialist"),
      target: data.get("target"),
      budget: Number(data.get("budget")),
      intelligence_spend: Number(data.get("intel")),
      risk_posture: data.get("posture"),
      secrecy: Number(data.get("secrecy")),
    });
  };
  const selected = query.data?.find((item) => item.id === operationId);
  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("operationsTitle")}</h1>
        <p>{t("noExactChance")}</p>
      </header>
      <StateView
        loading={
          query.isLoading || districts.isLoading || specialists.isLoading
        }
        error={
          query.error ?? districts.error ?? specialists.error ?? start.error
        }
      >
        <div className="content-grid">
          <Panel>
            <div className="list-stack">
              {query.data?.map((item) => (
                <Link
                  className="list-row"
                  to={`/operations/${item.id}`}
                  key={item.id}
                >
                  <span>
                    <strong>{humanize(item.operation_type)}</strong>
                    <small>{item.target}</small>
                  </span>
                  <Status value={item.result ?? item.status} />
                </Link>
              ))}
            </div>
          </Panel>
          {selected && (
            <Panel title={selected.target}>
              <p>{humanize(selected.operation_type)}</p>
              <p>
                {t("budget")}: {formatCurrency(selected.budget, i18n.language)}
              </p>
              <p>
                {t("finishes", {
                  date: formatDate(selected.finishes_at, i18n.language),
                })}
              </p>
              <Status value={selected.result ?? selected.status} />
              {selected.outcome_json && (
                <pre className="outcome">
                  {JSON.stringify(selected.outcome_json, null, 2)}
                </pre>
              )}
            </Panel>
          )}
          <Panel title={t("operationPlan")}>
            <form onSubmit={submit}>
              <Field label={t("operationType")}>
                <select id="field-operation-category" name="type">
                  {operationTypes.map((item) => (
                    <option key={item} value={item}>
                      {humanize(item)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={t("homeDistrict")}>
                <select id="field-starting-district" name="district">
                  {districts.data?.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={t("lead")}>
                <select id="field-responsible-specialist" name="specialist">
                  {specialists.data
                    ?.filter((item) => item.status === "available")
                    .map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                </select>
              </Field>
              <Field label={t("target")}>
                <input
                  id="field-fictional-objective"
                  name="target"
                  minLength={2}
                  required
                />
              </Field>
              <div className="form-row">
                <Field label={t("budget")}>
                  <input
                    id="field-budget"
                    name="budget"
                    type="number"
                    min="1000"
                    max="1000000"
                    defaultValue="5000"
                  />
                </Field>
                <Field label={t("intelSpend")}>
                  <input
                    id="field-information-effort"
                    name="intel"
                    type="number"
                    min="0"
                    max="100"
                    defaultValue="1"
                  />
                </Field>
              </div>
              <Field label={t("posture")}>
                <select id="field-risk-posture" name="posture">
                  <option value="cautious">{t("cautious")}</option>
                  <option value="balanced">{t("balanced")}</option>
                  <option value="aggressive">{t("aggressive")}</option>
                </select>
              </Field>
              <Field label={t("secrecy")}>
                <input
                  id="field-secrecy"
                  name="secrecy"
                  type="range"
                  min="0"
                  max="100"
                  defaultValue="60"
                />
              </Field>
              <button className="button">{t("start")}</button>
            </form>
          </Panel>
        </div>
      </StateView>
    </div>
  );
}

interface Network {
  nodes: Array<{ id: string; kind: string; label: string; uncertain: boolean }>;
  edges: Array<{
    source: string;
    target: string;
    kind: string;
    uncertain: boolean;
  }>;
}
export function NetworkPage() {
  const { t } = useTranslation();
  const container = useRef<HTMLDivElement>(null);
  const query = useQuery({
    queryKey: ["network"],
    queryFn: () => client.get<Network>("/network"),
  });
  useEffect(() => {
    if (!container.current || !query.data) return;
    const graph = cytoscape({
      container: container.current,
      elements: [
        ...query.data.nodes.map((node) => ({ data: node })),
        ...query.data.edges.map((edge, index) => ({
          data: { id: `edge-${index}`, ...edge },
        })),
      ],
      style: [
        {
          selector: "node",
          style: {
            "background-color": "#d8b15b",
            color: "#f3f0e7",
            label: "data(label)",
            "font-size": 9,
            "text-valign": "bottom",
            "text-margin-y": 7,
          },
        },
        {
          selector: "edge",
          style: {
            width: 2,
            "line-color": "#596575",
            "target-arrow-color": "#596575",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
          },
        },
        {
          selector: "edge[uncertain]",
          style: { "line-style": "dashed", "line-color": "#ffbe5c" },
        },
      ],
      layout: { name: "cose", animate: false },
    });
    return () => graph.destroy();
  }, [query.data]);
  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("networkTitle")}</h1>
      </header>
      <StateView
        loading={query.isLoading}
        error={query.error}
        empty={!query.data?.nodes.length}
      >
        <Panel>
          <div
            ref={container}
            className="network-graph"
            role="img"
            aria-label={t("networkTitle")}
          />
        </Panel>
        <details className="panel">
          <summary>{t("networkAlternative")}</summary>
          <ul className="relation-list">
            {query.data?.edges.map((edge, index) => {
              const source = query.data?.nodes.find(
                (node) => node.id === edge.source,
              );
              const target = query.data?.nodes.find(
                (node) => node.id === edge.target,
              );
              return (
                <li key={index}>
                  <strong>{source?.label}</strong> → {humanize(edge.kind)} →{" "}
                  <strong>{target?.label}</strong>
                  {edge.uncertain && (
                    <Status value={t("uncertain")} uncertain />
                  )}
                </li>
              );
            })}
          </ul>
        </details>
      </StateView>
    </div>
  );
}

export function IntelPage() {
  const { t, i18n } = useTranslation();
  const query = useQuery({
    queryKey: ["intel"],
    queryFn: () => client.get<IntelReport[]>("/intelligence"),
  });
  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("intelTitle")}</h1>
      </header>
      <StateView
        loading={query.isLoading}
        error={query.error}
        empty={!query.data?.length}
      >
        <div className="card-grid">
          {query.data?.map((item) => (
            <Panel key={item.id}>
              <Status
                value={item.status}
                uncertain={item.visible_confidence < 75}
              />
              <h2>{item.title}</h2>
              <p>{item.summary}</p>
              <Progress
                label={t("confidence", { value: item.visible_confidence })}
                value={item.visible_confidence}
              />
              <small>
                {item.source} ·{" "}
                {t("expires", {
                  date: formatDate(item.expires_at, i18n.language),
                })}
              </small>
            </Panel>
          ))}
        </div>
      </StateView>
    </div>
  );
}

export function InvestigationPage() {
  const { t, i18n } = useTranslation();
  const query = useQuery({
    queryKey: ["investigation"],
    queryFn: () =>
      client.get<{
        estimated: boolean;
        pressure: number;
        stage: string;
        notice: string;
        known_signals: Array<{
          id: string;
          type: string;
          estimated_strength: number;
          created_at: string;
        }>;
      }>("/investigations"),
  });
  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("investigationTitle")}</h1>
        <p className="notice notice--warning">{t("investigationEstimate")}</p>
      </header>
      <StateView loading={query.isLoading} error={query.error}>
        {query.data && (
          <>
            <div className="investigation-meter">
              <span style={{ width: `${query.data.pressure}%` }} />
              <strong>{query.data.pressure}/100</strong>
            </div>
            <Panel>
              <h2>{humanize(query.data.stage)}</h2>
              <p>{query.data.notice}</p>
              <h3>{t("knownSignals")}</h3>
              <div className="list-stack">
                {query.data.known_signals.map((item) => (
                  <div className="list-row" key={item.id}>
                    <span>
                      <strong>{humanize(item.type)}</strong>
                      <small>
                        {formatDate(item.created_at, i18n.language)}
                      </small>
                    </span>
                    <Status
                      value={`${item.estimated_strength}/100`}
                      uncertain
                    />
                  </div>
                ))}
              </div>
            </Panel>
          </>
        )}
      </StateView>
    </div>
  );
}
