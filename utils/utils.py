import os
import re
import logging

def is_in_config(ctx, section, key):
    """Check if a key is in the config file.

    Args:
        ctx (dict): ctx object from click/config
        section (str): Section in config file
        key (str): Key in config file

    Returns:
        bool: True if key is in config file
    """
    if section in ctx.obj:
        if key in ctx.obj[section]:
            return True
    return False

def write_arguments_to_config(ctx, section, arguments):
    """Write arguments to config file.

    Args:
        ctx (dict): Config file
        section (str): Section in config file
        arguments (dict): Arguments to write to config file
    """
    if section not in ctx.obj:
        ctx.obj[section] = {}
    for key, value in arguments.items():
        ctx.obj[section][key] = value

def get_config_value(ctx, section, key):
    """Get value from config file.

    Args:
        ctx (dict): Config file
        section (str): Section in config file
        key (str): Key in config file"""
    
    if is_in_config(ctx, section, key):
        return ctx.obj[section][key]
    return None

def get_newest_file(directory, regex=r".*", exclude_regex=None):
    """Get newest file in directory.

    Args:
        directory (str): Directory to search

    Returns:
        str: Newest file in directory
    """
    if not regex:
        regex = r".*"
    files = os.listdir(directory)
    regex = re.compile(regex.encode('unicode_escape').decode())
    files = [os.path.join(directory, file) for file in files if regex.search(file)]
    if exclude_regex:
        exclude_regex = re.compile(exclude_regex.encode('unicode_escape').decode())
        files = [os.path.join(directory, file) for file in files if not exclude_regex.search(file)]
    files.sort(key=os.path.getmtime)
    files.reverse()
    return files