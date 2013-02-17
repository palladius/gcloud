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

"""Commands for interacting with Google Compute Engine VM instances."""




import logging
import os
import time

from apiclient import errors

from google.apputils import app
from google.apputils import appcommands
import gflags as flags

from gcutil import command_base
from gcutil import gcutil_logging
from gcutil import metadata
from gcutil import scopes
from gcutil import ssh_keys



FLAGS = flags.FLAGS
LOGGER = gcutil_logging.LOGGER


class InstanceCommand(command_base.GoogleComputeCommand):
  """Base command for working with the instances collection."""

  default_sort_field = 'name'
  summary_fields = (('name', 'name'),
                    ('machine-type', 'machineType'),
                    ('image', 'image'),
                    ('network', 'networkInterfaces.network'),
                    ('network-ip', 'networkInterfaces.networkIP'),
                    ('external-ip', 'networkInterfaces.accessConfigs.natIP'),
                    ('disks', 'disks.source'),
                    ('zone', 'zone'),
                    ('status', 'status'),
                    ('status-message', 'statusMessage'))

  # The remaining complex fields are filled in via CustomizePrintResult
  detail_fields = (('name', 'name'),
                   ('description', 'description'),
                   ('creation-time', 'creationTimestamp'),
                   ('machine', 'machineType'),
                   ('image', 'image'),
                   ('zone', 'zone'),
                   ('tags-fingerprint', 'tags.fingerprint'),
                   ('metadata-fingerprint', 'metadata.fingerprint'),
                   ('status', 'status'),
                   ('status-message', 'statusMessage'))

  # A map from legal values for the disk "mode" option to the
  # corresponding API value. Keys in this map should be lowercase, as
  # we convert user provided values to lowercase prior to performing a
  # look-up.
  disk_modes = {
      'read_only': 'READ_ONLY',
      'ro': 'READ_ONLY',
      'read_write': 'READ_WRITE',
      'rw': 'READ_WRITE'}

  resource_collection_name = 'instances'

  # The default network interface name assigned by the service.
  DEFAULT_NETWORK_INTERFACE_NAME = 'nic0'

  # The default access config name
  DEFAULT_ACCESS_CONFIG_NAME = 'External NAT'

  # Currently, only access config type 'ONE_TO_ONE_NAT' is supported.
  ONE_TO_ONE_NAT_ACCESS_CONFIG_TYPE = 'ONE_TO_ONE_NAT'

  # Let the server select an ephemeral IP address.
  EPHEMERAL_ACCESS_CONFIG_NAT_IP = 'ephemeral'

  def __init__(self, name, flag_values):
    super(InstanceCommand, self).__init__(name, flag_values)

    flags.DEFINE_string('zone',
                        None,
                        'The zone for this request.',
                        flag_values=flag_values)

  def SetApi(self, api):
    """Set the Google Compute Engine API for the command.

    Args:
      api: The Google Compute Engine API used by this command.

    Returns:
      None.

    """
    self._projects_api = api.projects()
    self._instances_api = api.instances()
    self._images_api = api.images()
    self._kernels_api = api.kernels()
    self._disks_api = api.disks()
    self._machine_types_api = api.machineTypes()
    self._zones_api = api.zones()

  def CustomizePrintResult(self, result, table):
    """Customized result printing for this type.

    Args:
      result: json dictionary returned by the server
      table: the pretty printing table to be customized

    Returns:
      None.

    """
    # Add the disks
    for disk in result.get('disks', []):
      table.AddRow(('', ''))
      table.AddRow(('disk', disk['index']))
      table.AddRow(('  type', disk['type']))
      if 'mode' in disk:
        table.AddRow(('  mode', disk['mode']))
      if 'deviceName' in disk:
        table.AddRow(('  deviceName', disk['deviceName']))
      if 'source' in disk:
        table.AddRow(('  source', disk['source']))
      if 'boot' in disk:
        table.AddRow(('  boot', disk['boot']))
      if 'deleteOnTerminate' in disk:
        table.AddRow(('  delete on terminate', disk['deleteOnTerminate']))

    # Add the networks
    for network in result.get('networkInterfaces', []):
      table.AddRow(('', ''))
      table.AddRow(('network-interface', ''))
      table.AddRow(('  network',
                    self._PresentElement(network.get('network', ''))))
      table.AddRow(('  ip', network.get('networkIP', '')))
      for config in network.get('accessConfigs', []):
        table.AddRow(('  access-configuration', config.get('name', '')))
        table.AddRow(('    type', config.get('type', '')))
        table.AddRow(('    external-ip', config.get('natIP', '')))

    # Add the service accounts
    for service_account in result.get('serviceAccounts', []):
      table.AddRow(('', ''))
      table.AddRow(('service-account', service_account.get('email', '')))
      table.AddRow(('  scopes', service_account.get('scopes', '')))

    # Add metadata

    if result.get('metadata', []):
      table.AddRow(('', ''))
      table.AddRow(('metadata', ''))
      table.AddRow(('fingerprint', result.get('metadata', {})
                    .get('fingerprint', '')))
      metadata_container = result.get('metadata', {}).get('items', [])
      for i in metadata_container:
        table.AddRow(('  %s' % i.get('key', ''),
                      self._PresentElement(i.get('value', ''))))

    # Add tags

    if result.get('tags', []):
      table.AddRow(('', ''))
      table.AddRow(('tags', ''))
      table.AddRow(('fingerprint', result.get('tags', {})
                    .get('fingerprint', '')))
      tags_container = result.get('tags', {}).get('items', [])
      for i in tags_container:
        table.AddRow(('   ',
                      self._PresentElement(i)))

  def _ExtractExternalIpFromInstanceRecord(self, instance_record):
    """Extract the external IP(s) from an instance record.

    Args:
      instance_record: An instance as returned by the Google Compute Engine API.

    Returns:
      A list of internet IP addresses associated with this VM.
    """
    external_ips = set()

    for network_interface in instance_record.get('networkInterfaces', []):
      for access_config in network_interface.get('accessConfigs', []):
        # At the moment, we only know how to translate 1-to-1 NAT
        if (access_config.get('type') == self.ONE_TO_ONE_NAT_ACCESS_CONFIG_TYPE
            and 'natIP' in access_config):
          external_ips.add(access_config['natIP'])

    return list(external_ips)

  def _AddAuthorizedUserKeyToProject(self, authorized_user_key):
    """Update the project to include the specified user/key pair.

    Args:
      authorized_user_key: A dictionary of a user/key pair for the user.

    Returns:
      True iff the ssh key was added to the project.

    Raises:
      command_base.CommandError: If the metadata update fails.
    """
    project = self._projects_api.get(project=self._project).execute()
    common_instance_metadata = project.get('commonInstanceMetadata', {})

    project_metadata = common_instance_metadata.get(
        'items', [])
    project_ssh_keys = ssh_keys.SshKeys.GetAuthorizedUserKeysFromMetadata(
        project_metadata)
    if authorized_user_key in project_ssh_keys:
      return False
    else:
      project_ssh_keys.append(authorized_user_key)
      ssh_keys.SshKeys.SetAuthorizedUserKeysInMetadata(
          project_metadata, project_ssh_keys)

      try:
        request = self._projects_api.setCommonInstanceMetadata(
            project=self._project,
            body={'kind': self._GetResourceApiKind('metadata'),
                  'items': project_metadata})
        request.execute()
      except errors.HttpError:
        # A failure to add the ssh key probably means that the project metadata
        # has exceeded the max size. The user needs to either manually
        # clean up their project metadata, or set the ssh keys manually for this
        # instance. Either way, trigger a usage error to let them know.
        raise command_base.CommandError(
            'Unable to add the local ssh key to the project. Either manually '
            'remove some entries from the commonInstanceMetadata field of the '
            'project, or explicitly set the authorized keys for this instance.')
      return True

  def _PrepareRequestArgs(self, instance_name, **other_args):
    """Gets the dictionary of API method keyword arguments.

    Args:
      instance_name: The name of the instance.
      **other_args: Keyword arguments that should be included in the request.

    Returns:
      Dictionary of keyword arguments that should be passed in the API call,
      includes all keyword arguments passed in 'other_args' plus
      common keys such as the name of the resource and the project.
    """

    kwargs = {
        'project': self._project,
        'instance': self.DenormalizeResourceName(instance_name)
    }
    if self._IsUsingAtLeastApiVersion('v1beta14'):
      if not self._flags.zone:
        self._flags.zone = self.GetZoneForResource(self._instances_api,
                                                   instance_name)
      kwargs['zone'] = self._flags.zone

    for key, value in other_args.items():
      kwargs[key] = value
    return kwargs

  def _AddComputeKeyToProject(self):
    """Update the current project to include the user's public ssh key.

    Returns:
      True iff the ssh key was added to the project.
    """
    compute_key = ssh_keys.SshKeys.GetPublicKey()
    return self._AddAuthorizedUserKeyToProject(compute_key)

  def _BuildAttachedDisk(self, disk_arg):
    """Converts a disk argument into an AttachedDisk object."""
    # Start with the assumption that the argument only specifies the
    # name of the disk resource.
    disk_name = disk_arg
    device_name = disk_arg
    mode = 'READ_WRITE'
    boot = False

    disk_parts = disk_arg.split(',')
    if len(disk_parts) > 1:
      # The argument includes new-style decorators. The first part is
      # the disk resource name. The other parts are optional key/value
      # pairs.
      disk_name = disk_parts[0]
      device_name = disk_parts[0]
      for option in disk_parts[1:]:
        if option == 'boot':
          if self._IsUsingAtLeastApiVersion('v1beta14'):
            boot = True
            continue
          else:
            raise ValueError('boot flag is not supported for this API version')
        if not '=' in option:
          raise ValueError('Invalid disk option: %s' % option)
        key, value = option.split('=', 2)
        if key == 'deviceName':
          device_name = value
        elif key == 'mode':
          mode = self.disk_modes.get(value.lower())
          if not mode:
            raise ValueError('Invalid disk mode: %s' % value)
        else:
          raise ValueError('Invalid disk option: %s' % key)
    else:
      # The user didn't provide any options using the newer key/value
      # syntax, so check to see if they have used the old syntax where
      # the device name is delimited by a colon.
      disk_parts = disk_arg.split(':')
      if len(disk_parts) > 1:
        disk_name = disk_parts[0]
        device_name = disk_parts[1]
        LOGGER.info(
            'Please use new disk device naming syntax: --disk=%s,deviceName=%s',
            disk_name,
            device_name)

    disk_url = self.NormalizePerZoneResourceName(self._project,
                                                 self._flags.zone,
                                                 'disks',
                                                 disk_name)

    disk = {
        'type': 'PERSISTENT',
        'source': disk_url,
        'mode': mode,
        'deviceName': device_name}
    if self._IsUsingAtLeastApiVersion('v1beta14'):
      disk['boot'] = boot
    return disk


class AddInstance(InstanceCommand):
  """Create new VM instances.

  More than one instance name can be specified.  Multiple instances will be
  created in parallel.
  """

  positional_args = '<instance-name-1> ... <instance-name-n>'
  status_field = 'status'
  _TERMINAL_STATUS = ['RUNNING', 'TERMINATED']

  def __init__(self, name, flag_values):
    super(AddInstance, self).__init__(name, flag_values)

    flags.DEFINE_string('description',
                        '',
                        'Instance description',
                        flag_values=flag_values)
    flags.DEFINE_string('image',
                        None,
                        'Image name. To get a list of images built by Google, '
                        'run \'gcutil listimages --project=projects/google\'. '
                        'To get a list of images you have built, run \'gcutil '
                        'listimages\'.',
                        flag_values=flag_values)
    flags.DEFINE_string('kernel',
                        None,
                        'Kernel name. To get a list of kernels built by '
                        'Google, run \'gcutil listkernels --project=google\'. ',
                        flag_values=flag_values)
    flags.DEFINE_boolean('persistent_boot_disk',
                         None,
                         'Make boot disk persistent. Copy contents of the '
                         'image onto a new disk named "boot-{instanceName}" '
                         'and use it for booting. The preferred kernel for '
                         'the image will be used to boot, but it may be '
                         'overridden by passing --kernel.',
                         flag_values=flag_values)
    flags.DEFINE_string('machine_type',
                        None,
                        'Machine type name. To get a list of available machine '
                        'types, run \'gcutil listmachinetypes\'.',
                        flag_values=flag_values)
    flags.DEFINE_string('network',
                        'default',
                        'The network to which to attach the instance.',
                        flag_values=flag_values)
    flags.DEFINE_string('internal_ip_address',
                        '',
                        'The internal (within the specified network) IP '
                        'address for the instance; if not set the instance '
                        'will be assigned an appropriate address.',
                        flag_values=flag_values)
    flags.DEFINE_string('external_ip_address',
                        self.EPHEMERAL_ACCESS_CONFIG_NAT_IP,
                        'The external NAT IP of the new instance. The default '
                        'value "ephemeral" indicates the service should choose '
                        'an available ephemeral IP. The value "none" (or an '
                        'empty string) indicates no external IP will be '
                        'assigned to the new instance. If an explicit IP is '
                        'given, that IP must be reserved by the project and '
                        'not yet assigned to another instance.',
                        flag_values=flag_values)
    flags.DEFINE_multistring('disk',
                             [],
                             'The name of a disk to be attached to the '
                             'instance. The name may be followed by a '
                             'comma-separated list of name=value pairs '
                             'specifying options. Legal option names are '
                             '\'deviceName\', to specify the disk\'s device '
                             'name, and \'mode\', to indicate whether the disk '
                             'should be attached READ_WRITE (the default) or '
                             'READ_ONLY. You may also use the \'boot\' '
                             'flag to designate the disk as a boot device',
                             flag_values=flag_values)
    flags.DEFINE_boolean('use_compute_key',
                         False,
                         'Whether or not to include the default '
                         'Google Compute Engine ssh key as one of the '
                         'authorized ssh keys for the created instance. This '
                         'has the side effect of disabling project-wide ssh '
                         'key management for the instance.',
                         flag_values=flag_values)
    flags.DEFINE_boolean('add_compute_key_to_project',
                         None,
                         'Whether or not to add the default Google Compute '
                         'Engine ssh key as one of the authorized ssh keys '
                         'for the project. If the default key has already '
                         'been added to the project, then this will have no '
                         'effect. The default behavior is to add the key to '
                         'the project if no instance-specific keys are '
                         'defined.',
                         flag_values=flag_values)
    flags.DEFINE_list('authorized_ssh_keys',
                      [],
                      'Fix the list of user/key-file pairs to the specified '
                      'entries, disabling project-wide key management for this '
                      'instance. These are specified as a comma separated list '
                      'of colon separated entries: '
                      'user1:keyfile1,user2:keyfile2,...',
                      flag_values=flag_values)
    flags.DEFINE_string('service_account',
                        'default',
                        'The service account whose credentials are to be made'
                        ' available for this instance.',
                        flag_values=flag_values)
    flags.DEFINE_list('service_account_scopes',
                      [],
                      'The scopes of credentials of the above service'
                      ' account that are to be made available for this'
                      ' instance (comma separated).  There are also a set of '
                      'scope aliases supported: %s'
                      % ', '.join(sorted(scopes.SCOPE_ALIASES.keys())),
                      flag_values=flag_values)
    flags.DEFINE_boolean('wait_until_running',
                         False,
                         'Whether the program should wait until the instance is'
                         ' in running state.',
                         flag_values=flag_values)
    flags.DEFINE_list('tags',
                      [],
                      'A set of tags applied to this instance. Used for '
                      'filtering and to configure network firewall rules '
                      '(comma separated).',
                      flag_values=flag_values)

    self._metadata_flags_processor = metadata.MetadataFlagsProcessor(
        flag_values)

  def Handle(self, *instance_names):
    """Add the specified instance.

    Args:
      *instance_names: A list of instance names to add.

    Returns:
      A tuple of (result, exceptions)
    """
    if not instance_names:
      raise app.UsageError('You must specify at least one instance name')

    if len(instance_names) > 1 and self._flags.disk:
      raise command_base.CommandError(
          'Specifying a disk when starting multiple instances is not '
          'currently supported')

    if max([len(i) for i in instance_names]) > 32:
      LOGGER.warn('Hostnames longer than 32 characters have known issues with '
                  'some linux distributions.')

    self._flags.zone = self._GetZone(self._flags.zone or
                                     self._FindDefaultZone(self._flags.disk))
    if not self._flags.machine_type:
      self._flags.machine_type = self._PromptForMachineType()['name']

    # Processes the disks, so we can check for the presence of a boot
    # disk before prompting for image or kernel.
    disks = [self._BuildAttachedDisk(disk) for disk in self._flags.disk]

    if (not self._flags.image and
        self._IsUsingAtLeastApiVersion('v1beta14') and
        (not self._HasBootDisk(disks) or self._flags.persistent_boot_disk)):
      self._flags.image = self._PromptForImage()['selfLink']

    if not self._flags.kernel and self._HasBootDisk(disks):
      # Have boot disk but no kernel, prompt for a kernel.
      self._flags.kernel = self._PromptForKernel()['selfLink']

    instance_metadata = self._metadata_flags_processor.GatherMetadata()
    if self._flags.authorized_ssh_keys or self._flags.use_compute_key:
      instance_metadata = self._AddSshKeysToMetadata(instance_metadata)

    # Map of instance_name => boot_disk.
    boot_disks = {}
    if self._flags.persistent_boot_disk:
      if not self._IsUsingAtLeastApiVersion('v1beta14'):
        raise app.UsageError(
            'Booting from persistent disk is only supported in '
            'v1beta14 and above.')

      # Persistent boot device request. We need to create a new disk for each VM
      # and populate it with contents of the specified image.

      # Read the preferred kernel from the image unless overridden by the user.
      if not self._flags.kernel:
        normalized_image_name = self.NormalizeGlobalResourceName(
            self._project, 'images', self._flags.image)
        image_name_parts = normalized_image_name.split('/')

        # Read the actual image, but first verify that the user gave us valid
        # image URL.
        if (image_name_parts[-2] != 'images' or
            image_name_parts[-3] != 'global' or
            image_name_parts[-5] != 'projects'):
          raise app.UsageError('Invalid image URL: %s' %
                               normalized_image_name)

        image_resource = self._images_api.get(
            project=image_name_parts[-4],
            image=image_name_parts[-1]).execute()

        self._flags.kernel = image_resource['preferredKernel']

      disk_creation_requests = []
      for instance_name in instance_names:
        boot_disk_name = 'boot-%s' % (instance_name)
        boot_disks[instance_name] = self._BuildAttachedDisk(
            '%s,boot' % (boot_disk_name))
        LOGGER.info('Preparing boot disk [%s] for instance [%s]'
                    ' from disk image [%s].',
                    boot_disk_name, instance_name,
                    self._flags.image)
        disk_creation_requests.append(
            self._CreateDiskFromImageRequest(boot_disk_name))

      self._flags.image = None

      (disk_results, disk_exceptions) = self.ExecuteRequests(
          disk_creation_requests, collection_name='disks')
      if disk_exceptions:
        return (self.MakeListResult(disk_results, 'operationList'),
                disk_exceptions)

    if self._flags.add_compute_key_to_project or (
        self._flags.add_compute_key_to_project is None and
        not 'sshKeys' in [entry.get('key', '') for entry in instance_metadata]):
      try:
        self._AddComputeKeyToProject()
      except ssh_keys.UserSetupError as e:
        LOGGER.warn('Could not generate compute ssh key: %s', e)

    self._ValidateFlags()

    requests = []
    for instance_name in instance_names:
      instance_disks = disks
      if instance_name in boot_disks:
        instance_disks = [boot_disks[instance_name]] + disks
      requests.append(self._BuildRequestWithMetadata(
          instance_name, instance_metadata, instance_disks))

    (results, exceptions) = self.ExecuteRequests(requests)

    if self._flags.wait_until_running:
      instances_to_wait = results
      results = []
      for result in instances_to_wait:
        if self.IsResultAnOperation(result):
          results.append(result)
        else:
          instance_name = result['name']
          kwargs = self._PrepareRequestArgs(instance_name)
          get_request = self._instances_api.get(**kwargs)
          instance_result = get_request.execute()
          instance_result = self._WaitUntilInstanceIsRunning(
              instance_result, kwargs)
          results.append(instance_result)

    if self._flags.synchronous_mode:
      return (self.MakeListResult(results, 'instanceList'), exceptions)
    else:
      return (self.MakeListResult(results, 'operationList'), exceptions)

  def _WaitUntilInstanceIsRunning(self, result, kwargs):
    """Waits for the instance to start.

    Periodically polls the server for current instance status. Exits if the
    status of the instance is RUNNING or TERMINATED or the maximum waiting
    timeout has been reached. In both cases returns the last known instance
    details.

    Args:
      result: the current state of the instance.
      kwargs: keyword arguments to _instances_api.get()

    Returns:
      Json containing full instance information.
    """
    current_status = result[self.status_field]
    start_time = time.time()
    instance_name = kwargs['instance']
    LOGGER.info('Ensuring %s is running.  Will wait to start for: %d seconds.',
                instance_name, self._flags.max_wait_time)
    while (time.time() - start_time < self._flags.max_wait_time and
           current_status not in self._TERMINAL_STATUS):
      LOGGER.info(
          'Waiting for instance \'%s\' to start. '
          'Current status: %s. Sleeping for %ss.',
          instance_name,
          current_status, self._flags.sleep_between_polls)
      time.sleep(self._flags.sleep_between_polls)
      result = self._instances_api.get(**kwargs).execute()
      current_status = result[self.status_field]
    if current_status not in self._TERMINAL_STATUS:
      LOGGER.warn('Timeout reached. Instance %s has not yet started.',
                  instance_name)
    return result

  def _FindDefaultZone(self, disks):
    """Given the persistent disks for an instance, find a default zone.

    Args:
      disks: The list of persistent disks to be used by the instance.

    Returns:
      The name of a zone if a clear default can be determined
      from the persistent disks, otherwise None.
    """
    for disk in disks:
      # Remove any options from the disk name. We need to strip using
      # both ',' and ':' to handle the new and old methods for
      # providing disk options.
      if ',' in disk:
        disk = disk.split(',')[0]
      elif ':' in disk:
        disk = disk.split(':')[0]
      disk_name = self.DenormalizeResourceName(disk)

      if self._IsUsingAtLeastApiVersion('v1beta14'):
        return self.GetZoneForResource(self._disks_api, disk_name,
                                       fail_if_not_found=False)

      get_request = self._disks_api.get(
          project=self._project, disk=disk_name)
      return get_request.execute()['zone']

  def _AddSshKeysToMetadata(self, instance_metadata):
    instance_ssh_keys = ssh_keys.SshKeys.GetAuthorizedUserKeys(
        use_compute_key=self._flags.use_compute_key,
        authorized_ssh_keys=self._flags.authorized_ssh_keys)
    if instance_ssh_keys:
      new_value = ['%(user)s:%(key)s' % user_key
                   for user_key in instance_ssh_keys]
      # Have the new value extend the old value
      old_values = [entry['value'] for entry in instance_metadata
                    if entry['key'] == 'sshKeys']
      all_values = '\n'.join(old_values + new_value)
      instance_metadata = [entry for entry in instance_metadata
                           if entry['key'] != 'sshKeys']
      instance_metadata.append({'key': 'sshKeys', 'value': all_values})
    return instance_metadata

  def _HasBootDisk(self, disks):
    """Determines if any of the disks in a list is a boot disk."""
    for disk in disks:
      if disk.get('boot', False):
        return True

    return False

  def _ValidateFlags(self):
    """Validate flags coming in before we start building resources.

    Raises:
      app.UsageError: If service account explicitly given without scopes.
      command_base.CommandError: If scopes contains ' '.
    """
    if (self._flags.service_account and
        self._flags.service_account_scopes):
      # Ensures that the user did not space-delimit his or her scopes
      # list.
      for scope in self._flags.service_account_scopes:
        if ' ' in scope:
          raise command_base.CommandError(
              'Scopes list must be comma-delimited, not space-delimited.')
    elif self._flags['service_account'].present:
      raise app.UsageError(
          '--service_account given without --service_account_scopes.')

    if self._flags.wait_until_running and not self._flags.synchronous_mode:
      LOGGER.warn('wait_until_running set. Implying synchronous_mode.')
      self._flags.synchronous_mode = True

  def _CreateDiskFromImageRequest(self, disk_name):
    """Build a request that creates disk from source image.

    Args:
      disk_name: Name of the disk.

    Returns:
      The prepared disk insert request.
    """

    disk_resource = {
        'kind': self._GetResourceApiKind('instance'),
        'name': disk_name,
        'description': 'Persistent boot disk created from %s.' % (
            self._flags.image),
        'zone': self.NormalizeTopLevelResourceName(self._project, 'zones',
                                                   self._flags.zone),
        }
    source_image_url = self.NormalizeGlobalResourceName(self._project, 'images',
                                                        self._flags.image)
    kwargs = {
        'project': self._project,
        'body': disk_resource,
        'sourceImage': source_image_url
    }
    if self._IsUsingAtLeastApiVersion('v1beta14'):
      kwargs['zone'] = disk_resource['zone'].split('/')[-1]
      del disk_resource['zone']
    return self._disks_api.insert(**kwargs)

  def _BuildRequestWithMetadata(self, instance_name, instance_metadata, disks):
    """Build a request to add the specified instance, given the ssh keys for it.

    Args:
      instance_name: Name of the instance to build a request for.
      instance_metadata: The metadata to be passed to the VM.  This is in the
        form of [{'key': <key>, 'value': <value>}] form, ready to be
        sent to the server.
      disks: Disks to attach to the instance.

    Returns:
      The prepared instance request.
    """
    instance_resource = {
        'kind': self._GetResourceApiKind('instance'),
        'name': self.DenormalizeResourceName(instance_name),
        'description': self._flags.description,
        'networkInterfaces': [],
        'disks': disks,
        'metadata': [],
        }

    if self._flags.image:
      instance_resource['image'] = self.NormalizeGlobalResourceName(
          self._project, 'images', self._flags.image)

    if self._flags.kernel:
      instance_resource['kernel'] = self.NormalizeGlobalResourceName(
          self._project, 'kernels', self._flags.kernel)

    if self._flags.machine_type:
      instance_resource['machineType'] = self.NormalizeGlobalResourceName(
          self._project, 'machine-types', self._flags.machine_type)


    instance_resource['zone'] = self.NormalizeTopLevelResourceName(
        self._project, 'zones', self._flags.zone)

    if self._flags.network:
      network_interface = {
          'network': self.NormalizeGlobalResourceName(self._project, 'networks',
                                                      self._flags.network)
          }
      if self._flags.internal_ip_address:
        network_interface['networkIP'] = self._flags.internal_ip_address
      external_ip_address = self._flags.external_ip_address
      if external_ip_address and external_ip_address.lower() != 'none':
        access_config = {
            'name': self.DEFAULT_ACCESS_CONFIG_NAME,
            'type': self.ONE_TO_ONE_NAT_ACCESS_CONFIG_TYPE,
            }
        if external_ip_address.lower() != self.EPHEMERAL_ACCESS_CONFIG_NAT_IP:
          access_config['natIP'] = self._flags.external_ip_address

        network_interface['accessConfigs'] = [access_config]

      instance_resource['networkInterfaces'].append(network_interface)

    metadata_subresource = {
        'kind': self._GetResourceApiKind('metadata'),
        'items': []}

    metadata_subresource['items'].extend(instance_metadata)
    instance_resource['metadata'] = metadata_subresource

    if self._flags.service_account and (
        len(self._flags.service_account_scopes)):
      instance_resource['serviceAccounts'] = []
      expanded_scopes = scopes.ExpandScopeAliases(
          self._flags.service_account_scopes)
      instance_resource['serviceAccounts'].append({
          'email': self._flags.service_account,
          'scopes': expanded_scopes})

    instance_tags = sorted(set(self._flags.tags))
    if self._IsUsingAtLeastApiVersion('v1beta14'):
      instance_tags = {'items': sorted(set(self._flags.tags))}
    instance_resource['tags'] = instance_tags
    kwargs = {
        'project': self._project,
        'body': instance_resource,
    }
    if self._IsUsingAtLeastApiVersion('v1beta14'):
      kwargs['zone'] = self.DenormalizeResourceName(self._flags.zone)
      del instance_resource['zone']

    return self._instances_api.insert(**kwargs)


class GetInstance(InstanceCommand):
  """Get a machine instance."""

  positional_args = '<instance-name>'

  def Handle(self, instance_name):
    """Get the specified instance.

    Args:
      instance_name: The name of the instance to get.

    Returns:
      The result of getting the instance.
    """
    instance_request = self._instances_api.get(
        **self._PrepareRequestArgs(instance_name))

    return instance_request.execute()


class DeleteInstance(InstanceCommand):
  """Delete one or more VM instances.

  If multiple instance names are specified, the instances will be deleted
  in parallel.
  """

  positional_args = '<instance-name-1> ... <instance-name-n>'
  safety_prompt = 'Delete instance'

  def Handle(self, *instance_names):
    """Delete the specified instances.

    Args:
      *instance_names: Names of the instances to delete.

    Returns:
      The result of deleting the instance.
    """
    if self._IsUsingAtLeastApiVersion('v1beta14') and not self._flags.zone:
      if len(instance_names) > 1:
        self._flags.zone = self._GetZone()
      else:
        self._flags.zone = self.GetZoneForResource(self._instances_api,
                                                   instance_names[0])

    requests = []
    for instance_name in instance_names:
      requests.append(self._instances_api.delete(
          **self._PrepareRequestArgs(instance_name)))
    (results, exceptions) = self.ExecuteRequests(requests)
    return (self.MakeListResult(results, 'operationList'), exceptions)


class ListInstances(InstanceCommand, command_base.GoogleComputeListCommand):
  """List the instances for a project."""

  is_global_level_collection = False
  is_zone_level_collection = True

  def ListFunc(self):
    """Returns the function for listing instances."""
    if self._IsUsingAtLeastApiVersion('v1beta14'):
      return None
    return self._instances_api.list

  def ListZoneFunc(self):
    """Returns the function for listing instances in a zone."""
    return self._instances_api.list


class AddAccessConfig(InstanceCommand):
  """Adds an access config to an instance's network interface."""

  positional_args = '<instance-name>'

  def __init__(self, name, flag_values):
    super(AddAccessConfig, self).__init__(name, flag_values)

    flags.DEFINE_string('network_interface_name',
                        self.DEFAULT_NETWORK_INTERFACE_NAME,
                        'The name of the instance\'s network interface to '
                        'which to add the new access config.',
                        flag_values=flag_values)

    flags.DEFINE_string('access_config_name',
                        self.DEFAULT_ACCESS_CONFIG_NAME,
                        'The name of the new access config.',
                        flag_values=flag_values)

    flags.DEFINE_string('access_config_type',
                        self.ONE_TO_ONE_NAT_ACCESS_CONFIG_TYPE,
                        'The type of the new access config. Currently only '
                        'type "ONE_TO_ONE_NAT" is supported.',
                        flag_values=flag_values)

    flags.DEFINE_string('access_config_nat_ip',
                        self.EPHEMERAL_ACCESS_CONFIG_NAT_IP,
                        'The external NAT IP of the new access config. The '
                        'default value "ephemeral" indicates the service '
                        'should choose an available ephemeral IP. If an '
                        'explicit IP is given, that IP must be reserved by '
                        'the project and not yet assigned to another instance.',
                        flag_values=flag_values)

  def Handle(self, instance_name):
    """Adds an access config to an instance's network interface.

    Args:
      instance_name: The instance name to which to add the new access config.

    Returns:
      An operation resource.
    """
    access_config_resource = {
        'name': self._flags.access_config_name,
        'type': self._flags.access_config_type,
        }
    if (self._flags.access_config_nat_ip.lower() !=
        self.EPHEMERAL_ACCESS_CONFIG_NAT_IP):
      access_config_resource['natIP'] = self._flags.access_config_nat_ip

    add_access_config_request = self._instances_api.addAccessConfig(
        **self._PrepareRequestArgs(
            instance_name,
            network_interface=self._flags.network_interface_name,
            body=access_config_resource))
    return add_access_config_request.execute()


class DeleteAccessConfig(InstanceCommand):
  """Deletes an access config from an instance's network interface."""

  positional_args = '<instance-name>'

  def __init__(self, name, flag_values):
    super(DeleteAccessConfig, self).__init__(name, flag_values)

    flags.DEFINE_string('network_interface_name',
                        self.DEFAULT_NETWORK_INTERFACE_NAME,
                        'The name of the instance\'s network interface from '
                        'which to delete the access config.',
                        flag_values=flag_values)

    flags.DEFINE_string('access_config_name',
                        self.DEFAULT_ACCESS_CONFIG_NAME,
                        'The name of the access config to delete.',
                        flag_values=flag_values)

  def Handle(self, instance_name):
    """Deletes an access config from an instance's network interface.

    Args:
      instance_name: The instance name from which to delete the access config.

    Returns:
      An operation resource.
    """
    delete_access_config_request = self._instances_api.deleteAccessConfig(
        **self._PrepareRequestArgs(
            instance_name,
            network_interface=self._flags.network_interface_name,
            access_config=self._flags.access_config_name))
    return delete_access_config_request.execute()


class SshInstanceBase(InstanceCommand):
  """Base class for SSH-based commands."""

  # We want everything after 'ssh <instance>' to be passed on to the
  # ssh command in question.  As such, all arguments to the utility
  # must come before the 'ssh' command.
  sort_args_and_flags = False

  def __init__(self, name, flag_values):
    super(SshInstanceBase, self).__init__(name, flag_values)

    flags.DEFINE_integer(
        'ssh_port',
        22,
        'TCP port to connect to',
        flag_values=flag_values)
    flags.DEFINE_multistring(
        'ssh_arg',
        [],
        'Additional arguments to pass to ssh',
        flag_values=flag_values)
    flags.DEFINE_integer(
        'ssh_key_push_wait_time',
        300,  # 5 minutes
        'Number of seconds to wait for updates to project-wide ssh keys '
        'to cascade to the instances within the project',
        flag_values=flag_values)

  def PrintResult(self, _):
    """Override the PrintResult to be a noop."""
    pass

  def _GetInstanceResource(self, instance_name):
    """Get the instance resource. This is the dictionary returned by the API.

    Args:
      instance_name: The name of the instance to retrieve the ssh address for.

    Returns:
      The data for the instance resource as returned by the API.

    Raises:
      command_base.CommandError: If the instance does not exist.
    """
    request = self._instances_api.get(
        **self._PrepareRequestArgs(instance_name))
    result = request.execute()
    if not result:
      raise command_base.CommandError(
          'Unable to find the instance %s.' % (instance_name))
    return result

  def _GetSshAddress(self, instance_resource):
    """Retrieve the ssh address from the passed instance resource data.

    Args:
      instance_resource: The resource data of the instance for which
        to retrieve the ssh address.

    Returns:
      The ssh address and port.

    Raises:
      command_base.CommandError: If the instance has no external address.
    """
    external_addresses = self._ExtractExternalIpFromInstanceRecord(
        instance_resource)
    if len(external_addresses) < 1:
      raise command_base.CommandError(
          'Cannot connect to an instance with no external address')

    return (external_addresses[0], self._flags.ssh_port)

  def _EnsureSshable(self, instance_resource):
    """Ensure that the user can ssh into the specified instance.

    This method checks if the instance has SSH keys defined for it, and if
    it does not this makes sure the enclosing project contains a metadata
    entry for the user's public ssh key.

    If the project is updated to add the user's ssh key, then this method
    waits for the amount of time specified by the wait_time_for_ssh_key_push
    flag for the change to cascade down to the instance.

    Args:
      instance_resource: The resource data for the instance to which to connect.

    Raises:
      command_base.CommandError: If the instance is not in the RUNNING state.
    """
    instance_status = instance_resource.get('status')
    if instance_status != 'RUNNING':
      raise command_base.CommandError(
          'Cannot connect to the instance since its current status is %s.'
          % instance_status)

    instance_metadata = instance_resource.get('metadata', {})

    instance_ssh_key_entries = (
        [entry for entry in instance_metadata.get(
            'items', [])
         if entry.get('key') == 'sshKeys'])

    if not instance_ssh_key_entries:
      if self._AddComputeKeyToProject():
        wait_time = self._flags.ssh_key_push_wait_time
        LOGGER.info('Updated project with new ssh key. It can take several '
                    'minutes for the instance to pick up the key.')
        LOGGER.info('Waiting %s seconds before attempting to connect.',
                    wait_time)
        time.sleep(wait_time)

  def _BuildSshCmd(self, instance_resource, command, args):
    """Builds the given SSH-based command line with the given arguments.

    A complete SSH-based command line is built from the given command,
    any common arguments, and the arguments provided. The value of
    each argument is formatted using a dictionary that contains the
    following keys: host and port.

    Args:
      instance_resource: The resource data of the instance for which
        to build the ssh command.
      command: the ssh-based command to run (e.g. ssh or scp)
      args: arguments for the command

    Returns:
      The command line used to perform the requested ssh operation.

    Raises:
      IOError: An error occured accessing SSH details.
    """
    (host, port) = self._GetSshAddress(instance_resource)
    values = {'host': host,
              'port': port,
              'user': self._flags.ssh_user}

    command_line = [
        command,
        '-o', 'UserKnownHostsFile=/dev/null',
        '-o', 'CheckHostIP=no',
        '-o', 'StrictHostKeyChecking=no',
        '-i', self._flags.private_key_file
    ] + self._flags.ssh_arg

    if LOGGER.level <= logging.DEBUG:
      command_line.append('-v')

    for arg in args:
      command_line.append(arg % values)

    return command_line

  def _RunSshCmd(self, instance_name, command, args):
    """Run the given SSH-based command line with the given arguments.

    The specified SSH-base command is run for the arguments provided.
    The value of each argument is formatted using a dictionary that
    contains the following keys: host and port.

    Args:
      instance_name: The name of the instance for which to run the ssh command.
      command: the ssh-based command to run (e.g. ssh or scp)
      args: arguments for the command

    Raises:
      IOError: An error occured accessing SSH details.
    """
    instance_resource = self._GetInstanceResource(instance_name)
    command_line = self._BuildSshCmd(instance_resource, command, args)
    try:
      self._EnsureSshable(instance_resource)
    except ssh_keys.UserSetupError as e:
      LOGGER.warn('Could not generate compute ssh key: %s', e)
      return

    LOGGER.info('Running command line: %s', ' '.join(command_line))
    try:
      os.execvp(command, command_line)
    except OSError as e:
      LOGGER.error('There was a problem executing the command: %s', e)


class SshToInstance(SshInstanceBase):
  """Ssh to an instance."""

  positional_args = '<instance-name> <ssh-args>'

  def _GenerateSshArgs(self, *argv):
    """Generates the command line arguments for the ssh command.

    Args:
      *argv: List of additional ssh command line args, if any.

    Returns:
      The complete ssh argument list.
    """
    ssh_args = ['-A', '-p', '%(port)d', '%(user)s@%(host)s', '--']

    escaped_args = [a.replace('%', '%%') for a in argv]
    ssh_args.extend(escaped_args)

    return ssh_args

  def Handle(self, instance_name, *argv):
    """SSH into the instance.

    Args:
      instance_name: The name of the instance to ssh to.
      *argv: The remaining unhandled arguments.

    Returns:
      The result of the ssh command
    """
    ssh_args = self._GenerateSshArgs(*argv)
    self._RunSshCmd(instance_name, 'ssh', ssh_args)


class PushToInstance(SshInstanceBase):
  """Push one or more files to an instance."""

  positional_args = '<instance-name> <file-1> ... <file-n> <destination>'

  def _GenerateScpArgs(self, *argv):
    """Generates the command line arguments for the scp command.

    Args:
      *argv: List of files to push and instance-relative destination.

    Returns:
      The scp argument list.

    Raises:
      command_base.CommandError: If an invalid number of arguments are passed
          in.
    """
    if len(argv) < 2:
      raise command_base.CommandError('Invalid number of arguments passed.')

    scp_args = ['-r', '-P', '%(port)d', '--']

    escaped_args = [a.replace('%', '%%') for a in argv]
    scp_args.extend(escaped_args[0:-1])
    scp_args.append('%(user)s@%(host)s:' + escaped_args[-1])

    return scp_args

  def Handle(self, instance_name, *argv):
    """Pushes one or more files into the instance.

    Args:
      instance_name: The name of the instance to push files to.
      *argv: The remaining unhandled arguments.

    Returns:
      The result of the scp command

    Raises:
      command_base.CommandError: If an invalid number of arguments are passed
        in.
    """
    scp_args = self._GenerateScpArgs(*argv)
    self._RunSshCmd(instance_name, 'scp', scp_args)


class PullFromInstance(SshInstanceBase):
  """Pull one or more files from an instance."""

  positional_args = '<instance-name> <file-1> ... <file-n> <destination>'

  def _GenerateScpArgs(self, *argv):
    """Generates the command line arguments for the scp command.

    Args:
      *argv: List of files to pull and local-relative destination.

    Returns:
      The scp argument list.

    Raises:
      command_base.CommandError: If an invalid number of arguments are passed
          in.
    """
    if len(argv) < 2:
      raise command_base.CommandError('Invalid number of arguments passed.')

    scp_args = ['-r', '-P', '%(port)d', '--']

    escaped_args = [a.replace('%', '%%') for a in argv]
    for arg in escaped_args[0:-1]:
      scp_args.append('%(user)s@%(host)s:' + arg)
    scp_args.append(escaped_args[-1])

    return scp_args

  def Handle(self, instance_name, *argv):
    """Pulls one or more files from the instance.

    Args:
      instance_name: The name of the instance to pull files from.
      *argv: The remaining unhandled arguments.

    Returns:
      The result of the scp command

    Raises:
      command_base.CommandError: If an invalid number of arguments are passed
          in.
    """
    scp_args = self._GenerateScpArgs(*argv)
    self._RunSshCmd(instance_name, 'scp', scp_args)


class GetSerialPortOutput(InstanceCommand):
  """Get the output of an instance's serial port."""

  positional_args = '<instance-name>'

  def Handle(self, instance_name):
    """Get the specified instance's serial port output.

    Args:
      instance_name: The name of the instance.

    Returns:
      The output of the instance's serial port.
    """
    if self._IsUsingAtLeastApiVersion('v1beta13'):
      instance_request = self._instances_api.getSerialPortOutput(
          **self._PrepareRequestArgs(instance_name))

      return instance_request.execute()
    else:
      raise app.UsageError(
          'Serial port output is only supported in v1beta13 and above.')

  def PrintResult(self, result):
    """Override the PrintResult to be a noop."""

    if self._flags.print_json:
      super(GetSerialPortOutput, self).PrintResult(result)
    else:
      print result['contents']




class OptimisticallyLockedInstanceCommand(InstanceCommand):
  """Base class for instance commands that require a fingerprint."""

  def __init__(self, name, flag_values):
    super(OptimisticallyLockedInstanceCommand, self).__init__(name, flag_values)

    flags.DEFINE_string('fingerprint',
                        None,
                        'Fingerprint of the data to be overwritten. '
                        'This fingerprint provides optimistic locking--'
                        'data will only be set if the given fingerprint '
                        'matches the state of the data prior to this request.',
                        flag_values=flag_values)

  def Handle(self, *args, **kwargs):
    """Invokes the HandleCommand method of the subclass."""
    if not self._flags.fingerprint:
      raise app.UsageError('You must provide a fingerprint with your request.')
    return self.HandleCommand(*args, **kwargs)


class SetMetadata(OptimisticallyLockedInstanceCommand):
  """Sets instance metadata and sends new metadata to instances.

  This method overwrites existing instance metadata with new metadata.
  Common metadata (project-wide) is preserved.

  For example, running:

    gcutil --project=<project-name> setinstancemetadata my-instance \
      --metadata="key1:value1" \
      --fingerprint=<original-fingerprint>
    ...
    gcutil --project=<project-name> setinstancemetadata my-instance \
      --metadata="key2:value2" \
      --fingerprint=<new-fingerprint>

  will result in 'my-instance' having 'key2:value2' as its metadata.
  """

  positional_args = '<instance-name>'

  def __init__(self, name, flag_values):
    super(SetMetadata, self).__init__(name, flag_values)

    flags.DEFINE_bool('force',
                      None,
                      'Set new metadata even if the key "sshKeys" will '
                      'no longer be present.',
                      flag_values=flag_values,
                      short_name='f')
    self._metadata_flags_processor = metadata.MetadataFlagsProcessor(
        flag_values)

  def HandleCommand(self, instance_name):
    """Set instance-specific metadata.

    Args:
      instance_name: The name of the instance scoping this request.

    Returns:
      An operation resource.
    """
    new_metadata = self._metadata_flags_processor.GatherMetadata()
    if not self._flags.force:
      new_keys = set([entry['key'] for entry in new_metadata])
      get_project = self._projects_api.get(project=self._project)
      project_resource = get_project.execute()
      project_metadata = project_resource.get('commonInstanceMetadata', {})
      project_metadata = project_metadata.get('items', [])
      project_keys = set([entry['key'] for entry in project_metadata])

      get_instance = self._instances_api.get(
          **self._PrepareRequestArgs(instance_name))
      instance_resource = get_instance.execute()
      instance_metadata = instance_resource.get('metadata', {})
      instance_metadata = instance_metadata.get('items', [])
      instance_keys = set([entry['key'] for entry in instance_metadata])

      if ('sshKeys' in instance_keys and 'sshKeys' not in new_keys
          and 'sshKeys' not in project_keys):
        raise command_base.CommandError(
            'Discarding update that would have erased instance sshKeys.'
            '\n\nRe-run with the -f flag to force the update.')

    metadata_resource = {'kind': self._GetResourceApiKind('metadata'),
                         'items': new_metadata,
                         'fingerprint': self._flags.fingerprint}

    set_metadata_request = self._instances_api.setMetadata(
        **self._PrepareRequestArgs(instance_name, body=metadata_resource))
    return set_metadata_request.execute()


class SetTags(OptimisticallyLockedInstanceCommand):
  """Sets instance tags and sends new tags to the instance.

  This method overwrites existing instance tags.

  For example, running:

    gcutil --project=<project-name> setinstancetags my-instance \
      --tags="tag-1" \
      --fingerprint=<original-fingerprint>
    ...
    gcutil --project=<project-name> setinstancetags my-instance \
      --tags="tag-2,tag-3" \
      --fingerprint=<new-fingerprint>

  will result in 'my-instance' having tags 'tag-2' and 'tag-3'.
  """

  def __init__(self, name, flag_values):
    super(SetTags, self).__init__(name, flag_values)

    flags.DEFINE_list('tags',
                      [],
                      'A set of tags applied to this instance. Used for '
                      'filtering and to configure network firewall rules '
                      '(comma separated).',
                      flag_values=flag_values)

  def HandleCommand(self, instance_name):
    """Set instance tags.

    Args:
      instance_name: The name of the instance scoping this request.

    Returns:
      An operation resource.
    """
    tag_resource = {'items': sorted(set(self._flags.tags)),
                    'fingerprint': self._flags.fingerprint}
    set_tags_request = self._instances_api.setTags(
        **self._PrepareRequestArgs(instance_name, body=tag_resource))
    return set_tags_request.execute()


def AddCommands():
  """Add all of the instance related commands."""

  appcommands.AddCmd('addinstance', AddInstance)
  appcommands.AddCmd('getinstance', GetInstance)
  appcommands.AddCmd('deleteinstance', DeleteInstance)
  appcommands.AddCmd('listinstances', ListInstances)
  appcommands.AddCmd('addaccessconfig', AddAccessConfig)
  appcommands.AddCmd('deleteaccessconfig', DeleteAccessConfig)
  appcommands.AddCmd('ssh', SshToInstance)
  appcommands.AddCmd('push', PushToInstance)
  appcommands.AddCmd('pull', PullFromInstance)
  appcommands.AddCmd('getserialportoutput', GetSerialPortOutput)
  appcommands.AddCmd('setinstancemetadata', SetMetadata)
  appcommands.AddCmd('setinstancetags', SetTags)
