// Api.tsx
const BASE = "/api";

const TOKEN_KEY = "ms_access_token";

export const getAccessToken = () => localStorage.getItem(TOKEN_KEY);
export const setAccessToken = (t: string) => localStorage.setItem(TOKEN_KEY, t);
export const clearAccessToken = () => localStorage.removeItem(TOKEN_KEY);

export class ApiHttpError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export const isAuthError = (e: any) => e instanceof ApiHttpError && e.status === 401;

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers || undefined);
  headers.set("accept", "application/json");
  headers.set("content-type", "application/json");

  const token = getAccessToken();
  if (token) headers.set("authorization", `Bearer ${token}`);

  const r = await fetch(`${BASE}${path}`, { ...init, headers });

  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try {
      const j = await r.json();
      msg = j?.detail || j?.message || msg;
    } catch {}
    throw new ApiHttpError(msg, r.status);
  }

  return r.status === 204 ? (undefined as T) : await r.json();
}

/* ===== Types ===== */
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

/* ===== API calls ===== */
// health
export const apiHealth = () => request<{ status: string }>("/health");

// portfolios
export const listPortfolios = () => request<PortfolioSummary[]>("/v1/portfolios");
export const createPortfolio = (b: PortfolioCreate) =>
  request<PortfolioDetail>("/v1/portfolios", { method: "POST", body: JSON.stringify(b) });
export const getPortfolio = (pid: UUID) => request<PortfolioDetail>(`/v1/portfolios/${pid}`);
export const deletePortfolio = (pid: UUID) =>
  request<void>(`/v1/portfolios/${pid}`, { method: "DELETE" });
export const importPortfolio = (sourceId: UUID) =>
  request<PortfolioDetail>("/v1/portfolios/import", {
    method: "POST",
    body: JSON.stringify({ source_id: sourceId }),
  });
export const updatePortfolio = (pid: UUID, b: PortfolioUpdate) =>
  request<PortfolioDetail>(`/v1/portfolios/${pid}`, {
    method: "PUT",
    body: JSON.stringify(b),
  });
export async function importBybitKeys(pid: UUID, body: BybitKeysImportRequest) {
  return request<PortfolioDetail>(`/v1/portfolios/${pid}/import/bybit`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// assets
export const listAssets = (pid: UUID) => request<AssetSummary[]>(`/v1/portfolios/${pid}/assets`);
export const addAsset = (pid: UUID, b: AssetCreate) =>
  request<AssetSummary>(`/v1/portfolios/${pid}/assets`, {
    method: "POST",
    body: JSON.stringify(b),
  });

// transactions
export const listTransactions = (pid: UUID, assetId?: UUID) =>
  request<TxItem[]>(`/v1/portfolios/${pid}/transactions${assetId ? `?asset_id=${assetId}` : ""}`);

export const addTransaction = (pid: UUID, b: TxCreate) =>
  request<TxItem>(`/v1/portfolios/${pid}/transactions`, {
    method: "POST",
    body: JSON.stringify(b),
  });

export const updateTransaction = (pid: UUID, tid: UUID, b: TxCreate) =>
  request<TxItem>(`/v1/portfolios/${pid}/transactions/${tid}`, {
    method: "PUT",
    body: JSON.stringify(b),
  });

export const deleteTransaction = (pid: UUID, tid: UUID) =>
  request<void>(`/v1/portfolios/${pid}/transactions/${tid}`, { method: "DELETE" });

// timeseries
export const getTimeseries = (pid: UUID, days = 14) =>
  request<TimeseriesResponse>(`/v1/portfolios/${pid}/timeseries?days=${days}`);

// integrations
export const importWallet = (b: WalletImportRequest) =>
  request<ImportJob>("/v1/import/wallet", { method: "POST", body: JSON.stringify(b) });
export const importWalletStatus = (jobId: UUID) => request<ImportJob>(`/v1/import/wallet/${jobId}`);

export const listExchanges = () => request<any[]>("/v1/integrations/exchanges");
export const connectExchange = (b: ExchangeConnectRequest) =>
  request<any>("/v1/integrations/exchanges", { method: "POST", body: JSON.stringify(b) });
export const deleteExchange = (connId: string) =>
  request<void>(`/v1/integrations/exchanges/${connId}`, { method: "DELETE" });

export type BybitTicker = {
  category: string;
  symbol: string;
  bid1Price: string;
  bid1Size: string;
  ask1Price: string;
  ask1Size: string;
  lastPrice: string;
  prevPrice24h: string;
  price24hPcnt: string; // fraction, e.g. "0.0068" => 0.68%
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
export type AuthTokenResponse = { access_token: string; token_type: string; expires_in: number };
export type AuthMe = { id: string; email: string };

export const authRegister = (email: string) =>
  request<AuthRegisterResponse>("/v1/auth/register", {
    method: "POST",
    body: JSON.stringify({ email }),
  });

export const authLogin = (email: string, password: string) =>
  request<AuthTokenResponse>("/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

export const authMe = () => request<AuthMe>("/v1/auth/me");
