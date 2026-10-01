"""Validated, atomically written configuration with corruption recovery."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

log = logging.getLogger(__name__)


class AISettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    provider: Literal["anthropic", "openai", "gemini", "mock"] = "anthropic"
    model: str = ""  # empty = provider default
    confidence_threshold: float = Field(0.75, ge=0.3, le=0.99)
    timeout_s: float = Field(30.0, ge=5, le=120)
    retries: int = Field(2, ge=0, le=5)
    effort: Literal["low", "medium", "high"] = "low"
    cost_saver: bool = True
    vision_quality: Literal["low", "balanced", "high"] = "balanced"

    @property
    def png_max_side(self) -> int:
        return {"low": 640, "balanced": 1024, "high": 1568}[self.vision_quality]


class DetectionSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    ocr_backend: Literal["auto", "windows", "tesseract"] = "auto"
    title_patterns: list[str] = Field(
        default_factory=lambda: [
            r"360\s*°?\s*online",
            r"click\s*&\s*learn",
            r"degener",
            r"360°",
            r"fahrschul-?campus",
        ]
    )
    change_threshold: float = Field(3.0, ge=0.5, le=30)
    active_profile: str = ""  # empty = automatic choice
    profiles: list[dict[str, Any]] = Field(default_factory=list)


class ControlSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    confirm: str = "ENTER"
    reject: str = "ESC"
    pause: str = "F8"
    reanalyze: str = "F9"
    mini_mode: str = "CTRL+SHIFT+M"
    quit: str = "CTRL+SHIFT+Q"
    emergency_stop: str = "CTRL+SHIFT+X"  # always registered: stops everything, shows STOPPED
    global_hotkeys: bool = True
    execute_on_confirm: bool = True  # False = advisory only, never touch the mouse


class AppearanceSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    overlay_mode: Literal["full", "focus", "orbit"] = "full"
    overlay_opacity: float = Field(0.96, ge=0.35, le=1.0)
    overlay_pinned: bool = True
    overlay_pos: list[int] | None = None
    reduce_motion: bool = False
    sounds: bool = False
    system_backdrop: bool = True


class SafetySettings(BaseModel):
    """Conservative defaults for the first tests on a real PC with the real 360° online software."""

    model_config = ConfigDict(extra="ignore")
    # no click for uncertain predictions, estimated checkbox positions, a window that moved since the
    # question was read, ambiguous targets; no click retries
    safe_mode: bool = True
    # do everything up to the click, show WHERE it would click, click nothing - switch off deliberately
    dry_run: bool = True


class PrivacySettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    debug_screenshots: bool = False
    # per-question trace (capture -> OCR -> AI -> decision -> click) for "Create diagnosis"; images are crops
    # of the question/answer area only. Never contains API keys.
    session_trace: bool = True
    trace_images: bool = True
    store_question_text: bool = True
    history_retention_days: int = Field(90, ge=1, le=3650)


class FeatureFlags(BaseModel):
    model_config = ConfigDict(extra="ignore")
    orbit_mode: bool = True
    auto_advance: bool = False  # click the "next" button after a verified answer (experimental)
    number_input: bool = False  # type number answers (experimental)


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    version: int = 1
    first_run_done: bool = False
    demo_mode: bool = False
    ai: AISettings = Field(default_factory=AISettings)
    detection: DetectionSettings = Field(default_factory=DetectionSettings)
    controls: ControlSettings = Field(default_factory=ControlSettings)
    appearance: AppearanceSettings = Field(default_factory=AppearanceSettings)
    privacy: PrivacySettings = Field(default_factory=PrivacySettings)
    safety: SafetySettings = Field(default_factory=SafetySettings)
    flags: FeatureFlags = Field(default_factory=FeatureFlags)

    @field_validator("version")
    @classmethod
    def _v(cls, v: int) -> int:
        return max(1, v)


class ConfigStore:
    """Thread-safe load/save. A corrupted file is quarantined and defaults are used."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()
        self.recovered = False
        self.problem: str | None = None
        self.config = self._load()

    def _load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig()
        for candidate in (self.path, self.path.with_suffix(".json.bak")):
            if not candidate.exists():
                continue
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                cfg = AppConfig.model_validate(data)
                if candidate != self.path:
                    self.recovered = True
                    self.problem = "config restored from backup"
                return cfg
            except (OSError, json.JSONDecodeError, ValidationError) as e:
                log.warning("config %s unreadable: %s", candidate.name, e)
                self.problem = f"config corrupted: {type(e).__name__}"
        # both unusable -> quarantine and start with defaults
        stamp = time.strftime("%Y%m%d-%H%M%S")
        try:
            self.path.replace(self.path.with_name(self.path.name + f".corrupt-{stamp}"))
        except OSError:
            pass
        self.recovered = True
        return AppConfig()

    def save(self) -> None:
        with self._lock:
            data = self.config.model_dump_json(indent=2)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists():
                try:
                    self.path.with_suffix(".json.bak").write_bytes(self.path.read_bytes())
                except OSError:
                    pass
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".config-", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, self.path)
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise

    def update(self, **changes: Any) -> AppConfig:
        """Validated partial update, e.g. update(ai={"provider": "openai"})."""
        with self._lock:
            merged = self.config.model_dump()
            for k, v in changes.items():
                if isinstance(v, dict) and isinstance(merged.get(k), dict):
                    merged[k].update(v)
                else:
                    merged[k] = v
            self.config = AppConfig.model_validate(merged)
            self.save()
            return self.config
