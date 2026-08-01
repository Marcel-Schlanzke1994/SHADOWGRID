import { useEffect, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { createIdempotencyKey } from "@shadowgrid/api-client";
import { translateGameValue } from "@shadowgrid/i18n";
import type {
  CollectionEntry,
  Company,
  EventDossier,
  NarrativeActorRelationship,
  NarrativeChronicleEntry,
  ParallelRankings,
  PlayerIdentity,
  PlayerSeasonGoal,
  Profile,
  ReturnContract,
  StrategicProfileCard,
} from "@shadowgrid/shared-types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";
import { client } from "../auth";
import { Field, Panel, Progress, StateView, Status } from "../components";
import { formatDate } from "../format";

const identitySchema = z.object({
  title_item_id: z.string(),
  emblem_item_id: z.string(),
  hq_cosmetic_item_id: z.string(),
  profile_card_public: z.boolean(),
});
type IdentityInput = z.infer<typeof identitySchema>;

function ChronicleCards({ entries }: { entries: NarrativeChronicleEntry[] }) {
  const { t, i18n } = useTranslation();
  return (
    <div className="card-grid">
      {entries.map((entry) => (
        <article className="card" key={entry.id}>
          <div className="list-row">
            <h3>{t(entry.title_key)}</h3>
            <small>{formatDate(entry.created_at, i18n.language)}</small>
          </div>
          <p>{t(entry.body_key)}</p>
          <h4>{t("engagementLegacyCauses")}</h4>
          <ul>
            {entry.cause_keys_json.map((key) => (
              <li key={key}>{t(key)}</li>
            ))}
          </ul>
          <h4>{t("engagementLegacyConsequences")}</h4>
          <ul>
            {entry.impact_keys_json.map((key) => (
              <li key={key}>{t(key)}</li>
            ))}
          </ul>
          {entry.open_question_keys_json.map((key) => (
            <p key={key}>{t(key)}</p>
          ))}
        </article>
      ))}
    </div>
  );
}

export function LegacyPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [companyId, setCompanyId] = useState("");
  const profile = useQuery({
    queryKey: ["profile"],
    queryFn: () => client.get<Profile>("/profiles/me"),
  });
  const companies = useQuery({
    queryKey: ["companies"],
    queryFn: () => client.get<Company[]>("/companies"),
  });
  useEffect(() => {
    if (!companyId && companies.data?.[0]) setCompanyId(companies.data[0].id);
  }, [companies.data, companyId]);
  const actors = useQuery({
    queryKey: ["engagement-legacy-actors"],
    queryFn: () =>
      client.get<NarrativeActorRelationship[]>("/engagement/legacy/actors"),
  });
  const dossiers = useQuery({
    queryKey: ["engagement-legacy-dossiers"],
    queryFn: () => client.get<EventDossier[]>("/engagement/legacy/dossiers"),
  });
  const collection = useQuery({
    queryKey: ["engagement-legacy-collection"],
    queryFn: () =>
      client.get<CollectionEntry[]>("/engagement/legacy/collection"),
  });
  const identity = useQuery({
    queryKey: ["engagement-legacy-identity"],
    queryFn: () => client.get<PlayerIdentity>("/engagement/legacy/identity"),
  });
  const profileCard = useQuery({
    queryKey: ["engagement-legacy-profile-card"],
    queryFn: () =>
      client.get<StrategicProfileCard>("/engagement/legacy/profile-card"),
  });
  const seasonGoals = useQuery({
    queryKey: ["engagement-legacy-season-goals"],
    queryFn: () =>
      client.get<PlayerSeasonGoal[]>("/engagement/legacy/season-goals"),
  });
  const rankings = useQuery({
    queryKey: ["engagement-legacy-rankings"],
    queryFn: () => client.get<ParallelRankings>("/engagement/legacy/rankings"),
  });
  const worldChronicle = useQuery({
    queryKey: ["engagement-legacy-world-chronicle", profile.data?.world_id],
    queryFn: () =>
      client.get<NarrativeChronicleEntry[]>(
        `/engagement/legacy/chronicles/world/${profile.data?.world_id ?? ""}`,
      ),
    enabled: Boolean(profile.data?.world_id),
  });
  const companyChronicle = useQuery({
    queryKey: ["engagement-legacy-company-chronicle", companyId],
    queryFn: () =>
      client.get<NarrativeChronicleEntry[]>(
        `/engagement/legacy/chronicles/company/${companyId}`,
      ),
    enabled: Boolean(companyId),
  });
  const investigate = useMutation({
    mutationFn: (dossierId: string) =>
      client.post<EventDossier>(
        `/engagement/legacy/dossiers/${dossierId}/investigate`,
        {},
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["engagement-legacy-dossiers"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["engagement-legacy-collection"],
        }),
      ]);
    },
  });
  const selectGoal = useMutation({
    mutationFn: (goalId: string) =>
      client.post<PlayerSeasonGoal>(
        `/engagement/legacy/season-goals/${goalId}/select`,
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["engagement-legacy-season-goals"],
      });
    },
  });
  const returnContracts = useMutation({
    mutationFn: () =>
      client.post<ReturnContract[]>("/engagement/legacy/return-contracts"),
  });
  const selectContract = useMutation({
    mutationFn: (contractId: string) =>
      client.post<ReturnContract>(
        `/engagement/legacy/return-contracts/${contractId}/select`,
      ),
    onSuccess: (value) => {
      returnContracts.reset();
      returnContracts.mutate();
      if (value.status === "active") {
        void queryClient.invalidateQueries({
          queryKey: ["engagement-open-plans"],
        });
      }
    },
  });
  const identityForm = useForm<IdentityInput>({
    resolver: zodResolver(identitySchema),
    defaultValues: {
      title_item_id: "",
      emblem_item_id: "",
      hq_cosmetic_item_id: "",
      profile_card_public: true,
    },
  });
  useEffect(() => {
    if (!identity.data) return;
    identityForm.reset({
      title_item_id: identity.data.active_title_item_id ?? "",
      emblem_item_id: identity.data.active_emblem_item_id ?? "",
      hq_cosmetic_item_id: identity.data.active_hq_cosmetic_item_id ?? "",
      profile_card_public: identity.data.profile_card_public,
    });
  }, [identity.data, identityForm]);
  const updateIdentity = useMutation({
    mutationFn: (value: IdentityInput) =>
      client.put<PlayerIdentity>("/engagement/legacy/identity", {
        title_item_id: value.title_item_id || null,
        emblem_item_id: value.emblem_item_id || null,
        hq_cosmetic_item_id: value.hq_cosmetic_item_id || null,
        profile_card_public: value.profile_card_public,
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["engagement-legacy-identity"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["engagement-legacy-profile-card"],
        }),
      ]);
    },
  });
  const itemOptions = (itemType: CollectionEntry["item_type"]) =>
    collection.data?.filter((item) => item.item_type === itemType) ?? [];

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <span className="eyebrow">{t("engagementLegacyEyebrow")}</span>
          <h1>{t("engagementLegacyTitle")}</h1>
          <p>{t("engagementLegacyDescription")}</p>
        </div>
      </header>

      <Panel title={t("engagementActorsTitle")}>
        <StateView
          loading={actors.isLoading}
          error={actors.error}
          empty={!actors.data?.length}
        >
          <div className="card-grid">
            {actors.data?.map((actor) => (
              <article className="card" key={actor.actor_id}>
                <h3>{t(actor.name_key)}</h3>
                <p>{t(actor.description_key)}</p>
                <dl className="definition-list">
                  <div>
                    <dt>{t("engagementActorTrust")}</dt>
                    <dd>{actor.trust}</dd>
                  </div>
                  <div>
                    <dt>{t("engagementActorRivalry")}</dt>
                    <dd>{actor.rivalry}</dd>
                  </div>
                  <div>
                    <dt>{t("engagementActorReputation")}</dt>
                    <dd>{actor.reputation}</dd>
                  </div>
                  <div>
                    <dt>{t("engagementActorInformationAccess")}</dt>
                    <dd>{actor.information_access}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        </StateView>
      </Panel>

      <Panel title={t("engagementDossiersTitle")}>
        <StateView
          loading={dossiers.isLoading}
          error={dossiers.error ?? investigate.error}
          empty={!dossiers.data?.length}
        >
          <div className="card-grid">
            {dossiers.data?.map((dossier) => (
              <article className="card" key={dossier.id}>
                <div className="list-row">
                  <h3>{t(dossier.title_key)}</h3>
                  <Status value={dossier.archived ? "archived" : "active"} />
                </div>
                <p>{t(dossier.cause_key)}</p>
                <p>{t(dossier.local_impact_key)}</p>
                <p>{t(dossier.open_question_key)}</p>
                <ul>
                  {dossier.clues.map((clue) => (
                    <li key={clue.id}>
                      {clue.discovered
                        ? t(clue.clue_key)
                        : t("engagementDossierHiddenClue")}
                    </li>
                  ))}
                </ul>
                <button
                  className="button"
                  disabled={
                    investigate.isPending || Boolean(dossier.completed_at)
                  }
                  onClick={() => investigate.mutate(dossier.id)}
                >
                  {dossier.completed_at
                    ? t("engagementDossierCompleted")
                    : t("engagementDossierInvestigate")}
                </button>
              </article>
            ))}
          </div>
        </StateView>
      </Panel>

      <div className="two-column">
        <Panel title={t("engagementCompanyChronicleTitle")}>
          <StateView
            loading={companies.isLoading}
            error={companies.error}
            empty={!companies.data?.length}
          >
            <Field label={t("engagementChronicleCompany")}>
              <select
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
            <StateView
              loading={companyChronicle.isLoading}
              error={companyChronicle.error}
              empty={!companyChronicle.data?.length}
            >
              <ChronicleCards entries={companyChronicle.data ?? []} />
            </StateView>
          </StateView>
        </Panel>
        <Panel title={t("engagementWorldChronicleTitle")}>
          <StateView
            loading={profile.isLoading || worldChronicle.isLoading}
            error={profile.error ?? worldChronicle.error}
            empty={!worldChronicle.data?.length}
          >
            <ChronicleCards entries={worldChronicle.data ?? []} />
          </StateView>
        </Panel>
      </div>

      <div className="two-column">
        <Panel title={t("engagementCollectionTitle")}>
          <StateView
            loading={collection.isLoading}
            error={collection.error}
            empty={!collection.data?.length}
          >
            <div className="card-grid">
              {collection.data?.map((item) => (
                <article className="card" key={item.id}>
                  <h3>{t(item.title_key)}</h3>
                  <p>{t(item.description_key)}</p>
                  <small>
                    {t("engagementCollectionRarity", { rarity: item.rarity })}
                  </small>
                  {item.duplicate_points > 0 && (
                    <small>
                      {t("engagementCollectionDuplicatePoints", {
                        count: item.duplicate_points,
                      })}
                    </small>
                  )}
                </article>
              ))}
            </div>
          </StateView>
        </Panel>
        <Panel title={t("engagementIdentityTitle")}>
          <StateView
            loading={identity.isLoading || collection.isLoading}
            error={identity.error ?? updateIdentity.error}
          >
            <form
              onSubmit={identityForm.handleSubmit((value) =>
                updateIdentity.mutate(value),
              )}
            >
              {(["title", "emblem", "hq_cosmetic"] as const).map((itemType) => (
                <Field
                  key={itemType}
                  label={t(
                    `engagementIdentity${itemType === "hq_cosmetic" ? "Hq" : itemType.charAt(0).toUpperCase() + itemType.slice(1)}`,
                  )}
                >
                  <select {...identityForm.register(`${itemType}_item_id`)}>
                    <option value="">{t("engagementIdentityNone")}</option>
                    {itemOptions(itemType).map((item) => (
                      <option key={item.item_id} value={item.item_id}>
                        {t(item.title_key)}
                      </option>
                    ))}
                  </select>
                </Field>
              ))}
              <label className="check-row">
                <input
                  type="checkbox"
                  {...identityForm.register("profile_card_public")}
                />
                {t("engagementIdentityPublic")}
              </label>
              <button className="button" disabled={updateIdentity.isPending}>
                {t("save")}
              </button>
            </form>
            {profileCard.data && (
              <article className="card">
                <h3>{profileCard.data.codename}</h3>
                <p>
                  {profileCard.data.doctrine_key ??
                    t("engagementIdentityNoDoctrine")}
                </p>
                {profileCard.data.mastery_highlights.map((item) => (
                  <small key={item.area_key}>
                    {translateGameValue(item.area_key)} · {item.level}
                  </small>
                ))}
              </article>
            )}
          </StateView>
        </Panel>
      </div>

      <Panel title={t("engagementSeasonGoalsTitle")}>
        <StateView
          loading={seasonGoals.isLoading}
          error={seasonGoals.error ?? selectGoal.error}
          empty={!seasonGoals.data?.length}
        >
          <div className="card-grid">
            {seasonGoals.data?.map((goal) => (
              <article className="card" key={goal.id}>
                <div className="list-row">
                  <h3>{t(goal.title_key)}</h3>
                  <Status value={goal.status} />
                </div>
                <p>{t(goal.description_key)}</p>
                <Progress
                  label={t("engagementGoalProgress", {
                    current: goal.progress_value,
                    target: goal.target_value,
                  })}
                  value={(goal.progress_value * 100) / goal.target_value}
                />
                {goal.status === "offered" && (
                  <button
                    className="button"
                    disabled={selectGoal.isPending}
                    onClick={() => selectGoal.mutate(goal.id)}
                  >
                    {t("engagementChooseGoal")}
                  </button>
                )}
              </article>
            ))}
          </div>
        </StateView>
      </Panel>

      <Panel title={t("engagementReturnContractsTitle")}>
        <p>{t("engagementReturnContractsDescription")}</p>
        {!returnContracts.data && (
          <button
            className="button"
            disabled={returnContracts.isPending}
            onClick={() => returnContracts.mutate()}
          >
            {t("engagementReturnContractsCheck")}
          </button>
        )}
        <StateView
          error={returnContracts.error ?? selectContract.error}
          empty={returnContracts.data?.length === 0}
        >
          <div className="card-grid">
            {returnContracts.data?.map((contract) => (
              <article className="card" key={contract.id}>
                <div className="list-row">
                  <h3>{t(contract.title_key)}</h3>
                  <Status value={contract.status} />
                </div>
                <p>{t(contract.description_key)}</p>
                <small>
                  {t("engagementReturnAbsence", {
                    days: contract.absence_days,
                  })}
                </small>
                {contract.status === "offered" && (
                  <button
                    className="button"
                    disabled={selectContract.isPending}
                    onClick={() => selectContract.mutate(contract.id)}
                  >
                    {t("engagementReturnContractChoose")}
                  </button>
                )}
              </article>
            ))}
          </div>
        </StateView>
      </Panel>

      <Panel title={t("engagementParallelRankingsTitle")}>
        <p>{t("engagementParallelRankingsDescription")}</p>
        <StateView loading={rankings.isLoading} error={rankings.error}>
          <div className="card-grid">
            {rankings.data?.categories.map((category) => (
              <article className="card" key={category.category}>
                <h3>
                  {t(
                    `engagementRanking${category.category
                      .split("_")
                      .map(
                        (part) => part.charAt(0).toUpperCase() + part.slice(1),
                      )
                      .join("")}`,
                  )}
                </h3>
                <ol>
                  {category.entries.slice(0, 5).map((entry) => (
                    <li key={entry.profile_id}>
                      {entry.codename} · {entry.score} ·{" "}
                      {t(
                        `engagementRankingBracket${entry.bracket === "newcomer" ? "Newcomer" : "Veteran"}`,
                      )}
                      {" · "}
                      {t("engagementRankingHistoricalBest", {
                        score: entry.historical_best_score,
                      })}
                    </li>
                  ))}
                </ol>
              </article>
            ))}
          </div>
        </StateView>
      </Panel>
    </div>
  );
}
