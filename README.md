# Nextcloud Backup Script

Automated backup solution for self-hosted Nextcloud instances running in Docker. Supports full and differential (incremental) backups, encryption, remote replication, and automatic purging of old backups.

## Features

- **Full & differential backups** using `tar` with incremental snapshots (`.snar` files) and `pigz` compression
- **Database backups** via `mariadb-dump` (with Docker exec support)
- **Maintenance mode** handling — automatically enabled before backup and disabled after (with retry logic)
- **AES-256 encryption** using GPG (optional)
- **Remote replication** via `rsync` over SSH to one or more remote hosts
- **Automatic purging** of old full and differential backups based on retention policy
- **Discord notifications** via webhook on backup completion or failure
- **Configurable scheduling** — control intervals between full and differential backups

## Requirements

- Python 3.11+ (uses `tomllib`)
- `tar`, `pigz`, `rsync`
- `gpg` (if encryption is enabled)
- Docker & Docker Compose (if Nextcloud runs in Docker)
- `mariadb-dump` (available in the DB container or on the host)

## Configuration

All settings are defined in `config.toml`. Copy and edit it to match your setup:

```toml
[general]
maintance_cmd = "/usr/bin/docker compose -f /path/to/docker-compose.yml exec -ti --user www-data app /var/www/html/occ maintenance:mode"
log_file = "/var/log/cloud_backup.log"
source_dir = "/path/to/nextcloud/data/"
tmp_dir = "/path/to/backup_tmp"
target_dir = "/path/to/backup_storage"
num_full_backups = 1              # Number of full backups to retain
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

Run the backup manager directly:

```bash
python backup_manager.py
```

The script will:

1. Check if a new backup is needed based on the configured intervals
2. Enable Nextcloud maintenance mode
3. Dump the MariaDB database
4. Copy data files to the temp directory via `rsync`
5. Disable maintenance mode
6. Compress the backup (full or differential) with `tar` + `pigz`
7. Purge old backups according to retention settings
8. Encrypt the backup with GPG (if enabled)
9. Replicate to remote hosts via `rsync` (if configured)
10. Send a Discord notification with the result

### Cron setup

To run daily via cron (as root, since Docker and file access may require it):

```bash
# Edit root's crontab
sudo crontab -e

# Run backup daily at 3 AM
0 3 * * * cd /path/to/nextcloud_backup_script && python backup_manager.py
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

### Encryption

When enabled, each `.tar.gz` backup is encrypted with GPG symmetric encryption (AES-256). The unencrypted file is deleted after successful encryption, leaving only `.tar.gz.gpg` files.

### Remote replication

Backups are synced to remote hosts using `rsync` with `--append --inplace` flags for efficient transfers of large files. Each remote host manages its own retention independently.

## File structure

```
backup_manager.py     # Entry point — orchestrates the full backup pipeline
create_backup.py      # Backup creation (full & differential)
encrypt_backup.py     # GPG encryption of backup archives
purge_backups.py      # Retention policy enforcement
remote_backup.py      # rsync replication to remote hosts
utils.py              # Shared helpers (command execution, file utilities)
config.toml           # Configuration file
```
