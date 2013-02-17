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

"""Unit tests for the kernel commands."""



import path_initializer
path_initializer.InitializeSysPath()

import copy

import gflags as flags
import unittest

from gcutil import kernel_cmds
from gcutil import mock_api

FLAGS = flags.FLAGS


class KernelCmdsTest(unittest.TestCase):

  def testGetKernelGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)

    command = kernel_cmds.GetKernel('getkernel', flag_values)

    expected_project = 'test_project'
    expected_kernel = 'test_kernel'
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())

    result = command.Handle(expected_kernel)

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['kernel'], expected_kernel)


if __name__ == '__main__':
  unittest.main()
