// frontend/app/stats/page.tsx
"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { PrerequisiteGate } from "@/components/prerequisite-gate";
import { useWorkflow } from "@/lib/workflow";
import { apiFetch } from "@/lib/api";
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Legend,
  Cell,
} from "recharts";

interface StatsData {
  viable: boolean;
  below_n_threshold?: boolean;
  error?: string;
  message?: string;
  n?: number;
  roc?: {
    fpr: number[];
    tpr: number[];
    auc: number;
    ci_lower: number;
    ci_upper: number;
    ci_degraded: boolean;
  };
  calibration?: Array<{
    bucket: string;
    mean_score: number | null;
    fraction_positive: number | null;
    n: number;
  }>;
  calibration_viable?: boolean;
  pr?: {
    precision: number[];
    recall: number[];
    auc_pr: number;
    pr_baseline: number;
  };
  distribution?: Array<{
    bucket: string;
    accepted: number;
    rejected: number;
  }>;
  disagreements?: Array<{
    person_id: string;
    pmid: string;
    score: number;
    assertion: string;
    disagreement: number;
    first_name: string | null;
    last_name: string | null;
  }>;
}

const WEILL_RED = "#cf4520";
const CHART_BLUE = "#3b82f6";
const CHART_GREEN = "#22c55e";
const CHART_RED = "#ef4444";

function InfoTip({ text }: { text: string }) {
  const [show, setShow] = useState(false);
  const [style, setStyle] = useState<React.CSSProperties>({});
  const ref = useRef<HTMLSpanElement>(null);

  function handleEnter() {
    if (ref.current) {
      const rect = ref.current.getBoundingClientRect();
      const tipWidth = 288; // w-72
      const margin = 16;
      let left = rect.left + rect.width / 2 - tipWidth / 2;
      // Clamp to viewport
      if (left < margin) left = margin;
      if (left + tipWidth > window.innerWidth - margin) left = window.innerWidth - margin - tipWidth;
      setStyle({ top: rect.bottom + 8, left });
    }
    setShow(true);
  }

  return (
    <>
      <span
        ref={ref}
        onMouseEnter={handleEnter}
        onMouseLeave={() => setShow(false)}
        className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-gray-200 text-gray-500 hover:bg-gray-700 hover:text-white transition-colors text-[10px] leading-none cursor-help ml-1.5 align-middle"
        aria-label="More info"
      >
        ?
      </span>
      {show && (
        <div
          className="fixed z-[9999] w-72 rounded-lg bg-gray-900 text-white shadow-2xl p-3 text-xs font-normal normal-case tracking-normal leading-relaxed pointer-events-none"
          style={style}
        >
          {text}
        </div>
      )}
    </>
  );
}

function MetricCard({ label, value, sub, info }: { label: string; value: string; sub?: string; info?: string }) {
  return (
    <Card className="border-gray-200 bg-white shadow-sm">
      <CardContent className="p-4">
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
          {label}
          {info && <InfoTip text={info} />}
        </p>
        <p className="text-2xl font-semibold text-gray-900">{value}</p>
        {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
      </CardContent>
    </Card>
  );
}

export default function StatsPage() {
  const { assertionCount } = useWorkflow();
  const [stats, setStats] = useState<StatsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (assertionCount > 0) {
      apiFetch<StatsData>("/api/stats")
        .then(setStats)
        .finally(() => setLoading(false));
    }
  }, [assertionCount]);

  return (
    <PrerequisiteGate
      met={assertionCount > 0}
      message="Statistics require scored articles with accepted or rejected decisions. Retrieve and score articles first, then import assertions."
      actionLabel="Go to Retrieve & Score"
      actionHref="/pipeline"
    >
      <div className="max-w-5xl">
        <h2 className="text-2xl font-semibold mb-2 text-gray-900">Statistics</h2>
        <p className="text-gray-500 text-sm mb-6">
          Scoring quality metrics based on curated assertions.
        </p>

        {loading && <p className="text-sm text-gray-400">Computing statistics...</p>}

        {stats && !stats.viable && (
          <Card className="border-amber-300 bg-amber-50 shadow-sm">
            <CardContent className="p-5">
              <p className="text-amber-800 font-medium">Cannot compute statistics</p>
              <p className="text-amber-700 text-sm mt-1">{stats.message}</p>
            </CardContent>
          </Card>
        )}

        {stats && stats.viable && (
          <div className="space-y-8">
            {/* Summary cards */}
            <div className="grid grid-cols-4 gap-4">
              <MetricCard
                label="Score-Assertion Pairs"
                value={stats.n!.toLocaleString()}
                info="The number of articles where we have both a model score and a human accept/reject decision. More pairs means more reliable statistics."
              />
              <MetricCard
                label="AUC-ROC"
                value={stats.roc!.auc.toFixed(3)}
                sub={`95% CI: ${stats.roc!.ci_lower.toFixed(3)} – ${stats.roc!.ci_upper.toFixed(3)}`}
                info="Measures how well the model separates accepted from rejected articles. 1.0 is perfect, 0.5 is random guessing. Values above 0.99 indicate excellent discrimination."
              />
              <MetricCard
                label="AUC-PR"
                value={stats.pr!.auc_pr.toFixed(3)}
                sub={`Baseline: ${(stats.pr!.pr_baseline * 100).toFixed(1)}%`}
                info="Measures accuracy when the model predicts an article belongs to a researcher. More informative than AUC-ROC when most candidate articles are rejected."
              />
              <MetricCard
                label="Prevalence"
                value={`${(stats.pr!.pr_baseline * 100).toFixed(1)}%`}
                sub="Fraction accepted"
                info="The fraction of scored articles that curators accepted. This is the base rate: if you accepted everything blindly, you would be right this percentage of the time."
              />
            </div>

            {stats.below_n_threshold && (
              <div className="bg-amber-50 border border-amber-300 rounded-lg px-4 py-3 text-sm text-amber-800">
                Fewer than 50 score–assertion pairs. Statistics may be unreliable.
              </div>
            )}

            {/* Charts row 1: ROC + Score Distribution */}
            <div className="grid grid-cols-2 gap-6">
              <Card className="border-gray-200 bg-white shadow-sm">
                <CardContent className="p-5">
                  <p className="text-sm font-medium text-gray-700 mb-4">
                    ROC Curve
                    <InfoTip text="Shows the tradeoff between catching real matches (True Positive Rate, y-axis) and accidentally including wrong ones (False Positive Rate, x-axis). The curve should hug the top-left corner. The dashed diagonal represents random guessing." />
                  </p>
                  <ResponsiveContainer width="100%" height={280}>
                    <LineChart
                      data={stats.roc!.fpr.map((f, i) => ({
                        fpr: f,
                        tpr: stats.roc!.tpr[i],
                      }))}
                      margin={{ top: 5, right: 20, bottom: 20, left: 10 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis
                        dataKey="fpr"
                        type="number"
                        domain={[0, 1]}
                        tickFormatter={(v: number) => v.toFixed(1)}
                        label={{ value: "False Positive Rate", position: "insideBottom", offset: -10, style: { fontSize: 11, fill: "#6b7280" } }}
                        tick={{ fontSize: 11 }}
                      />
                      <YAxis
                        domain={[0, 1]}
                        tickFormatter={(v: number) => v.toFixed(1)}
                        label={{ value: "True Positive Rate", angle: -90, position: "insideLeft", offset: 5, style: { fontSize: 11, fill: "#6b7280" } }}
                        tick={{ fontSize: 11 }}
                      />
                      <ReferenceLine
                        segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]}
                        stroke="#d1d5db"
                        strokeDasharray="4 4"
                      />
                      <Tooltip
                        formatter={(v) => typeof v === 'number' ? v.toFixed(3) : String(v)}
                        labelFormatter={(l) => `FPR: ${typeof l === 'number' ? l.toFixed(3) : l}`}
                        contentStyle={{ fontSize: 12 }}
                      />
                      <Line
                        type="monotone"
                        dataKey="tpr"
                        stroke={WEILL_RED}
                        strokeWidth={2}
                        dot={false}
                        name="TPR"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                  <p className="text-xs text-gray-400 text-center mt-1">
                    AUC = {stats.roc!.auc.toFixed(3)} ({stats.roc!.ci_lower.toFixed(3)} – {stats.roc!.ci_upper.toFixed(3)})
                  </p>
                </CardContent>
              </Card>

              <Card className="border-gray-200 bg-white shadow-sm">
                <CardContent className="p-5">
                  <p className="text-sm font-medium text-gray-700 mb-4">
                    Score Distribution
                    <InfoTip text="Shows how many accepted (green) and rejected (red) articles fall in each score range. A good model separates them clearly: accepted articles cluster at high scores, rejected articles at low scores." />
                  </p>
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart
                      data={stats.distribution}
                      margin={{ top: 5, right: 20, bottom: 20, left: 10 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis
                        dataKey="bucket"
                        tick={{ fontSize: 10 }}
                        label={{ value: "Score Range", position: "insideBottom", offset: -10, style: { fontSize: 11, fill: "#6b7280" } }}
                      />
                      <YAxis
                        tick={{ fontSize: 11 }}
                        label={{ value: "Count", angle: -90, position: "insideLeft", offset: 5, style: { fontSize: 11, fill: "#6b7280" } }}
                      />
                      <Tooltip contentStyle={{ fontSize: 12 }} />
                      <Legend verticalAlign="top" height={28} wrapperStyle={{ fontSize: 12 }} />
                      <Bar dataKey="accepted" stackId="a" fill={CHART_GREEN} name="Accepted" />
                      <Bar dataKey="rejected" stackId="a" fill={CHART_RED} name="Rejected" radius={[2, 2, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </div>

            {/* Charts row 2: Calibration + Precision-Recall */}
            <div className="grid grid-cols-2 gap-6">
              <Card className="border-gray-200 bg-white shadow-sm">
                <CardContent className="p-5">
                  <p className="text-sm font-medium text-gray-700 mb-4">
                    Calibration (Reliability Diagram)
                    <InfoTip text="Tests whether scores match reality. If the model says 80% confidence, about 80% of those articles should actually be accepted. Bars close to the dashed diagonal line indicate good calibration." />
                  </p>
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart
                      data={stats.calibration!.map((b) => ({
                        bucket: b.bucket,
                        fractionPositive: b.fraction_positive != null ? +(b.fraction_positive * 100).toFixed(1) : 0,
                        n: b.n,
                      }))}
                      margin={{ top: 5, right: 20, bottom: 20, left: 10 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis
                        dataKey="bucket"
                        tick={{ fontSize: 10 }}
                        label={{ value: "Score Bin", position: "insideBottom", offset: -10, style: { fontSize: 11, fill: "#6b7280" } }}
                      />
                      <YAxis
                        domain={[0, 100]}
                        tickFormatter={(v: number) => `${v}%`}
                        tick={{ fontSize: 11 }}
                        label={{ value: "% Accepted", angle: -90, position: "insideLeft", offset: 5, style: { fontSize: 11, fill: "#6b7280" } }}
                      />
                      <ReferenceLine
                        segment={[{ x: "0-10", y: 5 }, { x: "90-100", y: 95 }]}
                        stroke="#d1d5db"
                        strokeDasharray="4 4"
                        label={{ value: "Perfect", position: "insideTopRight", style: { fontSize: 10, fill: "#9ca3af" } }}
                      />
                      <Tooltip
                        contentStyle={{ fontSize: 12 }}
                        formatter={(v, name) => {
                          if (name === "fractionPositive") return [`${v}%`, "% Accepted"];
                          return [v as number, String(name)];
                        }}
                      />
                      <Bar dataKey="fractionPositive" fill={CHART_BLUE} name="fractionPositive" radius={[2, 2, 0, 0]}>
                        {stats.calibration!.map((entry, i) => (
                          <Cell key={i} fill={entry.n === 0 ? "#e5e7eb" : CHART_BLUE} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                  {!stats.calibration_viable && (
                    <p className="text-xs text-amber-600 text-center mt-1">
                      Fewer than 50 pairs — calibration may be unreliable
                    </p>
                  )}
                </CardContent>
              </Card>

              <Card className="border-gray-200 bg-white shadow-sm">
                <CardContent className="p-5">
                  <p className="text-sm font-medium text-gray-700 mb-4">
                    Precision-Recall Curve
                    <InfoTip text="Precision is the fraction of predicted matches that are correct. Recall is the fraction of real matches the model finds. The curve shows how these trade off at different thresholds. Higher is better. The dashed line shows what you would get by accepting everything." />
                  </p>
                  <ResponsiveContainer width="100%" height={280}>
                    <LineChart
                      data={stats.pr!.recall.map((r, i) => ({
                        recall: r,
                        precision: stats.pr!.precision[i],
                      }))}
                      margin={{ top: 5, right: 20, bottom: 20, left: 10 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis
                        dataKey="recall"
                        type="number"
                        domain={[0, 1]}
                        tickFormatter={(v: number) => v.toFixed(1)}
                        label={{ value: "Recall", position: "insideBottom", offset: -10, style: { fontSize: 11, fill: "#6b7280" } }}
                        tick={{ fontSize: 11 }}
                      />
                      <YAxis
                        domain={[0, 1]}
                        tickFormatter={(v: number) => v.toFixed(1)}
                        label={{ value: "Precision", angle: -90, position: "insideLeft", offset: 5, style: { fontSize: 11, fill: "#6b7280" } }}
                        tick={{ fontSize: 11 }}
                      />
                      <ReferenceLine
                        y={stats.pr!.pr_baseline}
                        stroke="#d1d5db"
                        strokeDasharray="4 4"
                        label={{ value: "Baseline", position: "right", style: { fontSize: 10, fill: "#9ca3af" } }}
                      />
                      <Tooltip
                        formatter={(v) => typeof v === 'number' ? v.toFixed(3) : String(v)}
                        labelFormatter={(l) => `Recall: ${typeof l === 'number' ? l.toFixed(3) : l}`}
                        contentStyle={{ fontSize: 12 }}
                      />
                      <Line
                        type="monotone"
                        dataKey="precision"
                        stroke={WEILL_RED}
                        strokeWidth={2}
                        dot={false}
                        name="Precision"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                  <p className="text-xs text-gray-400 text-center mt-1">
                    AUC-PR = {stats.pr!.auc_pr.toFixed(3)} · Baseline = {(stats.pr!.pr_baseline * 100).toFixed(1)}%
                  </p>
                </CardContent>
              </Card>
            </div>

            {/* Disagreements table */}
            {stats.disagreements && stats.disagreements.length > 0 && (
              <Card className="border-gray-200 bg-white shadow-sm">
                <CardContent className="p-5">
                  <p className="text-sm font-medium text-gray-700 mb-4">
                    Top Disagreements
                    <InfoTip text="Articles where the model score most disagrees with the human decision. A high score on a rejected article, or a low score on an accepted one. These may indicate scoring errors or curation mistakes worth revisiting." />
                  </p>
                  <div className="border border-gray-200 rounded-lg overflow-hidden">
                    <div className="grid grid-cols-[1fr_120px_110px_100px_80px] gap-2 px-4 py-2 bg-gray-50 text-xs text-gray-500 uppercase tracking-wider">
                      <span>Researcher</span>
                      <span>PMID</span>
                      <span className="text-right">ReCiter Score (0–100)</span>
                      <span>Assertion</span>
                      <span className="text-right">Gap</span>
                    </div>
                    {stats.disagreements.map((d, i) => (
                      <div
                        key={i}
                        className="grid grid-cols-[1fr_120px_110px_100px_80px] gap-2 items-center px-4 py-2.5 border-t border-gray-100 text-sm"
                      >
                        <Link href={`/results/${d.person_id}`} className="text-gray-900 truncate hover:text-[#cf4520] transition-colors">
                          {d.last_name && d.first_name
                            ? `${d.last_name}, ${d.first_name}`
                            : d.person_id}
                        </Link>
                        <Link
                          href={`/results/${d.person_id}#pmid-${d.pmid}`}
                          className="text-[#cf4520] hover:underline font-mono text-xs"
                        >
                          {d.pmid}
                        </Link>
                        <span className="text-right font-mono text-gray-700">
                          {d.score.toFixed(1)}
                        </span>
                        <span>
                          <span
                            className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                              d.assertion === "ACCEPTED"
                                ? "bg-green-100 text-green-700"
                                : "bg-red-100 text-red-700"
                            }`}
                          >
                            {d.assertion.toLowerCase()}
                          </span>
                        </span>
                        <span className="text-right font-mono text-amber-600 text-xs">
                          {d.disagreement.toFixed(1)}
                        </span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </div>
    </PrerequisiteGate>
  );
}
