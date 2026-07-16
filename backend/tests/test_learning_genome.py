"""Unit tests for the Learning Genome helpers.

Inlines _build_summary and MODALITY_LABELS from app.services.learning_genome
so the test file can run without the full backend dependency chain.
"""

# ---------- Inlined from app.services.learning_genome ----------

MODALITY_LABELS = {
    "concept_qa": "conceptual Q&A",
    "teach_me": "teaching-back (Feynman)",
    "protege": "teaching-back (Feynman)",
    "viva": "oral viva practice",
    "exam_prep": "exam practice",
    "exam_predictor": "exam practice",
    "critique": "writing critique",
    "weak_point_tracker": "weak-point review",
    "general": "open-ended chat",
}


def _build_summary(pace_label: str, modality: str, optimal_hour: int,
                   persistence: float, misconceptions: list[str]) -> str:
    modality_h = MODALITY_LABELS.get(modality, modality)
    persistence_h = (
        "high" if persistence >= 0.66 else "moderate" if persistence >= 0.33 else "low"
    )
    parts = [
        f"This student is a {pace_label}-paced learner who prefers {modality_h}.",
        f"They are most active around {optimal_hour:02d}:00 and show {persistence_h} persistence on weak topics.",
    ]
    if pace_label == "slow":
        parts.append("Provide extra scaffolding, break ideas into small steps, and check understanding frequently.")
    elif pace_label == "fast":
        parts.append("Move briskly, offer challenge extensions, and avoid over-explaining basics.")
    if misconceptions:
        parts.append("Watch for these recurring misconceptions: " + "; ".join(misconceptions) + ".")
    return " ".join(parts)

# ---------- End inlined ----------


class TestBuildSummary:
    def test_fast_learner_summary(self):
        s = _build_summary("fast", "concept_qa", 14, 0.8, [])
        assert "fast-paced" in s
        assert "briskly" in s

    def test_slow_learner_summary(self):
        s = _build_summary("slow", "viva", 21, 0.2, ["confuses X with Y"])
        assert "slow-paced" in s
        assert "scaffolding" in s
        assert "confuses X with Y" in s

    def test_average_learner_no_extra_advice(self):
        s = _build_summary("average", "exam_prep", 10, 0.5, [])
        assert "average-paced" in s
        assert "scaffolding" not in s
        assert "briskly" not in s

    def test_modality_label_used(self):
        s = _build_summary("fast", "protege", 18, 0.7, [])
        assert "teaching-back" in s

    def test_hour_formatted(self):
        s = _build_summary("average", "general", 9, 0.5, [])
        assert "09:00" in s

    def test_persistence_labels(self):
        high = _build_summary("average", "general", 18, 0.8, [])
        assert "high persistence" in high
        moderate = _build_summary("average", "general", 18, 0.5, [])
        assert "moderate persistence" in moderate
        low = _build_summary("average", "general", 18, 0.1, [])
        assert "low persistence" in low

    def test_misconceptions_appended(self):
        s = _build_summary("average", "general", 18, 0.5, ["A", "B"])
        assert "A" in s and "B" in s
        assert "misconceptions" in s.lower()


class TestModalityLabels:
    def test_all_keys_have_labels(self):
        for key, label in MODALITY_LABELS.items():
            assert isinstance(label, str)
            assert len(label) > 2

    def test_known_agents_present(self):
        assert "concept_qa" in MODALITY_LABELS
        assert "viva" in MODALITY_LABELS
        assert "protege" in MODALITY_LABELS
