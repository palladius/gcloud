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

"""Commands for interacting with Google Compute Engine availability zones."""



import iso8601

from google.apputils import appcommands
import gflags as flags

from gcutil import command_base


FLAGS = flags.FLAGS


class ZoneCommand(command_base.GoogleComputeCommand):
  """Base command for working with the zones collection."""

  default_sort_field = 'name'
  summary_fields = (('name', 'name'),
                    ('description', 'description'),
                    ('status', 'status'),
                    ('next-maintenance-window', 'next_maintenance_window'))

  detail_fields = (('name', 'name'),
                   ('description', 'description'),
                   ('creation-time', 'creationTimestamp'),
                   ('status', 'status'))

  def SetApi(self, api):
    """Set the Google Compute Engine API for the command.

    Args:
      api: The Google Compute Engine API used by this command.

    Returns:
      None.
    """
    self._zones_api = api.zones()
    if self._IsUsingAtLeastApiVersion('v1beta14'):
      self.summary_fields = (
          ('name', 'name'),
          ('description', 'description'),
          ('status', 'status'),
          ('next-maintenance-window', 'next_maintenance_window'),
          ('instances-usage', 'instances'),
          ('cpus-usage', 'cpus'),
          ('disks-usage', 'disks'),
          ('disks-total-gb-usage', 'disks_total_gb'))


class GetZone(ZoneCommand):
  """Get a zone."""

  positional_args = '<zone-name>'

  def CustomizePrintResult(self, result, table):
    """Customized result printing for this type.

    Args:
      result: json dictionary returned by the server
      table: the pretty printing table to be customized

    Returns:
      None.

    """
    # Add machine types
    for (i, m) in enumerate(result.get('availableMachineType', [])):
      key = ''
      if i == 0:
        key = 'machine types'
      table.AddRow((key, self._PresentElement(m)))
    # Add the maintenance windows
    table.AddRow(('maintenance-windows', ''))
    for window in result.get('maintenanceWindows', []):
      table.AddRow(('', ''))
      table.AddRow(('  name', window['name']))
      table.AddRow(('  description', window['description']))
      table.AddRow(('  begin-time', window['beginTime']))
      table.AddRow(('  end-time', window['endTime']))
    # Add the zone quotas
    table.AddRow(('', ''))
    table.AddRow(('usage', ''))
    for quota in result.get('quotas', []):
      table.AddRow(('  %s' % quota['metric'].lower().replace('_', '-'),
                    '%s/%s' % (str(quota['usage']), str(quota['limit']))))

  def Handle(self, zone_name):
    """Get the specified zone.

    Args:
      zone_name: Path of the zone to get.

    Returns:
      The result of getting the zone.
    """
    request = self._zones_api.get(project=self._project, zone=zone_name)
    return request.execute()


class ListZones(ZoneCommand, command_base.GoogleComputeListCommand):
  """List available zones for a project."""

  def ListFunc(self):
    return self._zones_api.list

  def Handle(self):
    """List the project's zones."""
    result = super(ListZones, self).Handle()
    items = result.get('items', [])

    # Add the next maintenance window start time to each entry.
    for zone in items:
      next_iso = None
      next_str = 'None scheduled'

      for window in zone.get('maintenanceWindows', []):
        begin_str = window['beginTime']
        begin_iso = iso8601.parse_date(begin_str)
        if next_iso is None or begin_iso < next_iso:
          next_iso = begin_iso
          next_str = begin_str

      zone['next_maintenance_window'] = next_str

      for quota in zone.get('quotas', []):
        column_name = quota['metric'].lower()
        zone[column_name] = (
            '%s/%s' % (str(quota['usage']), str(quota['limit'])))

    return result


def AddCommands():
  appcommands.AddCmd('getzone', GetZone)
  appcommands.AddCmd('listzones', ListZones)
