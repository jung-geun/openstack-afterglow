from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.dockerfile_import import (
    DockerfileImportError,
    DockerfilePlan,
    _dockerfile_cloud_init_script,
    parse_dockerfile_plan,
    parse_github_url,
    prepare_dockerfile_import,
    validate_dockerfile_path,
    validate_layer_name,
)


def test_parse_github_url_accepts_only_canonical_public_repo():
    repo = parse_github_url("https://github.com/acme/widgets")

    assert repo.owner == "acme"
    assert repo.repo == "widgets"
    assert repo.canonical_url == "https://github.com/acme/widgets"
    for bad in [
        "http://github.com/acme/widgets",
        "https://evil.com/acme/widgets",
        "https://github.com/acme/widgets?x=1",
        "https://github.com/acme/widgets/tree/main",
        "https://user@github.com/acme/widgets",
    ]:
        with pytest.raises(DockerfileImportError):
            parse_github_url(bad)


def test_validate_names_and_paths_reject_traversal_and_overflow():
    assert validate_layer_name("my-layer.1", field="layer_prefix") == "my-layer.1"
    assert validate_dockerfile_path("docker/Dockerfile") == "docker/Dockerfile"
    for bad in ["../Dockerfile", "/Dockerfile", "docker/../Dockerfile", "Dockerfile;rm"]:
        with pytest.raises(DockerfileImportError):
            validate_dockerfile_path(bad)
    for bad in ["BadUpper", "bad/name", "x" * 65]:
        with pytest.raises(DockerfileImportError):
            validate_layer_name(bad, field="layer_prefix")


def test_parse_dockerfile_supported_subset_plans_layers_deterministically():
    dockerfile = """
    FROM ubuntu:22.04
    ENV APP_HOME=/opt/app PATH=/usr/local/bin
    WORKDIR /opt/app
    COPY src/ ./src/
    ADD config ./config
    RUN echo hello \\
        && touch /opt/app/ready
    """

    ubuntu_base, layers = parse_dockerfile_plan(
        dockerfile,
        layer_prefix="demo",
        profile_name="demo-profile",
        commit_sha="a" * 40,
        dockerfile_path="Dockerfile",
    )

    assert ubuntu_base == "ubuntu-22.04"
    assert [layer["instruction"] for layer in layers] == ["ENV", "WORKDIR", "COPY", "ADD", "RUN"]
    assert [layer["name"] for layer in layers] == [
        "demo-01-env-app-home-opt",
        "demo-02-workdir-opt-app",
        "demo-03-copy-src-src",
        "demo-04-add-config-config",
        "demo-05-run-echo-hello-touch",
    ]
    assert layers[-1]["payload"]["workdir"] == "/opt/app"
    assert layers[-1]["payload"]["env"]["APP_HOME"] == "/opt/app"


def test_parse_dockerfile_env_key_value_form():
    ubuntu_base, layers = parse_dockerfile_plan(
        "FROM ubuntu:22.04\nENV PATH /usr/local/bin\nRUN echo $PATH",
        layer_prefix="demo",
        profile_name="demo",
        commit_sha="a" * 40,
        dockerfile_path="Dockerfile",
    )

    assert ubuntu_base == "ubuntu-22.04"
    assert layers[0]["instruction"] == "ENV"
    assert layers[0]["payload"]["env"] == {"PATH": "/usr/local/bin"}
    assert layers[1]["payload"]["env"]["PATH"] == "/usr/local/bin"


@pytest.mark.parametrize(
    "dockerfile, message",
    [
        ("FROM ubuntu:22.04 AS base\nRUN true", "FROM AS"),
        ("FROM ubuntu:22.04\nFROM ubuntu:22.04\nRUN true", "multi-stage"),
        ("FROM debian:12\nRUN true", "FROM"),
        ("FROM ubuntu:22.04\nARG TOKEN", "ARG"),
        ("FROM ubuntu:22.04\nCOPY ../secret /x", "traversal"),
        ("FROM ubuntu:22.04\nADD https://example.com/a /x", "remote URL"),
        ("FROM ubuntu:22.04\nRUN --mount=type=cache echo hi", "RUN"),
    ],
)
def test_parse_dockerfile_rejects_unsafe_or_unsupported_instructions(dockerfile, message):
    with pytest.raises(DockerfileImportError, match=message):
        parse_dockerfile_plan(
            dockerfile,
            layer_prefix="demo",
            profile_name="demo",
            commit_sha="a" * 40,
            dockerfile_path="Dockerfile",
        )


def test_prepare_dockerfile_import_rejects_from_base_mismatch():
    conn = MagicMock()
    conn.image.get_image.return_value = SimpleNamespace(
        id="img-22",
        name="ubuntu-22.04",
        status="active",
        os_distro="ubuntu",
        os_version="22.04",
    )

    with (
        patch("app.services.dockerfile_import.resolve_github_commit", return_value="a" * 40),
        patch("app.services.dockerfile_import.fetch_pinned_archive", return_value=b"archive"),
        patch("app.services.dockerfile_import.fetch_pinned_dockerfile", return_value="FROM ubuntu:20.04\nRUN true"),
    ):
        with pytest.raises(DockerfileImportError, match="일치하지 않습니다"):
            prepare_dockerfile_import(
                conn,
                github_url="https://github.com/acme/widgets",
                ref=None,
                dockerfile_path="Dockerfile",
                layer_prefix="demo",
                profile_name=None,
                base_image_id="img-22",
            )


def test_dockerfile_cloud_init_mounts_outputs_rw_and_executes_real_steps():
    job = SimpleNamespace(
        repo_owner="acme",
        repo_name="widgets",
        commit_sha="a" * 40,
        dockerfile_path="Dockerfile",
        planned_layers=[
            {
                "name": "demo-01-run-echo",
                "instruction": "RUN",
                "payload": {"command": "echo hi", "env": {}, "workdir": "/"},
            }
        ],
    )

    script = _dockerfile_cloud_init_script(job, ["10.0.0.1:/share-1"], "tok")

    assert "https://codeload.github.com/acme/widgets/tar.gz/" + "a" * 40 in script
    assert "nfs4 rw,nofail" in script
    assert "chroot" in script
    assert "mksquashfs" in script
    assert "-latest.sqsh" in script


@pytest.mark.asyncio
async def test_dockerfile_import_route_enqueues_validated_job(admin_client, mock_conn):

    plan = DockerfilePlan(
        github_url="https://github.com/acme/widgets",
        repo_owner="acme",
        repo_name="widgets",
        commit_sha="a" * 40,
        dockerfile_path="Dockerfile",
        layer_prefix="demo",
        profile_name="demo",
        base_image_snapshot={"ubuntu_base": "ubuntu-22.04", "base_image_id": "img-22"},
        planned_layers=[],
    )
    with (
        patch("app.services.dockerfile_import.prepare_dockerfile_import", return_value=plan) as mock_prepare,
        patch(
            "app.services.dockerfile_import.create_import_job",
            new_callable=AsyncMock,
            return_value={"id": 7, "status": "queued"},
        ) as mock_create,
    ):
        resp = await admin_client.post(
            "/api/v1/admin/libraries/imports/dockerfile",
            json={
                "github_url": "https://github.com/acme/widgets",
                "dockerfile_path": "Dockerfile",
                "layer_prefix": "demo",
                "base_image_id": "img-22",
            },
        )

    assert resp.status_code == 200
    assert resp.json() == {"id": 7, "status": "queued"}
    assert mock_prepare.call_args.args[0] is mock_conn
    mock_create.assert_awaited_once()


@pytest.mark.asyncio
async def test_dockerfile_import_route_maps_base_image_validation_to_400(admin_client):
    with patch(
        "app.services.dockerfile_import.prepare_dockerfile_import", side_effect=ValueError("base image inactive")
    ):
        resp = await admin_client.post(
            "/api/v1/admin/libraries/imports/dockerfile",
            json={
                "github_url": "https://github.com/acme/widgets",
                "dockerfile_path": "Dockerfile",
                "layer_prefix": "demo",
                "base_image_id": "img-22",
            },
        )

    assert resp.status_code == 400
    assert "base image inactive" in resp.text
