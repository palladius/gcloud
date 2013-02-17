#!/usr/bin/python
#
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

"""Tests for auto_auth."""



import path_initializer
path_initializer.InitializeSysPath()

import datetime

import unittest
from gcutil import auto_auth
from gcutil import mock_metadata

SCOPE1 = 'https://www.googleapis.com/auth/compute'
SCOPE2 = 'https://www.googleapis.com/auth/devstorage.full_control'

class GoogleComputeAutoAuthTest(unittest.TestCase):

  def testCredentials(self):
    metadata = mock_metadata.MockMetadata()

    token1 = 'access token1'
    expiry1 = datetime.datetime(1970, 1, 1)
    token2 = 'access token2'
    expiry2 = datetime.datetime(1970, 1, 2)

    metadata.ExpectGetAccessScopes([SCOPE1, SCOPE2])
    metadata.ExpectGetAccessToken((token1, expiry1))
    metadata.ExpectGetAccessToken((token2, expiry2))

    credentials = auto_auth.Credentials(
        metadata, 'default', [SCOPE1, SCOPE2])
    self.assertTrue(SCOPE1 in credentials.available_scopes)
    self.assertTrue(SCOPE2 in credentials.available_scopes)
    self.assertEquals(2, len(credentials.available_scopes))
    self.assertEquals(token1, credentials.access_token)
    self.assertEquals(expiry1, credentials.token_expiry)

    credentials._refresh(None)
    self.assertEquals(token2, credentials.access_token)
    self.assertEquals(expiry2, credentials.token_expiry)

    self.assertFalse(metadata.ExpectsMoreCalls())

  def testWithNoComputeScope(self):
    metadata = mock_metadata.MockMetadata()
    metadata.ExpectGetAccessScopes([SCOPE2])

    success = False
    try:
      credentials = auto_auth.Credentials(
          metadata, 'default', [SCOPE2])
    except auto_auth.CredentialsNotPresentError:
      success = True
    self.assertTrue(success, 'Failed to throw exception without compute scope')


if __name__ == '__main__':
  unittest.main()
