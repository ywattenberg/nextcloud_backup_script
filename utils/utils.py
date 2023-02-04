

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