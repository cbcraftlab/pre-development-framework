"""Offline boundary/command-flow tests. No cluster, registry or credentials."""
import base64
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "integrations/ci-cd/deploy.py"
SPEC = importlib.util.spec_from_file_location("ci_cd_deploy", SOURCE)
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


def environment():
    return {
        "PATH": os.environ.get("PATH", ""),
        "DEPLOY_ENV": "test", "RELEASE_SHA": "a" * 40,
        "WEB_IMAGE": "ghcr.io/example/sample-web@sha256:" + "b" * 64,
        "SERVER_IMAGE": "ghcr.io/example/sample-server@sha256:" + "c" * 64,
        "KUBE_NAMESPACE": "sample-test", "WEB_DEPLOYMENT": "sample-web",
        "SERVER_DEPLOYMENT": "sample-server", "WEB_CONTAINER": "web",
        "SERVER_CONTAINER": "server", "SMOKE_URL": "https://app.example.com/health",
    }


class DeploymentBoundaryTests(unittest.TestCase):
    def test_default_plan_needs_no_credential_and_never_runs_commands(self):
        env = environment()
        env["KUBE_CONFIG_B64"] = "SYNTHETIC-SECRET-DO-NOT-PRINT"
        with patch.object(adapter.subprocess, "run") as run:
            plan = adapter.deploy(env)
        run.assert_not_called()
        self.assertEqual(plan["mode"], "dry-run")
        self.assertNotIn("SYNTHETIC-SECRET", json.dumps(plan))
        self.assertEqual(plan["commit"], env["RELEASE_SHA"])

    def test_invalid_inputs_fail_before_any_external_command(self):
        invalid = {
            "DEPLOY_ENV": ["", "unknown"],
            "RELEASE_SHA": ["abc123", "a" * 40 + "\n"],
            "WEB_IMAGE": ["ghcr.io/example/web:latest", "x;echo secret", "ghcr.io/x@y"],
            "SERVER_IMAGE": ["ghcr.io/example/server:sha-abc"],
            "KUBE_NAMESPACE": ["", "-bad", "x;echo secret", "x" * 64],
            "WEB_DEPLOYMENT": ["", "bad/name"],
            "SERVER_DEPLOYMENT": ["../other"],
            "WEB_CONTAINER": ["web\nother"],
            "SERVER_CONTAINER": ["bad=value"],
            "SMOKE_URL": ["http://app.example.com/health", "https://user:pass@app.example.com/health",
                          "https://app.example.com/?token=secret", "https://app.example.com/#secret",
                          "https://app.example.com:invalid", "https://app.example.com/health\n"],
        }
        for key, values in invalid.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    env = environment()
                    env[key] = value
                    with patch.object(adapter.subprocess, "run") as run:
                        with self.assertRaises(ValueError):
                            adapter.deploy(env, execute=True)
                    run.assert_not_called()

    def test_production_requires_both_enablement_and_current_confirmation(self):
        for enabled, confirmation in [("", ""), ("true", ""), ("", "deploy-production")]:
            env = {**environment(), "DEPLOY_ENV": "production",
                   "ENABLE_PRODUCTION_DEPLOY": enabled, "PRODUCTION_CONFIRMATION": confirmation}
            with self.subTest(enabled=enabled, confirmation=confirmation):
                with self.assertRaises(ValueError):
                    adapter.release_plan(env)
        env.update(ENABLE_PRODUCTION_DEPLOY="true", PRODUCTION_CONFIRMATION="deploy-production")
        self.assertEqual(adapter.release_plan(env)["environment"], "production")

    def test_missing_or_malformed_credential_fails_without_ambient_kubeconfig(self):
        for credential in ["", "%%%", base64.b64encode(b"  \n").decode("ascii")]:
            env = {**environment(), "KUBE_CONFIG_B64": credential, "KUBECONFIG": "/ambient/config"}
            with self.subTest(credential=credential), patch.object(adapter.subprocess, "run") as run:
                with self.assertRaises(ValueError):
                    adapter.deploy(env, execute=True)
                run.assert_not_called()

    def test_execute_uses_exact_digests_and_private_temporary_config_then_cleans_it(self):
        env = {**environment(), "KUBE_CONFIG_B64": base64.b64encode(b"synthetic-config").decode("ascii")}
        config_paths = []

        def simulated(command, **kwargs):
            command_env = kwargs["env"]
            self.assertNotIn("KUBE_CONFIG_B64", command_env)
            config = Path(command_env["KUBECONFIG"])
            config_paths.append(config)
            self.assertEqual(config.read_bytes(), b"synthetic-config")
            if os.name != "nt":
                self.assertEqual(config.stat().st_mode & 0o777, 0o600)
            self.assertTrue(kwargs["check"])
            self.assertNotIn("shell", kwargs)
            return subprocess.CompletedProcess(command, 0, stdout="200")

        with patch.object(adapter.subprocess, "run", side_effect=simulated) as run:
            result = adapter.deploy(env, execute=True)
        self.assertEqual(result["mode"], "executed")
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[:2], [
            ["kubectl", "-n", "sample-test", "set", "image", "deployment/sample-server", "server=" + env["SERVER_IMAGE"]],
            ["kubectl", "-n", "sample-test", "set", "image", "deployment/sample-web", "web=" + env["WEB_IMAGE"]],
        ])
        self.assertTrue(all("rollout" in command for command in commands[2:4]))
        self.assertEqual(commands[-1][0], "curl")
        self.assertTrue(all(not path.exists() for path in config_paths))

    def test_partial_rollout_failure_stops_smoke_and_cleans_credential(self):
        env = {**environment(), "KUBE_CONFIG_B64": base64.b64encode(b"synthetic-config").decode("ascii")}
        paths = []

        def fail_on_rollout(command, **kwargs):
            paths.append(Path(kwargs["env"]["KUBECONFIG"]))
            if "rollout" in command:
                raise subprocess.CalledProcessError(1, command)
            return subprocess.CompletedProcess(command, 0)

        with patch.object(adapter.subprocess, "run", side_effect=fail_on_rollout) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                adapter.deploy(env, execute=True)
        self.assertEqual(run.call_count, 3)
        self.assertTrue(all(not path.exists() for path in paths))

    def test_health_redirect_is_not_reported_as_success(self):
        env = {**environment(), "KUBE_CONFIG_B64": base64.b64encode(b"synthetic-config").decode("ascii")}
        with patch.object(adapter.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout="302")):
            with self.assertRaises(ValueError):
                adapter.deploy(env, execute=True)


if __name__ == "__main__":
    unittest.main()
