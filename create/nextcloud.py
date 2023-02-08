import click
import logging
import sys
import subprocess
import yaml
import os

from utils.utils import *
from .create import move_backup, encrypt_backup, compress_backup, rename_backup

@click.command()
@click.option('--docker', '-d', is_flag=True, help='Nextcloud is running in docker.')
@click.option('--container-name','-c', help='Name of the docker container. Only required if --docker is set')
@click.option('--docker-compose-path','--path','-p', help='Path to the docker-compose command. Only required if --docker is set')
@click.option('--docker-compose-file', '-f', help='Path to the docker-compose file. Only required if --docker is set')
@click.option('--differential', is_flag=True, help='Create a differential backup')
@click.option('--appdata', '-a', help='Path to the appdata directory. Required if --docker is not set. If --docker-compose-path is set the script will try to find the appdata directory automatically if none is set.')
@click.option('--dry-run', is_flag=True, help='Do not create a backup. Only show what would be done.')
@click.pass_context
def nextcloud(ctx, docker, container_name, docker_compose_path, docker_compose_file, differential, appdata, dry_run):
    """
    IMPORTANT: At the moment this program uses the nextcloud extension "backup" to do the actual backup. This extension is not part of the official nextcloud distribution. It can be installed from the nextcloud app store. This program will not work without this extension.
    Crate a backup of a nextcloud instace. This command will create a backup of the Nextcloud data directory and the database. The backup can subsequently be encrypted and compressed transfererd and/or uploaded. The backup will be created in the directory set in the config file. The backup will be named with the current date and time. The backup will be created in the following format: YYYY-MM-DD_HH-MM-SS.tar.gz.gpg. 

    Usage: backup_script.py [OPTIONS] nextcloud [OPTIONS]
    """
    dry_run = dry_run or get_config_value(ctx, 'general', 'dry_run')
    options = {'docker': docker, 'container_name': container_name, 'docker_compose_path': docker_compose_path, 'docker_compose_file': docker_compose_file, 'differential': differential, 'appdata': appdata}
    options = {k: v for k, v in options.items() if v is not None}
    write_arguments_to_config(ctx, 'nextcloud', options)

    options = {'dry_run': dry_run}
    write_arguments_to_config(ctx, 'create', options)
  
    if not appdata and not get_config_value(ctx, 'nextcloud', 'appdata') and not docker:
        logging.error("Appdata directory not set. Use the --appdata option to set the appdata directory or set the appdata directory in the config file.")
        sys.exit(1)

    differential_option=""
    if get_config_value(ctx, 'nextcloud', 'differential'):
        logging.info("Creating differential backup")
        differential_option = " --differential"
    
    if docker:
        logging.info("Nextcloud is running in docker")
        if not is_in_config(ctx, 'nextcloud', 'container_name'):
            logging.warning("Container name not set but --docker is set. A container name can be set in the config file or with the --container-name option. Using default container name from the official Nextcloud docker compose: app")
            write_arguments_to_config(ctx, 'nextcloud', {'container_name': 'app'})
        if not is_in_config(ctx, 'nextcloud', 'docker_compose_path'):
            logging.warning("Docker compose path not set but --docker is set. A docker compose path can be set in the config file or with the --docker-compose-path option. Using default docker compose path: docker-compose")
            write_arguments_to_config(ctx, 'nextcloud', {'docker_compose_path': 'docker-compose'})
        if not is_in_config(ctx, 'nextcloud', 'docker_compose_file'):
            logging.warning("Docker compose file not set but --docker is set. A docker compose file can be set in the config file or with the --docker-compose-file option. Using default docker compose file: docker-compose.yml. This assumes the docker compose file is in the current directory.")
            write_arguments_to_config(ctx, 'nextcloud', {'docker_compose_file': 'docker-compose.yml'})
        if not is_in_config(ctx, 'nextcloud', 'appdata'):
            logging.info("Appdata directory not set but --docker is set. Trying to find the appdata directory automatically")
            appdata = _extact_appdata_dir(get_config_value(ctx, 'nextcloud', 'docker_compose_file'), get_config_value(ctx, 'nextcloud', 'container_name'))
            if not appdata:
                logging.error("Could not find the appdata directory automatically. Please set the appdata directory in the config file or with the --appdata option.")
                sys.exit(1)
            else:
                write_arguments_to_config(ctx, 'nextcloud', {'appdata': appdata})
        docker_compose_file = get_config_value(ctx, 'nextcloud', 'docker_compose_file')
        docker_compose_path = get_config_value(ctx, 'nextcloud', 'docker_compose_path')
        container_name = get_config_value(ctx, 'nextcloud', 'container_name')
        logging.debug("Docker compose file: %s" % docker_compose_file)
        logging.debug("Docker compose path: %s" % docker_compose_path)
        logging.debug("Container name: %s" % container_name)

        cmd = f'{docker_compose_path} -f {docker_compose_file} exec -T -u  www-data {container_name} php occ backup:point:create {differential_option}'
    else:
        logging.warning("It is recommended to run Nextcloud in docker. If you are not running Nextcloud in docker, make sure to set the correct path to the Nextcloud directory in the config file.")
        logging.warning("This option is not tested. If you encounter any problems, please open an issue on GitHub.")
        occ_path = get_config_value(ctx, 'nextcloud', 'occ_path')
        logging.debug("Nextcloud occ path: %s" % occ_path)
        if not occ_path:
            logging.error("Nextcloud occ path not set. Please set the occ path in the config file.")
            sys.exit(1)
        cmd = f'{occ_path} occ backup:point:create {differential_option}'
    logging.debug(f"The final command is: {cmd}")
    if get_config_value(ctx, 'create', 'dry_run'):
        logging.info("Dry run. Not executing the command.")
    else:
        result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            logging.error("Error while creating backup point. Make sure the Nextcloud backup app is installed. Please check the error message below and open an issue on GitHub if the problem persists.")
            logging.error(result.stderr.decode("utf-8"))
            sys.exit(1)
        else:
            logging.info(result.stdout.decode("utf-8"))

    if not get_config_value(ctx, 'nextcloud', 'appdata'):
        logging.error("Appdata directory not set. Please set the appdata directory in the config file. The backup was created but all subsequent tasks can not be executed.")
        sys.exit(1)
    else:
        logging.debug("Appdata directory: %s" % get_config_value(ctx, 'nextcloud', 'appdata'))
        rename_backup(ctx, get_config_value(ctx, 'nextcloud', 'appdata')+'/backup')
        move_backup(ctx, get_config_value(ctx, 'nextcloud', 'appdata')+'/backup')
        if get_config_value(ctx, 'create', 'compress'):
            compress_backup(ctx, get_config_value(ctx, 'backup', 'backup_dir'))
        if get_config_value(ctx, 'create', 'encrypt'):
            encrypt_backup(ctx, get_config_value(ctx, 'backup', 'backup_dir'))

def _extact_appdata_dir(docker_compose_file, container_name):
    logging.debug(f"_extact_appdata_dir called with docker_compose_file: {docker_compose_file} and container_name: {container_name}" )
    with open(docker_compose_file, 'r') as f:
        docker_compose = yaml.load(f, Loader=yaml.FullLoader)
    for service in docker_compose['services']:
        if service == container_name:
            volumes = docker_compose['services'][service]['volumes']
            for volume in volumes:
                if volume.split(':')[1] == '/var/www/html':
                    appdata = volume.split(':')[0]
    if 'volumes' in docker_compose:
        appdata = docker_compose['volumes'][appdata]

    if not appdata:
        logging.error("Could not find appdata volume. Please open an issue on GitHub.")
        sys.exit(1)
    else:
        logging.debug("Found volume: %s" % appdata)
        for dir in os.listdir(os.path.abspath(os.path.join(appdata, 'data'))):
            if dir.split('_')[0] == 'appdata':
                logging.debug("Found appdata directory: %s" % os.path.join(appdata, dir))
                return os.path.abspath(os.path.join(appdata, 'data', dir))

