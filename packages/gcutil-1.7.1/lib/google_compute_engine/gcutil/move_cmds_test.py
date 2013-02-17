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

"""Unit tests for the move commands."""



import path_initializer
path_initializer.InitializeSysPath()

import copy
import uuid

from google.apputils import app
import gflags as flags
import unittest

from gcutil import command_base
from gcutil import mock_api
from gcutil import move_cmds

FLAGS = flags.FLAGS

class MoveInstancesBaseTestCase(unittest.TestCase):

  def setUp(self):
    self.flag_values = copy.deepcopy(FLAGS)
    self.command = self._CreateCommand()
    self.api = mock_api.MockApi()
    self.command.SetFlags(self.flag_values)
    self.command.SetApi(self.api)

  def _CreateCommand(self):
    return move_cmds.MoveInstances('basemoveinstances', self.flag_values)

class MoveInstancesBaseTest(MoveInstancesBaseTestCase):

  cmd_name = 'moveinstancesbase'

  def testExtractAvailableQuota(self):
    project_quota = [
        {'metric': 'INSTANCES',
         'usage': 5.0,
         'limit': 10.0},
        {'metric': 'CPUS',
         'usage': 40.0,
         'limit': 0},  # Quota was changed after resource-creation.
        {'metric': 'EPHEMERAL_ADDRESSES',
         'usage': 5.0,
         'limit': 10.0},
        {'metric': 'DISKS',
         'usage': 7.0,
         'limit': 10.0},
        {'metric': 'DISKS_TOTAL_GB',
         'usage': 40.0,
         'limit': 100.0},
        {'metric': 'SNAPSHOTS',
         'usage': 3.0,
         'limit': 100.0},
        {'metric': 'NETWORKS',
         'usage': 2.0,
         'limit': 10.0},
        {'metric': 'FIREWALLS',
         'usage': 3.0,
         'limit': 10.0},
        {'metric': 'IMAGES',
         'usage': 9.0,
         'limit': 10.0}]

    zone_quota = [
        {'metric': 'INSTANCES',
         'usage': 3.0,
         'limit': 10.0},
        {'metric': 'CPUS',
         'usage': 3.0,
         'limit': 10.0},
        {'metric': 'DISKS',
         'usage': 2.0,
         'limit': 10.0},
        {'metric': 'DISKS_TOTAL_GB',
         'usage': 22.0,
         'limit': 25.0}]

    requirements = {
        'INSTANCES': 2.0,
        'CPUS': 2.0,
        'DISKS_TOTAL_GB': 32.0,
        'SNAPSHOTS': 3.0,
        'DISKS': 3.0}

    expected = {
        'INSTANCES': 7.0,
        'CPUS': -38.0,
        'DISKS_TOTAL_GB': 3.0,
        'SNAPSHOTS': 97.0,
        'DISKS': 6.0}

    self.assertEqual(self.command._ExtractAvailableQuota(
        project_quota, zone_quota, requirements), expected)


class MoveInstancesTest(MoveInstancesBaseTestCase):

  def _CreateCommand(self):
    return move_cmds.MoveInstances('moveinstances', self.flag_values)

  def testServiceVersionValidation(self):
    for version in command_base.SUPPORTED_VERSIONS:
      if version == 'v1beta14':
        break

      self.flag_values.source_zone = 'src-zone'
      self.flag_values.destination_zone = 'dest-zone'
      self.flag_values.service_version = version
      self.assertRaises(app.UsageError, self.command.Handle, ['.*'])

  def testFlagValidationWithNoSourceZone(self):
    self.flag_values.destination_zone = 'dest-zone'
    self.flag_values.service_version = 'v1beta14'
    self.assertRaises(app.UsageError, self.command.Handle, ['.*'])

  def testFlagValidationWithNoDestinationZone(self):
    self.flag_values.source_zone = 'src-zone'
    self.flag_values.service_version = 'v1beta14'
    self.assertRaises(app.UsageError, self.command.Handle, ['.*'])

  def testFlagValidationWithNoSameSrcAndDest(self):
    self.flag_values.source_zone = 'my-zone'
    self.flag_values.destination_zone = 'my-zone'
    self.assertRaises(app.UsageError, self.command.Handle, ['.*'])

  def testGenerateSnapshotNames(self):
    test_cases = (
        [],
        ['disk-0'],
        ['disk-1', 'disk2', 'disk3'])

    for arg in test_cases:
      res = self.command._GenerateSnapshotNames(arg)
      self.assertEqual(len(res), len(arg))
      self.assertEqual(sorted(res.keys()), sorted(arg))
      for val in res.values():
        self.assertTrue(isinstance(val, basestring))
        self.assertTrue(val.startswith('snapshot-'))
        try:
          uuid.UUID(val[len('snapshot-'):])
        except ValueError:
          self.fail('Value generated does not include valid UUID.')

  def _GenerateInstanceResources(self, num, prefix='instance'):
    template = {
        'status': 'RUNNING',
        'kind': 'compute#instance',
        'machineType': 'https://googleapis.com/compute/.../n1-standard-1',
        'zone': 'https://googleapis.com/compute/.../zones/my-zone',
        'tags': [],
        'image': 'https://googleapis.com/compute/.../images/gcel',
        'disks': [
            {
                'index': 0,
                'kind': 'compute#instanceDisk',
                'type': 'EPHEMERAL',
                'mode': 'READ_WRITE'
                },
            {
                'index': 1,
                'kind': 'compute#attachedDisk',
                'mode': 'READ_ONLY',
                'type': 'PERSISTENT'
                }
            ],
        'networkInterfaces': [
            {
                'networkIP': '10.211.197.175',
                'kind': 'compute#instanceNetworkInterface',
                'accessConfigs': [
                    {
                        'type': 'ONE_TO_ONE_NAT',
                        'name': 'External NAT',
                        'natIP': '173.255.120.98'
                        }
                    ],
                'name': 'nic0',
                'network': 'https://googleapis.com/compute/.../networks/default'
                }
            ],
        'id': '12884714477555140369'}

    res = []
    for i in xrange(num):
      instance = copy.deepcopy(template)
      instance['name'] = '%s-%s' % (prefix, i)
      instance['selfLink'] = (
          'https://googleapis.com/compute/.../instances/%s' % instance['name'])
      instance['disks'][1]['deviceName'] = instance['name']
      instance['disks'][1]['source'] = (
          'https://www.googleapis.com/compute/.../disks/%s' % instance['name'])
      res.append(instance)
    return res

  def testCheckInstancePreconditionsWithNoMatchingInstances(self):
    self.assertRaises(command_base.CommandError,
                      self.command._CheckInstancePreconditions,
                      [], [])

  def testCheckInstancePreconditionsWithTooManyInstances(self):
    for num_instances_to_mv in (101, 120, 200):
      for num_instances_in_dest in (0, 10, 100, 101, 200):
        instances_to_mv = self._GenerateInstanceResources(
            num_instances_to_mv, prefix='i')
        instances_in_dest = self._GenerateInstanceResources(
            num_instances_in_dest, prefix='x')
        self.assertRaises(
            command_base.CommandError,
            self.command._CheckInstancePreconditions,
            instances_to_mv,
            instances_in_dest)

  def testCheckInstancePreconditionsWithNameCollisions(self):
    # Tests with lots of collisions.
    for num_instances in (1, 2, 10):
      instances = self._GenerateInstanceResources(num_instances)
      self.assertRaises(command_base.CommandError,
                        self.command._CheckInstancePreconditions,
                        instances, instances)

    # Tests with only a single collision.
    for num_instances in (1, 2, 10):
      instances_to_mv = self._GenerateInstanceResources(
          num_instances, prefix='i')
      instances_in_dest = self._GenerateInstanceResources(
          num_instances, prefix='x')
      instances_in_dest.extend(self._GenerateInstanceResources(1, prefix='i'))
      self.assertRaises(
          command_base.CommandError,
          self.command._CheckInstancePreconditions,
          instances_to_mv,
          instances_in_dest)

  def testCheckInstancePreconditionsUnderNormalConditions(self):
    for num_instances_to_mv in (1, 2, 10):
      for num_instances_in_dest in (0, 2, 10):
        instances_to_mv = self._GenerateInstanceResources(
            num_instances_to_mv, prefix='i')
        instances_in_dest = self._GenerateInstanceResources(
            num_instances_in_dest, prefix='x')
        self.command._CheckInstancePreconditions(
            instances_to_mv, instances_in_dest)

  def testCheckDiskPreconditionsWithTooManyDisks(self):
    for num_disks in (101, 120, 200):
      disk_names = ['disk-%s' % i for i in xrange(num_disks)]
      self.assertRaises(
          command_base.CommandError,
          self.command._CheckDiskPreconditions,
          [],
          disk_names)

  def testCheckDiskPreconditionsWithPoorDiskAttachment(self):
    for num_instances in (1, 2, 10):
      for num_disks in xrange(1, num_instances + 1):
        self.assertRaises(
            command_base.CommandError,
            self.command._CheckDiskPreconditions,
            self._GenerateInstanceResources(num_instances, prefix='i'),
            ['i-%s' % i for i in xrange(num_disks)])


class ResumeMoveTest(MoveInstancesBaseTestCase):

  def _CreateCommand(self):
    return move_cmds.ResumeMove('resumemove', self.flag_values)

  def testGetKeyWithGoodKeys(self):
    test_cases = (
        ({'key1': []}, 'key1', []),
        ({'key1': [1, 2, 3]}, 'key1', [1, 2, 3]),
        ({'key1': [1, 2, 3], 'key2': 5}, 'key2', 5))
    for log, key, expected in test_cases:
      self.assertEqual(self.command._GetKey(log, key), expected)

  def testGetKeyWithBadKeys(self):
    test_cases = (
        {},
        {'key1': []},
        {'key1': [1, 2, 3]},
        {'key1': [1, 2, 3], 'key2': 5})
    for log in test_cases:
      self.assertRaises(command_base.CommandError,
                        self.command._GetKey, log, 'nonexistent')


if __name__ == '__main__':
  unittest.main()
