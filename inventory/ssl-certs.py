#!/usr/bin/env python3
"""
Ansible Dynamic Inventory Script
"""

# Imports
import argparse
import ipaddress
import json
import traceback
import urllib.error
import urllib.request
import sys

# Local Imports
from helpers import is_cache_valid, load_from_cache, write_to_cache, json_format_dict
from helpers import empty_inventory, empty_inventory_children_group, empty_inventory_hosts_group, to_safe

__metaclass__ = type

class Inventory(object):

    cache_path = '/tmp/ansible/ssl-certs.cache'
    cache_max_age = 60 * 30
    ansible_inventory = {}

    def __init__(self):
        # Argument parsing
        # The --list option must enlist all the groups and associated hosts and group variables
        # The --host option must either return an empty dictionary or a dictionary of variables relevant to that host
        parser = argparse.ArgumentParser(description='Ansible dynamic inventory')
        parser.add_argument('--list', action='store_true', default=True, help='List instances (default: True)')
        parser.add_argument('--host', action='store', help='Get all the variables about a specific instance')
        parser.add_argument('--debug', action='store_true', default=False)

        cli_args = parser.parse_args()

        self.debug = cli_args.debug

        if self.debug:
            print('--list: {}'.format(cli_args.list))
            print('--host: {}'.format(cli_args.host))

        # Called with `--list`.
        if cli_args.list:
            if is_cache_valid(self.cache_path, self.cache_max_age):
                self.ansible_inventory = load_from_cache(self.cache_path)
            else:
                self.generate_inventory()
                write_to_cache(self.cache_path, self.ansible_inventory)
        # Called with `--host`.
        else:
            self.ansible_inventory = empty_inventory()

        # Print the inventory
        print(json_format_dict(self.ansible_inventory, True))


    def generate_inventory(self):
        '''
        Generate Ansible Inventory
        '''

        # Initialize an empty dictionary to store the inventory
        self.ansible_inventory = empty_inventory()

        try:
            # Get the list of servers
            servers = self.get_servers()
            if not servers:
                return

            # Add the servers to the ansible_inventory
            self.ansible_inventory['all'] = empty_inventory_children_group()

            for cert, hosts in servers.items():
                cert_group = to_safe(cert)

                #
                if cert_group not in self.ansible_inventory['all']['children']:
                    self.ansible_inventory['all']['children'].append(cert_group)
                    self.ansible_inventory[cert_group] = empty_inventory_children_group()

                for svr in hosts:
                    service_code  = svr['service']
                    service_group = svr['group']
                    svr_ip        = svr['ip']
                    ws_type       = svr['ws_type']

                    inven_group = f'{cert_group}_{service_code}'
                    if service_group:
                        inven_group = f'{inven_group}_{service_group}'

                    #
                    if svr_ip not in self.ansible_inventory['_meta']['hostvars']:
                        self.ansible_inventory['_meta']['hostvars'][svr_ip] = { 'web_server' : ws_type }

                    #
                    if inven_group not in self.ansible_inventory[cert_group]['children']:
                        self.ansible_inventory[cert_group]['children'].append(inven_group)

                    #
                    if inven_group not in self.ansible_inventory:
                        self.ansible_inventory[inven_group] = empty_inventory_hosts_group()

                    #
                    self.ansible_inventory[inven_group]['hosts'].append(svr_ip)

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


    def get_servers(self):
        '''
        서버관리 중 SSL 인증서 보유 서버 목록 추출
        '''
        response = {}

        try:
            #
            res = urllib.request.urlopen('https://gapi.firstmall.kr/service/ssl_certificate_servers')
            servers = json.loads(res.read().decode('utf-8'))
            if self.debug:
                print(' ... Storage Systems Payload : ')
                print(json_format_dict(servers, True))
        except urllib.error.HTTPError:
            raise
        except urllib.error.URLError:
            raise

        #
        for cert, hosts in servers.items():
            response[cert] = []

            for svr in hosts:
                service_code  = str(svr.get('service_code', '')).lower()
                service_group = str(svr.get('service_group', '')).lower()
                server_name   = svr.get('server_name', '')
                server_ip     = svr.get('server_ip', '')
                software      = svr.get('software') if svr.get('software', None) is not None else ''
                web_info      = svr.get('web_info', {})

                if service_group == 'none':
                    service_group = ''

                if isinstance(web_info, list):
                    web_info = dict(web_info)

                ws_type = web_info['ws_type'] if web_info.get('ws_type', None) is not None else ''

                if not ws_type:
                    software = software.lower()
                    if 'ha-proxy' in software or 'haproxy' in software:
                        ws_type = 'ha-proxy'
                    elif 'podman' in software or 'docker' in software:
                        ws_type = 'container'

                response[cert].append({
                    'name'   : server_name,
                    'ip'     : server_ip,
                    'service': service_code,
                    'group'  : service_group,
                    'ws_type': ws_type.lower(),
                })

        return response


# Main body
if __name__ == '__main__':
    Inventory()
