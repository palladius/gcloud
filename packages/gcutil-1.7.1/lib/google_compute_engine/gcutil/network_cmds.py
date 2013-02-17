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

"""Commands for interacting with Google Compute Engine VM networks."""





from google.apputils import appcommands
import gflags as flags

from gcutil import command_base


FLAGS = flags.FLAGS


class NetworkCommand(command_base.GoogleComputeCommand):
  """Base command for working with the networks collection."""

  default_sort_field = 'name'
  summary_fields = (('name', 'name'),
                    ('description', 'description'),
                    ('addresses', 'IPv4Range'),
                    ('gateway', 'gatewayIPv4'))

  detail_fields = (('name', 'name'),
                   ('description', 'description'),
                   ('creation-time', 'creationTimestamp'),
                   ('addresses', 'IPv4Range'),
                   ('gateway', 'gatewayIPv4'))

  resource_collection_name = 'networks'

  def __init__(self, name, flag_values):
    super(NetworkCommand, self).__init__(name, flag_values)

  def SetApi(self, api):
    """Set the Google Compute Engine API for the command.

    Args:
      api: The Google Compute Engine API used by this command.

    Returns:
      None.

    """
    self._networks_api = api.networks()


class AddNetwork(NetworkCommand):
  """Create a new network instance."""

  positional_args = '<network-name>'

  def __init__(self, name, flag_values):
    super(AddNetwork, self).__init__(name, flag_values)

    flags.DEFINE_string('description',
                        '',
                        'Network description.',
                        flag_values=flag_values)
    flags.DEFINE_string('range',
                        '10.0.0.0/8',
                        'IPv4 address range of this network.',
                        flag_values=flag_values)
    flags.DEFINE_string('gateway',
                        '10.0.0.1',
                        'IPv4 address of the gateway within the network.',
                        flag_values=flag_values)
    flags.DEFINE_list('reserve',
                      [],
                      'IPv4 addresses on the network which should not be '
                      'automatically assigned (comma separated).',
                      flag_values=flag_values)

  def Handle(self, network_name):
    """Add the specified network.

    Args:
      network_name: The name of the network to add.

    Returns:
      The result of adding the network.
    """
    network_resource = {
        'kind': self._GetResourceApiKind('network'),
        'name': self.DenormalizeResourceName(network_name),
        'description': self._flags.description,
        'IPv4Range': self._flags.range,
        'gatewayIPv4': self._flags.gateway,
        'reservedIPv4': self._flags.reserve,
        }

    network_request = self._networks_api.insert(project=self._project,
                                                body=network_resource)
    return network_request.execute()


class GetNetwork(NetworkCommand):
  """Get a network instance."""

  positional_args = '<network-name>'

  def __init__(self, name, flag_values):
    super(GetNetwork, self).__init__(name, flag_values)

  def Handle(self, network_name):
    """Get the specified network.

    Args:
      network_name: The name of the network to get.

    Returns:
      The result of getting the network.
    """
    network_request = self._networks_api.get(
        project=self._project,
        network=self.DenormalizeResourceName(network_name))

    return network_request.execute()


class DeleteNetwork(NetworkCommand):
  """Delete one or more machine networks.

  If multiple network names are specified, the networks will be deleted in
  parallel.
  """

  positional_args = '<network-name-1> ... <network-name-n>'
  safety_prompt = 'Delete network'

  def __init__(self, name, flag_values):
    super(DeleteNetwork, self).__init__(name, flag_values)

  def Handle(self, *network_names):
    """Delete the specified networks.

    Args:
      *network_names: The names of the networks to delete.

    Returns:
      Tuple (results, exceptions) - results of deleting the networks.
    """
    requests = []
    for name in network_names:
      requests.append(self._networks_api.delete(
          project=self._project,
          network=self.DenormalizeResourceName(name)))
    results, exceptions = self.ExecuteRequests(requests)
    return self.MakeListResult(results, 'operationList'), exceptions


class ListNetworks(NetworkCommand, command_base.GoogleComputeListCommand):
  """List the networks for a project."""

  def ListFunc(self):
    return self._networks_api.list


def AddCommands():
  appcommands.AddCmd('addnetwork', AddNetwork)
  appcommands.AddCmd('getnetwork', GetNetwork)
  appcommands.AddCmd('deletenetwork', DeleteNetwork)
  appcommands.AddCmd('listnetworks', ListNetworks)
