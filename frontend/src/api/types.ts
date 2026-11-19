export type Role = "ORG_ADMIN" | "SUPERVISOR" | "TECHNICIAN";
export type Lang = "en" | "es";
export type Environment = "OUTDOOR" | "INDOOR";
/** Mirrors ``app.models.CAPABILITIES``; the API sends one boolean per capability in ``User.can``. */
export type Capability = "manage_clients" | "manage_norm_rules" | "capture_measurements";
export type MeasurementStatus = "OK" | "OUT_OF_RANGE" | "NO_RULE";
export type Direction = "LOW" | "HIGH";
export type Classification = "NORMATIVE" | "COMPLEMENTARY";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  /** ``timezone``: IANA zone of the organization; the SPA shows times in it. */
  organization: { id: number; name: string; timezone: string };
  lang: Lang;
  can: Record<Capability, boolean>;
}

export interface Pool {
  id: number;
  client_id: number;
  client_name: string;
  name: string;
  volume_liters: number;
  environment: Environment;
}

export interface Client {
  id: number;
  name: string;
  contact_name: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  pool_count: number;
  pools?: Pool[];
}

/** Global catalog row from ``GET /api/parameters``. ``unit`` is null for dimensionless parameters (pH). */
export interface WaterParameter {
  id: number;
  code: string;
  name: string;
  unit: string | null;
  decimals: number;
  physical_min: number | null;
  physical_max: number | null;
  sort_order: number;
  active: boolean;
}

/** Row of ``GET /api/norm-rules``: one per parameter for the user's organization. Null bound = one-sided rule. */
export interface NormRule {
  id: number;
  parameter_id: number;
  parameter_code: string;
  parameter_name: string;
  unit: string | null;
  decimals: number;
  min_value: number | null;
  max_value: number | null;
  classification: Classification;
  source_notes: string | null;
  active: boolean;
  /** ISO 8601 UTC; null while the seeded planning default is unedited. */
  updated_at: string | null;
  updated_by_name: string | null;
}

/** Body of ``PATCH /api/norm-rules/{id}``: send only what changes; null or "" clears a bound. */
export interface NormRulePatch {
  min_value?: number | string | null;
  max_value?: number | string | null;
  active?: boolean;
  classification?: Classification;
}

/** Row of ``GET /api/measurements``. ``status``/``direction``/``rule_*`` are the create-time snapshot. */
export interface Measurement {
  id: number;
  /** MES-YYYYMMDD-#### (local date of recording + daily counter), unique per organization. */
  folio: string;
  pool_id: number;
  pool_name: string;
  client_id: number;
  client_name: string;
  parameter_id: number;
  parameter_code: string;
  parameter_name: string;
  /** Copied from the parameter at capture; null for dimensionless (pH). */
  unit: string | null;
  decimals: number;
  value: number;
  /** ISO 8601 UTC */
  measured_at: string;
  notes: string | null;
  recorded_at: string;
  recorded_by_id: number;
  recorded_by_name: string;
  status: MeasurementStatus;
  /** Only for OUT_OF_RANGE. */
  direction: Direction | null;
  /** Null for NO_RULE. */
  rule_id: number | null;
  rule_min: number | null;
  rule_max: number | null;
  rule_classification: Classification | null;
}

/** Body of ``POST /api/measurements``. ``value`` accepts "7,4" or "7.4". */
export interface MeasurementInput {
  pool_id: number;
  parameter_id: number;
  value: number | string;
  /** Optional; must equal the parameter's unit when sent. */
  unit?: string;
  /** ISO 8601 with time; without offset = UTC; omitted = now; future is rejected. */
  measured_at?: string;
  notes?: string;
}

export interface MeasurementFilters {
  pool_id?: number;
  parameter_id?: number;
  status?: MeasurementStatus;
  /** ISO 8601, inclusive. */
  measured_from?: string;
  limit?: number;
}

/** ``GET /api/dashboard``. Windows are local calendar days in ``windows.timezone`` (the organization's zone). */
export interface Dashboard {
  counts: { clients: number; pools: number; users: number };
  measurements: { today: number; out_of_range_last_7_days: number };
  /** ISO 8601 UTC (``...Z``) starts of the counted windows; use them as ``measured_from`` to list the counted rows. */
  windows: { timezone: string; today_from: string; last_7_days_from: string };
}

/** Body of the create forms: text inputs are sent as-is and validated by the API. */
export type ClientInput = Partial<Record<"name" | "contact_name" | "email" | "phone" | "address", string>>;
export type PoolInput = Partial<Record<"name" | "volume_liters" | "environment", string>>;
