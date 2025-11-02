"""
Generate evaluation dataset from SRM catalog.

This script reads the SRM catalog and generates diverse test queries including:
- Direct requests for each SRM
- Technology-specific queries
- Problem-based queries
- Clarification triggers (vague queries)
- Rejection triggers (out-of-scope queries)
"""

import csv
import json
import random
from pathlib import Path
from typing import List, Dict

# Query templates for different query types
DIRECT_TEMPLATES = [
    "I need {name_lower}",
    "Can you help me with {name_lower}?",
    "What SRM covers {name_lower}?",
    "Show me {name_lower}",
    "I'm looking for {name_lower}",
]

PROBLEM_TEMPLATES = [
    "I'm having issues with {keywords}",
    "My {keywords} isn't working correctly",
    "How do I troubleshoot {keywords} problems?",
    "I need help fixing {keywords}",
]

TECH_TEMPLATES = [
    "What services do you have for {tech}?",
    "I need help with {tech}",
    "Do you support {tech}?",
    "Show me {tech} related SRMs",
]


def load_srm_catalog(csv_path: str) -> List[Dict]:
    """Load SRM catalog from CSV file."""
    srms = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            srms.append(row)
    return srms


def extract_keywords(description: str) -> str:
    """Extract key terms from description for problem-based queries."""
    # Simple keyword extraction - take first meaningful phrase
    parts = description.split('.')
    if parts:
        first_part = parts[0].lower()
        # Extract main action/subject
        words = first_part.split()[:5]  # First 5 words
        return ' '.join(words).replace('deploy and configure', '').replace('implement', '').strip()
    return description[:50].lower()


def generate_direct_queries(srm: Dict) -> List[Dict]:
    """Generate direct request queries for an SRM."""
    queries = []
    name_lower = srm['Name'].lower()

    # Create 1-2 direct queries per SRM
    template = random.choice(DIRECT_TEMPLATES)
    query = template.format(name_lower=name_lower)

    queries.append({
        "query": query,
        "srm_id": srm['SRM_ID'],
        "expected_srm": srm['SRM_ID'],
        "ground_truth_context": f"{srm['Name']}: {srm['Description']}",
        "expected_behavior": "answer",
        "query_type": "direct",
        "notes": f"Direct request for {srm['SRM_ID']}"
    })

    return queries


def generate_tech_queries(srms: List[Dict]) -> List[Dict]:
    """Generate technology-specific queries."""
    queries = []

    # Group SRMs by technology
    tech_map = {}
    for srm in srms:
        techs = [t.strip() for t in srm['TechnologiesTeamWorksWith'].split(',')]
        for tech in techs:
            if tech not in tech_map:
                tech_map[tech] = []
            tech_map[tech].append(srm)

    # Generate queries for popular technologies (those with 2+ SRMs)
    popular_techs = {tech: srms for tech, srms in tech_map.items() if len(srms) >= 2}

    for tech, tech_srms in list(popular_techs.items())[:10]:  # Limit to 10 tech queries
        query = f"What services do you have for {tech}?"
        relevant_srms = [s['SRM_ID'] for s in tech_srms]

        queries.append({
            "query": query,
            "srm_id": relevant_srms[0],  # Primary match
            "expected_srm": relevant_srms[0],
            "ground_truth_context": f"SRMs related to {tech}: " + ", ".join([f"{s['SRM_ID']} ({s['Name']})" for s in tech_srms[:3]]),
            "expected_behavior": "answer",
            "query_type": "technology",
            "notes": f"Technology-specific query for {tech}"
        })

    return queries


def generate_problem_queries(srms: List[Dict]) -> List[Dict]:
    """Generate problem-based troubleshooting queries."""
    queries = []

    # Focus on Support and Services type SRMs
    support_srms = [s for s in srms if 'Support' in s.get('Type', '') or 'Troubleshoot' in s['Name']]

    for srm in support_srms[:15]:  # Limit to 15 problem queries
        keywords = extract_keywords(srm['Description'])
        if len(keywords) < 10:  # Skip if too short
            continue

        template = random.choice(PROBLEM_TEMPLATES)
        query = template.format(keywords=keywords)

        queries.append({
            "query": query,
            "srm_id": srm['SRM_ID'],
            "expected_srm": srm['SRM_ID'],
            "ground_truth_context": f"{srm['Name']}: {srm['Description']}",
            "expected_behavior": "answer",
            "query_type": "problem",
            "notes": f"Problem-based query for {srm['SRM_ID']}"
        })

    return queries


def generate_clarification_queries() -> List[Dict]:
    """Generate vague queries that should trigger clarification."""
    queries = [
        {
            "query": "I need help with my computer",
            "srm_id": None,
            "expected_srm": None,
            "ground_truth_context": "Vague query - multiple SRMs could apply",
            "expected_behavior": "clarify",
            "query_type": "clarification",
            "notes": "Vague query should trigger clarification"
        },
        {
            "query": "network",
            "srm_id": None,
            "expected_srm": None,
            "ground_truth_context": "Too vague - network could mean many things",
            "expected_behavior": "clarify",
            "query_type": "clarification",
            "notes": "Single word query should trigger clarification"
        },
        {
            "query": "help",
            "srm_id": None,
            "expected_srm": None,
            "ground_truth_context": "Generic help request",
            "expected_behavior": "clarify",
            "query_type": "clarification",
            "notes": "Generic help should trigger clarification"
        },
        {
            "query": "I need something",
            "srm_id": None,
            "expected_srm": None,
            "ground_truth_context": "Vague request without specifics",
            "expected_behavior": "clarify",
            "query_type": "clarification",
            "notes": "Vague 'something' should trigger clarification"
        },
        {
            "query": "Can you assist?",
            "srm_id": None,
            "expected_srm": None,
            "ground_truth_context": "Generic assistance request",
            "expected_behavior": "clarify",
            "query_type": "clarification",
            "notes": "Generic assistance should trigger clarification"
        },
    ]
    return queries


def generate_rejection_queries() -> List[Dict]:
    """Generate out-of-scope queries that should be rejected."""
    queries = [
        {
            "query": "What's the weather today?",
            "srm_id": None,
            "expected_srm": None,
            "ground_truth_context": "Out of scope - weather information",
            "expected_behavior": "reject",
            "query_type": "rejection",
            "notes": "Out-of-scope query about weather"
        },
        {
            "query": "Tell me a joke",
            "srm_id": None,
            "expected_srm": None,
            "ground_truth_context": "Out of scope - entertainment",
            "expected_behavior": "reject",
            "query_type": "rejection",
            "notes": "Out-of-scope entertainment request"
        },
        {
            "query": "What is the capital of France?",
            "srm_id": None,
            "expected_srm": None,
            "ground_truth_context": "Out of scope - general knowledge",
            "expected_behavior": "reject",
            "query_type": "rejection",
            "notes": "Out-of-scope general knowledge query"
        },
        {
            "query": "Can you order me a pizza?",
            "srm_id": None,
            "expected_srm": None,
            "ground_truth_context": "Out of scope - food ordering",
            "expected_behavior": "reject",
            "query_type": "rejection",
            "notes": "Out-of-scope food ordering"
        },
        {
            "query": "Write me a Python function to sort a list",
            "srm_id": None,
            "expected_srm": None,
            "ground_truth_context": "Out of scope - code generation",
            "expected_behavior": "reject",
            "query_type": "rejection",
            "notes": "Out-of-scope code generation"
        },
    ]
    return queries


def main():
    """Generate comprehensive evaluation dataset."""
    print("=" * 80)
    print("GENERATING COMPREHENSIVE EVALUATION DATASET")
    print("=" * 80)

    # Paths
    project_root = Path(__file__).parent.parent.parent
    catalog_path = project_root / "data" / "srm_index.csv"
    output_path = Path(__file__).parent / "datasets" / "qa_comprehensive_set.jsonl"

    print(f"\n[*] Loading SRM catalog from: {catalog_path}")
    srms = load_srm_catalog(str(catalog_path))
    print(f"[+] Loaded {len(srms)} SRMs")

    # Generate different query types
    all_queries = []

    print("\n[*] Generating direct queries...")
    direct_queries = []
    for srm in srms:
        direct_queries.extend(generate_direct_queries(srm))
    all_queries.extend(direct_queries)
    print(f"[+] Generated {len(direct_queries)} direct queries")

    print("\n[*] Generating technology-specific queries...")
    tech_queries = generate_tech_queries(srms)
    all_queries.extend(tech_queries)
    print(f"[+] Generated {len(tech_queries)} technology queries")

    print("\n[*] Generating problem-based queries...")
    problem_queries = generate_problem_queries(srms)
    all_queries.extend(problem_queries)
    print(f"[+] Generated {len(problem_queries)} problem-based queries")

    print("\n[*] Generating clarification triggers...")
    clarification_queries = generate_clarification_queries()
    all_queries.extend(clarification_queries)
    print(f"[+] Generated {len(clarification_queries)} clarification queries")

    print("\n[*] Generating rejection triggers...")
    rejection_queries = generate_rejection_queries()
    all_queries.extend(rejection_queries)
    print(f"[+] Generated {len(rejection_queries)} rejection queries")

    # Write to JSONL
    print(f"\n[*] Writing dataset to: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        for query in all_queries:
            f.write(json.dumps(query) + '\n')

    print(f"[+] Wrote {len(all_queries)} total test cases")

    # Print summary
    print("\n" + "=" * 80)
    print("DATASET SUMMARY")
    print("=" * 80)
    print(f"Total test cases: {len(all_queries)}")
    print(f"  - Direct queries: {len(direct_queries)}")
    print(f"  - Technology queries: {len(tech_queries)}")
    print(f"  - Problem-based queries: {len(problem_queries)}")
    print(f"  - Clarification triggers: {len(clarification_queries)}")
    print(f"  - Rejection triggers: {len(rejection_queries)}")
    print("\n[+] Dataset generation complete!")


if __name__ == "__main__":
    main()
