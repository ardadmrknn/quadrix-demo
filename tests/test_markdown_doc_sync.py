from __future__ import annotations

import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.sync_markdown_docs import collect_outdated_docs


def test_generated_markdown_docs_are_synced():
    outdated = collect_outdated_docs()
    assert not outdated, (
        'Generated Markdown docs are out of sync. Run '
        '`python tools/sync_markdown_docs.py` for: '
        + ', '.join(path.relative_to(ROOT_DIR).as_posix() for path in outdated)
    )