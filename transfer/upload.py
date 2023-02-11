import boto3
import os
import sys
import logging
from botocore.exceptions import ClientError
import click
import threading
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
@click.option('--key', '-k', help='Key to use for upload')
@click.pass_context
def upload(ctx, path, bucket, regex, upload_log, threads, key):
    """Upload files to S3"""
    arguments = {'path': path, 'bucket': bucket, 'regex': regex, 'upload_log': upload_log, 'threads': threads,  'key': key}
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
        logging.info("No key given, letting boto3 search for it")
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
    key = get_config_value(ctx, 'transfer', 'key')

    config = TransferConfig(multipart_threshold=1024 * 25, max_concurrency=threads, multipart_chunksize=1024*25, use_threads=True)

    if os.path.isdir(path):
        files = get_newest_files(path, regex)
        uploaded_files = _get_uploaded_files(upload_log)
        files = [file for file in files if file not in uploaded_files]
        for f in files:
            upload_file(os.path.join(path, f), bucket, config=config)
    else:
        upload_file(path, bucket, config=config)

class ProgressPercentage(object):

    def __init__(self, filename):
        self._filename = filename
        self._size = float(os.path.getsize(filename))
        self._seen_so_far = 0
        self._lock = threading.Lock()

    def __call__(self, bytes_amount):
        # To simplify, assume this is hooked up to a single filename
        with self._lock:
            self._seen_so_far += bytes_amount
            percentage = (self._seen_so_far / self._size) * 100
            sys.stdout.write(
                "\r%s  %s / %s  (%.2f%%)" % (
                    self._filename, self._seen_so_far, self._size,
                    percentage))
            sys.stdout.flush()


def upload_file(file_name, bucket, object_name=None, config=None):
    """Upload a file to an S3 bucket

    :param file_name: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """

    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = os.path.basename(file_name)

    # Upload the file
    s3_client = boto3.client('s3')
    try:
        response = s3_client.upload_file(file_name, bucket, object_name,
        config=config,
        Callback=ProgressPercentage(file_name))
    except ClientError as e:
        logging.error(e)
        return False
    return True

