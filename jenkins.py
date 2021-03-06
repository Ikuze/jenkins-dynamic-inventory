from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = '''
    name: jenkins
    plugin_type: inventory
    short_description: jenkins inventory source
    description:
        - Get inventory hosts from jenkins instance
        - Uses a .jenkins.yaml (or .jenkins.yml) YAML configuration file.
    extends_documentation_fragment:
        - constructed
        - inventory_cache
    options:
        jenkins_user:
            description: jenkins user
            type: string
        jenkins_pass:
            description: jenkins password
            type: string
        jenkins_host:
            description: jenkins host
            type: string
        jenkins_jsessionid:
            description: force login to use jsessionid and improve performance
            type: boolean
        timeout:
            description: timeout for each request
            type: int
'''

EXAMPLES = '''
# file must be named *.jenkins.yaml or *.jenkins.yml
simple_config_file:
    plugin: jenkins
    compose:
        ansible_connection: ('indows' in launcher_plugin)|ternary('winrm', 'ssh')
        ansible_port: ('indows' in launcher_plugin)|ternary('5986', 'ssh')
    jenkins_user: user
    jenkins_pass: password
    jenkins_jsessionid: True
    jenkins_host: http://127.0.0.1:8080/
    timeout: 30
'''

import sys

from ansible.errors import AnsibleError
from ansible.plugins.inventory import BaseInventoryPlugin, Constructable, Cacheable
from ansible.module_utils.urls import open_url
from ansible.module_utils.six.moves.urllib.parse import urlencode
from ansible.module_utils.six.moves.urllib.request import Request, HTTPRedirectHandler, build_opener

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()

from lxml import objectify
import getpass

try:
    import json
except ImportError:
    import simplejson as json


class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):
    ''' Host inventory parser for ansible using jenkins instance. '''

    NAME = 'jenkins'

    def _do_login(self):
        display.vvv('Do login. Using jsessionid cookie.')
        login_url = 'j_acegi_security_check'
        jenkins_url = '{0}/{1}'.format(self._get_jenkins_host(), login_url)
        data = urlencode({'j_username': self._get_jenkins_user(), 'j_password': self._get_jenkins_pass()}).encode("utf-8")

        class SmartRedirectHandler(HTTPRedirectHandler):

            def extract_cookie(self, setcookie):
                # Extracts the last cookie.
                # Example of set-cookie value for python2
                # ('set-cookie', 'JSESSIONID.30blah=blahblahblah;Path=/;HttpOnly, JSESSIONID.30ablah=blahblah;Path=/;HttpOnly'),
                return setcookie.split(',')[-1].split(';')[0].strip('\n\r ')

            def http_error_302(self, req, fp, code, msg, headers):
                # Jenkins can send several Set-Cookie values sometimes
                #  The valid one is the last one
                for header, value in headers.items():
                    if header.lower() == 'set-cookie':
                        cookie = self.extract_cookie(value)

                req.headers['Cookie'] = cookie
                result = HTTPRedirectHandler.http_error_302(self, req, fp,
                                                            code, msg,
                                                            headers)
                result.orig_status = code
                result.orig_headers = headers
                result.cookie = cookie
                return result

        request = Request(jenkins_url, data)
        opener = build_opener(SmartRedirectHandler())
        res = opener.open(request)
        self._save_cookie(res.cookie)

    def _save_cookie(self, cookie):
        self.cookie = cookie

    def parse(self, inventory, loader, path, cache=True):

        super(InventoryModule, self).parse(inventory, loader, path)

        # Load the configuration data from jenkins inventory file.
        self._read_config_data(path)

        # false when refresh_cache or --flush-cache is used
        if cache:
            # get the user-specified directive
            cache = self._options.get('cache')
            cache_key = self.get_cache_key(path)
        else:
            cache_key = None

        # Generate inventory
        cache_needs_update = False
        if cache:
            try:
                data = self.cache.get(cache_key)
            except KeyError:
                # if cache expires or cache file doesn't exist
                cache_needs_update = True

        display.vvv('Cache {0}. Needs update {1}. Cache key {2}'.format(cache,
                                                                        cache_needs_update,
                                                                        cache_key))

        if not cache or cache_needs_update:
            data = self.get_data_from_jenkins()

        self._data_2_inventory(data)
        self._add_composed_hostvars()

        if cache_needs_update:
            self.cache.set(cache_key, data)

    def _add_composed_hostvars(self):
        strict = self._options.get('strict', False)

        for hostname in self.inventory.hosts:
            host = self.inventory.get_host(hostname)
            hostvars = host.vars
            # Composed variables
            if self._options.get('compose'):
                # create composite vars
                self._set_composite_vars(self.get_option('compose'), hostvars, hostname, strict=strict)

            # Complex groups based on jinaj2 conditionals, hosts that meet the conditional are added to group
            if self._options.get('groups'):
                # constructed groups based on conditionals
                self._add_host_to_composed_groups(self.get_option('groups'), hostvars, hostname, strict=strict)

            # Create groups based on variable values and add the corresponding hosts to it
            if self._options.get('keyed_groups'):
                self._add_host_to_keyed_groups(self.get_option('keyed_groups'), hostvars, hostname, strict=strict)

    def get_data_from_jenkins(self):
        if self._must_login():
            self._do_login()
        else:
            # If we dont need to login, we ignore the cookie
            self.cookie = None

        data = self._init_empty_inventory()

        all_computers = self._get_all_computers()
        for computer in all_computers:
            if computer['_class'] == 'hudson.model.Hudson$MasterComputer':
                # Skip master node
                continue
            self.add_computer_2_data(computer, data)

        return data

    def add_computer_2_data(self, computer, data):
        computer_name = computer['displayName']
        computer_info = self._get_computer_info(computer_name)

        labels = [l.strip() for l in str(computer_info.label).strip().split(' ') if len(l) > 0]

        if len(labels) == 0:
            groups = ['ungrouped']
        else:
            groups = labels

        for group in groups:
            group_value = data.get(group, self._get_empty_group())
            group_value['hosts'].append(computer_name)
            data[group] = group_value
            if group == "":
                raise AnsibleError('Empty group not allowed. Computer: <{0}>'.format(computer_name))

            if group not in data['all']['children']:
                data['all']['children'].append(group)

        host_vars = {}

        host_vars['launcher_plugin'] = str(computer_info.launcher.attrib['plugin'])

        host_vars['inventory_hostname'] = computer_name
        # Host could not be present in a "launched by command" computer
        if hasattr(computer_info.launcher, "host"):
            host_vars['ansible_host'] = str(computer_info.launcher.host)
        # Port could not be defined if it's a windows computer
        if hasattr(computer_info.launcher, "port"):
            host_vars['ansible_port'] = str(computer_info.launcher.port)

        host_vars['temporary_offline'] = hasattr(computer_info, 'temporaryOfflineCause')

        host_vars['idle'] = computer['idle']
        host_vars['offline'] = computer['offline']
        host_vars['num_executors'] = computer['numExecutors']

        host_vars.update(self.get_node_properties(computer_info))

        data['_meta']['hostvars'][computer_name] = host_vars

    def get_node_properties(self, computer_xml_info):
        # We don't want anyone to override those properties, it could lead to serious problems if it happens
        forbidden_properties = ['launcher_plugin',
                                'inventory_hostname',
                                'ansible_host',
                                'ansible_port',
                                'temporary_offline']

        num_prop_path = './/nodeProperties/hudson.slaves.EnvironmentVariablesNodeProperty/envVars/tree-map/int'
        all_props_path = './/nodeProperties/hudson.slaves.EnvironmentVariablesNodeProperty/envVars/tree-map/string'

        num_properties = computer_xml_info.find(num_prop_path)
        all_props = computer_xml_info.find(all_props_path)

        node_properties = {}
        if num_properties is not None:
            for index in range(0, int(num_properties)):
                prop_name = str(all_props[index * 2])
                prop_value = str(all_props[(index * 2) + 1])

                if prop_name is not None \
                   and prop_value is not None \
                   and prop_name not in forbidden_properties:
                    node_properties[prop_name] = prop_value

        return node_properties

    def add_computer(self, computer):
        computer_info = self._get_computer_info(computer)

        labels = [l.strip() for l in str(computer_info.label).strip().split(' ') if len(l) > 0]

        if len(labels) == 0:
            groups = ['ungrouped']
        else:
            groups = labels

        host = str(computer_info.launcher.host)
        port = str(computer_info.launcher.port)

        for group in groups:
            self.inventory.add_group(group)
            self.inventory.add_host(computer)
            self.inventory.add_child(group, computer)
            self.inventory.set_variable(computer, 'ansible_host', host)
            self.inventory.set_variable(computer, 'ansible_port', port)

    def _get_computer_info(self, computer):
        computer_url = 'computer/{0}/config.xml'.format(computer)
        jenkins_host = self._get_jenkins_host()
        config_url = '{0}/{1}'.format(jenkins_host, computer_url)

        r = open_url(config_url, use_proxy=False,
                     validate_certs=False,
                     method='GET',
                     timeout=self._options.get('timeout', None),
                     force_basic_auth=(not self._must_login()),
                     url_username=self._get_jenkins_user(),
                     url_password=self._get_jenkins_pass(),
                     force=False,
                     headers=self._get_headers())

        xml_config = r.read()
        computer = objectify.fromstring(xml_config)

        return computer

    def _get_headers(self):
        if self.cookie is not None:
            headers = {'Cookie': self.cookie}
        else:
            headers = {}

        return headers

    def _get_all_computers(self):
        computers_api_url = 'computer/api/json'
        jenkins_host = self._get_jenkins_host()
        api_url = '{0}/{1}'.format(jenkins_host, computers_api_url)

        r = open_url(api_url, use_proxy=False,
                     validate_certs=False,
                     headers=self._get_headers(),
                     timeout=self._options.get('timeout', None),
                     force_basic_auth=(not self._must_login()),
                     url_username=self._get_jenkins_user(),
                     url_password=self._get_jenkins_pass(),
                     force=True,
                     method='GET')

        computers_json = json.loads(r.read().decode('utf-8'))

        all_computers = computers_json['computer']

        return all_computers

    def _get_jenkins_user(self):
        return self._options.get('jenkins_user', None)

    def _get_jenkins_pass(self):
        jenkins_pass = self._options.get('jenkins_pass', None)

        if jenkins_pass is None and self._get_jenkins_user() is not None:
            jenkins_pass = getpass.getpass()
            # For python 2 and 3 compatibility
            try:
                u_jenkins_pass = jenkins_pass.decode(sys.stdin.encoding).encode('UTF-8')
            except (TypeError, AttributeError):
                u_jenkins_pass = jenkins_pass.encode('UTF-8')
            # Save the pass not to ask it once and again and again
            jenkins_pass = u_jenkins_pass.decode('UTF-8')
            self._options['jenkins_pass'] = jenkins_pass

        return jenkins_pass

    def _get_jenkins_host(self):
        return self._options.get('jenkins_host', None)

    def _must_login(self):
        return (self._options.get('jenkins_jsessionid', False) and
                self._get_jenkins_user() is not None)

    def verify_file(self, path):
        valid = False

        if super(InventoryModule, self).verify_file(path):
            if path.endswith(('.jenkins.yaml', '.jenkins.yml')):
                valid = True

        return valid

    def _data_2_inventory(self, data):
        hostvars = data.get('_meta', {}).get('hostvars', {})

        for group in data:
            if group == 'all':
                continue
            else:
                self.inventory.add_group(group)
                hosts = data[group].get('hosts', [])
                for host in hosts:
                    self._populate_host_vars([host], hostvars.get(host, {}), group)

                self.inventory.add_child('all', group)

    def _get_empty_group(self):
        return {
            'children': [],
            'hosts': [],
            'vars': {}
        }

    def _init_empty_inventory(self):
        return {
            '_meta': {
                'hostvars': {}
            },
            'all': {
                'children': ['ungrouped'],
                'hosts': [],
                'vars': {}
            }
        }
