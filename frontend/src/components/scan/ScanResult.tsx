"use client";

import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft,
  Globe,
  Link2,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  ExternalLink,
  Sparkles,
  Code,
  Bot,
  FileText,
  Hammer,
  Copy,
  Check,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Search,
  BarChart3,
  Eye,
  EyeOff,
  Plus,
  List,
  Lock,
  Unlock,
  Info,
  X,
  KeyRound,
  Bug,
} from "lucide-react";
import Link from "next/link";
import {
  api,
  Scan,
  DiscoveredURL,
  ExternalDomainGroup,
  URLTab,
  DomainListsResponse,
  VisibilityFilter,
  ListStatusFilter,
  URLSummary,
} from "@/lib/api";

interface ScanResultProps {
  scan: Scan;
}

const sourceIcons: Record<string, React.ReactNode> = {
  html: <FileText className="w-3.5 h-3.5" />,
  js: <Code className="w-3.5 h-3.5" />,
  robots: <Bot className="w-3.5 h-3.5" />,
  sitemap: <Globe className="w-3.5 h-3.5" />,
  bruteforce: <Hammer className="w-3.5 h-3.5" />,
};

const sourceColors: Record<string, string> = {
  html: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  js: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  robots: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  sitemap: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  bruteforce: "bg-red-500/10 text-red-400 border-red-500/20",
};

/* ── Auth Debug Banner ─────────────────────────────────────────── */

function AuthDebugBanner({ authMethod, authError }: { authMethod?: string; authError?: string }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: -5 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-red-500/10 border border-red-500/20 rounded-xl overflow-hidden"
    >
      <div className="p-3 flex items-center gap-3">
        <XCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
        <div className="flex-1">
          <p className="text-sm font-medium text-red-300">
            Ошибка авторизации{authMethod ? ` (${authMethod})` : ""}
          </p>
          <p className="text-xs text-red-400/70">
            Приватные страницы не были просканированы
          </p>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30 rounded-lg text-red-300 text-xs font-medium transition-colors"
        >
          <Bug className="w-3.5 h-3.5" />
          {expanded ? "Скрыть" : "Debug"}
        </button>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="border-t border-red-500/20"
          >
            <div className="p-4 space-y-3">
              <div>
                <p className="text-[11px] font-semibold text-dark-400 uppercase tracking-wider mb-1">
                  Метод авторизации
                </p>
                <p className="text-sm text-dark-200 font-mono bg-dark-800 px-3 py-1.5 rounded-lg">
                  {authMethod || "—"}
                </p>
              </div>
              <div>
                <p className="text-[11px] font-semibold text-dark-400 uppercase tracking-wider mb-1">
                  Ошибка
                </p>
                <pre className="text-xs text-red-300/80 bg-dark-800 px-3 py-2 rounded-lg overflow-x-auto whitespace-pre-wrap break-words max-h-48 overflow-y-auto">
                  {authError || "Нет подробной информации об ошибке"}
                </pre>
              </div>
              <div className="pt-1">
                <Link
                  href="/settings"
                  className="inline-flex items-center gap-1.5 text-xs text-primary-400 hover:text-primary-300 transition-colors"
                >
                  <KeyRound className="w-3.5 h-3.5" />
                  Перейти к настройкам авторизации
                </Link>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export function ScanResult({ scan }: ScanResultProps) {
  const [urls, setUrls] = useState<DiscoveredURL[]>([]);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<URLTab>("all");
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [searchDebounced, setSearchDebounced] = useState("");
  const [nextPage, setNextPage] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [copiedUrl, setCopiedUrl] = useState<string | null>(null);
  const [externalDomains, setExternalDomains] = useState<ExternalDomainGroup[]>([]);
  const [showExternalDomains, setShowExternalDomains] = useState(false);
  const [listActionLoading, setListActionLoading] = useState<string | null>(null);
  const [listActionDone, setListActionDone] = useState<Record<string, "whitelist" | "blacklist">>({});
  const [domainLists, setDomainLists] = useState<DomainListsResponse | null>(null);
  const [showWhitelistMatches, setShowWhitelistMatches] = useState(true);
  const [showBlacklistMatches, setShowBlacklistMatches] = useState(true);
  const [showListsPanel, setShowListsPanel] = useState(true);
  const [addListInput, setAddListInput] = useState("");
  const [addListType, setAddListType] = useState<"whitelist" | "blacklist">("whitelist");
  const [addingToList, setAddingToList] = useState(false);

  // New state for enhanced features
  const [visibility, setVisibility] = useState<VisibilityFilter>("all");
  const [listStatus, setListStatus] = useState<ListStatusFilter>("all");
  const [urlSummary, setUrlSummary] = useState<URLSummary | null>(null);
  const [selectedUrl, setSelectedUrl] = useState<DiscoveredURL | null>(null);

  const handleAddToList = async (domain: string, listType: "whitelist" | "blacklist") => {
    setListActionLoading(`${domain}-${listType}`);
    try {
      await api.domainListQuickAction({
        site_domain: scan.domain,
        domain,
        list_type: listType,
      });
      setListActionDone((prev) => ({ ...prev, [domain]: listType }));
      // Reload lists + summary
      if (scan.domain) {
        api.getDomainLists(scan.domain).then(setDomainLists).catch(() => {});
        api.getScanUrlSummary(scan.id).then(setUrlSummary).catch(() => {});
      }
    } catch (err) {
      console.error("Failed to add to list:", err);
    } finally {
      setListActionLoading(null);
    }
  };

  const handleInlineAdd = async () => {
    if (!addListInput.trim()) return;
    setAddingToList(true);
    try {
      const domains = addListInput.split(/[\n,;]+/).map(d => d.trim()).filter(Boolean);
      await api.addToDomainList({
        site_domain: scan.domain,
        domains,
        list_type: addListType,
      });
      setAddListInput("");
      api.getDomainLists(scan.domain).then(setDomainLists).catch(() => {});
      api.getScanUrlSummary(scan.id).then(setUrlSummary).catch(() => {});
    } catch (err) {
      console.error("Failed to add to list:", err);
    } finally {
      setAddingToList(false);
    }
  };

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => setSearchDebounced(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const loadUrls = useCallback(async () => {
    if (scan.status !== "completed") return;
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (tab !== "all") params.tab = tab;
      if (sourceFilter !== "all") params.source = sourceFilter;
      if (searchDebounced) params.search = searchDebounced;
      if (visibility !== "all") params.visibility = visibility;
      if (listStatus !== "all") params.list_status = listStatus;

      const data = await api.getScanUrls(scan.id, params);
      setUrls(data.results || []);
      setNextPage(data.next);
      setTotalCount(data.count);
    } catch (err) {
      console.error("Failed to load URLs:", err);
    } finally {
      setLoading(false);
    }
  }, [scan.id, scan.status, tab, sourceFilter, searchDebounced, visibility, listStatus]);

  useEffect(() => {
    loadUrls();
  }, [loadUrls]);

  // Load external domains summary
  useEffect(() => {
    if (scan.status === "completed") {
      api.getExternalDomains(scan.id, true).then(setExternalDomains).catch(() => {});
    }
  }, [scan.id, scan.status]);

  // Load domain lists for whitelist/blacklist matching
  useEffect(() => {
    if (scan.status === "completed" && scan.domain) {
      api.getDomainLists(scan.domain).then(setDomainLists).catch(() => {});
    }
  }, [scan.id, scan.status, scan.domain]);

  // Load URL summary
  useEffect(() => {
    if (scan.status === "completed") {
      api.getScanUrlSummary(scan.id).then(setUrlSummary).catch(() => {});
    }
  }, [scan.id, scan.status]);

  // Compute whitelist/blacklist matches
  const whitelistSet = new Set(domainLists?.whitelist.map((e) => e.domain) || []);
  const blacklistSet = new Set(domainLists?.blacklist.map((e) => e.domain) || []);

  const whitelistMatches = externalDomains.filter((ed) => whitelistSet.has(ed.external_domain));
  const blacklistMatches = externalDomains.filter((ed) => blacklistSet.has(ed.external_domain));

  async function loadMore() {
    if (!nextPage || loadingMore) return;
    setLoadingMore(true);
    try {
      const data = await api.fetchNextPage<DiscoveredURL>(nextPage);
      setUrls((prev) => [...prev, ...(data.results || [])]);
      setNextPage(data.next);
    } catch (err) {
      console.error("Failed to load more:", err);
    } finally {
      setLoadingMore(false);
    }
  }

  async function copyUrl(url: string) {
    try {
      await navigator.clipboard.writeText(url);
      setCopiedUrl(url);
      setTimeout(() => setCopiedUrl(null), 2000);
    } catch {
      // fallback
    }
  }

  const statusBadge = () => {
    switch (scan.status) {
      case "completed":
        return (
          <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-sm">
            <CheckCircle2 className="w-4 h-4" /> Completed
          </span>
        );
      case "running":
        return (
          <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20 text-sm">
            <Loader2 className="w-4 h-4 animate-spin" /> Scanning
          </span>
        );
      case "pending":
        return (
          <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20 text-sm">
            <Clock className="w-4 h-4" /> Pending
          </span>
        );
      case "failed":
        return (
          <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/10 text-red-400 border border-red-500/20 text-sm">
            <XCircle className="w-4 h-4" /> Failed
          </span>
        );
    }
  };

  const tabs: { key: URLTab; label: string; count: number; icon: React.ReactNode; color: string }[] = [
    { key: "all", label: "All", count: scan.total_urls, icon: <Link2 className="w-3.5 h-3.5" />, color: "primary" },
    { key: "new", label: "New", count: scan.new_urls, icon: <Sparkles className="w-3.5 h-3.5" />, color: "emerald" },
    { key: "hidden", label: "Hidden", count: scan.hidden_urls, icon: <ShieldAlert className="w-3.5 h-3.5" />, color: "amber" },
    { key: "external", label: "External", count: scan.external_urls, icon: <ExternalLink className="w-3.5 h-3.5" />, color: "orange" },
    { key: "errors", label: "Errors", count: scan.error_urls, icon: <AlertTriangle className="w-3.5 h-3.5" />, color: "red" },
    ...(scan.private_urls > 0 ? [{ key: "private" as URLTab, label: "Private", count: scan.private_urls, icon: <Lock className="w-3.5 h-3.5" />, color: "violet" }] : []),
  ];

  // Determine list status for an external domain
  const getDomainListStatus = (extDomain: string): "whitelist" | "blacklist" | "unknown" | null => {
    if (!extDomain) return null;
    if (listActionDone[extDomain]) return listActionDone[extDomain] as "whitelist" | "blacklist";
    if (blacklistSet.has(extDomain)) return "blacklist";
    if (whitelistSet.has(extDomain)) return "whitelist";
    return "unknown";
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="p-2 rounded-lg hover:bg-dark-800 transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-dark-400" />
          </Link>
          <div>
            <h1 className="text-xl md:text-2xl font-bold flex items-center gap-2">
              <Globe className="w-5 h-5 md:w-6 md:h-6 text-primary-400" />
              {scan.domain}
            </h1>
            <p className="text-xs md:text-sm text-dark-500 mt-1">
              Scan #{scan.id}
              {scan.started_at && ` · ${new Date(scan.started_at).toLocaleString()}`}
              {scan.duration && ` · ${scan.duration}s`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {statusBadge()}
        </div>
      </div>

      {/* ═══════ Auth Status Banner ═══════ */}
      {scan.status === "completed" && scan.auth_success === true && (
        <motion.div
          initial={{ opacity: 0, y: -5 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-green-500/10 border border-green-500/20 rounded-xl p-3 flex items-center gap-3"
        >
          <Unlock className="w-5 h-5 text-green-400 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-medium text-green-300">
              Авторизация успешна{scan.auth_method ? ` (${scan.auth_method})` : ""}
            </p>
            <p className="text-xs text-green-400/70">Приватные страницы были просканированы</p>
          </div>
        </motion.div>
      )}

      {scan.status === "completed" && scan.auth_success === false && (
        <AuthDebugBanner
          authMethod={scan.auth_method}
          authError={scan.auth_error}
        />
      )}

      {/* ═══════ Summary Stats with Public/Private ═══════ */}
      {scan.status === "completed" && urlSummary && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-3"
        >
          {/* Main stats row */}
          <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-8 gap-2">
            <SummaryStat label="Total" value={urlSummary.total} color="white" />
            <SummaryStat
              label="🌐 Public"
              value={urlSummary.public}
              color="blue"
              active={visibility === "public"}
              onClick={() => setVisibility(visibility === "public" ? "all" : "public")}
            />
            <SummaryStat
              label="🔒 Private"
              value={urlSummary.private}
              color="violet"
              active={visibility === "private"}
              onClick={() => setVisibility(visibility === "private" ? "all" : "private")}
            />
            <SummaryStat label="New" value={scan.new_urls} color="emerald" />
            <SummaryStat
              label="🟢 Whitelist"
              value={urlSummary.whitelist}
              color="green"
              active={listStatus === "whitelist"}
              onClick={() => setListStatus(listStatus === "whitelist" ? "all" : "whitelist")}
            />
            <SummaryStat
              label="🔴 Blacklist"
              value={urlSummary.blacklist}
              color="red"
              active={listStatus === "blacklist"}
              onClick={() => setListStatus(listStatus === "blacklist" ? "all" : "blacklist")}
            />
            <SummaryStat
              label="🟡 Unknown"
              value={urlSummary.unknown}
              color="amber"
              active={listStatus === "unknown"}
              onClick={() => setListStatus(listStatus === "unknown" ? "all" : "unknown")}
            />
            <SummaryStat label="Errors" value={scan.error_urls} color="red" />
          </div>

          {/* Active filters indicator */}
          {(visibility !== "all" || listStatus !== "all") && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              className="flex items-center gap-2 flex-wrap"
            >
              <span className="text-[10px] text-dark-500 uppercase tracking-wider font-medium">Active filters:</span>
              {visibility !== "all" && (
                <button
                  onClick={() => setVisibility("all")}
                  className={`flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium border transition-colors ${
                    visibility === "public"
                      ? "bg-blue-500/15 text-blue-400 border-blue-500/30"
                      : "bg-violet-500/15 text-violet-400 border-violet-500/30"
                  }`}
                >
                  {visibility === "public" ? <Unlock className="w-3 h-3" /> : <Lock className="w-3 h-3" />}
                  {visibility === "public" ? "Public URLs" : "Private URLs"}
                  <X className="w-3 h-3 ml-1 opacity-60 hover:opacity-100" />
                </button>
              )}
              {listStatus !== "all" && (
                <button
                  onClick={() => setListStatus("all")}
                  className={`flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium border transition-colors ${
                    listStatus === "whitelist"
                      ? "bg-green-500/15 text-green-400 border-green-500/30"
                      : listStatus === "blacklist"
                      ? "bg-red-500/15 text-red-400 border-red-500/30"
                      : "bg-amber-500/15 text-amber-400 border-amber-500/30"
                  }`}
                >
                  {listStatus === "whitelist" ? <ShieldCheck className="w-3 h-3" /> :
                   listStatus === "blacklist" ? <ShieldX className="w-3 h-3" /> :
                   <AlertTriangle className="w-3 h-3" />}
                  {listStatus === "whitelist" ? "Whitelist" : listStatus === "blacklist" ? "Blacklist" : "Unknown"}
                  <X className="w-3 h-3 ml-1 opacity-60 hover:opacity-100" />
                </button>
              )}
              <button
                onClick={() => { setVisibility("all"); setListStatus("all"); }}
                className="text-[10px] text-dark-500 hover:text-dark-300 underline transition-colors"
              >
                Clear all
              </button>
            </motion.div>
          )}
        </motion.div>
      )}

      {/* Fallback summary if url_summary not yet loaded */}
      {scan.status === "completed" && !urlSummary && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="grid grid-cols-3 md:grid-cols-6 gap-2 md:gap-3"
        >
          <SummaryStat label="Total" value={scan.total_urls} color="white" />
          <SummaryStat label="New" value={scan.new_urls} color="emerald" />
          <SummaryStat label="Internal" value={scan.internal_urls} color="blue" />
          <SummaryStat label="External" value={scan.external_urls} color="orange" />
          <SummaryStat label="Hidden" value={scan.hidden_urls} color="amber" />
          <SummaryStat label="Errors" value={scan.error_urls} color="red" />
        </motion.div>
      )}

      {/* Source Breakdown */}
      {scan.status === "completed" && scan.source_breakdown && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="flex items-center gap-2 overflow-x-auto pb-1"
        >
          <BarChart3 className="w-4 h-4 text-dark-500 flex-shrink-0" />
          {Object.entries(scan.source_breakdown).map(([src, count]) => (
            <span
              key={src}
              className={`flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-medium border whitespace-nowrap ${
                sourceColors[src] || "bg-dark-700 text-dark-400 border-dark-600"
              }`}
            >
              {sourceIcons[src]}
              {src}: {count}
            </span>
          ))}
        </motion.div>
      )}

      {/* ═══════ Domain Lists Panel — Whitelist / Blacklist ═══════ */}
      {scan.status === "completed" && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.12 }}
          className="bg-dark-800/30 border border-dark-700/50 rounded-xl overflow-hidden"
        >
          {/* Panel Header */}
          <button
            onClick={() => setShowListsPanel(!showListsPanel)}
            className="flex items-center justify-between w-full px-4 py-3 hover:bg-dark-800/50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <List className="w-5 h-5 text-primary-400" />
              <span className="text-sm font-semibold text-dark-200">
                Domain Lists
              </span>
              <div className="flex items-center gap-1.5 ml-2">
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-green-500/15 text-green-400 font-medium">
                  ✓ {domainLists?.whitelist.length || 0} whitelist
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/15 text-red-400 font-medium">
                  ✕ {domainLists?.blacklist.length || 0} blacklist
                </span>
                {urlSummary && urlSummary.unknown_domains.length > 0 && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-400 font-medium">
                    ? {urlSummary.unknown_domains.length} unclassified
                  </span>
                )}
              </div>
            </div>
            <ChevronDown className={`w-4 h-4 text-dark-500 transition-transform ${showListsPanel ? "rotate-180" : ""}`} />
          </button>

          <AnimatePresence>
            {showListsPanel && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <div className="px-4 pb-4 space-y-4">
                  {/* Inline Add Form */}
                  <div className="flex gap-2">
                    <div className="flex-1 relative">
                      <input
                        type="text"
                        value={addListInput}
                        onChange={(e) => setAddListInput(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && handleInlineAdd()}
                        placeholder="Enter domain (e.g. example.com)"
                        className="w-full px-3 py-2 bg-dark-800/70 border border-dark-700 rounded-lg text-xs
                                   placeholder-dark-500 focus:outline-none focus:border-primary-500 transition-colors"
                      />
                    </div>
                    <select
                      value={addListType}
                      onChange={(e) => setAddListType(e.target.value as "whitelist" | "blacklist")}
                      className="bg-dark-800 border border-dark-700 rounded-lg px-2 py-2 text-xs text-dark-300 focus:border-primary-500 focus:outline-none"
                    >
                      <option value="whitelist">Whitelist</option>
                      <option value="blacklist">Blacklist</option>
                    </select>
                    <button
                      onClick={handleInlineAdd}
                      disabled={addingToList || !addListInput.trim()}
                      className="flex items-center gap-1 px-3 py-2 rounded-lg bg-primary-500/20 text-primary-400 border border-primary-500/30
                                 text-xs font-medium hover:bg-primary-500/30 transition-colors disabled:opacity-40"
                    >
                      {addingToList ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
                      Add
                    </button>
                  </div>

                  {/* Blacklisted Domains Found */}
                  {blacklistMatches.length > 0 && (
                    <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-3">
                      <button
                        onClick={() => setShowBlacklistMatches(!showBlacklistMatches)}
                        className="flex items-center justify-between w-full mb-1"
                      >
                        <div className="flex items-center gap-2">
                          <ShieldX className="w-4 h-4 text-red-400" />
                          <span className="text-xs font-semibold text-red-400">
                            🚨 Blacklisted Domains Detected
                          </span>
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-full bg-red-500/15 text-red-300">
                            {blacklistMatches.length}
                          </span>
                        </div>
                        <ChevronDown className={`w-3.5 h-3.5 text-red-400 transition-transform ${showBlacklistMatches ? "rotate-180" : ""}`} />
                      </button>
                      <AnimatePresence>
                        {showBlacklistMatches && (
                          <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: "auto" }}
                            exit={{ opacity: 0, height: 0 }}
                            className="mt-2 space-y-2 overflow-hidden"
                          >
                            {blacklistMatches.map((ed) => (
                              <MatchedDomainCard key={ed.external_domain} ed={ed} type="blacklist" sourceColors={sourceColors} />
                            ))}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  )}

                  {/* Whitelisted Domains Found */}
                  {whitelistMatches.length > 0 && (
                    <div className="bg-green-500/5 border border-green-500/15 rounded-lg p-3">
                      <button
                        onClick={() => setShowWhitelistMatches(!showWhitelistMatches)}
                        className="flex items-center justify-between w-full mb-1"
                      >
                        <div className="flex items-center gap-2">
                          <ShieldCheck className="w-4 h-4 text-green-400" />
                          <span className="text-xs font-semibold text-green-400">
                            Whitelisted Domains Found
                          </span>
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-full bg-green-500/15 text-green-300">
                            {whitelistMatches.length}
                          </span>
                        </div>
                        <ChevronDown className={`w-3.5 h-3.5 text-green-400 transition-transform ${showWhitelistMatches ? "rotate-180" : ""}`} />
                      </button>
                      <AnimatePresence>
                        {showWhitelistMatches && (
                          <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: "auto" }}
                            exit={{ opacity: 0, height: 0 }}
                            className="mt-2 space-y-2 overflow-hidden"
                          >
                            {whitelistMatches.map((ed) => (
                              <MatchedDomainCard key={ed.external_domain} ed={ed} type="whitelist" sourceColors={sourceColors} />
                            ))}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  )}

                  {/* Unclassified External Domains */}
                  {externalDomains.filter(ed => !whitelistSet.has(ed.external_domain) && !blacklistSet.has(ed.external_domain)).length > 0 && (
                    <div>
                      <p className="text-[10px] text-dark-500 uppercase tracking-wider font-medium mb-2">
                        Unclassified External Domains ({externalDomains.filter(ed => !whitelistSet.has(ed.external_domain) && !blacklistSet.has(ed.external_domain)).length})
                      </p>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 max-h-[300px] overflow-y-auto">
                        {externalDomains
                          .filter(ed => !whitelistSet.has(ed.external_domain) && !blacklistSet.has(ed.external_domain))
                          .map((ed) => (
                            <div
                              key={ed.external_domain}
                              className="flex items-center justify-between gap-2 bg-dark-800/50 rounded-lg border border-dark-700/30 px-3 py-2"
                            >
                              <div className="flex items-center gap-2 min-w-0">
                                <Globe className="w-3 h-3 text-dark-500 flex-shrink-0" />
                                <span className="text-xs text-dark-300 truncate">{ed.external_domain}</span>
                                <span className="text-[10px] text-dark-600 font-mono flex-shrink-0">{ed.count}</span>
                              </div>
                              <div className="flex items-center gap-1 flex-shrink-0">
                                {listActionDone[ed.external_domain] ? (
                                  <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                                    listActionDone[ed.external_domain] === "whitelist"
                                      ? "bg-green-500/15 text-green-400"
                                      : "bg-red-500/15 text-red-400"
                                  }`}>
                                    ✓ {listActionDone[ed.external_domain] === "whitelist" ? "WL" : "BL"}
                                  </span>
                                ) : (
                                  <>
                                    <button
                                      onClick={() => handleAddToList(ed.external_domain, "whitelist")}
                                      disabled={listActionLoading === `${ed.external_domain}-whitelist`}
                                      className="p-1 rounded hover:bg-green-500/20 transition-colors" title="Whitelist"
                                    >
                                      {listActionLoading === `${ed.external_domain}-whitelist` ? (
                                        <Loader2 className="w-3 h-3 text-green-400 animate-spin" />
                                      ) : (
                                        <ShieldCheck className="w-3 h-3 text-green-500/50 hover:text-green-400" />
                                      )}
                                    </button>
                                    <button
                                      onClick={() => handleAddToList(ed.external_domain, "blacklist")}
                                      disabled={listActionLoading === `${ed.external_domain}-blacklist`}
                                      className="p-1 rounded hover:bg-red-500/20 transition-colors" title="Blacklist"
                                    >
                                      {listActionLoading === `${ed.external_domain}-blacklist` ? (
                                        <Loader2 className="w-3 h-3 text-red-400 animate-spin" />
                                      ) : (
                                        <ShieldX className="w-3 h-3 text-red-500/50 hover:text-red-400" />
                                      )}
                                    </button>
                                  </>
                                )}
                              </div>
                            </div>
                          ))}
                      </div>
                    </div>
                  )}

                  {/* Empty state */}
                  {externalDomains.length === 0 && (domainLists?.whitelist.length || 0) === 0 && (domainLists?.blacklist.length || 0) === 0 && (
                    <div className="text-center py-6 text-dark-500">
                      <ShieldAlert className="w-8 h-8 mx-auto mb-2 opacity-30" />
                      <p className="text-xs">No external domains found in this scan</p>
                      <p className="text-[10px] text-dark-600 mt-1">Add domains manually using the form above</p>
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      )}

      {/* Running / Pending state */}
      {(scan.status === "running" || scan.status === "pending") && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center py-20">
          <Loader2 className="w-12 h-12 text-primary-400 animate-spin mx-auto mb-4" />
          <p className="text-lg font-medium">Loading scan data...</p>
        </motion.div>
      )}

      {/* Failed state */}
      {scan.status === "failed" && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center py-20">
          <XCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <p className="text-lg font-medium">Scan Failed</p>
          {scan.error_message && (
            <p className="text-sm text-dark-500 mt-2 max-w-md mx-auto">{scan.error_message}</p>
          )}
        </motion.div>
      )}

      {/* ═══════ URL List with Tabs ═══════ */}
      {scan.status === "completed" && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.15 }}>
          {/* Tabs */}
          <div className="flex items-center gap-1 overflow-x-auto pb-2 mb-3 border-b border-dark-700/50">
            {tabs.map((t) => {
              const isActive = tab === t.key;
              const colorMap: Record<string, string> = {
                primary: "text-primary-400 border-primary-500",
                emerald: "text-emerald-400 border-emerald-500",
                amber: "text-amber-400 border-amber-500",
                orange: "text-orange-400 border-orange-500",
                red: "text-red-400 border-red-500",
                violet: "text-violet-400 border-violet-500",
              };
              return (
                <button
                  key={t.key}
                  onClick={() => setTab(t.key)}
                  className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium whitespace-nowrap border-b-2 -mb-[2px] transition-all ${
                    isActive
                      ? `${colorMap[t.color]} bg-dark-800/50`
                      : "text-dark-500 border-transparent hover:text-dark-300 hover:border-dark-600"
                  }`}
                >
                  {t.icon}
                  {t.label}
                  {t.count > 0 && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                      isActive ? "bg-dark-700" : "bg-dark-800"
                    }`}>
                      {t.count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* ═══════ Visibility & List Status Filter Bar ═══════ */}
          <div className="flex flex-col gap-3 mb-4">
            {/* Row 1: Visibility + List Status toggles */}
            <div className="flex flex-wrap items-center gap-2">
              {/* Visibility filter */}
              <div className="flex items-center gap-1 bg-dark-800/50 rounded-lg p-1 border border-dark-700/50">
                {(["all", "public", "private"] as VisibilityFilter[]).map((v) => {
                  const isActive = visibility === v;
                  const icons: Record<VisibilityFilter, React.ReactNode> = {
                    all: <Eye className="w-3 h-3" />,
                    public: <Unlock className="w-3 h-3" />,
                    private: <Lock className="w-3 h-3" />,
                  };
                  const labels: Record<VisibilityFilter, string> = {
                    all: "All",
                    public: "🌐 Public",
                    private: "🔒 Private",
                  };
                  return (
                    <button
                      key={v}
                      onClick={() => setVisibility(v)}
                      className={`flex items-center gap-1 px-2.5 py-1.5 rounded-md text-[11px] font-medium transition-all ${
                        isActive
                          ? v === "public"
                            ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                            : v === "private"
                            ? "bg-violet-500/20 text-violet-400 border border-violet-500/30"
                            : "bg-dark-700 text-dark-200 border border-dark-600"
                          : "text-dark-500 border border-transparent hover:text-dark-300"
                      }`}
                    >
                      {icons[v]}
                      {labels[v]}
                    </button>
                  );
                })}
              </div>

              {/* Separator */}
              <div className="w-px h-6 bg-dark-700/50" />

              {/* List status filter */}
              <div className="flex items-center gap-1 bg-dark-800/50 rounded-lg p-1 border border-dark-700/50">
                {(["all", "whitelist", "blacklist", "unknown"] as ListStatusFilter[]).map((ls) => {
                  const isActive = listStatus === ls;
                  const config: Record<ListStatusFilter, { icon: React.ReactNode; label: string; activeClass: string }> = {
                    all: { icon: <List className="w-3 h-3" />, label: "All Lists", activeClass: "bg-dark-700 text-dark-200 border border-dark-600" },
                    whitelist: { icon: <ShieldCheck className="w-3 h-3" />, label: "🟢 Whitelist", activeClass: "bg-green-500/20 text-green-400 border border-green-500/30" },
                    blacklist: { icon: <ShieldX className="w-3 h-3" />, label: "🔴 Blacklist", activeClass: "bg-red-500/20 text-red-400 border border-red-500/30" },
                    unknown: { icon: <AlertTriangle className="w-3 h-3" />, label: "🟡 Unknown", activeClass: "bg-amber-500/20 text-amber-400 border border-amber-500/30" },
                  };
                  const c = config[ls];
                  return (
                    <button
                      key={ls}
                      onClick={() => setListStatus(ls)}
                      className={`flex items-center gap-1 px-2.5 py-1.5 rounded-md text-[11px] font-medium transition-all ${
                        isActive
                          ? c.activeClass
                          : "text-dark-500 border border-transparent hover:text-dark-300"
                      }`}
                    >
                      {c.icon}
                      {c.label}
                      {ls !== "all" && urlSummary && (
                        <span className="text-[9px] opacity-70 ml-0.5">
                          {urlSummary[ls as keyof Pick<URLSummary, "whitelist" | "blacklist" | "unknown">]}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Row 2: Search & Source Filter */}
            <div className="flex flex-col sm:flex-row gap-2">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-500" />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search URLs..."
                  className="w-full pl-10 pr-4 py-2.5 bg-dark-800/70 border border-dark-700 rounded-xl text-sm
                             placeholder-dark-500 focus:outline-none focus:border-primary-500 transition-colors"
                />
              </div>
              <div className="flex gap-1.5 overflow-x-auto pb-0.5">
                {["all", "html", "js", "robots", "sitemap", "bruteforce"].map((f) => (
                  <button
                    key={f}
                    onClick={() => setSourceFilter(f)}
                    className={`px-2.5 py-2 rounded-lg text-[10px] font-medium whitespace-nowrap transition-all flex items-center gap-1 ${
                      sourceFilter === f
                        ? "bg-primary-500/20 text-primary-400 border border-primary-500/30"
                        : "bg-dark-800 text-dark-500 border border-dark-700 hover:border-dark-600 hover:text-dark-400"
                    }`}
                  >
                    {f !== "all" && sourceIcons[f]}
                    {f === "all" ? "All" : f.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* External Domains Summary (shown when External tab is active) */}
          {tab === "external" && externalDomains.length > 0 && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              className="mb-4"
            >
              <button
                onClick={() => setShowExternalDomains(!showExternalDomains)}
                className="flex items-center gap-2 text-sm font-medium text-dark-300 mb-2 hover:text-primary-400 transition-colors"
              >
                <Globe className="w-4 h-4 text-orange-400" />
                External Domains ({externalDomains.length})
                <ChevronDown className={`w-4 h-4 transition-transform ${showExternalDomains ? "rotate-180" : ""}`} />
              </button>
              <AnimatePresence>
                {showExternalDomains && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 overflow-hidden"
                  >
                    {externalDomains.map((ed) => {
                      const domainStatus = getDomainListStatus(ed.external_domain);
                      return (
                        <div
                          key={ed.external_domain}
                          className={`bg-dark-800/50 rounded-lg border p-3 hover:border-orange-500/30 transition-colors ${
                            domainStatus === "blacklist"
                              ? "border-red-500/30"
                              : domainStatus === "whitelist"
                              ? "border-green-500/30"
                              : "border-dark-700/40"
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <div className="flex items-center gap-1.5">
                              {domainStatus === "whitelist" && <ShieldCheck className="w-3 h-3 text-green-400" />}
                              {domainStatus === "blacklist" && <ShieldX className="w-3 h-3 text-red-400" />}
                              <span
                                className="text-sm font-medium truncate text-dark-200 cursor-pointer hover:text-primary-400 transition-colors"
                                onClick={() => setSearch(ed.external_domain)}
                              >
                                {ed.external_domain}
                              </span>
                            </div>
                            <span className="text-xs text-orange-400 font-mono ml-2">{ed.count}</span>
                          </div>
                          {ed.sources && (
                            <div className="flex gap-1 mb-2">
                              {ed.sources.map((s) => (
                                <span
                                  key={s}
                                  className={`text-[9px] px-1 py-0.5 rounded border ${
                                    sourceColors[s] || "bg-dark-700 text-dark-400 border-dark-600"
                                  }`}
                                >
                                  {s}
                                </span>
                              ))}
                            </div>
                          )}
                          {/* Quick list actions */}
                          <div className="flex items-center gap-1.5 mt-1">
                            {listActionDone[ed.external_domain] ? (
                              <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
                                listActionDone[ed.external_domain] === "whitelist"
                                  ? "bg-green-500/15 text-green-400"
                                  : "bg-red-500/15 text-red-400"
                              }`}>
                                ✓ {listActionDone[ed.external_domain] === "whitelist" ? "Whitelisted" : "Blacklisted"}
                              </span>
                            ) : (
                              <>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleAddToList(ed.external_domain, "whitelist");
                                  }}
                                  disabled={listActionLoading === `${ed.external_domain}-whitelist`}
                                  className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-green-500/10 text-green-400
                                             text-[10px] font-medium hover:bg-green-500/20 border border-green-500/20
                                             transition-colors disabled:opacity-50"
                                >
                                  {listActionLoading === `${ed.external_domain}-whitelist` ? (
                                    <Loader2 className="w-2.5 h-2.5 animate-spin" />
                                  ) : (
                                    <ShieldCheck className="w-2.5 h-2.5" />
                                  )}
                                  Whitelist
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleAddToList(ed.external_domain, "blacklist");
                                  }}
                                  disabled={listActionLoading === `${ed.external_domain}-blacklist`}
                                  className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-red-500/10 text-red-400
                                             text-[10px] font-medium hover:bg-red-500/20 border border-red-500/20
                                             transition-colors disabled:opacity-50"
                                >
                                  {listActionLoading === `${ed.external_domain}-blacklist` ? (
                                    <Loader2 className="w-2.5 h-2.5 animate-spin" />
                                  ) : (
                                    <ShieldX className="w-2.5 h-2.5" />
                                  )}
                                  Blacklist
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          )}

          {/* Results count */}
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs text-dark-500">
              {loading ? "Loading..." : `${totalCount} result${totalCount !== 1 ? "s" : ""}`}
            </p>
          </div>

          {/* ═══════ URL Cards ═══════ */}
          <div className="space-y-1.5">
            <AnimatePresence mode="wait">
              {loading ? (
                <div className="space-y-2">
                  {[...Array(8)].map((_, i) => (
                    <div key={i} className="skeleton h-14 rounded-xl" />
                  ))}
                </div>
              ) : urls.length === 0 ? (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center py-16 text-dark-500">
                  <Eye className="w-10 h-10 mx-auto mb-3 opacity-30" />
                  <p className="font-medium">No URLs match your filters</p>
                  <p className="text-xs mt-1">Try adjusting the tab, source, visibility, or search</p>
                </motion.div>
              ) : (
                urls.map((url, i) => {
                  const domainStatus = url.external_domain ? getDomainListStatus(url.external_domain) : null;
                  return (
                    <motion.div
                      key={url.id}
                      initial={{ opacity: 0, y: 5 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.015 }}
                      className={`bg-dark-800/40 rounded-xl border p-3 md:p-3.5 transition-all group cursor-pointer ${
                        selectedUrl?.id === url.id
                          ? "border-primary-500/50 bg-dark-800/70"
                          : domainStatus === "blacklist"
                          ? "border-red-500/20 hover:border-red-500/40"
                          : domainStatus === "whitelist"
                          ? "border-green-500/15 hover:border-green-500/30"
                          : "border-dark-700/40 hover:border-dark-600/60"
                      }`}
                      onClick={() => setSelectedUrl(selectedUrl?.id === url.id ? null : url)}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          {/* Badges row */}
                          <div className="flex items-center gap-1.5 mb-1 flex-wrap">
                            {/* Visibility badge */}
                            {url.is_private ? (
                              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-violet-500/20 text-violet-400 border border-violet-500/20 flex items-center gap-0.5">
                                <Lock className="w-2.5 h-2.5" />
                                PRIVATE
                              </span>
                            ) : (
                              <span className="px-1.5 py-0.5 rounded text-[9px] font-medium bg-blue-500/10 text-blue-400/70 border border-blue-500/15 flex items-center gap-0.5">
                                <Unlock className="w-2.5 h-2.5" />
                                PUBLIC
                              </span>
                            )}
                            {url.is_new && (
                              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/20">
                                NEW
                              </span>
                            )}
                            {!url.is_internal && (
                              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-orange-500/20 text-orange-400 border border-orange-500/20 flex items-center gap-0.5">
                                <ExternalLink className="w-2.5 h-2.5" />
                                EXT
                              </span>
                            )}
                            {/* List status badge for external URLs */}
                            {!url.is_internal && domainStatus === "whitelist" && (
                              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-green-500/20 text-green-400 border border-green-500/20 flex items-center gap-0.5">
                                <ShieldCheck className="w-2.5 h-2.5" />
                                WL
                              </span>
                            )}
                            {!url.is_internal && domainStatus === "blacklist" && (
                              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-red-500/20 text-red-400 border border-red-500/20 flex items-center gap-0.5">
                                <ShieldX className="w-2.5 h-2.5" />
                                BL
                              </span>
                            )}
                            <span
                              className={`px-1.5 py-0.5 rounded text-[9px] font-medium border flex items-center gap-0.5 ${
                                sourceColors[url.source] || "bg-dark-700 text-dark-400 border-dark-600"
                              }`}
                            >
                              {sourceIcons[url.source]}
                              {url.source}
                            </span>
                            {url.status_code != null && url.status_code > 0 && (
                              <span
                                className={`text-[10px] font-mono px-1 py-0.5 rounded ${
                                  url.status_code >= 200 && url.status_code < 300
                                    ? "text-emerald-400 bg-emerald-500/10"
                                    : url.status_code >= 300 && url.status_code < 400
                                    ? "text-amber-400 bg-amber-500/10"
                                    : url.status_code === 403
                                    ? "text-orange-400 bg-orange-500/10"
                                    : "text-red-400 bg-red-500/10"
                                }`}
                              >
                                {url.status_code}
                              </span>
                            )}
                            {url.external_domain && (
                              <span className="text-[9px] text-dark-500 truncate max-w-[120px]">
                                → {url.external_domain}
                              </span>
                            )}
                          </div>

                          {/* URL */}
                          <div className="flex items-center gap-1">
                            <a
                              href={url.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs font-mono text-dark-300 hover:text-primary-400 transition-colors truncate"
                              onClick={(e) => e.stopPropagation()}
                            >
                              {url.url}
                            </a>
                          </div>

                          {/* Source URL (where this link was found) */}
                          {url.source_url && (
                            <div className="flex items-center gap-1.5 mt-1">
                              <span className="text-[10px] text-dark-600">found on:</span>
                              <a
                                href={url.source_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-[10px] font-mono text-dark-500 hover:text-primary-400 transition-colors truncate max-w-[400px]"
                                onClick={(e) => e.stopPropagation()}
                              >
                                {url.source_url}
                              </a>
                            </div>
                          )}
                        </div>

                        {/* Actions */}
                        <div className="flex items-center gap-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                          {/* Quick list buttons for external URLs */}
                          {!url.is_internal && url.external_domain && !listActionDone[url.external_domain] && domainStatus === "unknown" && (
                            <>
                              <button
                                onClick={(e) => { e.stopPropagation(); handleAddToList(url.external_domain, "whitelist"); }}
                                disabled={listActionLoading === `${url.external_domain}-whitelist`}
                                className="p-1.5 rounded-md hover:bg-green-500/20 transition-colors" title="Add to Whitelist"
                              >
                                {listActionLoading === `${url.external_domain}-whitelist` ? (
                                  <Loader2 className="w-3.5 h-3.5 text-green-400 animate-spin" />
                                ) : (
                                  <ShieldCheck className="w-3.5 h-3.5 text-green-500/60 hover:text-green-400" />
                                )}
                              </button>
                              <button
                                onClick={(e) => { e.stopPropagation(); handleAddToList(url.external_domain, "blacklist"); }}
                                disabled={listActionLoading === `${url.external_domain}-blacklist`}
                                className="p-1.5 rounded-md hover:bg-red-500/20 transition-colors" title="Add to Blacklist"
                              >
                                {listActionLoading === `${url.external_domain}-blacklist` ? (
                                  <Loader2 className="w-3.5 h-3.5 text-red-400 animate-spin" />
                                ) : (
                                  <ShieldX className="w-3.5 h-3.5 text-red-500/60 hover:text-red-400" />
                                )}
                              </button>
                            </>
                          )}
                          {!url.is_internal && url.external_domain && listActionDone[url.external_domain] && (
                            <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                              listActionDone[url.external_domain] === "whitelist"
                                ? "bg-green-500/20 text-green-400"
                                : "bg-red-500/20 text-red-400"
                            }`}>
                              ✓ {listActionDone[url.external_domain] === "whitelist" ? "WL" : "BL"}
                            </span>
                          )}
                          <button
                            onClick={(e) => { e.stopPropagation(); copyUrl(url.url); }}
                            className="p-1.5 rounded-md hover:bg-dark-700 transition-colors"
                            title="Copy URL"
                          >
                            {copiedUrl === url.url ? (
                              <Check className="w-3.5 h-3.5 text-emerald-400" />
                            ) : (
                              <Copy className="w-3.5 h-3.5 text-dark-500" />
                            )}
                          </button>
                          <a
                            href={url.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-1.5 rounded-md hover:bg-dark-700 transition-colors"
                            title="Open in new tab"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <ExternalLink className="w-3.5 h-3.5 text-dark-500" />
                          </a>
                        </div>
                      </div>

                      {/* ═══════ Expanded Link Details Panel ═══════ */}
                      <AnimatePresence>
                        {selectedUrl?.id === url.id && (
                          <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: "auto" }}
                            exit={{ opacity: 0, height: 0 }}
                            className="overflow-hidden"
                          >
                            <div className="mt-3 pt-3 border-t border-dark-700/30 space-y-3">
                              {/* Detail Grid */}
                              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                                <DetailItem label="Source" value={url.source_display || url.source} />
                                <DetailItem label="Status" value={url.status_code ? `${url.status_code} ${url.status_category || ""}` : "—"} />
                                <DetailItem label="Depth" value={String(url.depth)} />
                                <DetailItem label="Content Type" value={url.content_type || "—"} />
                                <DetailItem label="Visibility" value={url.is_private ? "🔒 Private" : "🌐 Public"} />
                                <DetailItem label="Internal" value={url.is_internal ? "Yes" : "No"} />
                                {url.external_domain && (
                                  <DetailItem
                                    label="Domain Status"
                                    value={
                                      domainStatus === "whitelist" ? "🟢 Whitelisted" :
                                      domainStatus === "blacklist" ? "🔴 Blacklisted" :
                                      "🟡 Unknown"
                                    }
                                  />
                                )}
                                <DetailItem label="First Seen" value={new Date(url.first_seen).toLocaleString()} />
                                <DetailItem label="Last Seen" value={new Date(url.last_seen).toLocaleString()} />
                              </div>

                              {/* Source Chain */}
                              {url.source_url && (
                                <div className="bg-dark-900/50 rounded-lg p-3 border border-dark-700/30">
                                  <p className="text-[10px] text-dark-500 uppercase tracking-wider font-medium mb-2">
                                    Discovery Chain
                                  </p>
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <a
                                      href={url.source_url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-[11px] font-mono text-dark-400 hover:text-primary-400 transition-colors bg-dark-800/80 px-2 py-1 rounded border border-dark-700/50 truncate max-w-[300px]"
                                      onClick={(e) => e.stopPropagation()}
                                    >
                                      {url.source_url}
                                    </a>
                                    <ChevronRight className="w-3 h-3 text-dark-600" />
                                    <span className={`text-[9px] px-1.5 py-0.5 rounded border ${
                                      sourceColors[url.source] || "bg-dark-700 text-dark-400 border-dark-600"
                                    }`}>
                                      {url.source}
                                    </span>
                                    <ChevronRight className="w-3 h-3 text-dark-600" />
                                    <span className="text-[11px] font-mono text-primary-400 bg-dark-800/80 px-2 py-1 rounded border border-primary-500/20 truncate max-w-[300px]">
                                      {url.url}
                                    </span>
                                  </div>
                                </div>
                              )}

                              {/* Quick actions for external domains */}
                              {!url.is_internal && url.external_domain && domainStatus === "unknown" && !listActionDone[url.external_domain] && (
                                <div className="flex items-center gap-2">
                                  <span className="text-[10px] text-dark-500">Quick action for {url.external_domain}:</span>
                                  <button
                                    onClick={(e) => { e.stopPropagation(); handleAddToList(url.external_domain, "whitelist"); }}
                                    disabled={listActionLoading === `${url.external_domain}-whitelist`}
                                    className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-green-500/10 text-green-400
                                               text-[10px] font-medium hover:bg-green-500/20 border border-green-500/20
                                               transition-colors disabled:opacity-50"
                                  >
                                    {listActionLoading === `${url.external_domain}-whitelist` ? (
                                      <Loader2 className="w-3 h-3 animate-spin" />
                                    ) : (
                                      <ShieldCheck className="w-3 h-3" />
                                    )}
                                    Add to Whitelist
                                  </button>
                                  <button
                                    onClick={(e) => { e.stopPropagation(); handleAddToList(url.external_domain, "blacklist"); }}
                                    disabled={listActionLoading === `${url.external_domain}-blacklist`}
                                    className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-red-500/10 text-red-400
                                               text-[10px] font-medium hover:bg-red-500/20 border border-red-500/20
                                               transition-colors disabled:opacity-50"
                                  >
                                    {listActionLoading === `${url.external_domain}-blacklist` ? (
                                      <Loader2 className="w-3 h-3 animate-spin" />
                                    ) : (
                                      <ShieldX className="w-3 h-3" />
                                    )}
                                    Add to Blacklist
                                  </button>
                                </div>
                              )}
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </motion.div>
                  );
                })
              )}
            </AnimatePresence>
          </div>

          {/* Load More */}
          {nextPage && !loading && (
            <motion.button
              onClick={loadMore}
              disabled={loadingMore}
              className="w-full py-3 mt-3 rounded-xl bg-dark-800/50 border border-dark-700/50 text-dark-400 
                         hover:text-dark-200 hover:border-dark-600 transition-all text-sm font-medium
                         flex items-center justify-center gap-2"
              whileHover={{ scale: 1.005 }}
              whileTap={{ scale: 0.995 }}
            >
              {loadingMore ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <ChevronDown className="w-4 h-4" />
                  Load More ({totalCount - urls.length} remaining)
                </>
              )}
            </motion.button>
          )}
        </motion.div>
      )}
    </div>
  );
}

/* ═══════ Sub-components ═══════ */

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-dark-900/30 rounded-lg px-3 py-2 border border-dark-700/20">
      <p className="text-[9px] text-dark-600 uppercase tracking-wider font-medium mb-0.5">{label}</p>
      <p className="text-[11px] text-dark-300 font-medium truncate">{value}</p>
    </div>
  );
}

function MatchedDomainCard({
  ed,
  type,
  sourceColors,
}: {
  ed: ExternalDomainGroup;
  type: "whitelist" | "blacklist";
  sourceColors: Record<string, string>;
}) {
  const isWhitelist = type === "whitelist";
  const borderColor = isWhitelist ? "border-green-500/15" : "border-red-500/20";
  const iconColor = isWhitelist ? "text-green-400" : "text-red-400";
  const textColor = isWhitelist ? "text-green-300" : "text-red-300";
  const countColor = isWhitelist ? "text-green-400/70" : "text-red-400/70";
  const lineColor = isWhitelist ? "border-green-500/20" : "border-red-500/25";
  const Icon = isWhitelist ? ShieldCheck : ShieldX;

  return (
    <div className={`bg-dark-800/60 rounded-lg border ${borderColor} p-3`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Icon className={`w-3.5 h-3.5 ${iconColor}`} />
          <span className={`text-sm font-medium ${textColor}`}>{ed.external_domain}</span>
        </div>
        <span className={`text-xs font-mono ${countColor}`}>
          {ed.count} link{ed.count !== 1 ? "s" : ""}
        </span>
      </div>
      {ed.urls && ed.urls.length > 0 && (
        <div className="space-y-1.5 mt-2">
          <p className="text-[10px] text-dark-500 uppercase tracking-wider font-medium">
            Found on pages:
          </p>
          {ed.urls.map((u, idx) => (
            <div key={idx} className={`flex flex-col gap-0.5 pl-3 border-l-2 ${lineColor} py-1`}>
              <a
                href={u.url}
                target="_blank"
                rel="noopener noreferrer"
                className={`text-xs font-mono text-dark-300 hover:${iconColor} transition-colors truncate`}
              >
                ↗ {u.url}
              </a>
              {u.source_url && (
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-dark-600">found on:</span>
                  <a
                    href={u.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[11px] font-mono text-dark-400 hover:text-primary-400 transition-colors truncate"
                  >
                    {u.source_url}
                  </a>
                </div>
              )}
              <div className="flex items-center gap-1.5 mt-0.5">
                {u.source && (
                  <span className={`text-[9px] px-1 py-0.5 rounded border ${sourceColors[u.source] || "bg-dark-700 text-dark-400 border-dark-600"}`}>
                    {u.source}
                  </span>
                )}
                {u.status_code != null && u.status_code > 0 && (
                  <span className={`text-[9px] font-mono px-1 py-0.5 rounded ${
                    u.status_code >= 200 && u.status_code < 300
                      ? "text-emerald-400 bg-emerald-500/10"
                      : "text-red-400 bg-red-500/10"
                  }`}>
                    {u.status_code}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SummaryStat({
  label,
  value,
  color,
  active,
  onClick,
}: {
  label: string;
  value: number;
  color: string;
  active?: boolean;
  onClick?: () => void;
}) {
  const colorMap: Record<string, string> = {
    white: "text-white",
    emerald: "text-emerald-400",
    blue: "text-blue-400",
    orange: "text-orange-400",
    amber: "text-amber-400",
    red: "text-red-400",
    violet: "text-violet-400",
    green: "text-green-400",
  };

  const activeRing: Record<string, string> = {
    blue: "ring-blue-500/50",
    violet: "ring-violet-500/50",
    green: "ring-green-500/50",
    red: "ring-red-500/50",
    amber: "ring-amber-500/50",
  };

  return (
    <div
      className={`bg-dark-800/40 rounded-xl border border-dark-700/40 p-3 text-center transition-all ${
        onClick ? "cursor-pointer hover:bg-dark-800/60 hover:border-dark-600/60" : ""
      } ${active ? `ring-2 ${activeRing[color] || "ring-primary-500/50"} border-transparent` : ""}`}
      onClick={onClick}
    >
      <p className={`text-lg md:text-xl font-bold ${colorMap[color] || "text-white"}`}>
        {value.toLocaleString()}
      </p>
      <p className="text-[10px] text-dark-500 mt-0.5 uppercase tracking-wider">{label}</p>
    </div>
  );
}
