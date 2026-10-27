#!/usr/bin/env python3
"""Optional Kubernetes adapter. Default is an offline plan; --execute mutates."""
import argparse
import base64
import binascii
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import urlsplit


IMAGE = re.compile(r"[a-z0-9][a-z0-9.:-]*/[a-z0-9][a-z0-9._/-]*@sha256:[0-9a-f]{64}")
LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


def release_plan(env):
    """Validate all non-secret inputs before producing any external command."""
    target = env.get("DEPLOY_ENV", "")
    if target not in {"test", "production"}:
        raise ValueError("DEPLOY_ENV must be test or production")
    if target == "production" and (
        env.get("ENABLE_PRODUCTION_DEPLOY") != "true"
        or env.get("PRODUCTION_CONFIRMATION") != "deploy-production"
    ):
        raise ValueError("production is disabled or this run lacks explicit confirmation")
    sha = env.get("RELEASE_SHA", "")
    if re.fullmatch(r"[0-9a-f]{40}", sha) is None:
        raise ValueError("RELEASE_SHA must be a full commit SHA")
    for key in ("WEB_IMAGE", "SERVER_IMAGE"):
        if IMAGE.fullmatch(env.get(key, "")) is None:
            raise ValueError(key + " must be a registry image pinned to a sha256 digest")
    for key in ("KUBE_NAMESPACE", "WEB_DEPLOYMENT", "SERVER_DEPLOYMENT", "WEB_CONTAINER", "SERVER_CONTAINER"):
        if LABEL.fullmatch(env.get(key, "")) is None:
            raise ValueError(key + " must be a non-empty Kubernetes DNS label")
    url = env.get("SMOKE_URL", "")
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or any(c.isspace() for c in url)):
        raise ValueError("SMOKE_URL must be HTTPS without credentials, query or fragment")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("SMOKE_URL has an invalid port") from exc
    namespace = env["KUBE_NAMESPACE"]
    commands = []
    for component in ("SERVER", "WEB"):
        commands.append(["kubectl", "-n", namespace, "set", "image",
                         "deployment/" + env[component + "_DEPLOYMENT"],
                         env[component + "_CONTAINER"] + "=" + env[component + "_IMAGE"]])
    for component in ("SERVER", "WEB"):
        commands.append(["kubectl", "-n", namespace, "rollout", "status",
                         "deployment/" + env[component + "_DEPLOYMENT"], "--timeout=180s"])
    commands.append(["curl", "--fail", "--silent", "--show-error", "--max-time", "20",
                     "--retry", "3", "--output", os.devnull, "--write-out", "%{http_code}", "--url", url])
    return {"environment": target, "commit": sha,
            "web": env["WEB_IMAGE"], "server": env["SERVER_IMAGE"], "commands": commands}


def deploy(env, execute=False):
    plan = release_plan(env)
    if not execute:
        return {"mode": "dry-run", **plan}
    try:
        config = base64.b64decode(env.get("KUBE_CONFIG_B64", ""), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("KUBE_CONFIG_B64 must be valid Base64") from exc
    if not config.strip():
        raise ValueError("KUBE_CONFIG_B64 is required for execution")
    # Never use the runner's ambient kubeconfig or expose this credential in argv.
    with tempfile.TemporaryDirectory(prefix="project-deploy-") as directory:
        config_path = Path(directory) / "config"
        config_path.touch(mode=0o600)
        config_path.write_bytes(config)
        command_env = dict(env)
        command_env.pop("KUBE_CONFIG_B64", None)
        command_env["KUBECONFIG"] = str(config_path)
        for command in plan["commands"][:-1]:
            subprocess.run(command, env=command_env, check=True, timeout=240)
        smoke = subprocess.run(plan["commands"][-1], env=command_env, check=True,
                               timeout=240, capture_output=True, text=True)
        if re.fullmatch(r"2[0-9]{2}", smoke.stdout.strip()) is None:
            raise ValueError("health endpoint did not return HTTP 2xx")
    return {"mode": "executed", **plan}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="update the configured cluster; default is dry-run")
    args = parser.parse_args()
    try:
        result = deploy(os.environ, execute=args.execute)
    except (ValueError, OSError, subprocess.SubprocessError):
        # Raw process/environment errors may contain sensitive external data.
        print("DEPLOY FAILED: validate configuration or inspect the failed rollout; partial changes may remain.")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
