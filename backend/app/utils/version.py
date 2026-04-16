"""애플리케이션 버전 읽기 공용 유틸."""

import pathlib
import tomllib


def read_app_version() -> str:
    """backend/pyproject.toml 의 [project].version 을 읽는다.

    CWD 와 파일 위치 두 경로 모두 시도 (uvicorn 실행 방식에 따라 달라짐).
    Docker 이미지(WORKDIR=/app) 및 로컬 실행 모두 커버.
    """
    here = pathlib.Path(__file__).resolve()
    candidates = [
        pathlib.Path("pyproject.toml"),  # CWD (docker WORKDIR=/app)
        here.parents[2] / "pyproject.toml",  # backend/pyproject.toml (app/utils 기준)
    ]
    for p in candidates:
        if p.exists():
            with open(p, "rb") as f:
                return tomllib.load(f).get("project", {}).get("version", "0.1.0")
    return "0.1.0"
