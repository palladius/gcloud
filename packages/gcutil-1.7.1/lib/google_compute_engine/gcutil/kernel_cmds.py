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

"""Commands for interacting with Google Compute Engine installed kernels."""




from google.apputils import appcommands
import gflags as flags

from gcutil import command_base


FLAGS = flags.FLAGS



class KernelCommand(command_base.GoogleComputeCommand):
  """Base command for working with the kernels collection."""

  default_sort_field = 'name'
  summary_fields = (('name', 'name'),
                    ('description', 'description'))

  detail_fields = (('name', 'name'),
                   ('description', 'description'),
                   ('creation-time', 'creationTimestamp'))

  resource_collection_name = 'kernels'

  def __init__(self, name, flag_values):
    super(KernelCommand, self).__init__(name, flag_values)

  def SetApi(self, api):
    """Set the Google Compute Engine API for the command.

    Args:
      api: The Google Compute Engine API used by this command.

    Returns:
      None.

    """
    self._kernels_api = api.kernels()


class GetKernel(KernelCommand):
  """Get a kernel."""

  def __init__(self, name, flag_values):
    super(GetKernel, self).__init__(name, flag_values)

  def Handle(self, kernel_name):
    """Get the specified kernel.

    Args:
      kernel_name: The name of the kernel to get.

    Returns:
      The result of getting the kernel.
    """
    kernel_request = self._kernels_api.get(
        project=self._project,
        kernel=self.DenormalizeResourceName(kernel_name))

    return kernel_request.execute()


class ListKernels(KernelCommand, command_base.GoogleComputeListCommand):
  """List the kernels for a project."""

  def ListFunc(self):
    """Returns the fuction for listing kernels."""
    return self._kernels_api.list


def AddCommands():
  appcommands.AddCmd('getkernel', GetKernel)
  appcommands.AddCmd('listkernels', ListKernels)
