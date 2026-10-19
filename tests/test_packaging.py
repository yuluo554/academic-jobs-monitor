"""非 editable 安装守门（M7 迭代新增）：wheel → 全新 venv → 装 → 中立目录跑子命令。

为什么必须有这道门：仓内所有"干净环境验证"与 CI 长期只做 `pip install -e .[dev]`，
而 hatchling 的 editable 安装把仓库 `src/` 整个塞进 `sys.path`
（`.venv/Lib/site-packages/_editable_impl_ajm.pth` 的内容就是 `src` 的绝对路径），
于是"wheel 里漏了包"这类缺陷在本地与 CI 全绿（M7 诊断 D1 实测：8 个子命令里 5 个
`ModuleNotFoundError`）。本文件走真实用户路径：构建 wheel → 全新 venv 装 wheel →
**在中立临时目录**（不是仓库根）跑子命令，并断言安装结果不是 editable 形态。

慢测（建 venv + 装依赖，约 1 分钟）：`-m "not slow"` 可跳过；
CI 的 `packaging` job 用 `-m slow` 单独跑本文件（该 job 不装 editable 包）。

断言口径（不许放宽的地方已注明）：
- `jobsctl bench` 的**退出码 1 与 108/109 = 99.1% 是正确期望**（唯一扣分项 position
  95.5%，诚实保留见 bench/README.md）——门禁断言的就是"仍是 1"，不许改成 0，也不许把
  基准"修"成 100%；
- `jobsctl feed` 缺 `subscribe.yaml` 的既定行为 = 友好提示 + 退出码 2，不是 traceback。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PKG = "ajm"
EXPECTED_VERSION = "0.1.0"
EXPECTED_REQUIRES_PYTHON = ">=3.12"
# 5 个子系统 + CLI 编排层：D1 里"没进 wheel"的正是这 5 个包。
SUBSYSTEM_MODULES = (
    "ajm/cli.py",
    "ajm/extract/engine.py",
    "ajm/snapshot/differ.py",
    "ajm/subscribe/matcher.py",
    "ajm/bench/truth.py",
    "ajm/webapp/app.py",
)
# 随包分发的数据（真值库 + 回放 fixture）：路径解析若越界，bench/extract 会在装完后挂。
PACKAGED_DATA = (
    "ajm/bench/fixtures/truth.json",
    "ajm/bench/fixtures/change_cases/cases.json",
    "ajm/sources/fixtures/pku/list.html",
)

pytestmark = pytest.mark.slow


def _bin_dir(venv: Path) -> Path:
    return venv / ("Scripts" if os.name == "nt" else "bin")


def _python(venv: Path) -> Path:
    return _bin_dir(venv) / ("python.exe" if os.name == "nt" else "python")


def _jobsctl(venv: Path) -> Path:
    return _bin_dir(venv) / ("jobsctl.exe" if os.name == "nt" else "jobsctl")


def _console_env() -> dict[str, str]:
    """与 CI ci.yml 同款环境：UTF-8 管道下中文才可断言（cp1252 会 UnicodeEncodeError）。

    同时**清掉 PYTHONPATH**：守门的意义是"只有 wheel 装进去的东西可用"。若把外层
    `PYTHONPATH=<repo>/src` 继承进去（本仓 pytest 的 `pythonpath = ["src"]` 就走这条路），
    子进程能 import 到未打包的源码，门禁会重新变成假绿。
    """
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("PYTHONPATH", None)
    return env


def _run_jobsctl(venv: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(_jobsctl(venv)), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_console_env(),
        check=False,
    )


def _run_python(venv: Path, code: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(_python(venv)), "-c", code],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_console_env(),
        check=False,
    )


@pytest.fixture(scope="session")
def built_wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """构建 wheel（`pip wheel . --no-deps`）；同时是"wheel 内容"断言的输入。"""
    out_dir = tmp_path_factory.mktemp("ajm-wheel")
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", str(REPO_ROOT), "-w", str(out_dir), "--no-deps"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert proc.returncode == 0, f"wheel 构建失败：\n{proc.stdout}\n{proc.stderr}"
    wheels = sorted(out_dir.glob("*.whl"))
    assert len(wheels) == 1, f"期望恰好 1 个 wheel，实际 {wheels}"
    return wheels[0]


@pytest.fixture(scope="session")
def installed_venv(
    built_wheel: Path, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    """全新 venv（不带 --system-site-packages）+ 装 wheel；返回 venv 根。"""
    venv = tmp_path_factory.mktemp("ajm-verify") / "venv"
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv)],
        check=True,
        capture_output=True,
    )
    proc = subprocess.run(
        [str(_python(venv)), "-m", "pip", "install", "--quiet", str(built_wheel)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert proc.returncode == 0, f"wheel 安装失败：\n{proc.stdout}\n{proc.stderr}"
    return venv


@pytest.fixture(scope="session")
def neutral_cwd(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """中立工作目录：不在仓库根跑，避免借 `src/` 或仓库其他文件（D1 的掩盖机制）。"""
    return tmp_path_factory.mktemp("ajm-neutral")


# -- 1. wheel 内容（快、确定性强，先卡住打包声明） --------------------------------


def test_wheel_top_level_is_ajm_only_with_subsystems_and_data(built_wheel: Path) -> None:
    """wheel 顶层只有 ajm + dist-info；5 个子系统与随包数据都在里面（DEC1=B 口径）。"""
    with zipfile.ZipFile(built_wheel) as zf:
        names = zf.namelist()
    top_level = {n.split("/")[0] for n in names}
    assert top_level == {PKG, f"{PKG}-{EXPECTED_VERSION}.dist-info"}, (
        f"wheel 顶层应只有 {PKG}/ 与 dist-info（不再向 site-packages 顶层投 "
        f"bench/extract/webapp 等通用名），实际 {sorted(top_level)}"
    )
    missing = [n for n in (*SUBSYSTEM_MODULES, *PACKAGED_DATA) if n not in names]
    assert not missing, f"wheel 缺项（D1 复发）：{missing}"
    # 未随包数据目录的空壳目录不应出现（打包噪声）
    assert not [n for n in names if n.endswith("/")]


def test_dist_info_metadata_matches_pyproject(built_wheel: Path) -> None:
    """发行名/版本/解释器 floor/入口点四处一致（版本口径漂移会被此处拦住）。"""
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    init_text = (REPO_ROOT / "src" / PKG / "__init__.py").read_text(encoding="utf-8")
    with zipfile.ZipFile(built_wheel) as zf:
        metadata = zf.read(f"{PKG}-{EXPECTED_VERSION}.dist-info/METADATA").decode("utf-8")
        entry_points = zf.read(
            f"{PKG}-{EXPECTED_VERSION}.dist-info/entry_points.txt"
        ).decode("utf-8")
    assert f"Name: {PKG}" in metadata
    assert f"Version: {EXPECTED_VERSION}" in metadata
    assert pyproject["project"]["version"] == EXPECTED_VERSION
    assert f'__version__ = "{EXPECTED_VERSION}"' in init_text
    assert f"Requires-Python: {EXPECTED_REQUIRES_PYTHON}" in metadata
    assert f'requires-python = "{EXPECTED_REQUIRES_PYTHON}"' in (
        REPO_ROOT / "pyproject.toml"
    ).read_text(encoding="utf-8")
    assert "jobsctl = ajm.cli:main" in entry_points


def test_venv_is_a_real_non_editable_install(installed_venv: Path) -> None:
    """自证：这个 venv 里没有把仓库 `src/` 塞进 sys.path 的 .pth（否则本门禁是假的）。"""
    site_packages = [
        p for p in installed_venv.glob("Lib/site-packages") if p.is_dir()
    ] + [p for p in installed_venv.glob("lib/python*/site-packages") if p.is_dir()]
    assert site_packages, "找不到 site-packages（venv 结构变了？）"
    offenders = []
    for sp in site_packages:
        for pth in sp.glob("*.pth"):
            text = pth.read_text(encoding="utf-8", errors="replace")
            if str(REPO_ROOT) in text:
                offenders.append(f"{pth}: {text.strip()}")
    assert not offenders, (
        "安装形态是 editable（仓库路径进了 sys.path）——本门禁会因此失去意义：\n"
        + "\n".join(offenders)
    )


def test_child_process_imports_package_from_venv_not_repo(
    installed_venv: Path, neutral_cwd: Path
) -> None:
    """第二重自证：子进程里 `ajm.__file__` 必须落在 venv 内，且 sys.path 不含仓库 `src/`。

    两者分别对应两个假绿来源：`_editable_impl_ajm.pth`（已由上一个测试盯住）与
    外层继承的 `PYTHONPATH`（`_console_env()` 已清掉，这里实测确认清干净了）。
    """
    probe = _run_python(
        installed_venv,
        "import json, sys, ajm; "
        "print(json.dumps({'file': ajm.__file__, "
        "'repo_src_in_path': any('10-15-academic-jobs-monitor' in p for p in sys.path)}))",
        neutral_cwd,
    )
    assert probe.returncode == 0, probe.stderr
    payload = json.loads(probe.stdout.strip().splitlines()[-1])
    installed = str(installed_venv).replace("\\", "/")
    assert installed in payload["file"].replace("\\", "/"), (
        f"ajm 不是从 venv 里导入的：{payload['file']}"
    )
    assert payload["repo_src_in_path"] is False, (
        f"子进程 sys.path 里仍有仓库路径（门禁会假绿）：{probe.stdout}"
    )


# -- 2. 装完能不能用（D1 的 5 个失败点逐条） -------------------------------------


def test_installed_sources_and_timeline(installed_venv: Path, neutral_cwd: Path) -> None:
    sources = _run_jobsctl(installed_venv, "sources", cwd=neutral_cwd)
    assert sources.returncode == 0, sources.stderr
    assert sources.stdout.split() == ["acabridge", "fudan", "gaoxiaojob", "nju", "pku"]

    timeline = _run_jobsctl(installed_venv, "timeline", cwd=neutral_cwd)
    assert timeline.returncode == 0, timeline.stderr
    assert "Traceback" not in timeline.stderr


def test_installed_extract_uses_packaged_fixture_with_rule_evidence(
    installed_venv: Path, neutral_cwd: Path
) -> None:
    """D1 失败点 1：`from extract.engine import …` 曾在非 editable 安装下 ModuleNotFoundError。"""
    proc = _run_jobsctl(installed_venv, "extract", "--fixture", "pku", cwd=neutral_cwd)
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    assert "ModuleNotFoundError" not in proc.stderr
    # 规则名证据链（fixture 也得随包，否则 fixture 目录在安装树外找不到）
    assert "registered deadline rules:" in proc.stdout
    assert "deadline_cn_ymd" in proc.stdout


def test_installed_bench_is_honest_108_of_109_exit_1(
    installed_venv: Path, neutral_cwd: Path
) -> None:
    """D1 失败点 2+真值数据路径：bench 在非 editable 安装下也必须跑出同一口径。

    退出码 1 是诚实扣分项（position 95.5%），门禁断言的就是它——**不许断言 exit 0**。
    """
    proc = _run_jobsctl(installed_venv, "bench", cwd=neutral_cwd)
    assert "ModuleNotFoundError" not in proc.stderr, proc.stderr
    assert "overall 108/109 = 99.1%" in proc.stdout, proc.stdout
    assert "NOT PASSED" in proc.stdout
    assert proc.returncode == 1, f"bench 正确期望是退出码 1，实际 {proc.returncode}"


def test_installed_feed_without_config_is_friendly_not_traceback(
    installed_venv: Path, neutral_cwd: Path
) -> None:
    """D1 失败点 3：缺 subscribe.yaml 的既定行为 = 友好提示 + exit 2。"""
    proc = _run_jobsctl(installed_venv, "feed", cwd=neutral_cwd)
    assert "ModuleNotFoundError" not in proc.stderr, proc.stderr
    assert "Traceback" not in f"{proc.stdout}{proc.stderr}"
    assert proc.returncode == 2, proc.stderr
    assert "subscribe.example.yaml" in proc.stderr


def test_installed_webapp_is_constructible(installed_venv: Path, neutral_cwd: Path) -> None:
    """D1 失败点 4：web 链路不得缺包。

    真实起服务（绑端口）不进离线门禁（K7），改为在装好的 venv 里构造 app 并解析路由；
    `jobsctl web --help` 另行断言入口可用。
    """
    probe = _run_python(
        installed_venv,
        "import ajm.webapp.app as a; app = a.create_app(); print('routes', len(app.routes))",
        neutral_cwd,
    )
    assert probe.returncode == 0, probe.stderr
    assert "routes" in probe.stdout
    assert int(probe.stdout.split()[-1]) >= 4  # /、/timeline、/subscribe、/bench

    help_proc = _run_jobsctl(installed_venv, "web", "--help", cwd=neutral_cwd)
    assert help_proc.returncode == 0, help_proc.stderr


def test_installed_snapshot_import_path_present(installed_venv: Path, neutral_cwd: Path) -> None:
    """D1 失败点 5：snapshot 链路（`jobsctl snapshot` 要抓网，故只验 import 链 + 入口）。"""
    probe = _run_python(
        installed_venv,
        "from ajm.snapshot import SnapshotPipeline; "
        "from ajm.subscribe import SubscriptionConfig; print('ok')",
        neutral_cwd,
    )
    assert probe.returncode == 0, probe.stderr
    assert probe.stdout.strip() == "ok"
    assert _jobsctl(installed_venv).is_file()