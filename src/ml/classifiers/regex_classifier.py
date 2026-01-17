"""
Regex-based document classifier.

Wrapper around the existing regex classification logic from DocumentProcessor.
Provides a fast, reliable fallback when ML classifiers are unavailable.
"""

import re
import time
from typing import Dict, List

from .base import BaseClassifier, ClassificationResult, DOCUMENT_TYPES


class RegexClassifier(BaseClassifier):
    """
    Regex-based document classifier.

    Uses pattern matching to identify tax document types based on
    known indicators and form identifiers.
    """

    name = "regex"

    # Document type indicators (patterns for each form type)
    DOCUMENT_INDICATORS: Dict[str, List[str]] = {
        "w2": [
            r"form\s*w-?2\b",
            r"wage\s+and\s+tax\s+statement",
            r"employer.s?\s+identification\s+number",
            r"box\s*1.*wages.*tips",
            r"social\s+security\s+wages",
            r"medicare\s+wages",
        ],
        "w2g": [
            r"form\s*w-?2g",
            r"certain\s+gambling\s+winnings",
            r"gambling\s+winnings",
            r"reportable\s+winnings",
            r"payer.s?\s+federal.*identification",
            r"type\s+of\s+wager",
        ],
        "1099-int": [
            r"form\s*1099-?int",
            r"interest\s+income",
            r"early\s+withdrawal\s+penalty",
            r"tax.exempt\s+interest",
        ],
        "1099-div": [
            r"form\s*1099-?div",
            r"dividends\s+and\s+distributions",
            r"ordinary\s+dividends",
            r"qualified\s+dividends",
            r"capital\s+gain\s+(?:distr|dist)",
        ],
        "1099-nec": [
            r"form\s*1099-?nec",
            r"nonemployee\s+compensation",
        ],
        "1099-misc": [
            r"form\s*1099-?misc",
            r"miscellaneous\s+(?:income|information)",
            r"rents.*royalties",
        ],
        "1099-b": [
            r"form\s*1099-?b",
            r"proceeds\s+from\s+broker",
            r"barter\s+exchange",
            r"cost\s+or\s+other\s+basis",
        ],
        "1099-r": [
            r"form\s*1099-?r",
            r"distributions\s+from\s+pensions",
            r"annuities.*retirement",
            r"ira.*distribution",
        ],
        "1099-g": [
            r"form\s*1099-?g",
            r"government\s+payments",
            r"unemployment\s+compensation",
            r"state.*local\s+income\s+tax\s+refunds",
        ],
        "1099-k": [
            r"form\s*1099-?k",
            r"payment\s+card.*third\s+party",
            r"merchant\s+card",
            r"third\s+party\s+network\s+transactions",
            r"gross\s+amount\s+of\s+payment\s+card",
            r"payment\s+settlement\s+entity",
        ],
        "1099-sa": [
            r"form\s*1099-?sa",
            r"distributions\s+from\s+an?\s+hsa",
            r"distributions\s+from\s+an?\s+(?:hsa|archer\s+msa|medicare\s+advantage)",
            r"health\s+savings\s+account",
            r"archer\s+msa",
            r"medicare\s+advantage\s+msa",
        ],
        "1099-q": [
            r"form\s*1099-?q",
            r"payments\s+from\s+qualified\s+education",
            r"qualified\s+tuition\s+program",
            r"coverdell\s+esa",
            r"529\s+(?:plan|program)",
            r"education\s+savings\s+account",
        ],
        "1099-c": [
            r"form\s*1099-?c",
            r"cancellation\s+of\s+debt",
            r"debt\s+canceled",
            r"amount\s+of\s+debt\s+(?:discharged|canceled)",
            r"creditor.s?\s+name",
        ],
        "1099-s": [
            r"form\s*1099-?s",
            r"proceeds\s+from\s+real\s+estate",
            r"real\s+estate\s+transactions",
            r"gross\s+proceeds",
            r"transferor.s?\s+.*identification",
            r"address.*property\s+transferred",
        ],
        "1099-oid": [
            r"form\s*1099-?oid",
            r"original\s+issue\s+discount",
            r"oid\s+on\s+u\.?s\.?\s+treasury",
            r"acquisition\s+premium",
            r"bond\s+premium",
        ],
        "1099-ltc": [
            r"form\s*1099-?ltc",
            r"long.term\s+care",
            r"accelerated\s+death\s+benefits",
            r"ltc\s+benefits",
            r"per\s+diem.*qualified",
        ],
        "1099-patr": [
            r"form\s*1099-?patr",
            r"taxable\s+distributions.*cooperatives",
            r"patronage\s+dividends",
            r"per.unit\s+retain\s+allocations",
            r"cooperative",
        ],
        "1098": [
            r"form\s*1098\b",
            r"mortgage\s+interest\s+statement",
            r"mortgage\s+interest\s+received",
        ],
        "1098-e": [
            r"form\s*1098-?e",
            r"student\s+loan\s+interest",
        ],
        "1098-t": [
            r"form\s*1098-?t",
            r"tuition\s+statement",
            r"payments\s+received.*qualified\s+tuition",
        ],
        "k1": [
            r"schedule\s*k-?1",
            r"partner.s?\s+share",
            r"shareholder.s?\s+share",
            r"beneficiary.s?\s+share",
        ],
        "1095-a": [
            r"form\s*1095-?a",
            r"health\s+insurance\s+marketplace",
            r"premium\s+tax\s+credit",
        ],
        "1095-b": [
            r"form\s*1095-?b",
            r"health\s+coverage",
            r"minimum\s+essential\s+coverage",
        ],
        "1095-c": [
            r"form\s*1095-?c",
            r"employer.provided\s+health\s+insurance",
            r"offer\s+and\s+coverage",
        ],
        "ssa-1099": [
            r"(?:form\s*)?ssa-?1099",
            r"social\s+security\s+benefit\s+statement",
            r"social\s+security\s+administration",
            r"benefits\s+paid",
            r"net\s+benefits.*box\s*5",
            r"medicare\s+premium.*deducted",
        ],
        "rrb-1099": [
            r"(?:form\s*)?rrb-?1099",
            r"railroad\s+retirement\s+(?:board|benefits)",
            r"payments\s+by.*railroad\s+retirement",
            r"social\s+security\s+equivalent\s+benefit",
            r"tier\s+[12]\s+(?:benefits|tax)",
        ],
        "5498": [
            r"form\s*5498\b",
            r"ira\s+contribution\s+information",
            r"rollover\s+contributions",
            r"roth\s+ira\s+conversion",
            r"fair\s+market\s+value.*ira",
            r"required\s+minimum\s+distribution",
        ],
        "5498-sa": [
            r"form\s*5498-?sa",
            r"hsa.*(?:archer\s+msa|medicare\s+advantage)?\s*information",
            r"hsa\s+contributions",
            r"archer\s+msa\s+contributions",
            r"fair\s+market\s+value.*(?:hsa|msa)",
            r"total\s+contributions",
        ],
    }

    def classify(self, text: str) -> ClassificationResult:
        """
        Classify document using regex pattern matching.

        Args:
            text: The extracted text content of the document.

        Returns:
            ClassificationResult with document type and confidence.
        """
        start_time = time.time()

        if not text:
            return ClassificationResult(
                document_type="unknown",
                confidence=0.0,
                classifier_used=self.name,
                processing_time_ms=self._measure_time(start_time),
                metadata={"reason": "empty_text"},
            )

        text_lower = text.lower()
        scores: Dict[str, Dict] = {}

        for doc_type, patterns in self.DOCUMENT_INDICATORS.items():
            score = 0
            matched_patterns = []

            for pattern in patterns:
                if re.search(pattern, text_lower):
                    score += 1
                    matched_patterns.append(pattern)

            if score > 0:
                # Normalize score (percentage of patterns matched)
                confidence = score / len(patterns)
                scores[doc_type] = {
                    "confidence": confidence,
                    "matched_patterns": matched_patterns,
                    "total_patterns": len(patterns),
                }

        if not scores:
            return ClassificationResult(
                document_type="unknown",
                confidence=0.0,
                classifier_used=self.name,
                processing_time_ms=self._measure_time(start_time),
                metadata={"reason": "no_patterns_matched"},
            )

        # Get highest scoring document type
        best_type = max(scores.keys(), key=lambda k: scores[k]["confidence"])
        best_score = scores[best_type]

        # Calculate probabilities for all document types
        probabilities = {doc_type: 0.0 for doc_type in DOCUMENT_TYPES}
        total_confidence = sum(s["confidence"] for s in scores.values())

        if total_confidence > 0:
            for doc_type, score_info in scores.items():
                probabilities[doc_type] = score_info["confidence"] / total_confidence

        # Set unknown probability as complement
        probabilities["unknown"] = max(0.0, 1.0 - sum(
            p for k, p in probabilities.items() if k != "unknown"
        ))

        return ClassificationResult(
            document_type=best_type,
            confidence=best_score["confidence"],
            probabilities=probabilities,
            classifier_used=self.name,
            processing_time_ms=self._measure_time(start_time),
            metadata={
                "matched_patterns": best_score["matched_patterns"],
                "total_patterns": best_score["total_patterns"],
                "all_scores": {k: v["confidence"] for k, v in scores.items()},
            },
        )

    def get_supported_types(self) -> List[str]:
        """Get list of document types this classifier can identify."""
        return list(self.DOCUMENT_INDICATORS.keys())
