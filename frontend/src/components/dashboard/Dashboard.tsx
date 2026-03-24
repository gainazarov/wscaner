"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Globe,
  Link2,
  Activity,
  Plus,
  Search,
  ArrowRight,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  ExternalLink,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  Eye,
  Zap,
  TrendingUp,
  Copy,
  Check,
  X,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, DashboardStats, Scan, MonitoringData } from "@/lib/api";

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08 },
  },
};

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0 },
};

export function Dashboard() {
  const router = useRouter();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [scans, setScans] = useState<Scan[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNewScan, setShowNewScan] = useState(false);
  const [domain, setDomain] = useState("");
  const [maxDepth, setMaxDepth] = useState(3);
  const [maxPages, setMaxPages] = useState(500);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [creating, setCreating] = useState(false);
  const [monitoring, setMonitoring] = useState<MonitoringData | null>(null);
  const [whitelistDomains, setWhitelistDomains] = useState<string[]>([]);
  const [blacklistDomains, setBlacklistDomains] = useState<string[]>([]);
  const [whitelistInput, setWhitelistInput] = useState("");
  const [blacklistInput, setBlacklistInput] = useState("");

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    try {
      const [statsData, monitoringData] = await Promise.all([
        api.getDashboardStats(),
        api.getMonitoringData().catch(() => null),
      ]);
      setStats(statsData);
      setScans(statsData.recent_scans || []);
      setMonitoring(monitoringData);
    } catch (err) {
      console.error("Failed to load dashboard:", err);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateScan(e: React.FormEvent) {
    e.preventDefault();
    if (!domain.trim()) return;

    setCreating(true);
    try {
      const siteDomain = domain.trim();
      const newScan = await api.createScan({
        domain: siteDomain,
        max_depth: maxDepth,
        max_pages: maxPages,
      });

      // Submit whitelist/blacklist domains if any
      if (whitelistDomains.length > 0) {
        await api.addToDomainList({
          site_domain: siteDomain,
          domains: whitelistDomains,
          list_type: "whitelist",
          note: "Added during scan creation",
        }).catch(console.error);
      }
      if (blacklistDomains.length > 0) {
        await api.addToDomainList({
          site_domain: siteDomain,
          domains: blacklistDomains,
          list_type: "blacklist",
          note: "Added during scan creation",
        }).catch(console.error);
      }

      setDomain("");
      setWhitelistDomains([]);
      setBlacklistDomains([]);
      setShowNewScan(false);
      router.push(`/scan/${newScan.id}`);
    } catch (err) {
      console.error("Failed to create scan:", err);
    } finally {
      setCreating(false);
    }
  }

  const statusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />;
      case "running":
        return <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin" />;
      case "pending":
        return <Clock className="w-3.5 h-3.5 text-amber-400" />;
      case "failed":
        return <XCircle className="w-3.5 h-3.5 text-red-400" />;
      default:
        return null;
    }
  };

  const statusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
      case "running":
        return "bg-blue-500/10 text-blue-400 border-blue-500/20";
      case "pending":
        return "bg-amber-500/10 text-amber-400 border-amber-500/20";
      case "failed":
        return "bg-red-500/10 text-red-400 border-red-500/20";
      default:
        return "bg-dark-700 text-dark-400";
    }
  };

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="skeleton h-28 rounded-2xl" />
          ))}
        </div>
        <div className="skeleton h-16 rounded-2xl" />
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="skeleton h-20 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  function formatTimeAgo(dateStr: string): string {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return "just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  }

  function formatTimeUntil(dateStr: string): string {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = date.getTime() - now.getTime();
    if (diffMs <= 0) return "any moment";
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 60) return `in ${diffMins}m`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `in ${diffHours}h`;
    const diffDays = Math.floor(diffHours / 24);
    return `in ${diffDays}d`;
  }

  return (
    <motion.div variants={container} initial="hidden" animate="show" className="space-y-8">
      {/* Hero Stats */}
      <motion.div variants={item}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold">Dashboard</h1>
            <p className="text-dark-500 text-sm mt-1">Overview of your scanning activity</p>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs text-emerald-400 font-medium">System Online</span>
          </div>
        </div>
      </motion.div>

      {/* Stats Grid */}
      <motion.div variants={item} className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
        <StatCard
          icon={<Globe className="w-5 h-5" />}
          label="Domains"
          value={stats?.unique_domains || 0}
          color="primary"
        />
        <StatCard
          icon={<Link2 className="w-5 h-5" />}
          label="Total URLs"
          value={stats?.total_urls_discovered || 0}
          color="blue"
        />
        <StatCard
          icon={<ExternalLink className="w-5 h-5" />}
          label="External"
          value={stats?.external_urls || 0}
          color="orange"
        />
        <StatCard
          icon={<ShieldAlert className="w-5 h-5" />}
          label="Hidden (403)"
          value={stats?.hidden_urls || 0}
          color="red"
        />
      </motion.div>

      {/* Quick Stats Row */}
      <motion.div variants={item} className="flex items-center gap-3 overflow-x-auto pb-1">
        <QuickStat label="Active" value={stats?.active_scans || 0} icon={<Activity className="w-3.5 h-3.5" />} color="blue" />
        <QuickStat label="Completed" value={stats?.completed_scans || 0} icon={<CheckCircle2 className="w-3.5 h-3.5" />} color="green" />
        <QuickStat label="Total Scans" value={stats?.total_scans || 0} icon={<TrendingUp className="w-3.5 h-3.5" />} color="purple" />
      </motion.div>

      {/* Last Scan / Next Scan Info */}
      {(stats?.last_scan || stats?.next_scheduled_scan || stats?.active_scan || stats?.last_monitoring_scan) && (
        <motion.div variants={item}>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {/* Active Scan */}
            {stats?.active_scan && (
              <Link href={`/scan/${stats.active_scan.id}`}>
                <div className="bg-blue-500/5 border border-blue-500/20 rounded-xl p-4 hover:border-blue-500/40 transition-all cursor-pointer">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
                    <span className="text-xs font-medium text-blue-400 uppercase tracking-wider">Active Scan</span>
                  </div>
                  <p className="font-semibold text-dark-100 truncate">{stats.active_scan.domain}</p>
                  <p className="text-xs text-dark-500 mt-1">
                    {stats.active_scan.started_at
                      ? `Started ${formatTimeAgo(stats.active_scan.started_at)}`
                      : "Pending..."}
                  </p>
                </div>
              </Link>
            )}

            {/* Last Scan */}
            {stats?.last_scan && (
              <Link href={`/scan/${stats.last_scan.id}`}>
                <div className="bg-dark-800/40 border border-dark-700/40 rounded-xl p-4 hover:border-primary-500/30 transition-all cursor-pointer">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      {stats.last_scan.status === "completed" ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      ) : stats.last_scan.status === "failed" ? (
                        <XCircle className="w-3.5 h-3.5 text-red-400" />
                      ) : stats.last_scan.status === "running" ? (
                        <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin" />
                      ) : (
                        <Clock className="w-3.5 h-3.5 text-amber-400" />
                      )}
                      <span className="text-xs font-medium text-dark-400 uppercase tracking-wider">Последний скан</span>
                    </div>
                    {stats.last_scan.status && stats.last_scan.status !== "completed" && (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                        stats.last_scan.status === "failed" ? "bg-red-500/10 text-red-400" :
                        stats.last_scan.status === "running" ? "bg-blue-500/10 text-blue-400" :
                        "bg-amber-500/10 text-amber-400"
                      }`}>
                        {stats.last_scan.status === "failed" ? "Ошибка" :
                         stats.last_scan.status === "running" ? "В процессе" :
                         stats.last_scan.status}
                      </span>
                    )}
                  </div>
                  <p className="font-semibold text-dark-100 truncate">{stats.last_scan.domain}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <p className="text-xs text-dark-500">
                      {stats.last_scan.completed_at
                        ? formatTimeAgo(stats.last_scan.completed_at)
                        : stats.last_scan.started_at
                        ? `Начат ${formatTimeAgo(stats.last_scan.started_at)}`
                        : "Время неизвестно"}
                    </p>
                    {stats.last_scan.duration != null && stats.last_scan.duration > 0 && (
                      <span className="text-xs text-dark-600">· {stats.last_scan.duration.toFixed(0)}s</span>
                    )}
                    {stats.last_scan.total_urls > 0 && (
                      <span className="text-xs text-dark-600">· {stats.last_scan.total_urls} URLs</span>
                    )}
                  </div>
                </div>
              </Link>
            )}

            {/* Next Scheduled Scan */}
            {stats?.next_scheduled_scan && stats.next_scheduled_scan.next_scan_at && (
              <div className="bg-dark-800/40 border border-dark-700/40 rounded-xl p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Clock className="w-3.5 h-3.5 text-amber-400" />
                  <span className="text-xs font-medium text-dark-400 uppercase tracking-wider">Следующий скан</span>
                </div>
                <p className="font-semibold text-dark-100 truncate">{stats.next_scheduled_scan.domain}</p>
                <div className="flex items-center gap-2 mt-1">
                  <p className="text-xs text-dark-500">
                    {formatTimeUntil(stats.next_scheduled_scan.next_scan_at)}
                  </p>
                  <span className="text-xs text-dark-600">· каждые {stats.next_scheduled_scan.interval_minutes}м</span>
                </div>
              </div>
            )}

            {/* Last Monitoring Scan */}
            {stats?.last_monitoring_scan && (
              <div className="bg-dark-800/40 border border-dark-700/40 rounded-xl p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Eye className="w-3.5 h-3.5 text-purple-400" />
                  <span className="text-xs font-medium text-dark-400 uppercase tracking-wider">Мониторинг</span>
                </div>
                <p className="font-semibold text-dark-100 truncate">{stats.last_monitoring_scan.domain}</p>
                <div className="flex items-center gap-2 mt-1">
                  <p className="text-xs text-dark-500">
                    {formatTimeAgo(stats.last_monitoring_scan.scanned_at)}
                  </p>
                  <span className="text-xs text-dark-600">· {stats.last_monitoring_scan.pages_checked} стр.</span>
                  {stats.last_monitoring_scan.has_changes && (
                    <span className="text-xs text-orange-400 font-medium">⚡ изменения</span>
                  )}
                  {stats.last_monitoring_scan.new_domains > 0 && (
                    <span className="text-xs text-red-400 font-medium">+{stats.last_monitoring_scan.new_domains} домен.</span>
                  )}
                </div>
              </div>
            )}
          </div>
        </motion.div>
      )}

      {/* Monitoring Alert Banner */}
      {monitoring?.summary && (monitoring.summary.suspicious_domains > 0 || monitoring.summary.unread_alerts > 0 || monitoring.summary.new_domains > 0) && (
        <motion.div variants={item}>
          <Link
            href="/monitoring"
            className={`flex items-center gap-3 p-4 rounded-xl border transition-all hover:scale-[1.005] ${
              monitoring.summary.suspicious_domains > 0
                ? "bg-red-500/5 border-red-500/20 hover:border-red-500/40"
                : "bg-orange-500/5 border-orange-500/20 hover:border-orange-500/40"
            }`}
          >
            <ShieldAlert className={`w-5 h-5 flex-shrink-0 ${
              monitoring.summary.suspicious_domains > 0 ? "text-red-400" : "text-orange-400"
            }`} />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-dark-200">
                {monitoring.summary.suspicious_domains > 0
                  ? `${monitoring.summary.suspicious_domains} suspicious domain${monitoring.summary.suspicious_domains > 1 ? "s" : ""} detected`
                  : monitoring.summary.unread_alerts > 0
                  ? `${monitoring.summary.unread_alerts} unread alert${monitoring.summary.unread_alerts > 1 ? "s" : ""}`
                  : `${monitoring.summary.new_domains} new domain${monitoring.summary.new_domains > 1 ? "s" : ""} found`}
              </p>
              <p className="text-xs text-dark-500 mt-0.5">
                {monitoring.summary.total_external_domains} external domains tracked
                {monitoring.summary.whitelist_domains > 0 && ` · ${monitoring.summary.whitelist_domains} whitelisted`}
                {monitoring.summary.blacklist_domains > 0 && ` · ${monitoring.summary.blacklist_domains} blacklisted`}
                {monitoring.summary.unknown_domains > 0 && ` · ${monitoring.summary.unknown_domains} unclassified`}
              </p>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className="text-xs font-medium text-primary-400 hidden sm:inline">Review →</span>
              <ArrowRight className="w-4 h-4 text-dark-500" />
            </div>
          </Link>
        </motion.div>
      )}

      {/* New Scan */}
      <motion.div variants={item}>
        <AnimatePresence mode="wait">
          {!showNewScan ? (
            <motion.button
              key="button"
              onClick={() => setShowNewScan(true)}
              className="w-full py-4 rounded-2xl border-2 border-dashed border-dark-600 hover:border-primary-500/50 
                         text-dark-400 hover:text-primary-400 transition-all duration-300 flex items-center justify-center gap-2
                         hover:bg-primary-500/5 group"
              whileHover={{ scale: 1.005 }}
              whileTap={{ scale: 0.995 }}
              exit={{ opacity: 0, scale: 0.95 }}
            >
              <Plus className="w-5 h-5 group-hover:rotate-90 transition-transform duration-300" />
              <span className="font-medium">Start New Scan</span>
            </motion.button>
          ) : (
            <motion.form
              key="form"
              onSubmit={handleCreateScan}
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="bg-dark-800/50 backdrop-blur-sm rounded-2xl border border-dark-700/50 p-5 md:p-6"
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold flex items-center gap-2">
                  <Zap className="w-5 h-5 text-primary-400" />
                  New Scan
                </h3>
                <button
                  type="button"
                  onClick={() => setShowNewScan(false)}
                  className="text-dark-500 hover:text-dark-300 transition-colors text-sm"
                >
                  Cancel
                </button>
              </div>

              <div className="space-y-4">
                <div className="flex flex-col sm:flex-row gap-3">
                  <div className="flex-1 relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-500" />
                    <input
                      type="text"
                      value={domain}
                      onChange={(e) => setDomain(e.target.value)}
                      placeholder="Enter domain (e.g. example.com)"
                      className="w-full pl-10 pr-4 py-3 bg-dark-900 border border-dark-600 rounded-xl text-dark-100
                                 placeholder-dark-500 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500/30
                                 transition-all duration-200"
                      autoFocus
                    />
                  </div>
                  <motion.button
                    type="submit"
                    disabled={creating || !domain.trim()}
                    className="px-6 py-3 bg-primary-600 hover:bg-primary-500 disabled:opacity-50 disabled:cursor-not-allowed
                               rounded-xl font-medium transition-colors duration-200 flex items-center justify-center gap-2 min-w-[120px]"
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    {creating ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <>
                        <span>Scan</span>
                        <ArrowRight className="w-4 h-4" />
                      </>
                    )}
                  </motion.button>
                </div>

                {/* Advanced settings toggle */}
                <button
                  type="button"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="text-xs text-dark-500 hover:text-dark-300 transition-colors flex items-center gap-1"
                >
                  <Eye className="w-3 h-3" />
                  {showAdvanced ? "Hide" : "Show"} advanced settings
                </button>

                <AnimatePresence>
                  {showAdvanced && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      className="space-y-4 overflow-hidden"
                    >
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="text-xs text-dark-500 mb-1 block">Max Depth</label>
                          <input
                            type="number"
                            value={maxDepth}
                            onChange={(e) => setMaxDepth(Number(e.target.value))}
                            min={1}
                            max={10}
                            className="w-full px-3 py-2 bg-dark-900 border border-dark-600 rounded-lg text-sm
                                       focus:outline-none focus:border-primary-500 transition-colors"
                          />
                        </div>
                        <div>
                          <label className="text-xs text-dark-500 mb-1 block">Max Pages</label>
                          <input
                            type="number"
                            value={maxPages}
                            onChange={(e) => setMaxPages(Number(e.target.value))}
                            min={1}
                            max={10000}
                            className="w-full px-3 py-2 bg-dark-900 border border-dark-600 rounded-lg text-sm
                                       focus:outline-none focus:border-primary-500 transition-colors"
                          />
                        </div>
                      </div>

                      {/* Whitelist Domains */}
                      <div>
                        <label className="text-xs text-dark-400 mb-1.5 flex items-center gap-1.5 font-medium">
                          <ShieldCheck className="w-3.5 h-3.5 text-green-400" />
                          Whitelist <span className="text-dark-600 font-normal">(optional — trusted domains)</span>
                        </label>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={whitelistInput}
                            onChange={(e) => setWhitelistInput(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") {
                                e.preventDefault();
                                const val = whitelistInput.trim().toLowerCase();
                                if (val && !whitelistDomains.includes(val)) {
                                  setWhitelistDomains([...whitelistDomains, val]);
                                }
                                setWhitelistInput("");
                              }
                            }}
                            placeholder="e.g. google.com"
                            className="flex-1 px-3 py-2 bg-dark-900 border border-dark-600 rounded-lg text-sm
                                       placeholder-dark-600 focus:outline-none focus:border-green-500/50 transition-colors"
                          />
                          <button
                            type="button"
                            onClick={() => {
                              const val = whitelistInput.trim().toLowerCase();
                              if (val && !whitelistDomains.includes(val)) {
                                setWhitelistDomains([...whitelistDomains, val]);
                              }
                              setWhitelistInput("");
                            }}
                            className="px-3 py-2 rounded-lg bg-green-500/10 text-green-400 text-xs font-medium
                                       hover:bg-green-500/20 border border-green-500/20 transition-colors"
                          >
                            <Plus className="w-3.5 h-3.5" />
                          </button>
                        </div>
                        {whitelistDomains.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 mt-2">
                            {whitelistDomains.map((d) => (
                              <span
                                key={d}
                                className="flex items-center gap-1 px-2 py-1 rounded-lg bg-green-500/10 text-green-400
                                           border border-green-500/20 text-xs font-medium"
                              >
                                {d}
                                <button
                                  type="button"
                                  onClick={() => setWhitelistDomains(whitelistDomains.filter((x) => x !== d))}
                                  className="hover:text-green-200 transition-colors"
                                >
                                  <X className="w-3 h-3" />
                                </button>
                              </span>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* Blacklist Domains */}
                      <div>
                        <label className="text-xs text-dark-400 mb-1.5 flex items-center gap-1.5 font-medium">
                          <ShieldX className="w-3.5 h-3.5 text-red-400" />
                          Blacklist <span className="text-dark-600 font-normal">(optional — blocked domains)</span>
                        </label>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={blacklistInput}
                            onChange={(e) => setBlacklistInput(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") {
                                e.preventDefault();
                                const val = blacklistInput.trim().toLowerCase();
                                if (val && !blacklistDomains.includes(val)) {
                                  setBlacklistDomains([...blacklistDomains, val]);
                                }
                                setBlacklistInput("");
                              }
                            }}
                            placeholder="e.g. malware-site.com"
                            className="flex-1 px-3 py-2 bg-dark-900 border border-dark-600 rounded-lg text-sm
                                       placeholder-dark-600 focus:outline-none focus:border-red-500/50 transition-colors"
                          />
                          <button
                            type="button"
                            onClick={() => {
                              const val = blacklistInput.trim().toLowerCase();
                              if (val && !blacklistDomains.includes(val)) {
                                setBlacklistDomains([...blacklistDomains, val]);
                              }
                              setBlacklistInput("");
                            }}
                            className="px-3 py-2 rounded-lg bg-red-500/10 text-red-400 text-xs font-medium
                                       hover:bg-red-500/20 border border-red-500/20 transition-colors"
                          >
                            <Plus className="w-3.5 h-3.5" />
                          </button>
                        </div>
                        {blacklistDomains.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 mt-2">
                            {blacklistDomains.map((d) => (
                              <span
                                key={d}
                                className="flex items-center gap-1 px-2 py-1 rounded-lg bg-red-500/10 text-red-400
                                           border border-red-500/20 text-xs font-medium"
                              >
                                {d}
                                <button
                                  type="button"
                                  onClick={() => setBlacklistDomains(blacklistDomains.filter((x) => x !== d))}
                                  className="hover:text-red-200 transition-colors"
                                >
                                  <X className="w-3 h-3" />
                                </button>
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </motion.form>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Recent Scans */}
      <motion.div variants={item}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold flex items-center gap-2">
            <Activity className="w-5 h-5 text-primary-400" />
            Recent Scans
          </h2>
          {scans.length > 0 && (
            <Link
              href="/explorer"
              className="text-xs text-dark-500 hover:text-primary-400 transition-colors flex items-center gap-1"
            >
              View all <ArrowRight className="w-3 h-3" />
            </Link>
          )}
        </div>

        {scans.length === 0 ? (
          <div className="text-center py-16 bg-dark-800/30 rounded-2xl border border-dark-700/30">
            <Globe className="w-16 h-16 mx-auto mb-4 text-dark-700" />
            <p className="text-lg font-medium text-dark-400">No scans yet</p>
            <p className="text-sm mt-1 text-dark-600">Start by scanning a domain above</p>
          </div>
        ) : (
          <div className="space-y-2">
            {scans.map((scan, i) => (
              <motion.div
                key={scan.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
              >
                <Link href={`/scan/${scan.id}`}>
                  <div className="bg-dark-800/40 backdrop-blur-sm rounded-xl border border-dark-700/40 p-4
                                  hover:border-primary-500/30 hover:bg-dark-800/70 transition-all duration-300
                                  cursor-pointer group glow-hover">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-3 min-w-0 flex-1">
                        <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0
                                        ${scan.status === "completed" ? "bg-emerald-500/10" : 
                                          scan.status === "running" ? "bg-blue-500/10" :
                                          scan.status === "failed" ? "bg-red-500/10" : "bg-primary-500/10"}`}>
                          <Globe className={`w-5 h-5 ${
                            scan.status === "completed" ? "text-emerald-400" :
                            scan.status === "running" ? "text-blue-400" :
                            scan.status === "failed" ? "text-red-400" : "text-primary-400"
                          }`} />
                        </div>
                        <div className="min-w-0">
                          <p className="font-semibold truncate group-hover:text-primary-300 transition-colors">
                            {scan.domain}
                          </p>
                          <div className="flex items-center gap-2 mt-0.5">
                            <p className="text-xs text-dark-500">
                              #{scan.id} · {new Date(scan.created_at).toLocaleDateString()}
                            </p>
                            {scan.duration && (
                              <span className="text-xs text-dark-600">{scan.duration}s</span>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-3 flex-shrink-0">
                        {scan.status === "completed" && (
                          <div className="hidden sm:flex items-center gap-3 text-xs">
                            <span className="text-dark-400">{scan.total_urls} URLs</span>
                            {scan.new_urls > 0 && (
                              <span className="text-emerald-400 font-medium">+{scan.new_urls} new</span>
                            )}
                            {scan.external_urls > 0 && (
                              <span className="text-orange-400/70 flex items-center gap-0.5">
                                <ExternalLink className="w-3 h-3" />
                                {scan.external_urls}
                              </span>
                            )}
                          </div>
                        )}
                        <span
                          className={`px-2 py-1 rounded-lg text-[10px] font-medium border ${statusColor(scan.status)} flex items-center gap-1`}
                        >
                          {statusIcon(scan.status)}
                          <span className="hidden sm:inline capitalize">{scan.status}</span>
                        </span>
                        <ArrowRight className="w-4 h-4 text-dark-600 group-hover:text-primary-400 group-hover:translate-x-0.5 transition-all" />
                      </div>
                    </div>

                    {/* Mobile stats row */}
                    {scan.status === "completed" && (
                      <div className="flex items-center gap-3 mt-2 sm:hidden text-xs text-dark-500">
                        <span>{scan.total_urls} URLs</span>
                        {scan.new_urls > 0 && <span className="text-emerald-400">+{scan.new_urls}</span>}
                        {scan.external_urls > 0 && (
                          <span className="text-orange-400/70 flex items-center gap-0.5">
                            <ExternalLink className="w-3 h-3" /> {scan.external_urls}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </Link>
              </motion.div>
            ))}
          </div>
        )}
      </motion.div>
    </motion.div>
  );
}

function StatCard({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  color: "primary" | "blue" | "green" | "purple" | "orange" | "red";
}) {
  const colorMap = {
    primary: "from-primary-500/20 to-primary-500/5 border-primary-500/20 text-primary-400",
    blue: "from-blue-500/20 to-blue-500/5 border-blue-500/20 text-blue-400",
    green: "from-emerald-500/20 to-emerald-500/5 border-emerald-500/20 text-emerald-400",
    purple: "from-purple-500/20 to-purple-500/5 border-purple-500/20 text-purple-400",
    orange: "from-orange-500/20 to-orange-500/5 border-orange-500/20 text-orange-400",
    red: "from-red-500/20 to-red-500/5 border-red-500/20 text-red-400",
  };

  return (
    <motion.div
      className={`bg-gradient-to-br ${colorMap[color]} rounded-2xl border p-4 md:p-5`}
      whileHover={{ scale: 1.02, y: -2 }}
      transition={{ type: "spring", stiffness: 300 }}
    >
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="text-[10px] md:text-xs font-medium text-dark-400 uppercase tracking-wider">{label}</span>
      </div>
      <p className="text-2xl md:text-3xl font-bold text-dark-100">
        {value.toLocaleString()}
      </p>
    </motion.div>
  );
}

function QuickStat({
  label,
  value,
  icon,
  color,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  color: "blue" | "green" | "purple";
}) {
  const colorMap = {
    blue: "text-blue-400 bg-blue-500/10 border-blue-500/20",
    green: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
    purple: "text-purple-400 bg-purple-500/10 border-purple-500/20",
  };

  return (
    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-medium whitespace-nowrap ${colorMap[color]}`}>
      {icon}
      <span>{value}</span>
      <span className="text-dark-500">{label}</span>
    </div>
  );
}
