import re
from typing import List


def parse_question_content(clipboard_content: str) -> List[str]:
    """Extract [File: ...] audit questions from JSON-like or Markdown output."""
    quoted_pattern = r'"(\[File:.*?)"'
    questions = re.findall(quoted_pattern, clipboard_content, flags=re.DOTALL)
    if questions:
        return [question.strip() for question in questions]

    markdown_pattern = (
        r'(\[File:.*?)(?=(?:\r?\n)+\s*(?:[-*]\s+|\d+[.)]\s+)?\[File:|\Z)'
    )
    return [
        question.strip()
        for question in re.findall(markdown_pattern, clipboard_content, flags=re.DOTALL)
        if question.strip()
    ]
