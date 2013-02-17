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

"""Unit tests for the project commands."""



import path_initializer
path_initializer.InitializeSysPath()

import copy
import re
import tempfile


import gflags as flags
import unittest

from gcutil import auth_helper
from gcutil import command_base
from gcutil import flags_cache
from gcutil import mock_api
from gcutil import project_cmds

FLAGS = flags.FLAGS


class ComputeCmdsTest(unittest.TestCase):
  def testGetProjectGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)

    command = project_cmds.GetProject('getproject', flag_values)

    expected_project = 'test_project'
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())

    result = command.Handle()

    self.assertEqual(result['project'], expected_project)

  def testSetCommonInstanceMetadataGeneratesCorrectRequest(self):

    class SetCommonInstanceMetadata(object):

      def __call__(self, project, body):
        self._project = project
        self._body = body
        return self

      def execute(self):
        return {'project': self._project, 'body': self._body}

    flag_values = copy.deepcopy(FLAGS)
    command = project_cmds.SetCommonInstanceMetadata(
        'setcommoninstancemetadata', flag_values)

    expected_project = 'test_project'
    flag_values.project = expected_project
    flag_values.service_version = 'v1beta13'
    with tempfile.NamedTemporaryFile() as metadata_file:
      metadata_file.write('foo:bar')
      metadata_file.flush()
      flag_values.metadata_from_file = ['sshKeys:%s' % metadata_file.name]

      command.SetFlags(flag_values)
      command.SetApi(mock_api.MockApi())
      command._projects_api.get = mock_api.CommandExecutor(
          {'commonInstanceMetadata': [{'key': 'sshKeys', 'value': ''}]})
      command._projects_api.setCommonInstanceMetadata = (
          SetCommonInstanceMetadata())

      result = command.Handle()
      self.assertEquals(expected_project, result['project'])
      self.assertEquals(
          {'kind': 'compute#metadata',
           'items': [{'key': 'sshKeys', 'value': 'foo:bar'}]},
          result['body'])

  def testSetCommonInstanceMetadataChecksForOverwrites(self):
    flag_values = copy.deepcopy(FLAGS)
    command = project_cmds.SetCommonInstanceMetadata(
        'setcommoninstancemetadata', flag_values)

    expected_project = 'test_project'
    flag_values.project = expected_project
    flag_values.service_version = 'v1beta13'
    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._projects_api.get = mock_api.CommandExecutor(
        {'commonInstanceMetadata': [{'key': 'sshKeys', 'value': 'foo:bar'}]})

    self.assertRaises(command_base.CommandError, command.Handle)

if __name__ == '__main__':
  unittest.main()
