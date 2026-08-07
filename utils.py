from typing import List, Optional
from datetime import datetime
import os
import re
import logging
import subprocess
import time

logger = logging.getLogger(__name__)

_SECRETS: List[str] = []
REDACTED = "***REDACTED***"

# Naming scheme of the artefacts in the backup dir, e.g.
# 2026-08-06-01-full.tar.gz.gpg / 2026-08-06-01-differential.tar.gz / 2026-08-06-01-full.snar
FULL_BACKUP_REGEX = r".*-full\.tar\.gz(?:\.gpg)?$"
DIFF_BACKUP_REGEX = r".*-differential\.tar\.gz(?:\.gpg)?$"
ANY_BACKUP_REGEX = r".*-(?:full|differential)\.tar\.gz(?:\.gpg)?$"
SNAR_REGEX = r".*\.snar$"
# Suffix for files that are still being written. Never matches the patterns above.
PARTIAL_SUFFIX = ".part"


def backup_prefix(name: str) -> str:
    """Strip directory and suffixes: '<dir>/2026-08-06-01-full.tar.gz.gpg' -> '2026-08-06-01-full'."""
    return os.path.basename(name).split('.')[0]


def backup_timestamp(name: str, warn: bool = True) -> Optional[datetime]:
    """Parse the creation time out of a backup file name, None if it does not fit the scheme."""
    stamp = backup_prefix(name).replace("-full", "").replace("-differential", "")
    try:
        return datetime.strptime(stamp, "%Y-%m-%d-%H")
    except ValueError:
        if warn:
            logger.warning(f"Could not read a timestamp from {name}. It will be left alone.")
        return None


def register_secrets(*secrets: Optional[str]) -> None:
    """Register values that must never end up in the log file.

    Everything logged by run_cmd/run_cmd_with_progress is passed through
    redact(), so registering here covers all current and future call sites.
    """
    for secret in secrets:
        if secret and secret not in _SECRETS:
            _SECRETS.append(secret)


class RedactionFilter(logging.Filter):
    """Run redact() over every record on its way to a handler.

    Calling redact() at the call site only covers our own log lines. Libraries
    log too: requests/urllib3 write the full request URL at DEBUG, which puts
    the Discord webhook token in the log file on every run. Filtering at the
    handler catches those, and anything else added later.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if isinstance(record.args, dict):
            record.args = {k: redact(v) if isinstance(v, str) else v for k, v in record.args.items()}
        elif record.args:
            record.args = tuple(redact(a) if isinstance(a, str) else a for a in record.args)
        return True


def install_redaction_filter() -> None:
    """Attach the redaction filter to every root handler. Call after basicConfig."""
    redaction = RedactionFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(redaction)
    # Belt and braces: this is the library that leaks the webhook URL today.
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def redact(text: str) -> str:
    """Replace every registered secret in text with a placeholder."""
    for secret in _SECRETS:
        text = text.replace(secret, REDACTED)
    return text


def get_docker_prepend(docker_config: dict[str, str], user:Optional[str]=None, container_name:Optional[str]=None) -> List[str]:
    if not container_name:
        container_name = docker_config['container_name']
    return  [
        "/usr/bin/docker",
        "compose",
        "-f",
        docker_config['compose_file'],
        "exec",
        container_name,
    ] + (["--user", user,] if user else [])


def run_cmd(cmd:List[str], shell:bool=False, stdin_data:Optional[str]=None) -> bool:
    res: Optional[subprocess.CompletedProcess[bytes]] = None
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            shell=shell,
            input=stdin_data.encode() if stdin_data is not None else None,
        )
        logger.debug(f"Ran command {redact(' '.join(cmd))}")
        res.check_returncode()
    except subprocess.CalledProcessError as e:
        logger.error(f"An exception occurred while executing the command: {redact(' '.join(cmd))}")
        logger.error(f"Stderr: {redact(res.stderr.decode()) if res and res.stderr else ''}")
        logger.error(f"Exception: {redact(str(e))}")
        return False
    except OSError as e:
        # e.g. the binary does not exist -- would otherwise abort the whole run
        logger.error(f"Could not execute the command: {redact(' '.join(cmd))}")
        logger.error(f"Exception: {redact(str(e))}")
        return False
    return True


def run_cmd_output(cmd:List[str]) -> Optional[str]:
    """Run a command and return its stdout, or None if it failed."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        logger.debug(f"Ran command {redact(' '.join(cmd))}")
        res.check_returncode()
    except subprocess.CalledProcessError as e:
        logger.error(f"An exception occurred while executing the command: {redact(' '.join(cmd))}")
        logger.error(f"Stderr: {redact(res.stderr) if res.stderr else ''}")
        logger.error(f"Exception: {redact(str(e))}")
        return None
    except OSError as e:
        logger.error(f"Could not execute the command: {redact(' '.join(cmd))}")
        logger.error(f"Exception: {redact(str(e))}")
        return None
    return res.stdout

def run_cmd_with_progress(cmd:List[str], log_interval:int=30) -> bool:
    logger.info(f"Running command with progress: {redact(' '.join(cmd))}")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        last_log_time = time.time()
        last_progress_line = ""
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            last_progress_line = line
            now = time.time()
            if now - last_log_time >= log_interval:
                logger.info(f"Progress: {redact(line)}")
                last_log_time = now
        proc.wait()
        if proc.returncode != 0:
            stderr = proc.stderr.read() if proc.stderr else ""
            logger.error(f"Command failed with return code {proc.returncode}: {redact(' '.join(cmd))}")
            logger.error(f"Stderr: {redact(stderr)}")
            return False
        if last_progress_line:
            logger.info(f"Final progress: {redact(last_progress_line)}")
        logger.info(f"Command completed successfully: {redact(' '.join(cmd))}")
    except Exception as e:
        logger.error(f"An exception occurred while executing: {redact(' '.join(cmd))}")
        logger.error(f"Exception: {redact(str(e))}")
        return False
    return True


def get_newest_files(directory:str, regex:str=r".*", exclude_regex:Optional[ str ]=None)->List[str]:
    """Get newest file in directory.

    Args:
        directory (str): Directory to seerch

    Returns:
        List[str]: list of all files matching regex and not matching exlude regex
                   sorted by there age
    """
    logger.debug(f"Searching files in dir {directory}")
    files = os.listdir(directory)
    regex_pattern = re.compile(regex)
    files = [os.path.join(directory, file) for file in files if regex_pattern.search(file)]
    logger.debug(f"Found the following files {files}")
    if exclude_regex:
        exclude_regex_pattern = re.compile(exclude_regex)
        files = [os.path.join(directory, file) for file in files if not exclude_regex_pattern.search(file)]
    files.sort(key=os.path.getmtime)
    files.reverse()
    return files

def get_backup_files(directory:str, regex:str=r".*") -> List[str]:
    """Backup artefacts in directory, newest first, ordered by the time in the file name.

    The file name records when the backup was made; the mtime does not. gpg
    stamps every .gpg with the moment that particular file finished encrypting,
    in whatever order the directory happened to be walked, so an mtime ordering
    can put a year-old backup first and make the retention sweep delete the
    newest one. Files whose name does not fit the scheme are left out entirely:
    they are never counted towards a retention limit and never deleted.
    """
    files = []
    unparseable = []
    for path in get_newest_files(directory, regex):
        if backup_timestamp(path, warn=False) is None:
            unparseable.append(os.path.basename(path))
        else:
            files.append(path)
    if unparseable:
        logger.warning(f"Ignoring files with an unreadable timestamp (they are kept): {unparseable}")
    files.sort(key=lambda path: backup_timestamp(path, warn=False) or datetime.min, reverse=True)
    return files


def get_newest_file_age(directory:str, regex:str=r".*", exclude_regex:Optional[str]=None) -> float:
    """Get the creation time of the newest backup in directory as an epoch timestamp.

    Read from the file name rather than the mtime for the same reason as
    get_backup_files: the mtime of an encrypted backup is when gpg finished,
    which can be hours after the backup itself was taken.

    Args:
        directory (str): Directory to search

    Returns:
        float: Epoch timestamp of the newest backup, -1 if there is none
    """
    backups = get_backup_files(directory, regex)
    if backups:
        logger.debug(f"newest backup found in {directory} is {backups[0]}")
        stamp = backup_timestamp(backups[0])
        if stamp is not None:
            return stamp.timestamp()

    # Nothing with a readable name: fall back to the mtime so a directory full
    # of oddly named files still schedules a backup instead of one every run.
    files = get_newest_files(directory, regex, exclude_regex)
    if files:
        logger.debug(f"no readable timestamps, falling back to the mtime of {files[0]}")
        return os.path.getmtime(files[0])
    logger.debug(f"No files in {directory} found returning default value (-1)")
    return -1.0
