import { zodResolver } from "@hookform/resolvers/zod";
import { createIdempotencyKey } from "@shadowgrid/api-client";
import type {
  Company,
  CompanyLoan,
  LoanApplication,
  LoanConfig,
} from "@shadowgrid/shared-types";
import {
  loanApplicationSchema,
  type LoanApplicationInput,
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

export function FinancePage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [message, setMessage] = useState("");
  const [pendingOffer, setPendingOffer] = useState<LoanApplication | null>(
    null,
  );
  const companies = useQuery({
    queryKey: ["companies"],
    queryFn: () => client.get<Company[]>("/companies"),
  });
  const config = useQuery({
    queryKey: ["loan-config"],
    queryFn: () => client.get<LoanConfig>("/loans/config"),
  });
  const applications = useQuery({
    queryKey: ["loan-applications"],
    queryFn: () => client.get<LoanApplication[]>("/loans/applications/me"),
  });
  const loans = useQuery({
    queryKey: ["company-loans"],
    queryFn: () => client.get<CompanyLoan[]>("/loans/me"),
  });
  const initialValues = useMemo<LoanApplicationInput | undefined>(() => {
    const company = companies.data?.[0];
    if (!company) return undefined;
    return {
      company_id: company.id,
      requested_principal_cents: 500_000,
      term_periods: 3,
      collateral_score_bps: 5_000,
      purpose: "",
    };
  }, [companies.data]);
  const form = useForm<LoanApplicationInput>({
    resolver: zodResolver(loanApplicationSchema),
    values: initialValues,
  });
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["companies"] }),
      queryClient.invalidateQueries({ queryKey: ["loan-applications"] }),
      queryClient.invalidateQueries({ queryKey: ["company-loans"] }),
    ]);
  };
  const createApplication = useMutation({
    mutationFn: (value: LoanApplicationInput) =>
      client.post<LoanApplication>(
        "/loans/applications",
        value,
        createIdempotencyKey(),
      ),
    onSuccess: async (application) => {
      setMessage(
        t(
          application.status === "offered"
            ? "loanOfferCreated"
            : "loanApplicationRejected",
        ),
      );
      await refresh();
    },
  });
  const acceptOffer = useMutation({
    mutationFn: (application: LoanApplication) =>
      client.post<CompanyLoan>(
        `/loans/applications/${application.id}/accept`,
        undefined,
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setMessage(t("loanDisbursed"));
      setPendingOffer(null);
      await refresh();
    },
  });
  const error =
    companies.error ??
    config.error ??
    applications.error ??
    loans.error ??
    createApplication.error ??
    acceptOffer.error;

  return (
    <div className="page">
      <header className="page-header">
        <h1>{t("financeTitle")}</h1>
        <p>{t("loanDescription")}</p>
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
          applications.isLoading ||
          loans.isLoading
        }
        error={error}
      >
        <div className="content-grid">
          <Panel title={t("loanApply")}>
            <StateView empty={!initialValues}>
              <form
                className="stack"
                onSubmit={form.handleSubmit((value) =>
                  createApplication.mutate(value),
                )}
              >
                <Field
                  label={t("loanCompany")}
                  error={form.formState.errors.company_id?.message}
                >
                  <select {...form.register("company_id")}>
                    {companies.data?.map((company) => (
                      <option key={company.id} value={company.id}>
                        {company.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field
                  label={t("loanPrincipal")}
                  error={
                    form.formState.errors.requested_principal_cents?.message
                  }
                >
                  <input
                    type="number"
                    {...form.register("requested_principal_cents", {
                      valueAsNumber: true,
                    })}
                  />
                </Field>
                <Field
                  label={t("loanTerm")}
                  error={form.formState.errors.term_periods?.message}
                >
                  <input
                    type="number"
                    max={config.data?.max_term_periods}
                    {...form.register("term_periods", { valueAsNumber: true })}
                  />
                </Field>
                <Field
                  label={t("loanCollateral")}
                  error={form.formState.errors.collateral_score_bps?.message}
                >
                  <input
                    type="number"
                    {...form.register("collateral_score_bps", {
                      valueAsNumber: true,
                    })}
                  />
                </Field>
                <Field
                  label={t("loanPurpose")}
                  error={form.formState.errors.purpose?.message}
                >
                  <textarea {...form.register("purpose")} />
                </Field>
                <button
                  className="button"
                  disabled={createApplication.isPending}
                >
                  {t("loanRequestOffer")}
                </button>
              </form>
            </StateView>
          </Panel>

          <Panel title={t("loanApplications")}>
            <StateView empty={!applications.data?.length}>
              <div className="stack">
                {applications.data?.map((application) => (
                  <article className="subcard" key={application.id}>
                    <div className="list-row">
                      <span>
                        <strong>{application.company_name}</strong>
                        <small>
                          {formatCents(
                            application.requested_principal_cents,
                            i18n.language,
                          )}{" "}
                          · {application.term_periods} {t("loanPeriods")}
                        </small>
                      </span>
                      <Status value={application.status} />
                    </div>
                    {application.status === "offered" &&
                      application.offered_interest_rate_bps !== null &&
                      application.offered_installment_cents !== null &&
                      application.offer_expires_at !== null && (
                        <>
                          <p>
                            {t("loanOfferTerms", {
                              rate: formatNumber(
                                application.offered_interest_rate_bps / 100,
                                i18n.language,
                              ),
                              installment: formatCents(
                                application.offered_installment_cents,
                                i18n.language,
                              ),
                            })}
                          </p>
                          <small>
                            {t("loanOfferExpires", {
                              date: formatDate(
                                application.offer_expires_at,
                                i18n.language,
                              ),
                            })}
                          </small>
                          <button
                            className="button button--small"
                            onClick={() => setPendingOffer(application)}
                          >
                            {t("loanAcceptOffer")}
                          </button>
                        </>
                      )}
                    {application.rejection_reason && (
                      <p className="notice notice--warning">
                        {t("loanAbstractDecision", {
                          reason: application.rejection_reason.replaceAll(
                            "_",
                            " ",
                          ),
                        })}
                      </p>
                    )}
                  </article>
                ))}
              </div>
            </StateView>
          </Panel>
        </div>

        <Panel title={t("loanPortfolio")}>
          <StateView empty={!loans.data?.length}>
            <div className="stack">
              {loans.data?.map((loan) => (
                <article className="subcard" key={loan.id}>
                  <div className="list-row">
                    <span>
                      <strong>{loan.company_name}</strong>
                      <small>
                        {formatCents(loan.principal_cents, i18n.language)} ·{" "}
                        {formatNumber(
                          loan.interest_rate_bps / 100,
                          i18n.language,
                        )}
                        %
                      </small>
                    </span>
                    <Status value={loan.status} />
                  </div>
                  <Progress
                    label={t("loanPaymentProgress", {
                      paid: loan.payments_made,
                      total: loan.term_periods,
                    })}
                    value={(loan.payments_made * 100) / loan.term_periods}
                  />
                  <p>
                    {t("loanOutstanding", {
                      amount: formatCents(
                        loan.outstanding_principal_cents +
                          loan.outstanding_interest_cents,
                        i18n.language,
                      ),
                    })}
                  </p>
                  {loan.default_reason && (
                    <p className="notice notice--warning">
                      {t("loanAbstractDefault", {
                        reason: loan.default_reason.replaceAll("_", " "),
                      })}
                    </p>
                  )}
                </article>
              ))}
            </div>
          </StateView>
        </Panel>
      </StateView>
      {pendingOffer && (
        <ConfirmDialog
          title={t("loanConfirmAccept")}
          description={t("loanConfirmAcceptDescription", {
            principal: formatCents(
              pendingOffer.requested_principal_cents,
              i18n.language,
            ),
            total: formatCents(
              pendingOffer.offered_total_repayment_cents ?? 0,
              i18n.language,
            ),
          })}
          confirmLabel={t("loanAcceptOffer")}
          cancelLabel={t("cancel")}
          pending={acceptOffer.isPending}
          onCancel={() => setPendingOffer(null)}
          onConfirm={() => acceptOffer.mutate(pendingOffer)}
        />
      )}
    </div>
  );
}
