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

"""Unit tests for the asynchronous operations commands."""



import path_initializer
path_initializer.InitializeSysPath()

import copy

import gflags as flags
import unittest

from gcutil import command_base
from gcutil import mock_api
from gcutil import operation_cmds

FLAGS = flags.FLAGS


class OperationCmdsTest(unittest.TestCase):

  def _DoTestGetOperationGeneratesCorrectRequest(self, service_version):
    flag_values = copy.deepcopy(FLAGS)

    command = operation_cmds.GetOperation('getoperation', flag_values)

    expected_project = 'test_project'
    expected_operation = 'test_operation'
    flag_values.project = expected_project
    flag_values.service_version = service_version

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    if command._IsUsingAtLeastApiVersion('v1beta14'):
      submitted_zone = 'myzone'
      flag_values.zone = submitted_zone

    result = command.Handle(expected_operation)

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['operation'], expected_operation)

    api = command._global_operations_api
    if command._IsUsingAtLeastApiVersion('v1beta14'):
      api = command._zone_operations_api

    self.assertEquals(1, len(api.requests))
    request = api.requests[0]
    if command._IsUsingAtLeastApiVersion('v1beta14'):
      self.assertEqual(submitted_zone, request.request_payload['zone'])
    else:
      self.assertFalse('zone' in request.request_payload)
    self.assertEqual(expected_project, request.request_payload['project'])
    self.assertEqual(expected_operation, request.request_payload['operation'])

  def testGetOperationGeneratesCorrectRequest(self):
    for version in command_base.SUPPORTED_VERSIONS:
      self._DoTestGetOperationGeneratesCorrectRequest(version)

  def _DoTestDeleteOperationGeneratesCorrectRequest(self, service_version):
    flag_values = copy.deepcopy(FLAGS)

    command = operation_cmds.DeleteOperation('deleteoperation', flag_values)

    expected_project = 'test_project'
    expected_operation = 'test_operation'
    flag_values.project = expected_project
    flag_values.service_version = service_version

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()
    if command._IsUsingAtLeastApiVersion('v1beta14'):
      submitted_zone = 'myzone'
      flag_values.zone = submitted_zone

    results, exceptions = command.Handle(expected_operation)
    self.assertEqual(exceptions, [])
    self.assertEqual(results, '')

    # Verify the request
    api = command._global_operations_api
    if command._IsUsingAtLeastApiVersion('v1beta14'):
      api = command._zone_operations_api

    self.assertEquals(1, len(api.requests))
    request = api.requests[0]
    if command._IsUsingAtLeastApiVersion('v1beta14'):
      self.assertEqual(submitted_zone, request.request_payload['zone'])
    else:
      self.assertFalse('zone' in request.request_payload)
    self.assertEqual(expected_project, request.request_payload['project'])
    self.assertEqual(expected_operation, request.request_payload['operation'])

  def testDeleteOperationGeneratesCorrectRequest(self):
    for version in command_base.SUPPORTED_VERSIONS:
      self._DoTestDeleteOperationGeneratesCorrectRequest(version)

  def _DoTestGetGlobalOperationGeneratesCorrectRequest(self, service_version):
    flag_values = copy.deepcopy(FLAGS)

    command = operation_cmds.GetOperation('getoperation', flag_values)

    expected_project = 'test_project'
    expected_operation = 'test_operation'
    flag_values.project = expected_project
    flag_values.service_version = service_version
    flag_values.zone = command_base.GLOBAL_ZONE_NAME

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()
    if not command._IsUsingAtLeastApiVersion('v1beta14'):
      return

    command.Handle(expected_operation)

    # Verify the request
    self.assertEquals(1, len(command._global_operations_api.requests))
    request = command._global_operations_api.requests[0]
    self.assertEqual('get', request.method_name)
    self.assertEqual(expected_project, request.request_payload['project'])
    self.assertEqual(expected_operation, request.request_payload['operation'])

  def testGetGlobalOperationGeneratesCorrectRequest(self):
    for version in command_base.SUPPORTED_VERSIONS:
      self._DoTestGetGlobalOperationGeneratesCorrectRequest(version)

  def _DoTestDeleteGlobalOperationGeneratesCorrectRequest(self,
                                                          service_version):
    flag_values = copy.deepcopy(FLAGS)

    command = operation_cmds.DeleteOperation('deleteoperation', flag_values)

    expected_project = 'test_project'
    expected_operation = 'test_operation'
    flag_values.project = expected_project
    flag_values.service_version = service_version
    flag_values.zone = command_base.GLOBAL_ZONE_NAME

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()
    if not command._IsUsingAtLeastApiVersion('v1beta14'):
      return

    results, exceptions = command.Handle(expected_operation)
    self.assertEqual(exceptions, [])
    self.assertEqual(results, '')

    # Verify the request
    self.assertEquals(1, len(command._global_operations_api.requests))
    request = command._global_operations_api.requests[0]
    self.assertEqual('delete', request.method_name)
    self.assertEqual(expected_project, request.request_payload['project'])
    self.assertEqual(expected_operation, request.request_payload['operation'])

  def testDeleteGlobalOperationGeneratesCorrectRequest(self):
    for version in command_base.SUPPORTED_VERSIONS:
      self._DoTestDeleteGlobalOperationGeneratesCorrectRequest(version)

  def testDeleteMultipleOperations(self):
    flag_values = copy.deepcopy(FLAGS)
    command = operation_cmds.DeleteOperation('deleteoperation', flag_values)

    expected_project = 'test_project'
    expected_operations = ['test-operation-%02d' % x for x in xrange(100)]
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    results, exceptions = command.Handle(*expected_operations)
    self.assertEqual(exceptions, [])
    self.assertEqual(results, '')


if __name__ == '__main__':
  unittest.main()
