import boto3
import os
import sys
import logging
import click
import re
from boto3.s3.transfer import TransferConfig

from utils.utils import get_config_value, is_in_config, write_arguments_to_config, get_newest_files
from .transfer import _get_uploaded_files
from .s3_multipart_upload import multi_part_upload

@click.command()
@click.option('--path', '-p', help='Path to file or directory to upload')
@click.option('--bucket', '-b', help='Bucket to upload to')
@click.option('--regex', '-r', help='Regex to filter files')
@click.option('--upload-log', '-l', help='File to store list of uploaded files')
@click.option('--threads', '-t', help='Number of threads to use for upload')
@click.option('--region', help='Region to use for upload')
@click.option('--profile', help='Profile to use for upload')
@click.option('--key', '-k', help='Key to use for upload')
@click.pass_context
def upload(ctx, path, bucket, regex, upload_log, threads, chunk_size, region, profile, key):
    """Upload files to S3"""
    arguments = {'path': path, 'bucket': bucket, 'regex': regex, 'upload_log': upload_log, 'threads': threads, 'region': region, 'profile': profile, 'key': key}
    write_arguments_to_config(ctx, 'transfer', arguments)
    if not is_in_config(ctx, 'transfer', 'path'):
        logging.warning("No path given. Using default: backup_dir from backup section")
        if is_in_config(ctx, 'backup', 'backup_dir'):
            logging.debug(f"Using path: {ctx.obj['backup']['backup_dir']} from backup section")
            write_arguments_to_config(ctx, 'transfer', {'path': ctx.obj['backup']['backup_dir']})
        else:
            logging.error("No path given and no default in backup section")
            sys.exit(1)
    if not is_in_config(ctx, 'transfer', 'bucket'):
        logging.error("No bucket given")
        sys.exit(1)
    if not is_in_config(ctx, 'transfer', 'key'):
        logging.error("No key given")
        sys.exit(1)
    if not is_in_config(ctx, 'transfer', 'prefix'):
        logging.info("No prefix given")
    if not is_in_config(ctx, 'transfer', 'regex'):
        logging.warning("No regex given, using default from backup section")
        if is_in_config(ctx, 'backup', 'regex'):
            logging.debug(f"Using regex: {ctx.obj['backup']['regex']} from backup section")
            write_arguments_to_config(ctx, 'transfer', {'regex': ctx.obj['backup']['regex']})
        else:
            logging.debug("Using default regex: .*")
            write_arguments_to_config(ctx, 'transfer', {'regex': '.*'})
    if not is_in_config(ctx, 'transfer', 'upload_log'):
        logging.info("No upload log given, using default: upload_log from transfer section")
        write_arguments_to_config(ctx, 'transfer', {'upload_log': 'upload.log'})
    
    path = get_config_value(ctx, 'transfer', 'path')
    bucket = get_config_value(ctx, 'transfer', 'bucket')
    regex = get_config_value(ctx, 'transfer', 'regex')
    upload_log = get_config_value(ctx, 'transfer', 'upload_log')
    threads = get_config_value(ctx, 'transfer', 'threads')
    region = get_config_value(ctx, 'transfer', 'region')
    profile = get_config_value(ctx, 'transfer', 'profile')
    key = get_config_value(ctx, 'transfer', 'key')

    if os.path.isdir(path):
        files = get_newest_files(path, regex)
        uploaded_files = _get_uploaded_files(upload_log)
        files = [file for file in files if file not in uploaded_files]
        for f in files:
            multi_part_upload(bucket, key, os.path.join(path, f), profile, region)
    else:
        multi_part_upload(bucket, key, path, profile, region)


