import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { createIdempotencyKey } from "@shadowgrid/api-client";
import {
  configuredLocales,
  organizationArchetypes,
  type Locale,
} from "@shadowgrid/game-config";
import { setLocale } from "@shadowgrid/i18n";
import type { Organization } from "@shadowgrid/shared-types";
import { client, logout, useAuth } from "../auth";
import {
  Field,
  Metric,
  Panel,
  Progress,
  StateView,
  Status,
} from "../components";
import { formatCurrency, formatDate } from "../format";

const humanize = (value: string) =>
  value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const assignableOrganizationRoles = [
  "candidate",
  "member",
  "district_lead",
  "intelligence_lead",
  "diplomacy_lead",
  "finance_lead",
  "deputy",
] as const;

interface OrganizationMember {
  membership_id: string;
  profile_id: string;
  codename: string;
  role: string;
  status: string;
  joined_at: string;
}

export function OrganizationsPage() {
  const { t, i18n } = useTranslation();
  const { organizationId } = useParams();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["organizations"],
    queryFn: () => client.get<Organization[]>("/organizations"),
  });
  const create = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      client.post<Organization>("/organizations", body, createIdempotencyKey()),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["organizations"] }),
  });
  const invite = useMutation({
    mutationFn: ({ id, email }: { id: string; email: string }) =>
      client.post(`/organizations/${id}/invites`, { email }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["organizations"] }),
  });
  const deposit = useMutation({
    mutationFn: ({ id, amount }: { id: string; amount: number }) =>
      client.post(
        `/organizations/${id}/treasury/deposit`,
        { resource_type: "cash", amount },
        createIdempotencyKey(),
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["organizations"] }),
  });
  const selected =
    query.data?.find((item) => item.id === organizationId) ??
    query.data?.find((item) => item.my_role);
  const members = useQuery({
    queryKey: ["organization-members", selected?.id],
    queryFn: () =>
      client.get<OrganizationMember[]>(
        `/organizations/${selected?.id}/members`,
      ),
    enabled: Boolean(selected?.my_role),
  });
  const updateRole = useMutation({
    mutationFn: ({
      membershipId,
      role,
    }: {
      membershipId: string;
      role: string;
    }) =>
      client.patch<OrganizationMember>(
        `/organizations/${selected?.id}/members/${membershipId}`,
        { role },
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["organization-members", selected?.id],
      }),
  });
  const removeMember = useMutation({
    mutationFn: (membershipId: string) =>
      client.delete(`/organizations/${selected?.id}/members/${membershipId}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["organization-members", selected?.id],
      });
      void queryClient.invalidateQueries({ queryKey: ["organizations"] });
    },
  });
  const createSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    create.mutate({
      name: data.get("name"),
      tag: data.get("tag"),
      archetype: data.get("archetype"),
      description: data.get("description"),
    });
  };
  const inviteSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selected) return;
    invite.mutate({
      id: selected.id,
      email: String(new FormData(event.currentTarget).get("email")),
    });
  };
  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("organizationTitle")}</h1>
        <p>{t("discoverOrganizations")}</p>
      </header>
      <StateView
        loading={query.isLoading}
        error={
          query.error ??
          members.error ??
          create.error ??
          invite.error ??
          deposit.error ??
          updateRole.error ??
          removeMember.error
        }
      >
        <div className="content-grid">
          <Panel>
            <div className="card-grid">
              {query.data?.map((item) => (
                <Link
                  className="data-card"
                  to={`/organizations/${item.id}`}
                  key={item.id}
                >
                  <span className="eyebrow">
                    {item.tag} // {humanize(item.archetype)}
                  </span>
                  <h3>{item.name}</h3>
                  <p>{item.description}</p>
                  <div>
                    <Status value={item.my_role ?? "public"} />
                    <span>{t("members", { count: item.member_count })}</span>
                  </div>
                </Link>
              ))}
            </div>
          </Panel>
          {selected && (
            <Panel title={selected.name}>
              <Progress label={t("stability")} value={selected.stability} />
              <div className="metric-grid metric-grid--compact">
                <Metric
                  label={t("cash")}
                  value={formatCurrency(selected.treasury_cash, i18n.language)}
                />
                <Metric
                  label={t("capital")}
                  value={formatCurrency(
                    selected.treasury_capital,
                    i18n.language,
                  )}
                />
              </div>
              {selected.my_role && (
                <>
                  <form onSubmit={inviteSubmit}>
                    <Field label={t("inviteEmail")}>
                      <input
                        id="field-invite-by-email"
                        name="email"
                        type="email"
                        required
                      />
                    </Field>
                    <button className="button">{t("invite")}</button>
                  </form>
                  <button
                    className="button button--ghost"
                    onClick={() =>
                      deposit.mutate({ id: selected.id, amount: 1000 })
                    }
                  >
                    {t("treasury")} +1,000
                  </button>
                </>
              )}
            </Panel>
          )}
          {selected?.my_role && (
            <Panel title={t("organizationMembers")}>
              <StateView
                loading={members.isLoading}
                empty={!members.data?.length}
              >
                <div className="list-stack">
                  {members.data?.map((member) => (
                    <div className="list-row" key={member.membership_id}>
                      <span>
                        <strong>{member.codename}</strong>
                        <small>{humanize(member.role)}</small>
                      </span>
                      {selected.my_role === "director" &&
                        member.role !== "director" && (
                          <div className="button-row">
                            <label
                              className="sr-only"
                              htmlFor={`role-${member.membership_id}`}
                            >
                              {t("changeRole")}
                            </label>
                            <select
                              id={`role-${member.membership_id}`}
                              value={member.role}
                              onChange={(event) =>
                                updateRole.mutate({
                                  membershipId: member.membership_id,
                                  role: event.target.value,
                                })
                              }
                            >
                              {assignableOrganizationRoles.map((role) => (
                                <option key={role} value={role}>
                                  {humanize(role)}
                                </option>
                              ))}
                            </select>
                            <button
                              className="button button--small button--danger"
                              onClick={() =>
                                removeMember.mutate(member.membership_id)
                              }
                            >
                              {t("removeMember")}
                            </button>
                          </div>
                        )}
                    </div>
                  ))}
                </div>
              </StateView>
            </Panel>
          )}
          <Panel title={t("createOrganization")}>
            <form onSubmit={createSubmit}>
              <Field label={t("organizationName")}>
                <input
                  id="field-organization-name"
                  name="name"
                  minLength={3}
                  required
                />
              </Field>
              <Field label={t("organizationTag")}>
                <input
                  id="field-short-tag"
                  name="tag"
                  minLength={2}
                  maxLength={8}
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
              <Field label={t("description")}>
                <textarea
                  id="field-description"
                  name="description"
                  maxLength={500}
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

interface Treaty {
  id: string;
  proposer_org_id: string;
  recipient_org_id: string;
  treaty_type: string;
  visibility: string;
  status: string;
  starts_at: string | null;
  expires_at: string;
}
export function DiplomacyPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const organizations = useQuery({
    queryKey: ["organizations"],
    queryFn: () => client.get<Organization[]>("/organizations"),
  });
  const treaties = useQuery({
    queryKey: ["treaties"],
    queryFn: () => client.get<Treaty[]>("/treaties"),
  });
  const create = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      client.post<Treaty>("/treaties", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["treaties"] }),
  });
  const accept = useMutation({
    mutationFn: (id: string) => client.post<Treaty>(`/treaties/${id}/accept`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["treaties"] }),
  });
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    create.mutate({
      recipient_org_id: data.get("recipient"),
      treaty_type: data.get("type"),
      duration_days: Number(data.get("duration")),
      visibility: data.get("visibility"),
      terms: { scope: "Vesper Metropolitan Zone" },
    });
  };
  const orgName = (id: string) =>
    organizations.data?.find((item) => item.id === id)?.name ?? id.slice(0, 8);
  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("diplomacyTitle")}</h1>
      </header>
      <StateView
        loading={treaties.isLoading || organizations.isLoading}
        error={
          treaties.error ?? organizations.error ?? create.error ?? accept.error
        }
      >
        <div className="content-grid">
          <Panel>
            <div className="list-stack">
              {treaties.data?.map((item) => (
                <div className="list-row" key={item.id}>
                  <span>
                    <strong>{humanize(item.treaty_type)}</strong>
                    <small>
                      {orgName(item.proposer_org_id)} ↔{" "}
                      {orgName(item.recipient_org_id)} ·{" "}
                      {formatDate(item.expires_at, i18n.language)}
                    </small>
                  </span>
                  <div>
                    <Status value={item.status} />
                    {item.status === "proposed" && (
                      <button
                        className="button button--small"
                        onClick={() => accept.mutate(item.id)}
                      >
                        {t("accept")}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Panel>
          <Panel title={t("treatyCreate")}>
            <form onSubmit={submit}>
              <Field label={t("recipient")}>
                <select id="field-recipient-organization" name="recipient">
                  {organizations.data
                    ?.filter((item) => !item.my_role)
                    .map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                </select>
              </Field>
              <Field label={t("treatyType")}>
                <select id="field-treaty-type" name="type">
                  <option value="non_aggression">
                    {t("treatyNonAggression")}
                  </option>
                  <option value="intelligence_exchange">
                    {t("treatyInformationExchange")}
                  </option>
                  <option value="trade_cooperation">
                    {t("treatyTradeCooperation")}
                  </option>
                  <option value="joint_operation">
                    {t("treatyJointOperation")}
                  </option>
                </select>
              </Field>
              <Field label={t("durationDays")}>
                <input
                  id="field-duration-in-days"
                  name="duration"
                  type="number"
                  min="1"
                  max="90"
                  defaultValue="7"
                />
              </Field>
              <Field label={t("visibility")}>
                <select id="field-visibility" name="visibility">
                  <option value="public">{t("public")}</option>
                  <option value="secret">{t("secret")}</option>
                </select>
              </Field>
              <button className="button">{t("create")}</button>
            </form>
          </Panel>
        </div>
      </StateView>
    </div>
  );
}

interface Research {
  id: string;
  research_key: string;
  category: string;
  status: string;
  started_at: string;
  finishes_at: string;
}
export function ResearchPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["research"],
    queryFn: () => client.get<Research[]>("/research"),
  });
  const start = useMutation({
    mutationFn: (research_key: string) =>
      client.post<Research>(
        "/research",
        { research_key },
        createIdempotencyKey(),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["research"] }),
  });
  const projects = [
    "distributed_command",
    "market_analytics",
    "source_validation",
    "risk_early_warning",
    "mediation_protocols",
    "predictive_systems",
  ];
  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("researchTitle")}</h1>
      </header>
      <StateView loading={query.isLoading} error={query.error ?? start.error}>
        <div className="content-grid">
          <Panel>
            <div className="list-stack">
              {query.data?.map((item) => (
                <div className="list-row" key={item.id}>
                  <span>
                    <strong>{humanize(item.research_key)}</strong>
                    <small>
                      {humanize(item.category)} ·{" "}
                      {formatDate(item.finishes_at, i18n.language)}
                    </small>
                  </span>
                  <Status value={item.status} />
                </div>
              ))}
            </div>
          </Panel>
          <Panel title={t("researchStart")}>
            <div className="button-row">
              {projects.map((item) => (
                <button
                  className="button button--ghost"
                  key={item}
                  onClick={() => start.mutate(item)}
                >
                  {humanize(item)}
                </button>
              ))}
            </div>
          </Panel>
        </div>
      </StateView>
    </div>
  );
}

interface News {
  id: string;
  title: string;
  summary: string;
  published_at: string;
  certainty: string;
}
interface Notification {
  id: string;
  title: string;
  body: string;
  read_at: string | null;
  created_at: string;
}
export function NewsPage() {
  const { t, i18n } = useTranslation();
  const news = useQuery({
    queryKey: ["news"],
    queryFn: () => client.get<News[]>("/news"),
  });
  const notifications = useQuery({
    queryKey: ["notifications"],
    queryFn: () => client.get<Notification[]>("/notifications"),
  });
  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("newsTitle")}</h1>
      </header>
      <div className="content-grid">
        <Panel>
          <StateView
            loading={news.isLoading}
            error={news.error}
            empty={!news.data?.length}
          >
            {news.data?.map((item) => (
              <article className="news-item" key={item.id}>
                <Status
                  value={item.certainty}
                  uncertain={item.certainty !== "verified"}
                />
                <h2>{item.title}</h2>
                <p>{item.summary}</p>
                <time>{formatDate(item.published_at, i18n.language)}</time>
              </article>
            ))}
          </StateView>
        </Panel>
        <Panel title={t("notificationsTitle")}>
          <StateView
            loading={notifications.isLoading}
            error={notifications.error}
            empty={!notifications.data?.length}
          >
            {notifications.data?.map((item) => (
              <div className="list-row" key={item.id}>
                <span>
                  <strong>{item.title}</strong>
                  <small>
                    {item.body} · {formatDate(item.created_at, i18n.language)}
                  </small>
                </span>
                {!item.read_at && (
                  <span className="unread-dot" aria-label={t("unread")} />
                )}
              </div>
            ))}
          </StateView>
        </Panel>
      </div>
    </div>
  );
}

interface Ranking {
  rank: number;
  profile_id: string;
  codename: string;
  economic_power: number;
  influence: number;
  stability: number;
  intelligence: number;
  diplomacy: number;
  resilience: number;
  social_impact: number;
  penalty: number;
  score: number;
}
export function RankingsPage() {
  const { t, i18n } = useTranslation();
  const query = useQuery({
    queryKey: ["rankings"],
    queryFn: () => client.get<Ranking[]>("/rankings"),
  });
  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("rankingsTitle")}</h1>
      </header>
      <StateView
        loading={query.isLoading}
        error={query.error}
        empty={!query.data?.length}
      >
        <Panel>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t("rank")}</th>
                  <th>{t("codename")}</th>
                  <th>{t("score")}</th>
                  <th>{t("capital")}</th>
                  <th>{t("influence")}</th>
                  <th>{t("stability")}</th>
                  <th>{t("intelligence")}</th>
                  <th>{t("pressure")}</th>
                </tr>
              </thead>
              <tbody>
                {query.data?.map((item) => (
                  <tr key={item.profile_id}>
                    <td>{item.rank}</td>
                    <th>{item.codename}</th>
                    <td>
                      {new Intl.NumberFormat(i18n.language, {
                        maximumFractionDigits: 1,
                      }).format(item.score)}
                    </td>
                    <td>{item.economic_power}</td>
                    <td>{item.influence}</td>
                    <td>{item.stability}</td>
                    <td>{item.intelligence}</td>
                    <td>−{item.penalty}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </StateView>
    </div>
  );
}

interface Session {
  id: string;
  user_agent: string;
  created_at: string;
  expires_at: string;
  revoked_at: string | null;
}
export function SettingsPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const user = useAuth((state) => state.user);
  const [message, setMessage] = useState("");
  const queryClient = useQueryClient();
  const sessions = useQuery({
    queryKey: ["sessions"],
    queryFn: () => client.get<Session[]>("/auth/sessions"),
  });
  const revoke = useMutation({
    mutationFn: (id: string) => client.delete(`/auth/sessions/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sessions"] }),
  });
  const exportData = async () => {
    const data = await client.get<Record<string, unknown>>("/privacy/export");
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "shadowgrid-account-export.json";
    anchor.click();
    URL.revokeObjectURL(url);
    setMessage(t("success"));
  };
  const deleteAccount = async () => {
    if (!window.confirm(t("privacyDelete"))) return;
    await client.delete("/privacy/account");
    await logout();
    navigate("/");
  };
  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("settingsTitle")}</h1>
        <p>
          {user?.display_name} · {user?.email}
        </p>
      </header>
      {message && (
        <p className="notice notice--success" role="status">
          {message}
        </p>
      )}
      <div className="content-grid">
        <Panel title={t("language")}>
          <Field label={t("language")}>
            <select
              id="field-language"
              value={i18n.language}
              onChange={(event) => void setLocale(event.target.value as Locale)}
            >
              {configuredLocales.map((locale) => (
                <option value={locale} key={locale}>
                  {new Intl.DisplayNames([i18n.language], {
                    type: "language",
                  }).of(locale.split("-")[0] ?? locale) ?? locale}{" "}
                  ({locale})
                </option>
              ))}
            </select>
          </Field>
        </Panel>
        <Panel title={t("sessions")}>
          <StateView loading={sessions.isLoading} error={sessions.error}>
            {sessions.data?.map((item) => (
              <div className="list-row" key={item.id}>
                <span>
                  <strong>{item.user_agent}</strong>
                  <small>{formatDate(item.created_at, i18n.language)}</small>
                </span>
                <button
                  className="button button--small"
                  disabled={Boolean(item.revoked_at)}
                  onClick={() => revoke.mutate(item.id)}
                >
                  {t("revoke")}
                </button>
              </div>
            ))}
          </StateView>
        </Panel>
        <Panel title={t("privacy")}>
          <div className="button-row">
            <button
              className="button button--ghost"
              onClick={() => void exportData()}
            >
              {t("privacyExport")}
            </button>
            <button
              className="button button--danger"
              onClick={() => void deleteAccount()}
            >
              {t("privacyDelete")}
            </button>
          </div>
        </Panel>
      </div>
    </div>
  );
}

export function AdminPage() {
  const { t } = useTranslation();
  const query = useQuery({
    queryKey: ["admin"],
    queryFn: () => client.get<Record<string, number>>("/admin/summary"),
  });
  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("adminTitle")}</h1>
      </header>
      <StateView loading={query.isLoading} error={query.error}>
        <div className="metric-grid">
          {query.data &&
            Object.entries(query.data).map(([key, value]) => (
              <Metric key={key} label={humanize(key)} value={value} />
            ))}
        </div>
      </StateView>
    </div>
  );
}

interface Audit {
  id: string;
  actor_user_id: string | null;
  action: string;
  target_type: string;
  target_id: string;
  request_id: string;
  created_at: string;
}
export function ModerationPage() {
  const { t, i18n } = useTranslation();
  const query = useQuery({
    queryKey: ["audit"],
    queryFn: () => client.get<Audit[]>("/moderation/audit"),
  });
  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("moderationTitle")}</h1>
      </header>
      <StateView
        loading={query.isLoading}
        error={query.error}
        empty={!query.data?.length}
      >
        <Panel>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t("status")}</th>
                  <th>{t("target")}</th>
                  <th>{t("requestId", { id: "" })}</th>
                  <th>{t("date")}</th>
                </tr>
              </thead>
              <tbody>
                {query.data?.map((item) => (
                  <tr key={item.id}>
                    <th>{item.action}</th>
                    <td>
                      {item.target_type}:{item.target_id.slice(0, 8)}
                    </td>
                    <td>
                      <code>{item.request_id}</code>
                    </td>
                    <td>{formatDate(item.created_at, i18n.language)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </StateView>
    </div>
  );
}
