"use client";

import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Shield,
  ShieldCheck,
  ShieldX,
  ShieldAlert,
  Plus,
  Trash2,
  X,
  Check,
  AlertTriangle,
  Globe,
  Loader2,
  ChevronDown,
  ChevronRight,
  HelpCircle,
  Lightbulb,
  RefreshCw,
  Search,
  Copy,
} from "lucide-react";
import {
  api,
  DomainListsResponse,
  DomainListEntry,
  DomainListSuggestion,
  DomainStats,
  ExternalDomainEntryWithReputation,
  MonitoringData,
} from "@/lib/api";

interface DomainListsProps {
  selectedSite: string;
  domains: DomainStats[];
  monitoringData: MonitoringData | null;
  onRefresh: () => void;
}

export function DomainLists({ selectedSite, domains, monitoringData, onRefresh }: DomainListsProps) {
  const [listsData, setListsData] = useState<DomainListsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState<"whitelist" | "blacklist" | null>(null);
  const [addInput, setAddInput] = useState("");
  const [addNote, setAddNote] = useState("");
  const [adding, setAdding] = useState(false);
  const [suggestions, setSuggestions] = useState<DomainListSuggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [sugLoading, setSugLoading] = useState(false);
  const [expandedList, setExpandedList] = useState<"whitelist" | "blacklist" | null>("whitelist");
  const [quickActionLoading, setQuickActionLoading] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [copiedDomain, setCopiedDomain] = useState<string | null>(null);

  const siteDomain = selectedSite || (domains.length > 0 ? domains[0].domain : "");

  const loadLists = useCallback(async () => {
    if (!siteDomain) return;
    setLoading(true);
    try {
      const data = await api.getDomainLists(siteDomain);
      setListsData(data);
    } catch (err) {
      console.error("Failed to load domain lists:", err);
    } finally {
      setLoading(false);
    }
  }, [siteDomain]);

  const loadSuggestions = useCallback(async () => {
    if (!siteDomain) return;
    setSugLoading(true);
    try {
      const data = await api.getDomainListSuggestions(siteDomain);
      setSuggestions(data.suggestions);
    } catch (err) {
      console.error("Failed to load suggestions:", err);
    } finally {
      setSugLoading(false);
    }
  }, [siteDomain]);

  useEffect(() => {
    loadLists();
  }, [loadLists]);

  async function handleAdd(listType: "whitelist" | "blacklist") {
    if (!addInput.trim() || !siteDomain) return;
    setAdding(true);
    try {
      const domainsList = addInput
        .split(/[\n,;]+/)
        .map((d) => d.trim())
        .filter(Boolean);

      await api.addToDomainList({
        site_domain: siteDomain,
        domains: domainsList,
        list_type: listType,
        note: addNote,
      });
      setAddInput("");
      setAddNote("");
      setShowAddForm(null);
      await loadLists();
      onRefresh();
    } catch (err) {
      console.error("Failed to add domains:", err);
    } finally {
      setAdding(false);
    }
  }

  async function handleRemove(entryId: number) {
    try {
      await api.removeFromDomainList(entryId);
      await loadLists();
      onRefresh();
    } catch (err) {
      console.error("Failed to remove:", err);
    }
  }

  async function handleQuickAction(domain: string, listType: "whitelist" | "blacklist") {
    if (!siteDomain) return;
    setQuickActionLoading(`${domain}-${listType}`);
    try {
      await api.domainListQuickAction({
        site_domain: siteDomain,
        domain,
        list_type: listType,
      });
      await loadLists();
      onRefresh();
    } catch (err) {
      console.error("Quick action failed:", err);
    } finally {
      setQuickActionLoading(null);
    }
  }

  async function handleClearList(listType: "whitelist" | "blacklist") {
    if (!siteDomain) return;
    if (!confirm(`Clear entire ${listType}? This cannot be undone.`)) return;
    try {
      await api.clearDomainList(siteDomain, listType);
      await loadLists();
      onRefresh();
    } catch (err) {
      console.error("Failed to clear list:", err);
    }
  }

  async function handleAddSuggestion(domain: string) {
    await handleQuickAction(domain, "whitelist");
    setSuggestions((prev) => prev.filter((s) => s.domain !== domain));
  }

  function copyDomain(domain: string) {
    navigator.clipboard.writeText(domain);
    setCopiedDomain(domain);
    setTimeout(() => setCopiedDomain(null), 2000);
  }

  if (!siteDomain) {
    return (
      <div className="text-center py-16">
        <Shield className="w-16 h-16 mx-auto mb-4 text-dark-700" />
        <p className="text-lg font-medium text-dark-400">Select a site to manage lists</p>
        <p className="text-sm text-dark-600 mt-1">Scan a domain first to start managing whitelist/blacklist</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="space-y-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="skeleton h-24 rounded-xl" />
        ))}
      </div>
    );
  }

  // Get unknown domains for quick-actions
  const unknownDomains = monitoringData?.domains.filter(
    (d) => d.list_classification === "unknown"
  ) || [];

  const filteredUnknown = search
    ? unknownDomains.filter((d) => d.domain.includes(search.toLowerCase()))
    : unknownDomains;

  return (
    <div className="space-y-6">
      {/* Classification Summary */}
      {listsData?.classification && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <SummaryCard
            icon={<Globe className="w-4 h-4" />}
            label="Total Domains"
            value={listsData.classification.total}
            color="blue"
          />
          <SummaryCard
            icon={<ShieldCheck className="w-4 h-4" />}
            label="Whitelisted"
            value={listsData.classification.whitelist}
            color="green"
          />
          <SummaryCard
            icon={<ShieldX className="w-4 h-4" />}
            label="Blacklisted"
            value={listsData.classification.blacklist}
            color="red"
          />
          <SummaryCard
            icon={<HelpCircle className="w-4 h-4" />}
            label="Unknown"
            value={listsData.classification.unknown}
            color="amber"
          />
        </div>
      )}

      {/* Whitelist Section */}
      <ListSection
        title="Whitelist"
        icon={<ShieldCheck className="w-5 h-5 text-emerald-400" />}
        color="emerald"
        entries={listsData?.whitelist || []}
        isExpanded={expandedList === "whitelist"}
        onToggle={() => setExpandedList(expandedList === "whitelist" ? null : "whitelist")}
        onAdd={() => setShowAddForm(showAddForm === "whitelist" ? null : "whitelist")}
        onRemove={handleRemove}
        onClear={() => handleClearList("whitelist")}
        onCopy={copyDomain}
        copiedDomain={copiedDomain}
      />

      {/* Add to Whitelist Form */}
      <AnimatePresence>
        {showAddForm === "whitelist" && (
          <AddForm
            listType="whitelist"
            input={addInput}
            note={addNote}
            adding={adding}
            onInputChange={setAddInput}
            onNoteChange={setAddNote}
            onSubmit={() => handleAdd("whitelist")}
            onCancel={() => { setShowAddForm(null); setAddInput(""); setAddNote(""); }}
          />
        )}
      </AnimatePresence>

      {/* Blacklist Section */}
      <ListSection
        title="Blacklist"
        icon={<ShieldX className="w-5 h-5 text-red-400" />}
        color="red"
        entries={listsData?.blacklist || []}
        isExpanded={expandedList === "blacklist"}
        onToggle={() => setExpandedList(expandedList === "blacklist" ? null : "blacklist")}
        onAdd={() => setShowAddForm(showAddForm === "blacklist" ? null : "blacklist")}
        onRemove={handleRemove}
        onClear={() => handleClearList("blacklist")}
        onCopy={copyDomain}
        copiedDomain={copiedDomain}
      />

      {/* Add to Blacklist Form */}
      <AnimatePresence>
        {showAddForm === "blacklist" && (
          <AddForm
            listType="blacklist"
            input={addInput}
            note={addNote}
            adding={adding}
            onInputChange={setAddInput}
            onNoteChange={setAddNote}
            onSubmit={() => handleAdd("blacklist")}
            onCancel={() => { setShowAddForm(null); setAddInput(""); setAddNote(""); }}
          />
        )}
      </AnimatePresence>

      {/* Auto-Suggestions */}
      <div className="bg-dark-800/40 border border-dark-700/40 rounded-xl overflow-hidden">
        <button
          onClick={() => {
            setShowSuggestions(!showSuggestions);
            if (!showSuggestions && suggestions.length === 0) loadSuggestions();
          }}
          className="w-full flex items-center justify-between p-4 hover:bg-dark-800/60 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Lightbulb className="w-5 h-5 text-amber-400" />
            <span className="font-semibold text-dark-200">Auto-Suggestions</span>
            <span className="text-xs text-dark-500">Frequently seen unknown domains</span>
          </div>
          {showSuggestions ? (
            <ChevronDown className="w-4 h-4 text-dark-500" />
          ) : (
            <ChevronRight className="w-4 h-4 text-dark-500" />
          )}
        </button>

        <AnimatePresence>
          {showSuggestions && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <div className="border-t border-dark-700/30 p-4">
                {sugLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-5 h-5 text-dark-500 animate-spin" />
                  </div>
                ) : suggestions.length === 0 ? (
                  <p className="text-center text-dark-500 text-sm py-4">
                    No suggestions — domains need to be seen at least 5 times
                  </p>
                ) : (
                  <div className="space-y-2">
                    {suggestions.map((s) => (
                      <div
                        key={s.domain}
                        className="flex items-center justify-between p-3 rounded-lg bg-dark-900/50 border border-dark-700/30"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-dark-200 truncate">{s.domain}</p>
                          <p className="text-xs text-dark-500">
                            Seen {s.times_seen} times · {s.status}
                          </p>
                        </div>
                        <button
                          onClick={() => handleAddSuggestion(s.domain)}
                          disabled={quickActionLoading === `${s.domain}-whitelist`}
                          className="px-3 py-1.5 bg-emerald-500/10 text-emerald-400 text-xs font-medium rounded-lg
                                     hover:bg-emerald-500/20 transition-colors border border-emerald-500/20
                                     disabled:opacity-50 flex items-center gap-1"
                        >
                          {quickActionLoading === `${s.domain}-whitelist` ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <Plus className="w-3 h-3" />
                          )}
                          Whitelist
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Unknown Domains — Quick Actions */}
      {unknownDomains.length > 0 && (
        <div className="bg-dark-800/40 border border-dark-700/40 rounded-xl overflow-hidden">
          <div className="p-4 border-b border-dark-700/30">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-amber-400" />
                <span className="font-semibold text-dark-200">
                  Unknown Domains ({unknownDomains.length})
                </span>
              </div>
              <button
                onClick={() => { loadLists(); onRefresh(); }}
                className="p-1.5 hover:bg-dark-700 rounded-lg transition-colors"
              >
                <RefreshCw className="w-4 h-4 text-dark-500" />
              </button>
            </div>
            {unknownDomains.length > 5 && (
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-500" />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Filter domains..."
                  className="w-full pl-10 pr-4 py-2 bg-dark-900 border border-dark-600 rounded-lg text-sm
                             placeholder-dark-500 focus:outline-none focus:border-primary-500 transition-colors"
                />
              </div>
            )}
          </div>

          <div className="max-h-96 overflow-y-auto divide-y divide-dark-700/20">
            {filteredUnknown.slice(0, 50).map((d) => (
              <div
                key={d.domain}
                className="flex items-center justify-between p-3 px-4 hover:bg-dark-800/60 transition-colors"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-dark-200 truncate">{d.domain}</p>
                    <button
                      onClick={() => copyDomain(d.domain)}
                      className="text-dark-600 hover:text-dark-400 transition-colors flex-shrink-0"
                    >
                      {copiedDomain === d.domain ? (
                        <Check className="w-3 h-3 text-emerald-400" />
                      ) : (
                        <Copy className="w-3 h-3" />
                      )}
                    </button>
                  </div>
                  <p className="text-xs text-dark-500">
                    seen {d.times_seen}x · {d.is_suspicious ? "⚠️ suspicious" : d.status}
                  </p>
                </div>
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  <button
                    onClick={() => handleQuickAction(d.domain, "whitelist")}
                    disabled={quickActionLoading === `${d.domain}-whitelist`}
                    className="px-2.5 py-1 bg-emerald-500/10 text-emerald-400 text-[10px] font-medium rounded-md
                               hover:bg-emerald-500/20 transition-colors border border-emerald-500/20
                               disabled:opacity-50 flex items-center gap-1"
                  >
                    {quickActionLoading === `${d.domain}-whitelist` ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <ShieldCheck className="w-3 h-3" />
                    )}
                    OK
                  </button>
                  <button
                    onClick={() => handleQuickAction(d.domain, "blacklist")}
                    disabled={quickActionLoading === `${d.domain}-blacklist`}
                    className="px-2.5 py-1 bg-red-500/10 text-red-400 text-[10px] font-medium rounded-md
                               hover:bg-red-500/20 transition-colors border border-red-500/20
                               disabled:opacity-50 flex items-center gap-1"
                  >
                    {quickActionLoading === `${d.domain}-blacklist` ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <ShieldX className="w-3 h-3" />
                    )}
                    Block
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


/* ────────── Sub-components ────────── */

function SummaryCard({
  icon, label, value, color,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  color: "blue" | "green" | "red" | "amber";
}) {
  const colors = {
    blue: "from-blue-500/20 to-blue-500/5 border-blue-500/20 text-blue-400",
    green: "from-emerald-500/20 to-emerald-500/5 border-emerald-500/20 text-emerald-400",
    red: "from-red-500/20 to-red-500/5 border-red-500/20 text-red-400",
    amber: "from-amber-500/20 to-amber-500/5 border-amber-500/20 text-amber-400",
  };

  return (
    <div className={`bg-gradient-to-br ${colors[color]} rounded-xl border p-4`}>
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className="text-[10px] font-medium text-dark-400 uppercase tracking-wider">{label}</span>
      </div>
      <p className="text-xl font-bold text-dark-100">{value}</p>
    </div>
  );
}


function ListSection({
  title, icon, color, entries, isExpanded, onToggle, onAdd, onRemove, onClear, onCopy, copiedDomain,
}: {
  title: string;
  icon: React.ReactNode;
  color: "emerald" | "red";
  entries: DomainListEntry[];
  isExpanded: boolean;
  onToggle: () => void;
  onAdd: () => void;
  onRemove: (id: number) => void;
  onClear: () => void;
  onCopy: (d: string) => void;
  copiedDomain: string | null;
}) {
  const borderColor = color === "emerald" ? "border-emerald-500/20" : "border-red-500/20";
  const bgColor = color === "emerald" ? "bg-emerald-500/5" : "bg-red-500/5";

  return (
    <div className={`${bgColor} border ${borderColor} rounded-xl overflow-hidden`}>
      <div className="flex items-center justify-between p-4">
        <button onClick={onToggle} className="flex items-center gap-2 flex-1">
          {icon}
          <span className="font-semibold text-dark-200">{title}</span>
          <span className="text-xs text-dark-500 bg-dark-800/50 px-2 py-0.5 rounded-full">
            {entries.length}
          </span>
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-dark-500" />
          ) : (
            <ChevronRight className="w-4 h-4 text-dark-500" />
          )}
        </button>
        <div className="flex items-center gap-2">
          <button
            onClick={onAdd}
            className="p-1.5 hover:bg-dark-700/50 rounded-lg transition-colors"
            title={`Add to ${title}`}
          >
            <Plus className="w-4 h-4 text-dark-400" />
          </button>
          {entries.length > 0 && (
            <button
              onClick={onClear}
              className="p-1.5 hover:bg-dark-700/50 rounded-lg transition-colors"
              title={`Clear ${title}`}
            >
              <Trash2 className="w-4 h-4 text-dark-600 hover:text-red-400 transition-colors" />
            </button>
          )}
        </div>
      </div>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            {entries.length === 0 ? (
              <div className="text-center py-6 text-dark-500 text-sm border-t border-dark-700/20">
                No domains in {title.toLowerCase()}
              </div>
            ) : (
              <div className="border-t border-dark-700/20 divide-y divide-dark-700/10 max-h-60 overflow-y-auto">
                {entries.map((entry) => (
                  <div
                    key={entry.id}
                    className="flex items-center justify-between px-4 py-2.5 hover:bg-dark-800/30 transition-colors"
                  >
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <span className="text-sm font-medium text-dark-200 truncate">{entry.domain}</span>
                      <button
                        onClick={() => onCopy(entry.domain)}
                        className="text-dark-600 hover:text-dark-400 transition-colors flex-shrink-0"
                      >
                        {copiedDomain === entry.domain ? (
                          <Check className="w-3 h-3 text-emerald-400" />
                        ) : (
                          <Copy className="w-3 h-3" />
                        )}
                      </button>
                      {entry.note && (
                        <span className="text-xs text-dark-600 truncate hidden md:inline">{entry.note}</span>
                      )}
                    </div>
                    <button
                      onClick={() => onRemove(entry.id)}
                      className="p-1 hover:bg-red-500/10 rounded transition-colors flex-shrink-0"
                    >
                      <X className="w-3.5 h-3.5 text-dark-600 hover:text-red-400 transition-colors" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}


function AddForm({
  listType, input, note, adding, onInputChange, onNoteChange, onSubmit, onCancel,
}: {
  listType: "whitelist" | "blacklist";
  input: string;
  note: string;
  adding: boolean;
  onInputChange: (v: string) => void;
  onNoteChange: (v: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
}) {
  const color = listType === "whitelist" ? "emerald" : "red";
  const borderColor = color === "emerald" ? "border-emerald-500/30" : "border-red-500/30";

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className={`bg-dark-800/50 border ${borderColor} rounded-xl p-4`}
    >
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-dark-200 flex items-center gap-2">
          {listType === "whitelist" ? (
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          ) : (
            <ShieldX className="w-4 h-4 text-red-400" />
          )}
          Add to {listType === "whitelist" ? "Whitelist" : "Blacklist"}
        </h4>
        <button onClick={onCancel} className="text-dark-500 hover:text-dark-300">
          <X className="w-4 h-4" />
        </button>
      </div>
      <textarea
        value={input}
        onChange={(e) => onInputChange(e.target.value)}
        placeholder="Enter domains (one per line, or comma-separated)&#10;e.g. google.com, cdn.jsdelivr.net"
        rows={3}
        className="w-full px-3 py-2 bg-dark-900 border border-dark-600 rounded-lg text-sm
                   placeholder-dark-500 focus:outline-none focus:border-primary-500 transition-colors
                   resize-none"
        autoFocus
      />
      <input
        type="text"
        value={note}
        onChange={(e) => onNoteChange(e.target.value)}
        placeholder="Note (optional)"
        className="w-full px-3 py-2 mt-2 bg-dark-900 border border-dark-600 rounded-lg text-sm
                   placeholder-dark-500 focus:outline-none focus:border-primary-500 transition-colors"
      />
      <div className="flex items-center gap-2 mt-3">
        <button
          onClick={onSubmit}
          disabled={adding || !input.trim()}
          className={`px-4 py-2 ${
            listType === "whitelist"
              ? "bg-emerald-600 hover:bg-emerald-500"
              : "bg-red-600 hover:bg-red-500"
          } rounded-lg text-sm font-medium transition-colors disabled:opacity-50
            flex items-center gap-2`}
        >
          {adding ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Plus className="w-4 h-4" />
          )}
          Add
        </button>
        <button
          onClick={onCancel}
          className="px-4 py-2 bg-dark-700 hover:bg-dark-600 rounded-lg text-sm text-dark-400 transition-colors"
        >
          Cancel
        </button>
      </div>
    </motion.div>
  );
}
