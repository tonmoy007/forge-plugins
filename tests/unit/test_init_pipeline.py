"""Tests for scripts/init-pipeline.sh"""
import os
import subprocess
import tempfile

SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../scripts/init-pipeline.sh"))

EXPECTED_DIRS = [
    "pipeline/01-srs",
    "pipeline/02-product-ux/wireframes",
    "pipeline/03-architecture/adr",
    "pipeline/04-spec",
    "pipeline/05-plan",
    "pipeline/06-implementation",
    "pipeline/07-evaluation",
    "pipeline/08-deploy",
    "pipeline/09-monitor",
    "pipeline/10-feedback",
    "pipeline/11-resolve",
    "pipeline/12-release",
    "tasks",
    ".forge/sessions",
]

EXPECTED_FILES = [
    "pipeline/state.md",
    "tasks/todo.md",
    "tasks/lessons.md",
    ".forge/lessons.yaml",
    ".forge/patterns.jsonl",
]


def run_script(cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", SCRIPT], cwd=cwd, capture_output=True, text=True)


def test_creates_all_directories_on_empty_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_script(tmpdir)
        assert result.returncode == 0, f"Script failed:\n{result.stderr}"
        for d in EXPECTED_DIRS:
            assert os.path.isdir(os.path.join(tmpdir, d)), f"Missing directory: {d}"


def test_creates_all_files_on_empty_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        run_script(tmpdir)
        for f in EXPECTED_FILES:
            assert os.path.isfile(os.path.join(tmpdir, f)), f"Missing file: {f}"


def test_state_md_has_valid_frontmatter():
    with tempfile.TemporaryDirectory() as tmpdir:
        run_script(tmpdir)
        content = open(os.path.join(tmpdir, "pipeline/state.md")).read()
        assert content.startswith("---"), "state.md must open with YAML frontmatter"
        assert "schema_version: 1" in content
        assert "current_stage: 0" in content
        assert "project_type: unknown" in content


def test_idempotent_does_not_overwrite_state_md():
    with tempfile.TemporaryDirectory() as tmpdir:
        run_script(tmpdir)
        state_path = os.path.join(tmpdir, "pipeline/state.md")
        with open(state_path, "a") as f:
            f.write("\n# SENTINEL_LINE\n")

        result = run_script(tmpdir)
        assert result.returncode == 0, f"Second run failed:\n{result.stderr}"
        assert "SENTINEL_LINE" in open(state_path).read(), "state.md was overwritten on second run"


def test_does_not_overwrite_existing_tasks_todo():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "tasks"), exist_ok=True)
        todo_path = os.path.join(tmpdir, "tasks/todo.md")
        with open(todo_path, "w") as f:
            f.write("# My Custom Todo\n")

        run_script(tmpdir)
        assert "My Custom Todo" in open(todo_path).read(), "Existing tasks/todo.md was overwritten"
