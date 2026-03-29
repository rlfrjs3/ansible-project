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

    cache_path = '/tmp/ansible/server-list.cache'
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

        # 대상 서버 목록 코드
        target_servers = {
            'FIRSTMALL' : [ 'PLUS', 'MULTI', 'ADDITION', 'STOCK', 'ETC'],
            'BUILDERS' : [ 'SOLUTION', 'ADDITION' ],
            'ZOOMONEY' : None,
            'DIAD' : None,
            'ESELLERS' : None,
            'IMAGEHOSTING' : None,
            'GEDITOR' : None,
            'COLOCATION' : None,
            'COMMON' : None,
            'MANAGEMENT' : None,
        }

        # Initialize an empty dictionary to store the inventory
        self.ansible_inventory = empty_inventory()

        # Add the servers to the ansible_inventory
        self.ansible_inventory['all'] = empty_inventory_children_group()

        try:
            #
            for service_code, service_groups in target_servers.items():
                if service_groups is None:
                    self.make_host_group(self.get_servers(service_code, ''))
                else:
                    for service_group in service_groups:
                        self.make_host_group(self.get_servers(service_code, service_group))

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


    def get_servers(self, service_code=None, service_group=None):
        '''
        서버관리 중 SSL 인증서 보유 서버 목록 추출
        '''
        response = []

        try:
            #
            url = 'https://gapi.firstmall.kr/service/serverlist?service_code={}&service_group={}'.format(service_code, service_group)
            res = urllib.request.urlopen(url)
            servers = json.loads(res.read().decode('utf-8'))
            if self.debug:
                print(' ... Storage Systems Payload : ')
                print(json_format_dict(servers, True))
        except urllib.error.HTTPError:
            raise
        except urllib.error.URLError:
            raise

        #
        for svr in servers:
            service_code   = str(svr.get('service_code', '')).lower()
            service_group  = str(svr.get('service_group', '')).lower()
            goods_code     = str(svr.get('goods_code', '')).lower()
            server_type    = str(svr.get('server_type', '')).lower()
            data_center    = str(svr.get('data_center', '')).lower()
            server_purpose = str(svr.get('server_purpose', '')).lower()
            server_os      = str(svr.get('server_os', '')).lower()
            server_ip      = str(svr.get('server_ip', ''))
            is_patch       = str(svr.get('is_patch', '')).lower()

            #
            if goods_code == 'colocation' or 'windows' in server_os or data_center == 'azure':
                continue
            #
            if server_purpose in ['switch', 'wireless', 'router', 'firewall', 'waf', 'ips', 'vip', 'security', 'etc']:
                continue

            #
            if service_code == 'builders':
                service_code = 'clickn'

            if service_group == 'none':
                service_group = ''
            if goods_code == 'none':
                goods_code = ''
            if data_center == 'none':
                data_center = ''

            #
            response.append({
                'service_code'   : service_code,
                'service_group'  : service_group,
                'goods_code'     : goods_code,
                'server_type'    : server_type,
                'data_center'    : data_center,
                'server_purpose' : server_purpose,
                'server_os'      : server_os,
                'server_ip'      : server_ip,
                'is_patch'       : is_patch,
            })

        #
        return response


    def make_host_group(self, servers):
        '''
        서버 목록을 ansible inventory 형식으로 변환
        '''
        for svr in servers:
            service_code   = svr['service_code']
            service_group  = svr['service_group']
            goods_code     = svr['goods_code']
            server_type    = svr['server_type']
            data_center    = svr['data_center']
            server_purpose = svr['server_purpose']
            server_os      = svr['server_os']
            server_ip      = svr['server_ip']
            is_patch       = svr['is_patch']

            if service_code not in self.ansible_inventory['all']['children']:
                self.ansible_inventory['all']['children'].append(service_code)
                self.ansible_inventory[service_code] = empty_inventory_children_group()

            inven_group = f'{service_code}'

            # 퍼스트몰
            if service_code == 'firstmall':
                inven_group = f'{inven_group}_{service_group}'

                # 솔루션
                if service_group in ['plus', 'multi']:
                    # 단독서버
                    if goods_code in ['sh_rent', 'sh_buy']:
                        if server_type == 'physical':
                            inven_group = f'{inven_group}_server'
                        else:
                            inven_group = f'{inven_group}_gcloud'
                    # 강원더몰
                    elif goods_code == 'gwmart':
                        inven_group = f'{inven_group}_{goods_code}'
                        if server_type == 'physical':
                            inven_group = f'{inven_group}_server'
                        else:
                            inven_group = f'{inven_group}_gcloud'
                    # 호스팅
                    else:
                        if service_group == 'multi':
                            if server_purpose == 'web_db':
                                server_purpose = 'web'
                            inven_group = f'{inven_group}_asp_{server_purpose}'

                    if goods_code != 'gwmart':
                        inven_group = f'{inven_group}_patch_{is_patch}'
                elif service_group in ['addition', 'etc']:
                    if server_type == 'physical':
                        inven_group = f'{inven_group}_server'
                    else:
                        inven_group = f'{inven_group}_gcloud'
                # elif service_group == 'stock':

            # 클릭엔
            elif service_code == 'clickn':
                if service_group == 'solution':
                    # 솔루션
                    inven_group = f'{inven_group}_asp_{server_purpose}'
                else:
                    # 부가서비스
                    inven_group = f'{inven_group}_{service_group}'

            # 주머니 / 다이애드 / 이셀러스 / 이미지호스팅 / 공통 / 관리
            # elif service_code in ['zoomoney', 'diad', 'esellers', 'imagehosting', 'common', 'management']:
            else:
                if server_type == 'physical':
                    inven_group = f'{inven_group}_server'
                else:
                    if service_code == 'common' and data_center == '서초idc':
                        data_center = '83cloud'
                    inven_group = f'{inven_group}_{data_center}'

            #
            if inven_group not in self.ansible_inventory[service_code]['children']:
                self.ansible_inventory[service_code]['children'].append(inven_group)

            #
            if inven_group not in self.ansible_inventory:
                self.ansible_inventory[inven_group] = empty_inventory_hosts_group()

            #
            self.ansible_inventory[inven_group]['hosts'].append(server_ip)


# Main body
if __name__ == '__main__':
    Inventory()
