import click
import logging
import sys
import os
import configparser
import subprocess
import datetime
import re
import json

from utils.utils import is_in_config, write_arguments_to_config, get_config_value

@click.command()
@click.option('--path','-p',type=click.Path())
@click.option('--remote-dir', '-t', type=click.Path())
@click.option('--port', help='Port to use for transfer', type=click.INT)
@click.option('--user', '-u', help='User to use for transfer', type=click.STRING)
@click.option('--host', '-h', help='Host to use for transfer', type=click.STRING)
@click.option('--identity', '-i', help='Identity file to use for transfer', type=click.Path())
@click.option('--options', '-o', help='Options to use for rsync. If set no other options will be applied', multiple=True, type=click.STRING)
@click.option('--script', '-s', help='Custom script to run for transfere. This is an advanced option which is not test.', type=click.STRING)
@click.option('--regex', '-r', help='Regex to use for filtering files to transfer', type=click.STRING)
@click.option('--dry-run', help='Do a dry run. This will not transfer any files.', is_flag=True)
@click.pass_context
def transfer(ctx, path, remote_dir, port, user, host, identity, options, script, regex, dry_run):
    #TODO: Fix names of arguments to fit with config
    #TODO: Test function
    """Transfer backups to a remote server. This command can be used to transfer backups to a remote server using rsync. The --new/-n option can be used to transfer all new backups that have not yet been transferred. If this option is set the path will be used as the path to the directory with backups.
    The default options for rsync are -r --inplace --append --progress --timeout=60. If the --options/-o option is set no other options will be applied. This includes the options for SSH which means that the port and identity options will not be used.

    path: Path to the backup file or directory to transfer.
    target: Path to the target directory on the remote server.

    If script is set the following arguments will be given to the script: path, target, port, user, host, identity, script
    """
    if not dry_run:
        dry_run = get_config_value(ctx, 'general', 'dry_run')
    logging.debug(f"{json.dumps(ctx.obj, indent=4, sort_keys=True)}")
    arguments = {'remote_dir': remote_dir, 'port': port, 'user': user, 'host': host, 'identity': identity, 'options': options, 'script': script, 'dry_run': dry_run, 'path': path}
    arguments = {key: value for key, value in arguments.items() if value is not None}
    
    write_arguments_to_config(ctx, 'transfer', arguments)
    logging.debug(f"{json.dumps(ctx.obj, indent=4, sort_keys=True)}")
    arguments = {}
    if regex:
        arguments['regex'] = regex.encode('unicode_escape').decode('utf-8')
        write_arguments_to_config(ctx, 'backup', arguments)

    logging.info("Starting transfer command")
    if not is_in_config(ctx, 'transfer', 'path'):
        logging.error("No path given")
        sys.exit(1)
    else:
        if not os.path.exists(ctx.obj['transfer']['path']):
                logging.error("Path does not exist")
                sys.exit(1)
    if not is_in_config(ctx, 'transfer', 'remote_dir'):
        logging.error("No target given, but it is required")
        sys.exit(1)
    if not is_in_config(ctx, 'transfer', 'port'):
        logging.warning("No port given, using default: 22")
        write_arguments_to_config(ctx, 'transfer', {'port': 22})
    if not is_in_config(ctx, 'transfer', 'user'):
        logging.error("No user given, but it is required")
        sys.exit(1)
    if not is_in_config(ctx, 'transfer', 'host'):
        logging.error("No host given, but it is required")
        sys.exit(1)
    if not is_in_config(ctx, 'transfer', 'identity'):
        logging.info("No identity given")
    if not is_in_config(ctx, 'transfer', 'options'):
        logging.info("No options given")
    if not is_in_config(ctx, 'transfer', 'regex'):
        logging.info("No regex given.")
    logging.debug(f"Using path: {ctx.obj['transfer']['path']}")
    if os.path.isdir(get_config_value(ctx, 'transfer', 'path')):
        logging.info("Given path is a directory. Transferring all files in directory.")
        if not is_in_config(ctx, 'transfer', 'upload_log'):
            logging.warning(f"No upload log file given. Using default: upload.log, in {get_config_value(ctx, 'transfer', 'path')}.")
            backup_log = os.path.join(get_config_value(ctx, 'transfer', 'path'), 'upload.log')
            write_arguments_to_config(ctx, 'transfer', {'upload_log': backup_log})
        regex = r".+\.tar\.gz(\.gpg|)"
        if not is_in_config(ctx, 'transfer', 'regex'):
            write_arguments_to_config(ctx, 'transfer', {'regex': '.*'})
            if is_in_config(ctx, 'backup', 'regex'):
                logging.debug(f"Using regex: {ctx.obj['backup']['regex']} from backup section")
                regex = ctx.obj['backup']['regex']
            else:

                logging.debug(f"Using default regex: {regex}")
        else:
            logging.debug(f"Using regex: {ctx.obj['backup']['regex']}")
            regex = get_config_value(ctx, 'backup', 'regex') 

        uploaded_files = _get_uploaded_files(ctx)
        existing_files = []
        reg = re.compile(regex)
        for file in os.listdir(path):
            logging.debug(f"Checking file: {file}")
            if reg.search(file) and file is not get_config_value(ctx, 'transfer', 'upload_log'):
                logging.debug(f"Found file: {file}")
                existing_files.append(file)
                if file not in uploaded_files:
                    _transfer_file(ctx, os.path.abspath(os.path.join(path, file)))
                else:
                    logging.debug(f"File {file} has already been uploaded. Skipping.")
        with open(ctx.obj['transfer']['upload_log'], 'w') as f:
            for file in existing_files:
                f.write(file+'\n')
    else:
        logging.info("Transferring single file")
        _transfer_file(ctx, path)
    

def _get_uploaded_files(ctx):
    """Get a list of files that have already been uploaded. This function is used by the transfer command to get a list of files that have already been uploaded. This is used to avoid uploading the same file multiple times. The list of files is stored in a file called upload.log in the current directory. This file is created if it does not exist.
    """
    if not os.path.exists(ctx.obj['transfer']['upload_log']):
        with open(ctx.obj['transfer']['upload_log'], 'w') as f:
            f.write("")
    with open(ctx.obj['transfer']['upload_log'], 'r') as f:
        uploaded_files = f.read().splitlines()
    return uploaded_files

def _transfer_file(ctx, file):
    """Transfer a single file to a remote server using rsync. This function is used by the transfer command to transfer a single file to a remote server using rsync.
    
    file: Path to the backup file to transfer.
    target: Path to the target directory on the remote server.
    port: Port to use for transfer.
    user: User to use for transfer.
    host: Host to use for transfer.
    identity: Identity file to use for transfer.
    script: Custom script to run for transfere. This is an advanced option which is not test.
    """
    logging.info("Transferring file: %s" % file)
    script = get_config_value(ctx, 'transfer', 'script')
    target = get_config_value(ctx, 'transfer', 'remote_dir')
    port = get_config_value(ctx, 'transfer', 'port')
    user = get_config_value(ctx, 'transfer', 'user')
    host = get_config_value(ctx, 'transfer', 'host')
    identity = get_config_value(ctx, 'transfer', 'identity')
    options = get_config_value(ctx, 'transfer', 'options')

    if script:
        if not os.path.exists(script):
            logging.error("Script file does not exist")
            sys.exit(1)
        else:
            logging.info("Running script file: %s" % script)
            args = [os.path.abspath(script), '--file', file, '--target', target, '--port', port, '--user', user, '--host', host, '--identity', identity]
            result = subprocess.run(args, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode != 0:
                logging.error("Script failed with error code: %s" % result.returncode)
                logging.error("Script error output: %s" % result.stderr.decode('utf-8'))
                sys.exit(1)
            else:
                logging.info("Script finished successfully")
            return
    args = ['rsync']
    if options:
        logging.info("Using custom options for rsync: %s" % options)
        args.extend(options)
    else:
        logging.debug("Using default options for rsync: -r --inplace --append --timeout=60")
        args.extend(['-r', '--inplace', '--append', '--timeout=60'])
        ssh_command = "ssh"
        if port:
            ssh_command += f" -p {port}"
        if identity:
            ssh_command += f" -i {identity}"
        args.extend([f'-e \"{ssh_command}\"'])
    args.extend([file, f'{user}@{host}:{target}'])

    logging.debug("Running rsync command: %s" % subprocess.list2cmdline(args))
    if not get_config_value(ctx, 'transfer', 'dry_run'):
        result = subprocess.run(args, capture_output=True)
        logging.info(result.stdout.decode('utf-8'))
        if result.returncode != 0:
            logging.error("rsync command failed")
            logging.error(result.stderr.decode('utf-8'))
            sys.exit(1)
        else:
            logging.debug("rsync command succeeded")
    

    
    
        
    
