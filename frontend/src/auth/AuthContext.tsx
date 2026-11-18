import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { onUnauthorized } from "../api/client";
import { auth } from "../api/endpoints";
import type { User } from "../api/types";
import { useI18n } from "../i18n/I18nContext";

interface AuthValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const { lang } = useI18n();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    auth.me().then(setUser).catch(() => setUser(null)).finally(() => setLoading(false));
    onUnauthorized(() => setUser(null));
    return () => onUnauthorized(null);
  }, []);

  const value: AuthValue = {
    user,
    loading,
    login: async (email, password) => setUser(await auth.login(email, password, lang)),
    logout: async () => {
      await auth.logout().catch(() => undefined);
      setUser(null);
    },
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside <AuthProvider>");
  return value;
}
