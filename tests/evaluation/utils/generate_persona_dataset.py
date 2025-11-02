"""
Generate evaluation dataset from persona prompts.

This script loads a persona, iterates through the SRM catalog, and generates
realistic questions using LLM based on the persona's characteristics.
"""

import argparse
import asyncio
import csv
import json
import logging
import sys
from pathlib import Path
from typing import List, Dict, Optional

from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.kernel_builder import create_kernel
from tests.evaluation.utils.persona_loader import PersonaLoader, Persona
from tests.evaluation.utils.question_generator import QuestionGenerator


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_srm_catalog(csv_path: str) -> List[Dict]:
    """
    Load SRM catalog from CSV file.

    Args:
        csv_path: Path to SRM catalog CSV

    Returns:
        List of SRM dictionaries
    """
    srms = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            srms.append(row)
    return srms


def select_persona_interactive(personas: List[Persona]) -> Optional[Persona]:
    """
    Display menu and let user select persona.

    Args:
        personas: List of available personas

    Returns:
        Selected Persona or None if cancelled
    """
    print("\n" + "=" * 60)
    print("PERSONA-BASED DATASET GENERATION")
    print("=" * 60)
    print("\nAvailable personas:\n")

    for i, persona in enumerate(personas, 1):
        level = persona.technical_level.capitalize()
        print(f"  {i}. {persona.name} ({level})")

    print()

    while True:
        try:
            choice = input(f"Select persona [1-{len(personas)}] (or 'q' to quit): ").strip()

            if choice.lower() == 'q':
                return None

            choice_num = int(choice)
            if 1 <= choice_num <= len(personas):
                return personas[choice_num - 1]
            else:
                print(f"Please enter a number between 1 and {len(personas)}")
        except ValueError:
            print("Invalid input. Please enter a number.")


async def generate_dataset(
    persona: Persona,
    srms: List[Dict],
    output_path: Path,
    limit: Optional[int] = None
):
    """
    Generate dataset for a persona.

    Args:
        persona: Selected persona
        srms: List of SRM data
        output_path: Where to save JSONL output
        limit: Optional limit on number of SRMs to process
    """
    print(f"\n{'=' * 60}")
    print(f"Generating questions for: {persona.name}")
    print(f"{'=' * 60}\n")

    # Load environment and create kernel
    load_dotenv()
    kernel = create_kernel()

    # Create question generator
    generator = QuestionGenerator(kernel, max_retries=3, retry_delay=2)

    # Process SRMs
    srms_to_process = srms[:limit] if limit else srms
    total = len(srms_to_process)

    print(f"Processing {total} SRMs...\n")

    all_questions = []
    success_count = 0
    failure_count = 0
    failed_srms = []

    for idx, srm in enumerate(srms_to_process, 1):
        srm_id = srm['SRM_ID']

        try:
            # Generate questions
            questions = await generator.generate_questions(persona, srm)

            # Add metadata to each question
            for question in questions:
                entry = {
                    "query": question['query'],
                    "srm_id": srm_id,
                    "expected_srm": srm_id,
                    "ground_truth_context": f"{srm['Name']}: {srm['Description']}",
                    "expected_behavior": "answer",
                    "query_type": question['query_type'],
                    "persona": {
                        "id": persona.id,
                        "name": persona.name,
                        "technical_level": persona.technical_level
                    },
                    "notes": f"{question['query_type'].capitalize()} request from {persona.id} persona for {srm_id}"
                }
                all_questions.append(entry)

            success_count += 1

            # Progress update every 10 SRMs
            if idx % 10 == 0:
                print(f"  Progress: {idx}/{total} ({success_count} success, {failure_count} failed)")

        except Exception as e:
            failure_count += 1
            failed_srms.append(srm_id)
            logger.error(f"Failed to generate questions for {srm_id}: {e}")

    # Write output
    print(f"\nWriting dataset to: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        for question in all_questions:
            f.write(json.dumps(question) + '\n')

    # Summary
    print(f"\n{'=' * 60}")
    print("GENERATION COMPLETE")
    print(f"{'=' * 60}")
    print(f"Total SRMs processed: {total}")
    print(f"  Successful: {success_count}")
    print(f"  Failed: {failure_count}")
    print(f"Questions generated: {len(all_questions)}")
    print(f"Output file: {output_path}")

    if failed_srms:
        print(f"\nFailed SRMs: {', '.join(failed_srms)}")

    print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate persona-based evaluation dataset"
    )
    parser.add_argument(
        '--persona',
        type=str,
        help='Persona ID to use (skips interactive selection)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of SRMs to process (for testing)'
    )
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompt (for automation)'
    )

    args = parser.parse_args()

    # Paths
    project_root = Path(__file__).parent.parent.parent.parent
    prompts_dir = Path(__file__).parent.parent / "prompts"
    catalog_path = project_root / "data" / "srm_index.csv"
    datasets_dir = Path(__file__).parent.parent / "datasets"

    # Load personas
    loader = PersonaLoader(prompts_dir)
    personas = loader.discover_personas()

    if not personas:
        print(f"[ERROR] No personas found in {prompts_dir}")
        print("Please create persona markdown files first.")
        sys.exit(1)

    # Select persona
    if args.persona:
        # Direct selection by ID
        selected = next((p for p in personas if p.id == args.persona), None)
        if not selected:
            print(f"[ERROR] Persona '{args.persona}' not found")
            print(f"Available: {', '.join(p.id for p in personas)}")
            sys.exit(1)
    else:
        # Interactive selection
        selected = select_persona_interactive(personas)
        if not selected:
            print("Cancelled by user.")
            sys.exit(0)

    # Load SRM catalog
    print(f"\nLoading SRM catalog from: {catalog_path}")
    srms = load_srm_catalog(str(catalog_path))
    print(f"Loaded {len(srms)} SRMs")

    # Confirm
    total_to_process = args.limit if args.limit else len(srms)
    expected_questions = total_to_process * 3

    print(f"\nWill generate ~{expected_questions} questions for '{selected.name}'")

    if not args.yes:
        confirm = input("Continue? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Cancelled.")
            sys.exit(0)

    # Output path
    output_path = datasets_dir / f"qa_{selected.id}.jsonl"

    # Generate
    asyncio.run(generate_dataset(selected, srms, output_path, args.limit))


if __name__ == "__main__":
    main()
