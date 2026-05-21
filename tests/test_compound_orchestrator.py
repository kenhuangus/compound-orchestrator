import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import compound_orchestrator as co  # noqa: E402


class CompoundOrchestratorTests(unittest.TestCase):
    def test_init_creates_expected_project_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            report = co.init_project(root)
            ok, failures = co.check_project(root)

            self.assertTrue(ok, failures)
            self.assertIn("AGENTS.md", report.created)
            self.assertTrue((root / ".claude/commands/compound-init.md").is_file())
            self.assertTrue((root / ".claude/commands/compound-start.md").is_file())
            self.assertTrue((root / ".claude/commands/compound-team-start.md").is_file())
            self.assertTrue((root / ".claude/commands/compound-harness-check.md").is_file())
            self.assertTrue((root / ".claude/agents/compound-reviewer.md").is_file())
            self.assertTrue((root / "CODEBASE_MAP.md").is_file())
            self.assertTrue((root / ".agent-loop/harness-checklist.md").is_file())
            self.assertTrue((root / ".agent-loop/module-claude-template.md").is_file())
            self.assertTrue((root / ".agent-loop/path-scoped-skill-template.md").is_file())
            self.assertTrue((root / ".agent-loop/lsp-mcp-roadmap.md").is_file())
            self.assertTrue((root / ".agent-loop/harness-ownership.md").is_file())
            self.assertTrue((root / ".agent-loop/team-topology.md").is_file())
            self.assertTrue((root / ".agent-loop/codex-parallel-contract.md").is_file())
            self.assertTrue((root / "scripts/verify.ps1").is_file())
            settings = json.loads((root / ".claude/settings.json").read_text(encoding="utf-8"))
            self.assertEqual(settings["env"][co.CLAUDE_AGENT_TEAM_ENV], "1")
            for deny_rule in co.DEFAULT_PERMISSION_DENY:
                self.assertIn(deny_rule, settings["permissions"]["deny"])
            self.assertIn(co.MANAGED_START, (root / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertIn(co.MANAGED_START, (root / "CLAUDE.md").read_text(encoding="utf-8"))

    def test_init_preserves_existing_docs_and_appends_managed_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text("# Existing Agents\n\nKeep this line.\n", encoding="utf-8")
            (root / "CLAUDE.md").write_text("# Existing Claude\n\nKeep this too.\n", encoding="utf-8")

            co.init_project(root)

            agents = (root / "AGENTS.md").read_text(encoding="utf-8")
            claude = (root / "CLAUDE.md").read_text(encoding="utf-8")
            self.assertIn("Keep this line.", agents)
            self.assertIn("Keep this too.", claude)
            self.assertIn(co.MANAGED_START, agents)
            self.assertIn(co.MANAGED_END, claude)

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

    def test_self_test_passes(self):
        ok, failures = co.self_test(ROOT)
        self.assertTrue(ok, failures)


if __name__ == "__main__":
    unittest.main()
