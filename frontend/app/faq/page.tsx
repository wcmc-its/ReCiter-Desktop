"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";

interface FAQItem {
  question: string;
  answer: string;
}

const FAQS: FAQItem[] = [
  {
    question: "What is ReCiter Desktop?",
    answer:
      "ReCiter Desktop is a standalone tool for author name disambiguation. It helps institutions identify which PubMed publications belong to their researchers by using machine learning to score each article-researcher match. It uses the same CARE (Comprehensive Author Recognition Engine) scoring models developed at Weill Cornell Medicine.",
  },
  {
    question: "How does the scoring work?",
    answer:
      "The system computes up to 25 evidence features for each article-researcher pair, including name matching, email matching, institutional affiliation, journal relevance, degree year, and more. These features are fed into a pre-trained XGBoost machine learning model, which outputs a confidence score from 0 to 100. Higher scores indicate a stronger match between the article and the researcher.",
  },
  {
    question: "What is the difference between 'Full Retrieval and Scoring' and 'Scoring Only'?",
    answer:
      "In Full Retrieval and Scoring mode, the system searches PubMed by researcher name to discover candidate publications, then scores them. This is useful when you want to find publications you may not already know about. In Scoring Only mode, you upload a list of known PMIDs and the system scores just those articles. Use this when you already have complete publication lists.",
  },
  {
    question: "What do I need to get started?",
    answer:
      "At minimum, you need: (1) Your institution's email domain (e.g., fredhutch.org) for the institution setup, and (2) A CSV or Excel file with your researchers — at minimum a unique ID, first name, and last name per row. Optional but helpful fields include email, department, title, doctoral year, and ORCID. A PubMed API key is recommended for faster retrieval (10 requests/second vs 3).",
  },
  {
    question: "What format should my researcher file be in?",
    answer:
      "CSV, Excel (.xlsx, .xls), or TSV. Column names are flexible — the system recognizes many common variations (e.g., 'emp_id' or 'cwid' for person ID, 'fname' for first name, 'phd_year' for doctoral year). After upload, you'll see a column mapping screen where you can confirm or adjust the detected mappings.",
  },
  {
    question: "What is the institution setup doing behind the scenes?",
    answer:
      "When you enter your email domain, the system searches PubMed for articles with that domain in the affiliation field. It then analyzes the affiliation strings to discover related email domains, institution name variants, and collaborating institutions. You classify each discovered institution as 'Home' (your institution) or 'Collaborating' (partner institutions). This information is used during scoring to determine how well an article's affiliations match your researchers.",
  },
  {
    question: "What is the difference between 'Home' and 'Collaborating' institutions?",
    answer:
      "Home institutions are your own organization and its close affiliates (e.g., your university and its medical school). Collaborating institutions are partner organizations where your researchers may have secondary appointments or co-author relationships. Both contribute to affiliation scoring, but home institution matches carry more weight.",
  },
  {
    question: "What does 'incremental retrieval' mean?",
    answer:
      "When you run the pipeline a second time for researchers who have already been scored, the system only searches for newly added publications since the last run. Previously scored articles and their scores are preserved. This makes subsequent runs much faster and avoids redundant PubMed queries.",
  },
  {
    question: "What score threshold should I use?",
    answer:
      "The default threshold of 70 works well for most institutions. Articles scoring above 70 are very likely to belong to the researcher. Articles between 30 and 70 may need manual review. Articles below 30 are unlikely matches. You can adjust the threshold on the Results page using the slider to see how it affects the count of articles above and below.",
  },
  {
    question: "Can I import existing accept/reject decisions?",
    answer:
      "Yes. If your researcher CSV includes 'pmid' and 'assertion' columns (with values like ACCEPTED or REJECTED), the system will detect this as curation data and offer to import it. When curation data is available, the system automatically uses a more powerful 43-feature scoring model instead of the 25-feature identity-only model.",
  },
  {
    question: "What is the 43-feature model vs the 25-feature model?",
    answer:
      "The 25-feature 'identity-only' model uses evidence from the researcher's identity (name, email, affiliation, etc.) to score articles. The 43-feature 'feedback + identity' model adds 12 additional features based on patterns in previously accepted and rejected articles — such as whether the journal, co-authors, keywords, or institutions match prior curations. The feedback model is significantly more accurate but requires curation data to activate.",
  },
  {
    question: "Do I need a PubMed API key?",
    answer:
      "It's recommended but not required. Without an API key, PubMed limits you to 3 requests per second. With a key, you get 10 requests per second — roughly 3x faster for large datasets. You can get a free API key from NCBI at https://www.ncbi.nlm.nih.gov/account/. Set it as the PUBMED_API_KEY environment variable when starting Docker Compose.",
  },
  {
    question: "How do I export my results?",
    answer:
      "Go to the Results page and click 'Export All Results (CSV)' for the full dataset, or navigate to an individual researcher and click 'Export CSV' for their articles only. The export includes person ID, name, PMID, article title, journal, year, score, and a PubMed link for each article.",
  },
  {
    question: "Can I run ReCiter Desktop without Docker?",
    answer:
      "Docker Compose is the recommended way to run ReCiter Desktop as it handles all dependencies automatically. For development, you can run the components separately: MariaDB on port 3306, the FastAPI backend on port 8090 (uvicorn api.main:app), and the Next.js frontend on port 3002 (npm run dev). You'll need Python 3.12+, Node.js 20+, and MariaDB 11+ installed.",
  },
  {
    question: "Will there be a curation interface?",
    answer:
      "Yes. A future release will integrate with ReCiter Publication Manager to add accept/reject curation directly in the UI. For now, you can import curation data via CSV upload and export scored results for review in your existing workflow.",
  },
];

export default function FAQPage() {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <div className="max-w-3xl">
      <h2 className="text-2xl font-semibold mb-2 text-gray-900">
        Frequently Asked Questions
      </h2>
      <p className="text-gray-500 mb-8">
        Common questions about ReCiter Desktop and the scoring pipeline.
      </p>

      <div className="space-y-2">
        {FAQS.map((faq, i) => (
          <Card key={i} className="border-gray-200 shadow-sm">
            <button
              className="w-full text-left px-5 py-4 flex items-start justify-between gap-4"
              onClick={() => setOpenIndex(openIndex === i ? null : i)}
            >
              <span className="text-sm font-medium text-gray-900">
                {faq.question}
              </span>
              <span className="text-gray-400 text-xs shrink-0 mt-0.5">
                {openIndex === i ? "\u25B2" : "\u25BC"}
              </span>
            </button>
            {openIndex === i && (
              <CardContent className="px-5 pb-4 pt-0">
                <p className="text-sm text-gray-600 leading-relaxed">
                  {faq.answer}
                </p>
              </CardContent>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
