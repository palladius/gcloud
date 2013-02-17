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

"""Commands for interacting with Google Compute Engine operations."""



from google.apputils import appcommands
import gflags as flags

from gcutil import command_base


FLAGS = flags.FLAGS


class OperationCommand(command_base.GoogleComputeCommand):
  """Base command for working with the operations collection.

  Attributes:
    default_sort_field: The json field name used to sort list output for the
        command.
    summary_fields: A set of tuples of (json field name, human
        readable name) used to generate a pretty-printed summary description
        of a list of operation resources.
    detail_fields: A set of tuples of (json field name, human
        readable name) used to generate a pretty-printed detailed description
        of an operation resource.
    resource_collection_name: The name of the REST API collection handled by
        this command type.
  """

  default_sort_field = (
      command_base.GoogleComputeCommand.operation_default_sort_field)
  summary_fields = command_base.GoogleComputeCommand.operation_summary_fields
  detail_fields = command_base.GoogleComputeCommand.operation_detail_fields

  resource_collection_name = 'operations'

  def __init__(self, name, flag_values):
    super(OperationCommand, self).__init__(name, flag_values)
    flags.DEFINE_string('zone',
                        None,
                        'The name of the operation zone or \'%s\' for global '
                        'operations.' % command_base.GLOBAL_ZONE_NAME,
                        flag_values=flag_values)

  def SetApi(self, api):
    """Set the Google Compute Engine API for the command.

    Args:
      api: The Google Compute Engine API used by this command.
    """
    self._zones_api = api.zones()

    if self._IsUsingAtLeastApiVersion('v1beta14'):
      self._zone_operations_api = api.zoneOperations()
      self._global_operations_api = api.globalOperations()
    else:
      self._global_operations_api = api.operations()

  def _PrepareRequestArgs(self, operation_name, **other_args):
    """Gets the dictionary of API method keyword arguments.

    Args:
      operation_name: The name of the operation.
      **other_args: Keyword arguments that should be included in the request.

    Returns:
      Dictionary of keyword arguments that should be passed in the API call,
      includes all keyword arguments passed in 'other_args' plus
      common keys such as the name of the resource and the project.
    """

    kwargs = {
        'project': self._project,
        'operation': self.DenormalizeResourceName(operation_name)
    }
    if self._IsUsingAtLeastApiVersion('v1beta14'):
      if self._flags.zone != command_base.GLOBAL_ZONE_NAME:
        kwargs['zone'] = self._flags.zone
    for key, value in other_args.items():
      kwargs[key] = value
    return kwargs


class GetOperation(OperationCommand):
  """Retrieve an operation resource."""

  positional_args = '<operation-name>'

  def Handle(self, operation_name):
    """Get the specified operation.

    Args:
      operation_name: The name of the operation to get.

    Returns:
      The json formatted object resulting from retrieving the operation
      resource.
    """
    # Force asynchronous mode so the caller doesn't wait for this operation
    # to complete before returning.
    self._flags.synchronous_mode = False

    kwargs = self._PrepareRequestArgs(operation_name)
    method = self._global_operations_api.get

    if self._IsUsingAtLeastApiVersion('v1beta14') and 'zone' in kwargs:
      method = self._zone_operations_api.get

    request = method(**kwargs)
    return request.execute()


class DeleteOperation(OperationCommand):
  """Delete one or more operations."""

  positional_args = '<operation-name-1> ... <operation-name-n>'
  safety_prompt = 'Delete operation'

  def Handle(self, *operation_names):
    """Delete the specified operations.

    Args:
      *operation_names: The names of the operations to delete.

    Returns:
      Tuple (results, exceptions) - results of deleting the operations.
    """
    requests = []
    for operation_name in operation_names:
      kwargs = self._PrepareRequestArgs(operation_name)
      method = self._global_operations_api.delete
      if self._IsUsingAtLeastApiVersion('v1beta14') and 'zone' in kwargs:
        method = self._zone_operations_api.delete
      requests.append(method(**kwargs))

    _, exceptions = self.ExecuteRequests(requests)
    return '', exceptions


class ListOperations(OperationCommand, command_base.GoogleComputeListCommand):
  """List the operations for a project."""

  is_global_level_collection = True
  is_zone_level_collection = True

  def __init__(self, name, flag_values):
    super(OperationCommand, self).__init__(name, flag_values)
    flags.DEFINE_string('zone',
                        None,
                        'The zone to list.',
                        flag_values=flag_values)

  def ListFunc(self):
    """Returns the function for listing global operations."""
    return self._global_operations_api.list

  def ListZoneFunc(self):
    """Returns the function for listing operations in a zone."""
    if self._IsUsingAtLeastApiVersion('v1beta14'):
      return self._zone_operations_api.list
    return self._global_operations_api.list


def AddCommands():
  appcommands.AddCmd('getoperation', GetOperation)
  appcommands.AddCmd('deleteoperation', DeleteOperation)
  appcommands.AddCmd('listoperations', ListOperations)
