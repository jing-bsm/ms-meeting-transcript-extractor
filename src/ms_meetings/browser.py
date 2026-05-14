from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
import contextlib
import os
import shutil
import tempfile

from playwright.sync_api import BrowserContext
from playwright.sync_api import Page
from playwright.sync_api import Playwright
from playwright.sync_api import sync_playwright


DEFAULT_CHROME_PATH = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
DEFAULT_USER_DATA_DIR = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"


@dataclass
class BrowserConfig:
    chrome_path: Path = DEFAULT_CHROME_PATH
    user_data_dir: Path = DEFAULT_USER_DATA_DIR
    profile_directory: str = "Default"
    headless: bool = False
    timeout_ms: int = 45000


class BrowserLaunchError(RuntimeError):
    pass


@contextlib.contextmanager
def open_page(config: BrowserConfig, url: str) -> Iterator[tuple[Playwright, BrowserContext, Page]]:
    if not config.chrome_path.exists():
        raise BrowserLaunchError(f"Chrome binary not found: {config.chrome_path}")
    if not config.user_data_dir.exists():
        raise BrowserLaunchError(f"Chrome user data directory not found: {config.user_data_dir}")

    playwright = sync_playwright().start()
    context: BrowserContext | None = None
    snapshot_dir: tempfile.TemporaryDirectory[str] | None = None
    try:
        try:
            context = _launch_context(playwright=playwright, config=config, user_data_dir=config.user_data_dir)
        except Exception as exc:
            if not _is_profile_lock_error(exc):
                raise
            snapshot_dir = _build_profile_snapshot(config)
            context = _launch_context(
                playwright=playwright,
                config=config,
                user_data_dir=Path(snapshot_dir.name),
            )
        context.set_default_timeout(config.timeout_ms)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(url, wait_until="domcontentloaded")
        yield playwright, context, page
    except Exception as exc:  # pragma: no cover - integration error path
        message = str(exc)
        if "SingletonLock" in message or "profile" in message.lower():
            message = (
                "Chrome profile is locked. Close all Google Chrome windows and retry. "
                f"Original error: {exc}"
            )
        raise BrowserLaunchError(message) from exc
    finally:
        if context is not None:
            context.close()
        if snapshot_dir is not None:
            snapshot_dir.cleanup()
        playwright.stop()


def load_env_browser_config() -> BrowserConfig:
    chrome_path = Path(os.environ.get("MS_MEETINGS_CHROME_PATH", DEFAULT_CHROME_PATH))
    user_data_dir = Path(os.environ.get("MS_MEETINGS_CHROME_USER_DATA_DIR", DEFAULT_USER_DATA_DIR))
    profile_directory = os.environ.get("MS_MEETINGS_CHROME_PROFILE", "Default")
    return BrowserConfig(
        chrome_path=chrome_path,
        user_data_dir=user_data_dir,
        profile_directory=profile_directory,
        headless=os.environ.get("MS_MEETINGS_HEADLESS", "false").lower() == "true",
        timeout_ms=int(os.environ.get("MS_MEETINGS_TIMEOUT_MS", "45000")),
    )


def _launch_context(playwright: Playwright, config: BrowserConfig, user_data_dir: Path) -> BrowserContext:
    return playwright.chromium.launch_persistent_context(
        user_data_dir=str(user_data_dir),
        executable_path=str(config.chrome_path),
        channel="chrome",
        headless=config.headless,
        args=[f"--profile-directory={config.profile_directory}"],
        viewport={"width": 1440, "height": 1100},
    )


def _build_profile_snapshot(config: BrowserConfig) -> tempfile.TemporaryDirectory[str]:
    temp_dir = tempfile.TemporaryDirectory(prefix="ms-meetings-chrome-")
    root = Path(temp_dir.name)
    source_profile_dir = config.user_data_dir / config.profile_directory
    target_profile_dir = root / config.profile_directory

    if not source_profile_dir.exists():
        raise BrowserLaunchError(f"Chrome profile directory not found: {source_profile_dir}")

    shutil.copytree(
        source_profile_dir,
        target_profile_dir,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(
            "Cache",
            "Code Cache",
            "Crashpad",
            "GPUCache",
            "ShaderCache",
            "GrShaderCache",
            "Singleton*",
        ),
    )

    local_state = config.user_data_dir / "Local State"
    if local_state.exists():
        shutil.copy2(local_state, root / "Local State")
    return temp_dir


def _is_profile_lock_error(exc: Exception) -> bool:
    message = str(exc)
    return "SingletonLock" in message or "profile" in message.lower() or "user data directory is already in use" in message.lower()