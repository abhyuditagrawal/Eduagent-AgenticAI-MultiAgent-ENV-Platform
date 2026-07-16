"""Knowledge Frontier / Zone of Proximal Development (ZPD) engine.

Vygotsky's ZPD is the band of concepts a learner cannot yet grasp alone but
*can* master with guidance - i.e. concepts whose prerequisites are already
understood. This service partitions a subject's concept graph into:

  - mastered:  own mastery >= MASTERY_THRESHOLD
  - frontier:  not yet mastered, but all prerequisites are mastered  (the ZPD)
  - locked:    not yet mastered, and >=1 prerequisite is still weak

Frontier concepts are ranked by a readiness score so the UI can present a
"learning GPS": the single best next concept to study.
"""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.concept import Concept, ConceptPrerequisite
from app.models.student import StudentConcept

logger = structlog.get_logger()

MASTERY_THRESHOLD = 0.7   # own mastery required to count a concept "learned"
PREREQ_THRESHOLD = 0.6    # prerequisite mastery required to "unlock" a concept


async def compute_frontier(db: AsyncSession, student_id, subject_id) -> dict:
    # Concepts + student confidence
    result = await db.execute(
        select(Concept, StudentConcept)
        .outerjoin(
            StudentConcept,
            (StudentConcept.concept_id == Concept.id)
            & (StudentConcept.student_id == student_id),
        )
        .where(Concept.subject_id == subject_id)
    )
    rows = result.all()

    mastery: dict[str, float] = {}
    concept_meta: dict[str, dict] = {}
    for concept, sc in rows:
        cid = str(concept.id)
        mastery[cid] = sc.confidence_score if sc else 0.0
        concept_meta[cid] = {
            "id": cid,
            "name": concept.name,
            "chapter": concept.chapter,
            "difficulty": concept.difficulty_tier,
        }

    concept_ids = list(concept_meta.keys())
    if not concept_ids:
        return {"mastered": [], "frontier": [], "locked": [], "next_best": None,
                "counts": {"mastered": 0, "frontier": 0, "locked": 0, "total": 0}}

    # Prerequisite edges (prerequisite_id -> concept_id means prereq needed for concept)
    edge_result = await db.execute(
        select(ConceptPrerequisite).where(
            ConceptPrerequisite.concept_id.in_([c for c in concept_ids])
        )
    )
    prereqs_by_concept: dict[str, list[tuple[str, float]]] = {}
    for edge in edge_result.scalars().all():
        prereqs_by_concept.setdefault(str(edge.concept_id), []).append(
            (str(edge.prerequisite_id), edge.strength)
        )

    mastered, frontier, locked = [], [], []

    for cid, meta in concept_meta.items():
        own = mastery.get(cid, 0.0)
        if own >= MASTERY_THRESHOLD:
            mastered.append({**meta, "mastery": round(own, 2)})
            continue

        prereqs = prereqs_by_concept.get(cid, [])
        missing = []
        prereq_mastery_vals = []
        for pid, strength in prereqs:
            pm = mastery.get(pid, 0.0)
            prereq_mastery_vals.append(pm)
            if pm < PREREQ_THRESHOLD:
                missing.append({
                    "id": pid,
                    "name": concept_meta.get(pid, {}).get("name", "?"),
                    "mastery": round(pm, 2),
                })

        avg_prereq = (
            sum(prereq_mastery_vals) / len(prereq_mastery_vals)
            if prereq_mastery_vals else 1.0
        )

        if missing:
            locked.append({
                **meta,
                "mastery": round(own, 2),
                "missing_prerequisites": missing,
                "prereq_readiness": round(avg_prereq, 2),
            })
        else:
            # In the ZPD: prerequisites satisfied, concept not yet mastered.
            # Readiness favours: high prereq mastery, low own mastery, and
            # foundational-first ordering (lower difficulty slightly preferred).
            difficulty_factor = 1.0 / (1.0 + 0.15 * (meta["difficulty"] - 1))
            readiness = avg_prereq * (1.0 - own) * difficulty_factor
            frontier.append({
                **meta,
                "mastery": round(own, 2),
                "prereq_readiness": round(avg_prereq, 2),
                "readiness_score": round(readiness, 4),
            })

    frontier.sort(key=lambda x: x["readiness_score"], reverse=True)

    return {
        "mastered": mastered,
        "frontier": frontier,
        "locked": locked,
        "next_best": frontier[0] if frontier else None,
        "counts": {
            "mastered": len(mastered),
            "frontier": len(frontier),
            "locked": len(locked),
            "total": len(concept_ids),
        },
    }
