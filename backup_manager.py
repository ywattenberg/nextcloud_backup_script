import tomllib
from create_backup import create_backup
from purge_backups import purge_backups
from encrypt_backup import encrypt_backup
from remote_backup import remote_backup
import logging
import json
import requests
from datetime import date
from pathlib import Path


def main() -> None:
    with open("./config.toml", "rb") as f:
        config = tomllib.load(f)

    log_file = Path(config['general']['log_dir']) / f"{date.today().strftime('%Y-%m-%d')}_cloud_backup.log"
    logging.basicConfig(
        format="[%(asctime)s][%(levelname)s][%(name)s] - %(message)s",
        level=logging.DEBUG,
        filename=log_file
    )
    logging.debug(f"Full config: {json.dumps(config, indent='  ')}")
    discord_webhook = config['notifier']['discord-webhook']

    def notify(message: str) -> None:
        if discord_webhook:
            requests.post(discord_webhook, json={"content": message})

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
    except Exception as e:
        notify(f"**CRITICAL**: Maintance mode could not be disabled. Error: {e}")
        raise

    purge_backups(config)
    if config['encryption']['enable']:
        encrypt_backup(config)
    remote_backup(config)
    notify(msg)


if __name__ == "__main__":
    main()
