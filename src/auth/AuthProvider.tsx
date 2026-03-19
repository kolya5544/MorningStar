/* eslint-disable react-refresh/only-export-components */
import {
  authLogin,
  authLogout,
  authMe,
  clearAuthTokens,
  getAccessToken,
  getRefreshToken,
  setAuthTokens,
  subscribeAuth,
  type AuthMe,
} from "@/Api";
import React, { createContext, useContext, useEffect, useMemo, useState } from "react";

type AuthContextValue = {
  user: AuthMe | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthMe | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = async () => {
    if (!getAccessToken() && !getRefreshToken()) {
      setUser(null);
      setIsLoading(false);
      return;
    }

    try {
      const me = await authMe();
      setUser(me);
    } catch {
      clearAuthTokens();
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void refreshUser();
  }, []);

  useEffect(() => {
    return subscribeAuth(() => {
      if (!getAccessToken() && !getRefreshToken()) {
        setUser(null);
        setIsLoading(false);
      }
    });
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: user !== null,
      isLoading,
      signIn: async (email: string, password: string) => {
        const tokens = await authLogin(email, password);
        setAuthTokens({
          accessToken: tokens.access_token,
          refreshToken: tokens.refresh_token,
        });
        const me = await authMe();
        setUser(me);
      },
      signOut: async () => {
        const refreshToken = getRefreshToken();
        try {
          if (refreshToken) {
            await authLogout(refreshToken);
          }
        } finally {
          clearAuthTokens();
          setUser(null);
        }
      },
      refreshUser,
    }),
    [isLoading, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
