#!/usr/bin/env python3
from __future__ import annotations

import re
import shlex
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = ROOT / "scripts" / "deploy_prod.sh"


def _run(*args: str) -> list[str]:
    result = subprocess.run(
        args,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _run_text(*args: str) -> str:
    result = subprocess.run(
        args,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _extract_quoted_items(block: str) -> list[str]:
    return re.findall(r'"([^"]+)"', block)


def _extract_ensure_named_volumes(script_text: str) -> list[str]:
    match = re.search(r"ensure_named_volumes\(\) \{\s+local volumes=\((.*?)\)\s+local volume", script_text, re.S)
    if not match:
        raise RuntimeError("Could not parse ensure_named_volumes() from deploy_prod.sh")
    return _extract_quoted_items(match.group(1))


def _extract_compose_up_services(script_text: str, compose_var: str) -> list[str]:
    services: list[str] = []
    pattern = re.compile(rf"run_with_timeout \d+ \${compose_var} up -d --build --remove-orphans ([^\n]+)")
    for match in pattern.finditer(script_text):
        services.extend(shlex.split(match.group(1).strip()))
    if not services:
        raise RuntimeError(f"Could not parse services for ${compose_var} up command")
    return services


def _extract_effective_volume_names(compose_text: str) -> set[str]:
    lines = compose_text.splitlines()
    in_top_level_volumes = False
    current_volume = None
    logical_to_effective: dict[str, str] = {}

    for line in lines:
        if not in_top_level_volumes:
            if line == "volumes:":
                in_top_level_volumes = True
            continue

        if line and not line.startswith("  "):
            break

        volume_match = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if volume_match:
            current_volume = volume_match.group(1)
            logical_to_effective[current_volume] = current_volume
            continue

        if current_volume is None:
            continue

        effective_match = re.match(r"^    name:\s+(.+?)\s*$", line)
        if effective_match:
            logical_to_effective[current_volume] = effective_match.group(1).strip()

    return set(logical_to_effective.values())


def main() -> int:
    script_text = DEPLOY_SCRIPT.read_text()

    ensure_volumes = sorted(set(_extract_ensure_named_volumes(script_text)))
    core_services = sorted(set(_extract_compose_up_services(script_text, "COMPOSE_CORE")))
    full_services = sorted(set(_extract_compose_up_services(script_text, "COMPOSE_FULL")))

    compose_core_services = set(_run("docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.prod.yml", "config", "--services"))
    compose_full_services = set(
        _run(
            "docker",
            "compose",
            "-f",
            "docker-compose.yml",
            "-f",
            "docker-compose.prod.yml",
            "-f",
            "docker-compose.metrics.yml",
            "config",
            "--services",
        )
    )
    compose_config_text = _run_text("docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.prod.yml", "config")
    compose_volumes = _extract_effective_volume_names(compose_config_text)

    errors: list[str] = []

    missing_core = sorted(set(core_services) - compose_core_services)
    if missing_core:
        errors.append(f"deploy_prod.sh references missing core services: {', '.join(missing_core)}")

    missing_full = sorted(set(full_services) - compose_full_services)
    if missing_full:
        errors.append(f"deploy_prod.sh references missing full-stack services: {', '.join(missing_full)}")

    missing_volumes = sorted(set(ensure_volumes) - compose_volumes)
    if missing_volumes:
        errors.append(f"deploy_prod.sh ensures volumes not present in compose config: {', '.join(missing_volumes)}")

    if "es" in core_services or "es" in full_services:
        errors.append("deploy_prod.sh still references legacy 'es' service name")
    if any(volume.endswith("esdata") for volume in ensure_volumes):
        errors.append("deploy_prod.sh still references legacy esdata volume naming")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("deploy/compose drift check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
