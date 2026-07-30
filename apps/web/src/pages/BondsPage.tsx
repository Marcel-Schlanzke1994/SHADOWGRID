import { zodResolver } from "@hookform/resolvers/zod";
import { createIdempotencyKey } from "@shadowgrid/api-client";
import type {
  BondConfig,
  BondHolding,
  BondIssue,
  BondSubscription,
  Company,
} from "@shadowgrid/shared-types";
import {
  bondIssueSchema,
  bondSubscriptionSchema,
  type BondIssueInput,
  type BondSubscriptionInput,
} from "@shadowgrid/validation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { client } from "../auth";
import {
  ConfirmDialog,
  Field,
  Panel,
  Progress,
  StateView,
  Status,
} from "../components";
import { formatCents, formatDate, formatNumber } from "../format";

export function BondsPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [message, setMessage] = useState("");
  const [pendingSubscription, setPendingSubscription] =
    useState<BondSubscriptionInput | null>(null);
  const [pendingActivation, setPendingActivation] = useState<BondIssue | null>(
    null,
  );
  const companies = useQuery({
    queryKey: ["companies"],
    queryFn: () => client.get<Company[]>("/companies"),
  });
  const config = useQuery({
    queryKey: ["bond-config"],
    queryFn: () => client.get<BondConfig>("/bonds/config"),
  });
  const issues = useQuery({
    queryKey: ["bond-issues"],
    queryFn: () => client.get<BondIssue[]>("/bonds/issues"),
  });
  const holdings = useQuery({
    queryKey: ["bond-holdings"],
    queryFn: () => client.get<BondHolding[]>("/bonds/holdings/me"),
  });
  const ownedCompanyIds = useMemo(
    () => new Set(companies.data?.map((company) => company.id) ?? []),
    [companies.data],
  );
  const offeringIssues = useMemo(
    () => issues.data?.filter((issue) => issue.status === "offering"),
    [issues.data],
  );
  const issueValues = useMemo<BondIssueInput | undefined>(() => {
    const company = companies.data?.[0];
    if (!company) return undefined;
    return {
      issuer_company_id: company.id,
      symbol: "",
      title: "",
      face_value_cents: 100_000,
      total_units: 5,
      coupon_rate_bps: 800,
      term_periods: 3,
    };
  }, [companies.data]);
  const subscriptionValues = useMemo<BondSubscriptionInput | undefined>(() => {
    const issue = offeringIssues?.[0];
    if (!issue) return undefined;
    return { issue_id: issue.id, quantity: 1 };
  }, [offeringIssues]);
  const issueForm = useForm<BondIssueInput>({
    resolver: zodResolver(bondIssueSchema),
    values: issueValues,
  });
  const subscriptionForm = useForm<BondSubscriptionInput>({
    resolver: zodResolver(bondSubscriptionSchema),
    values: subscriptionValues,
  });
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["companies"] }),
      queryClient.invalidateQueries({ queryKey: ["bond-issues"] }),
      queryClient.invalidateQueries({ queryKey: ["bond-holdings"] }),
    ]);
  };
  const createIssue = useMutation({
    mutationFn: (value: BondIssueInput) =>
      client.post<BondIssue>("/bonds/issues", value, createIdempotencyKey()),
    onSuccess: async () => {
      setMessage(t("bondIssueCreated"));
      await refresh();
    },
  });
  const subscribe = useMutation({
    mutationFn: (value: BondSubscriptionInput) =>
      client.post<BondSubscription>(
        `/bonds/issues/${value.issue_id}/subscribe`,
        { quantity: value.quantity },
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setMessage(t("bondSubscribed"));
      setPendingSubscription(null);
      await refresh();
    },
  });
  const activate = useMutation({
    mutationFn: (issue: BondIssue) =>
      client.post<BondIssue>(`/bonds/issues/${issue.id}/activate`),
    onSuccess: async () => {
      setMessage(t("bondActivated"));
      setPendingActivation(null);
      await refresh();
    },
  });
  const error =
    companies.error ??
    config.error ??
    issues.error ??
    holdings.error ??
    createIssue.error ??
    subscribe.error ??
    activate.error;
  const selectedSubscriptionIssue = issues.data?.find(
    (issue) => issue.id === pendingSubscription?.issue_id,
  );

  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("bondsTitle")}</h1>
        <p>{t("bondsDescription")}</p>
      </header>
      {message && (
        <p className="notice notice--success" role="status">
          {message}
        </p>
      )}
      <StateView
        loading={
          companies.isLoading ||
          config.isLoading ||
          issues.isLoading ||
          holdings.isLoading
        }
        error={error}
      >
        <div className="content-grid">
          <Panel title={t("bondCreateIssue")}>
            <StateView empty={!issueValues}>
              <form
                className="stack"
                onSubmit={issueForm.handleSubmit((value) =>
                  createIssue.mutate(value),
                )}
              >
                <Field
                  label={t("bondIssuer")}
                  error={issueForm.formState.errors.issuer_company_id?.message}
                >
                  <select {...issueForm.register("issuer_company_id")}>
                    {companies.data?.map((company) => (
                      <option key={company.id} value={company.id}>
                        {company.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field
                  label={t("bondSymbol")}
                  error={issueForm.formState.errors.symbol?.message}
                >
                  <input {...issueForm.register("symbol")} />
                </Field>
                <Field
                  label={t("bondTitle")}
                  error={issueForm.formState.errors.title?.message}
                >
                  <input {...issueForm.register("title")} />
                </Field>
                {(
                  [
                    ["face_value_cents", t("bondFaceValue")],
                    ["total_units", t("bondUnits")],
                    ["coupon_rate_bps", t("bondCouponRate")],
                    ["term_periods", t("bondTerm")],
                  ] as const
                ).map(([name, label]) => (
                  <Field
                    key={name}
                    label={label}
                    error={issueForm.formState.errors[name]?.message}
                  >
                    <input
                      type="number"
                      max={
                        name === "term_periods"
                          ? config.data?.max_term_periods
                          : undefined
                      }
                      {...issueForm.register(name, { valueAsNumber: true })}
                    />
                  </Field>
                ))}
                <button className="button" disabled={createIssue.isPending}>
                  {t("bondPublishIssue")}
                </button>
              </form>
            </StateView>
          </Panel>

          <Panel title={t("bondSubscribe")}>
            <StateView empty={!subscriptionValues}>
              <form
                className="stack"
                onSubmit={subscriptionForm.handleSubmit((value) =>
                  setPendingSubscription(value),
                )}
              >
                <Field
                  label={t("bondIssue")}
                  error={subscriptionForm.formState.errors.issue_id?.message}
                >
                  <select {...subscriptionForm.register("issue_id")}>
                    {offeringIssues?.map((issue) => (
                      <option key={issue.id} value={issue.id}>
                        {issue.symbol} · {issue.issuer_company_name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field
                  label={t("bondQuantity")}
                  error={subscriptionForm.formState.errors.quantity?.message}
                >
                  <input
                    type="number"
                    {...subscriptionForm.register("quantity", {
                      valueAsNumber: true,
                    })}
                  />
                </Field>
                <button className="button">
                  {t("bondReviewSubscription")}
                </button>
              </form>
            </StateView>
          </Panel>
        </div>

        <Panel title={t("bondMarket")}>
          <StateView empty={!issues.data?.length}>
            <div className="stack">
              {issues.data?.map((issue) => (
                <article className="subcard" key={issue.id}>
                  <div className="list-row">
                    <span>
                      <strong>
                        {issue.symbol} · {issue.title}
                      </strong>
                      <small>
                        {issue.issuer_company_name} ·{" "}
                        {formatCents(issue.face_value_cents, i18n.language)} ·{" "}
                        {formatNumber(
                          issue.coupon_rate_bps / 100,
                          i18n.language,
                        )}
                        %
                      </small>
                    </span>
                    <Status value={issue.status} />
                  </div>
                  <Progress
                    label={t("bondSoldProgress", {
                      sold: issue.sold_units,
                      total: issue.total_units,
                    })}
                    value={(issue.sold_units * 100) / issue.total_units}
                  />
                  <small>
                    {t("bondOfferingEnds", {
                      date: formatDate(issue.offering_ends_at, i18n.language),
                    })}
                  </small>
                  {issue.status === "offering" &&
                    issue.sold_units > 0 &&
                    ownedCompanyIds.has(issue.issuer_company_id) && (
                      <button
                        className="button button--small"
                        onClick={() => setPendingActivation(issue)}
                      >
                        {t("bondActivate")}
                      </button>
                    )}
                  {issue.default_reason && (
                    <p className="notice notice--warning">
                      {t("bondAbstractDefault", {
                        reason: issue.default_reason.replaceAll("_", " "),
                      })}
                    </p>
                  )}
                </article>
              ))}
            </div>
          </StateView>
        </Panel>

        <Panel title={t("bondPortfolio")}>
          <StateView empty={!holdings.data?.length}>
            <div className="stack">
              {holdings.data?.map((holding) => (
                <article className="subcard" key={holding.id}>
                  <div className="list-row">
                    <span>
                      <strong>
                        {holding.symbol} · {holding.quantity}{" "}
                        {t("bondUnitsLabel")}
                      </strong>
                      <small>
                        {holding.issuer_company_name} ·{" "}
                        {formatCents(
                          holding.face_value_cents * holding.quantity,
                          i18n.language,
                        )}
                      </small>
                    </span>
                    <Status value={holding.issue_status} />
                  </div>
                </article>
              ))}
            </div>
          </StateView>
        </Panel>
      </StateView>

      {pendingSubscription && selectedSubscriptionIssue && (
        <ConfirmDialog
          title={t("bondConfirmSubscription")}
          description={t("bondConfirmSubscriptionDescription", {
            quantity: pendingSubscription.quantity,
            symbol: selectedSubscriptionIssue.symbol,
            amount: formatCents(
              pendingSubscription.quantity *
                selectedSubscriptionIssue.face_value_cents,
              i18n.language,
            ),
          })}
          confirmLabel={t("bondSubscribe")}
          cancelLabel={t("cancel")}
          pending={subscribe.isPending}
          onCancel={() => setPendingSubscription(null)}
          onConfirm={() => subscribe.mutate(pendingSubscription)}
        />
      )}
      {pendingActivation && (
        <ConfirmDialog
          title={t("bondConfirmActivation")}
          description={t("bondConfirmActivationDescription", {
            symbol: pendingActivation.symbol,
            principal: formatCents(
              pendingActivation.face_value_cents * pendingActivation.sold_units,
              i18n.language,
            ),
          })}
          confirmLabel={t("bondActivate")}
          cancelLabel={t("cancel")}
          pending={activate.isPending}
          onCancel={() => setPendingActivation(null)}
          onConfirm={() => activate.mutate(pendingActivation)}
        />
      )}
    </div>
  );
}
