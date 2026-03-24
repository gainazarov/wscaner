"use client";

import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  Globe,
  Link2,
  ArrowRight,
  Filter,
  SlidersHorizontal,
  ExternalLink,
  ChevronDown,
  Shield,
  CheckCircle2,
  Loader2,
  XCircle,
  BarChart3,
  Clock,
  Copy,
  Check,
  AlertTriangle,
} from "lucide-react";
import Link from "next/link";
import { api, DomainStats, Scan } from "@/lib/api";

export function URLExplorer() {
  const [domains, setDomains] = useState<DomainStats[]>([]);
  const [scans, setScans] = useState<Scan[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [view, setView] = useState<"domains" | "scans">("domains");
  const [expandedDomain, setExpandedDomain] = useState<string | null>(null);
  const [copiedDomain, setCopiedDomain] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    try {
      const [domainsData, scansData] = await Promise.all([
        api.getDomains(),
        api.getScans(),
      ]);
      setDomains(domainsData);
      setScans(scansData.results || []);
    } catch (err) {
      console.error("Failed to load explorer data:", err);
    } finally {
      setLoading(false);
    }
  }

  function copyDomain(domain: string) {
    navigator.clipboard.writeText(domain);
    setCopiedDomain(domain);
    setTimeout(() => setCopiedDomain(null), 2000);
  }

  const filteredScans = scans.filter((scan) => {
    const matchesSearch =
      !search || scan.domain.toLowerCase().includes(search.toLowerCase());
    const matchesStatus =
      statusFilter === "all" || scan.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const filteredDomains = domains.filter(
    (d) =>
      !search || d.domain.toLowerCase().includes(search.toLowerCase())
  );

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

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="skeleton h-12 rounded-xl" />
        <div className="skeleton h-10 rounded-xl" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="skeleton h-28 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl md:text-2xl font-bold flex items-center gap-2">
            <SlidersHorizontal className="w-5 h-5 md:w-6 md:h-6 text-primary-400" />
            URL Explorer
          </h1>
          <p className="text-dark-500 mt-1 text-xs md:text-sm">
            Browse all discovered URLs across {domains.length} domains
          </p>
        </div>
        {/* Summary pills */}
        <div className="hidden md:flex items-center gap-2">
          <span className="px-2.5 py-1 rounded-lg bg-dark-800 border border-dark-700 text-[10px] text-dark-400">
            {domains.length} domains
          </span>
          <span className="px-2.5 py-1 rounded-lg bg-dark-800 border border-dark-700 text-[10px] text-dark-400">
            {scans.length} scans
          </span>
        </div>
      </div>

      {/* Search & View Toggle */}
      <div className="flex flex-col sm:flex-row gap-2">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={
              view === "domains" ? "Search domains..." : "Search scans..."
            }
            className="w-full pl-10 pr-4 py-2.5 bg-dark-800/70 border border-dark-700 rounded-xl text-sm
                       placeholder-dark-500 focus:outline-none focus:border-primary-500 transition-colors"
          />
        </div>
        <div className="flex gap-1.5">
          <button
            onClick={() => setView("domains")}
            className={`px-3 py-2 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all ${
              view === "domains"
                ? "bg-primary-500/20 text-primary-400 border border-primary-500/30"
                : "bg-dark-800 text-dark-500 border border-dark-700 hover:text-dark-400"
            }`}
          >
            <Globe className="w-3.5 h-3.5" />
            Domains
          </button>
          <button
            onClick={() => setView("scans")}
            className={`px-3 py-2 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all ${
              view === "scans"
                ? "bg-primary-500/20 text-primary-400 border border-primary-500/30"
                : "bg-dark-800 text-dark-500 border border-dark-700 hover:text-dark-400"
            }`}
          >
            <BarChart3 className="w-3.5 h-3.5" />
            Scans
          </button>
        </div>
      </div>

      {/* Status filter (scans view) */}
      {view === "scans" && (
        <div className="flex gap-1.5 overflow-x-auto pb-0.5">
          {["all", "completed", "running", "pending", "failed"].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-2.5 py-1.5 rounded-lg text-[10px] font-medium capitalize transition-all whitespace-nowrap ${
                statusFilter === s
                  ? "bg-primary-500/20 text-primary-400 border border-primary-500/30"
                  : "bg-dark-800 text-dark-500 border border-dark-700 hover:text-dark-400"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Domains View */}
      {view === "domains" && (
        <div className="space-y-2">
          {filteredDomains.length === 0 ? (
            <div className="text-center py-16 text-dark-500">
              <Globe className="w-10 h-10 mx-auto mb-3 opacity-20" />
              <p className="font-medium">No domains found</p>
              <p className="text-xs mt-1">Start a scan to discover URLs</p>
            </div>
          ) : (
            filteredDomains.map((d, i) => (
              <motion.div
                key={d.domain}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
                className="bg-dark-800/40 rounded-xl border border-dark-700/40 overflow-hidden
                           hover:border-dark-600/60 transition-all"
              >
                <div
                  className="p-3 md:p-4 cursor-pointer"
                  onClick={() =>
                    setExpandedDomain(
                      expandedDomain === d.domain ? null : d.domain
                    )
                  }
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-9 h-9 rounded-lg bg-primary-500/10 border border-primary-500/20 flex items-center justify-center flex-shrink-0">
                        <Globe className="w-4 h-4 text-primary-400" />
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="font-semibold text-sm truncate">{d.domain}</h3>
                          {statusIcon(d.last_scan_status)}
                        </div>
                        <div className="flex items-center gap-3 mt-0.5 text-[10px] text-dark-500">
                          <span>{d.total_scans} scans</span>
                          <span>{d.total_unique_urls} URLs</span>
                          {d.external_domains_count > 0 && (
                            <span className="text-orange-400/70">
                              {d.external_domains_count} ext domains
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          copyDomain(d.domain);
                        }}
                        className="p-1.5 rounded-md hover:bg-dark-700 transition-colors"
                      >
                        {copiedDomain === d.domain ? (
                          <Check className="w-3.5 h-3.5 text-emerald-400" />
                        ) : (
                          <Copy className="w-3.5 h-3.5 text-dark-600" />
                        )}
                      </button>
                      <ChevronDown
                        className={`w-4 h-4 text-dark-500 transition-transform ${
                          expandedDomain === d.domain ? "rotate-180" : ""
                        }`}
                      />
                    </div>
                  </div>
                </div>

                {/* Expanded: scan list for this domain */}
                <AnimatePresence>
                  {expandedDomain === d.domain && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      className="border-t border-dark-700/40 overflow-hidden"
                    >
                      <div className="p-2 space-y-1">
                        {scans
                          .filter((s) => s.domain === d.domain)
                          .slice(0, 10)
                          .map((scan) => (
                            <Link
                              key={scan.id}
                              href={`/scan/${scan.id}`}
                              className="flex items-center justify-between px-3 py-2 rounded-lg
                                         hover:bg-dark-700/40 transition-colors group"
                            >
                              <div className="flex items-center gap-2 min-w-0">
                                {statusIcon(scan.status)}
                                <span className="text-xs text-dark-300 truncate">
                                  Scan #{scan.id}
                                </span>
                                <span className="text-[10px] text-dark-500">
                                  {new Date(scan.created_at).toLocaleDateString()}
                                </span>
                              </div>
                              <div className="flex items-center gap-2">
                                <span className="text-[10px] text-dark-500">
                                  {scan.total_urls} URLs
                                  {scan.external_urls > 0 && (
                                    <span className="text-orange-400/70 ml-1">
                                      ({scan.external_urls} ext)
                                    </span>
                                  )}
                                </span>
                                <ArrowRight className="w-3 h-3 text-dark-600 group-hover:text-primary-400 transition-colors" />
                              </div>
                            </Link>
                          ))}
                        {d.last_scan_id && (
                          <Link
                            href={`/scan/${d.last_scan_id}`}
                            className="block text-center py-2 text-xs text-primary-400 hover:text-primary-300 transition-colors"
                          >
                            View latest scan →
                          </Link>
                        )}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            ))
          )}
        </div>
      )}

      {/* Scans View */}
      {view === "scans" && (
        <div className="space-y-1.5">
          {filteredScans.length === 0 ? (
            <div className="text-center py-16 text-dark-500">
              <Search className="w-10 h-10 mx-auto mb-3 opacity-20" />
              <p className="font-medium">No scans match your criteria</p>
            </div>
          ) : (
            filteredScans.map((scan, i) => (
              <motion.div
                key={scan.id}
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.025 }}
              >
                <Link href={`/scan/${scan.id}`}>
                  <div
                    className="bg-dark-800/40 rounded-xl border border-dark-700/40 p-3 md:p-4
                                hover:border-dark-600/60 transition-all cursor-pointer group"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3 min-w-0">
                        <div
                          className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                            scan.status === "completed"
                              ? "bg-emerald-500/10 border border-emerald-500/20"
                              : scan.status === "running"
                              ? "bg-blue-500/10 border border-blue-500/20"
                              : scan.status === "failed"
                              ? "bg-red-500/10 border border-red-500/20"
                              : "bg-dark-700 border border-dark-600"
                          }`}
                        >
                          {statusIcon(scan.status)}
                        </div>
                        <div className="min-w-0">
                          <p className="font-medium text-sm group-hover:text-primary-300 transition-colors truncate">
                            {scan.domain}
                          </p>
                          <div className="flex items-center gap-2 text-[10px] text-dark-500 mt-0.5">
                            <span>#{scan.id}</span>
                            <span>
                              {new Date(scan.created_at).toLocaleDateString()}
                            </span>
                            <span>{scan.total_urls} URLs</span>
                            {scan.new_urls > 0 && (
                              <span className="text-emerald-400/70">
                                +{scan.new_urls} new
                              </span>
                            )}
                            {scan.external_urls > 0 && (
                              <span className="text-orange-400/70">
                                {scan.external_urls} ext
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                      <ArrowRight className="w-4 h-4 text-dark-600 group-hover:text-primary-400 transition-all flex-shrink-0" />
                    </div>
                  </div>
                </Link>
              </motion.div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
