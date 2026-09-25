"""Seed the two EduAgent-Cyber subjects: Cyber Forensics and Cryptography &
Network Security - concepts + prerequisite graph only (Tier 1 content), so
BKT/Knowledge Frontier/ZPD have real structure to work with as soon as a
real student starts using either subject. No fake student/messages are
created here; unlike scripts/seed_demo.py this seeds subjects the actual
team will use, not a demo account.

Idempotent: re-running skips any subject/concept/prerequisite that already
exists, so it's safe to run again after adding more concepts below.

Run with: python -m scripts.seed_cyber_subjects
"""

import asyncio

from sqlalchemy import select

from app.database import async_session
from app.models.subject import Subject
from app.models.concept import Concept, ConceptPrerequisite

# (code, name, description)
SUBJECTS = [
    ("CYFOR", "Cyber Forensics", "Digital evidence handling, forensic imaging and analysis, and investigative reporting."),
    ("CRYPTNET", "Cryptography & Network Security", "Classical and modern cryptography, key exchange, PKI, and network-security protocols/defences."),
]

# code -> [(name, chapter, difficulty_tier), ...]
CONCEPTS: dict[str, list[tuple[str, str, int]]] = {
    "CYFOR": [
        ("Digital Evidence Fundamentals", "Foundations", 1),
        ("Chain of Custody", "Foundations", 1),
        ("Forensic Imaging & Write-Blocking", "Acquisition", 2),
        ("File Systems & Metadata", "Acquisition", 2),
        ("File Carving & Data Recovery", "Analysis", 2),
        ("Memory Forensics", "Analysis", 3),
        ("Network Forensics", "Analysis", 3),
        ("Timeline Analysis & Event Reconstruction", "Analysis", 2),
        ("Anti-Forensics Techniques", "Analysis", 3),
        ("Reporting & Legal/Ethical Considerations", "Reporting", 1),
    ],
    "CRYPTNET": [
        ("Modular Arithmetic & Number Theory", "Foundations", 1),
        ("Classical Ciphers", "Foundations", 1),
        ("Symmetric-Key Encryption (DES/AES)", "Symmetric Cryptography", 2),
        ("Cryptographic Hash Functions", "Symmetric Cryptography", 2),
        ("Public-Key Cryptography (RSA, Diffie-Hellman)", "Asymmetric Cryptography", 3),
        ("Digital Signatures & PKI", "Asymmetric Cryptography", 3),
        ("Authentication Protocols", "Network Security", 2),
        ("Network Security Protocols (TLS/IPSec)", "Network Security", 3),
        ("Firewalls & IDS/IPS", "Network Security", 2),
        ("Network Attacks & Mitigations", "Network Security", 3),
    ],
}

# code -> [(concept_name, prerequisite_name), ...]
PREREQUISITES: dict[str, list[tuple[str, str]]] = {
    "CYFOR": [
        ("Chain of Custody", "Digital Evidence Fundamentals"),
        ("Forensic Imaging & Write-Blocking", "Chain of Custody"),
        ("File Systems & Metadata", "Forensic Imaging & Write-Blocking"),
        ("File Carving & Data Recovery", "File Systems & Metadata"),
        ("Memory Forensics", "File Systems & Metadata"),
        ("Network Forensics", "File Systems & Metadata"),
        ("Timeline Analysis & Event Reconstruction", "File Carving & Data Recovery"),
        ("Timeline Analysis & Event Reconstruction", "Memory Forensics"),
        ("Timeline Analysis & Event Reconstruction", "Network Forensics"),
        ("Anti-Forensics Techniques", "Timeline Analysis & Event Reconstruction"),
        ("Reporting & Legal/Ethical Considerations", "Anti-Forensics Techniques"),
    ],
    "CRYPTNET": [
        ("Classical Ciphers", "Modular Arithmetic & Number Theory"),
        ("Symmetric-Key Encryption (DES/AES)", "Classical Ciphers"),
        ("Cryptographic Hash Functions", "Modular Arithmetic & Number Theory"),
        ("Public-Key Cryptography (RSA, Diffie-Hellman)", "Modular Arithmetic & Number Theory"),
        ("Digital Signatures & PKI", "Public-Key Cryptography (RSA, Diffie-Hellman)"),
        ("Digital Signatures & PKI", "Cryptographic Hash Functions"),
        ("Authentication Protocols", "Digital Signatures & PKI"),
        ("Network Security Protocols (TLS/IPSec)", "Authentication Protocols"),
        ("Network Security Protocols (TLS/IPSec)", "Symmetric-Key Encryption (DES/AES)"),
        ("Firewalls & IDS/IPS", "Network Security Protocols (TLS/IPSec)"),
        ("Network Attacks & Mitigations", "Firewalls & IDS/IPS"),
    ],
}

# Suggested Socratic Debate prompts for each subject - not DB-seeded (debate
# topics are entered live in the debate UI, there's no table for them), just
# documented here for whoever runs the first session.
SUGGESTED_DEBATE_TOPICS = {
    "CYFOR": [
        "Should companies be legally required to pay ransomware demands?",
        "Is evidence obtained via a forensic tool with no independent validation admissible in court?",
    ],
    "CRYPTNET": [
        "Is a government-mandated encryption backdoor for law enforcement ever justifiable?",
        "Should end-to-end encrypted messaging apps be required to support lawful intercept?",
    ],
}


async def seed_cyber_subjects():
    async with async_session() as db:
        for code, name, description in SUBJECTS:
            result = await db.execute(select(Subject).where(Subject.code == code))
            subject = result.scalar_one_or_none()
            if subject:
                print(f"  Subject {code} already exists, reusing")
            else:
                subject = Subject(code=code, name=name, description=description)
                db.add(subject)
                await db.flush()
                print(f"  Created subject: {code} - {name}")

            concept_map: dict[str, Concept] = {}
            for concept_name, chapter, difficulty in CONCEPTS[code]:
                existing = await db.execute(
                    select(Concept).where(
                        Concept.subject_id == subject.id,
                        Concept.name == concept_name,
                    )
                )
                concept = existing.scalar_one_or_none()
                if not concept:
                    concept = Concept(
                        subject_id=subject.id,
                        name=concept_name,
                        chapter=chapter,
                        difficulty_tier=difficulty,
                    )
                    db.add(concept)
                    await db.flush()
                concept_map[concept_name] = concept

            print(f"    {len(concept_map)} concepts ready for {code}")

            edge_count = 0
            for concept_name, prereq_name in PREREQUISITES[code]:
                tgt = concept_map[concept_name]
                src = concept_map[prereq_name]
                existing_edge = await db.execute(
                    select(ConceptPrerequisite).where(
                        ConceptPrerequisite.concept_id == tgt.id,
                        ConceptPrerequisite.prerequisite_id == src.id,
                    )
                )
                if not existing_edge.scalar_one_or_none():
                    db.add(ConceptPrerequisite(concept_id=tgt.id, prerequisite_id=src.id, strength=1.0))
                    edge_count += 1

            print(f"    {edge_count} new prerequisite edges added for {code}")

        await db.commit()
        print("\nDone. Suggested Socratic Debate topics (enter these live in the Debate Arena):")
        for code, topics in SUGGESTED_DEBATE_TOPICS.items():
            print(f"  {code}:")
            for t in topics:
                print(f"    - {t}")


if __name__ == "__main__":
    asyncio.run(seed_cyber_subjects())
