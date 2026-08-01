import {
  ActivityIndicator,
  ScrollView,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { createIdempotencyKey } from "@shadowgrid/api-client";
import { i18n as shadowgridI18n, translateGameValue } from "@shadowgrid/i18n";
import type {
  CollectionEntry,
  EventDossier,
  NarrativeActorRelationship,
  NarrativeChronicleEntry,
  ParallelRankings,
  PlayerIdentity,
  PlayerSeasonGoal,
  Profile,
  ReturnContract,
} from "@shadowgrid/shared-types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../../src/api";
import { colors, styles } from "../../src/theme";

export default function Legacy() {
  const { t } = useTranslation(undefined, { i18n: shadowgridI18n });
  const queryClient = useQueryClient();
  const profile = useQuery({
    queryKey: ["profile"],
    queryFn: () => api.get<Profile>("/profiles/me"),
  });
  const actors = useQuery({
    queryKey: ["engagement-legacy-actors"],
    queryFn: () =>
      api.get<NarrativeActorRelationship[]>("/engagement/legacy/actors"),
  });
  const dossiers = useQuery({
    queryKey: ["engagement-legacy-dossiers"],
    queryFn: () => api.get<EventDossier[]>("/engagement/legacy/dossiers"),
  });
  const collection = useQuery({
    queryKey: ["engagement-legacy-collection"],
    queryFn: () => api.get<CollectionEntry[]>("/engagement/legacy/collection"),
  });
  const identity = useQuery({
    queryKey: ["engagement-legacy-identity"],
    queryFn: () => api.get<PlayerIdentity>("/engagement/legacy/identity"),
  });
  const seasonGoals = useQuery({
    queryKey: ["engagement-legacy-season-goals"],
    queryFn: () =>
      api.get<PlayerSeasonGoal[]>("/engagement/legacy/season-goals"),
  });
  const rankings = useQuery({
    queryKey: ["engagement-legacy-rankings"],
    queryFn: () => api.get<ParallelRankings>("/engagement/legacy/rankings"),
  });
  const chronicle = useQuery({
    queryKey: ["engagement-legacy-world-chronicle", profile.data?.world_id],
    queryFn: () =>
      api.get<NarrativeChronicleEntry[]>(
        `/engagement/legacy/chronicles/world/${profile.data?.world_id ?? ""}`,
      ),
    enabled: Boolean(profile.data?.world_id),
  });
  const investigate = useMutation({
    mutationFn: (dossierId: string) =>
      api.post<EventDossier>(
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
  const chooseGoal = useMutation({
    mutationFn: (goalId: string) =>
      api.post<PlayerSeasonGoal>(
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
      api.post<ReturnContract[]>("/engagement/legacy/return-contracts"),
  });
  const chooseContract = useMutation({
    mutationFn: (contractId: string) =>
      api.post<ReturnContract>(
        `/engagement/legacy/return-contracts/${contractId}/select`,
      ),
    onSuccess: () => returnContracts.mutate(),
  });
  const equip = useMutation({
    mutationFn: (item: CollectionEntry) =>
      api.put<PlayerIdentity>("/engagement/legacy/identity", {
        title_item_id:
          item.item_type === "title"
            ? item.item_id
            : (identity.data?.active_title_item_id ?? null),
        emblem_item_id:
          item.item_type === "emblem"
            ? item.item_id
            : (identity.data?.active_emblem_item_id ?? null),
        hq_cosmetic_item_id:
          item.item_type === "hq_cosmetic"
            ? item.item_id
            : (identity.data?.active_hq_cosmetic_item_id ?? null),
        profile_card_public: identity.data?.profile_card_public ?? true,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["engagement-legacy-identity"],
      });
    },
  });
  const loading =
    profile.isLoading ||
    actors.isLoading ||
    dossiers.isLoading ||
    collection.isLoading ||
    identity.isLoading ||
    seasonGoals.isLoading ||
    rankings.isLoading;
  const error =
    profile.error ??
    actors.error ??
    dossiers.error ??
    collection.error ??
    identity.error ??
    seasonGoals.error ??
    rankings.error ??
    chronicle.error ??
    investigate.error ??
    chooseGoal.error ??
    returnContracts.error ??
    chooseContract.error ??
    equip.error;

  return (
    <ScrollView contentContainerStyle={styles.screen}>
      <Text accessibilityRole="header" style={styles.title}>
        {t("engagementLegacyTitle")}
      </Text>
      <Text style={styles.subtitle}>{t("engagementLegacyDescription")}</Text>
      {loading && <ActivityIndicator color={colors.gold} />}
      {error && (
        <Text accessibilityRole="alert" style={styles.text}>
          {t("offlineBody")}
        </Text>
      )}

      <View style={styles.list}>
        <Text accessibilityRole="header" style={styles.sectionTitle}>
          {t("engagementActorsTitle")}
        </Text>
        {actors.data?.map((actor) => (
          <View style={styles.card} key={actor.actor_id}>
            <Text style={styles.cardTitle}>{t(actor.name_key)}</Text>
            <Text style={styles.text}>{t(actor.description_key)}</Text>
            <Text style={styles.muted}>
              {t("engagementActorTrust")}: {actor.trust} ·{" "}
              {t("engagementActorReputation")}: {actor.reputation}
            </Text>
            <Text style={styles.muted}>
              {t("engagementActorInformationAccess")}:{" "}
              {actor.information_access}
            </Text>
          </View>
        ))}
      </View>

      <View style={styles.list}>
        <Text accessibilityRole="header" style={styles.sectionTitle}>
          {t("engagementDossiersTitle")}
        </Text>
        {!dossiers.data?.length && (
          <Text style={styles.muted}>{t("empty")}</Text>
        )}
        {dossiers.data?.map((dossier) => (
          <View style={styles.card} key={dossier.id}>
            <Text style={styles.cardTitle}>{t(dossier.title_key)}</Text>
            <Text style={styles.text}>{t(dossier.cause_key)}</Text>
            {dossier.clues.map((clue) => (
              <Text style={styles.muted} key={clue.id}>
                {clue.discovered
                  ? t(clue.clue_key)
                  : t("engagementDossierHiddenClue")}
              </Text>
            ))}
            <TouchableOpacity
              accessibilityRole="button"
              disabled={investigate.isPending || Boolean(dossier.completed_at)}
              onPress={() => investigate.mutate(dossier.id)}
              style={styles.secondaryButton}
            >
              <Text style={styles.secondaryButtonText}>
                {dossier.completed_at
                  ? t("engagementDossierCompleted")
                  : t("engagementDossierInvestigate")}
              </Text>
            </TouchableOpacity>
          </View>
        ))}
      </View>

      <View style={styles.list}>
        <Text accessibilityRole="header" style={styles.sectionTitle}>
          {t("engagementWorldChronicleTitle")}
        </Text>
        {!chronicle.data?.length && (
          <Text style={styles.muted}>{t("empty")}</Text>
        )}
        {chronicle.data?.map((entry) => (
          <View style={styles.card} key={entry.id}>
            <Text style={styles.cardTitle}>{t(entry.title_key)}</Text>
            <Text style={styles.text}>{t(entry.body_key)}</Text>
            {entry.open_question_keys_json.map((key) => (
              <Text style={styles.muted} key={key}>
                {t(key)}
              </Text>
            ))}
          </View>
        ))}
      </View>

      <View style={styles.list}>
        <Text accessibilityRole="header" style={styles.sectionTitle}>
          {t("engagementCollectionTitle")}
        </Text>
        {!collection.data?.length && (
          <Text style={styles.muted}>{t("empty")}</Text>
        )}
        {collection.data?.map((item) => {
          const equippable = ["title", "emblem", "hq_cosmetic"].includes(
            item.item_type,
          );
          return (
            <View style={styles.card} key={item.id}>
              <Text style={styles.cardTitle}>{t(item.title_key)}</Text>
              <Text style={styles.text}>{t(item.description_key)}</Text>
              <Text style={styles.muted}>
                {t("engagementCollectionRarity", { rarity: item.rarity })}
              </Text>
              {equippable && (
                <TouchableOpacity
                  accessibilityRole="button"
                  disabled={equip.isPending}
                  onPress={() => equip.mutate(item)}
                  style={styles.secondaryButton}
                >
                  <Text style={styles.secondaryButtonText}>
                    {t("engagementIdentityEquip")}
                  </Text>
                </TouchableOpacity>
              )}
            </View>
          );
        })}
      </View>

      <View style={styles.list}>
        <Text accessibilityRole="header" style={styles.sectionTitle}>
          {t("engagementSeasonGoalsTitle")}
        </Text>
        {!seasonGoals.data?.length && (
          <Text style={styles.muted}>{t("empty")}</Text>
        )}
        {seasonGoals.data?.map((goal) => (
          <View style={styles.card} key={goal.id}>
            <Text style={styles.cardTitle}>{t(goal.title_key)}</Text>
            <Text style={styles.text}>{t(goal.description_key)}</Text>
            <Text style={styles.muted}>
              {t("engagementGoalProgress", {
                current: goal.progress_value,
                target: goal.target_value,
              })}
            </Text>
            {goal.status === "offered" && (
              <TouchableOpacity
                accessibilityRole="button"
                disabled={chooseGoal.isPending}
                onPress={() => chooseGoal.mutate(goal.id)}
                style={styles.secondaryButton}
              >
                <Text style={styles.secondaryButtonText}>
                  {t("engagementChooseGoal")}
                </Text>
              </TouchableOpacity>
            )}
          </View>
        ))}
      </View>

      <View style={styles.list}>
        <Text accessibilityRole="header" style={styles.sectionTitle}>
          {t("engagementReturnContractsTitle")}
        </Text>
        <TouchableOpacity
          accessibilityRole="button"
          disabled={returnContracts.isPending}
          onPress={() => returnContracts.mutate()}
          style={styles.button}
        >
          <Text style={styles.buttonText}>
            {t("engagementReturnContractsCheck")}
          </Text>
        </TouchableOpacity>
        {returnContracts.data?.map((contract) => (
          <View style={styles.card} key={contract.id}>
            <Text style={styles.cardTitle}>{t(contract.title_key)}</Text>
            <Text style={styles.text}>{t(contract.description_key)}</Text>
            {contract.status === "offered" && (
              <TouchableOpacity
                accessibilityRole="button"
                disabled={chooseContract.isPending}
                onPress={() => chooseContract.mutate(contract.id)}
                style={styles.secondaryButton}
              >
                <Text style={styles.secondaryButtonText}>
                  {t("engagementReturnContractChoose")}
                </Text>
              </TouchableOpacity>
            )}
          </View>
        ))}
      </View>

      <View style={styles.list}>
        <Text accessibilityRole="header" style={styles.sectionTitle}>
          {t("engagementParallelRankingsTitle")}
        </Text>
        <Text style={styles.muted}>
          {t("engagementParallelRankingsDescription")}
        </Text>
        {rankings.data?.categories.map((category) => {
          const own = category.entries.find((entry) => entry.is_self);
          return (
            <View style={styles.card} key={category.category}>
              <Text style={styles.cardTitle}>
                {translateGameValue(category.category)}
              </Text>
              <Text style={styles.value}>
                {own ? `#${own.rank} · ${own.score}` : "—"}
              </Text>
              {own && (
                <Text style={styles.muted}>
                  {t("engagementRankingHistoricalBest", {
                    score: own.historical_best_score,
                  })}
                </Text>
              )}
            </View>
          );
        })}
      </View>
    </ScrollView>
  );
}
