"""Retention decides what gets deleted, so it is tested against the cases that
actually happen on a backup host: half-written archives, an interrupted gpg,
mtimes that do not match the file names, and listings that are empty or odd.

Nothing here touches a real backup -- every test builds its own directory.
"""
import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import purge_remote
import utils
from purge_backups import group_by_backup, purge_backups
from utils import (
    FULL_BACKUP_REGEX,
    PARTIAL_SUFFIX,
    RedactionFilter,
    get_backup_files,
    redact,
    register_secrets,
)

FULL_SIZE = 512


def make(directory: Path, name: str, size: int = FULL_SIZE, mtime: Optional[float] = None) -> Path:
    path = directory / name
    path.write_bytes(b"x" * size)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def config(target: Path, num_full: int = 2, num_diff: int = 2) -> Dict[str, Any]:
    return {
        "general": {
            "target_dir": str(target),
            "num_full_backups": num_full,
            "num_differential_backups": num_diff,
        }
    }


def names(directory: Path) -> Set[str]:
    return {p.name for p in directory.iterdir()}


# --- H1: ordering must come from the file name, never the mtime ---------------

def test_mtime_order_does_not_decide_which_full_is_newest(tmp_path: Path) -> None:
    # gpg stamps mtimes in whatever order it walked the directory, so here the
    # oldest backup carries the newest mtime.
    make(tmp_path, "2026-01-01-01-full.tar.gz.gpg", mtime=3000)
    make(tmp_path, "2026-02-01-01-full.tar.gz.gpg", mtime=2000)
    make(tmp_path, "2026-03-01-01-full.tar.gz.gpg", mtime=1000)

    newest = get_backup_files(str(tmp_path), FULL_BACKUP_REGEX)[0]
    assert Path(newest).name == "2026-03-01-01-full.tar.gz.gpg"

    purge_backups(config(tmp_path, num_full=1))
    assert names(tmp_path) == {"2026-03-01-01-full.tar.gz.gpg"}


# --- H4: one backup on disk as two files is still one backup -----------------

def test_plaintext_and_its_encrypted_copy_count_as_one_backup(tmp_path: Path) -> None:
    make(tmp_path, "2026-03-01-01-full.tar.gz")
    make(tmp_path, "2026-03-01-01-full.tar.gz.gpg")
    assert len(group_by_backup(get_backup_files(str(tmp_path), FULL_BACKUP_REGEX))) == 1


def test_interrupted_encryption_does_not_evict_a_real_backup(tmp_path: Path) -> None:
    make(tmp_path, "2026-01-01-01-full.tar.gz.gpg")
    make(tmp_path, "2026-02-01-01-full.tar.gz.gpg")
    make(tmp_path, "2026-03-01-01-full.tar.gz")
    partial = make(tmp_path, "2026-03-01-01-full.tar.gz.gpg" + PARTIAL_SUFFIX, size=8)

    purge_backups(config(tmp_path, num_full=3))

    # Three backups, three kept. The .part is not a backup and is left alone.
    assert "2026-01-01-01-full.tar.gz.gpg" in names(tmp_path)
    assert partial.name in names(tmp_path)


# --- differentials and snapshots ---------------------------------------------

def test_differential_without_its_full_is_dropped(tmp_path: Path) -> None:
    make(tmp_path, "2026-02-01-01-full.tar.gz.gpg")
    make(tmp_path, "2026-03-01-01-full.tar.gz.gpg")
    make(tmp_path, "2026-02-02-01-differential.tar.gz.gpg")  # belongs to the purged full
    make(tmp_path, "2026-03-02-01-differential.tar.gz.gpg")

    purge_backups(config(tmp_path, num_full=1, num_diff=5))

    assert names(tmp_path) == {"2026-03-01-01-full.tar.gz.gpg", "2026-03-02-01-differential.tar.gz.gpg"}


def test_snar_of_the_newest_full_is_always_kept(tmp_path: Path) -> None:
    make(tmp_path, "2026-02-01-01-full.tar.gz.gpg")
    make(tmp_path, "2026-02-01-01-full.snar")
    make(tmp_path, "2026-03-01-01-full.tar.gz.gpg")
    make(tmp_path, "2026-03-01-01-full.snar")

    purge_backups(config(tmp_path, num_full=1))

    assert "2026-03-01-01-full.snar" in names(tmp_path)
    assert "2026-02-01-01-full.snar" not in names(tmp_path)


# --- degenerate inputs must never clear the directory ------------------------

def test_empty_directory_is_a_no_op(tmp_path: Path) -> None:
    purge_backups(config(tmp_path))
    assert names(tmp_path) == set()


def test_unreadable_names_are_kept_and_never_counted(tmp_path: Path) -> None:
    make(tmp_path, "backup-full.tar.gz.gpg")  # no timestamp in the name
    make(tmp_path, "2026-03-01-01-full.tar.gz.gpg")

    purge_backups(config(tmp_path, num_full=1))

    assert names(tmp_path) == {"backup-full.tar.gz.gpg", "2026-03-01-01-full.tar.gz.gpg"}


def test_zero_retention_still_keeps_one_full(tmp_path: Path) -> None:
    make(tmp_path, "2026-02-01-01-full.tar.gz.gpg")
    make(tmp_path, "2026-03-01-01-full.tar.gz.gpg")

    purge_backups(config(tmp_path, num_full=0))

    assert names(tmp_path) == {"2026-03-01-01-full.tar.gz.gpg"}


def test_dry_run_deletes_nothing(tmp_path: Path) -> None:
    for name in ("2026-01-01-01-full.tar.gz.gpg", "2026-02-01-01-full.tar.gz.gpg", "2026-03-01-01-full.tar.gz.gpg"):
        make(tmp_path, name)
    before = names(tmp_path)

    purge_backups(config(tmp_path, num_full=1), dry_run=True)

    assert names(tmp_path) == before


# --- H3: the remote sweep -----------------------------------------------------

def remote_config(target: Path, num_full: int = 2, num_diff: int = 2) -> Dict[str, Any]:
    cfg = config(target, num_full, num_diff)
    cfg["remote"] = {
        "cocytus": {
            "enable": True,
            "address": "cocytus",
            "target_dir": "/remote/restore_points",
            "username": "backup",
        }
    }
    return cfg


class FakeRemote:
    """Stands in for the ssh calls: serves a listing, records any rm."""

    def __init__(self, sizes: Dict[str, int]) -> None:
        self.sizes = sizes
        self.deleted: List[str] = []

    def output(self, cmd: List[str]) -> str:
        return "".join(f"{size} {name}\n" for name, size in self.sizes.items())

    def run(self, cmd: List[str], **kwargs: Any) -> bool:
        self.deleted = [part for part in cmd[-1].split() if part.startswith("/remote/")]
        return True


@pytest.fixture
def fake_remote(monkeypatch: Any) -> Callable[[Dict[str, int]], FakeRemote]:
    def install(sizes: Dict[str, int]) -> FakeRemote:
        fake = FakeRemote(sizes)
        monkeypatch.setattr(purge_remote, "run_cmd_output", fake.output)
        monkeypatch.setattr(purge_remote, "run_cmd", fake.run)
        return fake
    return install


def test_truncated_remote_full_is_ignored_and_evicts_nothing(
    tmp_path: Path, fake_remote: Callable[[Dict[str, int]], FakeRemote]
) -> None:
    for name in ("2026-01-01-01-full.tar.gz.gpg", "2026-02-01-01-full.tar.gz.gpg", "2026-03-01-01-full.tar.gz.gpg"):
        make(tmp_path, name)
    # The newest one only made it partway across the wire.
    fake = fake_remote({
        "2026-01-01-01-full.tar.gz.gpg": FULL_SIZE,
        "2026-02-01-01-full.tar.gz.gpg": FULL_SIZE,
        "2026-03-01-01-full.tar.gz.gpg": 12,
    })

    purge_remote.purge_remote(remote_config(tmp_path, num_full=2))

    # Two intact fulls, limit two: nothing may be deleted, least of all the
    # oldest good one to make room for the truncated file.
    assert fake.deleted == []


def test_remote_purge_still_trims_when_everything_is_intact(
    tmp_path: Path, fake_remote: Callable[[Dict[str, int]], FakeRemote]
) -> None:
    for name in ("2026-01-01-01-full.tar.gz.gpg", "2026-02-01-01-full.tar.gz.gpg", "2026-03-01-01-full.tar.gz.gpg"):
        make(tmp_path, name)
    fake = fake_remote({name: FULL_SIZE for name in names(tmp_path)})

    purge_remote.purge_remote(remote_config(tmp_path, num_full=2))

    assert fake.deleted == ["/remote/restore_points/" + tmp_path.name + "/2026-01-01-01-full.tar.gz.gpg"]


def test_remote_purge_is_skipped_when_the_copy_failed(
    tmp_path: Path, fake_remote: Callable[[Dict[str, int]], FakeRemote]
) -> None:
    make(tmp_path, "2026-03-01-01-full.tar.gz.gpg")
    fake = fake_remote({"2026-01-01-01-full.tar.gz.gpg": FULL_SIZE, "2026-02-01-01-full.tar.gz.gpg": FULL_SIZE})

    purge_remote.purge_remote(remote_config(tmp_path, num_full=1), sync_results={"cocytus": False})

    assert fake.deleted == []


def test_remote_retention_never_drops_below_the_local_one(tmp_path: Path) -> None:
    cfg = remote_config(tmp_path, num_full=10, num_diff=5)
    cfg["remote"]["cocytus"]["num_full_backups"] = 3
    assert purge_remote.retention_limits(cfg["remote"]["cocytus"], cfg) == (10, 5)


# --- H5: nothing secret reaches a handler ------------------------------------

def test_redaction_covers_library_log_records() -> None:
    register_secrets("https://discord.com/api/webhooks/1/s3cr3t")
    record = logging.LogRecord(
        name="urllib3.connectionpool", level=logging.DEBUG, pathname=__file__, lineno=1,
        msg='%s "POST %s HTTP/1.1" 204', args=("https://discord.com:443", "https://discord.com/api/webhooks/1/s3cr3t"),
        exc_info=None,
    )

    assert RedactionFilter().filter(record) is True
    assert "s3cr3t" not in record.getMessage()
    assert utils.REDACTED in record.getMessage()


def test_redact_masks_every_registered_secret() -> None:
    register_secrets("db-pass-1", "gpg-pass-2")
    assert redact("--password=db-pass-1 --passphrase gpg-pass-2") == f"--password={utils.REDACTED} --passphrase {utils.REDACTED}"
