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

"""Unit tests for the machine image commands."""



import path_initializer
path_initializer.InitializeSysPath()

import copy

import gflags as flags
import unittest

from gcutil import command_base
from gcutil import image_cmds
from gcutil import mock_api

FLAGS = flags.FLAGS


class ImageCmdsTest(unittest.TestCase):

  def _doTestAddImageGeneratesCorrectRequest(self, service_version,
                                             requested_source,
                                             expected_source):
    flag_values = copy.deepcopy(FLAGS)

    command = image_cmds.AddImage('addimage', flag_values)

    expected_project = 'test_project'
    expected_image = 'test_image'
    expected_description = 'test image'
    submitted_kernel = 'projects/test_project/kernels/test_kernel'
    expected_type = 'RAW'
    flag_values.project = expected_project
    flag_values.description = expected_description
    flag_values.preferred_kernel = submitted_kernel
    flag_values.service_version = service_version

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())

    expected_kernel = command.NormalizeGlobalResourceName(expected_project,
                                                          'kernels',
                                                          submitted_kernel)

    result = command.Handle(expected_image, requested_source)

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['body']['name'], expected_image)
    self.assertEqual(result['body']['description'], expected_description)

    self.assertEqual(result['body']['preferredKernel'], expected_kernel)
    self.assertEqual(result['body']['sourceType'], expected_type)
    self.assertEqual(result['body']['rawDisk']['source'], expected_source)

  def testAddImageGeneratesCorrectRequest(self):
    for version in command_base.SUPPORTED_VERSIONS:
      self._doTestAddImageGeneratesCorrectRequest(
          version, 'http://test.source', 'http://test.source')
      self._doTestAddImageGeneratesCorrectRequest(
          version, 'gs://test_bucket/source',
          'http://storage.googleapis.com/test_bucket/source')

  def testGetImageGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)

    command = image_cmds.GetImage('getimage', flag_values)

    expected_project = 'test_project'
    expected_image = 'test_image'
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())

    result = command.Handle(expected_image)

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['image'], expected_image)

  def testDeleteImageGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)

    command = image_cmds.DeleteImage('deleteimage', flag_values)

    expected_project = 'test_project'
    expected_image = 'test_image'
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    results, exceptions = command.Handle(expected_image)
    self.assertEqual(exceptions, [])
    self.assertEqual(len(results['items']), 1)
    result = results['items'][0]

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['image'], expected_image)

  def testDeleteMultipleImages(self):
    flag_values = copy.deepcopy(FLAGS)
    command = image_cmds.DeleteImage('deleteimage', flag_values)

    expected_project = 'test_project'
    expected_images = ['test-image-%02d' % x for x in xrange(100)]
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    results, exceptions = command.Handle(*expected_images)
    self.assertEqual(exceptions, [])
    results = results['items']
    self.assertEqual(len(results), len(expected_images))

    for expected_image, result in zip(expected_images, results):
      self.assertEqual(result['project'], expected_project)
      self.assertEqual(result['image'], expected_image)

  def testDeprecate(self):
    flag_values = copy.deepcopy(FLAGS)

    command = image_cmds.Deprecate('deprecateimage', flag_values)

    expected_project = 'test_project'
    expected_image = 'test_image'
    expected_state = 'DEPRECATED'
    expected_replacement = 'replacement_image'
    expected_obsolete_timestamp = '1970-01-01T00:00:00Z'
    expected_deleted_timestamp = '1980-01-01T00:00:00.000Z'
    flag_values.project = expected_project
    flag_values.state = expected_state
    flag_values.replacement = expected_replacement
    flag_values.obsolete_on = expected_obsolete_timestamp
    flag_values.deleted_on = expected_deleted_timestamp

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())

    result = command.Handle(expected_image)

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['image'], expected_image)
    self.assertEqual(result['body']['state'], expected_state)
    self.assertEqual(result['body']['replacement'],
                     command.NormalizeGlobalResourceName(
                         expected_project, 'images', expected_replacement))
    self.assertEqual(result['body']['obsolete'], expected_obsolete_timestamp)
    self.assertEqual(result['body']['deleted'], expected_deleted_timestamp)


if __name__ == '__main__':
  unittest.main()
