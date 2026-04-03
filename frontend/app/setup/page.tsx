// frontend/app/setup/page.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch } from "@/lib/api";
import { subscribeSSE } from "@/lib/sse";

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
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [domain, setDomain] = useState("");
  const [institutionName, setInstitutionName] = useState("");
  const [statusMessages, setStatusMessages] = useState<string[]>([]);
  const [institutions, setInstitutions] = useState<DiscoveredInstitution[]>([]);
  const [emailDomains, setEmailDomains] = useState<DiscoveredDomain[]>([]);
  const [discovering, setDiscovering] = useState(false);
  const [saving, setSaving] = useState(false);

  function startDiscovery() {
    if (!domain.trim()) return;
    setDiscovering(true);
    setStatusMessages([]);
    setStep(2);

    subscribeSSE(
      "/api/institution/discover",
      { domain: domain.trim() },
      (event) => {
        if (event.type === "status") {
          setStatusMessages((prev) => [...prev, event.message as string]);
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
              (d) => ({ ...d, selected: true })
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
        }),
      });
      router.push("/");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <h2 className="text-2xl font-semibold mb-2">Institution Setup</h2>
      <p className="text-gray-400 mb-6">
        Configure your institution by entering your email domain. We will discover
        your institutional profile from PubMed automatically.
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
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-500"
              }`}
            >
              {s.n < step ? "\u2713" : s.n}
            </div>
            <span
              className={`text-xs ${
                s.n <= step ? "text-gray-300" : "text-gray-600"
              }`}
            >
              {s.label}
            </span>
            {s.n < 3 && (
              <div
                className={`flex-1 h-0.5 ${
                  s.n < step ? "bg-green-600" : "bg-gray-800"
                }`}
              />
            )}
          </div>
        ))}
      </div>

      {/* Step 1: Enter domain */}
      {step === 1 && (
        <Card className="border-gray-800">
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
            <Button onClick={startDiscovery} disabled={!domain.trim()}>
              Discover
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Discovery progress */}
      {step === 2 && (
        <Card className="border-gray-800">
          <CardContent className="p-6">
            <div className="space-y-2">
              {statusMessages.map((msg, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <span className={i === statusMessages.length - 1 && discovering ? "text-blue-400" : "text-green-500"}>
                    {i === statusMessages.length - 1 && discovering ? "\u25CB" : "\u2713"}
                  </span>
                  <span className="text-gray-300">{msg}</span>
                </div>
              ))}
              {discovering && (
                <p className="text-gray-500 text-sm mt-4">Analyzing affiliations...</p>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 3: Classify institutions */}
      {step === 3 && (
        <div className="space-y-6">
          <Card className="border-gray-800">
            <CardContent className="p-6">
              <h3 className="text-sm font-medium text-gray-300 mb-4">
                Classify discovered institutions
              </h3>
              <div className="space-y-3">
                {institutions.map((inst, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-3 rounded bg-gray-900 border border-gray-800"
                  >
                    <div>
                      <p className="text-sm text-gray-200">{inst.name}</p>
                      <p className="text-xs text-gray-500">
                        {inst.count} mentions
                      </p>
                    </div>
                    <div className="flex gap-1">
                      {(["home", "collaborating", "skip"] as const).map((cls) => (
                        <button
                          key={cls}
                          onClick={() => {
                            const updated = [...institutions];
                            updated[i] = { ...updated[i], classification: cls };
                            setInstitutions(updated);
                          }}
                          className={`px-3 py-1 text-xs rounded ${
                            inst.classification === cls
                              ? cls === "home"
                                ? "bg-green-900 text-green-300"
                                : cls === "collaborating"
                                ? "bg-blue-900 text-blue-300"
                                : "bg-gray-700 text-gray-400"
                              : "bg-gray-800 text-gray-500 hover:bg-gray-700"
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

          <Card className="border-gray-800">
            <CardContent className="p-6">
              <h3 className="text-sm font-medium text-gray-300 mb-4">
                Email domains
              </h3>
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
                      className="rounded border-gray-600"
                    />
                    <span className="text-gray-300">@{d.domain}</span>
                    <span className="text-gray-600 text-xs">
                      ({d.count} occurrences)
                    </span>
                  </label>
                ))}
              </div>
            </CardContent>
          </Card>

          <Button onClick={saveConfig} disabled={saving}>
            {saving ? "Saving..." : "Save Configuration"}
          </Button>
        </div>
      )}
    </div>
  );
}
