import click
import logging
import sys
import os
import configparser
import subprocess
import datetime

from utils import utils
import create
import purge

@click.group(invoke_without_command=True, chain=True)
@click.option('--config','-c', help='Config file', type=click.File())
@click.option('--log', '-l', default='backup.log', help='Log file', type=click.Path())
@click.option('--verbose','-v', is_flag=True, help='Print log to console as well')
@click.option('--task', '-t', help='runs the given file as a task', type=click.File())
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
        logging.basicConfig(filename=log, level=logging.DEBUG)
    else:
        logging.basicConfig(filename=log, level=logging.INFO)

    if verbose:
        click.echo("Verbose mode is on")
        logging.getLogger().addHandler(logging.StreamHandler())

    if config:
        click.echo("Config file: %s" % config)
        if not os.path.exists(config):
            click.echo("Config file does not exist")
            logging.error("Config file does not exist")
            sys.exit(1)
        config = configparser.ConfigParser()
        config.read(config)
        ctx.ensure_object(dict)
        for section in config.sections():
            if section not in ctx.obj:
                ctx.obj[section] = {}
            for key, value in config.items(section):
                logging.debug("Config: %s %s %s" % (section, key, value))
                ctx.obj[section][key] = value

    if task:
        if not os.path.exists(task):
            logging.error("Task file does not exist")
            sys.exit(1)
        else:
            logging.info("Running task file: %s" % task)
                # TODO: Run task file

    if dry_run:
        utils.write_arguments_to_config(ctx.obj, 'general', {'dry_run': True})
    
    # if not ctx.invoked_subcommand:
    #     logging.error("No subcommand given")
    #     sys.exit(1)


cli.add_command(create.nextcloud)
cli.add_command(purge.purge)
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