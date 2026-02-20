import tomllib
from create_backup import create_backup
from purge_backups import purge_backups
from encrypt_backup import encrypt_backup
from remote_backup import remote_backup
import logging
import json
import requests


if __name__ == "__main__":
    with open("./config.toml", "rb") as f:
        config = tomllib.load(f)

    logging.basicConfig(
        format="[%(asctime)s][%(levelname)s][%(name)s] - %(message)s",
        level=logging.DEBUG,
        filename=config['general']['log_file']
    )
    logging.debug(f"Full config: {json.dumps(config, indent='  ')}")
    discord_webkhook = config['notifier']['discord-webhook']

    try:
        type = create_backup(config)
        msg = "" 
        if type == "None":
            msg = "Backup script ran according to config no new backup was created"
        elif type == "Failed":
            msg = "**Failed**: Backup script ran, but creation failed."
        elif type == "Full":
            msg = "Full backup created"
        elif type == "Diff":
            msg = "Differential backup created"
    except Exception as e:
        data = {"content": f"**CRITICAL**: Maintance mode could not be disabled. Error: {e}"}
        requests.post(discord_webkhook, json=data)
        raise e


    purge_backups(config)
    if config['encryption']['enable']:
        encrypt_backup(config)
    remote_backup(config)
    data = {"content": msg}
    requests.post(discord_webkhook, json=data)
    
