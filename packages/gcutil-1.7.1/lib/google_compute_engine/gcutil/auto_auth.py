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

"""Interface for accessing auto-provided Google Compute Engine access tokens.

Once a Google Compute Engine instance has been started with
   --service_account=default \
   --service_account_scopes="...."

This module allows access tokens for the specified account and scopes to be
fetched from the Google Compute Engine instance automatically.
"""


import json
import logging

import apiclient
import httplib2
import oauth2client.client as oauth2client

from gcutil import metadata_lib
from gcutil import scopes


_logger = logging.getLogger(__name__)


class CredentialsError(oauth2client.Error):
  """Credentials could not be instantiated."""
  pass


class CredentialsNotPresentError(CredentialsError):
  """Credentials are not present."""
  pass


class Credentials(oauth2client.OAuth2Credentials):
  """Credentials object that gets credentials from Google Compute Engine."""

  def __init__(self, metadata, service_account, requested_scopes,
               available_scopes=None, access_token=None, token_expiry=None,
               any_available=False):
    self._metadata = metadata
    self.service_account = service_account
    self.requested_scopes = requested_scopes
    self.available_scopes = available_scopes
    self.any_available = any_available

    if access_token:
      self.invalid = False
    else:
      self.invalid = True
      try:
        # Check to see if the tokens are there for fetching.
        available_scopes = self._metadata.GetAccessScopes(
            service_account=self.service_account)
        # Keep track of whatever scopes were actually present.
        self.available_scopes = list(
            set(available_scopes).intersection(set(self.requested_scopes)))

        # Check that we have compute scopes.
        def HasComputeScope(scope_list):
          return (scopes.COMPUTE_RW_SCOPE in scope_list) or (
              scopes.COMPUTE_RO_SCOPE in scope_list)

        if not HasComputeScope(self.available_scopes):
          raise CredentialsNotPresentError('No compute scopes available')

        (access_token, token_expiry) = self._InternalRefresh()
      except metadata_lib.MetadataNotFoundError, e:
        # Metadata server says token is not present.
        raise CredentialsNotPresentError('Service account not found')
      except metadata_lib.MetadataError, e:
        raise CredentialsError('Metadata server failure: %s', e)

    oauth2client.OAuth2Credentials.__init__(
        self,
        access_token,
        None,
        None,
        None,
        token_expiry,
        None,
        None)
    self.invalid = False

  def _refresh(self, _):
    (self.access_token, self.token_expiry) = self._InternalRefresh()

  def _InternalRefresh(self):
    try:
      self.invalid = False
      return self._metadata.GetAccessToken(
          self.requested_scopes, service_account=self.service_account,
          any_available=self.any_available)
    except metadata_lib.MetadataError:
      self.invalid = True
      return (None, None)

  @classmethod
  def from_json(cls, s):
    """Create an Credentials from a json string.

    Args:
      s: The json string.
    Returns:
      An Credentials object.
    """
    data = json.loads(s)
    return Credentials(
        metadata_lib.Metadata(),
        data['service_account'],
        data['requested_scopes'],
        data['available_scopes'],
        data['access_token'],
        data['token_expiry'],
        data['any_available'])
