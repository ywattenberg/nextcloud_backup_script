import os
import sys
import logging
import subprocess
import datetime

from utils.utils import *

def rename_backup(ctx, backup):
    dry_run = get_config_value(ctx.obj, 'create', 'dry_run')
    if os.path.isdir(backup):
        logging.debug("Backup is a directory. Getting newest file.")
        backup = get_newest_file(backup, get_config_value(ctx.obj, 'backup', 'regex'))[0]
    logging.debug(f"Backup: {backup}")
    backup_name = get_config_value(ctx.obj, 'backup', 'backup_name')
    if not backup_name:
        logging.warning("Backup name not set. Using default name.")
        backup_name = r'%date%'
    backup_name = backup_name.replace(r'%date%', datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S'))
    
    backup_name = backup.split('/')[:-2] + backup_name
    backup_name = os.path.join(*backup_name)
    logging.debug(f"Backup name: {backup_name}")
    logging.debug(f"Backup: {backup}")
    if not dry_run:
        os.rename(backup, backup_name)
    return backup_name

def move_backup(ctx, backup):
    dry_run = get_config_value(ctx.obj, 'create', 'dry_run')
    backup_dir = get_config_value(ctx.obj, 'backup', 'backup_dir')
    if not backup_dir or not os.path.exists(backup_dir):
        logging.error("Backup directory does not exist")
        sys.exit(1)
    if os.path.isdir(backup):
        logging.debug("Backup is a directory. Getting newest file.")
        backup = get_newest_file(backup, get_config_value(ctx.obj, 'backup', 'regex'))[0]
    logging.debug(f"Backup directory: {backup_dir}, renaming backup: {backup} ")
    if not dry_run:
        os.rename(backup, backup_dir + '/' + backup)

def encrypt_backup(ctx, backup):
    dry_run = get_config_value(ctx.obj, 'create', 'dry_run')
    if os.path.isdir(backup):
        logging.debug("Backup is a directory. Getting newest file.")
        backup = get_newest_file(backup, get_config_value(ctx.obj, 'backup', 'regex'))[0]
    encrypted_name = backup + '.gpg'
    encrypt_cmd = ['gpg', '--batch', '--yes', '--cipher-algo', 'AES256', '--passphrase', '-o', encrypted_name, get_config_value(ctx.obj, 'backup', 'password'), '-c', backup]
    if get_config_value(ctx.obj, 'create', 'encryption_command'):
        encrypt_cmd = get_config_value(ctx.obj, 'create', 'encryption_command')
        encrypt_cmd = encrypt_cmd.replace('%s', backup)
        encrypt_cmd = encrypt_cmd.replace('%d', encrypted_name)
        encrypt_cmd = encrypt_cmd.replace('%p', get_config_value(ctx.obj, 'backup', 'password'))
        encrypt_cmd = encrypt_cmd.split(' ')

    logging.info("Encrypting %s" % backup)
    logging.debug("Running command: %s" % encrypt_cmd)
    if dry_run:
        return
    else:
        res = subprocess.run(encrypt_cmd, capture_output=True)
        if res.returncode != 0:
            logging.error("Error encrypting %s" % backup)
            logging.error(res.stderr.decode('utf-8'))
            sys.exit(1)
        else:
            logging.debug("Encrypted %s" % backup)
            logging.debug(res.stdout.decode('utf-8'))
            logging.debug(res.stderr.decode('utf-8'))
            os.remove(backup)

def compress_backup(ctx, backup):
    dry_run = get_config_value(ctx, 'create', 'dry_run')
    if os.path.isdir(backup):
        logging.debug("Backup is a directory. Getting newest file.")
        backup = get_newest_file(backup, get_config_value(ctx, 'backup', 'regex'))[0]
    compressed_name = backup + '.tar.gz'
    compress_cmd = ['tar', backup, compressed_name]
    if get_config_value(ctx, 'create', 'compression_command'):
        compress_cmd = get_config_value(ctx, 'create', 'compression_command')
        compress_cmd = compress_cmd.replace('%s', backup)
        compress_cmd = compress_cmd.replace('%d', compressed_name)
        compress_cmd = compress_cmd.split(' ')

    logging.info("Compressing %s" % backup)
    logging.debug("Running command: %s" % compress_cmd)
    if dry_run:
        return
    else:
        res = subprocess.run(compress_cmd, capture_output=True)
        if res.returncode != 0:
            logging.error("Error compressing %s" % backup)
            logging.error(res.stderr.decode('utf-8'))
            sys.exit(1)
        else:
            logging.debug("Compressed %s" % backup)
            logging.debug(res.stdout.decode('utf-8'))
            logging.debug(res.stderr.decode('utf-8'))
            os.remove(backup)

        

