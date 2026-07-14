import shutil
import time
from pathlib import Path
import sys

from questions_generator import GetQuestions

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import os
import uuid

from bot_runtime import batch_limit
from question_report_parser import parse_question_content


def get_scope_questions_pending():
    """
    Get all URLs from JSON files in the automation_pending directory.

    Returns:
        list: A list of URLs found in all JSON files
    """
    scope_questions_pending_dir = os.environ.get("SCOPE_QUESTIONS_PENDING_DIR", "scope_questions_pending")
    report_items = []

    # Ensure directory exists
    if not os.path.exists(scope_questions_pending_dir):
        print(f"Directory {scope_questions_pending_dir} does not exist")
        return report_items

    # Get all JSON files in the directory
    json_files = list(Path(scope_questions_pending_dir).glob("*.json"))

    if not json_files:
        print(f"No JSON files found in {scope_questions_pending_dir}")
        return report_items

    # Process each JSON file
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

                # Handle both list of questions and single question objects
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and 'url' in item:
                            report_items.append(item)
                elif isinstance(data, dict) and 'url' in data:
                    report_items.append(data)

        except json.JSONDecodeError as e:
            print(f"Error parsing {json_file}: {e}")
        except Exception as e:
            print(f"Error processing {json_file}: {e}")

    return report_items


def save_stored_response(response_text):
    questions = parse_question_content(response_text)
    if not questions:
        raise RuntimeError("Stored DeepWiki response contains no parseable questions")

    question_directory = Path(os.environ.get("QUESTION_DIR", "question"))
    question_directory.mkdir(parents=True, exist_ok=True)
    for offset in range(0, len(questions), 25):
        chunk = questions[offset:offset + 25]
        output = question_directory / f"{uuid.uuid4().hex}.json"
        output.write_text(
            json.dumps(chunk, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"Saved {len(chunk)} questions to {output}")
    return len(questions)


def move_files_back_to_scope_questions():
    """Move all files from automation_pending back to automation folder"""
    scope_questions_dir = os.environ.get("SCOPE_QUESTIONS_DIR", "scope_questions")
    scope_questions_pending_dir = os.environ.get("SCOPE_QUESTIONS_PENDING_DIR", "scope_questions_pending")

    moved_files = []

    try:
        # Ensure both directories exist
        os.makedirs(scope_questions_dir, exist_ok=True)
        os.makedirs(scope_questions_pending_dir, exist_ok=True)

        # Get all files in automation_pending
        pending_files = list(Path(scope_questions_pending_dir).glob("*"))

        for file_path in pending_files:
            try:
                # Create destination path
                dest_path = os.path.join(scope_questions_dir, file_path.name)

                # Handle filename conflicts
                if os.path.exists(dest_path):
                    # Append a timestamp to make filename unique
                    base_name = file_path.stem
                    extension = file_path.suffix
                    timestamp = int(time.time())
                    dest_path = os.path.join(scope_questions_dir, f"{base_name}_{timestamp}{extension}")

                # Move the file
                shutil.move(str(file_path), dest_path)
                moved_files.append(dest_path)

            except Exception as e:
                print(f"Error moving {file_path} back to automation: {e}")
                continue

        if moved_files:
            print(f"Moved {len(moved_files)} files back to {scope_questions_dir}")
        return moved_files

    except Exception as e:
        print(f"Error in move_files_back_to_automation: {e}")
        return []



def main():
    report = None
    try:
        pending_items = get_scope_questions_pending()
        total = len(pending_items)

        if total == 0:
            raise RuntimeError("No pending reports to generate")

        print(f"Found {total} stored DeepWiki reports")

        counter = 0
        generated_questions = 0
        failures = []
        # BOT_SMOKE_LIMIT limits how many input files are moved into pending.
        # Every record in each selected file must be processed to avoid losing
        # the unprocessed half of a scope file.
        for i, item in enumerate(pending_items):
            url = item["url"]
            try:
                print(f"[{i + 1}/{total}] Generating report for: {url}")
                response_text = item.get("response", "")
                if response_text:
                    generated_questions += save_stored_response(response_text)
                else:
                    if report is None:
                        report = GetQuestions(teardown=True)
                    generated_questions += report.get_questions(url, item.get("question"))
                counter += 1
            except Exception as exc:
                failures.append(f"{url}: {exc}")
                print(f"Report generation failed: {failures[-1]}")

        if failures:
            raise RuntimeError(
                f"{len(failures)} of {counter + len(failures)} reports failed: "
                + " | ".join(failures)
            )
        if generated_questions == 0:
            raise RuntimeError("Report generation produced zero audit questions")

        print(
            f"\n=== Completed {counter} reports with "
            f"{generated_questions} audit questions ==="
        )

    except Exception as e:
        print(f"\n!!! ERROR: {e}")
        print("Attempting to move files back to automation directory...")
        moved = move_files_back_to_scope_questions()
        if moved:
            print(f"Moved {len(moved)} files back to automation directory")
        else:
            print("No files were moved back")
        raise
    finally:
        if report is not None:
            report.driver.quit()



if __name__ == '__main__':
    main()
