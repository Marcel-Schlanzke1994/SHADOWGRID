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

export interface Specialist {
  id: string;
  name: string;
  role: string;
  competence: number;
  loyalty: number;
  ambition: number;
  stress: number;
  exposure: number;
  salary: number;
  status: string;
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

export interface ApiErrorBody {
  error: { code: string; message: string; request_id?: string; fields?: Record<string, string> };
  server_time: string;
}
