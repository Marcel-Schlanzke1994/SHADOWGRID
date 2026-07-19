import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import cytoscape from "cytoscape";
import { ApiError, createIdempotencyKey } from "@shadowgrid/api-client";
import {
  businessTypes,
  operationTypes,
  organizationArchetypes,
  specialistRoles,
} from "@shadowgrid/game-config";
import type {
  Business,
  District,
  IntelReport,
  Operation,
  Profile,
  Specialist,
  World,
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

export function WorldPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const worlds = useQuery({
    queryKey: ["worlds"],
    queryFn: () => client.get<World[]>("/worlds"),
  });
  const [worldId, setWorldId] = useState("");
  useEffect(() => {
    if (!worldId && worlds.data?.[0]) setWorldId(worlds.data[0].id);
  }, [worldId, worlds.data]);
  const districts = useQuery({
    queryKey: ["world-districts", worldId],
    queryFn: () => client.get<District[]>(`/worlds/${worldId}/districts`),
    enabled: Boolean(worldId),
  });
  const join = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      client.post<Profile>(
        `/worlds/${worldId}/join`,
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
      codename: data.get("codename"),
      archetype: data.get("archetype"),
      home_district_id: data.get("district"),
    });
  };
  return (
    <main className="centered-page">
      <div className="public-brand">
        <span className="brand__mark" aria-hidden="true">
          SG
        </span>
        <strong>{t("appName")}</strong>
      </div>
      <Panel className="wide-card">
        <h1>{t("worldsTitle")}</h1>
        <StateView
          loading={worlds.isLoading || districts.isLoading || join.isPending}
          error={worlds.error ?? districts.error ?? join.error}
          empty={worlds.data?.length === 0}
        >
          <form onSubmit={submit}>
            <Field label={t("worldsTitle")}>
              <select
                id="field-choose-a-world"
                value={worldId}
                onChange={(event) => setWorldId(event.target.value)}
              >
                {worlds.data?.map((world) => (
                  <option value={world.id} key={world.id}>
                    {world.name}
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
    queryFn: () =>
      client.get<
        Array<{ id: string; title: string; status: string; starts_at: string }>
      >("/world-events"),
    enabled: Boolean(profile.data),
  });
  if (
    profile.error instanceof ApiError &&
    profile.error.code === "world.not_joined"
  )
    return <Navigate to="/worlds" replace />;
  const p = profile.data;
  return (
    <div className="page">
      <header className="page-header">
        <p className="eyebrow">{t("liveStateEyebrow")}</p>
        <h1>{t("commandTitle")}</h1>
        <p>{t("commandSubtitle")}</p>
      </header>
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
              role="img"
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
  const { businessId } = useParams();
  const queryClient = useQueryClient();
  const districts = useDistricts();
  const query = useQuery({
    queryKey: ["businesses"],
    queryFn: () => client.get<Business[]>("/businesses"),
  });
  const buy = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      client.post<Business>("/businesses", body, createIdempotencyKey()),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["businesses"] }),
  });
  const upgrade = useMutation({
    mutationFn: (id: string) =>
      client.post<Business>(
        `/businesses/${id}/upgrade`,
        undefined,
        createIdempotencyKey(),
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["businesses"] }),
  });
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    buy.mutate({
      business_type: data.get("type"),
      district_id: data.get("district"),
      name: data.get("name"),
    });
  };
  const selected = query.data?.find((item) => item.id === businessId);
  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("businessesTitle")}</h1>
        <Link to="/facilities" className="text-link">
          {t("facilitiesTitle")} →
        </Link>
      </header>
      <StateView
        loading={query.isLoading || districts.isLoading}
        error={query.error ?? districts.error ?? buy.error ?? upgrade.error}
      >
        <div className="content-grid">
          <Panel>
            <div className="card-grid">
              {query.data?.map((item) => (
                <Link
                  className={`data-card ${selected?.id === item.id ? "data-card--selected" : ""}`}
                  to={`/businesses/${item.id}`}
                  key={item.id}
                >
                  <span className="eyebrow">
                    {humanize(item.business_type)}
                  </span>
                  <h3>{item.name}</h3>
                  <div>
                    <span>
                      {t("level")} {item.level}
                    </span>
                    <Status value={item.status} />
                  </div>
                  <strong>
                    {formatCurrency(
                      item.revenue - item.operating_cost,
                      i18n.language,
                    )}
                  </strong>
                </Link>
              ))}
            </div>
          </Panel>
          {selected && (
            <Panel title={selected.name}>
              <Progress label={t("compliance")} value={selected.compliance} />
              <Progress label={t("reputation")} value={selected.reputation} />
              <Progress
                label={t("marketShare")}
                value={selected.market_share}
              />
              <Progress label={t("risk")} value={selected.risk} />
              <button
                className="button"
                disabled={upgrade.isPending}
                onClick={() => upgrade.mutate(selected.id)}
              >
                {t("upgrade")}
              </button>
            </Panel>
          )}
          <Panel title={t("businessBuy")}>
            <form onSubmit={submit}>
              <Field label={t("businessType")}>
                <select id="field-business-type" name="type">
                  {businessTypes.map((item) => (
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
              <button className="button">{t("buy")}</button>
            </form>
          </Panel>
        </div>
      </StateView>
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
  const recruit = useMutation({
    mutationFn: (role: string) =>
      client.post<Specialist>("/specialists", { role }, createIdempotencyKey()),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["specialists"] }),
  });
  const selected = query.data?.find((item) => item.id === specialistId);
  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("specialistsTitle")}</h1>
      </header>
      <StateView loading={query.isLoading} error={query.error ?? recruit.error}>
        <div className="content-grid">
          <Panel>
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
                </Link>
              ))}
            </div>
          </Panel>
          {selected && (
            <Panel title={selected.name}>
              <Progress label={t("competence")} value={selected.competence} />
              <Progress label={t("loyalty")} value={selected.loyalty} />
              <Progress label={t("ambition")} value={selected.ambition} />
              <Progress label={t("stress")} value={selected.stress} />
              <Progress label={t("exposure")} value={selected.exposure} />
              <p>
                {t("salary")}: {formatCurrency(selected.salary, i18n.language)}
              </p>
            </Panel>
          )}
          <Panel title={t("specialistRecruit")}>
            <div className="button-row">
              {specialistRoles.map((role) => (
                <button
                  className="button button--ghost"
                  key={role}
                  disabled={recruit.isPending}
                  onClick={() => recruit.mutate(role)}
                >
                  {humanize(role)}
                </button>
              ))}
            </div>
          </Panel>
        </div>
      </StateView>
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
