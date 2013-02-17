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

"""Unit tests for the persistent disk commands."""



import path_initializer
path_initializer.InitializeSysPath()

import copy
import sys

from google.apputils import app
import gflags as flags
import unittest

from gcutil import command_base
from gcutil import disk_cmds
from gcutil import mock_api


FLAGS = flags.FLAGS


class DiskCmdsTest(unittest.TestCase):

  def _DoTestAddDiskGeneratesCorrectRequest(self, service_version):
    flag_values = copy.deepcopy(FLAGS)

    command = disk_cmds.AddDisk('adddisk', flag_values)

    expected_project = 'test_project'
    expected_disk = 'test_disk'
    expected_description = 'test disk'
    submitted_zone = 'copernicus-moon-base'
    expected_size = 20
    flag_values.service_version = service_version
    flag_values.zone = submitted_zone
    flag_values.project = expected_project
    flag_values.size_gb = expected_size
    flag_values.description = expected_description

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    results, exceptions = command.Handle(expected_disk)
    self.assertEqual(len(results['items']), 1)
    self.assertEqual(exceptions, [])
    result = results['items'][0]

    expected_zone = command.NormalizeTopLevelResourceName(
        expected_project,
        'zones',
        submitted_zone)

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['body']['name'], expected_disk)
    self.assertEqual(result['body']['description'], expected_description)
    self.assertEqual(result['body']['sizeGb'], expected_size)
    if command._IsUsingAtLeastApiVersion('v1beta14'):
      self.assertEqual(submitted_zone, result['zone'])
      self.assertFalse('zone' in result['body'])
    else:
      self.assertEqual(result['body']['zone'], expected_zone)
      self.assertFalse('zone' in result)

  def testAddDiskGeneratesCorrectRequest(self):
    for version in command_base.SUPPORTED_VERSIONS:
      self._DoTestAddDiskGeneratesCorrectRequest(version)

  def _DoTestAddMultipleDisks(self, service_version):
    flag_values = copy.deepcopy(FLAGS)
    command = disk_cmds.AddDisk('adddisk', flag_values)

    expected_kind = command._GetResourceApiKind('disk')
    expected_project = 'test_project'
    expected_disks = ['test-disk-%02d' % i for i in xrange(100)]
    expected_description = 'test disk'
    submitted_zone = 'copernicus-moon-base'
    expected_size = 12

    flag_values.service_version = service_version
    flag_values.zone = submitted_zone
    flag_values.project = expected_project
    flag_values.size_gb = expected_size
    flag_values.description = expected_description

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    expected_zone = command.NormalizeTopLevelResourceName(
        expected_project, 'zones', submitted_zone)

    results, exceptions = command.Handle(*expected_disks)
    self.assertEqual(exceptions, [])
    results = results['items']
    self.assertEqual(len(results), len(expected_disks))

    for expected_disk, result in zip(expected_disks, results):
      self.assertEqual(result['project'], expected_project)
      self.assertEqual(result['body']['kind'], expected_kind)
      self.assertEqual(result['body']['sizeGb'], expected_size)
      self.assertEqual(result['body']['name'], expected_disk)
      self.assertEqual(result['body']['description'], expected_description)
      if command._IsUsingAtLeastApiVersion('v1beta14'):
        self.assertEqual(submitted_zone, result['zone'])
        self.assertFalse('zone' in result['body'])
      else:
        self.assertFalse('zone' in result)
        self.assertEqual(result['body']['zone'], expected_zone)

  def testAddMultipleDisks(self):
    for version in command_base.SUPPORTED_VERSIONS:
      self._DoTestAddMultipleDisks(version)

  def _DoTestAddDiskFromSnapshotGeneratesCorrectRequest(self, service_version):
    flag_values = copy.deepcopy(FLAGS)

    command = disk_cmds.AddDisk('adddisk', flag_values)

    expected_project = 'test_project'
    expected_disk = 'test_disk'
    expected_description = 'test disk'
    submitted_zone = 'copernicus-moon-base'
    submitted_source_snapshot = 'snap1'
    flag_values.service_version = service_version
    flag_values.zone = submitted_zone
    flag_values.project = expected_project
    flag_values.description = expected_description
    flag_values.source_snapshot = submitted_source_snapshot

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    results, exceptions = command.Handle(expected_disk)
    self.assertEqual(len(results['items']), 1)
    self.assertEqual(exceptions, [])
    result = results['items'][0]

    expected_zone = command.NormalizeTopLevelResourceName(
        expected_project,
        'zones',
        submitted_zone)

    expected_source_snapshot = command.NormalizeGlobalResourceName(
        expected_project,
        'snapshots',
        submitted_source_snapshot)
    if command._IsUsingAtLeastApiVersion('v1beta14'):
      self.assertEqual(submitted_zone, result['zone'])
      self.assertFalse('zone' in result['body'])
    else:
      self.assertFalse('zone' in result)
      self.assertEqual(result['body']['zone'], expected_zone)

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['body']['name'], expected_disk)
    self.assertEqual(result['body']['description'], expected_description)
    self.assertEqual(result['body']['sourceSnapshot'], expected_source_snapshot)

  def testAddDiskFromSnapshotGeneratesCorrectRequest(self):
    for version in command_base.SUPPORTED_VERSIONS:
      self._DoTestAddDiskFromSnapshotGeneratesCorrectRequest(version)

  def testAddDiskDefaultSizeGb(self):
    flag_values = copy.deepcopy(FLAGS)

    command = disk_cmds.AddDisk('adddisk', flag_values)

    flag_values.zone = 'copernicus-moon-base'
    flag_values.project = 'test_project'

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    results, exceptions = command.Handle('disk1')
    self.assertEqual(len(results['items']), 1)
    self.assertEqual(exceptions, [])
    result = results['items'][0]

    # We did not set the size, make sure it defaults to 10GB.
    self.assertEqual(10, result['body']['sizeGb'])

  def testAddDiskFromImageDoesNotPassSizeGbUnlessExplicitlySet(self):
    flag_values = copy.deepcopy(FLAGS)

    command = disk_cmds.AddDisk('adddisk', flag_values)

    flag_values.zone = 'copernicus-moon-base'
    flag_values.project = 'test_project'
    flag_values.source_image = 'image1'
    flag_values.service_version = 'v1beta14'

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    results, exceptions = command.Handle('disk1')
    self.assertEqual(len(results['items']), 1)
    self.assertEqual(exceptions, [])
    result = results['items'][0]

    # Make sure we did not pass 'sizeGb' in the body.
    self.assertFalse('sizeGb' in result['body'])

  def _DoTestAddDiskFromImageGeneratesCorrectRequest(self, service_version):
    flag_values = copy.deepcopy(FLAGS)

    command = disk_cmds.AddDisk('adddisk', flag_values)

    expected_project = 'test_project'
    expected_disk = 'test_disk'
    expected_description = 'test disk'
    expected_size_gb = 123
    submitted_zone = 'copernicus-moon-base'
    submitted_source_image = 'image1'
    submitted_size_gb = 123
    flag_values.zone = submitted_zone
    flag_values.project = expected_project
    flag_values.description = expected_description
    flag_values.source_image = submitted_source_image
    flag_values.size_gb = submitted_size_gb
    flag_values.service_version = service_version

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    results, exceptions = command.Handle(expected_disk)
    self.assertEqual(len(results['items']), 1)
    self.assertEqual(exceptions, [])
    result = results['items'][0]

    expected_zone = command.NormalizeTopLevelResourceName(
        expected_project,
        'zones',
        submitted_zone)

    expected_source_image = command.NormalizeGlobalResourceName(
        expected_project,
        'images',
        submitted_source_image)

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['body']['name'], expected_disk)
    self.assertEqual(result['body']['description'], expected_description)
    self.assertEqual(result['body']['sizeGb'], expected_size_gb)
    self.assertEqual(result['sourceImage'], expected_source_image)
    if command._IsUsingAtLeastApiVersion('v1beta14'):
      self.assertEqual(submitted_zone, result['zone'])
      self.assertFalse('zone' in result['body'])
    else:
      self.assertEqual(result['body']['zone'], expected_zone)
      self.assertFalse('zone' in result)

  def testAddDiskFromImageGeneratesCorrectRequest(self):
    for version in command_base.SUPPORTED_VERSIONS:
      self._DoTestAddDiskFromImageGeneratesCorrectRequest(version)

  def testAddDiskWithKernelGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)

    command = disk_cmds.AddDisk('adddisk', flag_values)

    expected_project = 'test_project'
    expected_disk = 'test_disk'
    expected_description = 'test disk'
    expected_size_gb = 123
    submitted_zone = 'copernicus-moon-base'
    submitted_size_gb = 123
    flag_values.zone = submitted_zone
    flag_values.project = expected_project
    flag_values.description = expected_description
    flag_values.size_gb = submitted_size_gb

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    results, exceptions = command.Handle(expected_disk)
    self.assertEqual(len(results['items']), 1)
    self.assertEqual(exceptions, [])
    result = results['items'][0]

    expected_zone = command.NormalizeTopLevelResourceName(
        expected_project,
        'zones',
        submitted_zone)

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['body']['name'], expected_disk)
    self.assertEqual(result['body']['description'], expected_description)
    self.assertEqual(result['body']['sizeGb'], expected_size_gb)
    if command._IsUsingAtLeastApiVersion('v1beta14'):
      self.assertEqual(submitted_zone, result['zone'])
      self.assertFalse('zone' in result['body'])
    else:
      self.assertFalse('zone' in result)
      self.assertEqual(result['body']['zone'], expected_zone)

  def testAddDiskRequiresZone(self):
    flag_values = copy.deepcopy(FLAGS)

    command = disk_cmds.AddDisk('adddisk', flag_values)

    expected_project = 'test_project'
    expected_disk = 'test_disk'
    expected_description = 'test disk'
    expected_size = 20
    submitted_version = command_base.CURRENT_VERSION
    submitted_zone = 'us-east-a'

    flag_values.service_version = submitted_version
    flag_values.project = expected_project
    flag_values.size_gb = expected_size
    flag_values.description = expected_description

    command.SetFlags(flag_values)

    zones = {'items': [{'name': 'us-east-a'},
                       {'name': 'us-east-b'},
                       {'name': 'us-east-c'},
                       {'name': 'us-west-a'}]}

    class MockZonesApi(object):
      def list(self, **unused_kwargs):
        return mock_api.MockRequest(zones)

    api = mock_api.MockApi()
    api.zones = MockZonesApi
    command.SetApi(api)
    command._credential = mock_api.MockCredential()

    expected_zone = command.NormalizeTopLevelResourceName(
        expected_project,
        'zones',
        submitted_zone)

    mock_output = mock_api.MockOutput()
    mock_input = mock_api.MockInput('1\n\r')
    oldin = sys.stdin
    sys.stdin = mock_input
    oldout = sys.stdout
    sys.stdout = mock_output

    results, exceptions = command.Handle(expected_disk)
    self.assertEqual(len(results['items']), 1)
    self.assertEqual(exceptions, [])
    result = results['items'][0]

    if command._IsUsingAtLeastApiVersion('v1beta14'):
      self.assertEqual(submitted_zone, result['zone'])
      self.assertFalse('zone' in result['body'])
    else:
      self.assertFalse('zone' in result)
      self.assertEqual(result['body']['zone'], expected_zone)

    sys.stdin = oldin
    sys.stdout = oldout

  def _DoTestGetDiskGeneratesCorrectRequest(self, service_version):
    flag_values = copy.deepcopy(FLAGS)

    command = disk_cmds.GetDisk('getdisk', flag_values)

    expected_project = 'test_project'
    expected_disk = 'test_disk'
    flag_values.project = expected_project
    flag_values.service_version = service_version
    flag_values.zone = 'zone-a'

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()
    submitted_zone = 'copernicus-moon-base'
    if command._IsUsingAtLeastApiVersion('v1beta14'):
      flag_values.zone = submitted_zone

    result = command.Handle(expected_disk)

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['disk'], expected_disk)
    if command._IsUsingAtLeastApiVersion('v1beta14'):
      self.assertEqual(submitted_zone, result['zone'])
    else:
      self.assertFalse('zone' in result)

  def testGetDiskGeneratesCorrectRequest(self):
    for version in command_base.SUPPORTED_VERSIONS:
      self._DoTestGetDiskGeneratesCorrectRequest(version)

  def _DoTestDeleteDiskGeneratesCorrectRequest(self, service_version):
    flag_values = copy.deepcopy(FLAGS)

    command = disk_cmds.DeleteDisk('deletedisk', flag_values)

    expected_project = 'test_project'
    expected_disk = 'test_disk'
    flag_values.project = expected_project
    flag_values.zone = 'zone-a'

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    flag_values.service_version = service_version
    submitted_zone = 'copernicus-moon-base'
    if command._IsUsingAtLeastApiVersion('v1beta14'):
      flag_values.zone = submitted_zone

    command._credential = mock_api.MockCredential()

    results, exceptions = command.Handle(expected_disk)
    self.assertEqual(len(results['items']), 1)
    self.assertEqual(exceptions, [])
    result = results['items'][0]

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['disk'], expected_disk)
    if command._IsUsingAtLeastApiVersion('v1beta14'):
      self.assertEqual(submitted_zone, result['zone'])
    else:
      self.assertFalse('zone' in result)

  def testDeleteDiskGeneratesCorrectRequest(self):
    for version in command_base.SUPPORTED_VERSIONS:
      self._DoTestDeleteDiskGeneratesCorrectRequest(version)

  def testDeleteMultipleDisks(self):
    flag_values = copy.deepcopy(FLAGS)
    command = disk_cmds.DeleteDisk('deletedisk', flag_values)

    expected_project = 'test_project'
    expected_disks = ['test-disk-%02d' % x for x in xrange(100)]
    flag_values.project = expected_project
    flag_values.zone = 'zone-a'

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    results, exceptions = command.Handle(*expected_disks)
    self.assertEqual(exceptions, [])
    results = results['items']
    self.assertEqual(len(results), len(expected_disks))

    for expected_disk, result in zip(expected_disks, results):
      self.assertEqual(result['project'], expected_project)
      self.assertEqual(result['disk'], expected_disk)

  def testAddWithNoDisk(self):
    flag_values = copy.deepcopy(FLAGS)
    command = disk_cmds.AddDisk('adddisk', flag_values)
    self.assertRaises(app.UsageError, command.Handle)


if __name__ == '__main__':
  unittest.main()
