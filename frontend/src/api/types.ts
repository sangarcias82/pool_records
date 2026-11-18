export type Role = "ORG_ADMIN" | "SUPERVISOR" | "TECHNICIAN";
export type Lang = "en" | "es";
export type Environment = "OUTDOOR" | "INDOOR";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  organization: { id: number; name: string };
  lang: Lang;
  can: { manage_clients: boolean };
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

export interface Dashboard {
  counts: { clients: number; pools: number; users: number };
}

/** Body of the create forms: text inputs are sent as-is and validated by the API. */
export type ClientInput = Partial<Record<"name" | "contact_name" | "email" | "phone" | "address", string>>;
export type PoolInput = Partial<Record<"name" | "volume_liters" | "environment", string>>;
