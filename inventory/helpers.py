"""
Ansible Dynamic Inventory Helpers
"""

# Imports
import json
import os
import re
import time


def is_cache_valid(cache_path, cache_max_age):
    '''
    Determines if the cache files have expired, or if it is still valid
    '''
    if os.path.isfile(cache_path):
        mod_time = os.path.getmtime(cache_path)
        current_time = time.time()
        if (mod_time + cache_max_age) > current_time:
            return True

    return False


def load_from_cache(cache_path):
    '''
    Reads the cache from the cache file
    '''
    inventory = {}

    try:
        cache = open(cache_path, 'r')
        json_inventory = cache.read()
        inventory = json.loads(json_inventory)
        cache.close()
    except IOError as e:
        pass  # not really sure what to do here

    return inventory


def write_to_cache(cache_path, data):
    '''
    Writes data in JSON format to a file
    '''
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)

        json_data = json_format_dict(data, True)
        cache = open(cache_path, 'w')
        cache.write(json_data)
        cache.close()
    except IOError as e:
        pass  # not really sure what to do here


def empty_inventory():
    '''
    Empty Ansible Inventory
    '''
    return { '_meta': { 'hostvars': {} } }


def empty_inventory_children_group():
    '''
    Empty Ansible Inventory Group
    '''
    return { 'children': [] }


def empty_inventory_hosts_group():
    '''
    Empty Ansible Inventory Group
    '''
    return { 'hosts': [] }


def to_safe(string):
    """
    Converts 'bad' characters in a string to underscores so they can be used as Ansible groups
    """
    return re.sub(r"[^A-Za-z0-9\-]", "_", string)


def json_format_dict(data, pretty=False):
    """
    Converts a dict to a JSON object and dumps it as a formatted string
    """
    if pretty:
        return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False)
    else:
        return json.dumps(data)
