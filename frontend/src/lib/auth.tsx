import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { api, getUser, setToken, setUser } from "../lib/api";
import type { User } from "../lib/types";

interface AuthState {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
}

const AuthContext = createContext<AuthState>({
  user: null,
  token: null,
  login: async () => {
    throw new Error("not ready");
  },
  logout: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<User | null>(getUser() as User | null);
  const [token, setTokenState] = useState<string | null>(localStorage.getItem("3dulpin_token"));

  const value = useMemo<AuthState>(
    () => ({
      user,
      token,
      async login(email: string, password: string) {
        const res = (await api("/auth/login", {
          method: "POST",
          body: { email, password },
        })) as { access_token: string; user: User };
        setToken(res.access_token);
        setUser(res.user);
        setTokenState(res.access_token);
        setUserState(res.user);
        return res.user;
      },
      logout() {
        setToken(null);
        setUser(null);
        setTokenState(null);
        setUserState(null);
      },
    }),
    [user, token]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
