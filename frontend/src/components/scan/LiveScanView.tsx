"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Globe,
  Bot,
  FileText,
  Code,
  Hammer,
  CheckCircle2,
  XCircle,
  Loader2,
  SkipForward,
  Zap,
  ExternalLink,
  Radio,
  ShieldCheck,
  ShieldAlert,
  Shield,
  Lock,
  Unlock,
  KeyRound,
  Bug,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api";

/* ── types ───────────────────────────────────────────────────────────── */

interface ScanEvent {
  type: string;
  [key: string]: unknown;
}

interface PhaseInfo {
  name: string;
  module: string;
  status: "waiting" | "running" | "done" | "error" | "skipped";
  urlsFound: number;
  error?: string;
  // Reputation phase extras
  reputationChecked?: number;
  reputationTotal?: number;
  highRisk?: number;
  mediumRisk?: number;
  lowRisk?: number;
  reputationFailed?: number;
}

interface ReputationResult {
  domain: string;
  risk_level: string;
  check_status: string;
  virustotal_malicious?: number;
  virustotal_suspicious?: number;
  error?: string;
}

interface LiveURL {
  id: string;
  url: string;
  source: string;
  status_code: number | null;
  depth: number;
  is_internal: boolean;
  external_domain: string | null;
  timestamp: number;
}

interface LiveScanViewProps {
  scanId: number;
  domain: string;
  onComplete?: () => void;
}

/* ── phase icons & colours ───────────────────────────────────────────── */

const phaseConfig: Record<string, { icon: React.ReactNode; label: string }> = {
  robots: { icon: <Bot className="w-4 h-4" />, label: "robots.txt" },
  sitemap: { icon: <Globe className="w-4 h-4" />, label: "sitemap.xml" },
  bruteforce: { icon: <Hammer className="w-4 h-4" />, label: "Bruteforce" },
  crawl: { icon: <Code className="w-4 h-4" />, label: "HTML + JS Crawl" },
  auth: { icon: <KeyRound className="w-4 h-4" />, label: "Авторизация" },
  private_scan: { icon: <Lock className="w-4 h-4" />, label: "Приватные страницы" },
  reputation: { icon: <Shield className="w-4 h-4" />, label: "Domain Reputation" },
};

const sourceColors: Record<string, string> = {
  html: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  js: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  robots: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  sitemap: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  bruteforce: "bg-red-500/10 text-red-400 border-red-500/20",
  spa: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  api: "bg-orange-500/10 text-orange-400 border-orange-500/20",
};

const sourceIcons: Record<string, React.ReactNode> = {
  html: <FileText className="w-3 h-3" />,
  js: <Code className="w-3 h-3" />,
  robots: <Bot className="w-3 h-3" />,
  spa: <Globe className="w-3 h-3" />,
  api: <Zap className="w-3 h-3" />,
  sitemap: <Globe className="w-3 h-3" />,
  bruteforce: <Hammer className="w-3 h-3" />,
};

/* ── component ────────────────────────────────────────────────────────── */

export function LiveScanView({ scanId, domain, onComplete }: LiveScanViewProps) {
  const [phases, setPhases] = useState<PhaseInfo[]>([
    { name: "robots", module: "RobotsModule", status: "waiting", urlsFound: 0 },
    { name: "sitemap", module: "SitemapModule", status: "waiting", urlsFound: 0 },
    { name: "bruteforce", module: "BruteforceModule", status: "waiting", urlsFound: 0 },
    { name: "crawl", module: "HTML + JS Crawler", status: "waiting", urlsFound: 0 },
    { name: "auth", module: "Авторизация", status: "waiting", urlsFound: 0 },
    { name: "private_scan", module: "Приватные страницы", status: "waiting", urlsFound: 0 },
    { name: "reputation", module: "Domain Reputation", status: "waiting", urlsFound: 0, reputationChecked: 0, reputationTotal: 0, highRisk: 0, mediumRisk: 0, lowRisk: 0, reputationFailed: 0 },
  ]);
  const [liveUrls, setLiveUrls] = useState<LiveURL[]>([]);
  const [reputationResults, setReputationResults] = useState<ReputationResult[]>([]);
  const [totalUrls, setTotalUrls] = useState(0);
  const [internalCount, setInternalCount] = useState(0);
  const [externalCount, setExternalCount] = useState(0);
  const [privateCount, setPrivateCount] = useState(0);
  const [crawlProgress, setCrawlProgress] = useState({ visited: 0, queue: 0 });
  const [scanDone, setScanDone] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [authMethod, setAuthMethod] = useState<string | null>(null);
  const [authStepProgress, setAuthStepProgress] = useState<{
    step: number;
    total: number;
    action: string;
    description: string;
  } | null>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const [connected, setConnected] = useState(false);
  const [spaProgress, setSpaProgress] = useState<{
    currentUrl: string;
    pagesVisited: number;
    queueSize: number;
    urlsFound: number;
    apiFound: number;
    message: string;
    done: boolean;
  } | null>(null);
  const [spaLog, setSpaLog] = useState<{ time: string; text: string; type: string }[]>([]);
  const urlCounter = useRef(0);
  const feedRef = useRef<HTMLDivElement>(null);
  const spaLogRef = useRef<HTMLDivElement>(null);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  const updatePhase = useCallback(
    (phaseName: string, update: Partial<PhaseInfo>) => {
      setPhases((prev) =>
        prev.map((p) => (p.name === phaseName ? { ...p, ...update } : p))
      );
    },
    []
  );

  useEffect(() => {
    const controller = new AbortController();
    let reader: ReadableStreamDefaultReader<Uint8Array> | null = null;

    async function connect() {
      try {
        const res = await fetch(`${API_BASE}/scans/${scanId}/stream/`, {
          signal: controller.signal,
        });

        if (!res.ok || !res.body) {
          setScanError(`Stream connection failed (${res.status})`);
          return;
        }

        setConnected(true);
        reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            try {
              const event: ScanEvent = JSON.parse(line.slice(6));
              handleEvent(event);
            } catch {
              // skip malformed lines
            }
          }
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name === "AbortError") return;
        setScanError("Connection lost");
      } finally {
        setConnected(false);
      }
    }

    function handleEvent(event: ScanEvent) {
      switch (event.type) {
        case "scan_start":
          break;

        case "phase_start":
          updatePhase(event.phase as string, { status: "running" });
          break;

        case "phase_complete":
          updatePhase(event.phase as string, {
            status: "done",
            urlsFound: (event.urls_found as number) || 0,
            // Reputation phase extras
            ...(event.phase === "reputation" ? {
              highRisk: (event.high_risk as number) || 0,
              mediumRisk: (event.medium_risk as number) || 0,
              lowRisk: (event.low_risk as number) || 0,
              reputationFailed: (event.failed as number) || 0,
            } : {}),
          });
          break;

        case "phase_error":
          updatePhase(event.phase as string, {
            status: "error",
            error: event.error as string,
          });
          break;

        case "phase_skip":
          updatePhase(event.phase as string, {
            status: "skipped",
            error: event.reason as string,
          });
          break;

        case "url_found": {
          urlCounter.current += 1;
          const isPrivate = (event.is_private as boolean) ?? false;
          const newUrl: LiveURL = {
            id: `live-${urlCounter.current}`,
            url: event.url as string,
            source: event.source as string,
            status_code: (event.status_code as number) ?? null,
            depth: (event.depth as number) ?? 0,
            is_internal: (event.is_internal as boolean) ?? true,
            external_domain: (event.external_domain as string) ?? null,
            timestamp: Date.now(),
          };
          setLiveUrls((prev) => [newUrl, ...prev].slice(0, 200));
          setTotalUrls((n) => n + 1);
          if (isPrivate) {
            setPrivateCount((n) => n + 1);
          }
          if (newUrl.is_internal) {
            setInternalCount((n) => n + 1);
          } else {
            setExternalCount((n) => n + 1);
          }
          break;
        }

        case "auth_success":
          setAuthMethod(event.method as string);
          setAuthStepProgress(null);
          break;

        case "auth_error":
          setAuthError(event.error as string);
          setAuthMethod(event.method as string);
          setAuthStepProgress(null);
          break;

        case "auth_step_progress":
          setAuthStepProgress({
            step: (event.step as number) || 0,
            total: (event.total as number) || 0,
            action: (event.action as string) || "",
            description: (event.description as string) || "",
          });
          break;

        case "auth_recrawl_progress":
          updatePhase("private_scan", {
            status: "running",
            urlsFound: (event.current as number) || 0,
          });
          break;

        case "spa_progress": {
          const now = new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
          setSpaProgress({
            currentUrl: (event.currentUrl as string) || (event.current_url as string) || "",
            pagesVisited: (event.pagesVisited as number) || (event.pages_visited as number) || 0,
            queueSize: (event.queueSize as number) || (event.queue_size as number) || 0,
            urlsFound: (event.urlsFound as number) || (event.urls_found as number) || 0,
            apiFound: (event.apiFound as number) || (event.api_found as number) || 0,
            message: (event.message as string) || "",
            done: (event.done as boolean) || false,
          });
          if (event.message) {
            setSpaLog((prev) => [{ time: now, text: event.message as string, type: "progress" }, ...prev].slice(0, 100));
          }
          break;
        }

        case "spa_page_visited": {
          const now2 = new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
          const pagePath = (event.url as string)?.replace(/^https?:\/\/[^/]+/, "") || "/";
          const pageDepth = (event.depth as number) ?? 0;
          setSpaLog((prev) => [{ time: now2, text: `✅ ${pagePath}  [depth=${pageDepth}]`, type: "page" }, ...prev].slice(0, 100));
          break;
        }

        case "spa_api_found": {
          const now3 = new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
          const apiPath = (event.url as string)?.replace(/^https?:\/\/[^/]+/, "") || "/";
          const apiMethod = (event.method as string) || "XHR";
          setSpaLog((prev) => [{ time: now3, text: `🔗 API: ${apiMethod} ${apiPath}`, type: "api" }, ...prev].slice(0, 100));
          break;
        }

        case "spa_navigated": {
          const now4 = new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
          const navPath = (event.url as string)?.replace(/^https?:\/\/[^/]+/, "") || "/";
          setSpaLog((prev) => [{ time: now4, text: "\ud83d\uddb1\ufe0f \u041a\u043b\u0438\u043a \u2192 " + navPath, type: "click" }, ...prev].slice(0, 100));
          break;
        }

        case "crawl_progress":
          setCrawlProgress({
            visited: event.visited as number,
            queue: event.queue_size as number,
          });
          break;

        case "scan_complete":
          // Scanner crawl phases done — reputation phase may still follow
          // Just update stats, don't set scanDone yet
          setDuration(event.duration as number);
          setTotalUrls(event.total_urls as number);
          break;

        case "scan_fully_complete":
          // Everything done including reputation checks
          setScanDone(true);
          if (onCompleteRef.current) setTimeout(onCompleteRef.current, 2000);
          break;

        case "scan_already_done":
          setScanDone(true);
          setTotalUrls((event.total_urls as number) || 0);
          if (onCompleteRef.current) onCompleteRef.current();
          break;

        case "scan_error":
          setScanError(event.error as string);
          break;

        case "results":
          // final payload — scan_complete already handled the UI
          break;

        case "reputation_progress":
          // Update reputation phase with progress info
          updatePhase("reputation", {
            status: "running",
            reputationChecked: (event.checked as number) || 0,
            reputationTotal: (event.total as number) || 0,
          });
          break;

        case "reputation_domain_checked": {
          const repResult: ReputationResult = {
            domain: event.domain as string,
            risk_level: event.risk_level as string,
            check_status: event.check_status as string,
            virustotal_malicious: event.virustotal_malicious as number | undefined,
            virustotal_suspicious: event.virustotal_suspicious as number | undefined,
            error: event.error as string | undefined,
          };
          setReputationResults((prev) => [repResult, ...prev]);
          updatePhase("reputation", {
            reputationChecked: (event.checked as number) || 0,
            reputationTotal: (event.total as number) || 0,
          });
          break;
        }
      }
    }

    connect();
    return () => {
      controller.abort();
      if (reader) reader.cancel();
    };
  }, [scanId, updatePhase]);

  /* auto-scroll feed */
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = 0;
    }
  }, [liveUrls.length]);

  /* ── phase status icon ──────────────────────────── */
  function phaseStatusIcon(status: PhaseInfo["status"]) {
    switch (status) {
      case "waiting":
        return <div className="w-5 h-5 rounded-full border-2 border-dark-600" />;
      case "running":
        return <Loader2 className="w-5 h-5 text-primary-400 animate-spin" />;
      case "done":
        return <CheckCircle2 className="w-5 h-5 text-green-400" />;
      case "error":
        return <XCircle className="w-5 h-5 text-red-400" />;
      case "skipped":
        return <SkipForward className="w-5 h-5 text-dark-500" />;
    }
  }

  return (
    <div className="space-y-6">
      {/* Live indicator */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Radio
            className={`w-4 h-4 ${
              connected ? "text-red-500 animate-pulse" : "text-dark-500"
            }`}
          />
          <span className="text-sm font-medium text-dark-300">
            {scanDone ? "Scan Complete" : scanError ? "Error" : "Live Scan"}
          </span>
        </div>
        <div className="flex items-center gap-4 text-xs text-dark-500">
          <span className="flex items-center gap-1">
            <Zap className="w-3.5 h-3.5 text-primary-400" />
            {totalUrls} URLs
          </span>
          {internalCount > 0 && (
            <span className="text-blue-400">{internalCount} int</span>
          )}
          {externalCount > 0 && (
            <span className="text-orange-400">{externalCount} ext</span>
          )}
          {privateCount > 0 && (
            <span className="text-purple-400">🔒 {privateCount} private</span>
          )}
          {crawlProgress.visited > 0 && (
            <span>{crawlProgress.visited} pages</span>
          )}
          {duration !== null && <span>{duration}s</span>}
        </div>
      </div>

      {/* Phase timeline */}
      <div className="bg-dark-800/50 rounded-2xl border border-dark-700/50 p-5">
        <h3 className="text-sm font-semibold text-dark-300 mb-4 uppercase tracking-wider">
          Scan Phases
        </h3>
        <div className="space-y-1">
          {phases
            .filter((phase) => {
              // Hide auth/private_scan phases if they were never started
              if ((phase.name === "auth" || phase.name === "private_scan") && phase.status === "waiting") {
                return false;
              }
              return true;
            })
            .map((phase, i, filteredPhases) => {
            const cfg = phaseConfig[phase.name];
            return (
              <div key={phase.name} className="flex items-start gap-3">
                {/* Vertical line + status icon */}
                <div className="flex flex-col items-center">
                  {phaseStatusIcon(phase.status)}
                  {i < filteredPhases.length - 1 && (
                    <div
                      className={`w-0.5 h-8 mt-1 ${
                        phase.status === "done"
                          ? "bg-green-500/30"
                          : phase.status === "error"
                          ? "bg-red-500/30"
                          : "bg-dark-700"
                      }`}
                    />
                  )}
                </div>

                {/* Phase info */}
                <div className="flex-1 pb-4">
                  <div className="flex items-center gap-2">
                    <span className="text-dark-400">{cfg?.icon}</span>
                    <span
                      className={`text-sm font-medium ${
                        phase.status === "running"
                          ? "text-primary-400"
                          : phase.status === "done"
                          ? "text-white"
                          : phase.status === "error"
                          ? "text-red-400"
                          : "text-dark-500"
                      }`}
                    >
                      {cfg?.label || phase.name}
                    </span>
                    {/* Auth phase — done */}
                    {phase.status === "done" && phase.name === "auth" && (
                      <span className="text-xs text-green-400/70 ml-auto flex items-center gap-1">
                        <Unlock className="w-3 h-3" />
                        Вход выполнен{authMethod ? ` (${authMethod})` : ""}
                      </span>
                    )}
                    {/* Auth phase — running */}
                    {phase.status === "running" && phase.name === "auth" && (
                      <span className="text-xs text-primary-400/70 ml-auto animate-pulse flex items-center gap-1">
                        <KeyRound className="w-3 h-3" />
                        {authStepProgress
                          ? `Шаг ${authStepProgress.step}/${authStepProgress.total}`
                          : "Авторизация…"}
                      </span>
                    )}
                    {/* Private scan — done */}
                    {phase.status === "done" && phase.name === "private_scan" && (
                      <span className="text-xs text-purple-400/70 ml-auto flex items-center gap-1">
                        <Lock className="w-3 h-3" />
                        +{phase.urlsFound} приватных URL
                      </span>
                    )}
                    {/* Private scan — running */}
                    {phase.status === "running" && phase.name === "private_scan" && (
                      <span className="text-xs text-primary-400/70 ml-auto animate-pulse flex items-center gap-1">
                        <Lock className="w-3 h-3" />
                        Сканирование…
                      </span>
                    )}
                    {/* Other phases — done (not auth, not private_scan, not reputation) */}
                    {phase.status === "done" && !["reputation", "auth", "private_scan"].includes(phase.name) && (
                      <span className="text-xs text-green-400/70 ml-auto">
                        +{phase.urlsFound} URLs
                      </span>
                    )}
                    {phase.status === "done" && phase.name === "reputation" && (
                      <span className="text-xs text-green-400/70 ml-auto">
                        {phase.urlsFound} domains checked
                      </span>
                    )}
                    {/* Other phases — running (not auth, not private_scan, not reputation) */}
                    {phase.status === "running" && !["reputation", "auth", "private_scan"].includes(phase.name) && (
                      <span className="text-xs text-primary-400/70 ml-auto animate-pulse">
                        In progress…
                      </span>
                    )}
                    {phase.status === "running" && phase.name === "reputation" && (
                      <span className="text-xs text-primary-400/70 ml-auto animate-pulse">
                        {phase.reputationChecked}/{phase.reputationTotal} domains…
                      </span>
                    )}
                  </div>

                  {/* Reputation phase — progress bar when running */}
                  {phase.name === "reputation" && phase.status === "running" && (phase.reputationTotal ?? 0) > 0 && (
                    <div className="mt-2 ml-6">
                      <div className="w-full bg-dark-700 rounded-full h-1.5 overflow-hidden">
                        <motion.div
                          className="h-full bg-gradient-to-r from-primary-500 to-primary-400 rounded-full"
                          initial={{ width: 0 }}
                          animate={{ width: `${((phase.reputationChecked || 0) / (phase.reputationTotal || 1)) * 100}%` }}
                          transition={{ duration: 0.3 }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Auth phase — step progress bar and description when running */}
                  {phase.name === "auth" && phase.status === "running" && authStepProgress && (
                    <div className="mt-2 ml-6">
                      <div className="w-full bg-dark-700 rounded-full h-1.5 overflow-hidden mb-1.5">
                        <motion.div
                          className="h-full bg-gradient-to-r from-primary-500 to-primary-400 rounded-full"
                          initial={{ width: 0 }}
                          animate={{ width: `${(authStepProgress.step / Math.max(authStepProgress.total, 1)) * 100}%` }}
                          transition={{ duration: 0.3 }}
                        />
                      </div>
                      <p className="text-[11px] text-dark-400 truncate">
                        {authStepProgress.description}
                      </p>
                    </div>
                  )}

                  {/* Reputation phase — risk summary when done */}
                  {phase.name === "reputation" && phase.status === "done" && (
                    <div className="mt-2 ml-6 flex items-center gap-3 text-[11px]">
                      {(phase.highRisk ?? 0) > 0 && (
                        <span className="flex items-center gap-1 text-red-400">
                          <ShieldAlert className="w-3 h-3" />
                          {phase.highRisk} high
                        </span>
                      )}
                      {(phase.mediumRisk ?? 0) > 0 && (
                        <span className="flex items-center gap-1 text-yellow-400">
                          <Shield className="w-3 h-3" />
                          {phase.mediumRisk} medium
                        </span>
                      )}
                      {(phase.lowRisk ?? 0) > 0 && (
                        <span className="flex items-center gap-1 text-green-400">
                          <ShieldCheck className="w-3 h-3" />
                          {phase.lowRisk} safe
                        </span>
                      )}
                      {(phase.highRisk ?? 0) === 0 && (phase.mediumRisk ?? 0) === 0 && (
                        <span className="flex items-center gap-1 text-green-400">
                          <ShieldCheck className="w-3 h-3" />
                          All domains safe
                        </span>
                      )}
                    </div>
                  )}

                  {/* Auth phase — error details */}
                  {phase.name === "auth" && phase.status === "error" && (
                    <div className="mt-2 ml-6 flex items-center gap-2 text-[11px]">
                      <span className="flex items-center gap-1 text-red-400">
                        <XCircle className="w-3 h-3" />
                        Ошибка авторизации{authMethod ? ` (${authMethod})` : ""}
                      </span>
                    </div>
                  )}

                  {/* Auth phase — success details */}
                  {phase.name === "auth" && phase.status === "done" && (
                    <div className="mt-2 ml-6 flex items-center gap-2 text-[11px]">
                      <span className="flex items-center gap-1 text-green-400">
                        <Unlock className="w-3 h-3" />
                        Авторизация успешна
                      </span>
                    </div>
                  )}

                  {phase.status === "error" && phase.error && (
                    <p className="text-xs text-red-400/70 mt-1 ml-6">
                      ⚠ {phase.error}
                    </p>
                  )}
                  {phase.status === "skipped" && (
                    <p className="text-xs text-dark-500 mt-1 ml-6">Skipped</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Error banner */}
      {scanError && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 flex items-center gap-3"
        >
          <XCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
          <p className="text-sm text-red-300">{scanError}</p>
        </motion.div>
      )}

      {/* Auth error banner */}
      {authError && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-orange-500/10 border border-orange-500/20 rounded-xl p-4 flex items-start gap-3"
        >
          <KeyRound className="w-5 h-5 text-orange-400 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium text-orange-300 mb-1">
              Ошибка авторизации{authMethod ? ` (${authMethod})` : ""}
            </p>
            <p className="text-xs text-orange-400/70">{authError}</p>
            <p className="text-xs text-dark-400 mt-2">
              Приватные страницы не будут просканированы. Проверьте настройки авторизации в настройках сайта.
            </p>
          </div>
        </motion.div>
      )}

      {/* SPA Crawler Progress */}
      {spaProgress && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-dark-800/50 rounded-2xl border border-purple-500/20 overflow-hidden"
        >
          <div className="flex items-center justify-between px-5 py-3 border-b border-dark-700/50">
            <h3 className="text-sm font-semibold text-purple-300 uppercase tracking-wider flex items-center gap-2">
              <Globe className="w-4 h-4 text-purple-400" />
              SPA Browser Crawler
            </h3>
            <div className="flex items-center gap-3 text-xs">
              <span className="text-purple-400">{spaProgress.pagesVisited} \u0441\u0442\u0440\u0430\u043d\u0438\u0446</span>
              <span className="text-blue-400">{spaProgress.urlsFound} URL</span>
              <span className="text-yellow-400">{spaProgress.apiFound} API</span>
              {spaProgress.queueSize > 0 && <span className="text-dark-500">+{spaProgress.queueSize} \u0432 \u043e\u0447\u0435\u0440\u0435\u0434\u0438</span>}
            </div>
          </div>

          {/* Current URL */}
          {spaProgress.currentUrl && !spaProgress.done && (
            <div className="px-5 py-2 border-b border-dark-700/30 flex items-center gap-2">
              <Loader2 className="w-3.5 h-3.5 text-purple-400 animate-spin flex-shrink-0" />
              <span className="text-xs font-mono text-dark-300 truncate">{spaProgress.currentUrl}</span>
            </div>
          )}
          {spaProgress.done && (
            <div className="px-5 py-2 border-b border-dark-700/30 flex items-center gap-2">
              <CheckCircle2 className="w-3.5 h-3.5 text-green-400 flex-shrink-0" />
              <span className="text-xs text-green-300">{spaProgress.message}</span>
            </div>
          )}

          {/* SPA Live Log */}
          <div ref={spaLogRef} className="max-h-[200px] overflow-y-auto divide-y divide-dark-700/20">
            <AnimatePresence initial={false}>
              {spaLog.map((entry, i) => (
                <motion.div
                  key={`spa-${i}-${entry.time}`}
                  initial={{ opacity: 0, x: -10, height: 0 }}
                  animate={{ opacity: 1, x: 0, height: "auto" }}
                  className="px-5 py-1.5 flex items-center gap-2 text-[11px]"
                >
                  <span className="text-dark-600 font-mono flex-shrink-0">{entry.time}</span>
                  <span className={`truncate ${
                    entry.type === "api" ? "text-yellow-400" :
                    entry.type === "click" ? "text-purple-300" :
                    entry.type === "page" ? "text-green-400" :
                    "text-dark-400"
                  }`}>{entry.text}</span>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </motion.div>
      )}

      {/* Live URL feed */}
      <div className="bg-dark-800/50 rounded-2xl border border-dark-700/50">
        <div className="flex items-center justify-between px-5 py-3 border-b border-dark-700/50">
          <h3 className="text-sm font-semibold text-dark-300 uppercase tracking-wider">
            Discovered URLs
          </h3>
          <span className="text-xs text-dark-500">{totalUrls} total</span>
        </div>

        <div
          ref={feedRef}
          className="max-h-[420px] overflow-y-auto divide-y divide-dark-700/30"
        >
          <AnimatePresence initial={false}>
            {liveUrls.length === 0 ? (
              <div className="text-center py-12 text-dark-500 text-sm">
                <Loader2 className="w-6 h-6 mx-auto mb-2 animate-spin opacity-30" />
                Waiting for URLs…
              </div>
            ) : (
              liveUrls.map((u) => (
                <motion.div
                  key={u.id}
                  initial={{ opacity: 0, x: -20, height: 0 }}
                  animate={{ opacity: 1, x: 0, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.2 }}
                  className="px-4 py-2.5 flex items-center gap-2 group hover:bg-dark-700/20"
                >
                  {/* Source badge */}
                  <span
                    className={`flex-shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium border flex items-center gap-1 ${
                      sourceColors[u.source] || "bg-dark-700 text-dark-400"
                    }`}
                  >
                    {sourceIcons[u.source]}
                    {u.source}
                  </span>

                  {/* Internal/External badge */}
                  {!u.is_internal && (
                    <span className="flex-shrink-0 px-1 py-0.5 rounded text-[9px] font-bold bg-orange-500/15 text-orange-400 border border-orange-500/20">
                      EXT
                    </span>
                  )}

                  {/* Status code */}
                  {u.status_code != null && u.status_code > 0 && (
                    <span
                      className={`text-[10px] font-mono flex-shrink-0 ${
                        u.status_code >= 200 && u.status_code < 300
                          ? "text-green-400"
                          : u.status_code >= 300 && u.status_code < 400
                          ? "text-yellow-400"
                          : "text-red-400"
                      }`}
                    >
                      {u.status_code}
                    </span>
                  )}

                  {/* URL */}
                  <a
                    href={u.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-mono text-dark-300 truncate hover:text-primary-400 transition-colors flex-1 min-w-0"
                  >
                    {u.url}
                  </a>

                  {/* External domain hint */}
                  {u.external_domain && (
                    <span className="text-[9px] text-orange-400/60 flex-shrink-0 truncate max-w-[80px]">
                      → {u.external_domain}
                    </span>
                  )}

                  {/* Depth */}
                  <span className="text-[10px] text-dark-600 flex-shrink-0">
                    d{u.depth}
                  </span>

                  <ExternalLink className="w-3 h-3 text-dark-600 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                </motion.div>
              ))
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Reputation results feed */}
      {reputationResults.length > 0 && (
        <div className="bg-dark-800/50 rounded-2xl border border-dark-700/50">
          <div className="flex items-center justify-between px-5 py-3 border-b border-dark-700/50">
            <h3 className="text-sm font-semibold text-dark-300 uppercase tracking-wider flex items-center gap-2">
              <Shield className="w-4 h-4 text-primary-400" />
              Reputation Results
            </h3>
            <span className="text-xs text-dark-500">{reputationResults.length} checked</span>
          </div>

          <div className="max-h-[280px] overflow-y-auto divide-y divide-dark-700/30">
            <AnimatePresence initial={false}>
              {reputationResults.map((r, i) => (
                <motion.div
                  key={`rep-${r.domain}-${i}`}
                  initial={{ opacity: 0, x: -20, height: 0 }}
                  animate={{ opacity: 1, x: 0, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.2 }}
                  className="px-4 py-2.5 flex items-center gap-2 group hover:bg-dark-700/20"
                >
                  {/* Risk badge */}
                  <span
                    className={`flex-shrink-0 px-1.5 py-0.5 rounded text-[10px] font-bold border flex items-center gap-1 ${
                      r.risk_level === "high"
                        ? "bg-red-500/15 text-red-400 border-red-500/20"
                        : r.risk_level === "medium"
                        ? "bg-yellow-500/15 text-yellow-400 border-yellow-500/20"
                        : r.risk_level === "low"
                        ? "bg-green-500/15 text-green-400 border-green-500/20"
                        : "bg-dark-600/50 text-dark-400 border-dark-500/20"
                    }`}
                  >
                    {r.risk_level === "high" ? (
                      <ShieldAlert className="w-3 h-3" />
                    ) : r.risk_level === "low" ? (
                      <ShieldCheck className="w-3 h-3" />
                    ) : (
                      <Shield className="w-3 h-3" />
                    )}
                    {r.risk_level}
                  </span>

                  {/* Domain */}
                  <span className="text-xs font-mono text-dark-300 truncate flex-1 min-w-0">
                    {r.domain}
                  </span>

                  {/* VT stats */}
                  {(r.virustotal_malicious ?? 0) > 0 && (
                    <span className="text-[10px] text-red-400/70 flex-shrink-0">
                      {r.virustotal_malicious} malicious
                    </span>
                  )}
                  {(r.virustotal_suspicious ?? 0) > 0 && (
                    <span className="text-[10px] text-yellow-400/70 flex-shrink-0">
                      {r.virustotal_suspicious} suspicious
                    </span>
                  )}

                  {/* Error */}
                  {r.error && (
                    <span className="text-[10px] text-red-400/60 flex-shrink-0 truncate max-w-[100px]">
                      ⚠ {r.error}
                    </span>
                  )}

                  {/* Status */}
                  {r.check_status === "failed" && (
                    <XCircle className="w-3 h-3 text-red-400/50 flex-shrink-0" />
                  )}
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </div>
      )}

      {/* Done summary */}
      {scanDone && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="bg-green-500/5 border border-green-500/20 rounded-xl p-5 text-center"
        >
          <CheckCircle2 className="w-8 h-8 text-green-400 mx-auto mb-2" />
          <p className="font-semibold text-green-300">Scan Complete!</p>
          <p className="text-sm text-dark-400 mt-1">
            {totalUrls} URLs discovered in {duration ?? "—"}s
          </p>
          <div className="flex items-center justify-center gap-4 mt-2 text-xs">
            <span className="text-blue-400">{internalCount} internal</span>
            <span className="text-dark-700">·</span>
            <span className="text-orange-400">{externalCount} external</span>
          </div>
          {reputationResults.length > 0 && (
            <div className="flex items-center justify-center gap-3 mt-2 text-xs">
              <span className="text-dark-500">Reputation:</span>
              <span className="text-green-400 flex items-center gap-1">
                <ShieldCheck className="w-3 h-3" />
                {reputationResults.filter(r => r.risk_level === "low").length} safe
              </span>
              {reputationResults.filter(r => r.risk_level === "high").length > 0 && (
                <span className="text-red-400 flex items-center gap-1">
                  <ShieldAlert className="w-3 h-3" />
                  {reputationResults.filter(r => r.risk_level === "high").length} dangerous
                </span>
              )}
            </div>
          )}
          <p className="text-xs text-dark-500 mt-2">
            The page will update shortly.
          </p>
        </motion.div>
      )}
    </div>
  );
}
