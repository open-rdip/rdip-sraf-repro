# lifter/parsers/docker_parser.py
"""
Parses Docker-related artifacts into a normalised dict
ready for RDIP mapping.

Supports three input modes:
  1. docker inspect JSON (from a running/pulled image)
  2. Dockerfile text (static analysis, no Docker daemon needed)
  3. image reference string (pulls inspect data live)
"""

import subprocess
import json
import re
from pathlib import Path


def inspect_image(image_ref: str) -> dict:
    """
    Run `docker inspect` on an image reference and return raw JSON.
    Requires Docker to be running locally.
    """
    try:
        result = subprocess.run(
            ["docker", "inspect", image_ref],
            capture_output=True,
            text=True,
            check=True,
            timeout=60
        )
        data = json.loads(result.stdout)
        return data[0] if isinstance(data, list) else data
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"docker inspect failed for '{image_ref}': {e.stderr.strip()}"
        )
    except FileNotFoundError:
        raise RuntimeError(
            "Docker is not installed or not running. "
            "Use parse_dockerfile() for static analysis instead."
        )


def parse_docker_inspect(inspect_data: dict) -> dict:
    """
    Extract reproducibility-critical fields from docker inspect output.
    Returns a normalised dict ready for rdip_mapper.py.
    """
    config   = inspect_data.get("Config", {})
    repo_tags    = inspect_data.get("RepoTags", [])
    repo_digests = inspect_data.get("RepoDigests", [])

    # Image digest — prefer content-addressable RepoDigest over image ID
    image_digest = inspect_data.get("Id", "")
    if repo_digests:
        # RepoDigest looks like: pytorch/pytorch@sha256:abc123...
        digest_part = repo_digests[0].split("@")
        if len(digest_part) == 2:
            image_digest = digest_part[1]

    # Parse environment variables
    env_vars = {}
    for env_str in config.get("Env", []):
        if "=" in env_str:
            k, v = env_str.split("=", 1)
            env_vars[k.strip()] = v.strip()

    # Extract known version variables
    cuda_version   = (
        env_vars.get("CUDA_VERSION") or
        env_vars.get("CUDA_VER") or
        env_vars.get("CUDA_TOOLKIT_VERSION") or
        None
    )
    python_version = (
        env_vars.get("PYTHON_VERSION") or
        env_vars.get("PYTHON_VER") or
        None
    )
    pytorch_version = (
        env_vars.get("PYTORCH_VERSION") or
        env_vars.get("TORCH_VERSION") or
        None
    )

    return {
        "source":          "docker_inspect",
        "image_digest":    image_digest,
        "image_name":      repo_tags[0] if repo_tags else "",
        "os":              inspect_data.get("Os", "linux"),
        "architecture":    inspect_data.get("Architecture", "amd64"),
        "cuda_version":    cuda_version,
        "python_version":  python_version,
        "pytorch_version": pytorch_version,
        "created":         inspect_data.get("Created", ""),
        "spec_type":       "docker",
        "spec_uri":        repo_tags[0] if repo_tags else "",
        "env_vars":        env_vars,
    }


def parse_dockerfile(dockerfile_path: str) -> dict:
    """
    Statically analyse a Dockerfile without running Docker.
    Extracts FROM base image, ARG/ENV values, and LABEL metadata.
    Returns a normalised dict — note: no image digest available
    from static analysis.
    """
    path = Path(dockerfile_path)
    if not path.exists():
        raise FileNotFoundError(f"Dockerfile not found: {dockerfile_path}")

    content = path.read_text(encoding="utf-8", errors="ignore")
    lines   = content.splitlines()

    from_image     = ""
    env_vars       = {}
    arg_vars       = {}
    labels         = {}

    for line in lines:
        stripped = line.strip()

        # FROM — base image
        if stripped.upper().startswith("FROM "):
            parts = stripped.split()
            if len(parts) >= 2:
                from_image = parts[1]

        # ENV key=value or ENV key value
        elif stripped.upper().startswith("ENV "):
            rest = stripped[4:].strip()
            if "=" in rest:
                for part in rest.split():
                    if "=" in part:
                        k, v = part.split("=", 1)
                        env_vars[k.strip()] = v.strip().strip('"').strip("'")
            else:
                parts = rest.split(None, 1)
                if len(parts) == 2:
                    env_vars[parts[0]] = parts[1].strip().strip('"').strip("'")

        # ARG name=default
        elif stripped.upper().startswith("ARG "):
            rest = stripped[4:].strip()
            if "=" in rest:
                k, v = rest.split("=", 1)
                arg_vars[k.strip()] = v.strip()
            else:
                arg_vars[rest.strip()] = ""

        # LABEL key=value
        elif stripped.upper().startswith("LABEL "):
            rest = stripped[6:].strip()
            matches = re.findall(r'(\S+)=["\']?([^"\']+)["\']?', rest)
            for k, v in matches:
                labels[k] = v

    # Combine env + arg for version extraction
    all_vars = {**arg_vars, **env_vars}

    cuda_version   = (
        all_vars.get("CUDA_VERSION") or
        all_vars.get("CUDA_VER") or
        _extract_version_from_image(from_image, "cuda") or
        None
    )
    python_version = (
        all_vars.get("PYTHON_VERSION") or
        all_vars.get("PYTHON_VER") or
        _extract_version_from_image(from_image, "python") or
        None
    )

    return {
        "source":          "dockerfile",
        "image_digest":    "",          # not available from static analysis
        "image_name":      from_image,
        "os":              "linux",
        "architecture":    "",
        "cuda_version":    cuda_version,
        "python_version":  python_version,
        "pytorch_version": all_vars.get("PYTORCH_VERSION") or all_vars.get("TORCH_VERSION"),
        "created":         "",
        "spec_type":       "docker",
        "spec_uri":        str(path.resolve()),
        "env_vars":        all_vars,
        "labels":          labels,
    }


def _extract_version_from_image(image_ref: str, keyword: str) -> str | None:
    """
    Try to extract a version hint from the image tag itself.
    e.g. pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime
         → cuda: "12.1", python: None
    """
    if not image_ref:
        return None
    tag_part = image_ref.split(":")[-1] if ":" in image_ref else ""
    if not tag_part:
        return None

    if keyword == "cuda":
        m = re.search(r"cuda(\d+\.\d+)", tag_part, re.IGNORECASE)
        return m.group(1) if m else None

    if keyword == "python":
        m = re.search(r"py(\d)(\d+)", tag_part, re.IGNORECASE)
        if m:
            return f"{m.group(1)}.{m.group(2)}"
        m = re.search(r"python(\d+\.\d+)", tag_part, re.IGNORECASE)
        return m.group(1) if m else None

    return None


def from_repo(repo_dir: str) -> dict | None:
    """
    Auto-detect and parse the best available Docker artifact in a repo.
    Returns parsed dict or None if no Docker artifact found.
    Tries Dockerfile first, then falls back to docker-compose.yml hints.
    """
    repo_path = Path(repo_dir)

    # Common Dockerfile locations
    candidates = [
        repo_path / "Dockerfile",
        repo_path / "docker" / "Dockerfile",
        repo_path / ".docker" / "Dockerfile",
        repo_path / "Docker" / "Dockerfile",
    ]

    for candidate in candidates:
        if candidate.exists():
            print(f"[DockerParser] Found {candidate.relative_to(repo_path)}")
            return parse_dockerfile(str(candidate))

    return None
