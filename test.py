import tomllib
from create_backup import create_backup
from purge_backups import purge_backups
import logging
logging.basicConfig(format="[%(asctime)s][%(levelname)s][%(name)s] - %(message)s", level=logging.DEBUG)

if __name__ == "__main__":
    with open("./config.toml", "rb") as f:
        config = tomllib.load(f)

    create_backup(config)
    purge_backups(config)
    
