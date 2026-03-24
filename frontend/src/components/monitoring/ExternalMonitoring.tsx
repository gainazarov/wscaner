"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Shield,
  AlertTriangle,
  CheckCircle2,
  Globe,
  Bell,
  BellOff,
  Clock,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  Search,
  RefreshCw,
  TrendingUp,
  XCircle,
  MapPin,
  ShieldCheck,
  ShieldAlert,
  ArrowRight,
  Check,
  Copy,
  Filter,
  Scan,
  Loader2,
  ShieldX,
  BarChart3,
  Zap,
} from "lucide-react";
import {
  api,
  MonitoringData,
  ExternalDomainAlertItem,
  TimelineEntry,
  DomainDetail,
  DomainStats,
  DomainReputation,
  ReputationListResponse,
  ExternalDomainEntryWithReputation,
} from "@/lib/api";
import { RealtimeMonitoring } from "./RealtimeMonitoring";
import { DomainLists } from "./DomainLists";

type ViewTab = "overview" | "domains" | "alerts" | "timeline" | "reputation" | "realtime" | "lists";
type DomainFilter = "all" | "safe" | "suspicious" | "new";

export function ExternalMonitoring() {
  const [data, setData] = useState<MonitoringData | null>(null);
  const [domains, setDomains] = useState<DomainStats[]>([]);
  const [selectedSite, setSelectedSite] = useState<string>("");
  const [activeTab, setActiveTab] = useState<ViewTab>("overview");
  const [domainFilter, setDomainFilter] = useState<DomainFilter>("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [expandedDomain, setExpandedDomain] = useState<string | null>(null);
  const [domainDetail, setDomainDetail] = useState<DomainDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [copiedDomain, setCopiedDomain] = useState<string | null>(null);
  const [reputationData, setReputationData] = useState<ReputationListResponse | null>(null);
  const [repLoading, setRepLoading] = useState(false);
  const [checkingAll, setCheckingAll] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [monitoringData, domainStats] = await Promise.all([
        api.getMonitoringData(selectedSite || undefined),
        api.getDomains(),
      ]);
      setData(monitoringData);
      setDomains(domainStats);
    } catch (err) {
      console.error("Failed to load monitoring data:", err);
    } finally {
      setLoading(false);
    }
  }, [selectedSite]);

  const loadReputation = useCallback(async () => {
    setRepLoading(true);
    try {
      const repData = await api.getReputationList(selectedSite || undefined);
      setReputationData(repData);
    } catch (err) {
      console.error("Failed to load reputation data:", err);
    } finally {
      setRepLoading(false);
    }
  }, [selectedSite]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (activeTab === "reputation") {
      loadReputation();
    }
  }, [activeTab, loadReputation]);

  useEffect(() => {
    if (selectedSite && activeTab === "timeline") {
      api.getMonitoringTimeline(selectedSite).then(setTimeline).catch(console.error);
    }
  }, [selectedSite, activeTab]);

  const loadDomainDetail = async (domain: string) => {
    if (!selectedSite) return;
    if (expandedDomain === domain) {
      setExpandedDomain(null);
      setDomainDetail(null);
      return;
    }
    setExpandedDomain(domain);
    setDetailLoading(true);
    try {
      const detail = await api.getMonitoringDomainDetail(domain, selectedSite);
      setDomainDetail(detail);
    } catch (err) {
      console.error("Failed to load domain detail:", err);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleMarkSafe = async (domain: string) => {
    if (!selectedSite) return;
    try {
      await api.markDomainSafe(selectedSite, domain);
      loadData();
    } catch (err) {
      console.error("Failed to mark domain safe:", err);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await api.markAlertsRead({ site_domain: selectedSite || undefined });
      loadData();
    } catch (err) {
      console.error("Failed to mark alerts read:", err);
    }
  };

  const handleCheckAllReputations = async () => {
    setCheckingAll(true);
    try {
      await api.checkAllReputations(selectedSite || undefined);
      setTimeout(() => {
        loadReputation();
        loadData();
      }, 2000);
    } catch (err) {
      console.error("Failed to trigger reputation checks:", err);
    } finally {
      setCheckingAll(false);
    }
  };

  const handleQuickAddToList = async (domain: string, listType: "whitelist" | "blacklist", siteDomain?: string) => {
    const site = siteDomain || selectedSite;
    if (!site) return;
    try {
      await api.domainListQuickAction({ domain, list_type: listType, site_domain: site });
      loadData();
    } catch (err) {
      console.error("Failed to add domain to list:", err);
    }
  };

  const handleIgnoreAlert = async (alertId: number) => {
    try {
      await api.markAlertsRead({ alert_ids: [alertId] });
      loadData();
    } catch (err) {
      console.error("Failed to ignore alert:", err);
    }
  };

  // Build domain classification map from monitoring data
  const domainClassifications = useMemo(() => {
    const map: Record<string, "whitelist" | "blacklist" | "unknown"> = {};
    data?.domains.forEach((d) => {
      if (d.list_classification && d.list_classification !== "unknown") {
        map[d.domain] = d.list_classification;
      }
    });
    return map;
  }, [data?.domains]);

  const handleCheckSingleReputation = async (domain: string) => {
    try {
      await api.checkReputation({ domain, force: true });
      setTimeout(() => {
        loadReputation();
        loadData();
      }, 3000);
    } catch (err) {
      console.error("Failed to check reputation:", err);
    }
  };

  const copyDomain = (domain: string) => {
    navigator.clipboard.writeText(domain);
    setCopiedDomain(domain);
    setTimeout(() => setCopiedDomain(null), 2000);
  };

  const filteredDomains = data?.domains.filter((d) => {
    if (domainFilter !== "all" && d.status !== domainFilter) return false;
    if (search && !d.domain.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  }) ?? [];

  const filteredAlerts = data?.alerts.filter((a) => {
    if (search && !a.external_domain.toLowerCase().includes(search.toLowerCase()) &&
        !a.message.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  }) ?? [];

  const filteredReputations = reputationData?.results.filter((r) => {
    if (search && !r.domain.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  }) ?? [];

  const tabs: { key: ViewTab; label: string; icon: React.ReactNode; count?: number }[] = [
    { key: "overview", label: "Overview", icon: <TrendingUp className="w-4 h-4" /> },
    { key: "domains", label: "Domains", icon: <Globe className="w-4 h-4" />, count: data?.summary.total_external_domains },
    { key: "reputation", label: "Reputation", icon: <Shield className="w-4 h-4" />, count: reputationData?.summary.high_risk },
    { key: "alerts", label: "Alerts", icon: <Bell className="w-4 h-4" />, count: data?.summary.unread_alerts },
    { key: "timeline", label: "Timeline", icon: <Clock className="w-4 h-4" /> },
    { key: "realtime", label: "Real-Time", icon: <Zap className="w-4 h-4" /> },
    { key: "lists", label: "Lists", icon: <ShieldCheck className="w-4 h-4" /> },
  ];

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
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
          <h1 className="text-2xl font-bold text-dark-100 flex items-center gap-2">
            <ShieldAlert className="w-7 h-7 text-primary-500" />
            External Monitoring
          </h1>
          <p className="text-dark-400 text-sm mt-1">
            Track external domains, detect threats via Safe Browsing &amp; VirusTotal
          </p>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={selectedSite}
            onChange={(e) => setSelectedSite(e.target.value)}
            className="bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-sm text-dark-200 focus:border-primary-500 focus:outline-none"
          >
            <option value="">All Sites</option>
            {domains.map((d) => (
              <option key={d.domain} value={d.domain}>
                {d.domain}
              </option>
            ))}
          </select>

          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={loadData}
            className="p-2 rounded-lg bg-dark-800 border border-dark-700 text-dark-400 hover:text-primary-400 hover:border-primary-500 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </motion.button>
        </div>
      </div>

      {/* Summary Cards */}
      {data?.summary && <SummaryCards summary={data.summary} repSummary={data.reputation_summary} />}

      {/* Tabs */}
      <div className="flex items-center gap-1 bg-dark-800/50 rounded-xl p-1 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium whitespace-nowrap transition-all ${
              activeTab === tab.key
                ? "bg-primary-500/20 text-primary-400 shadow-sm"
                : "text-dark-400 hover:text-dark-200 hover:bg-dark-700/50"
            }`}
          >
            {tab.icon}
            {tab.label}
            {tab.count !== undefined && tab.count > 0 && (
              <span className={`px-1.5 py-0.5 rounded-full text-xs font-bold ${
                tab.key === "alerts" || tab.key === "reputation"
                  ? "bg-red-500/20 text-red-400"
                  : "bg-dark-700 text-dark-300"
              }`}>
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Search bar */}
      {(activeTab === "domains" || activeTab === "alerts" || activeTab === "reputation") && (
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={
              activeTab === "domains" ? "Search domains..." :
              activeTab === "reputation" ? "Search reputation results..." :
              "Search alerts..."
            }
            className="w-full pl-10 pr-4 py-2.5 bg-dark-800 border border-dark-700 rounded-xl text-sm text-dark-200 placeholder-dark-500 focus:border-primary-500 focus:outline-none"
          />
        </div>
      )}

      {/* Tab Content */}
      <AnimatePresence mode="wait">
        {activeTab === "overview" && data && (
          <motion.div
            key="overview"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            <OverviewTab
              data={data}
              onViewDomain={(d) => { setActiveTab("domains"); setSearch(d); }}
              onViewReputation={() => setActiveTab("reputation")}
            />
          </motion.div>
        )}

        {activeTab === "domains" && (
          <motion.div
            key="domains"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="space-y-4"
          >
            <div className="flex items-center gap-2 flex-wrap">
              <Filter className="w-4 h-4 text-dark-500" />
              {(["all", "safe", "suspicious", "new"] as DomainFilter[]).map((f) => (
                <button
                  key={f}
                  onClick={() => setDomainFilter(f)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                    domainFilter === f
                      ? f === "suspicious"
                        ? "bg-red-500/20 text-red-400"
                        : f === "safe"
                        ? "bg-green-500/20 text-green-400"
                        : f === "new"
                        ? "bg-blue-500/20 text-blue-400"
                        : "bg-primary-500/20 text-primary-400"
                      : "bg-dark-800 text-dark-400 hover:text-dark-200"
                  }`}
                >
                  {f === "all" ? "All" : f === "safe" ? "✅ Safe" : f === "suspicious" ? "⚠️ Suspicious" : "🆕 New"}
                  {f !== "all" && data && (
                    <span className="ml-1">
                      ({f === "safe"
                        ? data.summary.safe_domains
                        : f === "suspicious"
                        ? data.summary.suspicious_domains
                        : data.summary.new_domains})
                    </span>
                  )}
                </button>
              ))}
            </div>

            <div className="space-y-2">
              {filteredDomains.length === 0 ? (
                <div className="text-center py-12 text-dark-500">
                  <Globe className="w-12 h-12 mx-auto mb-3 opacity-30" />
                  <p>No external domains found</p>
                  <p className="text-xs mt-1">Run a scan to discover external links</p>
                </div>
              ) : (
                filteredDomains.map((entry) => (
                  <DomainCard
                    key={entry.id}
                    entry={entry}
                    isExpanded={expandedDomain === entry.domain}
                    detail={expandedDomain === entry.domain ? domainDetail : null}
                    detailLoading={detailLoading && expandedDomain === entry.domain}
                    onToggle={() => loadDomainDetail(entry.domain)}
                    onMarkSafe={() => handleMarkSafe(entry.domain)}
                    onCopy={() => copyDomain(entry.domain)}
                    copied={copiedDomain === entry.domain}
                    onCheckReputation={() => handleCheckSingleReputation(entry.domain)}
                    onAddToList={(listType) => handleQuickAddToList(entry.domain, listType)}
                  />
                ))
              )}
            </div>
          </motion.div>
        )}

        {activeTab === "reputation" && (
          <motion.div
            key="reputation"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            <ReputationTab
              data={reputationData}
              filteredResults={filteredReputations}
              loading={repLoading}
              checkingAll={checkingAll}
              onCheckAll={handleCheckAllReputations}
              onCheckSingle={handleCheckSingleReputation}
              onRefresh={loadReputation}
            />
          </motion.div>
        )}

        {activeTab === "alerts" && (
          <motion.div
            key="alerts"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="space-y-4"
          >
            {data?.summary && data.summary.unread_alerts > 0 && (
              <div className="flex justify-end">
                <button
                  onClick={handleMarkAllRead}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-dark-800 border border-dark-700 text-xs text-dark-400 hover:text-primary-400 transition-colors"
                >
                  <BellOff className="w-3.5 h-3.5" />
                  Mark all as read
                </button>
              </div>
            )}

            <div className="space-y-2">
              {filteredAlerts.length === 0 ? (
                <div className="text-center py-12 text-dark-500">
                  <Bell className="w-12 h-12 mx-auto mb-3 opacity-30" />
                  <p>No alerts</p>
                </div>
              ) : (
                filteredAlerts.map((alert) => (
                  <AlertCard
                    key={alert.id}
                    alert={alert}
                    onAddToList={handleQuickAddToList}
                    onIgnore={handleIgnoreAlert}
                    domainClassifications={domainClassifications}
                  />
                ))
              )}
            </div>
          </motion.div>
        )}

        {activeTab === "timeline" && (
          <motion.div
            key="timeline"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            {!selectedSite ? (
              <div className="text-center py-12 text-dark-500">
                <Clock className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>Select a site to view timeline</p>
              </div>
            ) : (
              <TimelineView entries={timeline} />
            )}
          </motion.div>
        )}

        {activeTab === "realtime" && (
          <motion.div
            key="realtime"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            <RealtimeMonitoring />
          </motion.div>
        )}

        {activeTab === "lists" && (
          <motion.div
            key="lists"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            {!selectedSite ? (
              <div className="text-center py-12">
                <ShieldCheck className="w-12 h-12 mx-auto mb-3 text-dark-700" />
                <p className="text-lg font-medium text-dark-400">Select a site to manage lists</p>
                <p className="text-sm text-dark-600 mt-2">Choose a domain from the dropdown above to view and manage whitelist/blacklist</p>
                {domains.length > 0 && (
                  <button
                    onClick={() => setSelectedSite(domains[0].domain)}
                    className="mt-4 px-4 py-2 rounded-lg bg-primary-500/20 text-primary-400 border border-primary-500/30 text-sm font-medium hover:bg-primary-500/30 transition-colors"
                  >
                    Select {domains[0].domain}
                  </button>
                )}
              </div>
            ) : (
              <DomainLists selectedSite={selectedSite} domains={domains} monitoringData={data} onRefresh={loadData} />
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── Summary Cards ──────────────────────────────────────────────────────────

function SummaryCards({ summary, repSummary }: {
  summary: MonitoringData["summary"];
  repSummary?: MonitoringData["reputation_summary"];
}) {
  const cards = [
    {
      label: "External Domains",
      value: summary.total_external_domains,
      icon: <Globe className="w-5 h-5" />,
      color: "text-blue-400",
      bg: "bg-blue-500/10",
    },
    {
      label: "Whitelisted",
      value: summary.whitelist_domains,
      icon: <ShieldCheck className="w-5 h-5" />,
      color: "text-green-400",
      bg: "bg-green-500/10",
    },
    {
      label: "Blacklisted",
      value: summary.blacklist_domains,
      icon: <ShieldX className="w-5 h-5" />,
      color: summary.blacklist_domains ? "text-red-400" : "text-dark-500",
      bg: summary.blacklist_domains ? "bg-red-500/10" : "bg-dark-700/50",
    },
    {
      label: "New",
      value: summary.new_domains,
      icon: <TrendingUp className="w-5 h-5" />,
      color: "text-cyan-400",
      bg: "bg-cyan-500/10",
    },
    {
      label: "Suspicious",
      value: summary.suspicious_domains,
      icon: <AlertTriangle className="w-5 h-5" />,
      color: "text-red-400",
      bg: "bg-red-500/10",
    },
    {
      label: "High Risk",
      value: repSummary?.high_risk ?? 0,
      icon: <Shield className="w-5 h-5" />,
      color: repSummary?.high_risk ? "text-red-400" : "text-dark-500",
      bg: repSummary?.high_risk ? "bg-red-500/10" : "bg-dark-700/50",
    },
    {
      label: "Unread Alerts",
      value: summary.unread_alerts,
      icon: <Bell className="w-5 h-5" />,
      color: "text-orange-400",
      bg: "bg-orange-500/10",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
      {cards.map((card, i) => (
        <motion.div
          key={card.label}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.1 }}
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

// ─── Overview Tab ───────────────────────────────────────────────────────────

function OverviewTab({
  data,
  onViewDomain,
  onViewReputation,
}: {
  data: MonitoringData;
  onViewDomain: (domain: string) => void;
  onViewReputation: () => void;
}) {
  const suspicious = data.domains.filter((d) => d.is_suspicious);
  const newDomains = data.domains.filter((d) => d.status === "new");
  const recentAlerts = data.alerts.slice(0, 5);
  const highRiskDomains = data.domains.filter((d: ExternalDomainEntryWithReputation) => d.reputation?.risk_level === "high");
  const mediumRiskDomains = data.domains.filter((d: ExternalDomainEntryWithReputation) => d.reputation?.risk_level === "medium");

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Reputation Threats */}
      {(highRiskDomains.length > 0 || mediumRiskDomains.length > 0) && (
        <div className="lg:col-span-2 bg-dark-800/60 backdrop-blur-sm border border-red-500/20 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-dark-200 flex items-center gap-2 mb-4">
            <Shield className="w-4 h-4 text-red-400" />
            Reputation Threats
            <span className="px-1.5 py-0.5 rounded-full text-xs bg-red-500/20 text-red-400 font-bold">
              {highRiskDomains.length + mediumRiskDomains.length}
            </span>
            <button
              onClick={onViewReputation}
              className="ml-auto text-xs text-dark-500 hover:text-primary-400 flex items-center gap-1 transition-colors"
            >
              View all <ArrowRight className="w-3 h-3" />
            </button>
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {highRiskDomains.slice(0, 4).map((d: ExternalDomainEntryWithReputation) => (
              <div
                key={d.id}
                className="flex items-center gap-3 p-3 rounded-lg bg-red-500/5 border border-red-500/10"
              >
                <RiskBadge level="high" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-dark-200 truncate">{d.domain}</p>
                  <p className="text-xs text-red-400/70">
                    {d.reputation?.virustotal_malicious ? `VT: ${d.reputation.virustotal_malicious} malicious` : ""}
                    {d.reputation?.safe_browsing_result?.matched ? " · SafeBrowsing: matched" : ""}
                  </p>
                </div>
              </div>
            ))}
            {mediumRiskDomains.slice(0, 4).map((d: ExternalDomainEntryWithReputation) => (
              <div
                key={d.id}
                className="flex items-center gap-3 p-3 rounded-lg bg-yellow-500/5 border border-yellow-500/10"
              >
                <RiskBadge level="medium" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-dark-200 truncate">{d.domain}</p>
                  <p className="text-xs text-yellow-400/70">
                    {d.reputation?.virustotal_malicious ? `VT: ${d.reputation.virustotal_malicious} malicious` : "Medium risk"}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Suspicious Domains */}
      <div className="bg-dark-800/60 backdrop-blur-sm border border-dark-700/50 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-dark-200 flex items-center gap-2 mb-4">
          <ShieldAlert className="w-4 h-4 text-red-400" />
          Suspicious Domains
          {suspicious.length > 0 && (
            <span className="px-1.5 py-0.5 rounded-full text-xs bg-red-500/20 text-red-400 font-bold">
              {suspicious.length}
            </span>
          )}
        </h3>
        {suspicious.length === 0 ? (
          <div className="text-center py-6 text-dark-500">
            <ShieldCheck className="w-8 h-8 mx-auto mb-2 text-green-500/50" />
            <p className="text-sm">No suspicious domains detected</p>
          </div>
        ) : (
          <div className="space-y-2">
            {suspicious.slice(0, 5).map((d) => (
              <button
                key={d.id}
                onClick={() => onViewDomain(d.domain)}
                className="w-full flex items-center justify-between p-3 rounded-lg bg-red-500/5 border border-red-500/10 hover:border-red-500/30 transition-colors text-left"
              >
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-dark-200">{d.domain}</p>
                    <p className="text-xs text-red-400/70">{d.suspicious_reasons[0]}</p>
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-dark-500" />
              </button>
            ))}
          </div>
        )}
      </div>

      {/* New Domains */}
      <div className="bg-dark-800/60 backdrop-blur-sm border border-dark-700/50 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-dark-200 flex items-center gap-2 mb-4">
          <TrendingUp className="w-4 h-4 text-green-400" />
          Recently Discovered
          {newDomains.length > 0 && (
            <span className="px-1.5 py-0.5 rounded-full text-xs bg-green-500/20 text-green-400 font-bold">
              {newDomains.length}
            </span>
          )}
        </h3>
        {newDomains.length === 0 ? (
          <div className="text-center py-6 text-dark-500">
            <Globe className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No new domains</p>
          </div>
        ) : (
          <div className="space-y-2">
            {newDomains.slice(0, 5).map((d: ExternalDomainEntryWithReputation) => (
              <button
                key={d.id}
                onClick={() => onViewDomain(d.domain)}
                className="w-full flex items-center justify-between p-3 rounded-lg bg-green-500/5 border border-green-500/10 hover:border-green-500/30 transition-colors text-left"
              >
                <div className="flex items-center gap-2">
                  <Globe className="w-4 h-4 text-green-400 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-dark-200">{d.domain}</p>
                    <p className="text-xs text-dark-500">
                      Seen {d.times_seen}× · {d.found_on_pages.length} pages
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {d.reputation && <RiskBadge level={d.reputation.risk_level} small />}
                  <ArrowRight className="w-4 h-4 text-dark-500" />
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Recent Alerts */}
      <div className="lg:col-span-2 bg-dark-800/60 backdrop-blur-sm border border-dark-700/50 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-dark-200 flex items-center gap-2 mb-4">
          <Bell className="w-4 h-4 text-orange-400" />
          Recent Alerts
        </h3>
        {recentAlerts.length === 0 ? (
          <div className="text-center py-6 text-dark-500">
            <Bell className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No alerts yet</p>
          </div>
        ) : (
          <div className="space-y-2">
            {recentAlerts.map((alert) => (
              <AlertCard key={alert.id} alert={alert} compact />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Risk Badge ─────────────────────────────────────────────────────────────

function RiskBadge({ level, small }: { level: string; small?: boolean }) {
  const config: Record<string, { icon: string; color: string; bg: string; border: string; label: string }> = {
    high: { icon: "🔴", color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/20", label: "high" },
    medium: { icon: "🟡", color: "text-yellow-400", bg: "bg-yellow-500/10", border: "border-yellow-500/20", label: "medium" },
    low: { icon: "🟢", color: "text-green-400", bg: "bg-green-500/10", border: "border-green-500/20", label: "safe" },
    unknown: { icon: "⚪", color: "text-dark-400", bg: "bg-dark-700/50", border: "border-dark-600", label: "unknown" },
  };

  const cfg = config[level] || config.unknown;

  if (small) {
    return (
      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${cfg.bg} ${cfg.color} border ${cfg.border}`}>
        {cfg.icon} {cfg.label}
      </span>
    );
  }

  return (
    <span className={`px-2 py-1 rounded-lg text-xs font-bold ${cfg.bg} ${cfg.color} border ${cfg.border} flex items-center gap-1`}>
      {cfg.icon} {cfg.label}
    </span>
  );
}

// ─── Reputation Tab ─────────────────────────────────────────────────────────

function ReputationTab({
  data,
  filteredResults,
  loading,
  checkingAll,
  onCheckAll,
  onCheckSingle,
  onRefresh,
}: {
  data: ReputationListResponse | null;
  filteredResults: DomainReputation[];
  loading: boolean;
  checkingAll: boolean;
  onCheckAll: () => void;
  onCheckSingle: (domain: string) => void;
  onRefresh: () => void;
}) {
  const [riskFilter, setRiskFilter] = useState<string>("all");
  const [expandedRep, setExpandedRep] = useState<string | null>(null);

  const filtered = filteredResults.filter((r) => {
    if (riskFilter !== "all" && r.risk_level !== riskFilter) return false;
    return true;
  });

  return (
    <div className="space-y-4">
      {/* Reputation Summary */}
      {data?.summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div className="bg-dark-800/60 border border-dark-700/50 rounded-xl p-3 text-center">
            <p className="text-lg font-bold text-dark-200">{data.summary.total}</p>
            <p className="text-[10px] text-dark-500 uppercase tracking-wider">Checked</p>
          </div>
          <div className="bg-red-500/5 border border-red-500/20 rounded-xl p-3 text-center">
            <p className="text-lg font-bold text-red-400">{data.summary.high_risk}</p>
            <p className="text-[10px] text-red-400/70 uppercase tracking-wider">🔴 High</p>
          </div>
          <div className="bg-yellow-500/5 border border-yellow-500/20 rounded-xl p-3 text-center">
            <p className="text-lg font-bold text-yellow-400">{data.summary.medium_risk}</p>
            <p className="text-[10px] text-yellow-400/70 uppercase tracking-wider">🟡 Medium</p>
          </div>
          <div className="bg-green-500/5 border border-green-500/20 rounded-xl p-3 text-center">
            <p className="text-lg font-bold text-green-400">{data.summary.low_risk}</p>
            <p className="text-[10px] text-green-400/70 uppercase tracking-wider">🟢 Safe</p>
          </div>
          <div className="bg-dark-800/60 border border-dark-700/50 rounded-xl p-3 text-center">
            <p className="text-lg font-bold text-dark-400">{data.summary.pending + data.summary.checking}</p>
            <p className="text-[10px] text-dark-500 uppercase tracking-wider">Pending</p>
          </div>
        </div>
      )}

      {/* Actions & Filters */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <Filter className="w-4 h-4 text-dark-500" />
          {["all", "high", "medium", "low", "unknown"].map((f) => (
            <button
              key={f}
              onClick={() => setRiskFilter(f)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                riskFilter === f
                  ? f === "high"
                    ? "bg-red-500/20 text-red-400"
                    : f === "medium"
                    ? "bg-yellow-500/20 text-yellow-400"
                    : f === "low"
                    ? "bg-green-500/20 text-green-400"
                    : "bg-primary-500/20 text-primary-400"
                  : "bg-dark-800 text-dark-400 hover:text-dark-200"
              }`}
            >
              {f === "all" ? "All" : f === "high" ? "🔴 High" : f === "medium" ? "🟡 Medium" : f === "low" ? "🟢 Safe" : "⚪ Unknown"}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={onCheckAll}
            disabled={checkingAll}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-500/10 text-primary-400 text-xs font-medium hover:bg-primary-500/20 transition-colors disabled:opacity-50"
          >
            {checkingAll ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
            Check All Domains
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={onRefresh}
            className="p-1.5 rounded-lg bg-dark-800 border border-dark-700 text-dark-400 hover:text-primary-400 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </motion.button>
        </div>
      </div>

      {/* Reputation List */}
      {loading && !data ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 text-primary-500 animate-spin" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 text-dark-500">
          <Shield className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>No reputation data available</p>
          <p className="text-xs mt-1">Click &ldquo;Check All Domains&rdquo; to start analysis</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((rep) => (
            <ReputationCard
              key={rep.id}
              rep={rep}
              isExpanded={expandedRep === rep.domain}
              onToggle={() => setExpandedRep(expandedRep === rep.domain ? null : rep.domain)}
              onRecheck={() => onCheckSingle(rep.domain)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Reputation Card ────────────────────────────────────────────────────────

function ReputationCard({
  rep,
  isExpanded,
  onToggle,
  onRecheck,
}: {
  rep: DomainReputation;
  isExpanded: boolean;
  onToggle: () => void;
  onRecheck: () => void;
}) {
  const riskConfig: Record<string, { border: string; bg: string }> = {
    high: { border: "border-red-500/30", bg: "bg-red-500/5" },
    medium: { border: "border-yellow-500/30", bg: "bg-yellow-500/5" },
    low: { border: "border-green-500/20", bg: "bg-transparent" },
    unknown: { border: "border-dark-700/50", bg: "bg-transparent" },
  };

  const cfg = riskConfig[rep.risk_level] || riskConfig.unknown;
  const isChecking = rep.check_status === "checking" || rep.check_status === "pending";

  const vtTotal = rep.virustotal_malicious + rep.virustotal_suspicious + rep.virustotal_harmless + rep.virustotal_undetected;

  return (
    <motion.div
      layout
      className={`bg-dark-800/60 backdrop-blur-sm border rounded-xl overflow-hidden ${cfg.border} ${cfg.bg}`}
    >
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 p-4 text-left hover:bg-dark-700/30 transition-colors"
      >
        <RiskBadge level={rep.risk_level} />

        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-dark-200 truncate">{rep.domain}</p>
          <div className="flex items-center gap-3 mt-1 text-xs text-dark-500">
            {isChecking ? (
              <span className="flex items-center gap-1 text-primary-400">
                <Loader2 className="w-3 h-3 animate-spin" />
                Checking...
              </span>
            ) : rep.check_status === "failed" ? (
              <span className="text-red-400">Check failed</span>
            ) : (
              <>
                <span>Checked {rep.check_count}×</span>
                {rep.checked_at && (
                  <>
                    <span>·</span>
                    <span>{new Date(rep.checked_at).toLocaleDateString()}</span>
                  </>
                )}
                {!rep.is_cache_valid && rep.checked_at && (
                  <span className="text-yellow-400/70 text-[10px]">cache expired</span>
                )}
              </>
            )}
          </div>
        </div>

        {/* Quick Stats */}
        <div className="hidden sm:flex items-center gap-4 text-xs flex-shrink-0">
          {rep.check_status === "completed" && (
            <>
              <div className="flex items-center gap-1" title="Google Safe Browsing">
                <span className="text-dark-500">SB:</span>
                {rep.safe_browsing_result?.matched ? (
                  <span className="text-red-400 font-bold">THREAT</span>
                ) : rep.safe_browsing_risk === "unknown" ? (
                  <span className="text-dark-500">—</span>
                ) : (
                  <span className="text-green-400">clean</span>
                )}
              </div>

              <div className="flex items-center gap-1" title="VirusTotal">
                <span className="text-dark-500">VT:</span>
                {rep.virustotal_malicious > 0 ? (
                  <span className="text-red-400 font-bold">{rep.virustotal_malicious}/{vtTotal}</span>
                ) : rep.virustotal_risk === "unknown" ? (
                  <span className="text-dark-500">—</span>
                ) : (
                  <span className="text-green-400">0/{vtTotal}</span>
                )}
              </div>
            </>
          )}
        </div>

        {isExpanded ? (
          <ChevronDown className="w-4 h-4 text-dark-500 flex-shrink-0" />
        ) : (
          <ChevronRight className="w-4 h-4 text-dark-500 flex-shrink-0" />
        )}
      </button>

      {/* Expanded Details */}
      <AnimatePresence>
        {isExpanded && rep.check_status === "completed" && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="border-t border-dark-700/50"
          >
            <div className="p-4 space-y-4">
              {/* Google Safe Browsing Section */}
              <div>
                <h4 className="text-xs font-semibold text-dark-300 flex items-center gap-1.5 mb-2">
                  <Shield className="w-3.5 h-3.5 text-blue-400" />
                  Google Safe Browsing
                </h4>
                <div className="bg-dark-900/50 rounded-lg p-3">
                  {rep.safe_browsing_result?.error && String(rep.safe_browsing_result.error).includes("API key") ? (
                    <p className="text-xs text-dark-500">API key not configured</p>
                  ) : rep.safe_browsing_result?.matched ? (
                    <div className="space-y-1">
                      <p className="text-xs text-red-400 font-medium">⚠️ Threats detected</p>
                      <div className="flex flex-wrap gap-1">
                        {(rep.safe_browsing_result.threats as string[] || []).map((t: string, i: number) => (
                          <span key={i} className="px-2 py-0.5 rounded-full text-[10px] bg-red-500/10 text-red-400 border border-red-500/20">
                            {t}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-green-400">✅ No threats detected</p>
                  )}
                </div>
              </div>

              {/* VirusTotal Section */}
              <div>
                <h4 className="text-xs font-semibold text-dark-300 flex items-center gap-1.5 mb-2">
                  <BarChart3 className="w-3.5 h-3.5 text-purple-400" />
                  VirusTotal Analysis
                </h4>
                <div className="bg-dark-900/50 rounded-lg p-3">
                  {rep.virustotal_stats?.error && typeof rep.virustotal_stats.error === "string" && rep.virustotal_stats.error.includes("API key") ? (
                    <p className="text-xs text-dark-500">API key not configured</p>
                  ) : (
                    <div className="space-y-3">
                      {/* Stats bar */}
                      <div className="flex items-center gap-0 h-3 rounded-full overflow-hidden bg-dark-700">
                        {vtTotal > 0 && (
                          <>
                            {rep.virustotal_malicious > 0 && (
                              <div
                                className="h-full bg-red-500"
                                style={{ width: `${(rep.virustotal_malicious / vtTotal) * 100}%` }}
                                title={`${rep.virustotal_malicious} malicious`}
                              />
                            )}
                            {rep.virustotal_suspicious > 0 && (
                              <div
                                className="h-full bg-yellow-500"
                                style={{ width: `${(rep.virustotal_suspicious / vtTotal) * 100}%` }}
                                title={`${rep.virustotal_suspicious} suspicious`}
                              />
                            )}
                            {rep.virustotal_harmless > 0 && (
                              <div
                                className="h-full bg-green-500"
                                style={{ width: `${(rep.virustotal_harmless / vtTotal) * 100}%` }}
                                title={`${rep.virustotal_harmless} harmless`}
                              />
                            )}
                            {rep.virustotal_undetected > 0 && (
                              <div
                                className="h-full bg-dark-500"
                                style={{ width: `${(rep.virustotal_undetected / vtTotal) * 100}%` }}
                                title={`${rep.virustotal_undetected} undetected`}
                              />
                            )}
                          </>
                        )}
                      </div>

                      {/* Stats legend */}
                      <div className="grid grid-cols-4 gap-2 text-center">
                        <div>
                          <p className="text-sm font-bold text-red-400">{rep.virustotal_malicious}</p>
                          <p className="text-[10px] text-dark-500">Malicious</p>
                        </div>
                        <div>
                          <p className="text-sm font-bold text-yellow-400">{rep.virustotal_suspicious}</p>
                          <p className="text-[10px] text-dark-500">Suspicious</p>
                        </div>
                        <div>
                          <p className="text-sm font-bold text-green-400">{rep.virustotal_harmless}</p>
                          <p className="text-[10px] text-dark-500">Harmless</p>
                        </div>
                        <div>
                          <p className="text-sm font-bold text-dark-400">{rep.virustotal_undetected}</p>
                          <p className="text-[10px] text-dark-500">Undetected</p>
                        </div>
                      </div>

                      {/* Categories */}
                      {rep.virustotal_stats?.categories && typeof rep.virustotal_stats.categories === "object" && Object.keys(rep.virustotal_stats.categories).length > 0 && (
                        <div>
                          <p className="text-[10px] text-dark-500 mb-1">Categories:</p>
                          <div className="flex flex-wrap gap-1">
                            {Object.entries(rep.virustotal_stats.categories as Record<string, string>).slice(0, 5).map(([engine, cat]) => (
                              <span key={engine} className="px-2 py-0.5 rounded-full text-[10px] bg-dark-700 text-dark-300">
                                {String(cat)}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Meta Info */}
              <div className="flex items-center justify-between pt-2 border-t border-dark-700/50">
                <div className="text-xs text-dark-500 space-x-3">
                  {rep.checked_at && (
                    <span>Checked: {new Date(rep.checked_at).toLocaleString()}</span>
                  )}
                  <span>Check count: {rep.check_count}</span>
                  {!rep.is_cache_valid && <span className="text-yellow-400">Cache expired</span>}
                </div>
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={(e) => { e.stopPropagation(); onRecheck(); }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-500/10 text-primary-400 text-xs font-medium hover:bg-primary-500/20 transition-colors"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Recheck
                </motion.button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ─── Domain Card ────────────────────────────────────────────────────────────

function DomainCard({
  entry,
  isExpanded,
  detail,
  detailLoading,
  onToggle,
  onMarkSafe,
  onCopy,
  copied,
  onCheckReputation,
  onAddToList,
}: {
  entry: ExternalDomainEntryWithReputation;
  isExpanded: boolean;
  detail: DomainDetail | null;
  detailLoading: boolean;
  onToggle: () => void;
  onMarkSafe: () => void;
  onCopy: () => void;
  copied: boolean;
  onCheckReputation: () => void;
  onAddToList: (listType: "whitelist" | "blacklist") => void;
}) {
  const statusConfig = {
    safe: { icon: <CheckCircle2 className="w-4 h-4" />, color: "text-green-400", bg: "bg-green-500/10", border: "border-green-500/20", label: "Safe" },
    suspicious: { icon: <AlertTriangle className="w-4 h-4" />, color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/20", label: "Suspicious" },
    new: { icon: <TrendingUp className="w-4 h-4" />, color: "text-blue-400", bg: "bg-blue-500/10", border: "border-blue-500/20", label: "New" },
  };

  const cfg = statusConfig[entry.status] || statusConfig.new;

  return (
    <motion.div
      layout
      className={`bg-dark-800/60 backdrop-blur-sm border rounded-xl overflow-hidden ${cfg.border}`}
    >
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 p-4 text-left hover:bg-dark-700/30 transition-colors"
      >
        <div className={`p-1.5 rounded-lg ${cfg.bg}`}>
          <div className={cfg.color}>{cfg.icon}</div>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-dark-200 truncate">{entry.domain}</span>
            <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${cfg.bg} ${cfg.color}`}>
              {cfg.label}
            </span>
            {entry.list_classification === "whitelist" && (
              <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-green-500/15 text-green-400 border border-green-500/20">
                ✓ Whitelist
              </span>
            )}
            {entry.list_classification === "blacklist" && (
              <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-red-500/15 text-red-400 border border-red-500/20">
                ✕ Blacklist
              </span>
            )}
            {entry.reputation && (
              <RiskBadge level={entry.reputation.risk_level} small />
            )}
          </div>
          <div className="flex items-center gap-3 mt-1 text-xs text-dark-500">
            <span>Seen {entry.times_seen}×</span>
            <span>·</span>
            <span>{entry.found_on_pages.length} pages</span>
            <span>·</span>
            <span>{entry.days_since_first_seen}d ago</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            onClick={(e) => { e.stopPropagation(); onCopy(); }}
            className="p-1.5 rounded-lg hover:bg-dark-700 text-dark-500 hover:text-dark-300 transition-colors"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
          </motion.button>
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-dark-500" />
          ) : (
            <ChevronRight className="w-4 h-4 text-dark-500" />
          )}
        </div>
      </button>

      {/* Suspicious reasons */}
      {entry.is_suspicious && entry.suspicious_reasons.length > 0 && (
        <div className="px-4 pb-2">
          <div className="flex flex-wrap gap-1">
            {entry.suspicious_reasons.map((r, i) => (
              <span key={i} className="px-2 py-0.5 rounded-full text-[10px] bg-red-500/10 text-red-400 border border-red-500/20">
                {r}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Expanded Detail */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="border-t border-dark-700/50"
          >
            <div className="p-4 space-y-4">
              {detailLoading ? (
                <div className="flex items-center justify-center py-6">
                  <RefreshCw className="w-5 h-5 text-primary-500 animate-spin" />
                </div>
              ) : detail ? (
                <>
                  {/* Reputation inline */}
                  {entry.reputation && entry.reputation.check_status === "completed" && (
                    <div className="bg-dark-900/50 rounded-lg p-3">
                      <h4 className="text-xs font-semibold text-dark-300 flex items-center gap-1.5 mb-2">
                        <Shield className="w-3.5 h-3.5 text-purple-400" />
                        Reputation
                      </h4>
                      <div className="grid grid-cols-3 gap-3 text-center">
                        <div>
                          <RiskBadge level={entry.reputation.risk_level} />
                          <p className="text-[10px] text-dark-500 mt-1">Overall</p>
                        </div>
                        <div>
                          <p className="text-xs font-medium text-dark-300">
                            {entry.reputation.safe_browsing_result?.matched ? "⚠️ Threat" : "✅ Clean"}
                          </p>
                          <p className="text-[10px] text-dark-500">Safe Browsing</p>
                        </div>
                        <div>
                          <p className="text-xs font-medium text-dark-300">
                            {entry.reputation.virustotal_malicious > 0
                              ? `🔴 ${entry.reputation.virustotal_malicious} mal.`
                              : "✅ Clean"}
                          </p>
                          <p className="text-[10px] text-dark-500">VirusTotal</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Found on pages */}
                  {entry.found_on_pages.length > 0 && (
                    <div>
                      <h4 className="text-xs font-semibold text-dark-300 flex items-center gap-1.5 mb-2">
                        <MapPin className="w-3.5 h-3.5 text-primary-400" />
                        Found on pages
                      </h4>
                      <div className="space-y-1 max-h-40 overflow-y-auto">
                        {entry.found_on_pages.slice(0, 10).map((page, i) => (
                          <div key={i} className="flex items-center gap-2 text-xs">
                            <ArrowRight className="w-3 h-3 text-dark-600 flex-shrink-0" />
                            <a
                              href={page}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-primary-400 hover:text-primary-300 truncate transition-colors"
                            >
                              {page}
                            </a>
                          </div>
                        ))}
                        {entry.found_on_pages.length > 10 && (
                          <p className="text-xs text-dark-500 pl-5">
                            +{entry.found_on_pages.length - 10} more pages
                          </p>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Related URLs */}
                  {detail.urls.length > 0 && (
                    <div>
                      <h4 className="text-xs font-semibold text-dark-300 flex items-center gap-1.5 mb-2">
                        <ExternalLink className="w-3.5 h-3.5 text-blue-400" />
                        External URLs ({detail.urls.length})
                      </h4>
                      <div className="space-y-1 max-h-40 overflow-y-auto">
                        {detail.urls.slice(0, 15).map((u, i) => (
                          <div key={i} className="flex items-center gap-2 text-xs group">
                            <span className="px-1.5 py-0.5 rounded bg-dark-700 text-dark-400 text-[10px] flex-shrink-0">
                              {u.source}
                            </span>
                            <a
                              href={u.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-dark-300 hover:text-primary-400 truncate transition-colors"
                            >
                              {u.url}
                            </a>
                            {u.source_url && (
                              <span className="text-dark-600 flex-shrink-0 hidden group-hover:inline">
                                ← {new URL(u.source_url).pathname}
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex items-center gap-2 pt-2 border-t border-dark-700/50 flex-wrap">
                    {entry.status !== "safe" && (
                      <motion.button
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={onMarkSafe}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-green-500/10 text-green-400 text-xs font-medium hover:bg-green-500/20 transition-colors"
                      >
                        <ShieldCheck className="w-3.5 h-3.5" />
                        Mark as Safe
                      </motion.button>
                    )}
                    <motion.button
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={onCheckReputation}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-500/10 text-primary-400 text-xs font-medium hover:bg-primary-500/20 transition-colors"
                    >
                      <Scan className="w-3.5 h-3.5" />
                      Check Reputation
                    </motion.button>
                    {entry.list_classification !== "whitelist" && (
                      <motion.button
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => onAddToList("whitelist")}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 text-xs font-medium hover:bg-emerald-500/20 transition-colors border border-emerald-500/20"
                      >
                        <ShieldCheck className="w-3.5 h-3.5" />
                        + Whitelist
                      </motion.button>
                    )}
                    {entry.list_classification !== "blacklist" && (
                      <motion.button
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => onAddToList("blacklist")}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/10 text-red-400 text-xs font-medium hover:bg-red-500/20 transition-colors border border-red-500/20"
                      >
                        <ShieldX className="w-3.5 h-3.5" />
                        + Blacklist
                      </motion.button>
                    )}
                  </div>
                </>
              ) : (
                <p className="text-xs text-dark-500 text-center py-4">
                  Select a site to view details
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ─── Alert Card ─────────────────────────────────────────────────────────────

function AlertCard({
  alert,
  compact,
  onAddToList,
  onIgnore,
  domainClassifications,
}: {
  alert: ExternalDomainAlertItem;
  compact?: boolean;
  onAddToList?: (domain: string, listType: "whitelist" | "blacklist", siteDomain?: string) => void;
  onIgnore?: (alertId: number) => void;
  domainClassifications?: Record<string, "whitelist" | "blacklist" | "unknown">;
}) {
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionDone, setActionDone] = useState<"whitelist" | "blacklist" | "ignored" | null>(null);

  const severityConfig = {
    info: { icon: <Globe className="w-4 h-4" />, color: "text-blue-400", bg: "bg-blue-500/10", border: "border-blue-500/20" },
    warning: { icon: <AlertTriangle className="w-4 h-4" />, color: "text-yellow-400", bg: "bg-yellow-500/10", border: "border-yellow-500/20" },
    critical: { icon: <ShieldAlert className="w-4 h-4" />, color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/20" },
  };

  const cfg = severityConfig[alert.severity] || severityConfig.info;

  // Check if domain is already in a list
  const existingClassification = domainClassifications?.[alert.external_domain] || null;
  // If we just did an action in this session, use that
  const currentStatus = actionDone || (existingClassification !== "unknown" ? existingClassification : null);

  const handleAction = async (listType: "whitelist" | "blacklist") => {
    if (!onAddToList) return;
    setActionLoading(listType);
    try {
      await onAddToList(alert.external_domain, listType, alert.site_domain);
      setActionDone(listType);
    } catch (err) {
      console.error("Action failed:", err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleIgnore = async () => {
    if (!onIgnore) return;
    setActionLoading("ignore");
    try {
      await onIgnore(alert.id);
      setActionDone("ignored");
    } catch (err) {
      console.error("Ignore failed:", err);
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      className={`flex items-start gap-3 p-3 rounded-xl border ${cfg.border} ${
        alert.is_read || actionDone === "ignored" ? "opacity-60" : ""
      } ${compact ? "bg-transparent" : "bg-dark-800/60 backdrop-blur-sm"}`}
    >
      <div className={`p-1.5 rounded-lg ${cfg.bg} flex-shrink-0`}>
        <div className={cfg.color}>{cfg.icon}</div>
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-medium ${cfg.color}`}>
            {alert.alert_type_display}
          </span>
          {!alert.is_read && !actionDone && (
            <span className="w-1.5 h-1.5 rounded-full bg-primary-500" />
          )}
        </div>
        <p className="text-sm text-dark-200 mt-0.5 font-medium">{alert.external_domain}</p>
        {!compact && (
          <p className="text-xs text-dark-400 mt-1 whitespace-pre-line">{alert.message}</p>
        )}
        <div className="flex items-center gap-2 mt-1.5 text-xs text-dark-500">
          <Clock className="w-3 h-3" />
          {new Date(alert.created_at).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })}
          {alert.site_domain && (
            <>
              <span>·</span>
              <span>{alert.site_domain}</span>
            </>
          )}
        </div>

        {/* Quick list actions */}
        {!compact && alert.external_domain && (
          <div className="flex items-center gap-1.5 mt-2">
            {currentStatus === "whitelist" ? (
              <span className="flex items-center gap-1 px-2 py-1 rounded-md bg-green-500/15 text-green-400
                         text-[10px] font-bold border border-green-500/25">
                <ShieldCheck className="w-3 h-3" />
                ✓ Whitelisted
              </span>
            ) : currentStatus === "blacklist" ? (
              <span className="flex items-center gap-1 px-2 py-1 rounded-md bg-red-500/15 text-red-400
                         text-[10px] font-bold border border-red-500/25">
                <ShieldX className="w-3 h-3" />
                ✗ Blacklisted
              </span>
            ) : currentStatus === "ignored" ? (
              <span className="flex items-center gap-1 px-2 py-1 rounded-md bg-dark-700/70 text-dark-400
                         text-[10px] font-bold border border-dark-600/50">
                <BellOff className="w-3 h-3" />
                Ignored
              </span>
            ) : (
              /* Show action buttons when not yet classified */
              <>
                <button
                  onClick={() => handleAction("whitelist")}
                  disabled={!!actionLoading}
                  className="flex items-center gap-1 px-2 py-1 rounded-md bg-green-500/10 text-green-400
                             text-[10px] font-medium hover:bg-green-500/20 border border-green-500/20 transition-colors
                             disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {actionLoading === "whitelist" ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <ShieldCheck className="w-3 h-3" />
                  )}
                  Whitelist
                </button>
                <button
                  onClick={() => handleAction("blacklist")}
                  disabled={!!actionLoading}
                  className="flex items-center gap-1 px-2 py-1 rounded-md bg-red-500/10 text-red-400
                             text-[10px] font-medium hover:bg-red-500/20 border border-red-500/20 transition-colors
                             disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {actionLoading === "blacklist" ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <ShieldX className="w-3 h-3" />
                  )}
                  Blacklist
                </button>
                <button
                  onClick={handleIgnore}
                  disabled={!!actionLoading}
                  className="flex items-center gap-1 px-2 py-1 rounded-md bg-dark-700/50 text-dark-400
                             text-[10px] font-medium hover:bg-dark-700 border border-dark-600/50 transition-colors
                             disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {actionLoading === "ignore" ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <BellOff className="w-3 h-3" />
                  )}
                  Ignore
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
}

// ─── Timeline View ──────────────────────────────────────────────────────────

function TimelineView({ entries }: { entries: TimelineEntry[] }) {
  if (entries.length === 0) {
    return (
      <div className="text-center py-12 text-dark-500">
        <Clock className="w-12 h-12 mx-auto mb-3 opacity-30" />
        <p>No timeline data available</p>
        <p className="text-xs mt-1">Run scans to build a timeline</p>
      </div>
    );
  }

  const grouped: Record<string, TimelineEntry[]> = {};
  entries.forEach((entry) => {
    const date = new Date(entry.first_seen).toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
    if (!grouped[date]) grouped[date] = [];
    grouped[date].push(entry);
  });

  return (
    <div className="relative">
      <div className="absolute left-[19px] top-0 bottom-0 w-0.5 bg-dark-700/50" />

      <div className="space-y-8">
        {Object.entries(grouped).map(([date, dateEntries]) => (
          <div key={date}>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-dark-800 border-2 border-dark-600 flex items-center justify-center z-10">
                <Clock className="w-4 h-4 text-dark-400" />
              </div>
              <h3 className="text-sm font-semibold text-dark-300">{date}</h3>
            </div>

            <div className="ml-[19px] pl-8 space-y-2">
              {dateEntries.map((entry, i) => (
                <motion.div
                  key={entry.domain}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className={`flex items-center gap-3 p-3 rounded-lg border ${
                    entry.is_suspicious
                      ? "bg-red-500/5 border-red-500/20"
                      : entry.status === "new"
                      ? "bg-green-500/5 border-green-500/20"
                      : "bg-dark-800/60 border-dark-700/50"
                  }`}
                >
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-dark-500">+</span>
                    <span className="font-medium text-dark-200">{entry.domain}</span>
                  </div>

                  {entry.is_suspicious ? (
                    <span className="px-2 py-0.5 rounded-full text-[10px] bg-red-500/20 text-red-400 font-bold">
                      ⚠️ suspicious
                    </span>
                  ) : entry.status === "safe" ? (
                    <span className="px-2 py-0.5 rounded-full text-[10px] bg-green-500/20 text-green-400 font-bold">
                      ✅ safe
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded-full text-[10px] bg-blue-500/20 text-blue-400 font-bold">
                      🆕 new
                    </span>
                  )}

                  <span className="text-xs text-dark-500 ml-auto">
                    seen {entry.times_seen}×
                  </span>
                </motion.div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
