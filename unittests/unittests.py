from jenkins import InventoryModule

import unittest
from unittest import TestCase
from mock import patch, MagicMock

from ansible.plugins.inventory import BaseInventoryPlugin


CACHE_TEST_KEY = 'cache_key_for_testing_purposes'
DATA_NO_CACHE = {
    u'compose': {
        u'ansible_connection': u"('indows' in launcher_plugin)|ternary('winrm', 'ssh')"
    },
    u'jenkins_user': u'user',
    u'jenkins_pass': u'user',
    u'plugin': u'jenkins',
    u'cache': False,
    u'jenkins_host': u'http://127.0.0.1:8081/',
    u'cache_plugin': u'jsonfile',
    u'strict': False,
    u'keyed_groups': [{u'prefix': u'oss', u'key': u"launcher_plugin.split('@')[0]"}],
    u'groups': {u'temporary_offline': u'(temporary_offline)'},
    u'cache_timeout': 3600, u'cache_connection':
    u'/home/user/playbooks/cache'
}


# TODO:  Decent UT?

class JenkinsInventory_Parse_Tests(TestCase):

    @patch.object(BaseInventoryPlugin, 'parse')
    @patch.object(InventoryModule, '_read_config_data')
    @patch.object(InventoryModule, '_get_all_computers')
    @patch.object(InventoryModule, '_add_composed_hostvars')
    @patch.object(InventoryModule, '_data_2_inventory')
    @patch.object(InventoryModule, 'get_data_from_jenkins')
    def test_parse_calls_nocache(self,
                                 get_data_from_jenkins_mock,
                                 _data_2_inventory_mock,
                                 _add_composed_hostvars_mock,
                                 _get_all_computers_mock,
                                 _read_config_mock,
                                 base_parse_mock):
        '''
        Tests that all necessary calls are done when executing the
            parse method. Cache is supposed to be set to False
        '''
        jenkins_inventory = InventoryModule()
        jenkins_inventory.parse(None, None, None, cache=False)

        # Assert we retrieved the data from jenkins (Cache=False)
        get_data_from_jenkins_mock.assert_called_once()
        # Assert data was transformed to inventory
        _data_2_inventory_mock.assert_called_once()
        # Assert composed data was created
        _add_composed_hostvars_mock.assert_called_once()
        # Assert the configuration file/params were loaded
        _read_config_mock.assert_called_once()
        # Assert the baseclass attributes were initialized
        base_parse_mock.assert_called_once()

    @patch.object(BaseInventoryPlugin, 'parse')
    @patch.object(InventoryModule, '_read_config_data')
    @patch.object(InventoryModule, '_get_all_computers')
    @patch.object(InventoryModule, '_add_composed_hostvars')
    @patch.object(InventoryModule, '_data_2_inventory')
    @patch.object(InventoryModule, 'get_data_from_jenkins')
    @patch.object(InventoryModule, 'get_cache_key',
                  return_value=CACHE_TEST_KEY)
    def test_parse_calls_cache_ow(self,
                                  get_cache_key_mock,
                                  get_data_from_jenkins_mock,
                                  _data_2_inventory_mock,
                                  _add_composed_hostvars_mock,
                                  _get_all_computers_mock,
                                  _read_config_mock,
                                  base_parse_mock):
        '''
        Tests that all necessary calls are done when execute the parse
            method. Cache is set to True, but is overwritten to False
            by the user.
        '''

        fake_cache = {}
        fake_cache[CACHE_TEST_KEY] = 'faked cache data'

        jenkins_inventory = InventoryModule()

        # Fake the cache option, test overwritten param by user
        jenkins_inventory._options['cache'] = False
        jenkins_inventory.cache = fake_cache

        jenkins_inventory.parse(None, None, None, cache=True)

        # Assert we retrieved the data from cache (cache=True,
        #   overwritten by _options['cache'] = False)
        get_cache_key_mock.assert_called_once()
        # Assert we retrieved the data from jenkins (Cache=True,
        #   but user overwrote to False)
        get_data_from_jenkins_mock.assert_called_once()
        # Assert data was transformed to inventory
        _data_2_inventory_mock.assert_called_once()
        # Assert composed data was created
        _add_composed_hostvars_mock.assert_called_once()
        # Assert the configuration file/params were loaded
        _read_config_mock.assert_called_once()
        # Assert the baseclass attributes were initialized
        base_parse_mock.assert_called_once()

    @patch.object(BaseInventoryPlugin, 'parse')
    @patch.object(InventoryModule, '_read_config_data')
    @patch.object(InventoryModule, '_get_all_computers')
    @patch.object(InventoryModule, '_add_composed_hostvars')
    @patch.object(InventoryModule, '_data_2_inventory')
    @patch.object(InventoryModule, 'get_data_from_jenkins')
    @patch.object(InventoryModule, 'get_cache_key',
                  return_value=CACHE_TEST_KEY)
    def test_parse_calls_cache(self,
                               get_cache_key_mock,
                               get_data_from_jenkins_mock,
                               _data_2_inventory_mock,
                               _add_composed_hostvars_mock,
                               _get_all_computers_mock,
                               _read_config_mock,
                               base_parse_mock):
        '''
        Tests that all necessary calls are done when execute the parse
            method. Cache is set to True, not overwritten.
        '''
        fake_cache = MagicMock()
        fake_cache.get = MagicMock(return_value='faked cache data')

        jenkins_inventory = InventoryModule()

        # Fake the cache option, test overwritten param by user
        jenkins_inventory._options['cache'] = True
        # Use a fake cache
        jenkins_inventory.cache = fake_cache

        jenkins_inventory.parse(None, None, None, cache=True)

        # Assert we retrieved the data from cache (cache=True)
        get_cache_key_mock.assert_called_once()
        # Assert we DO NOT retrieve the data from jenkins (Cache=True)
        get_data_from_jenkins_mock.assert_not_called()
        # Assert the data was retrieved from cache
        fake_cache.get.assert_called_once_with(CACHE_TEST_KEY)
        # Assert data was transformed to inventory
        _data_2_inventory_mock.assert_called_once()
        # Assert composed data was created
        _add_composed_hostvars_mock.assert_called_once()
        # Assert the configuration file/params were loaded
        _read_config_mock.assert_called_once()
        # Assert the baseclass attributes were initialized
        base_parse_mock.assert_called_once()


if __name__ == '__main__':
    unittest.main()
