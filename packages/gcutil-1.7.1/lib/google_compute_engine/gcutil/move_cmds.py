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

"""Commands for moving resources from one zone to another."""



import collections
import datetime
import json
import os
import textwrap
import time
import uuid

from google.apputils import app
from google.apputils import appcommands
import gflags as flags

from gcutil import command_base
from gcutil import gcutil_logging
from gcutil import utils
from gcutil import version


LOGGER = gcutil_logging.LOGGER

MAX_INSTANCES_TO_MOVE = 100
MAX_DISKS_TO_MOVE = 100


class MoveInstancesBase(command_base.GoogleComputeCommand):
  """The base class for the move commands."""

  def __init__(self, name, flag_values):
    super(MoveInstancesBase, self).__init__(name, flag_values)

    flags.DEFINE_boolean(
        'force',
        False,
        'Override the confirmation prompt.',
        flag_values=flag_values)

    flags.DEFINE_boolean(
        'keep_snapshots',
        False,
        'Do not delete snapshots that were created for the disks.',
        flag_values=flag_values)

  def SetApi(self, api):
    self._disks_api = api.disks()
    self._instances_api = api.instances()
    self._machine_type_api = api.machineTypes()
    self._projects_api = api.projects()
    self._snapshots_api = api.snapshots()
    self._zones_api = api.zones()

  def Handle(self, *args, **kwargs):
    """The point of entry to the command.

    This dispatches the subclass' HandleMove method.

    Raises:
      UsageError: If the service version is not v1beta14 or higher.
        The dependency on the version is due to the fact that
        snapshots were introduced in v1beta14.
    """
    if not self._IsUsingAtLeastApiVersion('v1beta14'):
      raise app.UsageError(
          'This command requires using API version v1beta14 or higher.')
    self._project_resource = self._projects_api.get(
        project=self._project).execute()
    self.HandleMove(*args, **kwargs)
    print 'The move completed successfully.'

  def _Confirm(self, instances_to_mv, instances_to_ignore, disks_to_mv,
               dest_zone):
    """Displays what is about to happen and prompts the user to proceed.

    Args:
      instances_to_mv: The instances that will be moved.
      instances_to_ignore: Instances that will not be moved because they're
        already in the destination zone.
      disks_to_mv: A list of the disk names that will be moved.
      dest_zone: The destination zone.

     Raises:
       CommandError: If the user declines to proceed.
    """
    # Ensures that the parameters make sense.
    assert instances_to_mv, (
        'Cannot confirm move if there are no instances to move.')
    assert not [i for i in instances_to_mv if i['zone'].endswith(dest_zone)], (
        'Some instances in the move set are already in the destination zone.')
    assert ([i for i in instances_to_ignore if i['zone'].endswith(dest_zone)] ==
            instances_to_ignore), (
                'Not all instances in ignore set are in destination zone.')

    if instances_to_ignore:
      print ('These instances are already in %s and will not be moved:' %
             dest_zone)
      print utils.ListStrings(i['name'] for i in instances_to_ignore)

    print 'The following instances will be moved to %s:' % dest_zone
    print utils.ListStrings(i['name'] for i in instances_to_mv)

    if disks_to_mv:
      print 'The following disks will be moved to %s:' % dest_zone
      print utils.ListStrings(disks_to_mv)

    if not self._flags.force and not utils.Proceed():
      raise command_base.CommandError('Move aborted.')

  def _DeleteInstances(self, instances, zone):
    """Deletes the given instances.

    Args:
      instances: A list of instance resources.
      zone: The zone to which the instances belong.

    Raises:
      CommandError: If one or more of the deletions fail.
    """
    if not instances:
      return

    print 'Deleting instances...'
    requests = []
    for instance in instances:
      requests.append(self._instances_api.delete(
          project=self._project,
          zone=zone,
          instance=instance['name']))
    results, exceptions = self.ExecuteRequests(
        requests, collection_name='instances')
    if exceptions:
      raise command_base.CommandError(
          'Aborting due to errors while deleting instances:\n%s' %
          utils.ListStrings(exceptions))
    self._CheckForErrorsInOps(self.MakeListResult(results, 'operationList'))

  def _CreateInstances(self, instances, src_zone, dest_zone):
    """Creates the instance resources in the given list in dest_zone.

    The instance resources are changed in two ways:
      (1) Their zone fields are changed to dest_zone; and
      (2) Their ephemeral IPs are cleared.

    Args:
      instances: A list of instance resources.
      src_zone: The zone to which the instances belong.
      dest_zone: The destination zone.

    Raises:
      CommandError: If one or more of the insertions fail.
    """
    if not instances:
      return

    print 'Recreating instances in %s...' % dest_zone
    ip_addresses = set(self._project_resource.get('externalIpAddresses', []))
    self._SetIps(instances, ip_addresses)

    requests = []
    for instance in instances:
      instance['zone'] = self.NormalizeTopLevelResourceName(
          self._project, 'zones', dest_zone)

      # Replaces the zones for the persistent disks.
      for disk in instance['disks']:
        if 'source' in disk:
          disk['source'] = disk['source'].replace(
              'zones/' + src_zone, 'zones/' + dest_zone)

      requests.append(self._instances_api.insert(
          project=self._project, body=instance, zone=dest_zone))
    results, exceptions = self.ExecuteRequests(
        requests, collection_name='instances')
    if exceptions:
      raise command_base.CommandError(
          'Aborting due to errors while creating instances:\n%s' %
          utils.ListStrings(exceptions))
    self._CheckForErrorsInOps(self.MakeListResult(results, 'operationList'))

  def _CheckForErrorsInOps(self, results):
    """Raises CommandError if any operations in results contains an error."""
    _, ops = self._PartitionResults(results)
    errors = []
    for op in (ops or []):
      if 'error' in op and 'errors' in op['error'] and op['error']['errors']:
        error = op['error']['errors'][0].get('message')
        if error:
          errors.append(error)
    if errors:
      raise command_base.CommandError(
          'Encountered errors:\n%s' % utils.ListStrings(errors))

  def _SetIps(self, instances, ip_addresses):
    """Clears the natIP field for instances without reserved addresses."""
    for instance in instances:
      for interface in instance.get('networkInterfaces', []):
        for config in interface.get('accessConfigs', []):
          if 'natIP' in config and config['natIP'] not in ip_addresses:
            config['natIP'] = None

  def _WaitForSnapshots(self, snapshots):
    """Waits for the given snapshots to be in the READY state."""
    snapshots = set(snapshots)
    start_sec = time.time()
    while True:
      if time.time() - start_sec > self._flags.max_wait_time:
        raise command_base.CommandError(
            'Timeout reached while waiting for snapshots to be ready.')

      all_snapshots = [
          s for s in utils.All(self._snapshots_api.list, self._project)['items']
          if s['name'] in snapshots and s['status'] != 'READY']
      if not all_snapshots:
        break
      LOGGER.info('Waiting for snapshots to be READY. Sleeping for %ss' %
                  self._flags.sleep_between_polls)
      time.sleep(self._flags.sleep_between_polls)

  def _CreateSnapshots(self, snapshot_mappings, src_zone, dest_zone):
    """Creates snapshots for the disks to be moved.

    Args:
      snapshot_mappings: A map of disk names that should be moved to
        the names that should be used for each disk's snapshot.
      src_zone: The source zone. All disks in snapshot_mappings must be
        in this zone.
      dest_zone: The zone the disks are destined for.
    """
    if not snapshot_mappings:
      return

    print 'Snapshotting disks...'
    requests = []
    for disk_name, snapshot_name in snapshot_mappings.iteritems():
      snapshot_resource = {
          'name': snapshot_name,
          'sourceDisk': self.NormalizePerZoneResourceName(
              self._project, src_zone, 'disks', disk_name),
          'description': ('Snapshot for moving disk %s from %s to %s.' %
                          (disk_name, src_zone, dest_zone))}
      requests.append(self._snapshots_api.insert(
          project=self._project, body=snapshot_resource))

    results, exceptions = self.ExecuteRequests(
        requests, collection_name='snapshots')
    if exceptions:
      raise command_base.CommandError(
          'Aborting due to errors while creating snapshots:\n%s' %
          utils.ListStrings(exceptions))
    self._CheckForErrorsInOps(self.MakeListResult(results, 'operationList'))
    self._WaitForSnapshots(snapshot_mappings.values())

  def _DeleteSnapshots(self, snapshot_names, zone):
    """Deletes the given snapshots.

    Args:
      snapshot_names: A list of snapshot names to delete.
      zone: The zones to which the snapshots belong.
    """
    if not snapshot_names or self._flags.keep_snapshots:
      return

    print 'Deleting snapshots...'
    requests = []
    for name in snapshot_names:
      requests.append(self._snapshots_api.delete(
          project=self._project, snapshot=name))

    results, exceptions = self.ExecuteRequests(
        requests, collection_name='snapshots')
    if exceptions:
      raise command_base.CommandError(
          'Aborting due to errors while deleting snapshots:\n%s' %
          utils.ListStrings(exceptions))
    self._CheckForErrorsInOps(self.MakeListResult(results, 'operationList'))

  def _CreateDisksFromSnapshots(self, snapshot_mappings, dest_zone):
    """Creates disks in the destination zone from the given snapshots.

    Args:
      snapshot_mappings: A dict of disk names to snapshot names. Disks are
        created in the destination zone from the given snapshot names. The
        disks will assume their previous names as indicated by the key-value
        pairs.
      dest_zone: The zone in which the disks will be created.
    """
    if not snapshot_mappings:
      return

    print 'Recreating disks from snapshots...'
    requests = []
    for disk_name, snapshot_name in snapshot_mappings.iteritems():
      disk_resource = {
          'name': disk_name,
          'sourceSnapshot': self.NormalizeGlobalResourceName(
              self._project, 'snapshots', snapshot_name)}
      requests.append(self._disks_api.insert(
          project=self._project, body=disk_resource, zone=dest_zone))

    results, exceptions = self.ExecuteRequests(
        requests, collection_name='disks')
    if exceptions:
      raise command_base.CommandError(
          'Aborting due to errors while re-creating disks:\n%s' %
          utils.ListStrings(exceptions))
    self._CheckForErrorsInOps(self.MakeListResult(results, 'operationList'))

  def _DeleteDisks(self, disk_names, zone):
    """Deletes the given disks.

    Args:
      disk_names: A list of disk names to delete.
      zone: The zone to which the disks belong.
    """
    if not disk_names:
      return

    print 'Deleting disks...'
    requests = []
    for name in disk_names:
      requests.append(self._disks_api.delete(
          project=self._project, disk=name, zone=zone))

    results, exceptions = self.ExecuteRequests(
        requests, collection_name='disks')
    if exceptions:
      raise command_base.CommandError(
          'Aborting due to errors while deleting disks:\n%s' %
          utils.ListStrings(exceptions))
    self._CheckForErrorsInOps(self.MakeListResult(results, 'operationList'))

  def _CalculateNumCpus(self, instances_to_mv):
    """Calculates the amount of CPUs used by the given instances."""
    machines = utils.All(
        self._machine_type_api.list,
        self._project)['items']
    num_cpus = dict((m['selfLink'], m['guestCpus']) for m in machines)
    return sum(float(num_cpus[i['machineType']]) for i in instances_to_mv)

  def _CalculateTotalDisksSizeGb(self, disk_names, zone):
    """Calculates the total size of the given disks."""
    disk_names = set(disk_names)
    disks = utils.All(
        self._disks_api.list,
        self._project,
        zone=zone)['items']
    disk_sizes = [float(d['sizeGb']) for d in disks if d['name'] in disk_names]
    return sum(disk_sizes)

  def _CreateQuotaRequirementsDict(self, instances_to_mv, disks_to_mv,
                                   src_zone, snapshots_to_create=None):
    """Generates a mapping between resource type to the quota required."""
    return {'INSTANCES': len(instances_to_mv),
            'CPUS': self._CalculateNumCpus(instances_to_mv),
            'DISKS': len(disks_to_mv),
            'DISKS_TOTAL_GB': self._CalculateTotalDisksSizeGb(
                disks_to_mv, src_zone),
            'SNAPSHOTS': (len(snapshots_to_create)
                          if snapshots_to_create is not None
                          else len(disks_to_mv))}

  def _CheckQuotas(self, instances_to_mv, disks_to_mv, src_zone, dest_zone,
                   snapshots_to_create=None):
    """Raises a CommandError if the quota to perform the move does not exist."""
    print 'Checking project and destination zone quotas...'

    dest_zone_resource = self._zones_api.get(
        project=self._project, zone=dest_zone).execute()
    requirements = self._CreateQuotaRequirementsDict(
        instances_to_mv, disks_to_mv, src_zone,
        snapshots_to_create=snapshots_to_create)
    available = self._ExtractAvailableQuota(
        self._project_resource.get('quotas', []),
        dest_zone_resource.get('quotas', []), requirements)

    LOGGER.debug('Required quota for move is: %s', requirements)
    LOGGER.debug('Available quota is: %s', available)

    for metric, required in requirements.iteritems():
      if available.get(metric, 0) - required < 0:
        raise command_base.CommandError(
            'You do not have enough quota for %s in %s or your project.' % (
                metric, dest_zone))

  def _ExtractAvailableQuota(self, project_quota, zone_quota, requirements):
    """Extracts the required quota from the given project and zone resources.

    Args:
      project_quota: The list of project quotas that's included in a project
        resource.
      zone_quota: The list of zone quotas that's included in a zone resource.
      requirements: A dict mapping resource type to the amount of required
        quota.

    Returns:
      A mapping of available quota for INSTANCES, CPUS, DISKS, DISKS_TOTAL_GB,
      and SNAPSHOTS. The value can be negative if enough quota does not exist.
    """
    pertinent_resources = set(requirements.keys())
    available = {}

    for quota in project_quota:
      metric = quota.get('metric')
      if metric in pertinent_resources:
        available[metric] = quota.get('limit') - quota.get('usage')
        # For existing resources that are to be moved (i.e.,
        # everything in requirements except snapshots since they do
        # not exist yet) since they do not exist yet) we must count
        # them into the available number since they will be deleted
        # shortly.
        if metric != 'SNAPSHOTS':
          available[metric] += requirements[metric]

    for quota in zone_quota:
      metric = quota.get('metric')
      if metric in pertinent_resources:
        available[metric] = min(available[metric],
                                quota.get('limit') - quota.get('usage'))

    return available


class MoveInstances(MoveInstancesBase):
  """Move a set of instances from one zone to another zone.

  This command also moves any persistent disks that are attached to
  the instances.

  During the move, do not modify your project, as changes to the
  project may interfere with the move.

  In case of failure, use the gcutil resumemove command to re-attempt
  the move.

  You can pick which instances to move by specifying a series regular
  expressions that will be used to match instance names in the source
  zone. For example, the following command will move all instances in
  zone-a whose names match the regular expressions i-[0-9] or b-.* to
  zone-b:

    gcutil moveinstances \
      --source_zone=zone-a \
      --destination_zone=zone-b \
      "i-[0-9]" "b-.*"

  WARNING: Instances that are moved will lose ALL of their ephemeral
  state (i.e., ephemeral disks, ephemeral IP addresses, and memory).
  """

  positional_args = '<name-regex-1> ... <name-regex-n>'

  def __init__(self, name, flag_values):
    """Constructs a new MoveInstances object."""
    super(MoveInstances, self).__init__(name, flag_values)

    flags.DEFINE_string(
        'source_zone',
        None,
        'The source zone from which instances will be moved.',
        flag_values=flag_values)
    flags.DEFINE_string(
        'destination_zone',
        None,
        'The zone to which the instances should be moved.',
        flag_values=flag_values)

  def _ValidateFlags(self):
    """Raises a UsageError if there is any problem with the flags."""
    if not self._flags.source_zone:
      raise app.UsageError(
          'You must specify a source zone through the --source_zone flag.')
    if not self._flags.destination_zone:
      raise app.UsageError('You must specify a destination zone '
                           'through the --destination_zone flag.')
    if self._flags.source_zone == self._flags.destination_zone:
      raise app.UsageError('The destination and source zones cannot be equal.')

  def HandleMove(self, *instance_regexes):
    """Handles the actual move.

    Args:
      *instance_regexes: The sequence of name regular expressions used
        for filtering.
    """
    self._ValidateFlags()

    if not instance_regexes:
      raise app.UsageError(
          'You must specify at least one regex for instances to move.')

    self._flags.destination_zone = self.DenormalizeResourceName(
        self._flags.destination_zone)
    self._CheckDestinationZone()

    print 'Retrieving instances in %s matching: %s...' % (
        self._flags.source_zone, ' '.join(instance_regexes))
    instances_to_mv = utils.All(
        self._instances_api.list,
        self._project,
        filter=utils.RegexesToFilterExpression(instance_regexes),
        zone=self._flags.source_zone)['items']
    instances_in_dest = utils.All(
        self._instances_api.list,
        self._project,
        filter=utils.RegexesToFilterExpression(instance_regexes),
        zone=self._flags.destination_zone)['items']

    self._CheckInstancePreconditions(instances_to_mv, instances_in_dest)

    instances_to_ignore = utils.All(
        self._instances_api.list,
        self._project,
        filter=utils.RegexesToFilterExpression(instance_regexes, op='ne'),
        zone=self._flags.source_zone)['items']

    print 'Checking disk preconditions...'
    disks_to_mv = self._GetPersistentDiskNames(instances_to_mv)
    self._CheckDiskPreconditions(instances_to_ignore, disks_to_mv)
    # At this point, all disks in use by instances_to_mv are only
    # attached to instances in the set instances_to_mv.

    # Check the snapshots quota and the quota in the destination zone
    # to make sure that enough quota exists to support the move.
    self._CheckQuotas(instances_to_mv, disks_to_mv, self._flags.source_zone,
                      self._flags.destination_zone)

    self._Confirm(instances_to_mv, [], disks_to_mv,
                  self._flags.destination_zone)

    log_path = self._GenerateLogPath()
    snapshot_mappings = self._GenerateSnapshotNames(disks_to_mv)
    self._WriteLog(log_path, instances_to_mv, snapshot_mappings)

    self._DeleteInstances(instances_to_mv, self._flags.source_zone)

    # Assuming no other processes have modified the user's project, at
    # this point, we can assume that all disks-to-be-moved are
    # dormant.
    self._CreateSnapshots(snapshot_mappings,
                          self._flags.source_zone,
                          self._flags.destination_zone)
    self._DeleteDisks(disks_to_mv, self._flags.source_zone)
    self._CreateDisksFromSnapshots(snapshot_mappings,
                                   self._flags.destination_zone)
    self._CreateInstances(instances_to_mv,
                          self._flags.source_zone,
                          self._flags.destination_zone)

    self._DeleteSnapshots(snapshot_mappings.values(),
                          self._flags.destination_zone)

    # We have succeeded, so it's safe to delete the log file.
    os.remove(log_path)

  def _GenerateSnapshotNames(self, disk_names):
    """Returns a dict mapping each disk name to a random UUID.

    The UUID will be used as the disk's snapshot name. UUID's are
    valid Compute resource names. Further, UUID collisions are
    improbable, so using them is a great way for generating resource
    names (e.g., we avoid network communication to check if the name
    we choose already exists).

    Args:
      disk_names: A list of disk_names for which snapshot names
        should be generated.

    Returns:
      A dict with the mapping.
    """
    return dict((name, 'snapshot-' + str(uuid.uuid4())) for name in disk_names)

  def _CheckInstancePreconditions(self, instances_to_mv, instances_in_dest):
    if not instances_to_mv:
      raise command_base.CommandError('No matching instances were found.')

    if len(instances_to_mv) > MAX_INSTANCES_TO_MOVE:
      raise command_base.CommandError(
          'At most %s instances can be moved at a '
          'time. Refine your query and try again.' % MAX_INSTANCES_TO_MOVE)

    # Checks for name collisions.
    src_names = [i['name'] for i in instances_to_mv]
    dest_names = [i['name'] for i in instances_in_dest]
    common_names = set(src_names) & set(dest_names)
    if common_names:
      raise command_base.CommandError(
          'Encountered name collisions. Instances with the following names '
          'exist in both the source and destination zones: \n%s' %
          utils.ListStrings(common_names))

  def _CheckDiskPreconditions(self, instances_to_ignore, disk_names):
    if len(disk_names) > MAX_DISKS_TO_MOVE:
      raise command_base.CommandError(
          'At most %s disks can be moved at a '
          'time. Refine your query and try again.' % MAX_DISKS_TO_MOVE)

    res = self._CheckForDisksInUseByOtherInstances(
        instances_to_ignore, disk_names)
    if res:
      offending_instances = ['%s: %s' % (instance, ', '.join(disks))
                             for instance, disks in res]
      raise command_base.CommandError(
          'Some of the instances you\'d like to move have disks that are in '
          'use by other instances: (Offending instance: disks attached)\n%s' %
          (utils.ListStrings(offending_instances)))

  def _CheckForDisksInUseByOtherInstances(self, instances, disk_names):
    """Returns a list containing a mapping of instance to persistent disks.

    Args:
      instances: The set of instances to inspect.
      disk_names: The disks to look for.

    Returns:
      A list of tuples where the first element of each tuple is an instance
      name and the second element is a list of disks attached to that
      instance.
    """
    res = {}
    disk_names = set(disk_names)
    for instance in instances:
      instance_name = instance['name']
      for disk in instance.get('disks', []):
        if disk['type'] != 'PERSISTENT':
          continue
        disk_name = disk['source'].split('/')[-1]
        if disk_name in disk_names:
          if instance_name not in res:
            res[instance_name] = []
          res[instance_name].append(disk_name)
    return sorted(res.iteritems())

  def _GetPersistentDiskNames(self, instances):
    res = []
    for instance in instances:
      for disk in instance.get('disks', []):
        if disk['type'] == 'PERSISTENT':
          res.append(disk['source'].split('/')[-1])
    return res

  def _CheckDestinationZone(self):
    """Raises an exception if the destination zone is not valid."""
    print 'Checking destination zone...'
    self._zones_api.get(project=self._project,
                        zone=self._flags.destination_zone).execute()

  def _WriteLog(self, log_path, instances_to_mv, snapshot_mappings):
    """Logs the instances that will be moved and the destination zone."""
    print 'If the move fails, you can re-attempt it using:'
    print '  gcutil resumemove %s' % log_path
    with open(log_path, 'w') as f:
      contents = {'version': version.__version__,
                  'dest_zone': self._flags.destination_zone,
                  'src_zone': self._flags.source_zone,
                  'instances': instances_to_mv,
                  'snapshot_mappings': snapshot_mappings}
      json.dump(contents, f)

  def _GenerateLogPath(self):
    """Generates a file path in the form ~/.gcutil.move.YYmmddHHMMSS."""
    timestamp = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
    return os.path.join(os.path.expanduser('~'), '.gcutil.move.' + timestamp)


class ResumeMove(MoveInstancesBase):
  """Resume a previously-failed move.

  The moveinstances subcommand produces a log file that can be used to
  re-attempt a move that fails. This is intended to help complete
  moves that are interrupted by the user or by transient network
  failures.

  WARNING: Instances that are moved will lose ALL of their ephemeral
  state (i.e., ephemeral disks, ephemeral IP addresses, and memory).
  """

  positional_args = '<log-path>'

  def __init__(self, name, flag_values):
    super(ResumeMove, self).__init__(name, flag_values)

    flags.DEFINE_boolean(
        'keep_log_file',
        False,
        'If true, the log file is not deleted at the end of the resume.',
        flag_values=flag_values)

  def _Intersect(self, resources1, resources2):
    """set(resources1) & set(resources2) based on the name field."""
    names1 = set(r['name'] for r in resources1)
    return [r for r in resources2 if r['name'] in names1]

  def _Subtract(self, resources1, resources2):
    """set(resources1) - set(resources2) based on the name field."""
    names2 = set(r['name'] for r in resources2)
    return [r for r in resources1 if r['name'] not in names2]

  def _GetKey(self, log, key):
    """Returns log[key] or raises a CommandError if key does not exist."""
    value = log.get(key)
    if value is None:
      raise command_base.CommandError(
          'The log file did not contain a %s key.' % repr(key))
    return value

  def _ParseLog(self, log_path):
    """Loads the JSON contents of the file pointed to by log_path."""
    print 'Parsing log file...'
    with open(log_path) as f:
      result = json.load(f)
    return result

  def HandleMove(self, log_path):
    """Attempts the move dictated in the given log file.

    This method first checks the current state of the project to see
    which instances have already been moved before moving the
    instances that were left behind in a previous failed move.

    The user is prompted to continue before any changes are made.

    Args:
      log_path: The path to the replay log.
    """
    if not os.path.exists(log_path):
      raise command_base.CommandError('File not found: %s' % log_path)

    log = self._ParseLog(log_path)

    src_zone = self._GetKey(log, 'src_zone')
    print 'Source zone is %s.' % src_zone

    dest_zone = self._GetKey(log, 'dest_zone')
    print 'Destination zone is %s.' % dest_zone

    snapshot_mappings = self._GetKey(log, 'snapshot_mappings')
    instances_to_mv = self._GetKey(log, 'instances')

    instances_in_dest = utils.All(
        self._instances_api.list, self._project, zone=dest_zone)['items']
    instances_in_source = utils.All(
        self._instances_api.list, self._project, zone=src_zone)['items']

    # Note that we cannot use normal set intersection and subtraction
    # because two different instance resources could be referring to
    # the same instance (e.g., the instance was restarted by the
    # system).
    instances_to_ignore = self._Intersect(instances_to_mv, instances_in_dest)
    instances_to_mv = self._Subtract(instances_to_mv, instances_in_dest)

    if not instances_to_mv:
      raise command_base.CommandError(
          'All instances are already in %s.' % dest_zone)

    # Figures out which disks have not been moved.
    disks_in_dest = set(utils.AllNames(
        self._disks_api.list, self._project, zone=dest_zone))
    disks_in_src = set(utils.AllNames(
        self._disks_api.list, self._project, zone=src_zone))

    disks_to_mv = set(snapshot_mappings.keys()) & disks_in_src

    instances_to_delete = self._Intersect(instances_to_mv, instances_in_source)

    # For the disks that are still in the source zone, figures out
    # which ones still need to be snapshotted before being deleted.
    snapshot_mappings_for_unmoved_disks = {}
    if disks_to_mv:
      current_snapshots = utils.AllNames(
          self._snapshots_api.list, self._project)

      for disk, snapshot in snapshot_mappings.iteritems():
        if disk in disks_to_mv and snapshot not in current_snapshots:
          snapshot_mappings_for_unmoved_disks[disk] = snapshot

    # Ensures that the current quotas can support the move and prompts
    # the user for confirmation.
    self._CheckQuotas(instances_to_mv, disks_to_mv, src_zone, dest_zone,
                      snapshots_to_create=snapshot_mappings_for_unmoved_disks)
    self._Confirm(instances_to_mv, instances_to_ignore,
                  disks_to_mv, dest_zone)

    self._DeleteInstances(instances_to_delete, src_zone)
    self._CreateSnapshots(snapshot_mappings_for_unmoved_disks,
                          src_zone, dest_zone)
    self._DeleteDisks(disks_to_mv, src_zone)

    # Create disks in destination zone from snapshots.
    all_snapshots = set(utils.AllNames(
        self._snapshots_api.list, self._project))
    disks_to_create = {}
    for disk, snapshot in snapshot_mappings.iteritems():
      if snapshot in all_snapshots and disk not in disks_in_dest:
        disks_to_create[disk] = snapshot
    self._CreateDisksFromSnapshots(disks_to_create, dest_zone)

    self._CreateInstances(instances_to_mv, src_zone, dest_zone)
    self._DeleteSnapshots(disks_to_create.values(), dest_zone)

    if not self._flags.keep_log_file:
      # We have succeeded, so it's safe to delete the log file.
      os.remove(log_path)


def AddCommands():
  appcommands.AddCmd('moveinstances', MoveInstances)
  appcommands.AddCmd('resumemove', ResumeMove)
