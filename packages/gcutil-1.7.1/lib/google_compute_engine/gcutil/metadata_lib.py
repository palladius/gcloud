#!/usr/bin/python2.4
#
# Copyright 2011 Google Inc. All Rights Reserved.
#

"""Helper module for fetching metadata variables."""



import datetime
import json
import urllib2


class MetadataError(Exception):
  """Base class for metadata errors."""
  pass


class NoMetadataServerError(MetadataError):
  """Metadata server is not responding."""
  pass


class MetadataNotFoundError(MetadataError):
  """Metadata not present."""
  pass


class Metadata(object):
  """Client API for the metadata server."""

  DEFAULT_METADATA_URL = 'http://metadata.google.internal/0.1/meta-data'

  def __init__(self, server_address=DEFAULT_METADATA_URL):
    """Construct a Metadata client.

    Args:
      server_address: The address of the metadata server.
    """
    self._server_address = server_address

  def IsPresent(self):
    """Return whether the metadata server is ready and available."""
    try:
      self.GetInstanceId(timeout=1)
      return True
    except MetadataError:
      return False

  def GetAttribute(self, path, **kwargs):
    """Return a string value from the attributes/ subpath.

    Args:
      path: A subpath under attributes/ on the metadata server.

    Returns:
      The metadata value.

    Raises:
      MetadataError on failure.
    """
    return self.GetValue('attributes/%s' % (path), **kwargs)

  def GetValue(self, path, **kwargs):
    """Return a string value from the metadata server.

    Args:
      path: The path of the variable.

    Returns:
      The metadata value.

    Raises:
      MetadataError on failure.
      MetadataNotFoundError if the metadata path is not present.
      NoMetadataServerError if the metadata server does not seem to be present.
    """
    url = '%s/%s' % (self._server_address, path)
    req = urllib2.Request(url)
    try:
      return self._DoHttpRequestRead(req, **kwargs)
    except urllib2.URLError as e:
      try:
        if e.reason.errno == 111:
          raise NoMetadataServerError('Metadata server not responding')
        if e.reason.errno == -2:
          raise NoMetadataServerError('Metadata server not resolving')
      except AttributeError:
        pass

      raise MetadataError('URLError %s: %s' % (url, e))
    except urllib2.HTTPError as e:
      if e.code == 404:
        raise MetadataNotFoundError('Metadata not found: %s' % (path))
      raise MetadataError(
          'Failed to get value %s: %s %s' % (path, e.code, e.reason))

  def GetJSONValue(self, path, **kwargs):
    """Return a decoded JSON value from the metadata server.

    Args:
      path: The path of the variable.

    Returns:
      A json-decoded object.

    Raises:
      MetadataError on failure.
      MetadataNotFoundError if the metadata path is not present.
      NoMetadataServerError if the metadata server does not seem to be present.
    """
    try:
      return json.loads(self.GetValue(path, **kwargs))
    except ValueError as e:
      raise MetadataError('Failed to parse JSON: %s', e)

  def GetAccessScopes(self, restrict_scopes=None,
                      service_account='default'):
    """Return available scopes for service_account.

    Args:
      restrict_scopes: Only check for these scopes.
      service_account: The service_account to get scopes for.

    Return:
      A list of scopes.

    Raises:
      MetadataError on failure.
    """
    service_account_info = self.GetJSONValue(
        'service-accounts/%s' % service_account)
    scope_set = set(service_account_info['scopes'])
    if restrict_scopes is not None:
      scope_set = scope_set.intersection(set(restrict_scopes))
    return list(scope_set)

  def GetAccessToken(self, scopes, service_account='default',
                     any_available=False):
    """Get an access token.

    Args:
      scopes: The set of scopes desired in the access token.
      service_account: The service account to use.
      any_available: Allow only a subset of scopes to be in access token.

    Returns:
      (access-token, expiry-time). Expiry time is a datetime that may be None.

    Raises:
      MetadataError on failure.
      MetadataNotFoundError if the token is not present.
    """
    if any_available:
      scopes = self.GetAccessScopes(service_account=service_account,
                                    restrict_scopes=scopes)
    path = 'service-accounts/%s/acquire?scopes=%s' % (
        service_account, '%20'.join(scopes))
    token_info = self.GetJSONValue(path)
    if 'accessToken' not in token_info:
      raise MetadataError('Could not find accessToken in response.')

    def ExtractExpiry(name):
      """Try to extract a numeric field name from token_info."""
      if name in token_info:
        try:
          return int(token_info[name])
        except ValueError:
          raise MetadataError(
              '%s field %s is non-numeric' % (name, token_info[name]))
      return None

    # If response provides expiresAt, use it.
    expires_at = ExtractExpiry('expiresAt')
    if expires_at:
      expires_at = datetime.datetime.utcfromtimestamp(expires_at)
    else:
      # Otherwise, look for an expiresIn and use it.
      expires_in = ExtractExpiry('expiresIn')
      if expires_in:
        if expires_in > 1000000000:
          expires_at = datetime.datetime.utcfromtimestamp(expires_in)
        else:
          expires_at = (datetime.datetime.utcnow() +
                        datetime.timedelta(seconds=expires_in))

    return (token_info['accessToken'], expires_at)

  def AuthHttpRequest(self, http_request, scopes, service_account='default',
                      any_available=False):
    """Add an authorization header to an http request.

    Args:
      http_request: A urllib2 HTTP Request.
      scopes: The scopes desired on the access token.
      service_account: Which service_account to use.
      any_available: Allow only a subset of scopes to be in access token.

    Returns:
      Whether we successfully authorized the request.

    Raises:
      MetadataError on failure.
    """
    (token, expiry) = self.GetAccessToken(scopes,
                                          service_account=service_account,
                                          any_available=any_available)
    http_request.headers['Authorization'] = ('OAuth %s' % (token))
    return True

  def GetUserKeys(self, **kwargs):
    """Get the current user keys from the metadata server.

    Returns:
      A dictionary mapping user names to their ssh keys.

    Raises:
      MetadataError on failure.
    """
    keys = self.GetValue('attributes/sshKeys', **kwargs)
    keyof = lambda line: line.split(':', 1)[0]
    return dict(map(lambda line: (keyof(line), line), keys.splitlines()))

  def GetAttachedDisks(self, **kwargs):
    """Get the set of disks attached to the VM.

    Returns:
      A list of the disks attached to the VM.

    Raises:
      MetadataError on failure.
    """
    data = self.GetJSONValue('attached-disks', **kwargs)
    if 'disks' not in data:
      raise MetadataError('No disks in attached-disks')
    return data['disks']

  def GetInstanceId(self, **kwargs):
    """Return the unique instance id of this VM.

    Returns:
      The unique instance id of this VM.

    Raises:
      MetadataError on failure.
    """
    return self.GetValue('instance-id', **kwargs)

  def GetNumericProjectId(self, **kwargs):
    """Return the numeric project ID for this VM.

    This value is typically useful for Google Storage "legacy access."
    Other uses should probably use GetProjectId().

    Returns:
      The numeric project ID for this VM.

    Raises:
      MetadataError on failure.
    """
    return self.GetValue('numeric-project-id', **kwargs)

  def GetProjectId(self, **kwargs):
    """Return the unique name of the project for this VM.

    Returns:
      The unique name of the project for this VM.

    Raises:
      MetadataError on failure.
    """
    return self.GetValue('project-id', **kwargs)

  def GetHostname(self, **kwargs):
    """Get the hostname of the VM.

    Returns:
      The hostname of the VM.

    Raises:
      MetadataError on failure.
    """
    return self.GetValue('hostname', **kwargs)

  def GetTags(self, **kwargs):
    """Return the list of tags for the VM.

    Returns:
      The list of tags for this VM.

    Raises:
      MetadataError on failure.
    """
    return self.GetJSONValue('tags', **kwargs)

  def GetZone(self, **kwargs):
    """Return the zone of the VM.

    Returns:
      The zone this VM is running in.

    Raises:
      MetadataError on failure.
    """
    return self.GetValue('zone', **kwargs)

  def GetImage(self, **kwargs):
    """Return the name of this VM's disk image.

    Returns:
      The name of this VM's disk image.

    Raises:
      MetadataError on failure.
    """
    return self.GetValue('image')

  def GetMachineType(self, **kwargs):
    """Return the name of this VM's machine type.

    Returns:
      The name of this VM's machine type.

    Raises:
      MetadataError on failure.
    """
    return self.GetValue('machine-type', **kwargs)

  def GetDescription(self, **kwargs):
    """Return the description associated with this VM.

    Returns:
      The description associated with this VM.

    Raises:
      MetadataError on failure.
    """
    return self.GetValue('description', **kwargs)

  def GetNetwork(self, **kwargs):
    """Return the network configuration for this VM.

    Returns:
      The network configuration for this VM.

    Raises:
      MetadataError on failure.
    """
    return self.GetJSONValue('network', **kwargs)

  def _DoHttpRequestRead(self, request, timeout=None):
    """Open and return contents of an http request."""
    if timeout is None:
      return urllib2.urlopen(request).read()
    else:
      return urllib2.urlopen(request, timeout=timeout).read()
