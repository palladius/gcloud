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

"""Commands for interacting with Google Compute Engine disk snapshots."""



import time


from google.apputils import appcommands
import gflags as flags

from gcutil import command_base
from gcutil import gcutil_logging


FLAGS = flags.FLAGS
LOGGER = gcutil_logging.LOGGER


class SnapshotCommand(command_base.GoogleComputeCommand):
  """Base command for working with the snapshots collection."""

  default_sort_field = 'name'
  summary_fields = (('name', 'name'),
                    ('description', 'description'),
                    ('creation-time', 'creationTimestamp'),
                    ('status', 'status'),
                    ('disk-size-gb', 'diskSizeGb'),
                    ('source-disk', 'sourceDisk'))

  detail_fields = (('name', 'name'),
                   ('description', 'description'),
                   ('creation-time', 'creationTimestamp'),
                   ('status', 'status'),
                   ('disk-size-gb', 'diskSizeGb'),
                   ('source-disk', 'sourceDisk'))

  resource_collection_name = 'snapshots'

  def __init__(self, name, flag_values):
    super(SnapshotCommand, self).__init__(name, flag_values)

  def SetApi(self, api):
    """Set the Google Compute Engine API for the command.

    Args:
      api: The Google Compute Engine API used by this command.

    Returns:
      None.

    """
    self._snapshots_api = api.snapshots()
    self._disks_api = api.disks()
    self._zones_api = api.zones()

  def _PrepareRequestArgs(self, snapshot_name, **other_args):
    """Gets the dictionary of API method keyword arguments.

    Args:
      snapshot_name: The name of the snapshot.
      **other_args: Keyword arguments that should be included in the request.

    Returns:
      Dictionary of keyword arguments that should be passed in the API call,
      includes all keyword arguments passed in 'other_args' plus
      common keys such as the name of the resource and the project.
    """

    kwargs = {
        'project': self._project,
        'snapshot': self.DenormalizeResourceName(snapshot_name)
    }
    for key, value in other_args.items():
      kwargs[key] = value
    return kwargs


class AddSnapshot(SnapshotCommand):
  """Create a new persistent disk snapshot."""

  positional_args = '<snapshot-name>'
  status_field = 'status'
  _TERMINAL_STATUS = ['READY', 'FAILED']

  def __init__(self, name, flag_values):
    super(AddSnapshot, self).__init__(name, flag_values)
    flags.DEFINE_string('description',
                        '',
                        'Snapshot description.',
                        flag_values=flag_values)
    flags.DEFINE_string('source_disk',
                        None,
                        'The source disk for this snapshot.',
                        flag_values=flag_values)
    flags.DEFINE_string('zone',
                        None,
                        'The zone of the disk.',
                        flag_values=flag_values)
    flags.DEFINE_boolean('wait_until_complete',
                         False,
                         'Whether the program should wait until the snapshot'
                         ' is complete.',
                         flag_values=flag_values)

  def Handle(self, snapshot_name):
    """Add the specified snapshot.

    Args:
      snapshot_name: The name of the snapshot to add

    Returns:
      The result of inserting the snapshot.
    """
    if not self._flags.source_disk:
      disk = self._PromptForDisk()
      if not disk:
        raise command_base.CommandError(
            'You cannot create a snapshot if you have no disks.')
      self._flags.source_disk = disk['name']

    zone = 'unused'
    if self._IsUsingAtLeastApiVersion('v1beta14'):
      zone = self.GetZoneForResource(self._disks_api, self._flags.source_disk)

    source_disk = self.NormalizePerZoneResourceName(
        self._project,
        zone,
        'disks',
        self._flags.source_disk)

    kwargs = {
        'project': self._project,
    }

    snapshot_resource = {
        'kind': self._GetResourceApiKind('snapshot'),
        'name': self.DenormalizeResourceName(snapshot_name),
        'description': self._flags.description,
        'sourceDisk': source_disk
        }

    kwargs['body'] = snapshot_resource
    snapshot_request = self._snapshots_api.insert(**kwargs)

    result = snapshot_request.execute()

    if self._flags.wait_until_complete:
      result = self.WaitForOperation(self._flags, time, result)
      if not result.get('error'):
        result = self._InternalGetSnapshot(snapshot_name)
        result = self._WaitUntilSnapshotIsComplete(result, snapshot_name)

    return result

  def _InternalGetSnapshot(self, snapshot_name):
    """A simple implementation of getting current snapshot state.

    Args:
      snapshot_name: the name of the snapshot to get.

    Returns:
      Json containing full snapshot information.
    """
    snapshot_request = self._snapshots_api.get(
        **self._PrepareRequestArgs(snapshot_name))
    return snapshot_request.execute()

  def _WaitUntilSnapshotIsComplete(self, result, snapshot_name):
    """Waits for the snapshot to complete.

    Periodically polls the server for current snapshot status. Exits if the
    status of the snapshot is READY or FAILED or the maximum waiting
    timeout has been reached. In both cases returns the last known snapshot
    details.

    Args:
      result: the current state of the snapshot.
      snapshot_name: the name of the snapshot to watch.

    Returns:
      Json containing full snapshot information.
    """
    current_status = result[self.status_field]
    start_time = time.time()
    LOGGER.info('Will wait for snapshot to complete for: %d seconds.',
                self._flags.max_wait_time)
    while (time.time() - start_time < self._flags.max_wait_time and
           current_status not in self._TERMINAL_STATUS):
      LOGGER.info(
          'Waiting for snapshot. Current status: %s. Sleeping for %ss.',
          current_status, self._flags.sleep_between_polls)
      time.sleep(self._flags.sleep_between_polls)
      result = self._InternalGetSnapshot(snapshot_name)
      current_status = result[self.status_field]
    if current_status not in self._TERMINAL_STATUS:
      LOGGER.warn('Timeout reached. Snapshot %s has not yet completed.',
                  snapshot_name)
    return result


class GetSnapshot(SnapshotCommand):
  """Get a machine snapshot."""

  positional_args = '<snapshot-name>'

  def __init__(self, name, flag_values):
    super(GetSnapshot, self).__init__(name, flag_values)

  def Handle(self, snapshot_name):
    """Get the specified snapshot.

    Args:
      snapshot_name: The name of the snapshot to get

    Returns:
      The result of getting the snapshot.
    """
    snapshot_request = self._snapshots_api.get(
        **self._PrepareRequestArgs(snapshot_name))

    return snapshot_request.execute()


class DeleteSnapshot(SnapshotCommand):
  """Delete one or more machine snapshots."""

  positional_args = '<snapshot-name>'
  safety_prompt = 'Delete snapshot'

  def __init__(self, name, flag_values):
    super(DeleteSnapshot, self).__init__(name, flag_values)

  def Handle(self, *snapshot_names):
    """Delete the specified snapshots.

    Args:
      *snapshot_names: The names of the snapshots to delete

    Returns:
      Tuple (results, exceptions) - results of deleting the snapshots.
    """
    requests = []
    for snapshot_name in snapshot_names:
      requests.append(self._snapshots_api.delete(
          **self._PrepareRequestArgs(snapshot_name)))
    results, exceptions = self.ExecuteRequests(requests)
    return self.MakeListResult(results, 'operationList'), exceptions


class ListSnapshots(SnapshotCommand, command_base.GoogleComputeListCommand):
  """List the machine snapshots for a project."""

  def ListFunc(self):
    """Returns the function for listing snapshots."""
    return self._snapshots_api.list


def AddCommands():
  appcommands.AddCmd('addsnapshot', AddSnapshot)
  appcommands.AddCmd('getsnapshot', GetSnapshot)
  appcommands.AddCmd('deletesnapshot', DeleteSnapshot)
  appcommands.AddCmd('listsnapshots', ListSnapshots)
