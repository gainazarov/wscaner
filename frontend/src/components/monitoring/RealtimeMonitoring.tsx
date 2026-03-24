"use client";

import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Check,
  ChevronDown,
  ChevronRight,
  Clock,
  Globe,
  Loader2,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Settings,
  Trash2,
  TrendingUp,
  X,
  Zap,
} from "lucide-react";
import {
  api,
  SiteMonitorConfig,
  LightScanResult,
  RealtimeMonitoringStatus,
  DomainStats,
} from "@/lib/api";

export function RealtimeMonitoring() {
  const [status, setStatus] = useState<RealtimeMonitoringStatus | null>(null);
  const [domains, setDomains] = useState<DomainStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [expandedConfig, setExpandedConfig] = useState<number | null>(null);
  const [history, setHistory] = useState<LightScanResult[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const loadStatus = useCallback(async () => {
    try {
      const [statusData, domainStats] = await Promise.all([
        api.getRealtimeStatus(),
        api.getDomains(),
      ]);
      setStatus(statusData);
      setDomains(domainStats);
    } catch (err) {
      console.error("Failed to load realtime monitoring status:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 30000); // refresh every 30s
    return () => clearInterval(interval);
  }, [loadStatus]);

  const handleToggle = async (configId: number) => {
    try {
      await api.toggleMonitoring(configId);
      loadStatus();
    } catch (err) {
      console.error("Failed to toggle monitoring:", err);
    }
  };

  const handleScanNow = async (configId: number) => {
    try {
      await api.scanNow(configId);
      setTimeout(loadStatus, 3000);
    } catch (err) {
      console.error("Failed to trigger scan:", err);
    }
  };

  const handleDelete = async (configId: number) => {
    if (!confirm("Delete this monitoring configuration?")) return;
    try {
      await api.deleteMonitorConfig(configId);
      loadStatus();
    } catch (err) {
      console.error("Failed to delete config:", err);
    }
  };

  const loadHistory = async (configId: number) => {
    if (expandedConfig === configId) {
      setExpandedConfig(null);
      setHistory([]);
      return;
    }
    setExpandedConfig(configId);
    setHistoryLoading(true);
    try {
      const data = await api.getMonitorHistory(configId, 20);
      setHistory(data.results);
    } catch (err) {
      console.error("Failed to load history:", err);
    } finally {
      setHistoryLoading(false);
    }
  };

  if (loading && !status) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
        >
          <RefreshCw className="w-8 h-8 text-primary-500" />
        </motion.div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-dark-100 flex items-center gap-2">
            <Activity className="w-6 h-6 text-green-400" />
            Real-Time Monitoring
          </h2>
          <p className="text-dark-400 text-sm mt-1">
            Automated light scans every 15 minutes — detects content changes &amp; new external domains
          </p>
        </div>
        <div className="flex items-center gap-3">
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => setShowCreateForm(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary-500/20 text-primary-400 border border-primary-500/30 hover:bg-primary-500/30 text-sm font-medium transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Site
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={loadStatus}
            className="p-2 rounded-lg bg-dark-800 border border-dark-700 text-dark-400 hover:text-primary-400 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </motion.button>
        </div>
      </div>

      {/* Stats Summary */}
      {status && <StatsSummary status={status} />}

      {/* Create Form Modal */}
      <AnimatePresence>
        {showCreateForm && (
          <CreateConfigForm
            domains={domains}
            onClose={() => setShowCreateForm(false)}
            onCreated={() => {
              setShowCreateForm(false);
              loadStatus();
            }}
          />
        )}
      </AnimatePresence>

      {/* Config Cards */}
      {status && status.configs.length === 0 ? (
        <EmptyState onAdd={() => setShowCreateForm(true)} />
      ) : (
        <div className="space-y-4">
          {status?.configs.map((config) => (
            <ConfigCard
              key={config.id}
              config={config}
              isExpanded={expandedConfig === config.id}
              history={expandedConfig === config.id ? history : []}
              historyLoading={historyLoading && expandedConfig === config.id}
              onToggle={() => handleToggle(config.id)}
              onScanNow={() => handleScanNow(config.id)}
              onDelete={() => handleDelete(config.id)}
              onExpand={() => loadHistory(config.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Stats Summary ──────────────────────────────────────────────────────────

function StatsSummary({ status }: { status: RealtimeMonitoringStatus }) {
  const cards = [
    {
      label: "Monitored Sites",
      value: status.total_configs,
      icon: <Globe className="w-5 h-5" />,
      color: "text-blue-400",
      bg: "bg-blue-500/10",
    },
    {
      label: "Active",
      value: status.active_configs,
      icon: <Activity className="w-5 h-5" />,
      color: "text-green-400",
      bg: "bg-green-500/10",
    },
    {
      label: "Total Scans",
      value: status.total_light_scans,
      icon: <Zap className="w-5 h-5" />,
      color: "text-purple-400",
      bg: "bg-purple-500/10",
    },
    {
      label: "Changes Detected",
      value: status.total_changes_detected,
      icon: <AlertTriangle className="w-5 h-5" />,
      color: "text-orange-400",
      bg: "bg-orange-500/10",
    },
    {
      label: "New Domains Found",
      value: status.total_new_domains_found,
      icon: <TrendingUp className="w-5 h-5" />,
      color: "text-red-400",
      bg: "bg-red-500/10",
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
      {cards.map((card, i) => (
        <motion.div
          key={card.label}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.08 }}
          className="bg-dark-800/60 backdrop-blur-sm border border-dark-700/50 rounded-xl p-4"
        >
          <div className="flex items-center justify-between mb-2">
            <div className={`p-2 rounded-lg ${card.bg}`}>
              <div className={card.color}>{card.icon}</div>
            </div>
            <span className={`text-2xl font-bold ${card.color}`}>
              {card.value}
            </span>
          </div>
          <p className="text-xs text-dark-400">{card.label}</p>
        </motion.div>
      ))}
    </div>
  );
}

// ─── Empty State ────────────────────────────────────────────────────────────

function EmptyState({ onAdd }: { onAdd: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="text-center py-16 bg-dark-800/40 backdrop-blur-sm border border-dark-700/50 rounded-2xl"
    >
      <Activity className="w-16 h-16 mx-auto mb-4 text-dark-600" />
      <h3 className="text-lg font-semibold text-dark-300 mb-2">
        No sites being monitored
      </h3>
      <p className="text-dark-500 text-sm mb-6 max-w-md mx-auto">
        Add a site to start real-time monitoring. Light scans run every 15 minutes
        to detect content changes and new external domains.
      </p>
      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={onAdd}
        className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-primary-500/20 text-primary-400 border border-primary-500/30 hover:bg-primary-500/30 font-medium transition-colors"
      >
        <Plus className="w-5 h-5" />
        Add Your First Site
      </motion.button>
    </motion.div>
  );
}

// ─── Create Config Form ─────────────────────────────────────────────────────

function CreateConfigForm({
  domains,
  onClose,
  onCreated,
}: {
  domains: DomainStats[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const [domain, setDomain] = useState("");
  const [interval, setInterval] = useState(15);
  const [keyPages, setKeyPages] = useState("/\n/login\n/checkout");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setError("");

    try {
      await api.createMonitorConfig({
        domain: domain.trim().toLowerCase(),
        is_enabled: true,
        interval_minutes: interval,
        key_pages: keyPages
          .split("\n")
          .map((p) => p.trim())
          .filter(Boolean),
      });
      onCreated();
    } catch (err: any) {
      const msg = err?.message || "Failed to create monitoring config";
      setError(msg);
    } finally {
      setCreating(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        className="bg-dark-900 border border-dark-700 rounded-2xl p-6 w-full max-w-md"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold text-dark-100 flex items-center gap-2">
            <Plus className="w-5 h-5 text-primary-400" />
            Add Monitoring Site
          </h3>
          <button onClick={onClose} className="text-dark-500 hover:text-dark-300">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Domain */}
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">Domain</label>
            {domains.length > 0 ? (
              <select
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2.5 text-sm text-dark-200 focus:border-primary-500 focus:outline-none"
                required
              >
                <option value="">Select a scanned domain…</option>
                {domains.map((d) => (
                  <option key={d.domain} value={d.domain}>
                    {d.domain}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                placeholder="example.com"
                className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2.5 text-sm text-dark-200 placeholder-dark-500 focus:border-primary-500 focus:outline-none"
                required
              />
            )}
          </div>

          {/* Interval */}
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Scan Interval (minutes)
            </label>
            <div className="flex items-center gap-3">
              {[5, 15, 30, 60].map((v) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => setInterval(v)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                    interval === v
                      ? "bg-primary-500/20 text-primary-400 border border-primary-500/30"
                      : "bg-dark-800 text-dark-400 border border-dark-700 hover:text-dark-200"
                  }`}
                >
                  {v}m
                </button>
              ))}
            </div>
          </div>

          {/* Key Pages */}
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Key Pages (one per line)
            </label>
            <textarea
              value={keyPages}
              onChange={(e) => setKeyPages(e.target.value)}
              rows={4}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2.5 text-sm text-dark-200 placeholder-dark-500 focus:border-primary-500 focus:outline-none font-mono"
              placeholder={"/\n/login\n/checkout\n/account"}
            />
            <p className="text-xs text-dark-500 mt-1">
              These pages will be fetched and hashed each scan cycle
            </p>
          </div>

          {error && (
            <p className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <div className="flex items-center gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2.5 rounded-lg bg-dark-800 border border-dark-700 text-dark-400 text-sm font-medium hover:text-dark-200 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={creating || !domain}
              className="flex-1 px-4 py-2.5 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
            >
              {creating ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Plus className="w-4 h-4" />
              )}
              {creating ? "Creating..." : "Start Monitoring"}
            </button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  );
}

// ─── Config Card ────────────────────────────────────────────────────────────

function ConfigCard({
  config,
  isExpanded,
  history,
  historyLoading,
  onToggle,
  onScanNow,
  onDelete,
  onExpand,
}: {
  config: SiteMonitorConfig;
  isExpanded: boolean;
  history: LightScanResult[];
  historyLoading: boolean;
  onToggle: () => void;
  onScanNow: () => void;
  onDelete: () => void;
  onExpand: () => void;
}) {
  const formatTime = (iso: string | null) => {
    if (!iso) return "—";
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return "just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24) return `${diffH}h ago`;
    return d.toLocaleDateString();
  };

  const timeUntilNext = (iso: string | null) => {
    if (!iso) return "pending";
    const d = new Date(iso);
    const now = new Date();
    const diffMs = d.getTime() - now.getTime();
    if (diffMs <= 0) return "due now";
    const diffMin = Math.ceil(diffMs / 60000);
    if (diffMin < 60) return `in ${diffMin}m`;
    const diffH = Math.floor(diffMin / 60);
    return `in ${diffH}h ${diffMin % 60}m`;
  };

  const hasError = config.consecutive_errors > 0;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`bg-dark-800/60 backdrop-blur-sm border rounded-xl overflow-hidden transition-colors ${
        hasError
          ? "border-red-500/30"
          : config.is_enabled
          ? "border-green-500/20"
          : "border-dark-700/50"
      }`}
    >
      {/* Header */}
      <div className="p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            {/* ON/OFF Toggle */}
            <button
              onClick={onToggle}
              className={`relative w-12 h-6 rounded-full transition-colors ${
                config.is_enabled ? "bg-green-500" : "bg-dark-600"
              }`}
            >
              <motion.div
                layout
                className="absolute top-0.5 w-5 h-5 bg-white rounded-full shadow-md"
                animate={{ left: config.is_enabled ? "26px" : "2px" }}
                transition={{ type: "spring", stiffness: 500, damping: 30 }}
              />
            </button>

            <div>
              <h3 className="text-base font-semibold text-dark-100 flex items-center gap-2">
                {config.domain}
                {config.is_enabled && (
                  <span className="flex items-center gap-1 text-xs text-green-400 bg-green-500/10 px-2 py-0.5 rounded-full">
                    <Activity className="w-3 h-3" />
                    Active
                  </span>
                )}
                {hasError && (
                  <span className="flex items-center gap-1 text-xs text-red-400 bg-red-500/10 px-2 py-0.5 rounded-full">
                    <AlertTriangle className="w-3 h-3" />
                    Error ({config.consecutive_errors})
                  </span>
                )}
              </h3>
              <p className="text-xs text-dark-500 mt-0.5">
                Every {config.interval_minutes}m · {config.key_pages.length || 7} pages ·{" "}
                {config.total_light_scans} scans
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={onScanNow}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-500/10 text-primary-400 border border-primary-500/20 text-xs font-medium hover:bg-primary-500/20 transition-colors"
              title="Run scan now"
            >
              <Zap className="w-3.5 h-3.5" />
              Scan Now
            </motion.button>
            <button
              onClick={onDelete}
              className="p-1.5 rounded-lg text-dark-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
              title="Delete config"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Status row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
          <div className="bg-dark-900/50 rounded-lg p-3">
            <p className="text-[10px] uppercase tracking-wider text-dark-500 mb-1">Last Scan</p>
            <p className="text-sm font-medium text-dark-200">
              {formatTime(config.last_scan_at)}
            </p>
          </div>
          <div className="bg-dark-900/50 rounded-lg p-3">
            <p className="text-[10px] uppercase tracking-wider text-dark-500 mb-1">Next Scan</p>
            <p className="text-sm font-medium text-dark-200">
              {config.is_enabled ? timeUntilNext(config.next_scan_at) : "paused"}
            </p>
          </div>
          <div className="bg-dark-900/50 rounded-lg p-3">
            <p className="text-[10px] uppercase tracking-wider text-dark-500 mb-1">Changes</p>
            <p className={`text-sm font-medium ${config.changes_detected_count > 0 ? "text-orange-400" : "text-dark-200"}`}>
              {config.changes_detected_count}
            </p>
          </div>
          <div className="bg-dark-900/50 rounded-lg p-3">
            <p className="text-[10px] uppercase tracking-wider text-dark-500 mb-1">Content Hash</p>
            <p className="text-sm font-mono text-dark-300 truncate" title={config.last_content_hash}>
              {config.last_content_hash ? `${config.last_content_hash.slice(0, 12)}…` : "—"}
            </p>
          </div>
        </div>

        {/* Last result compact */}
        {config.last_result && (
          <div className="mt-3 flex items-center gap-4 text-xs text-dark-400">
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {config.last_result.scan_duration.toFixed(1)}s
            </span>
            <span className="flex items-center gap-1">
              <Globe className="w-3 h-3" />
              {config.last_result.pages_checked} pages
            </span>
            {config.last_result.new_domains_count > 0 && (
              <span className="flex items-center gap-1 text-green-400">
                <TrendingUp className="w-3 h-3" />
                +{config.last_result.new_domains_count} new
              </span>
            )}
            {config.last_result.has_changes && (
              <span className="flex items-center gap-1 text-orange-400">
                <AlertTriangle className="w-3 h-3" />
                content changed
              </span>
            )}
          </div>
        )}

        {/* Error message */}
        {hasError && config.last_error && (
          <div className="mt-3 px-3 py-2 rounded-lg bg-red-500/5 border border-red-500/10 text-xs text-red-400">
            {config.last_error}
          </div>
        )}

        {/* Expand/collapse */}
        <button
          onClick={onExpand}
          className="mt-3 flex items-center gap-1 text-xs text-dark-500 hover:text-primary-400 transition-colors"
        >
          {isExpanded ? (
            <>
              <ChevronDown className="w-3.5 h-3.5" />
              Hide scan history
            </>
          ) : (
            <>
              <ChevronRight className="w-3.5 h-3.5" />
              View scan history ({config.light_scans_count || config.total_light_scans} scans)
            </>
          )}
        </button>
      </div>

      {/* History */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-t border-dark-700/50 overflow-hidden"
          >
            <div className="p-4 space-y-2">
              {historyLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-5 h-5 animate-spin text-primary-500" />
                </div>
              ) : history.length === 0 ? (
                <p className="text-center py-6 text-dark-500 text-sm">
                  No scan results yet
                </p>
              ) : (
                history.map((result) => (
                  <HistoryRow key={result.id} result={result} />
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ─── History Row ────────────────────────────────────────────────────────────

function HistoryRow({ result }: { result: LightScanResult }) {
  const [expanded, setExpanded] = useState(false);

  const time = new Date(result.created_at);
  const timeStr = time.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className="bg-dark-900/50 rounded-lg border border-dark-700/30">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-3 text-left"
      >
        <div className="flex items-center gap-3">
          <div
            className={`w-2 h-2 rounded-full ${
              result.has_changes ? "bg-orange-400" : "bg-green-400"
            }`}
          />
          <span className="text-xs text-dark-300">{timeStr}</span>
          <span className="text-xs text-dark-500">
            {result.pages_checked} pages · {result.scan_duration.toFixed(1)}s
          </span>
        </div>
        <div className="flex items-center gap-2">
          {result.new_domains_count > 0 && (
            <span className="text-xs text-green-400 bg-green-500/10 px-1.5 py-0.5 rounded-full">
              +{result.new_domains_count}
            </span>
          )}
          {result.removed_domains_count > 0 && (
            <span className="text-xs text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded-full">
              −{result.removed_domains_count}
            </span>
          )}
          {result.has_changes && (
            <span className="text-xs text-orange-400 bg-orange-500/10 px-1.5 py-0.5 rounded-full">
              changed
            </span>
          )}
          {result.reputation_enqueued && (
            <span className="text-xs text-purple-400 bg-purple-500/10 px-1.5 py-0.5 rounded-full">
              rep queued
            </span>
          )}
          <ChevronDown
            className={`w-3.5 h-3.5 text-dark-500 transition-transform ${
              expanded ? "rotate-180" : ""
            }`}
          />
        </div>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-t border-dark-700/30 overflow-hidden"
          >
            <div className="p-3 space-y-3">
              {/* Hash info */}
              <div className="flex items-center gap-4 text-xs">
                <span className="text-dark-500">Hash:</span>
                <code className="text-dark-300 font-mono">
                  {result.content_hash.slice(0, 16)}
                </code>
                {result.previous_hash && result.previous_hash !== result.content_hash && (
                  <>
                    <span className="text-dark-600">←</span>
                    <code className="text-dark-500 font-mono">
                      {result.previous_hash.slice(0, 16)}
                    </code>
                  </>
                )}
              </div>

              {/* New domains */}
              {result.new_domains.length > 0 && (
                <div>
                  <p className="text-xs text-green-400 font-medium mb-1">
                    New domains ({result.new_domains.length}):
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {result.new_domains.map((d) => (
                      <span
                        key={d}
                        className="text-xs bg-green-500/10 text-green-400 px-2 py-0.5 rounded-full border border-green-500/20"
                      >
                        {d}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Removed domains */}
              {result.removed_domains.length > 0 && (
                <div>
                  <p className="text-xs text-red-400 font-medium mb-1">
                    Removed domains ({result.removed_domains.length}):
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {result.removed_domains.map((d) => (
                      <span
                        key={d}
                        className="text-xs bg-red-500/10 text-red-400 px-2 py-0.5 rounded-full border border-red-500/20"
                      >
                        {d}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Pages data */}
              {result.pages_data.length > 0 && (
                <div>
                  <p className="text-xs text-dark-400 font-medium mb-1">Pages checked:</p>
                  <div className="space-y-1">
                    {result.pages_data.map((page, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-2 text-xs"
                      >
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${
                            page.status_code === 200
                              ? "bg-green-400"
                              : page.status_code === 0
                              ? "bg-red-400"
                              : "bg-yellow-400"
                          }`}
                        />
                        <span className="text-dark-400 font-mono truncate flex-1">
                          {page.url.replace(/^https?:\/\/[^/]+/, "")}
                        </span>
                        <span className="text-dark-500">
                          {page.status_code || "err"}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Error */}
              {result.error && (
                <p className="text-xs text-red-400 bg-red-500/5 px-2 py-1 rounded">
                  {result.error}
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
