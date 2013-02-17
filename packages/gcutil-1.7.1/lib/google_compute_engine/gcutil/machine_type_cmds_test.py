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

"""Unit tests for the machine type commands."""



import path_initializer
path_initializer.InitializeSysPath()

import copy

import gflags as flags
import unittest

from gcutil import command_base
from gcutil import machine_type_cmds

try:
  from gcutil import mock_api
except ImportError:
  import mock_api

FLAGS = flags.FLAGS


class MachineTypeCmdsTest(unittest.TestCase):

  def testGetMachineTypeGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)

    command = machine_type_cmds.GetMachineType('getmachinetype', flag_values)

    expected_machine_type = 'test_machine_type'
    flag_values.service_version = command_base.CURRENT_VERSION

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())

    result = command.Handle(expected_machine_type)

    self.assertEqual(result['machineType'], expected_machine_type)


if __name__ == '__main__':
  unittest.main()
