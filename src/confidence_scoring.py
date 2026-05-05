#!/usr/bin/env python3
"""
Three-Factor Adaptive Confidence Scoring for Document Classification

Improves on the original two-factor approach by:
  1. Incorporating the LLM's self-reported calibration as a third signal
  2. Scaling evidence continuously with trigger count rather than flat buckets
  3. Treating "no rules match" direction-aware (neutral for low-risk, penalty for high)
  4. Using adaptive weights that shift based on how the classification decision was made

ACADEMIC REFERENCES:
====================
1. ENSEMBLE AGREEMENT (Dietterich, 2000)
   - Dietterich, T. G. (2000). Ensemble Methods in Machine Learning.
   - Lecture Notes in Computer Science, vol 1857, pp. 1–15.
   - DOI: 10.1007/3-540-45014-9_1

2. EVIDENCE THEORY (Dempster-Shafer, 1967/1976)
   - Dempster, A. P. (1967). Upper and Lower Probabilities Induced by a
     Multivalued Mapping. Annals of Mathematical Statistics, 38(2), 325–339.
   - Shafer, G. (1976). A Mathematical Theory of Evidence. Princeton UP.

3. LLM CALIBRATION (Guo et al., 2017)
   - Guo, C. et al. (2017). On Calibration of Modern Neural Networks.
   - ICML 2017. https://arxiv.org/abs/1706.04599
   - Principle: self-reported probabilities from large language models carry
     meaningful signal when used as one input among others.

FORMULA:
========
Confidence = w_agreement × Agreement
           + w_evidence  × Evidence
           + w_llm       × LLM_Calibration

Weights are adaptive — they shift based on the classification method:

  RULES_OVERRIDE        → evidence dominates  (0.25 / 0.60 / 0.15)
  AGREEMENT             → balanced            (0.40 / 0.35 / 0.25)
  RULES_ESCALATED       → evidence-heavy      (0.25 / 0.55 / 0.20)
  MASKED_DATA_DOWNGRADE → evidence-heavy      (0.30 / 0.50 / 0.20)
  AI_DECISION           → LLM-heavy           (0.20 / 0.25 / 0.55)
"""

from typing import Dict, List, Optional


# ── Adaptive weight profiles ───────────────────────────────────────────────────
ADAPTIVE_WEIGHTS: Dict[str, Dict[str, float]] = {
    # Hard PII found by rules — trust evidence most
    'RULES_OVERRIDE':          {'agreement': 0.25, 'evidence': 0.60, 'llm': 0.15},
    # Both classifiers agreed — balanced
    'AGREEMENT':               {'agreement': 0.40, 'evidence': 0.35, 'llm': 0.25},
    # Rules escalated over LLM — evidence-heavy
    'RULES_ESCALATED':         {'agreement': 0.25, 'evidence': 0.55, 'llm': 0.20},
    # Downgraded due to masking — evidence-heavy
    'MASKED_DATA_DOWNGRADE':   {'agreement': 0.30, 'evidence': 0.50, 'llm': 0.20},
    # AI alone, no rules match — LLM calibration matters most
    'AI_DECISION':             {'agreement': 0.20, 'evidence': 0.25, 'llm': 0.55},
}
DEFAULT_WEIGHTS = {'agreement': 0.35, 'evidence': 0.40, 'llm': 0.25}

# PII triggers considered definitively high-risk
PII_TRIGGERS = {'National ID', 'Passport', 'IBAN', 'Credit Card', 'Account Number', 'Salary'}

CLASS_HIERARCHY = {'C0': 0, 'C1': 1, 'C2': 2, 'C3': 3}


class ConfidenceScorer:
    """
    Three-factor adaptive confidence scorer.

    Factors:
      - Agreement  (Dietterich, 2000): do LLM and rules agree?
      - Evidence   (Dempster-Shafer): how much and what kind of evidence exists?
      - LLM Cal.   (Guo et al., 2017): the model's own probability estimate
    """

    def calculate_agreement_score(
        self, llm_class: str, rules_class: Optional[str], final_class: str
    ) -> float:
        """
        Agreement score between LLM and security rules.

        Direction-aware when rules find nothing:
          - Rules found nothing + low final class (C0/C1) → 0.65 (reasonable,
            low-risk documents often don't trigger pattern rules)
          - Rules found nothing + high final class (C2/C3) → 0.40 (uncertain,
            the AI is making a strong claim without corroboration)
        """
        if rules_class is None:
            final_level = CLASS_HIERARCHY.get(final_class, 1)
            return 0.65 if final_level <= 1 else 0.40

        if llm_class == rules_class:
            return 1.00

        llm_level   = CLASS_HIERARCHY.get(llm_class, 0)
        rules_level = CLASS_HIERARCHY.get(rules_class, 0)
        distance    = abs(llm_level - rules_level)

        return {1: 0.75, 2: 0.50, 3: 0.25}.get(distance, 0.25)

    def calculate_evidence_score(self, triggers: List[str]) -> float:
        """
        Continuous evidence score that scales with trigger count.

        Base:   0.40 (no evidence)
        +0.12   per non-PII trigger (capped, diminishing)
        +0.20   per PII trigger (high-risk, hard signal)
        Capped at 1.00.

        This replaces the original 4-bucket system so 3 triggers score
        higher than 2 and 10 triggers don't score the same as 2.
        """
        if not triggers:
            return 0.40

        score = 0.40
        for t in triggers:
            score += 0.20 if t in PII_TRIGGERS else 0.12
        return min(score, 1.00)

    def calculate_llm_score(self, llm_raw_confidence: Optional[float]) -> float:
        """
        LLM calibration factor (Guo et al., 2017).

        Uses the model's self-reported probability directly.
        Falls back to 0.60 (neutral-ish) when not available — LLaMA 3
        tends to be reasonably calibrated so 0.60 is a conservative prior.
        """
        if llm_raw_confidence is None:
            return 0.60
        return max(0.0, min(1.0, float(llm_raw_confidence)))

    def calculate_confidence(
        self,
        classification: str,
        llm_class: str,
        llm_raw_confidence: Optional[float],
        rules_class: Optional[str],
        triggers: List[str],
        method: str,
    ) -> Dict:
        """
        Three-factor adaptive confidence score.

        Confidence = w_agreement × Agreement
                   + w_evidence  × Evidence
                   + w_llm       × LLM_Calibration
        """
        weights  = ADAPTIVE_WEIGHTS.get(method, DEFAULT_WEIGHTS)

        agreement = self.calculate_agreement_score(llm_class, rules_class, classification)
        evidence  = self.calculate_evidence_score(triggers)
        llm_score = self.calculate_llm_score(llm_raw_confidence)

        confidence = (
            weights['agreement'] * agreement +
            weights['evidence']  * evidence  +
            weights['llm']       * llm_score
        )

        confidence = max(0.0, min(1.0, confidence))

        explanation = self._build_explanation(
            confidence, agreement, evidence, llm_score,
            method, weights, triggers, llm_class, rules_class,
        )

        return {
            'confidence':         round(confidence, 3),
            'confidence_percent': round(confidence * 100, 1),
            'factors': {
                'agreement': round(agreement, 3),
                'evidence':  round(evidence, 3),
                'llm':       round(llm_score, 3),
            },
            'weights':            weights,
            'method_adjustment':  method,
            'explanation':        explanation,
            'llm_raw_confidence': llm_raw_confidence,
            'formula':            (
                f"Confidence = {weights['agreement']} × Agreement"
                f" + {weights['evidence']} × Evidence"
                f" + {weights['llm']} × LLM_Calibration"
            ),
            'references': [
                'Dietterich (2000) — Ensemble Methods in Machine Learning',
                'Dempster-Shafer (1967/1976) — Theory of Evidence',
                'Guo et al. (2017) — On Calibration of Modern Neural Networks',
            ],
        }

    def _build_explanation(
        self,
        confidence: float,
        agreement: float,
        evidence: float,
        llm_score: float,
        method: str,
        weights: Dict[str, float],
        triggers: List[str],
        llm_class: str,
        rules_class: Optional[str],
    ) -> str:
        if confidence >= 0.90:
            level = "Very High Confidence"
        elif confidence >= 0.75:
            level = "High Confidence"
        elif confidence >= 0.60:
            level = "Moderate Confidence"
        elif confidence >= 0.45:
            level = "Low Confidence"
        else:
            level = "Very Low Confidence"

        if rules_class is None:
            agr_note = "Rules: no match"
        elif llm_class == rules_class:
            agr_note = f"Agreement: both say {llm_class}"
        else:
            agr_note = f"Disagreement: LLM={llm_class}, Rules={rules_class}"

        if triggers:
            pii = [t for t in triggers if t in PII_TRIGGERS]
            ev_note = f"PII detected ({', '.join(pii[:2])})" if pii else f"{len(triggers)} pattern(s)"
        else:
            ev_note = "No evidence"

        llm_note = f"LLM self-confidence: {llm_score:.0%}"

        return f"{level} | {agr_note} | Evidence: {ev_note} | {llm_note}"


# ── Singleton ──────────────────────────────────────────────────────────────────
_scorer: Optional[ConfidenceScorer] = None

def get_confidence_scorer() -> ConfidenceScorer:
    global _scorer
    if _scorer is None:
        _scorer = ConfidenceScorer()
    return _scorer


def calculate_confidence(
    classification: str,
    llm_class: str,
    llm_raw_confidence: Optional[float],
    rules_class: Optional[str],
    triggers: List[str],
    method: str,
) -> Dict:
    return get_confidence_scorer().calculate_confidence(
        classification, llm_class, llm_raw_confidence,
        rules_class, triggers, method,
    )
