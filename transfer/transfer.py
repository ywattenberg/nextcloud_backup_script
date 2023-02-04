import click
import logging
import sys
import os
import configparser
import subprocess
import datetime

from utils.utils import is_in_config

@click.command()
@click.pass_context()
@click.argument('path', type=click.Path(), required=False)
@click.argument('target', type=click.Path(), required=False)
@click.option('--port', '-p', help='Port to use for transfer', type=click.INT)
@click.option('--user', '-u', help='User to use for transfer', type=click.STRING)
@click.option('--host', '-h', help='Host to use for transfer', type=click.STRING)
@click.option('--identity', '-i', help='Identity file to use for transfer', type=click.Path())
@click.option('--keyfile', '-k', help='Keyfile to use for transfer (SSH)', type=click.STRING)
@click.option('--script', '-s', help='Custom script to run for transfere. This is an advanced option which is not test.', type=click.STRING)
@click.option('--new', '-n', help='Transfere all new backups that have not yet been transfererd.', is_flag=True)
def transfer(ctx, path, target, port, user, host, identity, password, command, new):
    """Transfer backups to a remote server. This command can be used to transfer backups to a remote server using rsync. The --new/-n option can be used to transfer all new backups that have not yet been transfered. If this option is set the path will be used as the path to the directory with backups.
    
    path: Path to the backup file or directory to transfer.
    target: Path to the target directory on the remote server.
    """

    pass