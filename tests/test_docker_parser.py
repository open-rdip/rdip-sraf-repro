"""Unit tests for Dockerfile static parsing, incl. author-declared digest."""
from lifter.parsers.docker_parser import parse_dockerfile


def _df(tmp_path, text):
    p = tmp_path / "Dockerfile"
    p.write_text(text)
    return str(p)


def test_pinned_digest_extracted(tmp_path):
    d = parse_dockerfile(_df(tmp_path, "FROM pytorch/pytorch@sha256:9f2eabc123 AS base\n"))
    assert d["image_digest"] == "sha256:9f2eabc123"


def test_bare_tag_has_no_digest(tmp_path):
    d = parse_dockerfile(_df(tmp_path, "FROM pytorch/pytorch:2.1.0-cuda12.1\n"))
    assert d["image_digest"] == ""


def test_latest_has_no_digest(tmp_path):
    d = parse_dockerfile(_df(tmp_path, "FROM ubuntu:latest\n"))
    assert d["image_digest"] == ""


def test_cuda_version_from_tag(tmp_path):
    d = parse_dockerfile(_df(tmp_path, "FROM pytorch/pytorch:2.1.0-cuda12.1-cudnn8\n"))
    assert d["cuda_version"] == "12.1"


def test_env_var_parsing(tmp_path):
    d = parse_dockerfile(_df(tmp_path, "FROM python:3.10\nENV CUDA_VERSION=11.8\n"))
    assert d["cuda_version"] == "11.8"
    assert d["spec_type"] == "docker"
