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

"""Contains a utility for initializing the system path."""



import os
import sys

def InitializeSysPath():
  """Adds gcutil's dependencies to sys.path.

  This function assumes that the site module has not been
  imported. The site module can be supressed by launching this program
  using python -S.
  """
  lib_dir = os.path.dirname(os.path.dirname(os.path.dirname(
      os.path.realpath(__file__))))
  libs = [os.path.join(lib_dir, lib) for lib in os.listdir(lib_dir)]

  # Removes entries from libs that are already on the path.
  libs = list(set(libs) - set(sys.path))

  sys.path = libs + sys.path
