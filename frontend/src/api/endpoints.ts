import { api } from "./client";
import type { Client, ClientInput, Dashboard, Lang, Pool, PoolInput, User } from "./types";

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
  get: (id: number) => api.get<Pool>(`/api/pools/${id}`),
  create: (clientId: number, body: PoolInput) => api.post<Pool>(`/api/clients/${clientId}/pools`, body),
};
