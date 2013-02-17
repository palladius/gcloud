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

"""Commands for interacting with Google Compute Engine."""



import httplib2
import json


from google.apputils import appcommands
import gflags as flags

from gcutil import auth_helper
from gcutil import command_base
from gcutil import gcutil_logging
from gcutil import metadata
from gcutil import scopes
from gcutil import version


FLAGS = flags.FLAGS
LOGGER = gcutil_logging.LOGGER


class ProjectCommand(command_base.GoogleComputeCommand):
  """Base command for working with the projects collection."""

  default_sort_field = 'name'
  summary_fields = (('name', 'name'),
                    ('ips', 'externalIpAddresses'))

  def __init__(self, name, flag_values):
    super(ProjectCommand, self).__init__(name, flag_values)

  def SetApi(self, api):
    """Set the Google Compute Engine API for the command.

    Args:
      api: The Google Compute Engine API used by this command.

    Returns:
      None.

    """
    self._projects_api = api.projects()

  def CustomizePrintResult(self, result, table):
    """Customized result printing for this type.

    Args:
      result: json dictionary returned by the server
      table: the pretty printing table to be customized

    Returns:
      None.

    """
    # Add the quotas
    table.AddRow(('', ''))
    table.AddRow(('usage', ''))
    for quota in result.get('quotas', []):
      table.AddRow(('  %s' % quota['metric'].lower().replace('_', '-'),
                    '%s/%s' % (str(quota['usage']), str(quota['limit']))))
    # Add the metadata
    if result.get('commonInstanceMetadata', []):
      table.AddRow(('', ''))
      table.AddRow(('common-instance-metadata', ''))
      metadata_container = result.get('commonInstanceMetadata', [])
      if 'kind' in metadata_container:
        metadata_container = metadata_container.get('items', [])
      for metadata_entry in metadata_container:
        table.AddRow(('  %s' % metadata_entry.get('key', ''),
                      self._PresentElement(metadata_entry.get('value', ''))))


class GetProject(ProjectCommand):
  """Get the resource for a Google Compute Engine project."""

  positional_args = '<project-name>'

  # The remaining complex fields are filled in via CustomizePrintResult
  detail_fields = (('name', 'name'),
                   ('description', 'description'),
                   ('creation-time', 'creationTimestamp'),
                   ('ips', 'externalIpAddresses'))

  def __init__(self, name, flag_values):
    super(GetProject, self).__init__(name, flag_values)

  def Handle(self, project=None):
    """Get the specified project.

    Args:
      project: The project for which to get defails.

    Returns:
      The result of getting the project.
    """
    project = project or self._flags.project
    project_request = self._projects_api.get(project=project)
    return project_request.execute()


class SetCommonInstanceMetadata(ProjectCommand):
  """Set the commonInstanceMetadata field for a Google Compute Engine project.

  This is a blanket overwrite of all of the project wide metadata.
  """

  def __init__(self, name, flag_values):
    super(SetCommonInstanceMetadata, self).__init__(name, flag_values)
    flags.DEFINE_bool('force',
                      False,
                      'Set the metadata even if it erases existing keys',
                      flag_values=flag_values,
                      short_name='f')
    self._metadata_flags_processor = metadata.MetadataFlagsProcessor(
        flag_values)

  def Handle(self):
    """Set the metadata common to all instances in the specified project.

    Args:
      None.

    Returns:
      The result of setting the project wide metadata.

    Raises:

      command_base.CommandError: If the update would cause some metadata to
        be deleted.
    """
    new_metadata = self._metadata_flags_processor.GatherMetadata()

    if not self._flags.force:
      get_request = self._projects_api.get(project=self._flags.project)
      project_resource = get_request.execute()
      project_metadata = project_resource.get('commonInstanceMetadata', [])
      if 'kind' in project_metadata:
        project_metadata = project_metadata.get('items', [])
      existing_keys = set([entry['key'] for entry in project_metadata])
      new_keys = set([entry['key'] for entry in new_metadata])
      dropped_keys = existing_keys - new_keys
      if dropped_keys:
        raise command_base.CommandError(
            'Discarding update that would wipe out the following metadata: %s.'
            '\n\nRe-run with the -f flag to force the update.' %
            ', '.join(list(dropped_keys)))

    project_request = self._projects_api.setCommonInstanceMetadata(
        project=self._flags.project,
        body={'kind': self._GetResourceApiKind('metadata'),
              'items': new_metadata})
    return project_request.execute()


def AddCommands():
  appcommands.AddCmd('getproject', GetProject)
  appcommands.AddCmd('setcommoninstancemetadata', SetCommonInstanceMetadata)
