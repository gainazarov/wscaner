const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api";

export interface Scan {
  id: number;
  domain: string;
  status: "pending" | "running" | "completed" | "failed";
  status_display: string;
  total_urls: number;
  new_urls: number;
  internal_urls: number;
  external_urls: number;
  hidden_urls: number;
  error_urls: number;
  private_urls: number;
  max_depth: number;
  max_pages: number;
  started_at: string | null;
  completed_at: string | null;
  duration: number | null;
  error_message?: string;
  // Auth fields
  auth_success?: boolean | null;
  auth_method?: string;
  auth_error?: string;
  created_at: string;
  updated_at?: string;
  // Detail fields
  source_breakdown?: Record<string, number>;
  status_breakdown?: {
    success: number;
    redirect: number;
    hidden: number;
    client_error: number;
    server_error: number;
    unknown: number;
  };
  external_domains?: ExternalDomainGroup[];
}

export interface DiscoveredURL {
  id: number;
  url: string;
  source: "html" | "js" | "robots" | "sitemap" | "bruteforce";
  source_display: string;
  status_code: number | null;
  status_category: string;
  content_type: string;
  depth: number;
  is_internal: boolean;
  is_new: boolean;
  external_domain: string;
  source_url: string;
  is_private: boolean;
  is_sensitive: boolean;
  first_seen: string;
  last_seen: string;
}

export interface ExternalDomainGroup {
  external_domain: string;
  count: number;
  sources?: string[];
  urls?: { url: string; source: string; status_code: number | null; source_url?: string }[];
}

export interface DomainStats {
  domain: string;
  total_scans: number;
  last_scan_date: string;
  last_scan_status: string;
  total_unique_urls: number;
  last_scan_id: number;
  external_domains_count: number;
}

export interface DashboardStats {
  total_scans: number;
  active_scans: number;
  completed_scans: number;
  total_urls_discovered: number;
  unique_domains: number;
  external_urls: number;
  hidden_urls: number;
  recent_scans: Scan[];
  last_scan: {
    id: number;
    domain: string;
    completed_at: string | null;
    started_at: string | null;
    total_urls: number;
    duration: number | null;
    status: string;
  } | null;
  next_scheduled_scan: {
    domain: string;
    next_scan_at: string | null;
    interval_minutes: number;
  } | null;
  last_monitoring_scan: {
    domain: string;
    scanned_at: string;
    has_changes: boolean;
    pages_checked: number;
    new_domains: number;
    duration: number;
  } | null;
  active_scan: {
    id: number;
    domain: string;
    status: string;
    started_at: string | null;
  } | null;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ScanDiff {
  id: number;
  current_scan: number;
  previous_scan: number;
  new_urls_count: number;
  removed_urls_count: number;
  diff_urls: DiffURL[];
  created_at: string;
}

export interface DiffURL {
  id: number;
  url: string;
  change_type: "added" | "removed";
}

export type URLTab = "all" | "new" | "hidden" | "external" | "errors" | "private";
export type VisibilityFilter = "all" | "public" | "private";
export type ListStatusFilter = "all" | "whitelist" | "blacklist" | "unknown";

export interface URLSummary {
  total: number;
  public: number;
  private: number;
  internal: number;
  external: number;
  whitelist: number;
  blacklist: number;
  unknown: number;
  whitelist_domains: { domain: string; count: number }[];
  blacklist_domains: { domain: string; count: number }[];
  unknown_domains: { domain: string; count: number }[];
}

// ─── External Monitoring Types ──────────────────────────────────────────────

export interface ExternalDomainEntry {
  id: number;
  site_domain: string;
  domain: string;
  status: "safe" | "suspicious" | "new";
  list_classification: "whitelist" | "blacklist" | "unknown";
  is_suspicious: boolean;
  suspicious_reasons: string[];
  first_seen: string;
  last_seen: string;
  times_seen: number;
  found_on_pages: string[];
  first_seen_scan_id: number | null;
  last_seen_scan_id: number | null;
  days_since_first_seen: number;
}

export interface ExternalDomainAlertItem {
  id: number;
  scan_id: number | null;
  site_domain: string;
  external_domain: string;
  alert_type: "new_domain" | "suspicious_domain" | "removed_domain" | "content_change" | "domain_removed" | "blacklist_hit" | "auth_failed" | "session_expired" | "new_private_page";
  alert_type_display: string;
  severity: "info" | "warning" | "critical";
  severity_display: string;
  message: string;
  domain_list: string[];
  is_read: boolean;
  created_at: string;
}

export interface MonitoringSummary {
  total_external_domains: number;
  new_domains: number;
  suspicious_domains: number;
  safe_domains: number;
  unread_alerts: number;
  total_alerts: number;
  whitelist_domains: number;
  blacklist_domains: number;
  unknown_domains: number;
}

export interface MonitoringData {
  summary: MonitoringSummary;
  reputation_summary?: ReputationSummary;
  domains: ExternalDomainEntryWithReputation[];
  alerts: ExternalDomainAlertItem[];
}

export interface DomainReputation {
  id: number;
  domain: string;
  risk_level: "low" | "medium" | "high" | "unknown";
  check_status: "pending" | "checking" | "completed" | "failed";
  safe_browsing_result: Record<string, any>;
  safe_browsing_risk: "low" | "medium" | "high" | "unknown";
  virustotal_stats: Record<string, any>;
  virustotal_risk: "low" | "medium" | "high" | "unknown";
  virustotal_malicious: number;
  virustotal_suspicious: number;
  virustotal_harmless: number;
  virustotal_undetected: number;
  checked_at: string | null;
  error_message: string;
  check_count: number;
  is_cache_valid: boolean;
  created_at: string;
  updated_at: string;
}

export interface ExternalDomainEntryWithReputation extends ExternalDomainEntry {
  reputation?: DomainReputation | null;
}

export interface ReputationSummary {
  total: number;
  high_risk: number;
  medium_risk: number;
  low_risk: number;
  unknown_risk: number;
  pending: number;
  checking: number;
  completed: number;
  failed: number;
}

export interface ReputationListResponse {
  summary: ReputationSummary;
  results: DomainReputation[];
}

export interface TimelineEntry {
  domain: string;
  first_seen: string;
  last_seen: string;
  status: string;
  is_suspicious: boolean;
  suspicious_reasons: string[];
  times_seen: number;
  scan_id: number | null;
}

export interface DomainDetail {
  entry: ExternalDomainEntry;
  urls: { url: string; source: string; status_code: number | null; source_url: string; scan_id: number }[];
  alerts: ExternalDomainAlertItem[];
}

// ─── Real-Time Monitoring Types ─────────────────────────────────────────────

// ─── Blacklist / Whitelist Types ────────────────────────────────────────────

export interface DomainListEntry {
  id: number;
  site_domain: string;
  domain: string;
  list_type: "whitelist" | "blacklist";
  note: string;
  added_by: string;
  created_at: string;
}

export interface DomainListsResponse {
  site_domain: string;
  whitelist: DomainListEntry[];
  blacklist: DomainListEntry[];
  classification: {
    total: number;
    whitelist: number;
    blacklist: number;
    unknown: number;
  };
}

export interface DomainListAddResponse {
  status: string;
  created: string[];
  skipped: string[];
  moved_from_opposite: string[];
  total_created: number;
}

export interface DomainListQuickActionResponse {
  status: string;
  entry: DomainListEntry;
  created: boolean;
}

export interface DomainListSuggestion {
  domain: string;
  times_seen: number;
  first_seen: string;
  status: string;
}

// ─── Real-Time Monitoring Types (continued) ─────────────────────────────────

export interface LightScanResultCompact {
  id: number;
  has_changes: boolean;
  new_domains_count: number;
  removed_domains_count: number;
  pages_checked: number;
  scan_duration: number;
  created_at: string;
}

export interface SiteMonitorConfig {
  id: number;
  domain: string;
  is_enabled: boolean;
  interval_minutes: number;
  key_pages: string[];
  last_content_hash: string;
  last_scan_at: string | null;
  next_scan_at: string | null;
  total_light_scans: number;
  changes_detected_count: number;
  consecutive_errors: number;
  last_error: string;
  is_due: boolean;
  light_scans_count: number;
  last_result: LightScanResultCompact | null;
  created_at: string;
  updated_at: string;
}

export interface LightScanResult {
  id: number;
  domain: string;
  content_hash: string;
  previous_hash: string;
  has_changes: boolean;
  pages_checked: number;
  pages_data: { url: string; status_code: number; hash: string; has_content: boolean; error: string }[];
  external_domains_snapshot: string[];
  new_domains: string[];
  removed_domains: string[];
  new_domains_count: number;
  removed_domains_count: number;
  reputation_enqueued: boolean;
  scan_duration: number;
  error: string;
  created_at: string;
}

export interface RealtimeMonitoringStatus {
  total_configs: number;
  active_configs: number;
  total_light_scans: number;
  total_changes_detected: number;
  total_new_domains_found: number;
  configs: SiteMonitorConfig[];
}

export interface RealtimeHistoryResponse {
  domain: string;
  total: number;
  results: LightScanResult[];
}

// ─── Site Auth Config Types ─────────────────────────────────────────────

export interface SiteAuthConfig {
  id: number;
  domain: string;
  auth_type: "none" | "form" | "cookie" | "interactive" | "recorded";
  auth_strategy: "auto" | "http_only" | "playwright_only";
  is_enabled: boolean;
  login_url: string;
  username: string;
  has_password: boolean;
  username_selector: string;
  password_selector: string;
  submit_selector: string;
  login_button_selector: string;
  home_url: string;
  recorded_steps: RecordedStep[];
  cookie_value: string;
  auth_status: "untested" | "success" | "failed";
  last_test_at: string | null;
  last_error: string;
  session_valid_until: string | null;
  created_at: string;
  updated_at: string;
}

export interface RecordedStep {
  action: "goto" | "click" | "type" | "select" | "wait" | "press" | "check" | "wait_for";
  selector?: string;
  value?: string;
  wait_ms?: number;
  description?: string;
}

export interface AuthTestResult {
  status: "success" | "failed";
  message: string;
  method?: string;
  pages_accessible?: number;
  accessible_paths?: string[];
  login_redirects?: string[];
  cookies_count?: number;
  warning?: string;
  playwright_available?: boolean;
  needs_selectors?: boolean;
}

export interface DetectedField {
  tag: string;
  type: string;
  name: string;
  id: string;
  placeholder?: string;
  aria_label?: string;
  autocomplete?: string;
  required?: boolean;
  text?: string;
  css_selector: string;
}

export interface DetectFieldsResult {
  login_url: string;
  success: boolean;
  fields: DetectedField[];
  forms_count: number;
  detected_username_field: string | null;
  detected_password_field: string | null;
  detected_submit: string | null;
  suggested_username_selector: string;
  suggested_password_selector: string;
  suggested_submit_selector: string;
  error?: string;
}

export interface AuthDebugStep {
  step: string;
  status: "ok" | "warning" | "failed";
  detail: string;
  data?: any;
}

export interface AuthDebugResult {
  steps: AuthDebugStep[];
  step_results?: AuthDebugStep[];
  success: boolean;
  result?: any;
  error?: string;
}

export interface AuthStabilityScore {
  score: number | null;
  label?: string;
  reason?: string;
  auth_status?: string;
  auth_failed_count?: number;
  session_expired_count?: number;
  total_scans_period?: number;
  period_days?: number;
}

export interface RecordingSession {
  success: boolean;
  session_id?: string;
  status?: string;
  novnc_url?: string;
  domain?: string;
  start_url?: string;
  error?: string;
}

export interface RecordingStatus {
  active: boolean;
  session_id?: string;
  status?: string;
  domain?: string;
  elapsed?: number;
  timeout?: number;
  events_count?: number;
  error?: string;
}

export interface RecordingStopResult {
  success: boolean;
  session_id?: string;
  steps?: RecordedStep[];
  total_steps?: number;
  duration?: number;
  error?: string;
}

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = JSON.stringify(body);
    } catch {}
    throw new Error(`API error: ${res.status} ${res.statusText}${detail ? " — " + detail : ""}`);
  }

  return res.json();
}

export const api = {
  // Dashboard
  getDashboardStats: () =>
    fetchJSON<DashboardStats>(`${API_BASE}/dashboard/`),

  getDomains: () =>
    fetchJSON<DomainStats[]>(`${API_BASE}/domains/`),

  // Scans
  getScans: (params?: Record<string, string>) => {
    const query = params ? "?" + new URLSearchParams(params).toString() : "";
    return fetchJSON<PaginatedResponse<Scan>>(`${API_BASE}/scans/${query}`);
  },

  getScan: (id: number) =>
    fetchJSON<Scan>(`${API_BASE}/scans/${id}/`),

  createScan: (data: { domain: string; max_depth?: number; max_pages?: number }) =>
    fetchJSON<Scan>(`${API_BASE}/scans/`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  rescan: (id: number) =>
    fetchJSON<Scan>(`${API_BASE}/scans/${id}/rescan/`, {
      method: "POST",
    }),

  // URLs
  getScanUrls: (scanId: number, params?: Record<string, string>) => {
    const query = params ? "?" + new URLSearchParams(params).toString() : "";
    return fetchJSON<PaginatedResponse<DiscoveredURL>>(
      `${API_BASE}/scans/${scanId}/urls/${query}`
    );
  },

  getScanUrlSummary: (scanId: number) =>
    fetchJSON<URLSummary>(`${API_BASE}/scans/${scanId}/url_summary/`),

  // External domains
  getExternalDomains: (scanId: number, expand = false) => {
    const query = expand ? "?expand=true" : "";
    return fetchJSON<ExternalDomainGroup[]>(
      `${API_BASE}/scans/${scanId}/external_domains/${query}`
    );
  },

  // Diff
  getScanDiff: (scanId: number) =>
    fetchJSON<ScanDiff[]>(`${API_BASE}/scans/${scanId}/diff/`),

  // Load more (pagination)
  fetchNextPage: <T>(url: string) =>
    fetchJSON<PaginatedResponse<T>>(url),

  // External Monitoring
  getMonitoringData: (domain?: string) => {
    const query = domain ? `?domain=${encodeURIComponent(domain)}` : "";
    return fetchJSON<MonitoringData>(`${API_BASE}/monitoring/${query}`);
  },

  getMonitoringTimeline: (domain: string) =>
    fetchJSON<TimelineEntry[]>(
      `${API_BASE}/monitoring/timeline/?domain=${encodeURIComponent(domain)}`
    ),

  getMonitoringDomainDetail: (domain: string, siteDomain: string) =>
    fetchJSON<DomainDetail>(
      `${API_BASE}/monitoring/domain/${encodeURIComponent(domain)}/?site_domain=${encodeURIComponent(siteDomain)}`
    ),

  markAlertsRead: (data: { alert_ids?: number[]; site_domain?: string }) =>
    fetchJSON<{ status: string }>(`${API_BASE}/monitoring/alerts/read/`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  markDomainSafe: (siteDomain: string, domain: string) =>
    fetchJSON<ExternalDomainEntry>(
      `${API_BASE}/monitoring/domain/safe/`,
      {
        method: "POST",
        body: JSON.stringify({ site_domain: siteDomain, domain }),
      }
    ),

  // Reputation
  getReputationList: (siteDomain?: string) => {
    const query = siteDomain
      ? `?site_domain=${encodeURIComponent(siteDomain)}`
      : "";
    return fetchJSON<ReputationListResponse>(
      `${API_BASE}/monitoring/reputation/${query}`
    );
  },

  checkReputation: (data: { domain: string; force?: boolean }) =>
    fetchJSON<DomainReputation | { status: string; domain: string }>(
      `${API_BASE}/monitoring/reputation/check/`,
      {
        method: "POST",
        body: JSON.stringify(data),
      }
    ),

  checkAllReputations: (siteDomain?: string) =>
    fetchJSON<{ status: string; queued: number }>(
      `${API_BASE}/monitoring/reputation/check-all/`,
      {
        method: "POST",
        body: JSON.stringify(
          siteDomain ? { site_domain: siteDomain } : {}
        ),
      }
    ),

  // ─── Real-Time Monitoring ───────────────────────────────────────────────

  // ─── Blacklist / Whitelist ──────────────────────────────────────────────

  getDomainLists: (siteDomain: string) =>
    fetchJSON<DomainListsResponse>(
      `${API_BASE}/monitoring/lists/?site_domain=${encodeURIComponent(siteDomain)}`
    ),

  addToDomainList: (data: {
    site_domain: string;
    domains: string[];
    list_type: "whitelist" | "blacklist";
    note?: string;
  }) =>
    fetchJSON<DomainListAddResponse>(
      `${API_BASE}/monitoring/lists/add/`,
      {
        method: "POST",
        body: JSON.stringify(data),
      }
    ),

  removeFromDomainList: (entryId: number) =>
    fetch(`${API_BASE}/monitoring/lists/${entryId}/remove/`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
    }),

  domainListQuickAction: (data: {
    site_domain: string;
    domain: string;
    list_type: "whitelist" | "blacklist";
  }) =>
    fetchJSON<DomainListQuickActionResponse>(
      `${API_BASE}/monitoring/lists/quick-action/`,
      {
        method: "POST",
        body: JSON.stringify(data),
      }
    ),

  clearDomainList: (siteDomain: string, listType: "whitelist" | "blacklist") =>
    fetchJSON<{ status: string; deleted: number }>(
      `${API_BASE}/monitoring/lists/clear/`,
      {
        method: "POST",
        body: JSON.stringify({ site_domain: siteDomain, list_type: listType }),
      }
    ),

  getDomainListSuggestions: (siteDomain: string) =>
    fetchJSON<{ suggestions: DomainListSuggestion[] }>(
      `${API_BASE}/monitoring/lists/suggestions/?site_domain=${encodeURIComponent(siteDomain)}`
    ),

  // ─── Real-Time Monitoring (continued) ───────────────────────────────────

  getRealtimeStatus: () =>
    fetchJSON<RealtimeMonitoringStatus>(
      `${API_BASE}/monitoring/realtime/`
    ),

  createMonitorConfig: (data: {
    domain: string;
    is_enabled?: boolean;
    interval_minutes?: number;
    key_pages?: string[];
  }) =>
    fetchJSON<SiteMonitorConfig>(
      `${API_BASE}/monitoring/realtime/create/`,
      {
        method: "POST",
        body: JSON.stringify(data),
      }
    ),

  getMonitorConfig: (configId: number) =>
    fetchJSON<SiteMonitorConfig>(
      `${API_BASE}/monitoring/realtime/${configId}/`
    ),

  updateMonitorConfig: (
    configId: number,
    data: Partial<{ is_enabled: boolean; interval_minutes: number; key_pages: string[] }>
  ) =>
    fetchJSON<SiteMonitorConfig>(
      `${API_BASE}/monitoring/realtime/${configId}/`,
      {
        method: "PATCH",
        body: JSON.stringify(data),
      }
    ),

  deleteMonitorConfig: (configId: number) =>
    fetch(`${API_BASE}/monitoring/realtime/${configId}/`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
    }),

  toggleMonitoring: (configId: number) =>
    fetchJSON<SiteMonitorConfig>(
      `${API_BASE}/monitoring/realtime/${configId}/toggle/`,
      { method: "POST" }
    ),

  scanNow: (configId: number) =>
    fetchJSON<{ status: string; domain: string }>(
      `${API_BASE}/monitoring/realtime/${configId}/scan-now/`,
      { method: "POST" }
    ),

  getMonitorHistory: (configId: number, limit = 50) =>
    fetchJSON<RealtimeHistoryResponse>(
      `${API_BASE}/monitoring/realtime/${configId}/history/?limit=${limit}`
    ),

  getLatestLightScans: (limit = 20) =>
    fetchJSON<{ results: LightScanResult[] }>(
      `${API_BASE}/monitoring/realtime/latest/?limit=${limit}`
    ),

  // ─── Site Auth Config ─────────────────────────────────────────────────

  getAuthConfig: (domain: string) =>
    fetchJSON<SiteAuthConfig>(
      `${API_BASE}/auth/config/?domain=${encodeURIComponent(domain)}`
    ),

  saveAuthConfig: (data: {
    domain: string;
    auth_type: "none" | "form" | "cookie" | "interactive" | "recorded";
    auth_strategy?: "auto" | "http_only" | "playwright_only";
    is_enabled?: boolean;
    login_url?: string;
    username?: string;
    password?: string;
    username_selector?: string;
    password_selector?: string;
    submit_selector?: string;
    login_button_selector?: string;
    home_url?: string;
    recorded_steps?: RecordedStep[];
    cookie_value?: string;
  }) =>
    fetchJSON<SiteAuthConfig>(`${API_BASE}/auth/config/save/`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  testAuthConfig: async (data: {
    domain: string;
    auth_type: "form" | "cookie" | "interactive" | "recorded";
    login_url?: string;
    username?: string;
    password?: string;
    username_selector?: string;
    password_selector?: string;
    submit_selector?: string;
    cookie_value?: string;
  }): Promise<AuthTestResult> => {
    const res = await fetch(`${API_BASE}/auth/config/test/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    return res.json();
  },

  deleteAuthConfig: (domain: string) =>
    fetch(`${API_BASE}/auth/config/delete/`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ domain }),
    }),

  detectAuthFields: async (login_url: string): Promise<DetectFieldsResult> => {
    const res = await fetch(`${API_BASE}/auth/detect-fields/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ login_url }),
    });
    return res.json();
  },

  debugAuthLogin: async (domain: string): Promise<AuthDebugResult> => {
    const res = await fetch(`${API_BASE}/auth/debug/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ domain }),
    });
    return res.json();
  },

  getAuthStability: (domain: string) =>
    fetchJSON<AuthStabilityScore>(
      `${API_BASE}/auth/stability/?domain=${encodeURIComponent(domain)}`
    ),

  // ─── Recorder ─────────────────────────────────────────────────────────

  startRecording: (data: { domain: string; start_url?: string }) =>
    fetchJSON<RecordingSession>(`${API_BASE}/auth/record/start/`, {
      method: "POST",
      body: JSON.stringify(data),
    }).catch((err) => {
      // fetchJSON throws on non-2xx, but we want the error body
      return err.message?.includes("API error")
        ? fetch(`${API_BASE}/auth/record/start/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
          }).then((r) => r.json())
        : { success: false, error: err.message };
    }),

  stopRecording: (session_id: string) =>
    fetchJSON<RecordingStopResult>(`${API_BASE}/auth/record/stop/`, {
      method: "POST",
      body: JSON.stringify({ session_id }),
    }).catch((err) =>
      fetch(`${API_BASE}/auth/record/stop/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id }),
      }).then((r) => r.json())
    ),

  getRecordingStatus: (session_id?: string) => {
    const query = session_id ? `?session_id=${encodeURIComponent(session_id)}` : "";
    return fetchJSON<RecordingStatus>(
      `${API_BASE}/auth/record/status/${query}`
    );
  },

  // ── Scanner Logs ──────────────────────────────────────────────────────
  getScannerLogs: async (
    file: string = "scanner",
    lines: number = 500,
    level?: string
  ): Promise<{ file: string; count: number; entries: Array<{ timestamp?: string; level?: string; module?: string; message?: string; raw?: string }> }> => {
    const params = new URLSearchParams({ file, lines: String(lines) });
    if (level) params.set("level", level);
    const res = await fetch(`${API_BASE}/logs/?${params.toString()}`);
    return res.json();
  },

  getScannerLogFiles: async (): Promise<{ files: Array<{ name: string; size: number; size_human: string; modified: number }> }> => {
    const res = await fetch(`${API_BASE}/logs/files/`);
    return res.json();
  },

  clearScannerLog: async (file: string = "scanner"): Promise<{ status: string }> => {
    const res = await fetch(`${API_BASE}/logs/clear/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file }),
    });
    return res.json();
  },
};
