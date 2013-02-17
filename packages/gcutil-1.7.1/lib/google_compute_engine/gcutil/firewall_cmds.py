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

"""Commands for interacting with Google Compute Engine firewalls."""



import socket

from google.apputils import appcommands
import gflags as flags

from gcutil import command_base
from gcutil import utils


FLAGS = flags.FLAGS


class FirewallCommand(command_base.GoogleComputeCommand):
  """Base command for working with the firewalls collection."""

  default_sort_field = 'name'
  summary_fields = (('name', 'name'),
                    ('description', 'description'),
                    ('network', 'network'),
                    ('source-ips', 'sourceRanges'),
                    ('source-tags', 'sourceTags'),
                    ('target-tags', 'targetTags'))

  # The remaining complex fields are filled in via CustomizePrintResult
  detail_fields = (('name', 'name'),
                   ('description', 'description'),
                   ('creation-time', 'creationTimestamp'),
                   ('network', 'network'),
                   ('source-ips', 'sourceRanges'),
                   ('source-tags', 'sourceTags'),
                   ('target-tags', 'targetTags'))

  resource_collection_name = 'firewalls'

  def __init__(self, name, flag_values):
    super(FirewallCommand, self).__init__(name, flag_values)

  def SetApi(self, api):
    """Set the Google Compute Engine API for the command.

    Args:
      api: The Google Compute Engine API used by this command.

    Returns:
      None.

    """
    self._firewalls_api = api.firewalls()

  def CustomizePrintResult(self, result, table):
    """Customized result printing for this type.

    Args:
      result: json dictionary returned by the server
      table: the pretty printing table to be customized

    Returns:
      None.

    """
    # Add the rules
    for allowed in result.get('allowed', []):
      as_string = str(allowed['IPProtocol'])
      if allowed.get('ports'):
        as_string += ': %s' % ', '.join(allowed['ports'])
      table.AddRow(('allowed', as_string))


class FirewallRules(object):
  """Class representing the list of a firewall's rules.

  This class is only used for parsing a firewall from command-line flags,
  for printing the firewall, we simply dump the JSON.
  """

  @staticmethod
  def ParsePortSpecs(port_spec_strings):
    """Parse the port-specification portion of firewall rules.

    This takes the value of the 'allowed' flag and builds the
    corresponding firewall rules, excluding the 'source' fields.

    Args:
      port_spec_strings: A list of strings specifying the port-specific
      components of a firewall rule. These are of the form
      "(<protocol>)?(:<port>('-'<port>)?)?"

    Returns:
      A list of dict values containing a protocol string and a list
      of port range strings. This is a substructure of the firewall
      rule dictionaries, which additionally contain a 'source' field.

    Raises:
      ValueError: If any of the input strings are malformed.
    """

    def _AddToPortSpecs(protocol, port_string, port_specs):
      """Ensure the specified rule for this protocol allows the given port(s).

      If there is no port_string specified it implies all ports are allowed,
      and whatever is in the port_specs map for that protocol get clobbered.
      This method also makes sure that any protocol entry without a ports
      member does not get further restricted.

      Args:
        protocol: The protocol under which the given port range is allowed.
        port_string: The string specification of what ports are allowed.
        port_specs: The mapping from protocols to firewall rules.
      """
      port_spec_entry = port_specs.setdefault(protocol,
                                              {'IPProtocol': str(protocol),
                                               'ports': []})
      if 'ports' in port_spec_entry:
        # We only handle the 'then' case because in the other case the
        # existing entry already allows all ports.
        if not port_string:
          # A missing 'ports' field indicates all ports are allowed.
          port_spec_entry.pop('ports')
        else:
          port_spec_entry['ports'].append(port_string)

    port_specs = {}
    for port_spec_string in port_spec_strings:
      protocol = None
      port_string = None
      parts = port_spec_string.split(':')

      if len(parts) > 2:
        raise ValueError('Invalid allowed entry: %s' %
                         port_spec_string)
      elif len(parts) == 2:
        if parts[0]:
          protocol = utils.ParseProtocol(parts[0])
        port_string = utils.ReplacePortNames(parts[1])
      else:
        protocol = utils.ParseProtocol(parts[0])

      if protocol:
        _AddToPortSpecs(protocol, port_string, port_specs)
      else:
        # Add entries for both UPD and TCP
        _AddToPortSpecs(socket.getprotobyname('tcp'), port_string, port_specs)
        _AddToPortSpecs(socket.getprotobyname('udp'), port_string, port_specs)

    return port_specs.values()

  def __init__(self, allowed, allowed_ip_sources):
    self.port_specs = FirewallRules.ParsePortSpecs(allowed)
    self.source_ranges = allowed_ip_sources
    self.source_tags = []
    self.target_tags = []

  def SetTags(self, source_tags, target_tags):
    self.source_tags = sorted(set(source_tags))
    self.target_tags = sorted(set(target_tags))

  def AddToFirewall(self, firewall):
    if self.source_ranges:
      firewall['sourceRanges'] = self.source_ranges
    if self.source_tags:
      firewall['sourceTags'] = self.source_tags
    if self.target_tags:
      firewall['targetTags'] = self.target_tags
    firewall['allowed'] = self.port_specs


class AddFirewall(FirewallCommand):
  """Create a new firewall rule to allow incoming traffic for
  instances on a given network.
  """

  positional_args = '<firewall-name>'

  def __init__(self, name, flag_values):
    super(AddFirewall, self).__init__(name, flag_values)
    flags.DEFINE_string('description',
                        '',
                        'Firewall description',
                        flag_values=flag_values)
    flags.DEFINE_string('network',
                        'default',
                        'Which network to apply the firewall to.',
                        flag_values=flag_values)
    flags.DEFINE_list('allowed',
                      None,
                      'The set of allowed ports for this firewall. A list of '
                      'specifications of the form '
                      '"(<protocol>)?(\':\'<port>(\'-\'<port>)?)?" for allowing'
                      ' packets through the firewall. Examples: '
                      '"tcp:ssh", "udp:5000-6000", "tcp:80", or "icmp".',
                      flag_values=flag_values)
    flags.DEFINE_list('allowed_ip_sources',
                      [],
                      'The set of addresses allowed to talk to the '
                      'protocols:ports listed in allowed (comma separated). '
                      'If no ip or tag sources are listed, all sources '
                      'will be allowed.',
                      flag_values=flag_values)
    flags.DEFINE_list('allowed_tag_sources',
                      [],
                      'The set of tagged instances allowed to talk to the '
                      'protocols:ports listed in allowed (comma separated). '
                      'If no tag or ip sources are listed, all sources will '
                      'be allowed.',
                      flag_values=flag_values)
    flags.DEFINE_list('target_tags',
                      [],
                      'The set of tagged instances to apply the firewall to '
                      '(comma separated).',
                      flag_values=flag_values)

  def Handle(self, firewall_name):
    """Add the specified firewall.

    Args:
      firewall_name: The name of the firewall to add.

    Returns:
      The result of inserting the firewall.

    Raises:
      command_base.CommandError: If the passed flag values cannot be
          interpreted.
    """
    if not self._flags.allowed:
      raise command_base.CommandError(
          'You must specify at least one rule through --allowed.')

    firewall_resource = {
        'kind': self._GetResourceApiKind('firewall'),
        'name': self.DenormalizeResourceName(firewall_name),
        'description': self._flags.description,
        'rules': []
        }

    if self._flags.network is not None:
      firewall_resource['network'] = (self.NormalizeGlobalResourceName(
          self._project,
          'networks',
          self._flags.network))

    if (not self._flags.allowed_ip_sources and
        not self._flags.allowed_tag_sources):
      self._flags.allowed_ip_sources.append('0.0.0.0/0')

    try:
      firewall_rules = FirewallRules(self._flags.allowed,
                                     self._flags.allowed_ip_sources)
      firewall_rules.SetTags(self._flags.allowed_tag_sources,
                             self._flags.target_tags)
      firewall_rules.AddToFirewall(firewall_resource)
      firewall_request = self._firewalls_api.insert(project=self._project,
                                                    body=firewall_resource)
      return firewall_request.execute()
    except ValueError, e:
      raise command_base.CommandError(e)


class GetFirewall(FirewallCommand):
  """Get a firewall."""

  positional_args = '<firewall-name>'

  def __init__(self, name, flag_values):
    super(GetFirewall, self).__init__(name, flag_values)

  def Handle(self, firewall_name):
    """Get the specified firewall.

    Args:
      firewall_name: The name of the firewall to get.

    Returns:
      The result of getting the firewall.
    """
    firewall_request = self._firewalls_api.get(
        project=self._project,
        firewall=self.DenormalizeResourceName(firewall_name))

    return firewall_request.execute()


class DeleteFirewall(FirewallCommand):
  """Delete one or more firewall rules.

  If multiple firewall names are specified, the firewalls will be deleted in
  parallel.
  """

  positional_args = '<firewall-name-1> ... <firewall-name-n>'
  safety_prompt = 'Delete firewall'

  def __init__(self, name, flag_values):
    super(DeleteFirewall, self).__init__(name, flag_values)

  def Handle(self, *firewall_names):
    """Delete the specified firewall.

    Args:
      *firewall_names: The names of the firewalls to delete.

    Returns:
      Tuple (results, exceptions) - results of deleting the firewalls.
    """
    requests = []
    for name in firewall_names:
      requests.append(self._firewalls_api.delete(
          project=self._project,
          firewall=self.DenormalizeResourceName(name)))
    results, exceptions = self.ExecuteRequests(requests)
    return (self.MakeListResult(results, 'operationList'), exceptions)


class ListFirewalls(FirewallCommand, command_base.GoogleComputeListCommand):
  """List the firewall rules for a project."""

  def ListFunc(self):
    """Returns the function for listing firewalls."""
    return self._firewalls_api.list


def AddCommands():
  appcommands.AddCmd('addfirewall', AddFirewall)
  appcommands.AddCmd('getfirewall', GetFirewall)
  appcommands.AddCmd('deletefirewall', DeleteFirewall)
  appcommands.AddCmd('listfirewalls', ListFirewalls)
