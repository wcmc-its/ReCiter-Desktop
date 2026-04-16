// frontend/app/setup/page.tsx
"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch } from "@/lib/api";
import { subscribeSSE } from "@/lib/sse";
import { useWorkflow } from "@/lib/workflow";

interface InstitutionConfig {
  institution_label: string;
  email_suffixes: string[];
  home_institution_keywords: string[];
  home_institution_names?: string[];
  collaborating_institution_keywords: string[];
  collaborating_institution_names?: string[];
  pubmed_api_key?: string;
}

interface DiscoveredInstitution {
  name: string;
  count: number;
  keywords: string;
  classification: "home" | "collaborating" | "skip";
}

interface DiscoveredDomain {
  domain: string;
  count: number;
  selected: boolean;
}

export default function SetupPage() {
  const { institution, refresh } = useWorkflow();
  const [config, setConfig] = useState<InstitutionConfig | null>(null);
  const [editing, setEditing] = useState(false);
  const [step, setStep] = useState(1);
  const [domain, setDomain] = useState("");
  const [institutionName, setInstitutionName] = useState("");
  const [statusMessages, setStatusMessages] = useState<string[]>([]);
  const [affiliationCount, setAffiliationCount] = useState(0);
  const [institutions, setInstitutions] = useState<DiscoveredInstitution[]>([]);
  const [emailDomains, setEmailDomains] = useState<DiscoveredDomain[]>([]);
  const [discovering, setDiscovering] = useState(false);
  const [saving, setSaving] = useState(false);
  const [hideMinor, setHideMinor] = useState(true);
  const [pubmedApiKey, setPubmedApiKey] = useState("");
  const [editingApiKey, setEditingApiKey] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [savingApiKey, setSavingApiKey] = useState(false);

  useEffect(() => {
    if (institution && !editing) {
      apiFetch<InstitutionConfig>("/api/institution").then(setConfig);
    }
  }, [institution, editing]);

  function startDiscovery() {
    if (!domain.trim()) return;
    setDiscovering(true);
    setStatusMessages([]);
    setAffiliationCount(0);
    setStep(2);

    subscribeSSE(
      "/api/institution/discover",
      { domain: domain.trim() },
      (event) => {
        if (event.type === "status") {
          setStatusMessages((prev) => [...prev, event.message as string]);
        } else if (event.type === "affiliation_count") {
          setAffiliationCount(event.count as number);
        } else if (event.type === "complete") {
          const insts = (event.institutions as Array<{
            name: string;
            count: number;
            keywords: string;
          }>).map((inst, i) => ({
            ...inst,
            classification: (i < 2 ? "home" : "collaborating") as "home" | "collaborating" | "skip",
          }));
          setInstitutions(insts);
          setEmailDomains(
            (event.email_domains as Array<{ domain: string; count: number }>).map(
              (d, i) => ({ ...d, selected: i === 0 })
            )
          );
          if (!institutionName && insts.length > 0) {
            setInstitutionName(insts[0].name);
          }
          setDiscovering(false);
          setStep(3);
        }
      },
      () => setDiscovering(false)
    );
  }

  async function resetConfig() {
    const confirmed = window.confirm(
      "Reset institution configuration?\n\nThis will clear all scores and retrieval history. Researchers and curations are preserved.\n\nYou will need to re-run retrieval and scoring after reconfiguring."
    );
    if (!confirmed) return;
    await apiFetch("/api/institution", { method: "DELETE" });
    setStep(1);
    setDomain("");
    setInstitutionName("");
    setInstitutions([]);
    setEmailDomains([]);
    setStatusMessages([]);
    setAffiliationCount(0);
  }

  async function saveConfig() {
    setSaving(true);
    try {
      await apiFetch("/api/institution/configure", {
        method: "POST",
        body: JSON.stringify({
          institutions: institutions
            .filter((i) => i.classification !== "skip")
            .map((i) => ({
              name: i.name,
              classification: i.classification,
              keywords: i.keywords,
            })),
          email_domains: emailDomains
            .filter((d) => d.selected)
            .map((d) => d.domain),
          institution_label: institutionName,
          pubmed_api_key: pubmedApiKey || undefined,
        }),
      });
      refresh();
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  // Summary view when institution is configured
  if (institution && config && !editing) {
    const formatName = (k: string) =>
      k.split("|").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");

    return (
      <div className="max-w-2xl">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-semibold text-gray-900">Institution Setup</h2>
            <p className="text-gray-500 mt-1">Configuration complete</p>
          </div>
          <Button variant="outline" onClick={() => {
            setEditing(true);
            setStep(1);
            setDomain("");
            setInstitutionName("");
            setInstitutions([]);
            setEmailDomains([]);
            setStatusMessages([]);
            setAffiliationCount(0);
          }}>
            Reconfigure
          </Button>
        </div>

        <div className="space-y-4">
          <Card className="border-gray-200 shadow-sm">
            <CardContent className="p-5">
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Institution</p>
              <p className="text-lg font-medium text-gray-900">{config.institution_label}</p>
            </CardContent>
          </Card>

          <Card className="border-gray-200 shadow-sm">
            <CardContent className="p-5">
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Email Domains</p>
              <div className="flex flex-wrap gap-2">
                {config.email_suffixes.map((s) => (
                  <span key={s} className="inline-block px-2.5 py-1 rounded-full bg-blue-50 border border-blue-200 text-blue-700 text-sm">
                    {s}
                  </span>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card className="border-gray-200 shadow-sm">
            <CardContent className="p-5">
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Home Institutions</p>
              <div className="flex flex-wrap gap-2">
                {(config.home_institution_names ?? config.home_institution_keywords).map((k, i) => (
                  <span key={i} className="inline-block px-2.5 py-1 rounded-full bg-green-50 border border-green-200 text-green-700 text-sm">
                    {config.home_institution_names ? k : formatName(k)}
                  </span>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card className="border-gray-200 shadow-sm">
            <CardContent className="p-5">
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">
                Collaborating Institutions
                <span className="normal-case text-gray-400 ml-1">
                  ({config.collaborating_institution_keywords.length} total)
                </span>
              </p>
              <div className="flex flex-wrap gap-2">
                {(config.collaborating_institution_names ?? config.collaborating_institution_keywords).map((k, i) => (
                  <span key={i} className="inline-block px-2.5 py-1 rounded-full bg-gray-100 border border-gray-200 text-gray-600 text-sm">
                    {config.collaborating_institution_names ? k : formatName(k)}
                  </span>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card className="border-gray-200 shadow-sm">
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs text-gray-500 uppercase tracking-wider">PubMed API Key</p>
                {!editingApiKey && (
                  <button
                    onClick={() => { setEditingApiKey(true); setApiKeyInput(config.pubmed_api_key || ""); }}
                    className="text-xs text-blue-600 hover:underline"
                  >
                    {config.pubmed_api_key ? "Change" : "Add key"}
                  </button>
                )}
              </div>
              {editingApiKey ? (
                <div className="flex gap-2 items-center mt-1">
                  <Input
                    value={apiKeyInput}
                    onChange={(e) => setApiKeyInput(e.target.value)}
                    placeholder="Paste your NCBI API key"
                    className="font-mono text-sm flex-1"
                    autoFocus
                  />
                  <Button
                    size="sm"
                    className="bg-[#cf4520] hover:bg-[#a3381a] text-white"
                    disabled={savingApiKey}
                    onClick={async () => {
                      setSavingApiKey(true);
                      try {
                        await apiFetch("/api/institution/api-key", {
                          method: "PUT",
                          body: JSON.stringify({ pubmed_api_key: apiKeyInput }),
                        });
                        setConfig({ ...config, pubmed_api_key: apiKeyInput });
                        setEditingApiKey(false);
                      } finally {
                        setSavingApiKey(false);
                      }
                    }}
                  >
                    {savingApiKey ? "Saving..." : "Save"}
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => setEditingApiKey(false)}>
                    Cancel
                  </Button>
                </div>
              ) : config.pubmed_api_key ? (
                <p className="text-sm text-gray-700 font-mono">
                  {config.pubmed_api_key.slice(0, 8)}{"•".repeat(8)}
                  <span className="text-green-600 text-xs ml-2">Configured (10 req/sec)</span>
                </p>
              ) : (
                <p className="text-sm text-gray-400">
                  Not set — using default rate limit (3 req/sec).{" "}
                  <a
                    href="https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline"
                  >
                    Get a free key from NCBI
                  </a>
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-2xl font-semibold text-gray-900">Institution Setup</h2>
        {editing && (
          <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>
            ← Back to summary
          </Button>
        )}
      </div>
      <p className="text-gray-500 mb-6">
        Institution signals — email domains and affiliation keywords — are among the
        strongest evidence ReCiter uses to link publications to researchers. This
        one-time setup helps ReCiter recognize your institution in PubMed data,
        improving scores for <strong className="font-medium text-gray-700">both current publications</strong> and{" "}
        <strong className="font-medium text-gray-700">historical ones published before a researcher joined your institution</strong>.
        Enter your email domain below and we will discover your institutional profile
        from PubMed automatically.
      </p>

      {/* Step indicator */}
      <div className="flex gap-4 mb-8">
        {[
          { n: 1, label: "Enter Domain" },
          { n: 2, label: "Discover" },
          { n: 3, label: "Classify" },
        ].map((s) => (
          <div key={s.n} className="flex items-center gap-2 flex-1">
            <div
              className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
                s.n < step
                  ? "bg-green-600 text-white"
                  : s.n === step
                  ? "bg-[#cf4520] text-white"
                  : "bg-gray-200 text-gray-500"
              }`}
            >
              {s.n < step ? "\u2713" : s.n}
            </div>
            <span
              className={`text-xs ${
                s.n <= step ? "text-gray-700" : "text-gray-400"
              }`}
            >
              {s.label}
            </span>
            {s.n < 3 && (
              <div className="flex-1 h-0.5 bg-gray-200 overflow-hidden">
                <div
                  className={`h-full bg-green-600 transition-all duration-500 ease-out ${
                    s.n < step ? "w-full" : "w-0"
                  }`}
                />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Step 1: Enter domain */}
      {step === 1 && (
        <Card className="border-gray-200 shadow-sm animate-step-enter">
          <CardContent className="p-6 space-y-4">
            <div>
              <Label htmlFor="domain">Institution email domain</Label>
              <Input
                id="domain"
                placeholder="e.g., fredhutch.org"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                className="mt-1"
              />
            </div>
            <div>
              <Label htmlFor="name">Institution name (optional)</Label>
              <Input
                id="name"
                placeholder="e.g., Fred Hutchinson Cancer Center"
                value={institutionName}
                onChange={(e) => setInstitutionName(e.target.value)}
                className="mt-1"
              />
            </div>
            <div>
              <Label htmlFor="apikey">PubMed API key (optional)</Label>
              <Input
                id="apikey"
                placeholder="e.g., a1b2c3d4e5f6..."
                value={pubmedApiKey}
                onChange={(e) => setPubmedApiKey(e.target.value)}
                className="mt-1 font-mono text-sm"
              />
              <p className="text-xs text-gray-400 mt-1">
                Increases PubMed rate limit from 3 to 10 requests/sec.{" "}
                <a
                  href="https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline"
                >
                  Get a free key from NCBI
                </a>
              </p>
            </div>
            <Button
              onClick={startDiscovery}
              disabled={!domain.trim()}
              className={domain.trim()
                ? "bg-[#cf4520] hover:bg-[#a3381a] text-white"
                : "bg-gray-200 text-gray-400 disabled:opacity-100 disabled:bg-gray-200"}
            >
              Discover
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Discovery progress */}
      {step === 2 && (
        <Card className="border-gray-200 shadow-sm animate-step-enter">
          <CardContent className="p-6">
            <div className="space-y-2">
              {statusMessages.map((msg, i) => {
                const isActive = i === statusMessages.length - 1 && discovering;
                return (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    {isActive ? (
                      <span className="inline-block w-3 h-3 border-2 border-[#cf4520] border-t-transparent rounded-full animate-spin flex-shrink-0" />
                    ) : (
                      <span className="text-green-600 flex-shrink-0">&#10003;</span>
                    )}
                    <span className="text-gray-700">
                      {msg}
                      {isActive && affiliationCount > 0 && (
                        <span className="ml-2 font-mono font-semibold text-[#cf4520]">
                          {affiliationCount.toLocaleString()}x
                        </span>
                      )}
                    </span>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 3: Classify institutions */}
      {step === 3 && (
        <div className="space-y-6 animate-step-enter">
          <Card className="border-gray-200 shadow-sm">
            <CardContent className="px-6 pt-3 pb-6">
              <h3 className="text-sm font-medium text-gray-700 mb-0.5">
                Classify discovered institutions
              </h3>
              {affiliationCount > 0 && (
                <p className="text-xs text-gray-400 mb-2">
                  Sampled from {affiliationCount.toLocaleString()} author affiliations on PubMed
                </p>
              )}
              <div className="flex items-center gap-2 mb-3">
                <input
                  type="checkbox"
                  checked={hideMinor}
                  onChange={() => setHideMinor(!hideMinor)}
                  className="rounded border-gray-300"
                />
                <span className="text-xs text-gray-500">
                  Hide institutions with fewer than 5 mentions
                  <span className="ml-1.5 text-gray-400">
                    ({institutions.filter((i) => !hideMinor || i.count >= 5).length} of {institutions.length} shown)
                  </span>
                </span>
              </div>
              <div className="space-y-3">
                {institutions.filter((inst) => !hideMinor || inst.count >= 5).map((inst) => (
                  <div
                    key={inst.name}
                    className="flex items-center justify-between p-3 rounded bg-gray-50 border border-gray-200"
                  >
                    <div>
                      <p className="text-sm text-gray-900">{inst.name}</p>
                      <div className="relative group inline-flex items-center">
                        <span className="text-xs text-gray-400 cursor-help">
                          {inst.count.toLocaleString()}x
                        </span>
                        <div className="absolute bottom-full left-0 mb-1 px-2 py-1 bg-gray-800 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                          Found in {inst.count.toLocaleString()} author affiliations across sampled PubMed articles
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-1">
                      {(["home", "collaborating", "skip"] as const).map((cls) => (
                        <button
                          key={cls}
                          onClick={() => {
                            const updated = institutions.map((item) =>
                              item.name === inst.name ? { ...item, classification: cls } : item
                            );
                            setInstitutions(updated);
                          }}
                          className={`px-3 py-1 text-xs rounded ${
                            inst.classification === cls
                              ? cls === "home"
                                ? "bg-green-100 text-green-700 border border-green-300"
                                : cls === "collaborating"
                                ? "bg-blue-100 text-blue-700 border border-blue-300"
                                : "bg-gray-200 text-gray-600 border border-gray-300"
                              : "bg-white text-gray-500 border border-gray-200 hover:bg-gray-50"
                          }`}
                        >
                          {cls === "home"
                            ? "Home"
                            : cls === "collaborating"
                            ? "Collaborating"
                            : "Skip"}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card className="border-gray-200 shadow-sm">
            <CardContent className="px-6 pt-3 pb-6">
              <h3 className="text-sm font-medium text-gray-700 mb-1">
                Home institution email domains
              </h3>
              <p className="text-xs text-gray-500 mb-4">
                These domains identify emails belonging to your institution&apos;s authors.
                Used to match researcher identities during scoring.
                Counts reflect authorships found across up to 4,000 recent PubMed articles.
              </p>
              <div className="space-y-2">
                {emailDomains.map((d, i) => (
                  <label
                    key={i}
                    className="flex items-center gap-3 text-sm cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={d.selected}
                      onChange={() => {
                        const updated = [...emailDomains];
                        updated[i] = { ...updated[i], selected: !d.selected };
                        setEmailDomains(updated);
                      }}
                      className="rounded border-gray-300"
                    />
                    <span className="text-gray-700">@{d.domain}</span>
                    <span className="text-gray-400 text-xs">
                      ({d.count} authorships)
                    </span>
                  </label>
                ))}
              </div>
            </CardContent>
          </Card>

          <div className="flex items-center justify-between">
            <Button
              onClick={saveConfig}
              disabled={saving}
              className="bg-[#cf4520] hover:bg-[#a3381a] text-white"
            >
              {saving ? "Saving..." : "Save Configuration"}
            </Button>
            <button
              onClick={resetConfig}
              className="text-xs text-gray-400 hover:text-red-600 underline"
            >
              Reset configuration
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
