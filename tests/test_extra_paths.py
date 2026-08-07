"""The Nextcloud data dir is not the whole instance -- config.php and the
installed app code live outside it. These tests cover which paths get staged
into the archive and what happens when one of them is not there.

The rsync itself is left to the dry run; only the decision is tested here.
"""
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from create_backup import EXTRA_DIR, plan_extra_copies, prune_stale_extras


def test_directory_and_file_both_map_into_the_extra_dir(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.php").write_text("<?php")
    loose = tmp_path / "loose.conf"
    loose.write_text("x")
    staging = str(tmp_path / "tmp")

    copies, missing = plan_extra_copies([str(config_dir), str(loose)], staging)

    assert missing == []
    assert [source for source, _ in copies] == [str(config_dir), str(loose)]
    # rsync is handed the source without a trailing slash, so it creates
    # <extra>/<basename> for both a directory and a single file.
    assert {dest for _, dest in copies} == {os.path.join(staging, EXTRA_DIR)}


def test_missing_path_is_reported_and_does_not_raise(tmp_path: Path) -> None:
    present = tmp_path / "config"
    present.mkdir()

    copies, missing = plan_extra_copies([str(present), "/does/not/exist"], str(tmp_path / "tmp"))

    assert [source for source, _ in copies] == [str(present)]
    assert missing == ["/does/not/exist"]


def test_no_extra_paths_is_a_no_op(tmp_path: Path) -> None:
    assert plan_extra_copies([], str(tmp_path)) == ([], [])


def test_relative_paths_are_resolved(tmp_path: Path) -> None:
    (tmp_path / "config").mkdir()
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        copies, missing = plan_extra_copies(["config"], "tmp")
    finally:
        os.chdir(cwd)

    assert missing == []
    assert copies[0][0] == str((tmp_path / "config").resolve())


def test_dropping_a_path_from_the_config_removes_its_stale_copy(tmp_path: Path) -> None:
    extra_root = tmp_path / EXTRA_DIR
    (extra_root / "config").mkdir(parents=True)
    (extra_root / "config" / "config.php").write_text("<?php")
    (extra_root / "custom_apps").mkdir()
    (extra_root / "leftover.txt").write_text("old")

    prune_stale_extras(str(extra_root), ["config", "custom_apps"])

    assert {p.name for p in extra_root.iterdir()} == {"config", "custom_apps"}
    assert (extra_root / "config" / "config.php").exists()


def test_pruning_keeps_everything_when_all_are_configured(tmp_path: Path) -> None:
    extra_root = tmp_path / EXTRA_DIR
    extra_root.mkdir()
    (extra_root / "config").mkdir()

    prune_stale_extras(str(extra_root), ["config"])

    assert {p.name for p in extra_root.iterdir()} == {"config"}
