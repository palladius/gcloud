#!/usr/bin/python
#
# Copyright 2012 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for the network commands."""



import path_initializer
path_initializer.InitializeSysPath()

import copy

import gflags as flags
import unittest

from gcutil import command_base
from gcutil import mock_api
from gcutil import network_cmds

FLAGS = flags.FLAGS


class NetworkCmdsTest(unittest.TestCase):

  def _doTestAddNetworkGeneratesCorrectRequest(self, service_version):
    flag_values = copy.deepcopy(FLAGS)

    command = network_cmds.AddNetwork('addnetwork', flag_values)

    expected_project = 'test_project'
    expected_network = 'test-network'
    expected_range = '192.168.0.0/16'
    expected_gateway = '192.168.0.1'
    expected_description = 'test network'
    flag_values.project = expected_project
    flag_values.description = expected_description
    flag_values.range = expected_range
    flag_values.gateway = expected_gateway
    flag_values.service_version = service_version

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())

    result = command.Handle(expected_network)

    self.assertEqual(result['project'], expected_project)

    response_body = result['body']
    self.assertEqual(response_body['name'], expected_network)
    self.assertEqual(response_body['description'], expected_description)

    self.assertEqual(response_body['IPv4Range'], expected_range)
    self.assertEqual(response_body['gatewayIPv4'], expected_gateway)

  def testAddNetworkGeneratesCorrectRequest(self):
    for version in command_base.SUPPORTED_VERSIONS:
      self._doTestAddNetworkGeneratesCorrectRequest(version)

  def testGetNetworkGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)

    command = network_cmds.GetNetwork('getnetwork', flag_values)

    expected_project = 'test_project'
    expected_network = 'test_network'
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())

    result = command.Handle(expected_network)

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['network'], expected_network)

  def testDeleteNetworkGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)

    command = network_cmds.DeleteNetwork('deletenetwork', flag_values)

    expected_project = 'test_project'
    expected_network = 'test_network'
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    results, exceptions = command.Handle(expected_network)
    self.assertEqual(exceptions, [])
    self.assertEqual(len(results['items']), 1)
    result = results['items'][0]

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['network'], expected_network)

  def testDeleteMultipleNetworks(self):
    flag_values = copy.deepcopy(FLAGS)
    command = network_cmds.DeleteNetwork('deletenetwork', flag_values)

    expected_project = 'test_project'
    expected_networks = ['test-network-%02d' % x for x in xrange(100)]
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    results, exceptions = command.Handle(*expected_networks)
    self.assertEqual(exceptions, [])
    results = results['items']
    self.assertEqual(len(results), len(expected_networks))

    for expected_network, result in zip(expected_networks, results):
      self.assertEqual(result['project'], expected_project)
      self.assertEqual(result['network'], expected_network)


if __name__ == '__main__':
  unittest.main()
