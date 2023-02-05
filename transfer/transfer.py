import click
import logging
import sys
import os
import configparser
import subprocess
import datetime
import re

from utils.utils import is_in_config, write_arguments_to_config

@click.command()
@click.pass_context()
@click.argument('path', type=click.Path(), required=False)
@click.argument('target', type=click.Path(), required=False)
@click.option('--port', '-p', help='Port to use for transfer', type=click.INT)
@click.option('--user', '-u', help='User to use for transfer', type=click.STRING)
@click.option('--host', '-h', help='Host to use for transfer', type=click.STRING)
@click.option('--identity', '-i', help='Identity file to use for transfer', type=click.Path())
@click.option('--options', '-o', help='Options to use for rsync. If set no other options will be applied', multiple=True, type=click.STRING)
@click.option('--script', '-s', help='Custom script to run for transfere. This is an advanced option which is not test.', type=click.STRING)
@click.option('--new', '-n', help='Transfere all new backups that have not yet been transfererd.', is_flag=True)
@click.option('--regex', '-r', help='Regex to use for filtering files to transfer', type=click.STRING)
def transfer(ctx, path, target, port, user, host, identity, options, script, new, regex):
    #TODO: Fix names of arguments to fit with config
    #TODO: Test function
    """Transfer backups to a remote server. This command can be used to transfer backups to a remote server using rsync. The --new/-n option can be used to transfer all new backups that have not yet been transferred. If this option is set the path will be used as the path to the directory with backups.
    The default options for rsync are -r --inplace --append --progress --timeout=60. If the --options/-o option is set no other options will be applied. This includes the options for SSH which means that the port and identity options will not be used.

    path: Path to the backup file or directory to transfer.
    target: Path to the target directory on the remote server.

    If script is set the following arguments will be given to the script: path, target, port, user, host, identity, script
    """
    

    arguments = {'remote_dir': target, 'port': port, 'user': user, 'host': host, 'identity': identity, 'only_new': new, 'options': options, 'script': script}
    arguments = {key: value for key, value in arguments.items() if value is not None}
    write_arguments_to_config(ctx.obj, 'transfer', arguments)
    
    arguments = {'backup_dir': path, 'regex': regex.encode('unicode_escape').decode('utf-8')}
    arguments = {key: value for key, value in arguments.items() if value is not None}
    write_arguments_to_config(ctx.obj, 'backup', arguments)

    logging.info("Starting transfer command")
    if not is_in_config(ctx, 'transfer', 'path'):
        logging.error("No path given")
        sys.exit(1)
    else:
        if not os.path.exists(ctx.obj['transfer']['path']):
                logging.error("Path does not exist")
                sys.exit(1)
    if not is_in_config(ctx, 'transfer', 'target'):
        logging.error("No target given, but it is required")
        sys.exit(1)
    if not is_in_config(ctx, 'transfer', 'port'):
        logging.error("No port given, but it is required")
        sys.exit(1)
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
        logging.info("No regex given. All files will be transferred")
    
    if is_in_config(ctx, 'transfer', 'new'):
        logging.info("Transferring all new backups")
        if not os.path.isdir(path):
            logging.error("Path is not a directory")
            sys.exit(1)
        if not is_in_config(ctx, 'transfer', 'upload_log'):
            logging.warning("No upload log file given. Using default: upload.log, in the current directory. This means all backups will be transferred again.")
            write_arguments_to_config(ctx.obj, 'transfer', {'upload_log': os.path.abspath('upload.log')})
        regex = r'.*'
        if is_in_config(ctx, 'backup', 'regex'):
            logging.info("Using regex: {}".format(ctx.obj['backup']['regex']))
            regex = ctx.obj['backup']['regex'].encode('unicode_escape').decode('utf-8')

        uploaded_files = _get_uploaded_files(ctx)
        existing_files = []
        reg = re.compile(regex)
        for file in os.listdir(path):
            if reg.search(file):
                existing_files.append(file)
                if file not in uploaded_files:
                    _transfer_file(ctx, os.path.abspath(os.path.join(path, file)), target, port, user, host, identity, options, script)
        with open(ctx.obj['transfer']['upload_log'], 'w') as f:
            for file in existing_files:
                f.write(file+'\n')
    

def _get_uploaded_files(ctx):
    """Get a list of files that have already been uploaded. This function is used by the transfer command to get a list of files that have already been uploaded. This is used to avoid uploading the same file multiple times. The list of files is stored in a file called upload.log in the current directory. This file is created if it does not exist.
    """
    if not os.path.exists(ctx.obj['transfer']['upload_log']):
        with open(ctx.obj['transfer']['upload_log'], 'w') as f:
            f.write("")
    with open(ctx.obj['transfer']['upload_log'], 'r') as f:
        uploaded_files = f.read().splitlines()
    return uploaded_files

def _transfer_file(ctx, file, target, port, user, host, identity, script, options, identity_file):
    """Transfer a single file to a remote server using rsync. This function is used by the transfer command to transfer a single file to a remote server using rsync.
    
    file: Path to the backup file to transfer.
    target: Path to the target directory on the remote server.
    port: Port to use for transfer.
    user: User to use for transfer.
    host: Host to use for transfer.
    identity: Identity file to use for transfer.
    keyfile: Keyfile to use for transfer (SSH).
    script: Custom script to run for transfere. This is an advanced option which is not test.
    """
    logging.info("Transferring file: %s" % file)

    if script:
        if not os.path.exists(script):
            logging.error("Script file does not exist")
            sys.exit(1)
        else:
            logging.info("Running script file: %s" % script)
            args = [os.path.abspath(script), '--file', file, '--target', target, '--port', port, '--user', user, '--host', host, '--identity', identity]
            subprocess.run(args, shell=True)
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
        if identity_file:
            ssh_command += f" -i {identity_file}"
        args.extend([f"-e '{ssh_command}'"])
    args.extend([file, f'{user}@{host}:{target}'])

    logging.debug("Running rsync command: %s" % args)
    result = subprocess.run(args, capture_output=True)
    logging.info(result.stdout.decode('utf-8'))
    if result.returncode != 0:
        logging.error("rsync command failed")
        logging.error(result.stderr.decode('utf-8'))
        sys.exit(1)
    else:
        logging.debug("rsync command succeeded")
    

    
    
        
    
