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

"""Unit tests for the persistent disk snapshot commands."""



import path_initializer
path_initializer.InitializeSysPath()

import copy
import sys

import gflags as flags
import unittest

from gcutil import command_base
from gcutil import mock_api
from gcutil import snapshot_cmds


FLAGS = flags.FLAGS


class SnapshotCmdsTest(unittest.TestCase):

  def _DoTestAddSnapshotGeneratesCorrectRequest(self, service_version):
    flag_values = copy.deepcopy(FLAGS)

    command = snapshot_cmds.AddSnapshot('addsnapshot', flag_values)

    expected_project = 'test_project'
    expected_snapshot = 'test_snapshot'
    expected_description = 'test snapshot'
    submitted_source_disk = 'disk1'
    submitted_zone = 'myzone'
    flag_values.service_version = service_version
    flag_values.source_disk = submitted_source_disk
    flag_values.project = expected_project
    flag_values.description = expected_description

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())

    if command._IsUsingAtLeastApiVersion('v1beta14'):
      flag_values.zone = submitted_zone

    expected_source_disk = command.NormalizePerZoneResourceName(
        expected_project,
        submitted_zone,
        'disks',
        submitted_source_disk)

    result = command.Handle(expected_snapshot)

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['body']['name'], expected_snapshot)
    self.assertEqual(result['body']['description'], expected_description)
    self.assertEqual(result['body']['sourceDisk'], expected_source_disk)

  def testAddSnapshotGeneratesCorrectRequest(self):
    for version in command_base.SUPPORTED_VERSIONS:
      self._DoTestAddSnapshotGeneratesCorrectRequest(version)

  def _DoTestAddSnapshotWithoutZoneGeneratesCorrectRequest(self,
                                                           service_version):
    flag_values = copy.deepcopy(FLAGS)

    command = snapshot_cmds.AddSnapshot('addsnapshot', flag_values)

    expected_project = 'test_project'
    expected_snapshot = 'test_snapshot'
    expected_description = 'test snapshot'
    submitted_source_disk = 'disk1'
    disk_zone = 'us-east-a'
    api_base = 'https://www.googleapis.com/compute/%s' % service_version
    disk_self_link = '%s/projects/%s/zones/%s/disks/%s' % (
        api_base, expected_project, disk_zone, submitted_source_disk)

    flag_values.service_version = service_version
    flag_values.source_disk = submitted_source_disk
    flag_values.project = expected_project
    flag_values.description = expected_description

    zones = {'items': [{'name': disk_zone}]}
    disks = {'items': [{'name': 'disk1',
                        'selfLink': disk_self_link}]}

    class MockZonesApi(object):
      def list(self, **unused_kwargs):
        return mock_api.MockRequest(zones)

    class MockDisksApi(object):
      def list(self, **unused_kwargs):
        return mock_api.MockRequest(disks)

    api = mock_api.MockApi()
    api.zones = MockZonesApi
    api.disks = MockDisksApi

    command.SetFlags(flag_values)
    command.SetApi(api)

    expected_source_disk = command.NormalizePerZoneResourceName(
        expected_project,
        disk_zone,
        'disks',
        submitted_source_disk)

    result = command.Handle(expected_snapshot)

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['body']['name'], expected_snapshot)
    self.assertEqual(result['body']['description'], expected_description)
    self.assertEqual(result['body']['sourceDisk'], expected_source_disk)

  def testAddSnapshotWithoutZoneGeneratesCorrectRequest(self):
    for version in command_base.SUPPORTED_VERSIONS:
      self._DoTestAddSnapshotWithoutZoneGeneratesCorrectRequest(version)

  def testAddSnapshotRequiresSourceDisk(self):
    flag_values = copy.deepcopy(FLAGS)

    command = snapshot_cmds.AddSnapshot('addsnapshot', flag_values)

    expected_project = 'test_project'
    expected_snapshot = 'test_snapshot'
    expected_description = 'test snapshot'
    submitted_version = command_base.CURRENT_VERSION
    submitted_source_disk = 'disk1'

    flag_values.service_version = submitted_version
    flag_values.project = expected_project
    flag_values.description = expected_description

    command.SetFlags(flag_values)

    def GetDiskPath(disk_name):
      disk_path = 'projects/test_project/disks/%s' % (disk_name)
      if command._IsUsingAtLeastApiVersion('v1beta14'):
        disk_path = 'projects/test_project/zones/zone-a/disks/%s' % (disk_name)
      return disk_path

    disks = {
        'items': [
            {'name': GetDiskPath('disk1')},
            {'name': GetDiskPath('disk2')},
            {'name': GetDiskPath('disk3')}]}

    class MockDisksApi(object):
      def list(self, **unused_kwargs):
        return mock_api.MockRequest(disks)

    api = mock_api.MockApi()
    api.disks = MockDisksApi
    command.SetApi(api)

    expected_disk = command.NormalizePerZoneResourceName(
        expected_project,
        'zone-a',
        'disks',
        submitted_source_disk)

    mock_output = mock_api.MockOutput()
    mock_input = mock_api.MockInput('1\n\r')
    oldin = sys.stdin
    sys.stdin = mock_input
    oldout = sys.stdout
    sys.stdout = mock_output

    result = command.Handle(expected_snapshot)
    self.assertEqual(result['body']['sourceDisk'], expected_disk)
    sys.stdin = oldin
    sys.stdout = oldout

  def _DoTestGetSnapshotGeneratesCorrectRequest(self, service_version):
    flag_values = copy.deepcopy(FLAGS)

    command = snapshot_cmds.GetSnapshot('getsnapshot', flag_values)

    expected_project = 'test_project'
    expected_snapshot = 'test_snapshot'
    flag_values.project = expected_project
    flag_values.service_version = service_version

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())

    result = command.Handle(expected_snapshot)

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['snapshot'], expected_snapshot)

  def testGetSnapshotGeneratesCorrectRequest(self):
    for version in command_base.SUPPORTED_VERSIONS:
      self._DoTestGetSnapshotGeneratesCorrectRequest(version)

  def _DoTestDeleteSnapshotGeneratesCorrectRequest(self, service_version):
    flag_values = copy.deepcopy(FLAGS)

    command = snapshot_cmds.DeleteSnapshot('deletesnapshot', flag_values)

    expected_project = 'test_project'
    expected_snapshot = 'test_snapshot'
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()
    flag_values.service_version = service_version

    results, exceptions = command.Handle(expected_snapshot)
    self.assertEquals(exceptions, [])
    self.assertEquals(len(results['items']), 1)
    result = results['items'][0]

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['snapshot'], expected_snapshot)

  def testDeleteSnapshotGeneratesCorrectRequest(self):
    for version in command_base.SUPPORTED_VERSIONS:
      self._DoTestDeleteSnapshotGeneratesCorrectRequest(version)

  def testDeleteMultipleSnapshots(self):
    flag_values = copy.deepcopy(FLAGS)
    command = snapshot_cmds.DeleteSnapshot('deletesnapshot', flag_values)

    expected_project = 'test_project'
    expected_snapshots = ['test-snapshot-%02d' % x for x in xrange(100)]
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    results, exceptions = command.Handle(*expected_snapshots)
    self.assertEqual(exceptions, [])
    results = results['items']
    self.assertEqual(len(results), len(expected_snapshots))

    for expected_snapshot, result in zip(expected_snapshots, results):
      self.assertEqual(result['project'], expected_project)
      self.assertEqual(result['snapshot'], expected_snapshot)


if __name__ == '__main__':
  unittest.main()
