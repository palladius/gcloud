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

"""A module can check for new versions of gcutil.

A JSON file located at VERSION_INFO_URL contains the version number of
the latest version of gcutil.
"""



import json
import logging
import os
import time

import httplib2

import gflags as flags

from gcutil import gcutil_logging
from gcutil import version

LOGGER = gcutil_logging.LOGGER
VERSION_INFO_URL = 'http://dl.google.com/compute/latest-version.json'
VERSION_CACHE_FILE = '~/.gcutil.version'
SETUP_DOC_URL = 'https://developers.google.com/compute/docs/gcutil'
TIMEOUT_IN_SEC = 1

# The minimum amount of time that can pass between visits to
# VERSION_INFO_URL to grab the latest version string.
CACHE_TTL_SEC = 24 * 60 * 60

FLAGS = flags.FLAGS

flags.DEFINE_boolean('check_for_new_version',
                     True,
                     'Perform an update check.')


class VersionChecker(object):
  """A class that encapsulates the logic for performing version checks."""

  def __init__(
      self,
      perform_check=FLAGS.check_for_new_version,
      cache_path=VERSION_CACHE_FILE,
      cache_ttl_sec=CACHE_TTL_SEC,
      current_version=version.__version__):
    """Constructs a new VersionChecker.

    Args:
      perform_check: Skips the check if False.
      cache_path: The path to a file that caches the results of
        fetching VERSION_INFO_URL.
      cache_ttl_sec: The maximum amount of time the cache is considered
        valid.
    """
    self._perform_check = perform_check
    self._cache_path = os.path.expanduser(cache_path)
    self._cache_ttl_sec = cache_ttl_sec
    self._current_version = current_version

  @staticmethod
  def _IsCacheMalformed(cache):
    """Returns True if the given cache is not in its expected form."""
    if ('last_check' not in cache or
        'current_version' not in cache or
        'last_checked_version' not in cache):
      return True

    if not isinstance(cache['last_check'], float):
      return True

    try:
      VersionChecker._ParseVersionString(cache['current_version'])
      VersionChecker._ParseVersionString(cache['last_checked_version'])
    except BaseException:
      return True

    return False

  def _IsCacheStale(self, cache, current_time=None):
    """Returns True if the cache is stale."""
    if VersionChecker._IsCacheMalformed(cache):
      LOGGER.debug('Encountered malformed or empty cache: %s', cache)
      return True

    # If the gcutil version has changed since the last cache write, then
    # the cache is stale.
    if cache['current_version'] != self._current_version:
      return True

    current_time = time.time() if current_time is None else current_time

    # If the cache is old, then it's stale.
    if cache['last_check'] + self._cache_ttl_sec <= current_time:
      return True

    # If for some reason the current time is less than the last time
    # the cache was written to (e.g., the user changed his or her
    # system time), then the safest thing to do is to assume the cache
    # is stale.
    if cache['last_check'] > current_time:
      return True

    return False

  @staticmethod
  def _ParseVersionString(version_string):
    """Converts a version string into a tuple of its components.

    For example, '1.2.0' -> (1, 2, 0).

    Args:
      version_string: The input.

    Raises:
      ValueError: If any of the version components are not integers.

    Returns:
      A tuple of the version components.
    """
    try:
      return tuple([int(i) for i in version_string.split('.')])
    except ValueError as e:
      raise ValueError('Could not parse version string %s: %s' %
                       (version_string, e))

  @staticmethod
  def _CompareVersions(left, right):
    """Returns True if the left version is less than the right version."""
    return (VersionChecker._ParseVersionString(left) <
            VersionChecker._ParseVersionString(right))

  def _UpdateCache(self, cache, http=None, current_time=None):
    """Fetches the version info and updates the given cache dict.

    Args:
      cache: A dict representing the contents of the cache.
      http: An httplib2.Http object. This is used for testing.
      current_time: The current time since the Epoch, in seconds.
        This is also used for testing.

    Raises:
      ValueError: If the response code is not 200.
    """
    http = http or httplib2.Http(timeout=TIMEOUT_IN_SEC)
    response, content = http.request(
        VERSION_INFO_URL, headers={'Cache-Control': 'no-cache'})
    LOGGER.debug('Version check response: %s', response)
    LOGGER.debug('Version check payload: %s', content)
    if response.status != 200:
      raise ValueError('Received response code %s while fetching %s.',
                       response.status, VERSION_INFO_URL)

    latest_version = json.loads(content)['version']
    cache['current_version'] = self._current_version
    cache['last_checked_version'] = latest_version
    cache['last_check'] = current_time or time.time()

  def _ReadCache(self):
    """Reads the contents of the version cache file.

    Returns:
      A dict that corresponds to the JSON stored in the cache file.
      Returns an empty dict if the cache file does not exist or if
      there is a problem reading/parsing the cache.
    """
    if not os.path.exists(self._cache_path):
      return {}

    try:
      with open(self._cache_path) as f:
        return json.load(f)
    except BaseException as e:
      LOGGER.debug('Reading %s failed: %s', self._cache_path, e)

    return {}

  def _WriteToCache(self, cache):
    """JSON-serializes the given dict and writes it to the cache."""
    with open(self._cache_path, 'w') as f:
      json.dump(cache, f)

  def _NewVersionExists(self):
    """Returns True if a new gcutil version exists."""
    cache = self._ReadCache()
    if self._IsCacheStale(cache):
      LOGGER.debug('%s is stale. Consulting %s for latest version info...',
                    self._cache_path, VERSION_INFO_URL)
      self._UpdateCache(cache)
      self._WriteToCache(cache)
    else:
      LOGGER.debug('Consulting %s for latest version info...', self._cache_path)

    latest_version = cache['last_checked_version']
    ret = self._CompareVersions(self._current_version, latest_version)
    return ret

  def CheckForNewVersion(self):
    """Performs the actual check for a new version.

    This method may either consult the cache or the web, depending on
    the cache's age.

    The side-effect of this message is a WARN log that tells the user
    of an old version.

    Returns:
      True if version checking was requested and a new version is
      available.
    """
    if not self._perform_check:
      logging.debug('Skipping version check...')
      return

    LOGGER.debug('Performing version check...')

    try:
      if self._NewVersionExists():
        LOGGER.warning(
            'There is a new version of gcutil available. Go to: %s',
            SETUP_DOC_URL)
        LOGGER.warning(
            'Your version of gcutil is %s, the latest version is %s.',
            version.__version__, latest_version)
      else:
        LOGGER.debug('gcutil is up-to-date.')

    # So much can go wrong with this code that it's unreasonable to
    # add error handling everywhere hence the "catch-all" exception
    # handling.
    except BaseException as e:
      LOGGER.debug('Version checking failed: %s', e)
