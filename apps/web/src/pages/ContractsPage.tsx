import { zodResolver } from "@hookform/resolvers/zod";
import { createIdempotencyKey } from "@shadowgrid/api-client";
import { translateGameValue } from "@shadowgrid/i18n";
import type {
  CommercialContract,
  Company,
  ContractBid,
  ContractTender,
} from "@shadowgrid/shared-types";
import {
  contractBidSchema,
  contractTenderSchema,
  type ContractBidInput,
  type ContractTenderInput,
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
import { formatCents, formatDate } from "../format";

interface PendingAward {
  tender: ContractTender;
  bid: ContractBid;
}

export function ContractsPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [message, setMessage] = useState("");
  const [awardTenderId, setAwardTenderId] = useState("");
  const [pendingAward, setPendingAward] = useState<PendingAward | null>(null);
  const companies = useQuery({
    queryKey: ["companies"],
    queryFn: () => client.get<Company[]>("/companies"),
  });
  const tenders = useQuery({
    queryKey: ["contract-tenders"],
    queryFn: () => client.get<ContractTender[]>("/contracts/tenders"),
  });
  const contracts = useQuery({
    queryKey: ["contracts"],
    queryFn: () => client.get<CommercialContract[]>("/contracts/me"),
  });
  const bids = useQuery({
    queryKey: ["contract-bids", awardTenderId],
    queryFn: () =>
      client.get<ContractBid[]>(`/contracts/tenders/${awardTenderId}/bids`),
    enabled: Boolean(awardTenderId),
  });
  const ownedCompanyIds = useMemo(
    () => new Set(companies.data?.map((company) => company.id) ?? []),
    [companies.data],
  );
  const openTenders = useMemo(
    () => tenders.data?.filter((tender) => tender.status === "open"),
    [tenders.data],
  );
  const tenderValues = useMemo<ContractTenderInput | undefined>(() => {
    const company = companies.data?.[0];
    if (!company) return undefined;
    return {
      issuer_company_id: company.id,
      contract_type: "supply",
      title: "",
      description: "",
      max_price_cents: 200_000,
      duration_periods: 2,
      capacity_units: 10,
      min_reputation_bps: 0,
      min_compliance_bps: 0,
      submission_minutes: 60,
    };
  }, [companies.data]);
  const bidValues = useMemo<ContractBidInput | undefined>(() => {
    const tender = openTenders?.find(
      (item) => !ownedCompanyIds.has(item.issuer_company_id),
    );
    const company = companies.data?.find(
      (item) => item.id !== tender?.issuer_company_id,
    );
    if (!tender || !company) return undefined;
    return {
      tender_id: tender.id,
      bidder_company_id: company.id,
      price_cents: tender.max_price_cents,
    };
  }, [companies.data, openTenders, ownedCompanyIds]);
  const tenderForm = useForm<ContractTenderInput>({
    resolver: zodResolver(contractTenderSchema),
    values: tenderValues,
  });
  const bidForm = useForm<ContractBidInput>({
    resolver: zodResolver(contractBidSchema),
    values: bidValues,
  });
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["contract-tenders"] }),
      queryClient.invalidateQueries({ queryKey: ["contract-bids"] }),
      queryClient.invalidateQueries({ queryKey: ["contracts"] }),
      queryClient.invalidateQueries({ queryKey: ["companies"] }),
    ]);
  };
  const createTender = useMutation({
    mutationFn: (value: ContractTenderInput) =>
      client.post<ContractTender>(
        "/contracts/tenders",
        value,
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setMessage(t("contractTenderCreated"));
      await refresh();
    },
  });
  const submitBid = useMutation({
    mutationFn: (value: ContractBidInput) =>
      client.post<ContractBid>(
        `/contracts/tenders/${value.tender_id}/bids`,
        {
          bidder_company_id: value.bidder_company_id,
          price_cents: value.price_cents,
        },
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setMessage(t("contractBidSubmitted"));
      await refresh();
    },
  });
  const awardBid = useMutation({
    mutationFn: (value: PendingAward) =>
      client.post<CommercialContract>(
        `/contracts/tenders/${value.tender.id}/award`,
        { bid_id: value.bid.id },
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setMessage(t("contractAwarded"));
      setPendingAward(null);
      setAwardTenderId("");
      await refresh();
    },
  });
  const error =
    companies.error ??
    tenders.error ??
    contracts.error ??
    bids.error ??
    createTender.error ??
    submitBid.error ??
    awardBid.error;

  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("contractsTitle")}</h1>
        <p>{t("contractsDescription")}</p>
      </header>
      {message && (
        <p className="notice notice--success" role="status">
          {message}
        </p>
      )}
      <StateView
        loading={
          companies.isLoading || tenders.isLoading || contracts.isLoading
        }
        error={error}
      >
        <div className="content-grid">
          <Panel title={t("contractCreateTender")}>
            <StateView empty={!companies.data?.length}>
              <form
                className="stack"
                onSubmit={tenderForm.handleSubmit((value) =>
                  createTender.mutate(value),
                )}
              >
                <Field
                  label={t("contractIssuer")}
                  error={tenderForm.formState.errors.issuer_company_id?.message}
                >
                  <select {...tenderForm.register("issuer_company_id")}>
                    {companies.data?.map((company) => (
                      <option key={company.id} value={company.id}>
                        {company.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field
                  label={t("contractType")}
                  error={tenderForm.formState.errors.contract_type?.message}
                >
                  <select {...tenderForm.register("contract_type")}>
                    <option value="supply">{t("contractSupply")}</option>
                    <option value="service">{t("contractService")}</option>
                  </select>
                </Field>
                <Field
                  label={t("contractTitle")}
                  error={tenderForm.formState.errors.title?.message}
                >
                  <input {...tenderForm.register("title")} />
                </Field>
                <Field
                  label={t("description")}
                  error={tenderForm.formState.errors.description?.message}
                >
                  <textarea {...tenderForm.register("description")} />
                </Field>
                {(
                  [
                    ["max_price_cents", t("contractMaxPrice")],
                    ["duration_periods", t("contractDurationPeriods")],
                    ["capacity_units", t("contractCapacity")],
                    ["min_reputation_bps", t("contractMinReputation")],
                    ["min_compliance_bps", t("contractMinCompliance")],
                    ["submission_minutes", t("contractSubmissionMinutes")],
                  ] as const
                ).map(([name, label]) => (
                  <Field
                    key={name}
                    label={label}
                    error={tenderForm.formState.errors[name]?.message}
                  >
                    <input
                      type="number"
                      {...tenderForm.register(name, { valueAsNumber: true })}
                    />
                  </Field>
                ))}
                <button className="button" disabled={createTender.isPending}>
                  {t("contractPublishTender")}
                </button>
              </form>
            </StateView>
          </Panel>

          <Panel title={t("contractSubmitBid")}>
            <StateView empty={!bidValues}>
              <form
                className="stack"
                onSubmit={bidForm.handleSubmit((value) =>
                  submitBid.mutate(value),
                )}
              >
                <Field
                  label={t("contractTender")}
                  error={bidForm.formState.errors.tender_id?.message}
                >
                  <select {...bidForm.register("tender_id")}>
                    {openTenders
                      ?.filter(
                        (tender) =>
                          !ownedCompanyIds.has(tender.issuer_company_id),
                      )
                      .map((tender) => (
                        <option key={tender.id} value={tender.id}>
                          {tender.title} · {tender.issuer_company_name}
                        </option>
                      ))}
                  </select>
                </Field>
                <Field
                  label={t("contractProvider")}
                  error={bidForm.formState.errors.bidder_company_id?.message}
                >
                  <select {...bidForm.register("bidder_company_id")}>
                    {companies.data?.map((company) => (
                      <option key={company.id} value={company.id}>
                        {company.name} · {company.capacity}{" "}
                        {t("contractCapacityUnits")}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field
                  label={t("contractBidPrice")}
                  error={bidForm.formState.errors.price_cents?.message}
                >
                  <input
                    type="number"
                    {...bidForm.register("price_cents", {
                      valueAsNumber: true,
                    })}
                  />
                </Field>
                <button className="button" disabled={submitBid.isPending}>
                  {t("contractSubmitBid")}
                </button>
              </form>
            </StateView>
          </Panel>
        </div>

        <Panel title={t("contractTenderFeed")}>
          <StateView empty={!tenders.data?.length}>
            <div className="stack">
              {tenders.data?.map((tender) => (
                <article className="subcard" key={tender.id}>
                  <div className="list-row">
                    <span>
                      <strong>{tender.title}</strong>
                      <small>
                        {tender.issuer_company_name} ·{" "}
                        {formatCents(tender.max_price_cents, i18n.language)} /{" "}
                        {t("contractPeriod")} · {tender.capacity_units}{" "}
                        {t("contractCapacityUnits")}
                      </small>
                    </span>
                    <Status value={tender.status} />
                  </div>
                  <p>{tender.description}</p>
                  <small>
                    {t("contractBids", { count: tender.bid_count })} ·{" "}
                    {t("contractCloses", {
                      date: formatDate(
                        tender.submission_ends_at,
                        i18n.language,
                      ),
                    })}
                  </small>
                  {tender.status === "open" &&
                    ownedCompanyIds.has(tender.issuer_company_id) && (
                      <button
                        className="button button--small"
                        onClick={() => setAwardTenderId(tender.id)}
                      >
                        {t("contractReviewBids")}
                      </button>
                    )}
                  {awardTenderId === tender.id && (
                    <StateView
                      loading={bids.isLoading}
                      empty={!bids.data?.length}
                    >
                      <div className="stack">
                        {bids.data?.map((bid) => (
                          <div className="list-row" key={bid.id}>
                            <span>
                              <strong>{bid.bidder_company_name}</strong>
                              <small>
                                {formatCents(bid.price_cents, i18n.language)} ·{" "}
                                {t("contractScore", {
                                  value: bid.score_points,
                                })}
                              </small>
                            </span>
                            <button
                              className="button button--small"
                              onClick={() => setPendingAward({ tender, bid })}
                            >
                              {t("contractAward")}
                            </button>
                          </div>
                        ))}
                      </div>
                    </StateView>
                  )}
                </article>
              ))}
            </div>
          </StateView>
        </Panel>

        <Panel title={t("contractActiveAndHistory")}>
          <StateView empty={!contracts.data?.length}>
            <div className="stack">
              {contracts.data?.map((contract) => (
                <div className="subcard" key={contract.id}>
                  <div className="list-row">
                    <span>
                      <strong>{contract.title}</strong>
                      <small>
                        {contract.issuer_company_name} →{" "}
                        {contract.provider_company_name} ·{" "}
                        {formatCents(
                          contract.price_cents_per_period,
                          i18n.language,
                        )}{" "}
                        / {t("contractPeriod")}
                      </small>
                    </span>
                    <Status value={contract.status} />
                  </div>
                  <Progress
                    label={t("contractSettlementProgress", {
                      settled: contract.periods_settled,
                      total: contract.duration_periods,
                    })}
                    value={
                      (contract.periods_settled * 100) /
                      contract.duration_periods
                    }
                  />
                  {contract.breach_reason && (
                    <p className="notice notice--warning">
                      {t("contractAbstractBreach", {
                        reason: translateGameValue(contract.breach_reason),
                      })}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </StateView>
        </Panel>
      </StateView>
      {pendingAward && (
        <ConfirmDialog
          title={t("contractConfirmAward")}
          description={t("contractConfirmAwardDescription", {
            company: pendingAward.bid.bidder_company_name,
            price: formatCents(pendingAward.bid.price_cents, i18n.language),
          })}
          confirmLabel={t("contractAward")}
          cancelLabel={t("cancel")}
          pending={awardBid.isPending}
          onCancel={() => setPendingAward(null)}
          onConfirm={() => awardBid.mutate(pendingAward)}
        />
      )}
    </div>
  );
}
