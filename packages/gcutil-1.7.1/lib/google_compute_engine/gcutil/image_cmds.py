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

"""Commands for interacting with Google Compute Engine machine images."""





from google.apputils import appcommands
import gflags as flags

from gcutil import command_base


FLAGS = flags.FLAGS



class ImageCommand(command_base.GoogleComputeCommand):
  """Base command for working with the images collection."""

  default_sort_field = 'name'
  summary_fields = (('name', 'name'),
                    ('description', 'description'),
                    ('creation-time', 'creationTimestamp'),
                    ('kernel', 'preferredKernel'))

  detail_fields = (('name', 'name'),
                   ('description', 'description'),
                   ('creation-time', 'creationTimestamp'),
                   ('kernel', 'preferredKernel'))

  resource_collection_name = 'images'

  def __init__(self, name, flag_values):
    super(ImageCommand, self).__init__(name, flag_values)

  def SetApi(self, api):
    """Set the Google Compute Engine API for the command.

    Args:
      api: The Google Compute Engine API used by this command.

    Returns:
      None.
    """
    self._images_api = api.images()
    self._kernels_api = api.kernels()


class AddImage(ImageCommand):
  """Create a new machine image.

  The root_source_tarball parameter must point to a tar file of the
  contents of the desired root directory stored in Google Storage.
  """

  positional_args = '<image-name> <root-source-tarball>'

  def __init__(self, name, flag_values):
    super(AddImage, self).__init__(name, flag_values)
    flags.DEFINE_string('description',
                        '',
                        'Image description',
                        flag_values=flag_values)
    flags.DEFINE_string('preferred_kernel',
                        None,
                        'Kernel name',
                        flag_values=flag_values)

  def Handle(self, image_name, root_source_tarball):
    """Add the specified image.

    Args:
      image_name: The name of the image to add.
      root_source_tarball: Tarball in Google Storage containing the
        desired root directory for the resulting image.

    Returns:
      The result of inserting the image.
    """

    # Accept gs:// URLs.
    if root_source_tarball.startswith('gs://'):
      root_source_tarball = ('http://storage.googleapis.com/' +
                             root_source_tarball[len('gs://'):])

    image_resource = {
        'kind': self._GetResourceApiKind('image'),
        'name': self.DenormalizeResourceName(image_name),
        'description': self._flags.description,
        'sourceType': 'RAW',
        'rawDisk': {
            'source': root_source_tarball,
            'containerType': 'TAR'
            }
        }

    if self._flags.preferred_kernel:
      image_resource['preferredKernel'] = self.NormalizeGlobalResourceName(
          self._project, 'kernels', self._flags.preferred_kernel)
    elif self._IsUsingAtLeastApiVersion('v1beta14'):
      kernel = self._PromptForKernel()
      image_resource['preferredKernel'] = kernel['selfLink']
    image_request = self._images_api.insert(project=self._project,
                                            body=image_resource)
    return image_request.execute()


class GetImage(ImageCommand):
  """Get a machine image."""

  positional_args = '<image-name>'

  def __init__(self, name, flag_values):
    super(GetImage, self).__init__(name, flag_values)

  def Handle(self, image_name):
    """GSet the specified image.

    Args:
      image_name: The name of the image to get.

    Returns:
      The result of getting the image.
    """
    image_request = self._images_api.get(
        project=self._project,
        image=self.DenormalizeResourceName(image_name))

    return image_request.execute()


class DeleteImage(ImageCommand):
  """Delete one or more machine images.

  If multiple image names are specified, the images will be deleted in parallel.
  """

  positional_args = '<image-name-1> ... <image-name-n>'
  safety_prompt = 'Delete image'

  def __init__(self, name, flag_values):
    super(DeleteImage, self).__init__(name, flag_values)

  def Handle(self, *image_names):
    """Delete the specified images.

    Args:
      *image_names: The names of the images to delete.

    Returns:
      Tuple (results, exceptions) - results of deleting the images.
    """
    requests = []
    for name in image_names:
      requests.append(self._images_api.delete(
          project=self._project,
          image=self.DenormalizeResourceName(name)))
    results, exceptions = self.ExecuteRequests(requests)
    return (self.MakeListResult(results, 'operationList'), exceptions)


class ListImages(ImageCommand, command_base.GoogleComputeListCommand):
  """List the images for a project."""

  def ListFunc(self):
    """Returns the function for listing images."""
    return self._images_api.list


class Deprecate(ImageCommand):
  """Sets the deprecation status for an image."""

  positional_args = '<image-name>'

  def __init__(self, name, flag_values):
    super(Deprecate, self).__init__(name, flag_values)
    flags.DEFINE_enum('state',
                      None,
                      ['DEPRECATED', 'OBSOLETE', 'DELETED'],
                      'The new deprecation state for this image. '
                      'Valid values are DEPRECATED, OBSOLETE, and '
                      'DELETED.  DEPRECATED resources will generate '
                      'a warning when new uses occur, OBSOLETE '
                      'and DELETED resources generate an error on '
                      'new uses.',
                      flag_values=flag_values)
    flags.DEFINE_string('replacement',
                        None,
                        'A valid full URL to a compute engine image. '
                        'Users of the deprecated image will be advised '
                        'to switch to this replacement.',
                        flag_values=flag_values)
    flags.DEFINE_string('deprecated_on',
                        None,
                        'A valid RFC 3339 full-date or date-time on which '
                        'the state of this resource became or will become '
                        'DEPRECATED.  For example:  2020-01-02T00:00:00Z for '
                        'midnight on January 2nd, 2020.',
                        flag_values=flag_values)
    flags.DEFINE_string('obsolete_on',
                        None,
                        'A valid RFC 3339 full-date or date-time on which '
                        'the state of this resource became or will become '
                        'OBSOLETE.  For example:  2020-01-02T00:00:00Z for '
                        'midnight on January 2nd, 2020.',
                        flag_values=flag_values)
    flags.DEFINE_string('deleted_on',
                        None,
                        'A valid RFC 3339 full-date or date-time on which '
                        'the state of this resource became or will become '
                        'DELETED.  For example:  2020-01-02T00:00:00Z for '
                        'midnight on January 2nd, 2020.',
                        flag_values=flag_values)

  def _BuildRequest(self, image_name):
    """Build a request to set deprecation status for the given image."""
    deprecation_status = {
        'state': self._flags.state,
        'replacement': self.NormalizeGlobalResourceName(
            self._project, 'images', self._flags.replacement),
        'deprecated': self._flags.deprecated_on,
        'obsolete': self._flags.obsolete_on,
        'deleted': self._flags.deleted_on,
        }
    return self._images_api.deprecate(
        project=self._project,
        image=self.DenormalizeResourceName(image_name),
        body=deprecation_status)

  def Handle(self, image_name):
    """Sets deprecation status on an image.

    Args:
      image_name: the name of the image for which deprecation will be set.

    Returns:
      An operation resource.
    """
    set_deprecation_request = self._BuildRequest(image_name)
    return set_deprecation_request.execute()


def AddCommands():
  appcommands.AddCmd('addimage', AddImage)
  appcommands.AddCmd('getimage', GetImage)
  appcommands.AddCmd('deleteimage', DeleteImage)
  appcommands.AddCmd('listimages', ListImages)
  appcommands.AddCmd('deprecateimage', Deprecate)
