const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    headers: { accept: "application/json", "content-type": "application/json" },
    ...init,
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
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

// assets
export const listAssets = (pid: UUID) => request<AssetSummary[]>(`/v1/portfolios/${pid}/assets`);
export const addAsset = (pid: UUID, b: AssetCreate) =>
  request<AssetSummary>(`/v1/portfolios/${pid}/assets`, {
    method: "POST",
    body: JSON.stringify(b),
  });

// transactions
export const listTransactions = (pid: UUID) =>
  request<TxItem[]>(`/v1/portfolios/${pid}/transactions`);
export const addTransaction = (pid: UUID, b: TxCreate) =>
  request<TxItem>(`/v1/portfolios/${pid}/transactions`, {
    method: "POST",
    body: JSON.stringify(b),
  });

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
