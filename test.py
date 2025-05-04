import re 
import tomllib
import logging
logging.basicConfig(format="[%(asctime)s][%(levelname)s][%(name)s] - %(message)s", level=logging.DEBUG)

if __name__ == "__main__":
    with open("./config.toml", "rb") as f:
        config = tomllib.load(f)

    # create_backup(config)
    # purge_backups(config)
    
    regex = re.compile(r".*-full\.tar\.gz(?:\.gpg)?")
    s = ["saodfisoi-full.tar.gz.gpg", "dfdsfsdfpf-full.tar.gpp", "oifoij-full.tar", "d-full.tar.gz"]
    for a in s:
        print(regex.fullmatch(a))

