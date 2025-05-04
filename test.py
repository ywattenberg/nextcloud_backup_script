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
    s = ["saodfisoi.tar.gz.gpg", "dfdsfsdfpf.tar.gpp", "oifoij.tar", "d.tar.gz"]
    for a in s:
        print(regex.fullmatch(a), a)

