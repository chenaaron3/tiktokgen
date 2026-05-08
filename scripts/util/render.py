"""Remotion CLI: copy plan media into ``public/``, run ``npm run render``, clean up staging."""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path

from edit.schema_render_plan import RenderPlan
from project_inputs import PROJECT_ROOT
from util.path_util import PathUtil

_REMOTION_PUBLIC_DIR = PROJECT_ROOT / "remotion" / "public"


def _relative_if_under_public(path: Path) -> str | None:
    """POSIX path relative to the Remotion public dir, or None if outside it."""
    pub = _REMOTION_PUBLIC_DIR
    try:
        return path.resolve().relative_to(pub.resolve()).as_posix()
    except ValueError:
        return None


def copy_plan_media_to_public(plan: RenderPlan) -> Path | None:
    """Normalize local media to paths relative to ``remotion/public`` (Remotion ``--public-dir``).

    Paths must be absolute filesystem paths (no ``http(s)://`` or ``file://``). Files already
    under public are rewritten to a POSIX path relative to that directory. Anything else is
    copied into ``render-assets/<uuid>/``.
    Mutates ``plan`` in place.
    """
    public_dir = _REMOTION_PUBLIC_DIR
    asset_dir: Path | None = None
    public_rel_by_src: dict[str, str] = {}

    def staging_dir() -> Path:
        nonlocal asset_dir
        if asset_dir is None:
            asset_dir = public_dir / "render-assets" / uuid.uuid4().hex
            asset_dir.mkdir(parents=True, exist_ok=False)
        return asset_dir

    def rewrite(path_str: str | None) -> str | None:
        if not path_str or not isinstance(path_str, str):
            return path_str
        assert not path_str.startswith(
            ("http://", "https://", "file://")
        ), f"expected absolute filesystem path, got {path_str!r}"
        assert Path(path_str).is_absolute(), f"expected absolute path, got {path_str!r}"
        src = Path(path_str).expanduser().resolve()

        if not src.is_file():
            raise RuntimeError(f"Missing media file: {src}")
        rel_existing = _relative_if_under_public(src)
        if rel_existing is not None:
            return rel_existing

        key = str(src.resolve())
        if key not in public_rel_by_src:
            dst = staging_dir() / f"{len(public_rel_by_src):03d}-{src.name}"
            shutil.copy2(src, dst)
            public_rel_by_src[key] = dst.relative_to(public_dir).as_posix()
        return public_rel_by_src[key]

    if plan.voiceover_static_path:
        updated_voice = rewrite(plan.voiceover_static_path)
        assert updated_voice is not None
        plan.voiceover_static_path = updated_voice

    for beat in plan.beats:
        updated = rewrite(beat.source_path)
        assert updated is not None
        beat.source_path = updated

    return asset_dir


def run_remotion_render(plan: RenderPlan, paths: PathUtil) -> None:
    """Stage media under ``remotion/public``, render AiShort to the run default MP4, remove staging."""
    asset_dir = copy_plan_media_to_public(plan)
    try:
        mp4 = paths.default_render_mp4()
        command = [
            "npm",
            "run",
            "render",
            "--",
            str(mp4),
            "--public-dir",
            str(_REMOTION_PUBLIC_DIR),
            "--props",
            json.dumps(plan.model_dump(by_alias=True), ensure_ascii=False),
        ]
        print(f"\n==> Remotion render\n{' '.join(command)}")
        proc = subprocess.run(command, cwd=str(PROJECT_ROOT), check=False, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"render failed with exit code {proc.returncode}")
    finally:
        if asset_dir is not None:
            shutil.rmtree(asset_dir, ignore_errors=True)
