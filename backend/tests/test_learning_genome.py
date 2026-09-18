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
                   persistence: float, misconceptions: list[str],
                   social_summary: str | None = None) -> str:
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
    if social_summary:
        parts.append(social_summary)
    return " ".join(parts)


def _compute_collaboration_score(room_count: int, annotation_count: int) -> float | None:
    """Inlined from app.services.learning_genome._compute_social_signals's scoring formula."""
    if room_count == 0 and annotation_count == 0:
        return None
    return round(min(1.0, room_count * 0.15 + annotation_count * 0.05), 3)

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


class TestSocialSignals:
    def test_no_activity_returns_none(self):
        assert _compute_collaboration_score(0, 0) is None

    def test_room_sessions_increase_score(self):
        low = _compute_collaboration_score(1, 0)
        high = _compute_collaboration_score(5, 0)
        assert high > low

    def test_annotations_increase_score(self):
        assert _compute_collaboration_score(0, 3) > 0

    def test_score_saturates_at_one(self):
        assert _compute_collaboration_score(20, 20) == 1.0

    def test_social_summary_appended_to_genome_summary(self):
        s = _build_summary(
            "average", "general", 18, 0.5, [],
            social_summary="This student has joined 3 collaborative study sessions.",
        )
        assert "joined 3 collaborative study sessions" in s

    def test_no_social_summary_omits_sentence(self):
        s = _build_summary("average", "general", 18, 0.5, [], social_summary=None)
        assert "collaborative" not in s


class TestModalityLabels:
    def test_all_keys_have_labels(self):
        for key, label in MODALITY_LABELS.items():
            assert isinstance(label, str)
            assert len(label) > 2

    def test_known_agents_present(self):
        assert "concept_qa" in MODALITY_LABELS
        assert "viva" in MODALITY_LABELS
        assert "protege" in MODALITY_LABELS
