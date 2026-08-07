import argparse
import copy
import tomllib
from create_backup import (
    BackupCopyError,
    BackupCreateError,
    MaintenanceDisableError,
    MaintenanceEnableError,
    create_backup,
)
from purge_backups import purge_backups
from encrypt_backup import encrypt_backup
from remote_backup import remote_backup
from purge_remote import purge_remote
from utils import REDACTED, install_redaction_filter, register_secrets
import logging
import json
import requests
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SECRET_KEYS = [("database", "password"), ("encryption", "password"), ("notifier", "discord-webhook")]


def redacted_config(config: dict[str, Any]) -> dict[str, Any]:
    """Copy of the config with the credentials masked, safe to write to the log."""
    safe = copy.deepcopy(config)
    for section, key in SECRET_KEYS:
        if safe.get(section, {}).get(key):
            safe[section][key] = REDACTED
    return safe


def main() -> None:
    parser = argparse.ArgumentParser(description="Create, prune and replicate Nextcloud backups")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not create, encrypt or copy anything. Only report which backups the retention policy would delete.",
    )
    args = parser.parse_args()

    with open("./config.toml", "rb") as f:
        config = tomllib.load(f)

    log_file = Path(config['general']['log_dir']) / f"{date.today().strftime('%Y-%m-%d')}_cloud_backup.log"
    logging.basicConfig(
        format="[%(asctime)s][%(levelname)s][%(name)s] - %(message)s",
        level=logging.DEBUG,
        filename=log_file
    )
    # Everything that reaches a log handler is filtered through these, so they
    # must be registered before the first command runs. Read defensively: none
    # of these keys is required to run a backup, and a KeyError here would abort
    # before notify() exists to report it.
    register_secrets(
        config.get('database', {}).get('password'),
        config.get('encryption', {}).get('password'),
        config.get('notifier', {}).get('discord-webhook'),
    )
    install_redaction_filter()
    logging.debug(f"Full config: {json.dumps(redacted_config(config), indent='  ')}")
    discord_webhook = config.get('notifier', {}).get('discord-webhook')

    def notify(message: str) -> None:
        if discord_webhook and message:
            requests.post(discord_webhook, json={"content": message})

    if args.dry_run:
        logger.info("DRY RUN: no backup will be created and no file will be deleted")
        purge_backups(config, dry_run=True)
        purge_remote(config, dry_run=True)
        return

    try:
        backup_type = create_backup(config)
        msg = ""
        if backup_type == "None":
            msg = "Backup script ran according to config no new backup was created"
        elif backup_type == "Failed":
            msg = "**Failed**: Backup script ran, but creation failed."
        elif backup_type == "Full":
            msg = "Full backup created"
        elif backup_type == "Diff":
            msg = "Differential backup created"
    except MaintenanceDisableError as e:
        notify(f"**CRITICAL**: Maintance mode could not be disabled, Nextcloud is still offline. Error: {e}")
        raise
    except MaintenanceEnableError as e:
        notify(f"**Failed**: Maintance mode could not be enabled, no backup was created. Error: {e}")
        raise
    except BackupCopyError as e:
        notify(f"**Failed**: Copying the data failed, no backup was created. Maintance mode was disabled again. Error: {e}")
        raise
    except BackupCreateError as e:
        notify(f"**Failed**: Writing the archive failed, the partial file was removed. Error: {e}")
        raise
    except Exception as e:
        notify(f"**Failed**: Backup run aborted with an unexpected error: {e}")
        raise

    purge_backups(config)
    if config.get('encryption', {}).get('enable'):
        encrypt_backup(config)
    sync_results = remote_backup(config)
    purge_remote(config, sync_results=sync_results)
    notify(msg)


if __name__ == "__main__":
    main()
