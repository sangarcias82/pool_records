import { api } from "./client";
import type {
  Client,
  ClientInput,
  Dashboard,
  Lang,
  Measurement,
  MeasurementFilters,
  MeasurementInput,
  NormRule,
  NormRulePatch,
  Pool,
  PoolInput,
  User,
  WaterParameter,
} from "./types";

export const auth = {
  login: (login: string, password: string, lang: Lang) => api.post<User>("/api/auth/login", { login, password, lang }),
  logout: () => api.post<void>("/api/auth/logout"),
  me: () => api.get<User>("/api/auth/me"),
  setLang: (lang: Lang) => api.post<{ lang: Lang }>("/api/lang", { lang }),
};

export const core = {
  dashboard: () => api.get<Dashboard>("/api/dashboard"),
};

export const clients = {
  list: () => api.get<Client[]>("/api/clients"),
  get: (id: number) => api.get<Client>(`/api/clients/${id}`),
  create: (body: ClientInput) => api.post<Client>("/api/clients", body),
};

export const pools = {
  list: () => api.get<Pool[]>("/api/pools"),
  get: (id: number) => api.get<Pool>(`/api/pools/${id}`),
  create: (clientId: number, body: PoolInput) => api.post<Pool>(`/api/clients/${clientId}/pools`, body),
};

export const parameters = {
  list: (includeInactive = false) =>
    api.get<WaterParameter[]>(includeInactive ? "/api/parameters?include_inactive=true" : "/api/parameters"),
};

export const normRules = {
  list: () => api.get<NormRule[]>("/api/norm-rules"),
  update: (id: number, body: NormRulePatch) => api.patch<NormRule>(`/api/norm-rules/${id}`, body),
};

export const measurements = {
  list: (filters: MeasurementFilters = {}) => {
    const query = new URLSearchParams(
      Object.entries(filters).flatMap(([key, value]) => (value === undefined ? [] : [[key, String(value)]])),
    ).toString();
    return api.get<Measurement[]>(query ? `/api/measurements?${query}` : "/api/measurements");
  },
  get: (id: number) => api.get<Measurement>(`/api/measurements/${id}`),
  create: (body: MeasurementInput) => api.post<Measurement>("/api/measurements", body),
};
