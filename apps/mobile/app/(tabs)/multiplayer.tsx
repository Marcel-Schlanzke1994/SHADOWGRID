import {
  Alert,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { createIdempotencyKey } from "@shadowgrid/api-client";
import { i18n as shadowgridI18n } from "@shadowgrid/i18n";
import type {
  Alliance,
  CartelWar,
  ChatChannel,
  ChatMessage,
  PvpOperation,
  PvpTarget,
  Territory,
} from "@shadowgrid/shared-types";
import { api } from "../../src/api";
import { styles } from "../../src/theme";

const humanize = (value: string) => value.replaceAll("_", " ");

export default function Multiplayer() {
  const { t } = useTranslation(undefined, { i18n: shadowgridI18n });
  const queryClient = useQueryClient();
  const [channelId, setChannelId] = useState("");
  const [message, setMessage] = useState("");
  const targets = useQuery({
    queryKey: ["pvp-targets"],
    queryFn: () => api.get<PvpTarget[]>("/pvp/targets"),
  });
  const operations = useQuery({
    queryKey: ["pvp-operations"],
    queryFn: () => api.get<PvpOperation[]>("/pvp/operations"),
  });
  const territories = useQuery({
    queryKey: ["territories"],
    queryFn: () => api.get<Territory[]>("/territories"),
  });
  const wars = useQuery({
    queryKey: ["cartel-wars"],
    queryFn: () => api.get<CartelWar[]>("/cartel-wars"),
  });
  const alliances = useQuery({
    queryKey: ["alliances"],
    queryFn: () => api.get<Alliance[]>("/alliances"),
  });
  const channels = useQuery({
    queryKey: ["chat-channels"],
    queryFn: () => api.get<ChatChannel[]>("/chat/channels"),
  });
  useEffect(() => {
    if (!channelId && channels.data?.[0]) setChannelId(channels.data[0].id);
  }, [channelId, channels.data]);
  const messages = useQuery({
    queryKey: ["chat-messages", channelId],
    queryFn: () =>
      api.get<ChatMessage[]>(`/chat/channels/${channelId}/messages`),
    enabled: Boolean(channelId),
  });
  const launch = useMutation({
    mutationFn: (targetId: string) =>
      api.post<PvpOperation>(
        "/pvp/operations",
        {
          defender_profile_id: targetId,
          operation_type: "intelligence_probe",
          risk_posture: "balanced",
        },
        createIdempotencyKey(),
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["pvp-operations"] }),
  });
  const defend = useMutation({
    mutationFn: (operationId: string) =>
      api.post<PvpOperation>(`/pvp/operations/${operationId}/defend`, {
        action_type: "secure_information",
        commitment: { posture: "mobile_standard" },
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["pvp-operations"] }),
  });
  const claim = useMutation({
    mutationFn: (districtId: string) =>
      api.post(
        `/territories/${districtId}/claim`,
        { claim_type: "influence" },
        createIdempotencyKey(),
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["territories"] }),
  });
  const send = useMutation({
    mutationFn: () =>
      api.post<ChatMessage>(`/chat/channels/${channelId}/messages`, {
        body: message,
      }),
    onSuccess: () => {
      setMessage("");
      void queryClient.invalidateQueries({
        queryKey: ["chat-messages", channelId],
      });
    },
  });

  return (
    <ScrollView contentContainerStyle={styles.screen}>
      <Text accessibilityRole="header" style={styles.title}>
        {t("navPvp")}
      </Text>
      <Text style={styles.subtitle}>{t("pvpDescription")}</Text>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>{t("pvpTargets")}</Text>
        {targets.data?.slice(0, 5).map((target) => (
          <View key={target.profile_id} style={styles.card}>
            <Text style={styles.text}>{target.codename}</Text>
            <Text style={styles.muted}>
              {humanize(target.estimated_strength)} ·{" "}
              {humanize(target.protection_status)}
            </Text>
            <Pressable
              accessibilityRole="button"
              style={styles.button}
              disabled={target.protection_status === "protected"}
              onPress={() =>
                Alert.alert(t("navPvp"), t("confirmPvpLaunch"), [
                  { text: t("cancel"), style: "cancel" },
                  {
                    text: t("launch"),
                    onPress: () => launch.mutate(target.profile_id),
                  },
                ])
              }
            >
              <Text style={styles.buttonText}>{t("launch")}</Text>
            </Pressable>
          </View>
        ))}
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>{t("pvpOperations")}</Text>
        {operations.data?.map((operation) => (
          <View key={operation.id} style={styles.card}>
            <Text style={styles.text}>
              {humanize(operation.operation_type)}
            </Text>
            <Text style={styles.muted}>
              {humanize(operation.my_side)} · {humanize(operation.status)}
            </Text>
            {operation.my_side === "defender" &&
              !operation.defense_submitted && (
                <Pressable
                  style={styles.button}
                  onPress={() => defend.mutate(operation.id)}
                >
                  <Text style={styles.buttonText}>{t("defend")}</Text>
                </Pressable>
              )}
          </View>
        ))}
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>{t("territoriesTitle")}</Text>
        {territories.data?.map((territory) => (
          <View key={territory.district_id} style={styles.card}>
            <Text style={styles.text}>{territory.district_name}</Text>
            <Text style={styles.muted}>{humanize(territory.status)}</Text>
            <Pressable
              style={styles.button}
              onPress={() => claim.mutate(territory.district_id)}
            >
              <Text style={styles.buttonText}>{t("claim")}</Text>
            </Pressable>
          </View>
        ))}
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>
          {t("warsTitle")} · {wars.data?.length ?? 0}
        </Text>
        <Text style={styles.text}>
          {t("alliancesTitle")} · {alliances.data?.length ?? 0}
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>{t("communicationsTitle")}</Text>
        <ScrollView horizontal contentContainerStyle={styles.list}>
          {channels.data?.map((channel) => (
            <Pressable
              style={styles.button}
              key={channel.id}
              onPress={() => setChannelId(channel.id)}
            >
              <Text style={styles.buttonText}>{channel.name}</Text>
            </Pressable>
          ))}
        </ScrollView>
        {messages.data?.slice(-10).map((item) => (
          <Text style={styles.text} key={item.id}>
            {item.body}
          </Text>
        ))}
        <TextInput
          accessibilityLabel={t("message")}
          style={styles.input}
          value={message}
          maxLength={1000}
          onChangeText={setMessage}
        />
        <Pressable
          style={styles.button}
          disabled={!message.trim()}
          onPress={() => send.mutate()}
        >
          <Text style={styles.buttonText}>{t("send")}</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}
