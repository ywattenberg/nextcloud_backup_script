import os
import re

def is_in_config(config, section, key):
    """Check if a key is in the config file.

    Args:
        config (dict): Config file
        section (str): Section in config file
        key (str): Key in config file

    Returns:
        bool: True if key is in config file
    """
    if section in config:
        if key in config[section]:
            return True
    return False

def write_arguments_to_config(config, section, arguments):
    """Write arguments to config file.

    Args:
        config (dict): Config file
        section (str): Section in config file
        arguments (dict): Arguments to write to config file
    """
    if section not in config:
        config[section] = {}
    for key, value in arguments.items():
        config[section][key] = value

def get_config_value(config, section, key):
    """Get value from config file.

    Args:
        config (dict): Config file
        section (str): Section in config file
        key (str): Key in config file"""
    
    if is_in_config(config, section, key):
        return config[section][key]
    return None

def get_newest_file(directory, regex=r".*"):
    """Get newest file in directory.

    Args:
        directory (str): Directory to search

    Returns:
        str: Newest file in directory
    """
    files = os.listdir(directory)
    regex = re.compile(regex.encode('unicode_escape').decode())
    files = [os.path.join(directory, file) for file in files if regex.search(file)]
    files.sort(key=os.path.getmtime)
    return files.reverse()