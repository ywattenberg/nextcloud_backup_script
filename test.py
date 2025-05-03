import tomllib
from create_backup import create_backup
import logging
logging.basicConfig(format="[%(asctime)s][%(levelname)s][%(name)s] - %(message)s", level=logging.DEBUG)

if __name__ == "__main__":
    with open("/home/wattenberg/Documents/Repositories/nextcloud_backup_script/config.toml", "rb") as f:
        config = tomllib.load(f)

    create_backup(config)
