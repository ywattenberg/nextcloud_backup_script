import click
import logging
import sys
import os
import subprocess
import datetime
import re

from utils import utils

@click.command()
@click.pass_context
@click.option('--keep', '-k', help='Number of (full) backups to keep. If set to 0, all backups will be kept.')
@click.option('--path', '--dir', '-d', '-p', help='Path to the backup directory. If not set, the path from the config file will be used.')
@click.option('--dry-run', is_flag=True, help='Do not delete any files. Only show which files would be deleted.')
@click.option('--age', '-a', help='Delete all backups older than AGE days. If set keep will be ignored.')
@click.option('--regex', '-r', help='Regex to match the backup files. Files containing the regex will be deleted. Defaults to "\\.tar\\.gz\\.gpg" which will match all files containing this string not only ones that end with it.')
def purge(ctx, keep, path, dry_run, age, regex):
    """
    Delete old backups matching the set pattern in the folder path. By default, the last two backups will be kept. 
    If the --age option is set, all backups older than AGE days will be deleted and the keep option is ignored. 
    If the --dry-run option is set, no files will be deleted. Instead, the files that would be deleted will be printed to the console.
    Usage: backup_script.py [OPTIONS] purge [OPTIONS]
    """

    if not path and not utils.is_in_config(ctx.obj, 'genral', 'backup_path'):
        logging.error("Backup path not set. Please set the backup path in the config file or with the --path option.")
        sys.exit(1)
    elif not path and utils.is_in_config(ctx.obj, 'genral', 'backup_path'):
        logging.info("Using backup path from config file: %s" % ctx.obj['backup']['backup_path'])
        path = ctx.obj['backup']['backup_path']
    if not os.path.isdir(path):
        logging.error("Backup path does not exist: %s" % path)
        sys.exit(1)

    # Check if keep or age is set. If not, check if it is set in the config file. If not, use default value of 2 for keep.
    remove_method = 'keep'
    if not keep and not age:
        if utils.is_in_config(ctx.obj, 'purge', 'keep'):
            keep = ctx.obj['purge']['keep']
            logging.info("Using keep value from config file: %s" % keep)
        elif utils.is_in_config(ctx.obj, 'purge', 'age'):
            age = ctx.obj['purge']['age']
            logging.info("Using age value from config file: %s" % age)
            remove_method = 'age'
        else:
            logging.warning("No keep or age value set. Please set either the keep or age value in the config file or with the --keep or --age option. Using default value of 2 for keep.")
            keep = 2
    elif not keep and age:
        remove_method = 'age'
    elif keep and age:
        logging.warning("Both keep and age are set. Using keep value.")
    
    if keep:
        keep = int(keep)
    if age:
        age = int(age)
    
    if regex:
        logging.debug("Using regex: %s." % regex)
    elif utils.is_in_config(ctx.obj, 'purge', 'regex'):
        regex = ctx.obj['purge']['regex']
        logging.info("Using regex from config file: %s" % regex)
    else:
        logging.warning("No regex set. Using default value: '.tar.gz.gpg'")
        regex = r'\.tar\.gz\.gpg'
    backups = _find_backups(path, regex)
    if not backups:
        logging.info("No backups found in %s" % path)
        sys.exit(0)

    logging.debug("Found %s backups in %s" % (len(backups), path))
    logging.debug("Using %s as remove method." % remove_method)
    logging.debug("Found backups:")
    for backup in backups:
        logging.debug(backup)
    
    # Remove backups
    if remove_method == 'keep':
        _purge_keep(backups, keep, dry_run)
    elif remove_method == 'age':
        _purge_age(backups, age, dry_run)


def _find_backups(path, regex):
    regex = re.compile(regex)
    return [os.path.join(path, f) for f in os.listdir(path) if regex.search(f)]

def _purge_keep(backups, keep, dry_run):
    backups.sort(key=os.path.getmtime)
    for backup in backups[:-keep]:
        if dry_run:
            logging.info("Would delete %s" % backup)
        else:
            logging.info("Deleting %s" % backup)
            os.remove(backup)

def _purge_age(backups, age, dry_run):
    for backup in backups:
        backup_date = datetime.datetime.fromtimestamp(os.path.getmtime(backup))
        if (datetime.datetime.now() - backup_date).days > age:
            if dry_run:
                logging.info("Would delete %s" % backup)
            else:
                logging.info("Deleting %s" % backup)
                os.remove(backup)