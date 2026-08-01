import { zodResolver } from "@hookform/resolvers/zod";
import { createIdempotencyKey } from "@shadowgrid/api-client";
import type {
  Profile,
  SeasonState,
  SeasonTemplate,
} from "@shadowgrid/shared-types";
import {
  seasonAdminSchema,
  type SeasonAdminInput,
} from "@shadowgrid/validation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { client } from "../auth";
import { ConfirmDialog, Field, Panel, StateView, Status } from "../components";
import { formatDate } from "../format";

interface SeasonCloseResponse {
  season: SeasonState;
  score_count: number;
  hall_of_fame_count: number;
  reward_count: number;
  archive_count: number;
}

export function SeasonsAdmin() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [message, setMessage] = useState("");
  const [confirmClose, setConfirmClose] = useState(false);
  const profile = useQuery({
    queryKey: ["profile"],
    queryFn: () => client.get<Profile>("/profiles/me"),
  });
  const seasons = useQuery({
    queryKey: ["admin-seasons", profile.data?.world_id],
    queryFn: () =>
      client.get<SeasonState[]>(
        `/admin/seasons?world_id=${profile.data?.world_id}`,
      ),
    enabled: Boolean(profile.data?.world_id),
  });
  const templates = useQuery({
    queryKey: ["admin-season-templates"],
    queryFn: () => client.get<SeasonTemplate[]>("/admin/seasons/templates"),
  });
  const latest = seasons.data?.[0];
  const initialValues = useMemo<SeasonAdminInput>(
    () => ({
      duration_minutes: latest
        ? Math.max(
            5,
            Math.floor(
              (new Date(latest.ends_at).getTime() -
                new Date(latest.starts_at).getTime()) /
                60_000,
            ) - 5,
          )
        : 60,
      simulate_at: new Date(Date.now() + 60 * 60_000)
        .toISOString()
        .slice(0, 16),
    }),
    [latest],
  );
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SeasonAdminInput>({
    resolver: zodResolver(seasonAdminSchema),
    values: initialValues,
  });
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["admin-seasons"] }),
      queryClient.invalidateQueries({ queryKey: ["season"] }),
      queryClient.invalidateQueries({ queryKey: ["hall-of-fame"] }),
      queryClient.invalidateQueries({ queryKey: ["account-rewards"] }),
    ]);
  };
  const shorten = useMutation({
    mutationFn: (value: SeasonAdminInput) =>
      client.post<SeasonState>(`/admin/seasons/${latest?.id}/shorten`, {
        duration_minutes: value.duration_minutes,
      }),
    onSuccess: async () => {
      setMessage(t("seasonShortenedSuccess"));
      await refresh();
    },
  });
  const simulate = useMutation({
    mutationFn: (value: SeasonAdminInput) =>
      client.post<SeasonState | SeasonCloseResponse>(
        `/admin/seasons/${latest?.id}/simulate`,
        { at: new Date(value.simulate_at).toISOString() },
      ),
    onSuccess: async () => {
      setMessage(t("seasonSimulatedSuccess"));
      await refresh();
    },
  });
  const close = useMutation({
    mutationFn: () =>
      client.post<SeasonCloseResponse>(
        `/admin/seasons/${latest?.id}/close`,
        {},
        createIdempotencyKey(),
      ),
    onSuccess: async (result) => {
      setMessage(
        t("seasonClosedSuccess", {
          scores: result.score_count,
          rewards: result.reward_count,
        }),
      );
      setConfirmClose(false);
      await refresh();
    },
  });
  const create = useMutation({
    mutationFn: () => {
      const template = templates.data?.find((item) => item.enabled);
      if (!template || !profile.data) {
        throw new Error(t("seasonTemplateMissing"));
      }
      return client.post<SeasonState>(
        "/admin/seasons",
        {
          world_id: profile.data.world_id,
          template_key: template.template_key,
          template_version: template.version,
        },
        createIdempotencyKey(),
      );
    },
    onSuccess: async () => {
      setMessage(t("seasonCreatedSuccess"));
      await refresh();
    },
  });
  const error =
    profile.error ??
    seasons.error ??
    templates.error ??
    shorten.error ??
    simulate.error ??
    close.error ??
    create.error;

  return (
    <Panel title={t("seasonAdminTitle")}>
      {message && (
        <p className="notice notice--success" role="status">
          {message}
        </p>
      )}
      <StateView
        loading={profile.isLoading || seasons.isLoading || templates.isLoading}
        error={error}
        empty={!latest}
      >
        {latest && (
          <div className="stack">
            <div className="list-row">
              <span>
                <strong>
                  {t("seasonLabel", { number: latest.season_number })} ·{" "}
                  {latest.name}
                </strong>
                <small>
                  {formatDate(latest.starts_at, i18n.language)} →{" "}
                  {formatDate(latest.ends_at, i18n.language)}
                </small>
              </span>
              <Status value={latest.phase} />
            </div>
            {latest.status !== "archived" ? (
              <form
                className="stack"
                onSubmit={handleSubmit((value) => shorten.mutate(value))}
              >
                <Field
                  label={t("seasonDuration")}
                  error={errors.duration_minutes?.message}
                >
                  <input
                    type="number"
                    min={5}
                    max={201_600}
                    {...register("duration_minutes", { valueAsNumber: true })}
                  />
                </Field>
                <button
                  className="button"
                  disabled={shorten.isPending}
                  type="submit"
                >
                  {t("seasonShorten")}
                </button>
                <Field
                  label={t("seasonSimulateAt")}
                  error={errors.simulate_at?.message}
                >
                  <input type="datetime-local" {...register("simulate_at")} />
                </Field>
                <button
                  className="button button--secondary"
                  disabled={simulate.isPending}
                  type="button"
                  onClick={handleSubmit((value) => simulate.mutate(value))}
                >
                  {t("seasonSimulate")}
                </button>
                <button
                  className="button button--danger"
                  disabled={close.isPending}
                  type="button"
                  onClick={() => setConfirmClose(true)}
                >
                  {t("seasonClose")}
                </button>
              </form>
            ) : (
              <button
                className="button"
                disabled={create.isPending || !templates.data?.length}
                onClick={() => create.mutate()}
              >
                {t("seasonCreateNext")}
              </button>
            )}
          </div>
        )}
      </StateView>
      {confirmClose && latest && (
        <ConfirmDialog
          title={t("seasonConfirmClose")}
          description={t("seasonConfirmCloseDescription", {
            season: latest.season_number,
          })}
          confirmLabel={t("seasonClose")}
          cancelLabel={t("cancel")}
          pending={close.isPending}
          onCancel={() => setConfirmClose(false)}
          onConfirm={() => close.mutate()}
        />
      )}
    </Panel>
  );
}
