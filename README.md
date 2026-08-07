# Nextcloud Backup Script

Automated backup solution for self-hosted Nextcloud instances running in Docker. Supports full and differential (incremental) backups, encryption, remote replication, and automatic purging of old backups.

## Features

- **Full & differential backups** using `tar` with incremental snapshots (`.snar` files) and `pigz` compression
- **Database backups** via `mariadb-dump` (with Docker exec support)
- **Maintenance mode** handling — automatically enabled before backup and disabled after (with retry logic)
- **AES-256 encryption** using GPG (optional)
- **Remote replication** via `rsync` over SSH to one or more remote hosts
- **Automatic purging** of old full and differential backups, locally and on the remotes, based on retention policy
- **Discord notifications** via webhook on backup completion or failure
- **Configurable scheduling** — control intervals between full and differential backups

## Requirements

- Python 3.11+ (uses `tomllib`)
- [uv](https://docs.astral.sh/uv/) for dependency management
- `tar`, `pigz`, `rsync`
- `gpg` (if encryption is enabled)
- Docker & Docker Compose (if Nextcloud runs in Docker)
- `mariadb-dump` (available in the DB container or on the host)

## Setup

```bash
# Install dependencies
uv sync

# Type-check (optional)
uv run mypy .

# Run the tests
uv run pytest
```

## Configuration

All settings are defined in `config.toml`. Copy and edit it to match your setup:

```toml
[general]
maintance_cmd = "/usr/bin/docker compose -f /path/to/docker-compose.yml exec -ti --user www-data app /var/www/html/occ maintenance:mode"
log_dir = "/var/log"              # One log file per day is written in here
source_dir = "/path/to/nextcloud/data/"
tmp_dir = "/path/to/backup_tmp"
target_dir = "/path/to/backup_storage"
num_full_backups = 10             # Number of full backups to retain
num_differential_backups = 5      # Number of differential backups to retain
days_between_backups = 7          # Days between full backups
days_between_diff_backups = 1     # Days between differential backups

[database]
username = "nextcloud"
password = "your_db_password"
db_name = "nextcloud"

[docker]
enable = true
nc_container_name = "app"
db_container_name = "db"
compose_file = "/path/to/docker-compose.yml"

[encryption]
enable = true
password = "your_gpg_passphrase"

[remote.my_server]
enable = true
address = "backup-host"
target_dir = "/mnt/backup/nextcloud"
username = "backup_user"
ssh_key = "/home/user/.ssh/id_ecdsa"
run_as = "someuser"               # Optional: run the rsync/ssh as this user
num_full_backups = 10             # Optional: retention on the remote, defaults to [general]
num_differential_backups = 5

[notifier]
discord-webhook = "https://discord.com/api/webhooks/..."
```

### Key options

| Section | Option | Description |
|---------|--------|-------------|
| `general` | `source_dir` | Nextcloud data directory to back up |
| `general` | `target_dir` | Where backups are stored locally |
| `general` | `tmp_dir` | Temporary directory for staging files before compression |
| `general` | `days_between_backups` | Minimum days between full backups |
| `general` | `days_between_diff_backups` | Minimum days between differential backups |
| `general` | `num_full_backups` | How many full backups to keep |
| `encryption` | `enable` | Set to `true` to encrypt backups with GPG (AES-256) |
| `remote.*` | `enable` | Set to `true` to rsync backups to this remote host |

## Usage

Run the backup manager:

```bash
uv run python backup_manager.py
```

The script will:

1. Check if a new backup is needed based on the configured intervals
2. Enable Nextcloud maintenance mode
3. Dump the MariaDB database
4. Copy data files to the temp directory via `rsync`
5. Disable maintenance mode
6. Compress the backup (full or differential) with `tar` + `pigz`
7. Purge old local backups according to retention settings
8. Encrypt the backup with GPG (if enabled)
9. Replicate to remote hosts via `rsync` (if configured)
10. Purge old backups on the remote hosts according to retention settings
11. Send a Discord notification with the result

### Dry run

To see which backups the retention policy would delete, locally and on every remote, without
creating, encrypting or copying anything:

```bash
uv run python backup_manager.py --dry-run
```

Run this after changing any retention setting — the remote purge deletes over SSH, so it is worth
reading the list once before letting it run for real.

### Cron setup

To run daily via cron (as root, since Docker and file access may require it):

```bash
# Edit root's crontab
sudo crontab -e

# Run backup daily at 3 AM
0 3 * * * cd /path/to/nextcloud_backup_script && uv run python backup_manager.py
```

## How it works

### Backup types

- **Full backup**: A complete snapshot of the Nextcloud data directory and database. Creates a `.snar` file for tracking incremental changes.
- **Differential backup**: Only files changed since the last full backup, using the `.snar` snapshot file. Smaller and faster than full backups.

### Backup lifecycle

```
Day 1:  Full backup created     → 2025-01-01-03-full.tar.gz + .snar
Day 2:  Differential backup     → 2025-01-02-03-differential.tar.gz
Day 3:  Differential backup     → 2025-01-03-03-differential.tar.gz
...
Day 8:  New full backup, old one purged based on retention
```

### Retention

Each differential is built from a *copy* of the full backup's `.snar`, so it contains everything
that changed since that full. Any one full plus any one of its differentials is therefore a complete
restore point, and dropping differentials in the middle breaks no chain.

The purge keeps the newest `num_full_backups` fulls and the newest `num_differential_backups`
differentials, and additionally drops differentials whose full backup is gone, since those can no
longer be restored. `.snar` files are kept only for retained full backups — the newest full is always
retained, so the snapshot needed to build the next differential is never removed.

"Newest" is read from the timestamp in the file name, never from the mtime: the mtime of an
encrypted backup records when `gpg` finished, which can be hours later and in a different order.
Files whose name does not fit the scheme are never counted towards a limit and never deleted.

A half-written file must never be mistaken for a restore point, so several checks exist: a failed
`tar` deletes its partial archive and aborts the run, `gpg` writes to a `.part` and is renamed into
place only on success, and the remote purge compares each remote file against the size of its local
counterpart — a mismatch means the transfer was cut short, so the file is ignored rather than counted
or deleted. A remote whose `rsync` failed this run is not purged at all.

### Encryption

When enabled, each `.tar.gz` backup is encrypted with GPG symmetric encryption (AES-256). The unencrypted file is deleted after successful encryption, leaving only `.tar.gz.gpg` files.

The passphrase is passed to `gpg` on stdin rather than as an argument, so it does not appear in the
process list. Credentials are filtered out of every log record on its way to a handler, which covers
library logging too — `requests`/`urllib3` write the full request URL at DEBUG, webhook token
included. `config.toml` itself holds the credentials in plaintext, so keep it `chmod 600`.

### Remote replication

Backups are synced to remote hosts using `rsync` with `--append --inplace` flags for efficient transfers of large files. Each remote host manages its own retention independently.

## File structure

```
backup_manager.py     # Entry point — orchestrates the full backup pipeline
create_backup.py      # Backup creation (full & differential)
encrypt_backup.py     # GPG encryption of backup archives
purge_backups.py      # Local retention policy enforcement
remote_backup.py      # rsync replication to remote hosts
purge_remote.py       # Retention policy enforcement on the remote hosts
utils.py              # Shared helpers (command execution, file utilities, log redaction)
tests/                # pytest suite for the retention decisions
config.toml           # Configuration file
pyproject.toml        # Project metadata, dependencies, and mypy config
uv.lock               # Locked dependency versions
```
