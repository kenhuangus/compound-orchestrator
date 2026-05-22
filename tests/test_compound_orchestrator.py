import datetime as dt
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import compound_orchestrator as co  # noqa: E402


def complete_two_round_review(root: Path, task_id: str) -> None:
    for stage in co.CROSS_REVIEW_STAGES:
        co.cross_review(
            root,
            task_id=task_id,
            reviewer_tool="codex" if "review" in stage or stage == "final-acceptance" else "claude",
            author_tool="claude" if "review" in stage or stage == "final-acceptance" else "codex",
            summary=f"Test fixture completed {stage} across all six planning artifacts.",
            stage=stage,
        )


class CompoundOrchestratorTests(unittest.TestCase):
    def test_init_creates_expected_project_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            report = co.init_project(root)
            ok, failures = co.check_project(root)

            self.assertTrue(ok, failures)
            self.assertIn("README.md", report.created)
            self.assertIn("AGENTS.md", report.created)
            self.assertTrue((root / "README.md").is_file())
            self.assertTrue((root / ".claude/commands/compound-init.md").is_file())
            self.assertTrue((root / ".claude/commands/compound-start.md").is_file())
            self.assertTrue((root / ".claude/commands/compound-team-start.md").is_file())
            self.assertTrue((root / ".claude/commands/compound-harness-check.md").is_file())
            self.assertTrue((root / ".claude/commands/compound-claim.md").is_file())
            self.assertTrue((root / ".claude/commands/compound-cross-review.md").is_file())
            self.assertTrue((root / ".claude/agents/compound-reviewer.md").is_file())
            self.assertTrue((root / ".claude/agents/compound-cross-tool-reviewer.md").is_file())
            self.assertTrue((root / "CODEBASE_MAP.md").is_file())
            self.assertTrue((root / ".agent-loop/harness-checklist.md").is_file())
            self.assertTrue((root / ".agent-loop/readme-maintenance.md").is_file())
            self.assertTrue((root / ".agent-loop/module-claude-template.md").is_file())
            self.assertTrue((root / ".agent-loop/path-scoped-skill-template.md").is_file())
            self.assertTrue((root / ".agent-loop/lsp-mcp-roadmap.md").is_file())
            self.assertTrue((root / ".agent-loop/harness-ownership.md").is_file())
            self.assertTrue((root / ".agent-loop/team-topology.md").is_file())
            self.assertTrue((root / ".agent-loop/codex-parallel-contract.md").is_file())
            self.assertTrue((root / ".agent-loop/cross-tool-protocol.md").is_file())
            self.assertTrue((root / ".agent-loop/core-planning-artifacts.md").is_file())
            self.assertTrue((root / ".agent-loop/two-round-review-protocol.md").is_file())
            self.assertTrue((root / ".agent-loop/parallel-agent-team-protocol.md").is_file())
            self.assertTrue((root / ".agent-loop/deliverables-checklist.md").is_file())
            for artifact in co.CORE_PLANNING_ARTIFACTS:
                self.assertTrue((root / artifact).is_file(), artifact)
            self.assertTrue((root / "architecture.excalidraw").is_file())
            self.assertTrue((root / ".agent-loop/coordination/ownership.json").is_file())
            self.assertTrue((root / "scripts/compound_orchestrator.py").is_file())
            self.assertTrue((root / "scripts/verify.py").is_file())
            self.assertTrue((root / "scripts/verify.ps1").is_file())
            self.assertTrue((root / "scripts/verify.sh").is_file())
            settings = json.loads((root / ".claude/settings.json").read_text(encoding="utf-8"))
            self.assertEqual(settings["env"][co.CLAUDE_AGENT_TEAM_ENV], "1")
            for deny_rule in co.DEFAULT_PERMISSION_DENY:
                self.assertIn(deny_rule, settings["permissions"]["deny"])
            self.assertIn(co.MANAGED_START, (root / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertIn(co.MANAGED_START, (root / "CLAUDE.md").read_text(encoding="utf-8"))
            self.assertIn(co.MANAGED_START, (root / "README.md").read_text(encoding="utf-8"))

    def test_core_planning_artifacts_have_architecture_and_spec_test_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            co.init_project(root)

            architecture = (root / "architecture.html").read_text(encoding="utf-8")
            tests = (root / "test-cases.html").read_text(encoding="utf-8")
            diagram = json.loads((root / "architecture.excalidraw").read_text(encoding="utf-8"))

            self.assertIn("architecture.excalidraw", architecture)
            self.assertEqual(diagram["type"], "excalidraw")
            for phrase in ["spec.html", "Happy paths", "Edge cases", "Error cases", "Performance cases", "User workflow cases", "Acceptance criteria"]:
                self.assertIn(phrase, tests)

    def test_task_gate_requires_two_round_cross_review_and_responses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            co.init_project(root)
            task_id, _ = co.start_task(root, "Require two reviews", today=dt.date(2026, 5, 21))
            co.learn(root, kind="review", title="Review require two reviews", summary="Local review done.", task_id=task_id)
            co.learn(root, kind="compound", title="Compound require two reviews", summary="Learning done.", task_id=task_id)
            co.cross_review(
                root,
                task_id=task_id,
                reviewer_tool="codex",
                author_tool="claude",
                summary="Round one only.",
                stage="round-1-review",
            )

            ok, failures = co.check_project(root, task_id=task_id)

            self.assertFalse(ok)
            self.assertIn(f"Task gate missing file: docs/cross-reviews/{task_id}/round-1-response.md", failures)
            self.assertIn(f"Task gate missing file: docs/cross-reviews/{task_id}/final-acceptance.md", failures)

            complete_two_round_review(root, task_id)
            ok, failures = co.check_project(root, task_id=task_id)
            self.assertTrue(ok, failures)

    def test_init_preserves_existing_docs_and_appends_managed_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text("# Existing Agents\n\nKeep this line.\n", encoding="utf-8")
            (root / "CLAUDE.md").write_text("# Existing Claude\n\nKeep this too.\n", encoding="utf-8")
            (root / "README.md").write_text("# Existing README\n\nKeep this readme line.\n", encoding="utf-8")

            co.init_project(root)

            agents = (root / "AGENTS.md").read_text(encoding="utf-8")
            claude = (root / "CLAUDE.md").read_text(encoding="utf-8")
            readme = (root / "README.md").read_text(encoding="utf-8")
            self.assertIn("Keep this line.", agents)
            self.assertIn("Keep this too.", claude)
            self.assertIn("Keep this readme line.", readme)
            self.assertIn(co.MANAGED_START, agents)
            self.assertIn(co.MANAGED_END, claude)
            self.assertIn(co.MANAGED_START, readme)

    def test_init_preserves_existing_claude_settings_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings_path = root / ".claude/settings.json"
            settings_path.parent.mkdir(parents=True)
            settings_path.write_text(
                json.dumps(
                    {
                        "env": {
                            "EXISTING_FLAG": "kept",
                        },
                        "permissions": {
                            "allow": ["Bash(npm test)"],
                            "deny": ["Read(./private/**)"],
                        },
                    }
                ),
                encoding="utf-8",
            )

            co.init_project(root)

            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(settings["env"]["EXISTING_FLAG"], "kept")
            self.assertEqual(settings["env"][co.CLAUDE_AGENT_TEAM_ENV], "1")
            self.assertEqual(settings["permissions"]["allow"], ["Bash(npm test)"])
            self.assertIn("Read(./private/**)", settings["permissions"]["deny"])
            self.assertIn("Read(./node_modules/**)", settings["permissions"]["deny"])

    def test_check_fails_before_init_and_passes_after_init(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            ok, failures = co.check_project(root)
            self.assertFalse(ok)
            self.assertGreater(len(failures), 0)

            co.init_project(root)
            ok, failures = co.check_project(root)
            self.assertTrue(ok, failures)

    def test_start_and_learn_satisfy_task_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            co.init_project(root)

            task_id, report = co.start_task(
                root,
                "Add compound loop",
                today=dt.date(2026, 5, 21),
            )
            self.assertEqual(task_id, "2026-05-21-add-compound-loop")
            self.assertIn(f"docs/plans/{task_id}.md", report.created)

            ok, failures = co.check_project(root, task_id=task_id)
            self.assertFalse(ok)
            self.assertIn(f"Task gate missing file: docs/reviews/{task_id}.md", failures)
            self.assertIn(f"Task gate missing file: docs/compound/{task_id}.md", failures)

            co.learn(
                root,
                kind="review",
                title="Review add compound loop",
                summary="No blocking issues.",
                task_id=task_id,
            )
            co.learn(
                root,
                kind="compound",
                title="Compound add compound loop",
                summary="The gate requires review and compound notes.",
                task_id=task_id,
            )
            complete_two_round_review(root, task_id)

            ok, failures = co.check_project(root, task_id=task_id)
            self.assertTrue(ok, failures)

    def test_team_start_creates_shared_team_run_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            co.init_project(root)

            task_id, report = co.start_team(
                root,
                "Coordinate agents",
                mode="codex-parallel-agents",
                today=dt.date(2026, 5, 21),
            )

            self.assertEqual(task_id, "2026-05-21-coordinate-agents")
            team_run = f"docs/compound/{task_id}-team-run.md"
            self.assertIn(team_run, report.created)
            text = (root / team_run).read_text(encoding="utf-8")
            self.assertIn("Mode: `codex-parallel-agents`", text)
            self.assertIn(".agent-loop/team-topology.md", text)

    def test_claims_block_cross_tool_file_conflicts_and_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            co.init_project(root)

            co.claim_scope(
                root,
                tool="claude",
                agent="claude-implementer",
                task_id="task-1",
                paths=["src/service.py"],
                intent="Claude edit",
            )
            with self.assertRaises(co.OwnershipConflict):
                co.claim_scope(
                    root,
                    tool="codex",
                    agent="codex-worker",
                    task_id="task-1",
                    paths=["src/service.py"],
                    intent="Codex edit",
                )

            claims = co.active_claims(root)
            self.assertEqual(len(claims), 1)
            self.assertEqual(claims[0]["tool"], "claude")

            released, _ = co.release_scope(root, tool="claude", agent="claude-implementer", task_id="task-1")
            self.assertEqual(released, 1)
            co.claim_scope(
                root,
                tool="codex",
                agent="codex-worker",
                task_id="task-1",
                paths=["src/service.py"],
                intent="Codex edit after release",
            )
            self.assertEqual(co.active_claims(root)[0]["tool"], "codex")

    def test_claims_accept_other_agent_runtime_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            co.init_project(root)

            co.claim_scope(root, tool="cursor", agent="cursor-worker", task_id="task-other", paths=["drafts/chapter.md"])
            with self.assertRaises(co.OwnershipConflict):
                co.claim_scope(root, tool="aider", agent="aider-worker", task_id="task-other", paths=["drafts/chapter.md"])

            review_path, _ = co.cross_review(
                root,
                task_id="task-other",
                reviewer_tool="codex",
                author_tool="cursor",
                summary="Codex reviewed Cursor-authored writing changes.",
            )
            self.assertTrue((root / review_path).is_file())

    def test_directory_claim_blocks_nested_file_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            co.init_project(root)

            co.claim_scope(root, tool="codex", agent="codex-worker", task_id="task-2", paths=["src/payments"])
            with self.assertRaises(co.OwnershipConflict):
                co.claim_scope(root, tool="claude", agent="claude-teammate", task_id="task-2", paths=["src/payments/api.py"])

    def test_check_project_fails_on_forced_active_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            co.init_project(root)

            co.claim_scope(root, tool="codex", agent="codex-worker", task_id="task-2b", paths=["src/app.py"])
            co.claim_scope(root, tool="claude", agent="claude-teammate", task_id="task-2b", paths=["src/app.py"], force=True)

            ok, failures = co.check_project(root)

            self.assertFalse(ok)
            self.assertTrue(any("Active ownership conflict" in failure for failure in failures))

    def test_cross_review_records_opposite_tool_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            co.init_project(root)
            co.claim_scope(root, tool="claude", agent="claude-teammate", task_id="task-3", paths=["app.py"])

            path, report = co.cross_review(
                root,
                task_id="task-3",
                reviewer_tool="codex",
                author_tool="claude",
                summary="Codex reviewed Claude-authored dummy code.",
            )

            self.assertIn(path, report.created)
            text = (root / path).read_text(encoding="utf-8")
            self.assertIn("Reviewer tool: `codex`", text)
            self.assertIn("Author tool: `claude`", text)
            self.assertIn("`app.py` claimed by claude/claude-teammate", text)

    def test_dummy_code_cross_tool_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "tests").mkdir()
            (root / "src/counter.py").write_text("def add_one(value):\n    return value + 1\n", encoding="utf-8")
            (root / "tests/test_counter.py").write_text(
                "import unittest\n\n"
                "from src.counter import add_one\n\n\n"
                "class CounterTests(unittest.TestCase):\n"
                "    def test_add_one(self):\n"
                "        self.assertEqual(add_one(1), 2)\n",
                encoding="utf-8",
            )
            co.init_project(root)
            task_id, _ = co.start_team(
                root,
                "Dummy cross tool workflow",
                mode="codex-parallel-agents",
                today=dt.date(2026, 5, 21),
            )

            co.claim_scope(root, tool="claude", agent="claude-implementer", task_id=task_id, paths=["src/counter.py"])
            with self.assertRaises(co.OwnershipConflict):
                co.claim_scope(root, tool="codex", agent="codex-worker", task_id=task_id, paths=["src/counter.py"])
            co.claim_scope(root, tool="codex", agent="codex-worker", task_id=task_id, paths=["tests/test_counter.py"])

            (root / "src/counter.py").write_text(
                "def add_one(value):\n"
                "    if value is None:\n"
                "        raise ValueError('value is required')\n"
                "    return value + 1\n",
                encoding="utf-8",
            )
            (root / "tests/test_counter.py").write_text(
                "import unittest\n\n"
                "from src.counter import add_one\n\n\n"
                "class CounterTests(unittest.TestCase):\n"
                "    def test_add_one(self):\n"
                "        self.assertEqual(add_one(1), 2)\n\n"
                "    def test_rejects_none(self):\n"
                "        with self.assertRaises(ValueError):\n"
                "            add_one(None)\n",
                encoding="utf-8",
            )

            codex_review, _ = co.cross_review(
                root,
                task_id=task_id,
                reviewer_tool="codex",
                author_tool="claude",
                summary="Codex reviewed Claude implementation.",
            )
            claude_review, _ = co.cross_review(
                root,
                task_id=task_id,
                reviewer_tool="claude",
                author_tool="codex",
                summary="Claude reviewed Codex tests.",
                stage="round-1-response",
            )
            complete_two_round_review(root, task_id)
            self.assertTrue((root / codex_review).is_file())
            self.assertTrue((root / claude_review).is_file())

            co.learn(root, kind="review", title="Review dummy cross tool workflow", summary="No blockers.", task_id=task_id)
            co.learn(root, kind="compound", title="Compound dummy cross tool workflow", summary="Claims prevented same-file collision.", task_id=task_id)
            ok, failures = co.check_project(root, task_id=task_id)
            self.assertTrue(ok, failures)

            released, _ = co.release_scope(root, task_id=task_id)
            self.assertEqual(released, 2)
            self.assertEqual(co.active_claims(root), [])

            result = subprocess.run(
                [sys.executable, str(root / "scripts/verify.py")],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_generated_verifier_runs_for_writing_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "drafts").mkdir()
            (root / "drafts/chapter.md").write_text("# Chapter\n\nA short draft without conflict markers.\n", encoding="utf-8")

            co.init_project(root)
            result = subprocess.run(
                [sys.executable, str(root / "scripts/verify.py"), "--compound-only"],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_harness_audit_passes_with_warnings_for_template_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            co.init_project(root)

            ok, failures, warnings = co.harness_audit(root)

            self.assertTrue(ok, failures)
            self.assertEqual(failures, [])
            self.assertTrue(any("DRI" in warning for warning in warnings))

    def test_hook_context_mentions_navigation_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            co.init_project(root)
            payload = json.dumps({"cwd": str(root), "hook_event_name": "SessionStart"})

            text = co.hook_context(payload)

            self.assertIn("Compound Orchestrator harness reminder", text)
            self.assertIn("CODEBASE_MAP.md", text)
            self.assertIn(".agent-loop/harness-checklist.md", text)

    def test_learn_writes_slugged_pattern_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            co.init_project(root)

            path, report = co.learn(
                root,
                kind="pattern",
                title="Use Owned Agent Lanes",
                summary="Parallel agents need clear write ownership.",
                task_id="task-123",
            )

            self.assertEqual(path, "docs/patterns/use-owned-agent-lanes.md")
            self.assertIn(path, report.created)
            text = (root / path).read_text(encoding="utf-8")
            self.assertIn("Parallel agents need clear write ownership.", text)
            self.assertIn("Task id: `task-123`", text)

    def test_codex_manifest_has_no_placeholders_and_skill_path_exists(self):
        manifest = ROOT / ".codex-plugin/plugin.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "compound-orchestrator")
        self.assertNotIn("[TODO:", manifest.read_text(encoding="utf-8"))
        self.assertTrue((ROOT / data["skills"].replace("./", "")).exists())

    def test_claude_manifest_has_no_placeholders_and_component_paths_exist(self):
        manifest = ROOT / ".claude-plugin/plugin.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "compound-orchestrator")
        self.assertNotIn("[TODO:", manifest.read_text(encoding="utf-8"))
        self.assertTrue((ROOT / "commands").is_dir())
        self.assertTrue((ROOT / "agents").is_dir())
        self.assertTrue((ROOT / "skills").is_dir())
        self.assertTrue((ROOT / "hooks/hooks.json").is_file())
        self.assertTrue((ROOT / "commands/compound-team-start.md").is_file())
        self.assertTrue((ROOT / "commands/compound-harness-check.md").is_file())
        self.assertTrue((ROOT / "commands/compound-claim.md").is_file())
        self.assertTrue((ROOT / "commands/compound-cross-review.md").is_file())
        self.assertTrue((ROOT / "agents/compound-cross-tool-reviewer.agent.md").is_file())
        self.assertTrue((ROOT / "skills/codex-cross-tool-reviewer/SKILL.md").is_file())

    def test_self_test_passes(self):
        ok, failures = co.self_test(ROOT)
        self.assertTrue(ok, failures)


if __name__ == "__main__":
    unittest.main()
