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

"""Unit tests for the firewall commands."""



import path_initializer
path_initializer.InitializeSysPath()

import copy

import gflags as flags
import unittest

from gcutil import command_base
from gcutil import firewall_cmds
from gcutil import mock_api

FLAGS = flags.FLAGS


class FirewallRulesTest(unittest.TestCase):
  def testParsePortSpecs(self):
    parse_port_specs = firewall_cmds.FirewallRules.ParsePortSpecs
    self.assertRaises(ValueError, parse_port_specs, [''])
    self.assertRaises(ValueError, parse_port_specs, ['foo'])
    self.assertRaises(ValueError, parse_port_specs, ['foo:'])
    self.assertRaises(ValueError, parse_port_specs, ['tcp:foo-bar'])
    self.assertRaises(ValueError, parse_port_specs, ['tcp:http:https'])

    self.assertEqual(parse_port_specs([]), [])
    self.assertEqual(parse_port_specs(['tcp']),
                     [{'IPProtocol': '6'}])
    self.assertEqual(parse_port_specs(['6']),
                     [{'IPProtocol': '6'}])
    self.assertEqual(parse_port_specs(['tcp:80', 'tcp', 'tcp:ssh']),
                     [{'IPProtocol': '6'}])
    self.assertEqual(parse_port_specs(['tcp:ssh']),
                     [{'IPProtocol': '6',
                       'ports': ['22']}])
    self.assertEqual(parse_port_specs([':ssh']),
                     [{'IPProtocol': '17',
                       'ports': ['22']},
                      {'IPProtocol': '6',
                       'ports': ['22']}])
    self.assertEqual(parse_port_specs([':ssh']),
                     parse_port_specs(['udp:ssh', 'tcp:ssh']))
    self.assertEqual(parse_port_specs([':ssh', 'tcp:80']),
                     [{'IPProtocol': '17',
                       'ports': ['22']},
                      {'IPProtocol': '6',
                       'ports': ['22', '80']}])


class FirewallCmdsTest(unittest.TestCase):

  def _doAddFirewallGeneratesCorrectRequest(self, service_version,
                                            allowed_ip_source):
    flag_values = copy.deepcopy(FLAGS)

    command = firewall_cmds.AddFirewall('addfirewall', flag_values)

    expected_project = 'test_project'
    expected_firewall = 'test_firewall'
    submitted_network = 'test_network'
    expected_description = 'test firewall'
    flag_values.service_version = service_version
    flag_values.project = expected_project
    flag_values.description = expected_description
    flag_values.network = submitted_network
    flag_values.allowed = [':22']
    if allowed_ip_source:
      flag_values.allowed_ip_sources.append(allowed_ip_source)

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())

    expected_network = command.NormalizeGlobalResourceName(expected_project,
                                                           'networks',
                                                           submitted_network)

    result = command.Handle(expected_firewall)

    self.assertEqual(result['project'], expected_project)

    response_body = result['body']
    self.assertEqual(response_body['name'], expected_firewall)
    self.assertEqual(response_body['network'], expected_network)
    self.assertEqual(response_body['description'], expected_description)

    self.assertEqual(response_body['sourceRanges'],
                     [allowed_ip_source or '0.0.0.0/0'])
    allowed = response_body['allowed']
    self.assertEqual(len(allowed), 2)
    used_protocols = set([x['IPProtocol'] for x in allowed])
    self.assertEqual(used_protocols, set(['6', '17']))
    self.assertEqual(allowed[0]['ports'], allowed[1]['ports'])
    self.assertFalse('sourceTags' in response_body, response_body)
    self.assertFalse('targetTags' in response_body, response_body)

  def testAddFirewallGeneratesCorrectRequest(self):
    for version in command_base.SUPPORTED_VERSIONS:
      self._doAddFirewallGeneratesCorrectRequest(version, '10.10.10.10/0')

  def testAddFirewallGeneratesCorrectRequestWithNoAllowedIpSource(self):
    for version in command_base.SUPPORTED_VERSIONS:
      self._doAddFirewallGeneratesCorrectRequest(version,
                                                 allowed_ip_source=None)

  def testGetFirewallGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)

    command = firewall_cmds.GetFirewall('getfirewall', flag_values)

    expected_project = 'test_project'
    expected_firewall = 'test_firewall'
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())

    result = command.Handle(expected_firewall)

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['firewall'], expected_firewall)

  def testDeleteFirewallGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)

    command = firewall_cmds.DeleteFirewall('deletefirewall', flag_values)

    expected_project = 'test_project'
    expected_firewall = 'test_firewall'
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    results, exceptions = command.Handle(expected_firewall)
    self.assertEqual(exceptions, [])
    self.assertEqual(len(results['items']), 1)
    result = results['items'][0]

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['firewall'], expected_firewall)

  def testDeleteMultipleFirewalls(self):
    flag_values = copy.deepcopy(FLAGS)
    command = firewall_cmds.DeleteFirewall('deletefirewall', flag_values)

    expected_project = 'test_project'
    expected_firewalls = ['test-firewalls-%02d' % x for x in xrange(100)]
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    results, exceptions = command.Handle(*expected_firewalls)
    self.assertEqual(exceptions, [])
    results = results['items']
    self.assertEqual(len(results), len(expected_firewalls))

    for expected_firewall, result in zip(expected_firewalls, results):
      self.assertEqual(result['project'], expected_project)
      self.assertEqual(result['firewall'], expected_firewall)

  def testAddtFirewallsWithTagsGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)

    command = firewall_cmds.AddFirewall('addfirewall', flag_values)

    expected_project = 'test_project'
    expected_firewall = 'test_firewall'
    submitted_network = 'test_network'
    expected_description = 'test firewall'
    expected_source_tags = ['a', 'b']
    expected_target_tags = ['c', 'd']
    flag_values.service_version = 'v1beta13'
    flag_values.project = expected_project
    flag_values.description = expected_description
    flag_values.network = submitted_network
    flag_values.allowed = [':22']
    flag_values.allowed_tag_sources = expected_source_tags
    flag_values.target_tags = expected_target_tags * 2  # Create duplicates

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())

    expected_network = command.NormalizeGlobalResourceName(expected_project,
                                                           'networks',
                                                           submitted_network)

    result = command.Handle(expected_firewall)

    self.assertEqual(result['project'], expected_project)

    response_body = result['body']
    self.assertEqual(response_body['name'], expected_firewall)
    self.assertEqual(response_body['network'], expected_network)
    self.assertEqual(response_body['description'], expected_description)

    allowed = response_body['allowed']
    self.assertEqual(len(allowed), 2)
    used_protocols = set([allowed[0]['IPProtocol'], allowed[1]['IPProtocol']])
    self.assertEqual(used_protocols, set(['6', '17']))
    self.assertEqual(allowed[0]['ports'], allowed[1]['ports'])
    self.assertEqual(allowed[0]['ports'], ['22'])
    self.assertTrue('sourceTags' in response_body)
    self.assertTrue('targetTags' in response_body)
    self.assertEqual(response_body['sourceTags'], expected_source_tags)
    self.assertEqual(response_body['targetTags'], expected_target_tags)


if __name__ == '__main__':
  unittest.main()
