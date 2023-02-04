import click
import logging
import sys
import os
import configparser
import subprocess

@click.group(invoke_without_command=True, chain=True)
@click.option('--config', default='config.ini', help='Config file', type=click.File())
@click.option('--log', default='backup.log', help='Log file', type=click.Path())
@click.option('--verbose', is_flag=True, help='Print log to console as well')
@click.option('--task', help='runs the given file as a task', type=click.File())
@click.option('--debug', is_flag=True, help='Debug mode')
@click.option('--version', is_flag=True, help='Show version')
@click.pass_context
def main(ctx, config, log, verbose, task, debug, version):
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
    
    # if not ctx.invoked_subcommand:
    #     logging.error("No subcommand given")
    #     sys.exit(1)



# @main.command()
# @click.option('--source', default='.', help='Source directory')
# @click.option('--destination', default='.', help='Destination directory')
# @click.option('--exclude', default='.', help='Exclude directory')
# @click.option('--encrypt', is_flag=True, help='Encrypt backup. This option requires a password to be set in the config file.') 
# @click.option('--compress', help='Tar options for compression. More specific options and commands can be set in the config file.')
# @click.pass_context
# def backup(ctx, source, destination, exclude, encrypt, compress):
#     pass

@main.command()
@click.option('--docker', is_flag=True, help='Nextcloud is running in docker')
@click.option('--container-name', help='Name of the docker container. Only required if --docker is set')
@click.option('--docker-compose-path', help='Path to the docker-compose command. Only required if --docker is set')
@click.option('--docker-compose-file', help='Path to the docker-compose file. Only required if --docker is set')
@click.option('--differential', is_flag=True, help='Create a differential backup')
@click.pass_context
def nextcloud(ctx, docker, container_name, docker_compose_path, docker_compose_file, differential):
    """
    IMPORTANT: At the moment this program uses the nextcloud extension "backup" to do the actual backup. This extension is not part of the official nextcloud distribution. It can be installed from the nextcloud app store. This program will not work without this extension.
    Crate a backup of a nextcloud instace. This command will create a backup of the Nextcloud data directory and the database. The backup can subsequently be encrypted and compressed transfererd and/or uploaded. The backup will be created in the directory set in the config file. The backup will be named with the current date and time. The backup will be created in the following format: YYYY-MM-DD_HH-MM-SS.tar.gz.gpg. 

    Usage: backup_script.py [OPTIONS] nextcloud [OPTIONS]
    """
    differential_option=""
    if differential:
        logging.info("Creating differential backup")
        differential_option = " --differential"
    
    if docker:
        logging.info("Nextcloud is running in docker")
        if not container_name and not ctx.obj['nextcloud']['container_name']:
            logging.warning("Container name not set but --docker is set. A container name can be set in the config file or with the --container-name option. Using default container name from the official Nextcloud docker compose: app")
            container_name = "app"
        elif ctx.obj['nextcloud']['container_name']:
            logging.info("Using container name from config file: %s" % ctx.obj['nextcloud']['container_name'])
            container_name = ctx.obj['nextcloud']['container_name']
        logging.debug("Container name: %s" % container_name)
        if not docker_compose_path and not ctx.obj['nextcloud']['docker-compose_path']:
            logging.warning("Docker compose path not set but --docker is set. A docker compose path can be set in the config file or with the --docker-compose-path option. Using default docker compose path: docker-compose")
            docker_compose_path = "docker-compose"
        elif ctx.obj['nextcloud']['docker-compose_path']:
            logging.info("Using docker compose path from config file: %s" % ctx.obj['nextcloud']['docker-compose_path'])
            docker_compose_path = ctx.obj['nextcloud']['docker-compose_path']
        logging.debug("Docker compose path: %s" % docker_compose_path)
        if not docker_compose_file and not ctx.obj['nextcloud']['docker-compose_file']:
            logging.warning("Docker compose file not set but --docker is set. A docker compose file can be set in the config file or with the --docker-compose-file option. Using default docker compose file: docker-compose.yml")
            docker_compose_file = "docker-compose.yml"
        elif ctx.obj['nextcloud']['docker-compose_file']:
            logging.info("Using docker compose file from config file: %s" % ctx.obj['nextcloud']['docker-compose_file'])
            docker_compose_file = ctx.obj['nextcloud']['docker-compose_file']
        logging.debug("Docker compose file: %s" % docker_compose_file)
        cmd = f'{ctx.obj["nextcloud"]["docker-compose_path"]} -f {ctx.obj["nextcloud"]["docker-compose_file"]} exec -T -u  www-data {container_name} php occ backup:point:create {differential_option}'
    else:
        logging.warning("It is recommended to run Nextcloud in docker. If you are not running Nextcloud in docker, make sure to set the correct path to the Nextcloud directory in the config file.")
        logging.warning("This option is not tested. If you encounter any problems, please open an issue on GitHub.")
        cmd = f'{ctx.obj["nextcloud"]["nextcloud_path"]} occ backup:point:create {differential_option}'
    logging.debug(f"The final command is: {cmd}")
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        logging.error("Error while creating backup point. Make sure the Nextcloud backup app is installed. Please check the error message below and open an issue on GitHub if the problem persists.")
        logging.error(result.stderr.decode("utf-8"))
        sys.exit(1)
    else:
        logging.info(result.stdout.decode("utf-8"))

# @main.command()
# @click.pass_context
# def transfer(ctx):
#     pass

# @main.command()
# @click.pass_context
# def upload(ctx):
#     pass

# @main.command()
# @click.pass_context
# def purge(ctx):
#     pass




if __name__ == "main":
    main(obj={})