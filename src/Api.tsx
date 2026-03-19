const BASE = "/api";

const ACCESS_TOKEN_KEY = "ms_access_token";
const REFRESH_TOKEN_KEY = "ms_refresh_token";

type AuthListener = () => void;

const authListeners = new Set<AuthListener>();
let refreshPromise: Promise<void> | null = null;

function emitAuthChanged() {
  for (const listener of authListeners) listener();
}

export function subscribeAuth(listener: AuthListener) {
  authListeners.add(listener);
  return () => {
    authListeners.delete(listener);
  };
}

export const getAccessToken = () => localStorage.getItem(ACCESS_TOKEN_KEY);
export const getRefreshToken = () => localStorage.getItem(REFRESH_TOKEN_KEY);

export function setAuthTokens(tokens: { accessToken: string; refreshToken: string }) {
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
  emitAuthChanged();
}

export function clearAuthTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  emitAuthChanged();
}

export const setAccessToken = (token: string) =>
  setAuthTokens({ accessToken: token, refreshToken: getRefreshToken() ?? "" });
export const clearAccessToken = () => clearAuthTokens();

export class ApiHttpError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export const isAuthError = (e: unknown) => e instanceof ApiHttpError && e.status === 401;

type RequestOptions = {
  retryAuth?: boolean;
  skipAuth?: boolean;
};

function shouldRefresh(path: string) {
  return ![
    "/v1/auth/login",
    "/v1/auth/register",
    "/v1/auth/refresh",
    "/v1/auth/logout",
  ].includes(path);
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let msg = `${response.status} ${response.statusText}`;
    try {
      const json = await response.json();
      msg = (json as { detail?: string; message?: string }).detail ?? (json as { message?: string }).message ?? msg;
    } catch {
      // Ignore non-JSON error responses.
    }
    throw new ApiHttpError(msg, response.status);
  }

  return response.status === 204 ? (undefined as T) : await response.json();
}

async function execute<T>(path: string, init: RequestInit = {}, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(init.headers || undefined);
  headers.set("accept", "application/json");
  if (init.body != null && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }

  if (!options.skipAuth) {
    const token = getAccessToken();
    if (token) headers.set("authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${BASE}${path}`, { ...init, headers });
  return parseResponse<T>(response);
}

async function refreshTokens() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    clearAuthTokens();
    throw new ApiHttpError("Session expired", 401);
  }

  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const response = await execute<AuthTokenResponse>(
          "/v1/auth/refresh",
          {
            method: "POST",
            body: JSON.stringify({ refresh_token: refreshToken }),
          },
          { retryAuth: false, skipAuth: true },
        );
        setAuthTokens({
          accessToken: response.access_token,
          refreshToken: response.refresh_token,
        });
      } catch (error) {
        clearAuthTokens();
        throw error;
      } finally {
        refreshPromise = null;
      }
    })();
  }

  return refreshPromise;
}

async function request<T>(path: string, init: RequestInit = {}, options: RequestOptions = {}): Promise<T> {
  const retryAuth = options.retryAuth ?? true;
  try {
    return await execute<T>(path, init, options);
  } catch (error) {
    if (
      retryAuth &&
      error instanceof ApiHttpError &&
      error.status === 401 &&
      shouldRefresh(path) &&
      getRefreshToken()
    ) {
      await refreshTokens();
      return execute<T>(path, init, options);
    }
    throw error;
  }
}

export type UUID = string;
export type Visibility = "public" | "private";
export type PortfolioKind = "personal" | "subscribed";

export type PortfolioSummary = {
  id: UUID;
  name: string;
  emoji?: string | null;
  balance_usd: string;
  pnl_day_usd: string;
  kind: PortfolioKind;
  visibility?: Visibility | null;
  owner_id?: UUID | null;
  owner_email?: string | null;
};
export type PortfolioDetail = PortfolioSummary & { created_at: string };

export type PortfolioCreate = { name: string; emoji?: string | null; visibility: Visibility };
export type PortfolioUpdate = {
  name?: string | null;
  emoji?: string | null;
  visibility?: Visibility | null;
};

export type AssetSummary = {
  id: UUID;
  symbol: string;
  display_name?: string | null;
  emoji?: string | null;
};
export type AssetCreate = { symbol: string; display_name?: string | null; emoji?: string | null };

export type TxType = "buy" | "sell" | "transfer_in" | "transfer_out";
export type TxItem = {
  id: UUID;
  asset_id: UUID;
  type: TxType;
  quantity: string;
  price_usd?: string | null;
  fee_usd?: string | null;
  at: string;
  note?: string | null;
  tx_hash?: string | null;
};
export type TxCreate = Omit<TxItem, "id">;

export type TimeseriesResponse = { points: { t: string; balance_usd: string }[] };

export type Chain = "ETH" | "SOL";
export type WalletImportRequest = { chain: Chain; address: string };
export type JobStatus = "queued" | "running" | "done" | "error";
export type ImportJob = { job_id: UUID; status: JobStatus; message?: string | null };

export type Exchange = "bybit";
export type ExchangeConnectRequest = {
  exchange: Exchange;
  label?: string | null;
  api_key: string;
  api_secret: string;
};

export type BybitKeysImportRequest = {
  api_key: string;
  api_secret: string;
};

export type Role = "user" | "manager" | "admin";

export const apiHealth = () => request<{ status: string }>("/health", {}, { retryAuth: false });

export const listPortfolios = () => request<PortfolioSummary[]>("/v1/portfolios");
export const createPortfolio = (body: PortfolioCreate) =>
  request<PortfolioDetail>("/v1/portfolios", { method: "POST", body: JSON.stringify(body) });
export const getPortfolio = (portfolioId: UUID) => request<PortfolioDetail>(`/v1/portfolios/${portfolioId}`);
export const deletePortfolio = (portfolioId: UUID) =>
  request<void>(`/v1/portfolios/${portfolioId}`, { method: "DELETE" });
export const importPortfolio = (sourceId: UUID) =>
  request<PortfolioDetail>("/v1/portfolios/import", {
    method: "POST",
    body: JSON.stringify({ source_id: sourceId }),
  });
export const updatePortfolio = (portfolioId: UUID, body: PortfolioUpdate) =>
  request<PortfolioDetail>(`/v1/portfolios/${portfolioId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
export const importBybitKeys = (portfolioId: UUID, body: BybitKeysImportRequest) =>
  request<PortfolioDetail>(`/v1/portfolios/${portfolioId}/import/bybit`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const listAssets = (portfolioId: UUID) =>
  request<AssetSummary[]>(`/v1/portfolios/${portfolioId}/assets`);
export const addAsset = (portfolioId: UUID, body: AssetCreate) =>
  request<AssetSummary>(`/v1/portfolios/${portfolioId}/assets`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const listTransactions = (portfolioId: UUID, assetId?: UUID) =>
  request<TxItem[]>(
    `/v1/portfolios/${portfolioId}/transactions${assetId ? `?asset_id=${assetId}` : ""}`,
  );
export const addTransaction = (portfolioId: UUID, body: TxCreate) =>
  request<TxItem>(`/v1/portfolios/${portfolioId}/transactions`, {
    method: "POST",
    body: JSON.stringify(body),
  });
export const updateTransaction = (portfolioId: UUID, txId: UUID, body: TxCreate) =>
  request<TxItem>(`/v1/portfolios/${portfolioId}/transactions/${txId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
export const deleteTransaction = (portfolioId: UUID, txId: UUID) =>
  request<void>(`/v1/portfolios/${portfolioId}/transactions/${txId}`, { method: "DELETE" });

export const getTimeseries = (portfolioId: UUID, days = 14) =>
  request<TimeseriesResponse>(`/v1/portfolios/${portfolioId}/timeseries?days=${days}`);

export const importWallet = (body: WalletImportRequest) =>
  request<ImportJob>("/v1/import/wallet", { method: "POST", body: JSON.stringify(body) });
export const importWalletStatus = (jobId: UUID) =>
  request<ImportJob>(`/v1/import/wallet/${jobId}`);
export const listExchanges = () => request<Record<string, unknown>[]>("/v1/integrations/exchanges");
export const connectExchange = (body: ExchangeConnectRequest) =>
  request<Record<string, unknown>>("/v1/integrations/exchanges", {
    method: "POST",
    body: JSON.stringify(body),
  });
export const deleteExchange = (connectionId: string) =>
  request<void>(`/v1/integrations/exchanges/${connectionId}`, { method: "DELETE" });

export type BybitTicker = {
  category: string;
  symbol: string;
  bid1Price: string;
  bid1Size: string;
  ask1Price: string;
  ask1Size: string;
  lastPrice: string;
  prevPrice24h: string;
  price24hPcnt: string;
  highPrice24h: string;
  lowPrice24h: string;
  turnover24h: string;
  volume24h: string;
  usdIndexPrice?: string | null;
};
export const getBybitTicker = (base: string, category = "spot") =>
  request<BybitTicker>(
    `/v1/market/bybit/ticker/${encodeURIComponent(base)}?category=${encodeURIComponent(category)}`,
  );

export type AuthRegisterResponse = { ok: boolean };
export type AuthTokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  refresh_expires_in: number;
};
export type AuthMe = { id: string; email: string; role: Role };
export type UserListItem = { id: string; email: string; role: Role; created_at: string };
export type UpdateRoleRequest = { role: Role };

export const authRegister = (email: string) =>
  request<AuthRegisterResponse>(
    "/v1/auth/register",
    { method: "POST", body: JSON.stringify({ email }) },
    { retryAuth: false, skipAuth: true },
  );
export const authLogin = (email: string, password: string) =>
  request<AuthTokenResponse>(
    "/v1/auth/login",
    { method: "POST", body: JSON.stringify({ email, password }) },
    { retryAuth: false, skipAuth: true },
  );
export const authLogout = (refreshToken: string) =>
  request<void>(
    "/v1/auth/logout",
    { method: "POST", body: JSON.stringify({ refresh_token: refreshToken }) },
    { retryAuth: false, skipAuth: true },
  );
export const authMe = () => request<AuthMe>("/v1/auth/me");
export const listUsers = () => request<UserListItem[]>("/v1/auth/users");
export const updateUserRole = (userId: string, body: UpdateRoleRequest) =>
  request<AuthMe>(`/v1/auth/users/${userId}/role`, { method: "PATCH", body: JSON.stringify(body) });
