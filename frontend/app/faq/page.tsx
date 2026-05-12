"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";

interface FAQItem {
  question: string;
  answer: string;
}

interface FAQSection {
  title: string;
  items: FAQItem[];
}

const FAQ_SECTIONS: FAQSection[] = [
  {
    title: "Getting Started",
    items: [
      {
        question: "What is ReCiter Desktop?",
        answer:
          "ReCiter Desktop is a standalone tool for author name disambiguation. It helps institutions identify which PubMed publications belong to their researchers by using machine learning to score each article-researcher match. It uses CARE (Composite Author Recognition Engine) scoring models developed at Weill Cornell Medicine and validated across multiple institutions.",
      },
      {
        question: "What do I need to get started?",
        answer:
          "At minimum, you need: (1) Your institution\u2019s email domain (e.g., fredhutch.org) for the institution setup, and (2) A CSV or Excel file with your researchers \u2014 at minimum a unique ID, first name, and last name per row. Optional but helpful fields include email, department, title, doctoral year, and ORCID. A PubMed API key is recommended for faster retrieval (10 requests/second vs 3).",
      },
      {
        question: "What format should my researcher file be in?",
        answer:
          "CSV, Excel (.xlsx, .xls), or TSV. Column names are flexible \u2014 the system recognizes many common variations (e.g., \"emp_id\" or \"cwid\" for person ID, \"fname\" for first name, \"phd_year\" for doctoral year). After upload, you will see a column mapping screen where you can confirm or adjust the detected mappings.",
      },
      {
        question: "Do I need a PubMed API key?",
        answer:
          "It is recommended but not required. Without an API key, PubMed limits you to 3 requests per second. With a key, you get 10 requests per second \u2014 roughly 3x faster for large datasets. You can get a free API key from NCBI at https://www.ncbi.nlm.nih.gov/account/.",
      },
      {
        question: "Can I run ReCiter Desktop without Docker?",
        answer:
          "Docker Compose is the recommended way to run ReCiter Desktop as it handles all dependencies automatically. For development, you can run the components separately: MariaDB on port 3306, the FastAPI backend on port 8090 (uvicorn api.main:app), and the Next.js frontend on port 3002 (npm run dev). You will need Python 3.12+, Node.js 20+, and MariaDB 11+ installed.",
      },
    ],
  },
  {
    title: "Institution Setup",
    items: [
      {
        question: "What is the institution setup doing behind the scenes?",
        answer:
          "When you enter your email domain, the system searches PubMed for articles with that domain in the affiliation field. It then analyzes the affiliation strings to discover related email domains, institution name variants, and collaborating institutions. You classify each discovered institution as \"Home\" (your institution) or \"Collaborating\" (partner institutions). This information is used during scoring to determine how well an article\u2019s affiliations match your researchers.",
      },
      {
        question: "What is the difference between \"Home\" and \"Collaborating\" institutions?",
        answer:
          "Home institutions are your own organization and its close affiliates (e.g., your university and its medical school). Collaborating institutions are partner organizations where your researchers may have secondary appointments or co-author relationships. Both contribute to affiliation scoring, but home institution matches carry more weight.",
      },
    ],
  },
  {
    title: "Scoring and Results",
    items: [
      {
        question: "How does the scoring work?",
        answer:
          "The system computes up to 42 evidence features for each article-researcher pair (or 72 with curation data), organized into identity signals (name, email, gender, degree year), institutional features (affiliation, department, grants), bibliometric features (journal relevance, author count), and derived uncertainty features. These are fed into a pre-trained XGBoost model, then calibrated via isotonic regression to produce a 0\u2013100 confidence score. A score of 95 means there is a 95% probability the article belongs to that researcher.",
      },
      {
        question: "How accurate is the scoring?",
        answer:
          "On a held-out test set of 25,091 candidate articles from 572 researchers (strict person-level split to prevent data leakage), CARE achieves AUC 0.9993 and 99.99% empirical accuracy at the 99% confidence threshold. At the 95% threshold, 99.95% of articles are correctly attributed. External validation at Fred Hutchinson Cancer Center (868 researchers) confirmed cross-site generalization with AUC 0.9991 and 99.995% accuracy at the 99% threshold \u2014 without any retraining.",
      },
      {
        question: "What do the confidence scores mean?",
        answer:
          "CARE scores are calibrated probabilities, meaning the score directly reflects the likelihood of a correct match. A score of 95 means approximately 95% of articles at that confidence level are correctly attributed. This is different from most disambiguation systems, which optimize for ranking but not calibrated probabilities. The calibration uses isotonic regression and has been validated to have an Expected Calibration Error (ECE) of just 0.0019.",
      },
      {
        question: "What score threshold should I use?",
        answer:
          "We recommend a threshold of 95 or 99 depending on your tolerance for errors. At the 95% threshold, about 64% of articles fall above the threshold with a 0.05% error rate. At the 99% threshold, error rates drop to 1.4 per 10,000 predictions. Articles between 10% and 95% should be flagged for manual review. Articles below 10% are very unlikely matches. The threshold is adjustable on the Results page.",
      },
      {
        question: "What are the error rates at high confidence?",
        answer:
          "At the 99% confidence threshold, CARE produces 1.4 wrong auto-accepts per 10,000 predictions. At 99.5%, zero erroneous auto-accepts were observed in the test set. For context, per 100,000 high-confidence predictions at 99%, an institution would expect about 14 errors with CARE versus 240 with the legacy SVM system \u2014 a 17x improvement.",
      },
      {
        question: "Will the model work at my institution without retraining?",
        answer:
          "Yes. External validation at Fred Hutchinson Cancer Center (868 researchers, 26,953 articles) demonstrated that the WCM-trained model generalizes without retraining: AUC 0.9991 and 99.995% accuracy at the 99% threshold. The model discriminates effectively across institutions; calibration may degrade slightly (ECE 0.0069 vs 0.0019) but remains conservative \u2014 meaning stated confidence levels are met or exceeded.",
      },
    ],
  },
  {
    title: "Pipeline",
    items: [
      {
        question: "What is the difference between \"Full Retrieval and Scoring\" and \"Scoring Only\"?",
        answer:
          "In Full Retrieval and Scoring mode, the system searches PubMed by researcher name to discover candidate publications, then scores them. This is useful when you want to find publications you may not already know about. In Scoring Only mode, you upload a list of known PMIDs and the system scores just those articles. Use this when you already have complete publication lists.",
      },
      {
        question: "What does incremental retrieval mean?",
        answer:
          "When you run the pipeline a second time for researchers who have already been scored, the system only searches for newly added publications since the last run. Previously scored articles and their scores are preserved. This makes subsequent runs much faster and avoids redundant PubMed queries.",
      },
    ],
  },
  {
    title: "Curation and Training",
    items: [
      {
        question: "Can I import existing accept/reject decisions?",
        answer:
          "Yes. If your researcher CSV includes \"pmid\" and \"assertion\" columns (with values like ACCEPTED or REJECTED), the system will detect this as curation data and offer to import it. When curation data is available, the system automatically uses the more powerful 72-feature scoring model instead of the 42-feature identity-only model.",
      },
      {
        question: "What is the 72-feature model vs the 42-feature model?",
        answer:
          "The 42-feature \"identity-only\" model uses evidence from the researcher\u2019s identity: 8 identity features (name, email, gender, degree year), 4 institutional features (affiliation, department, grants), 3 bibliometric features (journal, author count), 3 relationship features, and 24 engineered features. The 72-feature \"feedback + identity\" model adds 15 feedback synthesis features (patterns from prior curation decisions across co-authors, journals, keywords, etc.), 8 feedback-specific derived features, and 2 curation count features. In practice, feedback features account for 84.8% of model importance, reducing manual review burden from 18% to 2.3% of articles.",
      },
      {
        question: "How much does curation reduce manual review?",
        answer:
          "Dramatically. For new researchers (no curation history), about 18% of candidate articles fall in the review band (scores between 10\u201395%). For established researchers with curation history, this drops to just 2.3% \u2014 an 87% reduction. Even a single prior curation decision provides meaningful signal, as the system immediately learns researcher-specific patterns from that decision.",
      },
    ],
  },
  {
    title: "Reference Data and Exports",
    items: [
      {
        question: "What reference data is bundled with ReCiter Desktop?",
        answer:
          "ReCiter Desktop ships with four reference data files that are used during scoring: a name frequency table (399,826 first names) for computing firstNameFrequencyScore, a gender inference table (95,025 names) for genderScoreIdentityArticleDiscrepancy, a Science Metrix journal classification table (19,866 journals mapped to subfields) for journalSubfieldScore, and a Science Metrix department-to-category mapping (33,576 entries) for matching researcher departments to journal subfields. All files are loaded lazily on first use and cached in memory. Three features from the full ReCiter pipeline are not included: grant matching (grantMatchScore), co-authorship network analysis (relationshipPositiveMatchScore, relationshipNegativeMatchScore), and Scopus affiliation enrichment. These features are set to 0.0 (neutral) and have minimal impact on accuracy \u2014 the feedback model compensates via curation data, and the identity-only model still achieves AUC 0.9776 without them.",
      },
      {
        question: "How do I export my results?",
        answer:
          "Go to the Results page and click \"Export All Results (CSV)\" for the full dataset, or navigate to an individual researcher and click \"Export CSV\" for their articles only. The export includes person ID, name, PMID, article title, journal, year, score, and a PubMed link for each article.",
      },
    ],
  },
  {
    title: "Roadmap",
    items: [
      {
        question: "Will there be a curation interface?",
        answer:
          "Yes. A future release will integrate with ReCiter Publication Manager to add accept/reject curation directly in the UI. This is significant because curation data activates the 72-feature feedback model, which reduces manual review from 18% to 2.3% of articles. For now, you can import existing curation data via CSV upload.",
      },
    ],
  },
];

export default function FAQPage() {
  const [openIndex, setOpenIndex] = useState<string | null>(null);

  return (
    <div className="max-w-3xl">
      <h2 className="text-2xl font-semibold mb-2 text-gray-900">
        Frequently Asked Questions
      </h2>
      <p className="text-gray-500 mb-8">
        Common questions about ReCiter Desktop and the CARE scoring pipeline.
      </p>

      <div className="space-y-8">
        {FAQ_SECTIONS.map((section) => (
          <div key={section.title}>
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
              {section.title}
            </h3>
            <div className="space-y-2">
              {section.items.map((faq, i) => {
                const key = `${section.title}-${i}`;
                return (
                  <Card key={key} className="border-gray-200 shadow-sm">
                    <button
                      className="w-full text-left px-5 py-4 flex items-start justify-between gap-4"
                      onClick={() => setOpenIndex(openIndex === key ? null : key)}
                    >
                      <span className="text-sm font-medium text-gray-900">
                        {faq.question}
                      </span>
                      <span className="text-gray-400 text-xs shrink-0 mt-0.5">
                        {openIndex === key ? "\u25B2" : "\u25BC"}
                      </span>
                    </button>
                    {openIndex === key && (
                      <CardContent className="px-5 pb-4 pt-0">
                        <p className="text-sm text-gray-600 leading-relaxed">
                          {faq.answer}
                        </p>
                      </CardContent>
                    )}
                  </Card>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
