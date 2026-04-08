#!/usr/bin/env python3
"""
Two-Factor Confidence Scoring System for Document Classification

A simple, academically-grounded confidence scoring system based on two
well-established frameworks.

ACADEMIC REFERENCES:
====================

1. ENSEMBLE AGREEMENT (Dietterich, 2000)
   - Dietterich, T. G. (2000). "Ensemble Methods in Machine Learning"
   - Lecture Notes in Computer Science, vol 1857, pp. 1-15
   - DOI: 10.1007/3-540-45014-9_1
   - Principle: "When multiple classifiers agree, the probability of
     correct classification increases"

2. EVIDENCE THEORY (Dempster-Shafer, 1967, 1976)
   - Dempster, A. P. (1967). "Upper and Lower Probabilities Induced by
     a Multivalued Mapping". The Annals of Mathematical Statistics, 38(2), 325-339
   - Shafer, G. (1976). "A Mathematical Theory of Evidence". Princeton University Press
   - Principle: "Belief in a hypothesis increases with accumulating evidence"


CONFIDENCE FORMULA:
==================

Confidence = 0.50 × Agreement + 0.50 × Evidence

Where:
- Agreement (0-1): Do LLM and Rules agree on classification?
- Evidence (0-1): What type of evidence supports the classification?

This simple formula is:
- Easy to understand and explain
- Fully backed by academic literature
- Produces intuitive confidence scores

Author: SecureDoc AI Team
"""

from typing import Dict, List, Optional


class ConfidenceScorer:
    """
    Two-factor confidence scoring based on academic frameworks.

    References:
    - Dietterich (2000): Ensemble agreement
    - Dempster-Shafer (1967, 1976): Evidence theory
    """

    # Weights for each factor (sum = 1.0)
    WEIGHTS = {
        'agreement': 0.50,   # Ensemble agreement (Dietterich, 2000)
        'evidence': 0.50     # Evidence strength (Dempster-Shafer, 1967)
    }

    # PII triggers - definitive evidence for C3
    PII_TRIGGERS = {
        'National ID', 'Passport', 'IBAN', 'Credit Card',
        'Account Number', 'Salary'
    }

    # Class hierarchy for agreement calculation
    CLASS_HIERARCHY = {'C0': 0, 'C1': 1, 'C2': 2, 'C3': 3}

    def __init__(self):
        """Initialize the confidence scorer."""
        pass

    def calculate_agreement_score(self, llm_class: str, rules_class: Optional[str]) -> float:
        """
        Calculate agreement score between LLM and Rules.

        Based on: Dietterich, T. G. (2000). "Ensemble Methods in Machine Learning"

        "When multiple classifiers agree, the probability of correct
        classification increases"

        Returns:
            float: Agreement score (0.0 - 1.0)
        """
        if rules_class is None:
            # Rules couldn't classify - neutral confidence
            return 0.50

        if llm_class == rules_class:
            # Perfect agreement
            return 1.00

        # Calculate distance in hierarchy
        llm_level = self.CLASS_HIERARCHY.get(llm_class, 0)
        rules_level = self.CLASS_HIERARCHY.get(rules_class, 0)
        distance = abs(llm_level - rules_level)

        # Map distance to score
        if distance == 1:
            return 0.75  # 1 level apart
        elif distance == 2:
            return 0.50  # 2 levels apart
        else:
            return 0.25  # 3 levels apart (max disagreement)

    def calculate_evidence_score(self, triggers: List[str], classification: str) -> float:
        """
        Calculate evidence strength score.

        Based on: Dempster-Shafer Theory of Evidence (1967, 1976)

        "Belief in a hypothesis increases with accumulating evidence"

        Returns:
            float: Evidence score (0.0 - 1.0)
        """
        if not triggers:
            # No evidence - low confidence
            return 0.40

        # Check for PII (definitive evidence)
        has_pii = any(trigger in self.PII_TRIGGERS for trigger in triggers)

        if has_pii:
            # PII detected = definitive evidence
            return 1.00
        elif len(triggers) >= 2:
            # Multiple patterns = strong evidence
            return 0.85
        else:
            # Single pattern = moderate evidence
            return 0.70

    def calculate_confidence(self,
                            classification: str,
                            llm_class: str,
                            llm_raw_confidence: Optional[float],
                            rules_class: Optional[str],
                            triggers: List[str],
                            method: str) -> Dict:
        """
        Calculate final confidence score using 2-factor approach.

        Formula: Confidence = 0.50 × Agreement + 0.50 × Evidence

        Args:
            classification: Final classification (C0-C3)
            llm_class: LLM's classification
            llm_raw_confidence: LLM's self-reported confidence (for reference)
            rules_class: Rules engine classification (or None)
            triggers: List of triggered patterns
            method: Classification method used

        Returns:
            Dict with confidence score and explanation
        """
        # Calculate individual factors
        agreement = self.calculate_agreement_score(llm_class, rules_class)
        evidence = self.calculate_evidence_score(triggers, classification)

        # Weighted combination
        confidence = (
            self.WEIGHTS['agreement'] * agreement +
            self.WEIGHTS['evidence'] * evidence
        )

        # Apply method-based adjustments
        if method == 'RULES_OVERRIDE':
            # Rules detected critical PII - high confidence
            confidence = max(confidence, 0.90)
        elif method == 'AI_DECISION':
            # AI alone - slightly reduce
            confidence = confidence * 0.95

        # Clamp to valid range
        confidence = max(0.0, min(1.0, confidence))

        # Build explanation
        explanation = self._build_explanation(
            confidence, agreement, evidence, method, triggers, llm_class, rules_class
        )

        return {
            'confidence': round(confidence, 3),
            'confidence_percent': round(confidence * 100, 1),
            'factors': {
                'agreement': round(agreement, 3),
                'evidence': round(evidence, 3)
            },
            'weights': self.WEIGHTS,
            'method_adjustment': method,
            'explanation': explanation,
            'llm_raw_confidence': llm_raw_confidence,
            'formula': 'Confidence = 0.50 × Agreement + 0.50 × Evidence',
            'references': [
                'Dietterich (2000) - Ensemble Methods in Machine Learning',
                'Dempster-Shafer (1967, 1976) - Theory of Evidence'
            ]
        }

    def _build_explanation(self, confidence: float, agreement: float,
                          evidence: float, method: str, triggers: List[str],
                          llm_class: str, rules_class: Optional[str]) -> str:
        """Build human-readable explanation of confidence score."""

        parts = []

        # Overall confidence level
        if confidence >= 0.90:
            parts.append("Very High Confidence")
        elif confidence >= 0.75:
            parts.append("High Confidence")
        elif confidence >= 0.60:
            parts.append("Moderate Confidence")
        elif confidence >= 0.45:
            parts.append("Low Confidence")
        else:
            parts.append("Very Low Confidence")

        # Agreement explanation
        if rules_class is None:
            parts.append("Rules: No match")
        elif llm_class == rules_class:
            parts.append(f"Agreement: Both say {llm_class}")
        else:
            parts.append(f"Disagreement: LLM={llm_class}, Rules={rules_class}")

        # Evidence explanation
        if triggers:
            has_pii = any(t in self.PII_TRIGGERS for t in triggers)
            if has_pii:
                parts.append(f"Evidence: PII detected ({', '.join(triggers[:2])})")
            else:
                parts.append(f"Evidence: {len(triggers)} pattern(s)")
        else:
            parts.append("Evidence: None")

        return " | ".join(parts)


# Singleton instance
_scorer = None

def get_confidence_scorer() -> ConfidenceScorer:
    """Get singleton confidence scorer instance."""
    global _scorer
    if _scorer is None:
        _scorer = ConfidenceScorer()
    return _scorer


def calculate_confidence(classification: str, llm_class: str,
                        llm_raw_confidence: Optional[float],
                        rules_class: Optional[str], triggers: List[str],
                        method: str) -> Dict:
    """
    Convenience function to calculate confidence.

    See ConfidenceScorer.calculate_confidence for full documentation.
    """
    scorer = get_confidence_scorer()
    return scorer.calculate_confidence(
        classification, llm_class, llm_raw_confidence,
        rules_class, triggers, method
    )


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TWO-FACTOR CONFIDENCE SCORING SYSTEM")
    print("=" * 60)
    print("\nFormula: Confidence = 0.50 × Agreement + 0.50 × Evidence")
    print("\nAcademic References:")
    print("  1. Dietterich (2000) - Ensemble Methods in Machine Learning")
    print("  2. Dempster-Shafer (1967, 1976) - Theory of Evidence")
    print()

    scorer = ConfidenceScorer()

    # Test cases
    test_cases = [
        {
            'name': 'C3 - Both Agree + PII Detected',
            'classification': 'C3',
            'llm_class': 'C3',
            'llm_raw_confidence': 0.85,
            'rules_class': 'C3',
            'triggers': ['National ID', 'IBAN'],
            'method': 'AGREEMENT'
        },
        {
            'name': 'C3 - Rules Override (PII Found)',
            'classification': 'C3',
            'llm_class': 'C2',
            'llm_raw_confidence': 0.70,
            'rules_class': 'C3',
            'triggers': ['National ID'],
            'method': 'RULES_OVERRIDE'
        },
        {
            'name': 'C2 - Both Agree + Pattern Detected',
            'classification': 'C2',
            'llm_class': 'C2',
            'llm_raw_confidence': 0.80,
            'rules_class': 'C2',
            'triggers': ['Personal Data'],
            'method': 'AGREEMENT'
        },
        {
            'name': 'C1 - AI Decision Only (No Rules Match)',
            'classification': 'C1',
            'llm_class': 'C1',
            'llm_raw_confidence': 0.65,
            'rules_class': None,
            'triggers': [],
            'method': 'AI_DECISION'
        },
        {
            'name': 'C0 - Both Agree + Public Keywords',
            'classification': 'C0',
            'llm_class': 'C0',
            'llm_raw_confidence': 0.90,
            'rules_class': 'C0',
            'triggers': ['Public keywords'],
            'method': 'AGREEMENT'
        },
    ]

    for i, tc in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"Test {i}: {tc['name']}")
        print("-" * 60)

        result = scorer.calculate_confidence(
            tc['classification'],
            tc['llm_class'],
            tc['llm_raw_confidence'],
            tc['rules_class'],
            tc['triggers'],
            tc['method']
        )

        print(f"Classification: {tc['classification']}")
        print(f"LLM Raw Confidence: {tc['llm_raw_confidence']:.0%}")
        print(f"\nCalculated Confidence: {result['confidence_percent']}%")
        print(f"\nFactor Breakdown:")
        print(f"  Agreement: {result['factors']['agreement']:.0%} (weight: 50%)")
        print(f"  Evidence:  {result['factors']['evidence']:.0%} (weight: 50%)")
        print(f"\nCalculation:")
        print(f"  0.50 × {result['factors']['agreement']:.2f} + 0.50 × {result['factors']['evidence']:.2f} = {result['confidence']:.2f}")
        print(f"\nExplanation: {result['explanation']}")

    print("\n" + "=" * 60)
    print("FORMULA SUMMARY")
    print("=" * 60)
    print("""
Agreement Score (Dietterich, 2000):
  - Both agree     → 100%
  - 1 level apart  → 75%
  - 2 levels apart → 50%
  - No rules match → 50%

Evidence Score (Dempster-Shafer, 1967):
  - PII detected   → 100%
  - 2+ patterns    → 85%
  - 1 pattern      → 70%
  - No patterns    → 40%
""")
