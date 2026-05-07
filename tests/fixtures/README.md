# Test Fixtures

> Shared test data for unit and integration tests.

## Files

- `sample-state.md` — A pipeline state.md frozen at Stage 6, used by hook tests
- `sample-lessons.md` — A lessons.md with diverse entries (different stages, tags, projects)
- `sample-transcript.json` — A Claude Code transcript with corrections, used by lesson-extractor tests
- `sample-patterns.jsonl` — Pre-populated patterns for skill-miner tests

## Usage

```python
# In a test
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures"

def test_session_start_with_stage_6(tmp_path):
    # Copy fixture to a tmp dir to avoid mutating the fixture
    (tmp_path / "pipeline").mkdir()
    shutil.copy(FIXTURE_DIR / "sample-state.md", tmp_path / "pipeline/state.md")

    # Run hook
    result = run_hook("session-start.py", cwd=tmp_path)

    # Assert
    assert "[Forge] Pipeline: Stage 6" in result.stdout
```

## Adding New Fixtures

1. Add the file to this directory
2. Document it in this README
3. Reference it from tests by relative path

## Don't

- Don't write to fixtures from tests (always copy to tmp_path first)
- Don't put real-world sensitive data in fixtures
- Don't make fixtures depend on each other (each should stand alone)
