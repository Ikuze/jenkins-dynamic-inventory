import unittest
from unittest import TestCase
from mock import patch, MagicMock

from ansible.plugins.loader import inventory_loader
from ansible.parsing.dataloader import DataLoader
from ansible.inventory.manager import InventoryManager

import os
import yaml


HEADERS_DATA = {'Set-Cookie': 'fake-cookie'}


class JenkinsInventory_Unit_NoCache_Tests(TestCase):
    '''
    Tests to verify that the plugin's behavior is fine.
    Cache will not be enabled.
    '''

    INVENTORY_FILE = 'jenkins_inventory_data'
    COMPUTERS_JSON = 'computers_json'
    NODES_XML = 'nodes_xml'

    def set_test_info(self, test_filename):
        with open(test_filename, 'r') as yamlconfig:
            self.test_config = yaml.load(yamlconfig)

        self.test_base_dir = os.path.dirname(os.path.abspath(test_filename))

    def get_return_login_mock(self):
        opener = MagicMock()
        opener.open = MagicMock()
        res = MagicMock()
        res.orig_headers = HEADERS_DATA
        opener.open.return_value = res

        return opener

    def get_return_query_mock(self):
        returned_data = []
        computers_json_filename = os.path.join(self.test_base_dir, self.test_config[self.COMPUTERS_JSON])
        with open(computers_json_filename, 'r') as computers_file:
            data = computers_file.read()
            returned_data.append(data)

        for node_xml in self.test_config[self.NODES_XML]:
            node_xml_filename = os.path.join(self.test_base_dir, node_xml)
            with open(node_xml_filename, 'r') as node_xml_file:
                data = node_xml_file.read()
                returned_data.append(data)

        open_url_returned = MagicMock()
        open_url_returned.read = MagicMock()
        open_url_returned.read.side_effect = returned_data

        return open_url_returned

    def get_inventory_file(self):
        return os.path.join(self.test_base_dir, self.test_config[self.INVENTORY_FILE])

    def do_assertions(self, jenkins_inventory):
        # print (jenkins_inventory.inventory.get_host('node1').vars)
        expected_groups = self.test_config['expect']['groups'].keys()
        actual_groups = jenkins_inventory._inventory.groups.keys()

        # remove the _meta group, previously used for cache
        actual_groups.remove('_meta')

        self.assertItemsEqual(actual_groups,
                              expected_groups)

        for group_name, nodes in self.test_config['expect']['groups'].iteritems():
            one_group = jenkins_inventory._inventory.groups[group_name]
            group_nodes = [x.name for x in one_group.get_hosts()]
            self.assertItemsEqual(group_nodes, nodes)


def make_test_function(description, test_filename):
    # Plugin classes are loaded 'on the fly'
    # ansible.plugins.inventory.jenkins doesn't actually exist if
    # we don't copy the plugin to the plugin directory.
    # We dont want to copy the plugin there, or at least, we don't want that
    # to be mandatory. So we mock 'on the fly' as well.
    # That's the reason we wrapped build_opener and open_url functions in the plugin
    # If anyone has a better idea, dont hesitate to contact me. It would be greatly
    # appreciated.
    @patch.object(inventory_loader.get('jenkins').__class__, 'build_opener')
    @patch.object(inventory_loader.get('jenkins').__class__, 'open_url')
    def test_exec(self, open_url_query_mock, build_opener_login_mock):
        self.set_test_info(test_filename)
        inventory_loader.get('jenkins').__module__
        loader = DataLoader()

        inventory_file = self.get_inventory_file()

        open_url_query_mock.return_value = self.get_return_query_mock()
        build_opener_login_mock.return_value = self.get_return_login_mock()

        # We delegate the inventory plugin handling to the inventory manager
        manager = InventoryManager(loader, inventory_file)

        self.do_assertions(manager)

    return test_exec


if __name__ == '__main__':

    current_directory = os.path.dirname(os.path.realpath(__file__))
    tests_directory = os.path.join('datasets', 'tests')
    tests_directory = os.path.join(current_directory, tests_directory)

    for test in os.listdir(tests_directory):
        test_file = os.path.join(os.path.join(tests_directory,
                                              test),
                                 'test.yml')

        if os.path.exists(test_file):
            print('Test Added: {0}'.format(test))
            print('      File: {0}'.format(test_file))
            test_func = make_test_function(test, test_file)
            setattr(JenkinsInventory_Unit_NoCache_Tests, 'test_{0}'.format(test), test_func)

    suite = unittest.TestSuite()

    test_loader = unittest.TestLoader()
    all_tests = test_loader.getTestCaseNames(JenkinsInventory_Unit_NoCache_Tests)

    for test in all_tests:
        suite.addTest(JenkinsInventory_Unit_NoCache_Tests(test))
    unittest.TextTestRunner(verbosity=2).run(suite)
