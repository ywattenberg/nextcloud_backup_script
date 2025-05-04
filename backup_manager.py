import tomllib
from create_backup import create_backup
from purge_backups import purge_backups
import logging
import json


if __name__ == "__main__":
    with open("./config.toml", "rb") as f:
        config = tomllib.load(f)

    logging.basicConfig(
        format="[%(asctime)s][%(levelname)s][%(name)s] - %(message)s",
        level=logging.DEBUG,
        filename=config['general']['log_file']
    )
    logging.debug(f"Full config: {json.dumps(config, indent='  ')}")

    create_backup(config)
    purge_backups(config)
    
