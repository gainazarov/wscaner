"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Settings,
  ShieldCheck,
  ShieldX,
  Plus,
  Trash2,
  Edit3,
  Save,
  X,
  Search,
  Globe,
  RefreshCw,
  AlertTriangle,
  Check,
  ChevronDown,
  Loader2,
  Download,
  Upload,
  Copy,
  Lock,
  Key,
  Eye,
  EyeOff,
  Cookie,
  LogIn,
  TestTube,
  CheckCircle,
  XCircle,
  Clock,
  Circle,
  Square,
  Monitor,
  Play,
  FileText,
  Terminal,
  Filter,
} from "lucide-react";
import {
  api,
  DomainStats,
  DomainListEntry,
  DomainListsResponse,
  SiteAuthConfig,
  AuthTestResult,
  DetectFieldsResult,
  DetectedField,
  AuthDebugResult,
  AuthDebugStep,
  AuthStabilityScore,
  RecordedStep,
  RecordingSession,
  RecordingStatus,
  RecordingStopResult,
} from "@/lib/api";

export function ProjectSettings() {
  const [domains, setDomains] = useState<DomainStats[]>([]);
  const [selectedSite, setSelectedSite] = useState("");
  const [listsData, setListsData] = useState<DomainListsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeList, setActiveList] = useState<"whitelist" | "blacklist">("whitelist");
  const [search, setSearch] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);
  const [addInput, setAddInput] = useState("");
  const [addNote, setAddNote] = useState("");
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editNote, setEditNote] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [bulkInput, setBulkInput] = useState("");
  const [showBulkAdd, setShowBulkAdd] = useState(false);
  const [bulkAdding, setBulkAdding] = useState(false);
  const [clearConfirm, setClearConfirm] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [copiedList, setCopiedList] = useState(false);

  // ─── Scanner Logs State ─────────────────────────────────────────
  const [logsOpen, setLogsOpen] = useState(false);
  const [logEntries, setLogEntries] = useState<Array<{ timestamp?: string; level?: string; module?: string; message?: string; raw?: string }>>([]);
  const [logFiles, setLogFiles] = useState<Array<{ name: string; size: number; size_human: string }>>([]);
  const [logFile, setLogFile] = useState("scanner");
  const [logLevel, setLogLevel] = useState("");
  const [logLines, setLogLines] = useState(300);
  const [logLoading, setLogLoading] = useState(false);
  const [logAutoRefresh, setLogAutoRefresh] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  // ─── Auth Config State ──────────────────────────────────────────
  const [authConfig, setAuthConfig] = useState<SiteAuthConfig | null>(null);
  const [authLoading, setAuthLoading] = useState(false);
  const [authSaving, setAuthSaving] = useState(false);
  const [authTesting, setAuthTesting] = useState(false);
  const [authTestResult, setAuthTestResult] = useState<AuthTestResult | null>(null);
  const [showPassword, setShowPassword] = useState(false);

  // New: Auth strategy, detect fields, debug, stability
  const [authStrategy, setAuthStrategy] = useState<"auto" | "http_only" | "playwright_only">("auto");
  const [detectingFields, setDetectingFields] = useState(false);
  const [detectedFields, setDetectedFields] = useState<DetectFieldsResult | null>(null);
  const [debugLoading, setDebugLoading] = useState(false);
  const [debugResult, setDebugResult] = useState<AuthDebugResult | null>(null);
  const [showDebugModal, setShowDebugModal] = useState(false);
  const [stabilityScore, setStabilityScore] = useState<AuthStabilityScore | null>(null);

  // Auth form fields
  const [authType, setAuthType] = useState<"none" | "form" | "cookie" | "interactive" | "recorded">("none");
  const [authEnabled, setAuthEnabled] = useState(true);
  const [loginUrl, setLoginUrl] = useState("");
  const [authUsername, setAuthUsername] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [usernameSelector, setUsernameSelector] = useState("");
  const [passwordSelector, setPasswordSelector] = useState("");
  const [submitSelector, setSubmitSelector] = useState("");
  const [cookieValue, setCookieValue] = useState("");

  // Interactive login fields
  const [homeUrl, setHomeUrl] = useState("");
  const [loginButtonSelector, setLoginButtonSelector] = useState("");

  // Recorded flow fields
  const [recordedSteps, setRecordedSteps] = useState<Array<{
    action: string;
    selector?: string;
    value?: string;
    wait_ms?: number;
    description?: string;
  }>>([]);
  const [showAddStep, setShowAddStep] = useState(false);
  const [editingStepIndex, setEditingStepIndex] = useState<number | null>(null);
  const [stepAction, setStepAction] = useState("click");
  const [stepSelector, setStepSelector] = useState("");
  const [stepValue, setStepValue] = useState("");
  const [stepWaitMs, setStepWaitMs] = useState(1000);
  const [stepDescription, setStepDescription] = useState("");

  // Recorder state
  const [isRecording, setIsRecording] = useState(false);
  const [recorderSessionId, setRecorderSessionId] = useState("");
  const [recorderStatus, setRecorderStatus] = useState<RecordingStatus | null>(null);
  const [recorderLoading, setRecorderLoading] = useState(false);
  const [recorderError, setRecorderError] = useState("");
  const [showRecorderBrowser, setShowRecorderBrowser] = useState(false);
  const [recorderEventsCount, setRecorderEventsCount] = useState(0);

  useEffect(() => {
    api.getDomains().then((d) => {
      setDomains(d);
      if (d.length > 0 && !selectedSite) setSelectedSite(d[0].domain);
    }).catch(console.error);
  }, []);

  const loadLists = useCallback(async () => {
    if (!selectedSite) return;
    setLoading(true);
    try {
      const data = await api.getDomainLists(selectedSite);
      setListsData(data);
    } catch (err) {
      console.error("Failed to load lists:", err);
    } finally {
      setLoading(false);
    }
  }, [selectedSite]);

  useEffect(() => {
    loadLists();
  }, [loadLists]);

  // ─── Load Auth Config ───────────────────────────────────────────
  const loadAuthConfig = useCallback(async () => {
    if (!selectedSite) return;
    setAuthLoading(true);
    setAuthTestResult(null);
    setDetectedFields(null);
    setDebugResult(null);
    try {
      const cfg = await api.getAuthConfig(selectedSite);
      setAuthConfig(cfg);
      setAuthType(cfg.auth_type || "none");
      setAuthStrategy(cfg.auth_strategy || "auto");
      setAuthEnabled(cfg.is_enabled ?? true);
      setLoginUrl(cfg.login_url || "");
      setAuthUsername(cfg.username || "");
      setAuthPassword("");
      setUsernameSelector(cfg.username_selector || "");
      setPasswordSelector(cfg.password_selector || "");
      setSubmitSelector(cfg.submit_selector || "");
      setCookieValue(cfg.cookie_value || "");
      setHomeUrl(cfg.home_url || "");
      setLoginButtonSelector(cfg.login_button_selector || "");
      setRecordedSteps(cfg.recorded_steps || []);
      // Load stability score
      api.getAuthStability(selectedSite).then(setStabilityScore).catch(() => setStabilityScore(null));
    } catch {
      // No config yet
      setAuthConfig(null);
      setAuthType("none");
      setAuthStrategy("auto");
      setAuthEnabled(true);
      setLoginUrl("");
      setAuthUsername("");
      setAuthPassword("");
      setUsernameSelector("");
      setPasswordSelector("");
      setSubmitSelector("");
      setCookieValue("");
      setHomeUrl("");
      setLoginButtonSelector("");
      setRecordedSteps([]);
      setStabilityScore(null);
    } finally {
      setAuthLoading(false);
    }
  }, [selectedSite]);

  useEffect(() => {
    loadAuthConfig();
  }, [loadAuthConfig]);

  const handleAuthSave = async () => {
    if (!selectedSite) return;
    setAuthSaving(true);
    try {
      const data: any = {
        domain: selectedSite,
        auth_type: authType,
        auth_strategy: authStrategy,
        is_enabled: authEnabled,
        login_url: loginUrl,
        username: authUsername,
        username_selector: usernameSelector,
        password_selector: passwordSelector,
        submit_selector: submitSelector,
        cookie_value: cookieValue,
        home_url: homeUrl,
        login_button_selector: loginButtonSelector,
        recorded_steps: recordedSteps,
      };
      if (authPassword) data.password = authPassword;
      await api.saveAuthConfig(data);
      await loadAuthConfig();
    } catch (err) {
      console.error("Failed to save auth config:", err);
    } finally {
      setAuthSaving(false);
    }
  };

  // ─── Recorder Handlers ────────────────────────────────────────
  const handleStartRecording = async () => {
    if (!selectedSite) return;
    setRecorderLoading(true);
    setRecorderError("");
    setRecorderEventsCount(0);
    try {
      let result = await api.startRecording({
        domain: selectedSite,
        start_url: homeUrl || loginUrl || undefined,
      });
      // Auto-reset stale session and retry
      if (!result.success && result.error?.includes("already active")) {
        await api.resetRecording();
        result = await api.startRecording({
          domain: selectedSite,
          start_url: homeUrl || loginUrl || undefined,
        });
      }
      if (result.success && result.session_id) {
        setRecorderSessionId(result.session_id);
        setIsRecording(true);
        setShowRecorderBrowser(true);
      } else {
        setRecorderError(result.error || "Failed to start recording");
      }
    } catch (err: any) {
      setRecorderError(err.message || "Failed to start recording");
    } finally {
      setRecorderLoading(false);
    }
  };

  const handleStopRecording = async () => {
    if (!recorderSessionId) return;
    setRecorderLoading(true);
    setRecorderError("");
    try {
      const result = await api.stopRecording(recorderSessionId);
      if (result.success && result.steps) {
        setRecordedSteps(result.steps);
        setIsRecording(false);
        setShowRecorderBrowser(false);
        setRecorderSessionId("");
        setRecorderEventsCount(0);
      } else {
        setRecorderError(result.error || "Failed to stop recording");
      }
    } catch (err: any) {
      setRecorderError(err.message || "Failed to stop recording");
    } finally {
      setRecorderLoading(false);
    }
  };

  // Poll recording status every 2 seconds
  useEffect(() => {
    if (!isRecording || !recorderSessionId) return;
    const interval = setInterval(async () => {
      try {
        const status = await api.getRecordingStatus(recorderSessionId);
        setRecorderStatus(status);
        if (status.events_count !== undefined) {
          setRecorderEventsCount(status.events_count);
        }
        // Auto-stop if recording timed out
        if (!status.active && status.status !== "recording") {
          setIsRecording(false);
          setShowRecorderBrowser(false);
        }
      } catch {
        // ignore poll errors
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [isRecording, recorderSessionId]);

  const handleAuthTest = async () => {
    if (!selectedSite) return;

    // Validation for specific auth types
    if (authType === "recorded" && (!recordedSteps || recordedSteps.length === 0)) {
      setAuthTestResult({ status: "failed", message: "Сначала запишите шаги авторизации" });
      return;
    }
    if (authType === "interactive" && !homeUrl && !loginUrl) {
      setAuthTestResult({ status: "failed", message: "Укажите URL главной страницы или страницы входа" });
      return;
    }

    setAuthTesting(true);
    setAuthTestResult(null);
    try {
      // Auto-save config before testing (backend reads from DB)
      await handleAuthSave();

      const data: any = {
        domain: selectedSite,
        auth_type: authType,
        auth_strategy: authStrategy,
        login_url: loginUrl,
        username: authUsername,
        password: authPassword || (authConfig?.has_password ? "__stored__" : ""),
        username_selector: usernameSelector,
        password_selector: passwordSelector,
        submit_selector: submitSelector,
        home_url: homeUrl,
        login_button_selector: loginButtonSelector,
        recorded_steps: recordedSteps,
      };
      if (authType === "cookie") {
        const cookies: Record<string, string> = {};
        for (const part of cookieValue.split(";")) {
          const trimmed = part.trim();
          if (trimmed.includes("=")) {
            const [k, ...vParts] = trimmed.split("=");
            cookies[k.trim()] = vParts.join("=").trim();
          }
        }
        data.cookies = cookies;
      }
      const result = await api.testAuthConfig(data);
      setAuthTestResult(result);
    } catch (err) {
      setAuthTestResult({ status: "failed", message: "Test request failed" });
    } finally {
      setAuthTesting(false);
    }
  };

  const handleAuthDelete = async () => {
    if (!selectedSite) return;
    try {
      await api.deleteAuthConfig(selectedSite);
      await loadAuthConfig();
    } catch (err) {
      console.error("Failed to delete auth config:", err);
    }
  };

  // ─── Scanner Logs Functions ─────────────────────────────────────
  const loadLogs = useCallback(async () => {
    setLogLoading(true);
    try {
      const [logsRes, filesRes] = await Promise.all([
        api.getScannerLogs(logFile, logLines, logLevel || undefined),
        api.getScannerLogFiles(),
      ]);
      setLogEntries(logsRes.entries || []);
      setLogFiles(filesRes.files || []);
    } catch (err) {
      console.error("Failed to load logs:", err);
    } finally {
      setLogLoading(false);
    }
  }, [logFile, logLines, logLevel]);

  const clearLog = async (file: string) => {
    try {
      await api.clearScannerLog(file);
      await loadLogs();
    } catch (err) {
      console.error("Failed to clear log:", err);
    }
  };

  // Auto-refresh logs
  useEffect(() => {
    if (!logsOpen || !logAutoRefresh) return;
    const interval = setInterval(loadLogs, 3000);
    return () => clearInterval(interval);
  }, [logsOpen, logAutoRefresh, loadLogs]);

  // Load logs when panel opens
  useEffect(() => {
    if (logsOpen) loadLogs();
  }, [logsOpen, logFile, logLevel, logLines, loadLogs]);

  const handleDetectFields = async () => {
    if (!loginUrl) return;
    setDetectingFields(true);
    setDetectedFields(null);
    try {
      const result = await api.detectAuthFields(loginUrl);
      setDetectedFields(result);
      // Auto-fill selectors if detected
      if (result.suggested_username_selector && !usernameSelector) {
        setUsernameSelector(result.suggested_username_selector);
      }
      if (result.suggested_password_selector && !passwordSelector) {
        setPasswordSelector(result.suggested_password_selector);
      }
      if (result.suggested_submit_selector && !submitSelector) {
        setSubmitSelector(result.suggested_submit_selector);
      }
    } catch (err) {
      console.error("Failed to detect fields:", err);
    } finally {
      setDetectingFields(false);
    }
  };

  const handleDebugLogin = async () => {
    if (!selectedSite) return;
    setDebugLoading(true);
    setDebugResult(null);
    setShowDebugModal(true);
    try {
      const result = await api.debugAuthLogin(selectedSite);
      setDebugResult(result);
    } catch (err) {
      setDebugResult({ steps: [{ step: "error", status: "failed", detail: "Debug request failed" }], success: false });
    } finally {
      setDebugLoading(false);
    }
  };

  const currentList = listsData
    ? activeList === "whitelist"
      ? listsData.whitelist
      : listsData.blacklist
    : [];

  const filteredList = currentList.filter((entry) =>
    !search || entry.domain.toLowerCase().includes(search.toLowerCase()) ||
    (entry.note && entry.note.toLowerCase().includes(search.toLowerCase()))
  );

  const handleAdd = async () => {
    if (!addInput.trim() || !selectedSite) return;
    setAdding(true);
    try {
      await api.addToDomainList({
        site_domain: selectedSite,
        domains: [addInput.trim().toLowerCase()],
        list_type: activeList,
        note: addNote.trim() || undefined,
      });
      setAddInput("");
      setAddNote("");
      setShowAddForm(false);
      loadLists();
    } catch (err) {
      console.error("Failed to add:", err);
    } finally {
      setAdding(false);
    }
  };

  const handleBulkAdd = async () => {
    const domains = bulkInput
      .split(/[\n,;]+/)
      .map((d) => d.trim().toLowerCase())
      .filter((d) => d.length > 0);
    if (domains.length === 0 || !selectedSite) return;
    setBulkAdding(true);
    try {
      await api.addToDomainList({
        site_domain: selectedSite,
        domains,
        list_type: activeList,
        note: "Bulk import",
      });
      setBulkInput("");
      setShowBulkAdd(false);
      loadLists();
    } catch (err) {
      console.error("Failed to bulk add:", err);
    } finally {
      setBulkAdding(false);
    }
  };

  const handleDelete = async (entryId: number) => {
    try {
      await api.removeFromDomainList(entryId);
      setDeleteConfirm(null);
      loadLists();
    } catch (err) {
      console.error("Failed to delete:", err);
    }
  };

  const handleClearAll = async () => {
    if (!selectedSite) return;
    setClearing(true);
    try {
      await api.clearDomainList(selectedSite, activeList);
      setClearConfirm(false);
      loadLists();
    } catch (err) {
      console.error("Failed to clear:", err);
    } finally {
      setClearing(false);
    }
  };

  const handleExportList = () => {
    const text = currentList.map((e) => e.domain).join("\n");
    navigator.clipboard.writeText(text).then(() => {
      setCopiedList(true);
      setTimeout(() => setCopiedList(false), 2000);
    });
  };

  const whitelistCount = listsData?.classification.whitelist ?? 0;
  const blacklistCount = listsData?.classification.blacklist ?? 0;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-3">
          <Settings className="w-6 h-6 text-primary-400" />
          Project Settings
        </h1>
      </div>

      {/* Site selector */}
      <div className="bg-dark-800/50 backdrop-blur-sm rounded-2xl border border-dark-700/50 p-5">
        <label className="text-xs text-dark-400 mb-2 block uppercase tracking-wider font-medium">Select Site</label>
        {domains.length === 0 ? (
          <p className="text-sm text-dark-500">No scanned sites yet. Run a scan first.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {domains.map((d) => (
              <button
                key={d.domain}
                onClick={() => setSelectedSite(d.domain)}
                className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                  selectedSite === d.domain
                    ? "bg-primary-500/20 text-primary-400 border border-primary-500/30"
                    : "bg-dark-900 text-dark-400 border border-dark-700 hover:border-dark-500 hover:text-dark-200"
                }`}
              >
                <Globe className="w-3.5 h-3.5 inline mr-1.5" />
                {d.domain}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ─── Auth Config Section ─────────────────────────────────────── */}
      {selectedSite && (
        <div className="bg-dark-800/50 backdrop-blur-sm rounded-2xl border border-dark-700/50 overflow-hidden">
          <div className="p-5 border-b border-dark-700/50">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <Lock className="w-5 h-5 text-amber-400" />
                Authenticated Scanning
              </h2>
              <div className="flex items-center gap-2">
                {stabilityScore && stabilityScore.score !== null && (
                  <span className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ${
                    stabilityScore.score >= 90 ? "bg-green-500/20 text-green-400" :
                    stabilityScore.score >= 70 ? "bg-blue-500/20 text-blue-400" :
                    stabilityScore.score >= 50 ? "bg-yellow-500/20 text-yellow-400" :
                    "bg-red-500/20 text-red-400"
                  }`} title={`Auth stability: ${stabilityScore.label} (${stabilityScore.auth_failed_count} failures, ${stabilityScore.session_expired_count} expirations in ${stabilityScore.period_days}d)`}>
                    {stabilityScore.score}% {stabilityScore.label}
                  </span>
                )}
                {authConfig?.auth_status === "success" && (
                  <span className="flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full bg-green-500/20 text-green-400">
                    <CheckCircle className="w-3.5 h-3.5" /> Connected
                  </span>
                )}
                {authConfig?.auth_status === "failed" && (
                  <span className="flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full bg-red-500/20 text-red-400">
                    <XCircle className="w-3.5 h-3.5" /> Failed
                  </span>
                )}
              </div>
            </div>
            <p className="text-xs text-dark-400 mt-1">
              Log into the website to scan protected admin/dashboard pages.
            </p>
            {/* Session expiration warning */}
            {authConfig?.auth_status === "success" && authConfig.session_valid_until && (
              <div className={`mt-2 text-xs flex items-center gap-1.5 ${
                new Date(authConfig.session_valid_until) < new Date()
                  ? "text-amber-400"
                  : "text-dark-400"
              }`}>
                <Clock className="w-3 h-3" />
                {new Date(authConfig.session_valid_until) < new Date()
                  ? "⚠ Session expired — run a new scan or test to refresh"
                  : `Session valid until ${new Date(authConfig.session_valid_until).toLocaleString()}`
                }
              </div>
            )}
            {authConfig?.last_error && authConfig.auth_status === "failed" && (
              <p className="mt-2 text-xs text-red-400/70">
                Last error: {authConfig.last_error}
              </p>
            )}
          </div>

          <div className="p-5 space-y-5">
            {authLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-dark-500" />
              </div>
            ) : (
              <>
                {/* Auth type selector */}
                <div className="space-y-2">
                  <label className="text-xs text-dark-400 uppercase tracking-wider font-medium">
                    Authentication Method
                  </label>
                  <div className="grid grid-cols-5 gap-2">
                    {([
                      { val: "none" as const, label: "None", icon: X, desc: "No auth" },
                      { val: "form" as const, label: "Form Login", icon: LogIn, desc: "Username & password" },
                      { val: "cookie" as const, label: "Cookies", icon: Cookie, desc: "Session cookies" },
                      { val: "interactive" as const, label: "Interactive", icon: Globe, desc: "Click login btn" },
                      { val: "recorded" as const, label: "Recorded", icon: Eye, desc: "Replay steps" },
                    ]).map(({ val, label, icon: Icon, desc }) => (
                      <button
                        key={val}
                        onClick={() => setAuthType(val)}
                        className={`flex flex-col items-center gap-1.5 p-4 rounded-xl border transition-all ${
                          authType === val
                            ? "bg-primary-500/10 border-primary-500/40 text-primary-400"
                            : "bg-dark-900 border-dark-700 text-dark-400 hover:border-dark-500 hover:text-dark-200"
                        }`}
                      >
                        <Icon className="w-5 h-5" />
                        <span className="text-sm font-medium">{label}</span>
                        <span className="text-[10px] text-dark-500">{desc}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Form Login Fields */}
                {authType === "form" && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="space-y-4"
                  >
                    {/* Login Strategy selector */}
                    <div className="space-y-2">
                      <label className="text-xs text-dark-400 uppercase tracking-wider font-medium">
                        Login Strategy
                      </label>
                      <div className="grid grid-cols-3 gap-2">
                        {([
                          { val: "auto" as const, label: "Auto", desc: "HTTP → Browser fallback" },
                          { val: "http_only" as const, label: "HTTP Only", desc: "Fast, no browser" },
                          { val: "playwright_only" as const, label: "Browser Only", desc: "For SPA/JS sites" },
                        ]).map(({ val, label, desc }) => (
                          <button
                            key={val}
                            onClick={() => setAuthStrategy(val)}
                            className={`flex flex-col items-center gap-1 p-3 rounded-xl border transition-all text-center ${
                              authStrategy === val
                                ? "bg-blue-500/10 border-blue-500/40 text-blue-400"
                                : "bg-dark-900 border-dark-700 text-dark-400 hover:border-dark-500 hover:text-dark-200"
                            }`}
                          >
                            <span className="text-xs font-medium">{label}</span>
                            <span className="text-[10px] text-dark-500">{desc}</span>
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="space-y-2">
                      <label className="text-xs text-dark-400 font-medium">Login URL *</label>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={loginUrl}
                          onChange={(e) => setLoginUrl(e.target.value)}
                          placeholder="https://example.com/admin/login/"
                          className="flex-1 px-4 py-2.5 bg-dark-900 border border-dark-600 rounded-xl text-sm
                                     placeholder-dark-500 focus:outline-none focus:border-primary-500 transition-colors"
                        />
                        <motion.button
                          whileHover={{ scale: 1.02 }}
                          whileTap={{ scale: 0.98 }}
                          onClick={handleDetectFields}
                          disabled={detectingFields || !loginUrl}
                          className="flex items-center gap-1.5 px-3 py-2.5 rounded-xl text-xs font-medium
                                     bg-violet-500/15 text-violet-400 hover:bg-violet-500/25 border border-violet-500/20
                                     transition-colors disabled:opacity-50 whitespace-nowrap"
                          title="Detect form fields on this login page"
                        >
                          {detectingFields ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
                          Detect Fields
                        </motion.button>
                      </div>
                    </div>

                    {/* Detected fields result */}
                    {detectedFields && (
                      <motion.div
                        initial={{ opacity: 0, y: -5 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="p-3 rounded-xl bg-violet-500/5 border border-violet-500/20 text-xs space-y-2"
                      >
                        <div className="flex items-center justify-between">
                          <p className="font-medium text-violet-400">
                            {detectedFields.success ? `Found ${detectedFields.fields.length} field(s) in ${detectedFields.forms_count} form(s)` : "Detection failed"}
                          </p>
                          <button onClick={() => setDetectedFields(null)} className="text-dark-500 hover:text-dark-300">
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                        {detectedFields.success && (
                          <>
                            {detectedFields.detected_username_field && (
                              <p className="text-green-400">✓ Username field: <code className="bg-dark-800 px-1.5 py-0.5 rounded">{detectedFields.detected_username_field}</code></p>
                            )}
                            {detectedFields.detected_password_field && (
                              <p className="text-green-400">✓ Password field: <code className="bg-dark-800 px-1.5 py-0.5 rounded">{detectedFields.detected_password_field}</code></p>
                            )}
                            {detectedFields.detected_submit && (
                              <p className="text-green-400">✓ Submit: <code className="bg-dark-800 px-1.5 py-0.5 rounded">{detectedFields.detected_submit}</code></p>
                            )}
                            {detectedFields.fields.length > 0 && (
                              <div className="mt-2 border-t border-dark-700/50 pt-2">
                                <p className="text-dark-400 mb-1">All fields:</p>
                                <div className="space-y-1 max-h-32 overflow-y-auto">
                                  {detectedFields.fields.map((f, i) => (
                                    <div key={i} className="flex items-center gap-2 text-dark-300">
                                      <span className="text-dark-500">{f.tag}</span>
                                      <span className="text-amber-400">{f.type}</span>
                                      {f.name && <span>name=<code className="bg-dark-800 px-1 rounded">{f.name}</code></span>}
                                      {f.id && <span>id=<code className="bg-dark-800 px-1 rounded">{f.id}</code></span>}
                                      {f.placeholder && <span className="text-dark-500">"{f.placeholder}"</span>}
                                      {f.css_selector && (
                                        <button
                                          onClick={() => {
                                            if (f.type === "password") setPasswordSelector(f.css_selector);
                                            else if (f.type === "submit" || f.tag === "button") setSubmitSelector(f.css_selector);
                                            else setUsernameSelector(f.css_selector);
                                          }}
                                          className="ml-auto text-[10px] text-primary-400 hover:text-primary-300 bg-primary-500/10 px-1.5 py-0.5 rounded"
                                          title="Use this selector"
                                        >
                                          Use
                                        </button>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </>
                        )}
                        {detectedFields.error && (
                          <p className="text-red-400">{detectedFields.error}</p>
                        )}
                      </motion.div>
                    )}

                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-2">
                        <label className="text-xs text-dark-400 font-medium">Username *</label>
                        <input
                          type="text"
                          value={authUsername}
                          onChange={(e) => setAuthUsername(e.target.value)}
                          placeholder="admin"
                          className="w-full px-4 py-2.5 bg-dark-900 border border-dark-600 rounded-xl text-sm
                                     placeholder-dark-500 focus:outline-none focus:border-primary-500 transition-colors"
                        />
                      </div>
                      <div className="space-y-2">
                        <label className="text-xs text-dark-400 font-medium">
                          Password * {authConfig?.has_password && <span className="text-green-500 text-[10px]">(saved)</span>}
                        </label>
                        <div className="relative">
                          <input
                            type={showPassword ? "text" : "password"}
                            value={authPassword}
                            onChange={(e) => setAuthPassword(e.target.value)}
                            placeholder={authConfig?.has_password ? "••••••••" : "Enter password"}
                            className="w-full px-4 py-2.5 pr-10 bg-dark-900 border border-dark-600 rounded-xl text-sm
                                       placeholder-dark-500 focus:outline-none focus:border-primary-500 transition-colors"
                          />
                          <button
                            type="button"
                            onClick={() => setShowPassword(!showPassword)}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-500 hover:text-dark-300"
                          >
                            {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Advanced: CSS selectors */}
                    <details className="group">
                      <summary className="text-xs text-dark-500 cursor-pointer hover:text-dark-300 flex items-center gap-1.5">
                        <ChevronDown className="w-3.5 h-3.5 group-open:rotate-180 transition-transform" />
                        Advanced: CSS Selectors (optional)
                      </summary>
                      <div className="mt-3 space-y-3 pl-5 border-l border-dark-700">
                        <div className="space-y-1">
                          <label className="text-xs text-dark-500">Username field selector</label>
                          <input
                            type="text"
                            value={usernameSelector}
                            onChange={(e) => setUsernameSelector(e.target.value)}
                            placeholder='input[name="username"]'
                            className="w-full px-3 py-2 bg-dark-900 border border-dark-700 rounded-lg text-xs
                                       placeholder-dark-600 focus:outline-none focus:border-primary-500 transition-colors"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs text-dark-500">Password field selector</label>
                          <input
                            type="text"
                            value={passwordSelector}
                            onChange={(e) => setPasswordSelector(e.target.value)}
                            placeholder='input[name="password"]'
                            className="w-full px-3 py-2 bg-dark-900 border border-dark-700 rounded-lg text-xs
                                       placeholder-dark-600 focus:outline-none focus:border-primary-500 transition-colors"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs text-dark-500">Submit button selector</label>
                          <input
                            type="text"
                            value={submitSelector}
                            onChange={(e) => setSubmitSelector(e.target.value)}
                            placeholder='button[type="submit"]'
                            className="w-full px-3 py-2 bg-dark-900 border border-dark-700 rounded-lg text-xs
                                       placeholder-dark-600 focus:outline-none focus:border-primary-500 transition-colors"
                          />
                        </div>
                      </div>
                    </details>
                  </motion.div>
                )}

                {/* Cookie Fields */}
                {authType === "cookie" && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="space-y-3"
                  >
                    <div className="space-y-2">
                      <label className="text-xs text-dark-400 font-medium">
                        Session Cookies
                      </label>
                      <textarea
                        value={cookieValue}
                        onChange={(e) => setCookieValue(e.target.value)}
                        placeholder="sessionid=abc123; csrftoken=xyz456"
                        rows={3}
                        className="w-full px-4 py-2.5 bg-dark-900 border border-dark-600 rounded-xl text-sm font-mono
                                   placeholder-dark-500 focus:outline-none focus:border-primary-500 transition-colors resize-none"
                      />
                      <p className="text-[10px] text-dark-500">
                        Paste cookies from your browser DevTools (Application → Cookies). Format: name=value; name2=value2
                      </p>
                    </div>
                  </motion.div>
                )}

                {/* Interactive Login Fields */}
                {authType === "interactive" && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="space-y-4"
                  >
                    <div className="p-3 bg-blue-500/5 border border-blue-500/20 rounded-xl">
                      <p className="text-xs text-blue-400">
                        <strong>Interactive Login</strong> opens the homepage, clicks a login button (e.g. modal trigger),
                        waits for the login form to appear, then auto-fills credentials and submits.
                        Great for sites with login modals or SPA login flows.
                      </p>
                    </div>

                    <div className="space-y-2">
                      <label className="text-xs text-dark-400 font-medium">Homepage URL *</label>
                      <input
                        type="url"
                        value={homeUrl}
                        onChange={(e) => setHomeUrl(e.target.value)}
                        placeholder="https://example.com"
                        className="w-full px-4 py-2.5 bg-dark-900 border border-dark-600 rounded-xl text-sm
                                   placeholder-dark-500 focus:outline-none focus:border-primary-500 transition-colors"
                      />
                      <p className="text-[10px] text-dark-500">
                        The page where the login button is located (usually the homepage)
                      </p>
                    </div>

                    <div className="space-y-2">
                      <label className="text-xs text-dark-400 font-medium">Login Button Selector</label>
                      <input
                        type="text"
                        value={loginButtonSelector}
                        onChange={(e) => setLoginButtonSelector(e.target.value)}
                        placeholder='a[href="/login"], .login-btn, #signInBtn'
                        className="w-full px-4 py-2.5 bg-dark-900 border border-dark-600 rounded-xl text-sm font-mono
                                   placeholder-dark-500 focus:outline-none focus:border-primary-500 transition-colors"
                      />
                      <p className="text-[10px] text-dark-500">
                        CSS selector for the login button on the homepage. Leave blank for auto-detection.
                      </p>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-2">
                        <label className="text-xs text-dark-400 font-medium">Username *</label>
                        <input
                          type="text"
                          value={authUsername}
                          onChange={(e) => setAuthUsername(e.target.value)}
                          placeholder="user@example.com"
                          className="w-full px-4 py-2.5 bg-dark-900 border border-dark-600 rounded-xl text-sm
                                     placeholder-dark-500 focus:outline-none focus:border-primary-500 transition-colors"
                        />
                      </div>
                      <div className="space-y-2">
                        <label className="text-xs text-dark-400 font-medium">Password *</label>
                        <div className="relative">
                          <input
                            type={showPassword ? "text" : "password"}
                            value={authPassword}
                            onChange={(e) => setAuthPassword(e.target.value)}
                            placeholder={authConfig?.has_password ? "••••••••" : "Enter password"}
                            className="w-full px-4 py-2.5 bg-dark-900 border border-dark-600 rounded-xl text-sm
                                       placeholder-dark-500 focus:outline-none focus:border-primary-500 transition-colors pr-10"
                          />
                          <button
                            onClick={() => setShowPassword(!showPassword)}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-500 hover:text-dark-300"
                          >
                            {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                        </div>
                      </div>
                    </div>

                    <details className="group">
                      <summary className="text-xs text-dark-500 cursor-pointer hover:text-dark-300 transition-colors">
                        ▸ Advanced: CSS selectors (optional)
                      </summary>
                      <div className="mt-3 space-y-3 pl-3 border-l border-dark-700">
                        <div className="grid grid-cols-3 gap-3">
                          <div className="space-y-1">
                            <label className="text-[10px] text-dark-500">Username Selector</label>
                            <input
                              type="text"
                              value={usernameSelector}
                              onChange={(e) => setUsernameSelector(e.target.value)}
                              placeholder="auto-detect"
                              className="w-full px-3 py-2 bg-dark-900 border border-dark-700 rounded-lg text-xs font-mono
                                         placeholder-dark-600 focus:outline-none focus:border-primary-500 transition-colors"
                            />
                          </div>
                          <div className="space-y-1">
                            <label className="text-[10px] text-dark-500">Password Selector</label>
                            <input
                              type="text"
                              value={passwordSelector}
                              onChange={(e) => setPasswordSelector(e.target.value)}
                              placeholder="auto-detect"
                              className="w-full px-3 py-2 bg-dark-900 border border-dark-700 rounded-lg text-xs font-mono
                                         placeholder-dark-600 focus:outline-none focus:border-primary-500 transition-colors"
                            />
                          </div>
                          <div className="space-y-1">
                            <label className="text-[10px] text-dark-500">Submit Selector</label>
                            <input
                              type="text"
                              value={submitSelector}
                              onChange={(e) => setSubmitSelector(e.target.value)}
                              placeholder="auto-detect"
                              className="w-full px-3 py-2 bg-dark-900 border border-dark-700 rounded-lg text-xs font-mono
                                         placeholder-dark-600 focus:outline-none focus:border-primary-500 transition-colors"
                            />
                          </div>
                        </div>
                      </div>
                    </details>
                  </motion.div>
                )}

                {/* Recorded Flow Fields */}
                {authType === "recorded" && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="space-y-4"
                  >
                    <div className="p-3 bg-purple-500/5 border border-purple-500/20 rounded-xl">
                      <p className="text-xs text-purple-400">
                        <strong>Recorded Flow</strong> — record your login by interacting with a real browser,
                        or manually define steps. Credentials use <code className="bg-dark-800 px-1 rounded">{"{{USER_INPUT}}"}</code> and <code className="bg-dark-800 px-1 rounded">{"{{PASSWORD_INPUT}}"}</code> placeholders.
                      </p>
                    </div>

                    {/* ── Recorder Controls ───────────────────────── */}
                    <div className="p-4 bg-dark-900 border border-dark-700 rounded-xl space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Monitor className="w-4 h-4 text-purple-400" />
                          <span className="text-sm font-medium text-dark-200">Browser Recorder</span>
                        </div>
                        {isRecording && (
                          <div className="flex items-center gap-2">
                            <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                            <span className="text-xs text-red-400 font-medium">Recording...</span>
                            <span className="text-xs text-dark-500">
                              {recorderEventsCount} events · {recorderStatus?.elapsed ? `${Math.floor(recorderStatus.elapsed)}s` : "..."}
                            </span>
                          </div>
                        )}
                      </div>

                      {!isRecording ? (
                        <div className="space-y-3">
                          <p className="text-xs text-dark-400">
                            Click <strong>Start Recording</strong> to open a browser window.
                            Complete your login flow — clicks, typing, and navigation are captured automatically.
                          </p>
                          <div className="flex gap-2">
                            <button
                              onClick={handleStartRecording}
                              disabled={recorderLoading || !selectedSite}
                              className="flex items-center gap-2 px-4 py-2.5 bg-red-500/20 text-red-400 border border-red-500/30
                                         rounded-xl text-sm font-medium hover:bg-red-500/30 transition-all disabled:opacity-50"
                            >
                              {recorderLoading ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : (
                                <Circle className="w-4 h-4 fill-red-500" />
                              )}
                              Start Recording
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="space-y-3">
                          <div className="p-3 bg-red-500/5 border border-red-500/20 rounded-lg">
                            <p className="text-xs text-red-300">
                              🔴 <strong>Recording in progress</strong> — Complete the login in the browser below.
                              When done, click Stop Recording.
                            </p>
                          </div>
                          <button
                            onClick={handleStopRecording}
                            disabled={recorderLoading}
                            className="flex items-center gap-2 px-4 py-2.5 bg-dark-700 text-dark-200 border border-dark-600
                                       rounded-xl text-sm font-medium hover:bg-dark-600 transition-all disabled:opacity-50"
                          >
                            {recorderLoading ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Square className="w-4 h-4" />
                            )}
                            Stop Recording
                          </button>
                        </div>
                      )}

                      {recorderError && (
                        <div className="p-2 bg-red-500/10 border border-red-500/20 rounded-lg">
                          <p className="text-xs text-red-400">{recorderError}</p>
                        </div>
                      )}
                    </div>

                    {/* ── Embedded Browser (noVNC) ─────────────────── */}
                    {showRecorderBrowser && isRecording && (
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-dark-400 font-medium">Live Browser</span>
                          <button
                            onClick={() => window.open(`${window.location.protocol}//${window.location.hostname}:6080/vnc.html?autoconnect=true&resize=remote&quality=9&compression=0&show_dot=true&view_only=false`, "_blank")}
                            className="text-xs text-primary-400 hover:text-primary-300 flex items-center gap-1"
                          >
                            <Globe className="w-3 h-3" /> Open in new tab
                          </button>
                        </div>
                        <div className="border border-dark-600 rounded-xl overflow-hidden bg-black">
                          <iframe
                            src={`${typeof window !== 'undefined' ? window.location.protocol : 'http:'}//${typeof window !== 'undefined' ? window.location.hostname : 'localhost'}:6080/vnc.html?autoconnect=true&resize=scale&reconnect=true&reconnect_delay=2000&show_dot=true&view_only=false&quality=9&compression=0`}
                            className="w-full border-0"
                            style={{ height: "700px" }}
                            title="Browser Recorder"
                            allow="clipboard-read; clipboard-write"
                          />
                        </div>
                      </div>
                    )}

                    {/* ── Credentials ─────────────────────────────── */}
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-2">
                        <label className="text-xs text-dark-400 font-medium">Username</label>
                        <input
                          type="text"
                          value={authUsername}
                          onChange={(e) => setAuthUsername(e.target.value)}
                          placeholder="user@example.com"
                          className="w-full px-4 py-2.5 bg-dark-900 border border-dark-600 rounded-xl text-sm
                                     placeholder-dark-500 focus:outline-none focus:border-primary-500 transition-colors"
                        />
                      </div>
                      <div className="space-y-2">
                        <label className="text-xs text-dark-400 font-medium">Password</label>
                        <div className="relative">
                          <input
                            type={showPassword ? "text" : "password"}
                            value={authPassword}
                            onChange={(e) => setAuthPassword(e.target.value)}
                            placeholder={authConfig?.has_password ? "••••••••" : "Enter password"}
                            className="w-full px-4 py-2.5 bg-dark-900 border border-dark-600 rounded-xl text-sm
                                       placeholder-dark-500 focus:outline-none focus:border-primary-500 transition-colors pr-10"
                          />
                          <button
                            onClick={() => setShowPassword(!showPassword)}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-500 hover:text-dark-300"
                          >
                            {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* ── Steps list ──────────────────────────────── */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <label className="text-xs text-dark-400 font-medium">
                          Login Steps ({recordedSteps.length})
                        </label>
                        <button
                          onClick={() => {
                            setShowAddStep(true);
                            setEditingStepIndex(null);
                            setStepAction("click");
                            setStepSelector("");
                            setStepValue("");
                            setStepWaitMs(1000);
                            setStepDescription("");
                          }}
                          className="text-xs text-primary-400 hover:text-primary-300 flex items-center gap-1"
                        >
                          <Plus className="w-3 h-3" /> Add Step
                        </button>
                      </div>

                      {recordedSteps.length === 0 && !showAddStep && (
                        <div className="p-4 bg-dark-900 border border-dark-700 rounded-xl text-center">
                          <p className="text-xs text-dark-500">No steps yet. Use the <strong>Recorder</strong> or manually add steps.</p>
                          <div className="mt-3 space-y-1 text-left">
                            <p className="text-[10px] text-dark-600">Example flow:</p>
                            <p className="text-[10px] text-dark-500 font-mono">1. goto → https://example.com/login</p>
                            <p className="text-[10px] text-dark-500 font-mono">2. type → #email → {"{{USER_INPUT}}"}</p>
                            <p className="text-[10px] text-dark-500 font-mono">3. type → #password → {"{{PASSWORD_INPUT}}"}</p>
                            <p className="text-[10px] text-dark-500 font-mono">4. click → button[type=submit]</p>
                            <p className="text-[10px] text-dark-500 font-mono">5. wait → 3000ms</p>
                          </div>
                        </div>
                      )}

                      {recordedSteps.map((step, idx) => (
                        <div
                          key={idx}
                          className="flex items-center gap-2 p-2.5 bg-dark-900 border border-dark-700 rounded-lg group"
                        >
                          <span className="text-[10px] text-dark-600 font-mono w-5 text-right">{idx + 1}.</span>
                          <span className="text-xs font-mono text-purple-400 w-14">{step.action}</span>
                          {step.selector && (
                            <span className="text-xs font-mono text-dark-300 truncate max-w-[150px]" title={step.selector}>
                              {step.selector}
                            </span>
                          )}
                          {step.value && (
                            <span className="text-xs font-mono text-dark-400 truncate max-w-[120px]" title={step.value}>
                              → {step.value.includes("PASSWORD_INPUT") ? "***" : step.value}
                            </span>
                          )}
                          {step.action === "wait" && (
                            <span className="text-xs text-dark-500">{step.wait_ms || 1000}ms</span>
                          )}
                          {step.description && (
                            <span className="text-[10px] text-dark-600 truncate ml-auto max-w-[140px]" title={step.description}>
                              {step.description}
                            </span>
                          )}
                          <div className="ml-auto flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button
                              onClick={() => {
                                setEditingStepIndex(idx);
                                setShowAddStep(true);
                                setStepAction(step.action);
                                setStepSelector(step.selector || "");
                                setStepValue(step.value || "");
                                setStepWaitMs(step.wait_ms || 1000);
                                setStepDescription(step.description || "");
                              }}
                              className="p-1 text-dark-500 hover:text-primary-400"
                              title="Edit step"
                            >
                              <Edit3 className="w-3 h-3" />
                            </button>
                            <button
                              onClick={() => {
                                const newSteps = [...recordedSteps];
                                if (idx > 0) {
                                  [newSteps[idx - 1], newSteps[idx]] = [newSteps[idx], newSteps[idx - 1]];
                                  setRecordedSteps(newSteps);
                                }
                              }}
                              className="p-1 text-dark-500 hover:text-dark-300"
                              disabled={idx === 0}
                              title="Move up"
                            >
                              <ChevronDown className="w-3 h-3 rotate-180" />
                            </button>
                            <button
                              onClick={() => {
                                const newSteps = [...recordedSteps];
                                if (idx < newSteps.length - 1) {
                                  [newSteps[idx], newSteps[idx + 1]] = [newSteps[idx + 1], newSteps[idx]];
                                  setRecordedSteps(newSteps);
                                }
                              }}
                              className="p-1 text-dark-500 hover:text-dark-300"
                              disabled={idx === recordedSteps.length - 1}
                              title="Move down"
                            >
                              <ChevronDown className="w-3 h-3" />
                            </button>
                            <button
                              onClick={() => {
                                setRecordedSteps(recordedSteps.filter((_, i) => i !== idx));
                              }}
                              className="p-1 text-dark-500 hover:text-red-400"
                              title="Delete step"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          </div>
                        </div>
                      ))}

                      {/* Add/Edit Step Form */}
                      {showAddStep && (
                        <div className="p-3 bg-dark-800 border border-dark-600 rounded-xl space-y-3">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-medium text-dark-300">
                              {editingStepIndex !== null ? `Edit Step ${editingStepIndex + 1}` : "Add Step"}
                            </span>
                          </div>
                          <div className="grid grid-cols-2 gap-2">
                            <div className="space-y-1">
                              <label className="text-[10px] text-dark-500">Action *</label>
                              <select
                                value={stepAction}
                                onChange={(e) => setStepAction(e.target.value)}
                                className="w-full px-3 py-2 bg-dark-900 border border-dark-700 rounded-lg text-xs
                                           focus:outline-none focus:border-primary-500 transition-colors"
                              >
                                <option value="goto">goto — Navigate to URL</option>
                                <option value="click">click — Click element</option>
                                <option value="type">type — Type text into field</option>
                                <option value="press">press — Press key (Enter, Tab...)</option>
                                <option value="select">select — Select dropdown option</option>
                                <option value="check">check — Check checkbox</option>
                                <option value="wait">wait — Wait (ms)</option>
                                <option value="wait_for">wait_for — Wait for element</option>
                              </select>
                            </div>
                            {stepAction !== "wait" && (
                              <div className="space-y-1">
                                <label className="text-[10px] text-dark-500">
                                  {stepAction === "goto" ? "URL" : "CSS Selector"}
                                </label>
                                <input
                                  type="text"
                                  value={stepAction === "goto" ? stepValue : stepSelector}
                                  onChange={(e) => stepAction === "goto" ? setStepValue(e.target.value) : setStepSelector(e.target.value)}
                                  placeholder={stepAction === "goto" ? "https://..." : "#selector, .class"}
                                  className="w-full px-3 py-2 bg-dark-900 border border-dark-700 rounded-lg text-xs font-mono
                                             placeholder-dark-600 focus:outline-none focus:border-primary-500 transition-colors"
                                />
                              </div>
                            )}
                          </div>
                          {(stepAction === "type" || stepAction === "select" || stepAction === "press") && (
                            <div className="space-y-1">
                              <label className="text-[10px] text-dark-500">
                                Value {stepAction === "type" && "(use {{USER_INPUT}} or {{PASSWORD_INPUT}} for credentials)"}
                                {stepAction === "press" && "(e.g. Enter, Tab, Escape)"}
                              </label>
                              <input
                                type="text"
                                value={stepValue}
                                onChange={(e) => setStepValue(e.target.value)}
                                placeholder={
                                  stepAction === "type" ? "{{USER_INPUT}}" :
                                  stepAction === "press" ? "Enter" : "option value"
                                }
                                className="w-full px-3 py-2 bg-dark-900 border border-dark-700 rounded-lg text-xs font-mono
                                           placeholder-dark-600 focus:outline-none focus:border-primary-500 transition-colors"
                              />
                            </div>
                          )}
                          {(stepAction === "wait" || stepAction === "wait_for") && (
                            <div className="space-y-1">
                              <label className="text-[10px] text-dark-500">
                                {stepAction === "wait" ? "Wait time (ms)" : "Timeout (ms)"}
                              </label>
                              <input
                                type="number"
                                value={stepWaitMs}
                                onChange={(e) => setStepWaitMs(parseInt(e.target.value) || 1000)}
                                placeholder="1000"
                                className="w-full px-3 py-2 bg-dark-900 border border-dark-700 rounded-lg text-xs
                                           placeholder-dark-600 focus:outline-none focus:border-primary-500 transition-colors"
                              />
                            </div>
                          )}
                          <div className="space-y-1">
                            <label className="text-[10px] text-dark-500">Description (optional)</label>
                            <input
                              type="text"
                              value={stepDescription}
                              onChange={(e) => setStepDescription(e.target.value)}
                              placeholder="e.g. Click the Sign In button"
                              className="w-full px-3 py-2 bg-dark-900 border border-dark-700 rounded-lg text-xs
                                         placeholder-dark-600 focus:outline-none focus:border-primary-500 transition-colors"
                            />
                          </div>
                          <div className="flex gap-2">
                            <button
                              onClick={() => {
                                const step: any = { action: stepAction };
                                if (stepAction === "goto") {
                                  step.value = stepValue;
                                } else if (stepAction === "wait") {
                                  step.wait_ms = stepWaitMs;
                                } else if (stepAction === "wait_for") {
                                  step.selector = stepSelector;
                                  step.wait_ms = stepWaitMs;
                                } else {
                                  step.selector = stepSelector;
                                  if (stepValue) step.value = stepValue;
                                }
                                if (stepDescription) step.description = stepDescription;

                                if (editingStepIndex !== null) {
                                  const newSteps = [...recordedSteps];
                                  newSteps[editingStepIndex] = step;
                                  setRecordedSteps(newSteps);
                                } else {
                                  setRecordedSteps([...recordedSteps, step]);
                                }
                                setShowAddStep(false);
                                setEditingStepIndex(null);
                              }}
                              className="px-4 py-1.5 bg-primary-500/20 text-primary-400 border border-primary-500/30
                                         rounded-lg text-xs font-medium hover:bg-primary-500/30 transition-colors"
                            >
                              {editingStepIndex !== null ? "Update" : "Add"}
                            </button>
                            <button
                              onClick={() => {
                                setShowAddStep(false);
                                setEditingStepIndex(null);
                              }}
                              className="px-4 py-1.5 bg-dark-700 text-dark-300 rounded-lg text-xs hover:bg-dark-600 transition-colors"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  </motion.div>
                )}

                {/* Enable/Disable toggle */}
                {authType !== "none" && (
                  <label className="flex items-center gap-3 cursor-pointer">
                    <div
                      className={`w-10 h-5 rounded-full transition-colors relative ${
                        authEnabled ? "bg-primary-500" : "bg-dark-600"
                      }`}
                      onClick={() => setAuthEnabled(!authEnabled)}
                    >
                      <div
                        className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                          authEnabled ? "translate-x-5" : "translate-x-0.5"
                        }`}
                      />
                    </div>
                    <span className="text-sm text-dark-300">
                      {authEnabled ? "Enabled" : "Disabled"} — {authEnabled ? "scans will include authenticated pages" : "auth scan skipped"}
                    </span>
                  </label>
                )}

                {/* Test result */}
                {authTestResult && (
                  <motion.div
                    initial={{ opacity: 0, y: -5 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`p-3 rounded-xl text-sm flex items-start gap-2 ${
                      authTestResult.status === "success"
                        ? "bg-green-500/10 border border-green-500/30 text-green-400"
                        : "bg-red-500/10 border border-red-500/30 text-red-400"
                    }`}
                  >
                    {authTestResult.status === "success" ? (
                      <>
                        <CheckCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                        <div>
                          <p className="font-medium">Login successful!</p>
                          {authTestResult.method && (
                            <p className="text-xs mt-0.5 opacity-80">
                              Method: {authTestResult.method === "playwright" ? "Headless Browser" : "HTTP Form"}
                            </p>
                          )}
                          {authTestResult.pages_accessible !== undefined && (
                            <p className="text-xs mt-0.5 opacity-80">
                              {authTestResult.pages_accessible} protected page(s) accessible
                            </p>
                          )}
                          {authTestResult.accessible_paths && authTestResult.accessible_paths.length > 0 && (
                            <p className="text-xs mt-0.5 opacity-60">
                              Paths: {authTestResult.accessible_paths.join(", ")}
                            </p>
                          )}
                          {authTestResult.cookies_count !== undefined && (
                            <p className="text-xs mt-0.5 opacity-60">
                              {authTestResult.cookies_count} session cookie(s)
                            </p>
                          )}
                          {authTestResult.warning && (
                            <p className="text-xs mt-1 text-yellow-400/80">
                              ⚠ {authTestResult.warning}
                            </p>
                          )}
                        </div>
                      </>
                    ) : (
                      <>
                        <XCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                        <div>
                          <p className="font-medium">Login failed</p>
                          {authTestResult.message && (
                            <p className="text-xs mt-0.5 opacity-80">{authTestResult.message}</p>
                          )}
                          {authTestResult.needs_selectors && (
                            <p className="text-xs mt-1 text-amber-400/80">
                              💡 Try specifying CSS selectors for username/password fields above
                            </p>
                          )}
                          {authTestResult.playwright_available === false && (
                            <p className="text-xs mt-1 text-amber-400/80">
                              💡 Headless browser fallback unavailable. Contact admin to install Playwright.
                            </p>
                          )}
                        </div>
                      </>
                    )}
                  </motion.div>
                )}

                {/* Security notice */}
                {authType !== "none" && (
                  <div className="flex items-start gap-2 p-3 rounded-xl bg-amber-500/5 border border-amber-500/20 text-amber-400/80 text-xs">
                    <Key className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                    <p>Credentials are encrypted and stored securely. They are only used to authenticate scan requests.</p>
                  </div>
                )}

                {/* Action buttons */}
                <div className="flex flex-wrap gap-2 pt-2">
                  {authType !== "none" && (
                    <motion.button
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={handleAuthTest}
                      disabled={authTesting}
                      className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium
                                 bg-dark-700 text-dark-200 hover:bg-dark-600 transition-colors disabled:opacity-50"
                    >
                      {authTesting ? <Loader2 className="w-4 h-4 animate-spin" /> : <TestTube className="w-4 h-4" />}
                      Test Login
                    </motion.button>
                  )}
                  {authType !== "none" && authConfig && authConfig.auth_type !== "none" && (
                    <motion.button
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={handleDebugLogin}
                      disabled={debugLoading}
                      className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium
                                 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 border border-amber-500/20
                                 transition-colors disabled:opacity-50"
                      title="Debug login — shows step-by-step what happens"
                    >
                      {debugLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <AlertTriangle className="w-4 h-4" />}
                      Debug
                    </motion.button>
                  )}
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={handleAuthSave}
                    disabled={authSaving}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium
                               bg-primary-500 text-white hover:bg-primary-400 transition-colors disabled:opacity-50"
                  >
                    {authSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                    Save
                  </motion.button>
                  {authConfig && authConfig.auth_type !== "none" && (
                    <motion.button
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={handleAuthDelete}
                      className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium
                                 text-red-400 bg-red-500/10 hover:bg-red-500/20 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                      Remove
                    </motion.button>
                  )}
                </div>

                {/* Debug Modal */}
                <AnimatePresence>
                  {showDebugModal && (
                    <motion.div
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      className="p-4 rounded-xl bg-dark-900 border border-dark-600 space-y-3"
                    >
                      <div className="flex items-center justify-between">
                        <h3 className="text-sm font-semibold text-amber-400 flex items-center gap-2">
                          <AlertTriangle className="w-4 h-4" />
                          Auth Debug — Step-by-Step
                        </h3>
                        <button onClick={() => setShowDebugModal(false)} className="text-dark-500 hover:text-dark-300">
                          <X className="w-4 h-4" />
                        </button>
                      </div>

                      {debugLoading ? (
                        <div className="flex items-center gap-2 py-4 justify-center text-dark-400 text-sm">
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Running debug login attempt...
                        </div>
                      ) : debugResult ? (
                        <div className="space-y-2 max-h-64 overflow-y-auto">
                          {(debugResult.steps || debugResult.step_results || []).map((step, i) => (
                            <div key={i} className={`flex items-start gap-2 p-2 rounded-lg text-xs ${
                              step.status === "ok" ? "bg-green-500/5 text-green-400" :
                              step.status === "warning" ? "bg-yellow-500/5 text-yellow-400" :
                              "bg-red-500/5 text-red-400"
                            }`}>
                              <span className="flex-shrink-0 mt-0.5">
                                {step.status === "ok" ? <CheckCircle className="w-3.5 h-3.5" /> :
                                 step.status === "warning" ? <AlertTriangle className="w-3.5 h-3.5" /> :
                                 <XCircle className="w-3.5 h-3.5" />}
                              </span>
                              <div>
                                <span className="font-medium">{step.step}</span>
                                {step.detail && <span className="text-dark-300 ml-1.5">— {step.detail}</span>}
                                {step.data && (
                                  <pre className="mt-1 text-[10px] text-dark-400 bg-dark-800 p-1.5 rounded overflow-x-auto">
                                    {JSON.stringify(step.data, null, 2)}
                                  </pre>
                                )}
                              </div>
                            </div>
                          ))}
                          <div className={`text-xs font-medium mt-2 pt-2 border-t border-dark-700/50 ${
                            debugResult.success ? "text-green-400" : "text-red-400"
                          }`}>
                            {debugResult.success ? "✅ Login succeeded" : "❌ Login failed"}
                          </div>
                        </div>
                      ) : null}
                    </motion.div>
                  )}
                </AnimatePresence>
              </>
            )}
          </div>
        </div>
      )}

      {/* ─── Whitelist / Blacklist Section ────────────────────────────── */}
      {selectedSite && (
        <div className="bg-dark-800/50 backdrop-blur-sm rounded-2xl border border-dark-700/50 overflow-hidden">
          {/* List type tabs */}
          <div className="flex border-b border-dark-700/50">
            <button
              onClick={() => { setActiveList("whitelist"); setSearch(""); }}
              className={`flex-1 flex items-center justify-center gap-2 py-4 text-sm font-medium transition-all ${
                activeList === "whitelist"
                  ? "text-green-400 border-b-2 border-green-500 bg-green-500/5"
                  : "text-dark-400 hover:text-dark-200"
              }`}
            >
              <ShieldCheck className="w-4 h-4" />
              Whitelist
              <span className={`px-2 py-0.5 rounded-full text-xs ${
                activeList === "whitelist" ? "bg-green-500/20 text-green-400" : "bg-dark-700 text-dark-500"
              }`}>
                {listsData?.whitelist.length ?? 0}
              </span>
            </button>
            <button
              onClick={() => { setActiveList("blacklist"); setSearch(""); }}
              className={`flex-1 flex items-center justify-center gap-2 py-4 text-sm font-medium transition-all ${
                activeList === "blacklist"
                  ? "text-red-400 border-b-2 border-red-500 bg-red-500/5"
                  : "text-dark-400 hover:text-dark-200"
              }`}
            >
              <ShieldX className="w-4 h-4" />
              Blacklist
              <span className={`px-2 py-0.5 rounded-full text-xs ${
                activeList === "blacklist" ? "bg-red-500/20 text-red-400" : "bg-dark-700 text-dark-500"
              }`}>
                {listsData?.blacklist.length ?? 0}
              </span>
            </button>
          </div>

          <div className="p-5 space-y-4">
            {/* Toolbar */}
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-500" />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search domains..."
                  className="w-full pl-10 pr-4 py-2.5 bg-dark-900 border border-dark-600 rounded-xl text-sm
                             placeholder-dark-500 focus:outline-none focus:border-primary-500 transition-colors"
                />
              </div>
              <div className="flex gap-2">
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => { setShowAddForm(!showAddForm); setShowBulkAdd(false); }}
                  className={`flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${
                    activeList === "whitelist"
                      ? "bg-green-500/15 text-green-400 hover:bg-green-500/25 border border-green-500/20"
                      : "bg-red-500/15 text-red-400 hover:bg-red-500/25 border border-red-500/20"
                  }`}
                >
                  <Plus className="w-4 h-4" />
                  Add
                </motion.button>
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => { setShowBulkAdd(!showBulkAdd); setShowAddForm(false); }}
                  className="flex items-center gap-1.5 px-3 py-2.5 rounded-xl text-sm text-dark-400 hover:text-dark-200
                             bg-dark-900 border border-dark-600 hover:border-dark-500 transition-all"
                  title="Bulk import"
                >
                  <Upload className="w-4 h-4" />
                </motion.button>
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={handleExportList}
                  className="flex items-center gap-1.5 px-3 py-2.5 rounded-xl text-sm text-dark-400 hover:text-dark-200
                             bg-dark-900 border border-dark-600 hover:border-dark-500 transition-all"
                  title="Export list"
                >
                  {copiedList ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
                </motion.button>
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={loadLists}
                  className="flex items-center gap-1.5 px-3 py-2.5 rounded-xl text-sm text-dark-400 hover:text-dark-200
                             bg-dark-900 border border-dark-600 hover:border-dark-500 transition-all"
                >
                  <RefreshCw className="w-4 h-4" />
                </motion.button>
              </div>
            </div>

            {/* Add single domain form */}
            <AnimatePresence>
              {showAddForm && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden"
                >
                  <div className={`rounded-xl border p-4 space-y-3 ${
                    activeList === "whitelist"
                      ? "bg-green-500/5 border-green-500/20"
                      : "bg-red-500/5 border-red-500/20"
                  }`}>
                    <div>
                      <label className="text-xs text-dark-400 mb-1 block">Domain</label>
                      <input
                        type="text"
                        value={addInput}
                        onChange={(e) => setAddInput(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            handleAdd();
                          }
                        }}
                        placeholder="e.g. example.com"
                        className="w-full px-3 py-2 bg-dark-900 border border-dark-600 rounded-lg text-sm
                                   placeholder-dark-600 focus:outline-none focus:border-primary-500 transition-colors"
                        autoFocus
                      />
                    </div>
                    <div>
                      <label className="text-xs text-dark-400 mb-1 block">Note (optional)</label>
                      <input
                        type="text"
                        value={addNote}
                        onChange={(e) => setAddNote(e.target.value)}
                        placeholder="Why is this domain trusted/blocked?"
                        className="w-full px-3 py-2 bg-dark-900 border border-dark-600 rounded-lg text-sm
                                   placeholder-dark-600 focus:outline-none focus:border-primary-500 transition-colors"
                      />
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={handleAdd}
                        disabled={adding || !addInput.trim()}
                        className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
                          activeList === "whitelist"
                            ? "bg-green-500/20 text-green-400 hover:bg-green-500/30"
                            : "bg-red-500/20 text-red-400 hover:bg-red-500/30"
                        }`}
                      >
                        {adding ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                        Add to {activeList}
                      </button>
                      <button
                        onClick={() => setShowAddForm(false)}
                        className="px-3 py-2 rounded-lg text-sm text-dark-400 hover:text-dark-200 transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Bulk add form */}
            <AnimatePresence>
              {showBulkAdd && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden"
                >
                  <div className="rounded-xl border border-dark-600 bg-dark-900/50 p-4 space-y-3">
                    <label className="text-xs text-dark-400 mb-1 block">
                      Paste domains (one per line, or comma/semicolon separated)
                    </label>
                    <textarea
                      value={bulkInput}
                      onChange={(e) => setBulkInput(e.target.value)}
                      rows={5}
                      placeholder={"google.com\nfacebook.com\ntwitter.com"}
                      className="w-full px-3 py-2 bg-dark-900 border border-dark-600 rounded-lg text-sm font-mono
                                 placeholder-dark-600 focus:outline-none focus:border-primary-500 transition-colors resize-y"
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={handleBulkAdd}
                        disabled={bulkAdding || !bulkInput.trim()}
                        className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
                          activeList === "whitelist"
                            ? "bg-green-500/20 text-green-400 hover:bg-green-500/30"
                            : "bg-red-500/20 text-red-400 hover:bg-red-500/30"
                        }`}
                      >
                        {bulkAdding ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
                        Import to {activeList}
                      </button>
                      <button
                        onClick={() => setShowBulkAdd(false)}
                        className="px-3 py-2 rounded-lg text-sm text-dark-400 hover:text-dark-200 transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Domain list */}
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 text-primary-500 animate-spin" />
              </div>
            ) : filteredList.length === 0 ? (
              <div className="text-center py-12 text-dark-500">
                {activeList === "whitelist" ? (
                  <ShieldCheck className="w-12 h-12 mx-auto mb-3 opacity-20" />
                ) : (
                  <ShieldX className="w-12 h-12 mx-auto mb-3 opacity-20" />
                )}
                <p className="font-medium">
                  {search
                    ? "No domains match your search"
                    : `No domains in ${activeList} yet`}
                </p>
                <p className="text-xs mt-1">
                  {search
                    ? "Try a different search term"
                    : `Click "Add" to add domains to this ${activeList}`}
                </p>
              </div>
            ) : (
              <div className="space-y-1.5">
                {filteredList.map((entry, i) => (
                  <motion.div
                    key={entry.id}
                    initial={{ opacity: 0, y: 5 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.02 }}
                    className={`flex items-center gap-3 p-3 rounded-xl border transition-all group ${
                      activeList === "whitelist"
                        ? "bg-green-500/5 border-green-500/10 hover:border-green-500/25"
                        : "bg-red-500/5 border-red-500/10 hover:border-red-500/25"
                    }`}
                  >
                    <div className={`p-1.5 rounded-lg flex-shrink-0 ${
                      activeList === "whitelist" ? "bg-green-500/10" : "bg-red-500/10"
                    }`}>
                      {activeList === "whitelist" ? (
                        <ShieldCheck className="w-4 h-4 text-green-400" />
                      ) : (
                        <ShieldX className="w-4 h-4 text-red-400" />
                      )}
                    </div>

                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-dark-200 truncate">{entry.domain}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        {editingId === entry.id ? (
                          <div className="flex items-center gap-2 flex-1">
                            <input
                              type="text"
                              value={editNote}
                              onChange={(e) => setEditNote(e.target.value)}
                              placeholder="Add a note..."
                              className="flex-1 px-2 py-1 bg-dark-900 border border-dark-600 rounded text-xs
                                         placeholder-dark-600 focus:outline-none focus:border-primary-500 transition-colors"
                              autoFocus
                            />
                            <button
                              onClick={() => {
                                // Note: we'd need a PATCH endpoint for notes, for now just close
                                setEditingId(null);
                              }}
                              className="p-1 rounded hover:bg-dark-700 transition-colors"
                            >
                              <Save className="w-3 h-3 text-primary-400" />
                            </button>
                            <button
                              onClick={() => setEditingId(null)}
                              className="p-1 rounded hover:bg-dark-700 transition-colors"
                            >
                              <X className="w-3 h-3 text-dark-500" />
                            </button>
                          </div>
                        ) : (
                          <>
                            {entry.note && (
                              <span className="text-xs text-dark-500 truncate">{entry.note}</span>
                            )}
                            <span className="text-[10px] text-dark-600">
                              {new Date(entry.created_at).toLocaleDateString()}
                            </span>
                            {entry.added_by && (
                              <span className="text-[10px] text-dark-600 px-1.5 py-0.5 rounded bg-dark-800">
                                {entry.added_by}
                              </span>
                            )}
                          </>
                        )}
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => {
                          setEditingId(entry.id);
                          setEditNote(entry.note || "");
                        }}
                        className="p-1.5 rounded-md hover:bg-dark-700 transition-colors"
                        title="Edit note"
                      >
                        <Edit3 className="w-3.5 h-3.5 text-dark-500 hover:text-dark-300" />
                      </button>
                      {deleteConfirm === entry.id ? (
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => handleDelete(entry.id)}
                            className="p-1.5 rounded-md bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors"
                            title="Confirm delete"
                          >
                            <Check className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => setDeleteConfirm(null)}
                            className="p-1.5 rounded-md hover:bg-dark-700 transition-colors"
                            title="Cancel"
                          >
                            <X className="w-3.5 h-3.5 text-dark-500" />
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setDeleteConfirm(entry.id)}
                          className="p-1.5 rounded-md hover:bg-red-500/20 transition-colors"
                          title="Delete"
                        >
                          <Trash2 className="w-3.5 h-3.5 text-dark-500 hover:text-red-400" />
                        </button>
                      )}
                    </div>
                  </motion.div>
                ))}
              </div>
            )}

            {/* Clear all */}
            {currentList.length > 0 && (
              <div className="pt-4 border-t border-dark-700/50">
                {clearConfirm ? (
                  <div className="flex items-center gap-3 p-3 rounded-xl bg-red-500/5 border border-red-500/20">
                    <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0" />
                    <p className="text-sm text-dark-300 flex-1">
                      Remove all {currentList.length} domains from {activeList}?
                    </p>
                    <button
                      onClick={handleClearAll}
                      disabled={clearing}
                      className="px-3 py-1.5 rounded-lg bg-red-500/20 text-red-400 text-xs font-medium hover:bg-red-500/30
                                 transition-colors disabled:opacity-50"
                    >
                      {clearing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Yes, clear all"}
                    </button>
                    <button
                      onClick={() => setClearConfirm(false)}
                      className="px-3 py-1.5 rounded-lg text-dark-400 text-xs hover:text-dark-200 transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setClearConfirm(true)}
                    className="text-xs text-dark-600 hover:text-red-400 transition-colors flex items-center gap-1"
                  >
                    <Trash2 className="w-3 h-3" />
                    Clear entire {activeList} ({currentList.length} domains)
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─── Scanner Logs Section ───────────────────────────────────── */}
      <div className="bg-dark-800/50 rounded-2xl border border-dark-700/50 overflow-hidden">
        <button
          onClick={() => setLogsOpen(!logsOpen)}
          className="w-full flex items-center justify-between px-6 py-4 hover:bg-dark-700/30 transition-colors"
        >
          <div className="flex items-center gap-3">
            <Terminal className="w-5 h-5 text-emerald-400" />
            <div className="text-left">
              <h3 className="text-sm font-semibold text-dark-200">Логи сканера</h3>
              <p className="text-xs text-dark-500 mt-0.5">Подробные логи сканирования, авторизации и краулера</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {logFiles.length > 0 && (
              <span className="text-[10px] text-dark-500">
                {logFiles.map(f => `${f.name}: ${f.size_human}`).join(" · ")}
              </span>
            )}
            <ChevronDown className={`w-4 h-4 text-dark-500 transition-transform ${logsOpen ? "rotate-180" : ""}`} />
          </div>
        </button>

        <AnimatePresence>
          {logsOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <div className="px-6 pb-5 space-y-4 border-t border-dark-700/50 pt-4">
                {/* Controls */}
                <div className="flex flex-wrap items-center gap-3">
                  {/* Log file selector */}
                  <div className="flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-dark-500" />
                    <select
                      value={logFile}
                      onChange={(e) => setLogFile(e.target.value)}
                      className="bg-dark-700/50 border border-dark-600/50 rounded-lg px-2 py-1 text-xs text-dark-200 focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
                    >
                      <option value="scanner">scanner.log (всё)</option>
                      <option value="auth">auth.log (авторизация)</option>
                      <option value="scan">scan.log (сканирование)</option>
                      <option value="error">error.log (ошибки)</option>
                    </select>
                  </div>

                  {/* Level filter */}
                  <div className="flex items-center gap-1.5">
                    <Filter className="w-3.5 h-3.5 text-dark-500" />
                    <select
                      value={logLevel}
                      onChange={(e) => setLogLevel(e.target.value)}
                      className="bg-dark-700/50 border border-dark-600/50 rounded-lg px-2 py-1 text-xs text-dark-200 focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
                    >
                      <option value="">Все уровни</option>
                      <option value="DEBUG">DEBUG</option>
                      <option value="INFO">INFO</option>
                      <option value="WARNING">WARNING</option>
                      <option value="ERROR">ERROR</option>
                    </select>
                  </div>

                  {/* Lines count */}
                  <select
                    value={logLines}
                    onChange={(e) => setLogLines(Number(e.target.value))}
                    className="bg-dark-700/50 border border-dark-600/50 rounded-lg px-2 py-1 text-xs text-dark-200 focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
                  >
                    <option value={100}>100 строк</option>
                    <option value={300}>300 строк</option>
                    <option value={500}>500 строк</option>
                    <option value={1000}>1000 строк</option>
                    <option value={2000}>2000 строк</option>
                  </select>

                  {/* Auto-refresh toggle */}
                  <button
                    onClick={() => setLogAutoRefresh(!logAutoRefresh)}
                    className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs transition-colors ${
                      logAutoRefresh
                        ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                        : "bg-dark-700/50 text-dark-400 border border-dark-600/50 hover:text-dark-200"
                    }`}
                  >
                    <RefreshCw className={`w-3 h-3 ${logAutoRefresh ? "animate-spin" : ""}`} />
                    Авто
                  </button>

                  {/* Refresh button */}
                  <button
                    onClick={loadLogs}
                    disabled={logLoading}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-dark-700/50 text-dark-400 text-xs border border-dark-600/50 hover:text-dark-200 transition-colors disabled:opacity-50"
                  >
                    {logLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                    Обновить
                  </button>

                  {/* Clear button */}
                  <button
                    onClick={() => clearLog(logFile)}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-dark-500 text-xs hover:text-red-400 transition-colors"
                  >
                    <Trash2 className="w-3 h-3" />
                    Очистить
                  </button>

                  <span className="text-[10px] text-dark-600 ml-auto">
                    {logEntries.length} записей
                  </span>
                </div>

                {/* Log content */}
                <div className="bg-dark-900/80 rounded-xl border border-dark-700/50 max-h-[500px] overflow-y-auto font-mono text-[11px] leading-relaxed">
                  {logEntries.length === 0 ? (
                    <div className="text-center py-8 text-dark-600">
                      {logLoading ? (
                        <Loader2 className="w-5 h-5 mx-auto animate-spin" />
                      ) : (
                        <p>Логи пусты</p>
                      )}
                    </div>
                  ) : (
                    <div className="divide-y divide-dark-800/50">
                      {logEntries.map((entry, i) => (
                        <div
                          key={i}
                          className={`px-3 py-1 flex items-start gap-2 hover:bg-dark-800/30 ${
                            entry.level === "ERROR" || entry.level === "CRITICAL"
                              ? "bg-red-500/5"
                              : entry.level === "WARNING"
                              ? "bg-yellow-500/5"
                              : ""
                          }`}
                        >
                          {entry.timestamp && (
                            <span className="text-dark-600 flex-shrink-0 select-none">
                              {entry.timestamp.split(" ")[1] || entry.timestamp}
                            </span>
                          )}
                          {entry.level && (
                            <span
                              className={`flex-shrink-0 w-12 text-center rounded px-0.5 ${
                                entry.level === "ERROR"
                                  ? "text-red-400 bg-red-500/10"
                                  : entry.level === "WARNING"
                                  ? "text-yellow-400 bg-yellow-500/10"
                                  : entry.level === "DEBUG"
                                  ? "text-dark-500"
                                  : "text-emerald-400"
                              }`}
                            >
                              {entry.level}
                            </span>
                          )}
                          {entry.module && (
                            <span className="text-purple-400/60 flex-shrink-0 max-w-[180px] truncate">
                              {entry.module}
                            </span>
                          )}
                          <span className="text-dark-300 break-all">
                            {entry.message || entry.raw}
                          </span>
                        </div>
                      ))}
                      <div ref={logEndRef} />
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
