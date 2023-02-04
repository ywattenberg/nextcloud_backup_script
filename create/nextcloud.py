import click
import logging
import sys
import os
import configparser
import subprocess
import datetime

from utils.utils import is_in_config

@click.command()
@click.option('--docker', '-d', is_flag=True, help='Nextcloud is running in docker')
@click.option('--container-name','-c', help='Name of the docker container. Only required if --docker is set')
@click.option('--docker-compose-path','--path','-p', help='Path to the docker-compose command. Only required if --docker is set')
@click.option('--docker-compose-file', '-f', help='Path to the docker-compose file. Only required if --docker is set')
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
        if not container_name and not is_in_config(ctx.obj, 'nextcloud', 'container_name'):
            logging.warning("Container name not set but --docker is set. A container name can be set in the config file or with the --container-name option. Using default container name from the official Nextcloud docker compose: app")
            container_name = "app"
        elif is_in_config(ctx.obj, 'nextcloud', 'container_name'):
            logging.info("Using container name from config file: %s" % ctx.obj['nextcloud']['container_name'])
            container_name = ctx.obj['nextcloud']['container_name']
        logging.debug("Container name: %s" % container_name)
        if not docker_compose_path and not is_in_config(ctx.obj, 'docker-compose_path', 'container_name'):
            logging.warning("Docker compose path not set but --docker is set. A docker compose path can be set in the config file or with the --docker-compose-path option. Using default docker compose path: docker-compose")
            docker_compose_path = "docker-compose"
        elif is_in_config(ctx.obj, 'docker-compose_path', 'container_name'):
            logging.info("Using docker compose path from config file: %s" % ctx.obj['nextcloud']['docker-compose_path'])
            docker_compose_path = ctx.obj['nextcloud']['docker-compose_path']
        logging.debug("Docker compose path: %s" % docker_compose_path)
        if not docker_compose_file and not is_in_config(ctx.obj, 'docker-compose_file', 'container_name'):
            logging.warning("Docker compose file not set but --docker is set. A docker compose file can be set in the config file or with the --docker-compose-file option. Using default docker compose file: docker-compose.yml. This assumes the docker compose file is in the current directory.")
            docker_compose_file = "docker-compose.yml"
        elif docker_compose_file:
            logging.debug("Using docker compose file from command line: %s" % docker_compose_file)
        elif is_in_config(ctx.obj, 'docker-compose_file', 'container_name'):
            logging.debug("Using docker compose file from config file: %s" % ctx.obj['nextcloud']['docker-compose_file'])
            docker_compose_file = ctx.obj['nextcloud']['docker-compose_file']
        logging.debug("Docker compose file: %s" % docker_compose_file)
        cmd = f'{docker_compose_path} -f {docker_compose_file} exec -T -u  www-data {container_name} php occ backup:point:create {differential_option}'
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
