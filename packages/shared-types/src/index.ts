export type ISODateTime = string;

export interface User {
  id: string;
  email: string;
  display_name: string;
  locale: string;
  email_verified: boolean;
  is_admin: boolean;
  is_moderator: boolean;
}

export interface World {
  id: string;
  slug: string;
  name: string;
  status: string;
  starts_at: ISODateTime;
  ends_at: ISODateTime;
  season_number: number;
}

export interface Resources {
  cash: number;
  capital: number;
  influence: number;
  intelligence: number;
  logistics_capacity: number;
  personnel_capacity: number;
  version: number;
}

export interface Profile {
  id: string;
  world_id: string;
  city_id: string | null;
  codename: string;
  archetype: string;
  home_district_id: string | null;
  tutorial_step: number;
  loyalty: number;
  legitimacy: number;
  fear: number;
  investigation_pressure: number;
  stress: number;
  stability: number;
  operation_slots: number;
  protected_until: ISODateTime;
  recovery_until: ISODateTime | null;
  resources: Resources;
}

export interface District {
  id: string;
  slug: string;
  name: string;
  prosperity: number;
  employment: number;
  safety: number;
  authority_presence: number;
  digital_infrastructure: number;
  property_value: number;
  public_trust: number;
  media_attention: number;
  economic_activity: number;
  social_stability: number;
  map_x: number;
  map_y: number;
  map_points: string;
  influence: Record<string, number>;
}

export interface Business {
  id: string;
  district_id: string;
  business_type: string;
  name: string;
  level: number;
  revenue: number;
  operating_cost: number;
  personnel_need: number;
  logistics_need: number;
  status: string;
  compliance: number;
  reputation: number;
  market_share: number;
  risk: number;
  upgrade_finishes_at: ISODateTime | null;
}

export interface Company {
  id: string;
  world_id: string;
  founder_profile_id: string;
  district_id: string;
  industry: string;
  name: string;
  status: string;
  account_balance_cents: number;
  enterprise_value_cents: number;
  revenue_cents: number;
  cost_cents: number;
  profit_cents: number;
  debt_cents: number;
  employees: number;
  capacity: number;
  quality: number;
  market_share_bps: number;
  reputation_bps: number;
  compliance_bps: number;
  innovation_bps: number;
  risk_bps: number;
  investigation_pressure_bps: number;
  is_local_simulation: boolean;
  version: number;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface CompanyOwnership {
  id: string;
  company_id: string;
  owner_profile_id: string;
  ownership_bps: number;
  created_at: ISODateTime;
}

export interface CompanyInvestment {
  id: string;
  company_id: string;
  investor_profile_id: string;
  investment_type: string;
  amount_cents: number;
  metric_before: number;
  metric_after: number;
  created_at: ISODateTime;
}

export interface CompanyMetric {
  id: string;
  company_id: string;
  version: number;
  reason: string;
  reference_id: string;
  enterprise_value_cents: number;
  account_balance_cents: number;
  revenue_cents: number;
  cost_cents: number;
  profit_cents: number;
  capacity: number;
  quality: number;
  compliance_bps: number;
  innovation_bps: number;
  created_at: ISODateTime;
}

export interface CompanyDetail extends Company {
  ownership: CompanyOwnership[];
  investments: CompanyInvestment[];
  metrics_history: CompanyMetric[];
}

export interface ExchangeConfiguration {
  min_enterprise_value_cents: number;
  profitable_periods: number;
  min_compliance_bps: number;
  min_employees: number;
  max_investigation_pressure_bps: number;
  ipo_fee_cents: number;
  order_rate_limit_per_minute: number;
  max_price_deviation_bps: number;
}

export interface IpoEligibility {
  eligible: boolean;
  reasons: string[];
  metrics: Record<string, number>;
}

export interface ExchangeListing {
  id: string;
  world_id: string;
  company_id: string;
  company_name: string;
  company_industry: string;
  symbol: string;
  status: string;
  total_shares: number;
  offered_shares: number;
  initial_price_cents: number;
  last_price_cents: number;
  enterprise_value_cents: number;
  profit_cents: number;
  debt_cents: number;
  ipo_fee_cents: number;
  listed_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface ExchangeOrder {
  id: string;
  listing_id: string;
  share_class_id: string;
  side: "buy" | "sell";
  order_type: "market" | "limit" | "ipo";
  limit_price_cents: number | null;
  original_quantity: number;
  remaining_quantity: number;
  reserved_cash_cents: number;
  reserved_shares: number;
  status: string;
  expires_at: ISODateTime | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface ExchangeOrderBook {
  buys: ExchangeOrder[];
  sells: ExchangeOrder[];
}

export interface ExchangeTrade {
  id: string;
  listing_id: string;
  share_class_id: string;
  buy_order_id: string;
  sell_order_id: string;
  buyer_profile_id: string;
  seller_profile_id: string | null;
  seller_company_id: string | null;
  quantity: number;
  price_cents: number;
  gross_cents: number;
  executed_at: ISODateTime;
}

export interface PriceSnapshot {
  id: string;
  listing_id: string;
  trade_id: string;
  price_cents: number;
  volume: number;
  captured_at: ISODateTime;
}

export interface PortfolioItem {
  holding_id: string;
  listing_id: string;
  company_id: string;
  company_name: string;
  symbol: string;
  share_class: string;
  quantity: number;
  reserved_quantity: number;
  available_quantity: number;
  average_cost_cents: number;
  last_price_cents: number;
  market_value_cents: number;
  voting_rights: number;
}

export interface Shareholder {
  holding_id: string;
  profile_id: string;
  codename: string;
  quantity: number;
  ownership_bps: number;
  voting_rights: number;
}

export interface DividendDeclaration {
  id: string;
  listing_id: string;
  share_class_id: string;
  declared_by_profile_id: string;
  per_share_cents: number;
  total_paid_cents: number;
  eligible_shares: number;
  status: string;
  snapshot_at: ISODateTime;
  paid_at: ISODateTime;
  created_at: ISODateTime;
}

export interface EconomyTick {
  id: string;
  world_id: string;
  period_key: string;
  period_start: ISODateTime;
  period_end: ISODateTime;
  status: string;
  company_count: number;
  market_count: number;
  started_at: ISODateTime;
  completed_at: ISODateTime | null;
}

export interface EconomyStatus {
  last_tick: EconomyTick | null;
  next_scheduled_at: ISODateTime;
}

export interface CitySectorMarket {
  id: string;
  world_id: string;
  city_id: string;
  industry: string;
  demand_units: number;
  unit_revenue_cents: number;
  variable_cost_per_unit_cents: number;
  fixed_cost_cents: number;
  version: number;
}

export interface CompanyEconomyReport {
  id: string;
  tick_id: string;
  market_report_id: string;
  company_id: string;
  settlement_transaction_id: string | null;
  attractiveness_points: number;
  allocated_units: number;
  market_share_bps: number;
  revenue_cents: number;
  cost_cents: number;
  profit_cents: number;
  cash_delta_cents: number;
  debt_delta_cents: number;
  enterprise_value_before_cents: number;
  enterprise_value_after_cents: number;
  inputs_json: Record<string, number>;
  modifiers_json: Record<string, number>;
  created_at: ISODateTime;
}

export interface MarketEconomyReport {
  id: string;
  tick_id: string;
  market_id: string;
  demand_units: number;
  allocated_units: number;
  unfilled_units: number;
  allocated_share_bps: number;
  company_count: number;
  total_revenue_cents: number;
  total_cost_cents: number;
  total_profit_cents: number;
  inputs_json: Record<string, number>;
  created_at: ISODateTime;
}

export interface Specialist {
  id: string;
  name: string;
  role: string;
  level: number;
  energy: number;
  experience_points: number;
  skills_json: Record<string, number>;
  competence: number;
  loyalty: number;
  ambition: number;
  stress: number;
  exposure: number;
  salary: number;
  salary_cents: number;
  status: string;
  employer_company_id: string | null;
  assigned_operation_id: string | null;
  cooldown_until: ISODateTime | null;
  hired_at: ISODateTime | null;
}

export interface SpecialistMarketCandidate {
  id: string;
  world_id: string;
  city_id: string;
  market_cycle_key: string;
  role: string;
  name: string;
  level: number;
  salary_cents: number;
  loyalty: number;
  energy: number;
  skills_json: Record<string, number>;
  status: string;
  available_until: ISODateTime;
}

export interface SpecialistEffects {
  active_specialists: number;
  capacity_bonus_units: number;
  revenue_bonus_bps: number;
  cost_reduction_bps: number;
  attractiveness_bonus_points: number;
}

export interface SpecialistPayrollReport {
  id: string;
  payroll_tick_id: string;
  specialist_id: string;
  company_id: string;
  transaction_id: string | null;
  salary_due_cents: number;
  salary_paid_cents: number;
  unpaid_cents: number;
  loyalty_before: number;
  loyalty_after: number;
  energy_before: number;
  energy_after: number;
  level_before: number;
  level_after: number;
  created_at: ISODateTime;
}

export interface AiProfile {
  id: string;
  world_id: string;
  city_id: string | null;
  codename: string;
  is_local_ai: boolean;
  ai_strategy: string | null;
  ai_paused: boolean;
  ai_seed: number | null;
}

export interface Operation {
  id: string;
  operation_type: string;
  district_id: string;
  specialist_id: string;
  target: string;
  budget: number;
  intelligence_spend: number;
  risk_posture: string;
  secrecy: number;
  status: string;
  result: string | null;
  outcome_json: Record<string, unknown> | null;
  started_at: ISODateTime;
  finishes_at: ISODateTime;
  resolved_at: ISODateTime | null;
}

export interface Organization {
  id: string;
  world_id: string;
  city_id: string | null;
  name: string;
  tag: string;
  archetype: string;
  description: string;
  governance_model: string;
  stability: number;
  reputation: number;
  investigation_pressure: number;
  treasury_cash: number;
  treasury_capital: number;
  member_limit: number;
  my_role: string | null;
  member_count: number;
}

export interface Cartel {
  id: string;
  world_id: string;
  city_id: string | null;
  name: string;
  tag: string;
  archetype: string;
  description: string;
  governance_model: string;
  stability: number;
  reputation: number;
  investigation_pressure: number;
  approval_threshold_cents: number;
  single_spend_limit_cents: number;
  status: string;
  member_limit: number;
  member_count: number;
  treasury_balance_cents: number;
  my_role: string | null;
  my_permissions: string[];
}

export interface CartelMember {
  profile_id: string;
  codename: string;
  role: string;
  status: string;
  joined_at: string;
}

export interface CartelInvitation {
  id: string;
  organization_id: string;
  email: string;
  status: string;
  expires_at: string;
  created_at: string;
  cartel_name: string;
  cartel_tag: string;
}

export interface CartelTreasury {
  cartel_id: string;
  balance_cents: number;
  reserved_cents: number;
  approval_threshold_cents: number;
  single_spend_limit_cents: number;
}

export interface CartelExpense {
  id: string;
  organization_id: string;
  requested_by_profile_id: string;
  approved_by_profile_id: string | null;
  amount_cents: number;
  purpose: string;
  requires_approval: boolean;
  status: string;
  transaction_id: string | null;
  requested_at: string;
  resolved_at: string | null;
}

export interface CartelProject {
  id: string;
  organization_id: string;
  district_id: string;
  project_type: string;
  title: string;
  status: string;
  required_cash_cents: number;
  required_influence: number;
  required_intelligence: number;
  contributed_cash_cents: number;
  contributed_influence: number;
  contributed_intelligence: number;
  influence_kind: string;
  influence_reward: number;
  starts_at: string;
  ends_at: string;
  completed_at: string | null;
  progress_bps: number;
}

export interface CartelInfluenceEntry {
  cartel_id: string;
  cartel_name: string;
  kind: string;
  points: number;
}

export interface DistrictCartelInfluence {
  district_id: string;
  district_name: string;
  status: string;
  controlling_cartel_id: string | null;
  controlling_cartel_name: string | null;
  top_points: number;
  entries: CartelInfluenceEntry[];
}

export interface CartelRanking {
  rank: number;
  cartel_id: string;
  name: string;
  tag: string;
  season_number: number;
  score: number;
  treasury_cents: number;
  member_count: number;
  completed_projects: number;
  influence: number;
}

export interface CartelActivity {
  id: string;
  action: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface City {
  id: string;
  world_id: string;
  slug: string;
  name: string;
  region_key: string;
  instance_key: string;
  status: string;
  max_players: number;
  active_players: number;
  active_cartels: number;
}

export interface PvpTarget {
  profile_id: string;
  codename: string;
  city_id: string;
  cartel_id: string | null;
  cartel_name: string | null;
  public_reputation: Record<string, number>;
  estimated_strength: string;
  known_businesses: number;
  known_district_presence: string[];
  last_public_activity: ISODateTime;
  treaty_status: string | null;
  protection_status: string;
  recommendation: string;
}

export interface PvpPreview {
  defender_profile_id: string;
  operation_type: string;
  estimated_cost_cash: number;
  estimated_cost_influence: number;
  estimated_minutes: number;
  estimated_success_band: string;
  repetition_multiplier: number;
  reward_multiplier: number;
  protection_status: string;
  treaty_status: string | null;
  can_launch: boolean;
  reasons: string[];
}

export interface PvpOperation {
  id: string;
  world_id: string;
  city_id: string;
  attacker_profile_id: string;
  attacker_cartel_id: string | null;
  defender_profile_id: string;
  defender_cartel_id: string | null;
  operation_type: string;
  district_id: string | null;
  risk_posture: string;
  status: string;
  starts_at: ISODateTime;
  response_deadline_at: ISODateTime;
  resolves_at: ISODateTime;
  resolved_at: ISODateTime | null;
  result_payload: Record<string, unknown> | null;
  my_side: string;
  defense_submitted: boolean;
  my_report_id: string | null;
}

export interface PvpReport {
  id: string;
  operation_id: string;
  profile_id: string;
  perspective: string;
  summary: string;
  confidence: number;
  details_json: Record<string, unknown>;
  created_at: ISODateTime;
}

export interface TerritoryClaim {
  id: string;
  district_id: string;
  cartel_id: string;
  status: string;
  claim_strength: number;
  visibility: number;
  expires_at: ISODateTime;
  version: number;
}

export interface TerritoryControlPoint {
  id: string;
  point_type: string;
  controlling_cartel_id: string | null;
  control_value: number;
  status: string;
  version: number;
}

export interface Territory {
  district_id: string;
  district_name: string;
  status: string;
  controlling_cartel_id: string | null;
  active_claims: TerritoryClaim[];
  control_points: TerritoryControlPoint[];
}

export interface CartelWar {
  id: string;
  world_id: string;
  attacker_cartel_id: string;
  defender_cartel_id: string;
  war_type: string;
  war_status: string;
  city_id: string | null;
  objective_config: Record<string, unknown>;
  rules_config: Record<string, unknown>;
  declaration_reason: string;
  preparation_starts_at: ISODateTime | null;
  active_starts_at: ISODateTime | null;
  active_ends_at: ISODateTime | null;
  aftermath_ends_at: ISODateTime | null;
  attacker_score: number;
  defender_score: number;
  winner_cartel_id: string | null;
  resolution_type: string | null;
  my_cartel_id: string | null;
  my_side: string | null;
}

export interface Alliance {
  id: string;
  world_id: string;
  name: string;
  tag: string;
  charter: string;
  governance_model: string;
  trust_score: number;
  member_limit: number;
  status: string;
  member_count: number;
  my_cartel_id: string | null;
  my_role: string | null;
}

export interface ChatChannel {
  id: string;
  channel_type: string;
  scope_id: string;
  name: string;
  moderated: boolean;
  status: string;
}

export interface ChatMessage {
  id: string;
  channel_id: string;
  sender_profile_id: string;
  body: string;
  moderation_state: string;
  created_at: ISODateTime;
}

export interface DirectMessage {
  id: string;
  sender_profile_id: string;
  recipient_profile_id: string;
  body: string;
  status: string;
  read_at: ISODateTime | null;
  created_at: ISODateTime;
}

export interface MarketOffer {
  id: string;
  city_id: string;
  seller_profile_id: string;
  resource_type: string;
  amount: number;
  unit_price: number;
  status: string;
  expires_at: ISODateTime;
  created_at: ISODateTime;
}

export interface IntelReport {
  id: string;
  title: string;
  summary: string;
  target_type: string;
  target_id: string;
  visible_confidence: number;
  source: string;
  observed_at: ISODateTime;
  expires_at: ISODateTime;
  status: string;
}

export interface IntelligenceOperation {
  id: string;
  target_profile_id: string;
  specialist_id: string;
  information_type: "public" | "analyzed" | "covert";
  category: string;
  cost_cash_cents: number;
  cost_intelligence: number;
  success_chance_bps: number;
  detection_chance_bps: number;
  outcome: "success" | "partial" | "failure";
  detected: boolean;
  investigation_pressure_delta: number;
  report_id: string | null;
  cooldown_until: ISODateTime;
  created_at: ISODateTime;
}

export interface IntelligenceReport {
  id: string;
  owner_profile_id: string;
  target_type: string;
  target_id: string;
  information_type: "public" | "analyzed" | "covert";
  category: string;
  statement: string;
  confidence_bps: number;
  source_category: string;
  source_report_id: string | null;
  tradable: boolean;
  observed_at: ISODateTime;
  expires_at: ISODateTime;
  created_at: ISODateTime;
  is_expired: boolean;
  age_seconds: number;
}

export interface IntelligenceOffer {
  id: string;
  report_id: string;
  seller_profile_id: string;
  buyer_profile_id: string | null;
  purchased_report_id: string | null;
  price_cents: number;
  status: "open" | "sold" | "cancelled" | "expired";
  expires_at: ISODateTime;
  sold_at: ISODateTime | null;
  created_at: ISODateTime;
  category: string;
  target_type: string;
  target_id: string;
  confidence_bps: number;
}

export interface StrategicAction {
  id: string;
  target_profile_id: string;
  specialist_id: string;
  action_type: string;
  target_type: string;
  target_id: string;
  cost_cash_cents: number;
  cost_intelligence: number;
  success_chance_bps: number;
  detection_chance_bps: number;
  outcome: "success" | "partial" | "failure";
  detected: boolean;
  investigation_pressure_delta: number;
  effect_id: string | null;
  cooldown_until: ISODateTime;
  created_at: ISODateTime;
}

export interface StrategicEffect {
  id: string;
  effect_type: string;
  target_type: string;
  target_id: string;
  magnitude: number;
  starts_at: ISODateTime;
  ends_at: ISODateTime;
}

export interface WorldEventDefinition {
  id: string;
  event_key: string;
  version: number;
  title: string;
  description: string;
  default_scope_type: "world" | "city" | "district" | "industry" | "company";
  default_duration_minutes: number;
  effect_config_json: Record<string, number>;
  enabled: boolean;
  created_at: ISODateTime;
}

export interface WorldEventInstance {
  id: string;
  world_id: string;
  definition_id: string;
  event_key: string;
  template_version: number;
  title: string;
  description: string;
  status: "scheduled" | "active" | "ended" | "cancelled";
  scope_type: string;
  scope_id: string;
  effect_config_json: Record<string, number>;
  starts_at: ISODateTime;
  ends_at: ISODateTime;
  activated_at: ISODateTime | null;
  ended_at: ISODateTime | null;
  end_reason: string | null;
  created_at: ISODateTime;
}

export interface WorldEventPreview {
  definition_id: string;
  event_key: string;
  template_version: number;
  title: string;
  description: string;
  scope_type: string;
  scope_id: string;
  starts_at: ISODateTime;
  ends_at: ISODateTime;
  effect_config: Record<string, number>;
  affected_companies: number;
}

export type SeasonPhase =
  | "setup"
  | "early"
  | "mid"
  | "late"
  | "scoring"
  | "archived";

export interface SeasonState {
  id: string;
  world_id: string;
  template_id: string;
  season_number: number;
  name: string;
  phase: SeasonPhase;
  status: "active" | "scoring" | "archived";
  goals_json: Array<Record<string, string | number>>;
  scoring_categories_json: string[];
  phase_schedule_json: Array<{ phase: SeasonPhase; ends_at: ISODateTime }>;
  starting_cash_cents: number;
  starts_at: ISODateTime;
  ends_at: ISODateTime;
  phase_changed_at: ISODateTime;
  scoring_started_at: ISODateTime | null;
  closed_at: ISODateTime | null;
  archived_at: ISODateTime | null;
  created_at: ISODateTime;
  phase_ends_at: ISODateTime;
  remaining_seconds: number;
}

export interface SeasonScore {
  category: string;
  entity_type: string;
  entity_id: string;
  entity_name: string;
  score_value: number;
  rank: number;
  tied: boolean;
  metrics_json: Record<string, string | number>;
  captured_at: ISODateTime | null;
}

export interface HallOfFameEntry {
  id: string;
  season_id: string;
  season_number: number;
  category: string;
  entity_type: string;
  entity_id: string;
  entity_name: string;
  score_value: number;
  rank: number;
  tied: boolean;
  metrics_json: Record<string, string | number>;
  awarded_at: ISODateTime;
}

export interface AccountReward {
  id: string;
  season_id: string;
  reward_type: "achievement" | "title" | "cosmetic";
  reward_key: string;
  label: string;
  metadata_json: Record<string, string | number | boolean>;
  awarded_at: ISODateTime;
}

export interface SeasonTemplate {
  id: string;
  template_key: string;
  version: number;
  name: string;
  duration_minutes: number;
  phase_weights_json: Record<string, number>;
  goals_json: Array<Record<string, string | number>>;
  scoring_categories_json: string[];
  starting_cash_cents: number;
  enabled: boolean;
  created_at: ISODateTime;
}

export interface ContractTender {
  id: string;
  world_id: string;
  issuer_company_id: string;
  issuer_company_name: string;
  created_by_profile_id: string;
  contract_type: "supply" | "service";
  title: string;
  description: string;
  max_price_cents: number;
  duration_periods: number;
  capacity_units: number;
  min_reputation_bps: number;
  min_compliance_bps: number;
  status: "open" | "awarded" | "cancelled" | "expired";
  submission_ends_at: ISODateTime;
  awarded_at: ISODateTime | null;
  created_at: ISODateTime;
  bid_count: number;
}

export interface ContractBid {
  id: string;
  tender_id: string;
  bidder_company_id: string;
  bidder_company_name: string;
  submitted_by_profile_id: string;
  price_cents: number;
  capacity_units: number;
  score_points: number;
  score_breakdown_json: Record<string, number>;
  status: "submitted" | "won" | "lost" | "withdrawn";
  created_at: ISODateTime;
}

export interface CommercialContract {
  id: string;
  world_id: string;
  tender_id: string;
  bid_id: string;
  issuer_company_id: string;
  issuer_company_name: string;
  provider_company_id: string;
  provider_company_name: string;
  contract_type: "supply" | "service";
  title: string;
  price_cents_per_period: number;
  duration_periods: number;
  periods_settled: number;
  reserved_capacity_units: number;
  reputation_reward_bps: number;
  status: "active" | "completed" | "breached" | "cancelled";
  starts_at: ISODateTime;
  ends_at: ISODateTime;
  next_settlement_at: ISODateTime;
  completed_at: ISODateTime | null;
  breached_at: ISODateTime | null;
  breach_reason: string | null;
  created_at: ISODateTime;
}

export interface ContractSettlement {
  id: string;
  contract_id: string;
  period_number: number;
  amount_cents: number;
  status: "paid" | "defaulted";
  transaction_id: string | null;
  input_snapshot_json: Record<string, number>;
  settled_at: ISODateTime;
}

export interface LoanApplication {
  id: string;
  world_id: string;
  company_id: string;
  company_name: string;
  applicant_profile_id: string;
  requested_principal_cents: number;
  term_periods: number;
  collateral_score_bps: number;
  purpose: string;
  offered_interest_rate_bps: number | null;
  offered_installment_cents: number | null;
  offered_total_repayment_cents: number | null;
  status: "offered" | "rejected" | "accepted" | "cancelled";
  rejection_reason: string | null;
  risk_snapshot_json: Record<string, number>;
  offer_expires_at: ISODateTime | null;
  accepted_at: ISODateTime | null;
  cancelled_at: ISODateTime | null;
  created_at: ISODateTime;
}

export interface CompanyLoan {
  id: string;
  world_id: string;
  application_id: string;
  company_id: string;
  company_name: string;
  borrower_profile_id: string;
  principal_cents: number;
  interest_rate_bps: number;
  total_interest_cents: number;
  total_repayment_cents: number;
  scheduled_installment_cents: number;
  term_periods: number;
  payments_made: number;
  outstanding_principal_cents: number;
  outstanding_interest_cents: number;
  collateral_score_bps: number;
  status: "active" | "repaid" | "defaulted" | "cancelled";
  default_reason: string | null;
  disbursement_transaction_id: string;
  starts_at: ISODateTime;
  ends_at: ISODateTime;
  next_payment_at: ISODateTime;
  repaid_at: ISODateTime | null;
  defaulted_at: ISODateTime | null;
  cancelled_at: ISODateTime | null;
  created_at: ISODateTime;
}

export interface LoanPayment {
  id: string;
  loan_id: string;
  period_number: number;
  amount_cents: number;
  principal_cents: number;
  interest_cents: number;
  status: "paid" | "defaulted";
  transaction_id: string | null;
  input_snapshot_json: Record<string, number>;
  paid_at: ISODateTime;
}

export interface LoanConfig {
  payment_interval_minutes: number;
  offer_valid_minutes: number;
  max_principal_cents: number;
  max_term_periods: number;
  min_interest_rate_bps: number;
  max_interest_rate_bps: number;
  default_reputation_penalty_bps: number;
  default_investigation_penalty_bps: number;
}

export interface BondIssue {
  id: string;
  world_id: string;
  issuer_company_id: string;
  issuer_company_name: string;
  created_by_profile_id: string;
  symbol: string;
  title: string;
  face_value_cents: number;
  total_units: number;
  sold_units: number;
  coupon_rate_bps: number;
  term_periods: number;
  coupons_paid: number;
  status: "offering" | "active" | "repaid" | "defaulted" | "cancelled";
  default_reason: string | null;
  offering_ends_at: ISODateTime;
  starts_at: ISODateTime | null;
  ends_at: ISODateTime | null;
  next_coupon_at: ISODateTime | null;
  activated_at: ISODateTime | null;
  repaid_at: ISODateTime | null;
  defaulted_at: ISODateTime | null;
  cancelled_at: ISODateTime | null;
  created_at: ISODateTime;
  holder_count: number;
}

export interface BondSubscription {
  id: string;
  issue_id: string;
  subscriber_profile_id: string;
  quantity: number;
  amount_cents: number;
  transaction_id: string;
  created_at: ISODateTime;
}

export interface BondHolding {
  id: string;
  issue_id: string;
  symbol: string;
  title: string;
  issuer_company_name: string;
  profile_id: string;
  quantity: number;
  face_value_cents: number;
  coupon_rate_bps: number;
  issue_status: string;
  acquired_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface BondSettlement {
  id: string;
  issue_id: string;
  period_number: number;
  profile_id: string;
  payment_type: "coupon" | "redemption";
  quantity: number;
  amount_cents: number;
  status: "paid" | "defaulted";
  transaction_id: string | null;
  input_snapshot_json: Record<string, number>;
  settled_at: ISODateTime;
}

export interface BondConfig {
  coupon_interval_minutes: number;
  offering_minutes: number;
  max_principal_cents: number;
  max_term_periods: number;
  default_reputation_penalty_bps: number;
  default_investigation_penalty_bps: number;
}

export interface RealEstateConfig {
  index_interval_minutes: number;
  lease_interval_minutes: number;
  max_lease_periods: number;
  headquarters_upgrade_base_cost_cents: number;
}

export interface RealEstateIndex {
  id: string;
  world_id: string;
  city_id: string;
  city_name: string;
  district_id: string;
  district_name: string;
  price_index_bps: number;
  rent_index_bps: number;
  demand_bps: number;
  safety_score: number;
  infrastructure_score: number;
  economic_score: number;
  cartel_control_points: number;
  event_multiplier_bps: number;
  version: number;
  updated_at: ISODateTime;
}

export interface RealEstateProperty {
  id: string;
  world_id: string;
  city_id: string;
  city_name: string;
  district_id: string;
  district_name: string;
  property_code: string;
  property_type: "land" | "building" | "commercial_space" | "headquarters";
  name: string;
  area_units: number;
  base_value_cents: number;
  improvement_value_cents: number;
  owner_profile_id: string | null;
  owner_name: string | null;
  is_owned_by_me: boolean;
  company_use_id: string | null;
  company_use_name: string | null;
  status: "available" | "owned" | "leased" | "archived";
  listing_type: "sale" | "rent" | null;
  asking_price_cents: number;
  rent_cents_per_period: number;
  effective_sale_price_cents: number;
  effective_rent_cents_per_period: number;
  headquarters_level: number;
  version: number;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface PropertyTransfer {
  id: string;
  property_id: string;
  seller_profile_id: string | null;
  buyer_profile_id: string;
  price_cents: number;
  price_index_bps: number;
  transfer_type: "system_sale" | "resale";
  transaction_id: string;
  created_at: ISODateTime;
}

export interface PropertyLeasePayment {
  id: string;
  period_number: number;
  amount_cents: number;
  status: "paid" | "defaulted";
  transaction_id: string | null;
  input_snapshot_json: Record<string, number>;
  paid_at: ISODateTime;
}

export interface PropertyLease {
  id: string;
  world_id: string;
  property_id: string;
  property_name: string;
  landlord_profile_id: string;
  landlord_name: string;
  tenant_company_id: string;
  tenant_company_name: string;
  rent_cents_per_period: number;
  term_periods: number;
  periods_paid: number;
  status: "active" | "completed" | "defaulted" | "cancelled";
  default_reason: string | null;
  starts_at: ISODateTime;
  ends_at: ISODateTime;
  next_payment_at: ISODateTime;
  completed_at: ISODateTime | null;
  defaulted_at: ISODateTime | null;
  cancelled_at: ISODateTime | null;
  created_at: ISODateTime;
  payments: PropertyLeasePayment[];
}

export interface PropertyImprovement {
  id: string;
  property_id: string;
  company_id: string;
  improvement_type: "headquarters_upgrade";
  level_after: number;
  cost_cents: number;
  transaction_id: string;
  created_at: ISODateTime;
}

export interface InAppNotification {
  id: string;
  event_type: string;
  category: "critical" | "strategic" | "social" | "summary";
  title: string;
  body: string;
  metadata_json: Record<string, string | number | boolean | null>;
  read_at: ISODateTime | null;
  created_at: ISODateTime;
}

export type EngagementGoalCategory =
  | "economic"
  | "social"
  | "exploration"
  | "risk"
  | "long_term"
  | "season";

export interface EngagementGoal {
  id: string;
  template_key: string;
  category: EngagementGoalCategory;
  title_key: string;
  description_key: string;
  unit_key: string;
  status:
    | "offered"
    | "active"
    | "completed"
    | "swapped"
    | "declined"
    | "expired";
  target_value: number;
  progress_value: number;
  recommended_for_doctrine: boolean;
  choice_window_id: string;
  selected_at: ISODateTime | null;
  completed_at: ISODateTime | null;
  catch_up_until: ISODateTime;
  reward_type: "knowledge" | "chronicle" | "mastery" | "cosmetic";
  reward_key: string;
}

export interface EngagementGoalWindow {
  id: string;
  starts_at: ISODateTime;
  ends_at: ISODateTime;
  catch_up_until: ISODateTime;
  max_choices: number;
  status: "open" | "catch_up" | "closed";
  selected_count: number;
  goals: EngagementGoal[];
}

export interface OpenPlan {
  id: string;
  category: "urgent" | "strategic" | "discoverable";
  title: string;
  next_step: string;
  target_path: string;
  status: "active" | "completed" | "archived";
  priority: number;
  created_at: ISODateTime;
  updated_at: ISODateTime;
  completed_at: ISODateTime | null;
}

export interface CommandCenterOpportunity {
  category: "urgent" | "strategic" | "discoverable";
  source_type: "plan" | "goal" | "world_event" | "system";
  source_id: string;
  title: string;
  detail: string;
  target_path: string;
  priority: number;
}

export interface EngagementCommandCenter {
  opportunities: CommandCenterOpportunity[];
  active_goal_count: number;
  open_plan_count: number;
  natural_break_available: boolean;
}

export interface PlayerSession {
  id: string;
  profile_id: string;
  client_session_key: string;
  status: "active" | "completed" | "abandoned";
  started_at: ISODateTime;
  last_activity_at: ISODateTime;
  ended_at: ISODateTime | null;
}

export interface SessionSummary {
  id: string;
  session_id: string;
  duration_seconds: number;
  decisions_json: Record<string, unknown>[];
  changes_json: Record<string, unknown>[];
  open_plans_json: Record<string, unknown>[];
  next_entry_points_json: CommandCenterOpportunity[];
  natural_break_reached: boolean;
  created_at: ISODateTime;
}

export interface ReturnBriefing {
  id: string;
  since_at: ISODateTime;
  world_changes_json: Record<string, unknown>[];
  company_changes_json: Record<string, unknown>[];
  relevant_decisions_json: Record<string, unknown>[];
  available_content_json: Record<string, unknown>[];
  entry_points_json: CommandCenterOpportunity[];
  generated_at: ISODateTime;
  acknowledged_at: ISODateTime | null;
}

export interface NotificationPreference {
  id: string;
  category: "critical" | "strategic" | "social" | "summary";
  live_enabled: boolean;
  digest_frequency: "immediate" | "daily" | "weekly" | "off";
  quiet_start_minute: number;
  quiet_end_minute: number;
  timezone: string;
  updated_at: ISODateTime;
}

export interface EngagementSettings {
  id: string;
  adaptive_help_enabled: boolean;
  session_summary_enabled: boolean;
  ranking_visible: boolean;
  information_density: "compact" | "standard" | "detailed";
  updated_at: ISODateTime;
}

export type DoctrineKey =
  | "industrial_captain"
  | "financial_architect"
  | "innovator"
  | "real_estate_strategist"
  | "networker"
  | "information_strategist"
  | "opportunist";

export type MasteryArea =
  | "company_management"
  | "market_analysis"
  | "capital_markets"
  | "contract_management"
  | "people_leadership"
  | "real_estate"
  | "cartel_leadership"
  | "diplomacy"
  | "intelligence"
  | "risk_management"
  | "season_strategy";

export interface DoctrineCatalogItem {
  key: DoctrineKey;
  title_key: string;
  description_key: string;
  focus_areas: MasteryArea[];
  economic_bonus: false;
  reversible: true;
}

export interface DoctrineState {
  id: string;
  doctrine_key: DoctrineKey;
  version: number;
  selected_at: ISODateTime;
  changed_at: ISODateTime;
}

export interface MasteryProgress {
  id: string;
  area_key: MasteryArea;
  points: number;
  level: number;
  distinct_decisions_json: string[];
  updated_at: ISODateTime;
}

export interface OutcomeReport {
  id: string;
  source_type: string;
  source_id: string;
  title_key: string;
  controllable_factors_json: string[];
  external_factors_json: string[];
  worked_well_json: string[];
  alternatives_json: string[];
  knowledge_unlocked_json: string[];
  created_at: ISODateTime;
}

export interface AdaptiveHelpOffer {
  id: string;
  context_key: string;
  explanation_key: string;
  suggestion_key: string;
  target_path: string;
  status: "offered" | "accepted" | "dismissed" | "completed";
  created_at: ISODateTime;
  responded_at: ISODateTime | null;
}

export interface PersonalSuccessChain {
  id: string;
  chain_key: string;
  completed_steps: number;
  total_steps: number;
  status: "active" | "completed";
  completed_event_types_json: string[];
  updated_at: ISODateTime;
  completed_at: ISODateTime | null;
}

export interface Mentorship {
  id: string;
  mentor_profile_id: string;
  mentee_profile_id: string;
  status:
    | "proposed"
    | "active"
    | "paused"
    | "completed"
    | "declined"
    | "cancelled";
  mentor_opted_in: boolean;
  mentee_opted_in: boolean;
  feedback_positive: boolean | null;
  created_at: ISODateTime;
  accepted_at: ISODateTime | null;
  completed_at: ISODateTime | null;
  milestones: string[];
}

export interface CartelDelegation {
  id: string;
  organization_id: string;
  grantor_membership_id: string;
  delegate_membership_id: string;
  role_key: string;
  permissions_json: string[];
  status: "active" | "revoked" | "expired";
  starts_at: ISODateTime;
  expires_at: ISODateTime;
  revoked_at: ISODateTime | null;
}

export interface CartelMembershipPause {
  id: string;
  membership_id: string;
  status: "active" | "completed" | "cancelled";
  starts_at: ISODateTime;
  planned_until: ISODateTime;
  resumed_at: ISODateTime | null;
}

export interface CartelChronicleEntry {
  id: string;
  organization_id: string;
  actor_profile_id: string | null;
  entry_type: string;
  source_type: string;
  source_id: string;
  title_key: string;
  body_key: string;
  metadata_json: Record<string, unknown>;
  created_at: ISODateTime;
}

export interface NarrativeChronicleEntry {
  id: string;
  scope_type: "company" | "world" | "profile";
  scope_id: string;
  source_type: string;
  source_id: string;
  entry_type: string;
  title_key: string;
  body_key: string;
  cause_keys_json: string[];
  actor_keys_json: string[];
  impact_keys_json: string[];
  open_question_keys_json: string[];
  metadata_json: Record<string, unknown>;
  created_at: ISODateTime;
}

export interface NarrativeActorRelationship {
  actor_id: string;
  actor_key: string;
  actor_type: "entrepreneur" | "journalist" | "analyst" | "decision_maker";
  name_key: string;
  description_key: string;
  trust: number;
  rivalry: number;
  reputation: number;
  information_access: number;
  interaction_count: number;
  history_keys: string[];
}

export interface EventDossierClue {
  id: string;
  clue_key: string;
  order_index: number;
  rare: boolean;
  discovered: boolean;
}

export interface EventDossier {
  id: string;
  world_event_instance_id: string;
  title_key: string;
  cause_key: string;
  local_impact_key: string;
  open_question_key: string;
  archived: boolean;
  investigation_count: number;
  completed_at: ISODateTime | null;
  clues: EventDossierClue[];
}

export type CollectionItemType =
  | "title"
  | "emblem"
  | "hq_cosmetic"
  | "chronicle"
  | "discovery";

export interface CollectionEntry {
  id: string;
  item_id: string;
  item_key: string;
  item_type: CollectionItemType;
  title_key: string;
  description_key: string;
  rarity: string;
  duplicate_points: number;
  unlocked_at: ISODateTime;
}

export interface PlayerIdentity {
  id: string;
  active_title_item_id: string | null;
  active_emblem_item_id: string | null;
  active_hq_cosmetic_item_id: string | null;
  profile_card_public: boolean;
  updated_at: ISODateTime;
}

export interface MasteryHighlight {
  area_key: string;
  level: number;
  points: number;
}

export interface StrategicProfileCard {
  profile_id: string;
  codename: string;
  doctrine_key: string | null;
  active_title_item_id: string | null;
  active_emblem_item_id: string | null;
  active_hq_cosmetic_item_id: string | null;
  profile_card_public: boolean;
  mastery_highlights: MasteryHighlight[];
}

export interface LegacyRecord {
  id: string;
  record_key: string;
  source_type: string;
  source_id: string;
  title_key: string;
  metadata_json: Record<string, unknown>;
  created_at: ISODateTime;
}

export interface PlayerSeasonGoal {
  id: string;
  season_id: string;
  goal_key: string;
  title_key: string;
  description_key: string;
  target_value: number;
  progress_value: number;
  status: "offered" | "active" | "completed" | "archived";
  selected_at: ISODateTime | null;
  completed_at: ISODateTime | null;
}

export interface ReturnContract {
  id: string;
  contract_key: string;
  title_key: string;
  description_key: string;
  target_value: number;
  progress_value: number;
  status: "offered" | "active" | "completed" | "declined";
  absence_days: number;
  offered_at: ISODateTime;
  selected_at: ISODateTime | null;
  completed_at: ISODateTime | null;
}

export interface RankingEntry {
  rank: number;
  profile_id: string;
  codename: string;
  score: number;
  historical_best_score: number;
  bracket: "newcomer" | "veteran";
  is_self: boolean;
}

export interface ParallelRankingCategory {
  category: string;
  entries: RankingEntry[];
}

export interface ParallelRankings {
  categories: ParallelRankingCategory[];
  economic_rewards: false;
}

export interface NotificationCount {
  unread_count: number;
}

export interface RealtimeChannels {
  protocol_version: number;
  channels: string[];
}

export interface RealtimeEvent {
  id: string;
  world_id: string;
  event_type: string;
  event_version: number;
  audience_type: "world" | "player" | "cartel" | "city";
  channel: string;
  payload_json: Record<string, unknown>;
  created_at: ISODateTime;
  expires_at: ISODateTime;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    request_id?: string;
    fields?: Record<string, string>;
  };
  server_time: string;
}
