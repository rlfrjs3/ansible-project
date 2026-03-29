#!/usr/bin/env python3
"""
Ansible Dynamic Inventory Script
CLOUD_USER=gcu_163531 ansible-inventory -i ./event-cloud.py --list
"""

# Imports
import argparse
import ipaddress
import json
import os
import traceback
import urllib.error
import urllib.request
import urllib.parse
import sys
from cryptography.fernet import Fernet

# Local Imports
from helpers import is_cache_valid, load_from_cache, write_to_cache, json_format_dict
from helpers import empty_inventory, empty_inventory_children_group, empty_inventory_hosts_group, to_safe

__metaclass__ = type

class Inventory(object):

    ansible_inventory = {}

    ENCRYPTION_KEY = b'0IM-M3YVtjMxz5lxgwSFMEZWWRmtq55GvMwTmbUIa7o='


    def __init__(self):
        # Argument parsing
        # The --list option must enlist all the groups and associated hosts and group variables
        # The --host option must either return an empty dictionary or a dictionary of variables relevant to that host
        parser = argparse.ArgumentParser(description='Ansible dynamic inventory')
        parser.add_argument('--list', action='store_true', default=True, help='List instances (default: True)')
        parser.add_argument('--host', action='store', help='Get all the variables about a specific instance')
        # parser.add_argument('--cloud_user', action='store', help='Event Cloud User id')
        parser.add_argument('--debug', action='store_true', default=False)

        cli_args = parser.parse_args()

        cloud_user = os.environ.get('CLOUD_USER')
        self.debug = cli_args.debug

        if self.debug:
            print('--list: {}'.format(cli_args.list))
            print('--host: {}'.format(cli_args.host))
            print('--cloud_user: {}'.format(cloud_user))

        # Called with `--list`.
        if cli_args.list:
            self.generate_inventory(cloud_user)
        # Called with `--host`.
        else:
            self.ansible_inventory = empty_inventory()

        # Print the inventory
        print(json_format_dict(self.ansible_inventory, True))


    def generate_inventory(self, cloud_user):
        '''
        Generate Ansible Inventory
        '''
        # Initialize an empty dictionary to store the inventory
        self.ansible_inventory = empty_inventory()

        try:
            # Get the list of servers
            servers = self.get_servers(cloud_user)
            if not servers:
                return

            # Add the servers to the ansible_inventory
            self.ansible_inventory['all'] = empty_inventory_children_group()

            for svr_type, hosts in servers.items():
                svr_group = to_safe(svr_type)

                #
                if svr_group not in self.ansible_inventory['all']['children']:
                    self.ansible_inventory['all']['children'].append(svr_group)
                    self.ansible_inventory[svr_group] = empty_inventory_hosts_group()

                for svr in hosts:
                    svr_name = svr['name']
                    svr_ip   = svr['ip']

                    #
                    if svr_ip not in self.ansible_inventory['_meta']['hostvars']:
                        self.ansible_inventory['_meta']['hostvars'][svr_ip] = { 'hostname' : svr_name }

                    #
                    self.ansible_inventory[svr_group]['hosts'].append(svr_ip)

            # sort ip address
            for key, data in self.ansible_inventory.items():
                if 'hosts' in data:
                    group_hosts = data['hosts']
                    data['hosts'] = sorted(group_hosts, key = ipaddress.IPv4Address)
        except Exception as ex:
            if self.debug:
                traceback.print_exc()
            else:
                print('Unexpected %d: %s' % (ex.args[0], ex.args[1]))
            sys.exit(1)


    def get_servers(self, cloud_user):
        '''
        클라우드 VM 목록
        '''
        response = {}

        try:
            encrypted_user = self.encrypt_data(cloud_user)
            if self.debug:
                print('--encrypted_user: {}'.format(encrypted_user))

            encrypted_user = urllib.parse.quote(encrypted_user)

            #
            res = urllib.request.urlopen('https://gapi.firstmall.kr/service/event_cloud_servers?cloud_user={}'.format(encrypted_user))
            servers = json.loads(res.read().decode('utf-8'))
            if self.debug:
                print(' ... Storage Systems Payload : ')
                print(json_format_dict(servers, True))
            if not servers:
                return response
        except urllib.error.HTTPError:
            raise
        except urllib.error.URLError:
            raise
        #
        for svr_type, hosts in servers.items():
            response[svr_type] = []

            for svr in hosts:
                svr_name   = str(svr.get('svr_name', '')).lower()
                public_ip  = svr.get('public_ip', '')
                # private_ip = svr.get('private_ip', '')

                response[svr_type].append({
                    'name'   : svr_name,
                    'ip'     : public_ip,
                })

        return response


    def encrypt_data(self, data):
        """Encrypts data using Fernet and returns a URL-safe token."""
        if data is None:
            return None
        f = Fernet(self.ENCRYPTION_KEY)
        encrypted_token = f.encrypt(data.encode('utf-8'))
        return encrypted_token.decode('utf-8')

# Main body
if __name__ == '__main__':
    Inventory()
