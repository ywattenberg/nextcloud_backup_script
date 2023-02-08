#!/usr/bin/env python3

import click
import logging
import sys
import os
import json
import subprocess
import datetime

from utils import utils
import create
import purge
import transfer

@click.group(invoke_without_command=True, chain=True)
@click.option('--config','-c', help='Config file', type=click.Path())
@click.option('--log', '-l', default='backup.log', help='Log file', type=click.Path())
@click.option('--verbose','-v', is_flag=True, help='Print log to console as well')
@click.option('--task', '-t', help='runs the given file as a task', type=click.Path())
@click.option('--debug', '-d', is_flag=True, help='Debug mode')
@click.option('--version', is_flag=True, help='Show version')
@click.option('--dry-run', is_flag=True, help='Dry run')
@click.pass_context
def cli(ctx, config, log, verbose, task, debug, version, dry_run):
    """Backup script for Nextcloud and other applications. For creating, compressing, encrypting, transferring and uploading backups to aws s3. This script is still in development and not ready for production use. Use at your own risk."""
    if version:
        click.echo("Version 0.1")
        sys.exit(0)

    if debug:
        click.echo("Debug mode is on")
        logging.basicConfig(filename=log, level=logging.DEBUG, format='%(asctime)s:%(levelname)s:%(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    else:
        logging.basicConfig(filename=log, level=logging.INFO, format='%(asctime)s:%(levelname)s:%(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    if verbose:
        click.echo("Verbose mode is on")
        logging.getLogger().addHandler(logging.StreamHandler())
    
    if not config:
        config = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'config.toml')
        logging.info(f"Using default config file:{config}")
        if not os.path.exists(config):
            logging.warning("Config file does not exist")
            config = None
    if config:
        if not os.path.exists(config):
            logging.error("Config file does not exist")
            sys.exit(1)
        with open(config, 'r') as f:
            parser = json.load(f)
        ctx.ensure_object(dict)
        ctx.obj = parser
        logging.debug(f"Loaded config file: {config}")
        logging.debug(json.dumps(ctx.obj, indent=4, sort_keys=True))

    if task:
        if not os.path.exists(task):
            logging.error("Task file does not exist")
            sys.exit(1)
        else:
            logging.info(f"Running task file: {task}")
                # TODO: Run task file
            sys.exit(0)

    if dry_run:
        utils.write_arguments_to_config(ctx, 'general', {'dry_run': True})
    
    # if not ctx.invoked_subcommand:
    #     logging.error("No subcommand given")
    #     sys.exit(1)


cli.add_command(create.nextcloud)
cli.add_command(purge.purge)
cli.add_command(transfer.transfer)
cli.add_command(transfer.upload)
# @main.command()
# @click.option('--source', default='.', help='Source directory')
# @click.option('--destination', default='.', help='Destination directory')
# @click.option('--exclude', default='.', help='Exclude directory')
# @click.option('--encrypt', is_flag=True, help='Encrypt backup. This option requires a password to be set in the config file.') 
# @click.option('--compress', help='Tar options for compression. More specific options and commands can be set in the config file.')
# @click.pass_context
# def backup(ctx, source, destination, exclude, encrypt, compress):
#     pass


# @main.command()
# @click.pass_context
# def transfer(ctx):
#     pass

# @main.command()
# @click.pass_context
# def upload(ctx):
#     pass


if __name__ == '__main__':
    cli(obj={})