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

"""Tests for auth_helper."""



import path_initializer
path_initializer.InitializeSysPath()

import datetime


import apiclient
import oauth2client.client as oauth2_client
import oauth2client.multistore_file as oauth2_multistore_file
import oauth2client.tools as oauth2_tools

import gflags as flags
import unittest
from gcutil import auth_helper
from gcutil import mock_metadata


FLAGS = flags.FLAGS

CREDS_FILENAME = './unused_filename'


class AuthHelperTest(unittest.TestCase):

  class MockCred(object):
    pass

  class MockCredStorage(object):
    def __init__(self, cred):
      self.cred = cred

    def get(self):
      return self.cred

  @staticmethod
  def MockGetCredentialStorage(credentials_file,
                               client_id,
                               user_agent,
                               scopes):
    cred = AuthHelperTest.MockCred()
    storage = AuthHelperTest.MockCredStorage(cred)
    cred.credentials_file = credentials_file
    cred.client_id = client_id
    cred.user_agent = user_agent
    cred.scopes = scopes
    cred.invalid = False
    return storage

  @staticmethod
  def MockOAuthFlowRun(flow, unused_storage):
    cred = AuthHelperTest.MockCred()
    cred.client_id = flow.client_id
    cred.client_secret = flow.client_secret
    cred.scopes = flow.scope
    cred.user_agent = flow.user_agent
    return cred

  def setUp(self):
    FLAGS.credentials_file = CREDS_FILENAME

  def testGetValidCred(self):
    oauth2_multistore_file.get_credential_storage = (
        self.MockGetCredentialStorage)
    cred = auth_helper.GetCredentialFromStore(['a', 'b'])
    self.assertEqual(cred.credentials_file, CREDS_FILENAME)
    self.assertEqual(cred.client_id, auth_helper.OAUTH2_CLIENT_ID)
    self.assertEqual(cred.user_agent, auth_helper.USER_AGENT)
    self.assertEqual(cred.scopes, 'a b')
    self.assertEqual(cred.invalid, False)

  def testSortScopes(self):
    oauth2_multistore_file.get_credential_storage = (
        self.MockGetCredentialStorage)
    cred = auth_helper.GetCredentialFromStore(['b', 'a'])
    self.assertEqual(cred.credentials_file, CREDS_FILENAME)
    self.assertEqual(cred.client_id, auth_helper.OAUTH2_CLIENT_ID)
    self.assertEqual(cred.user_agent, auth_helper.USER_AGENT)
    self.assertEqual(cred.scopes, 'a b')
    self.assertEqual(cred.invalid, False)

  def testNoAskuser(self):
    oauth2_multistore_file.get_credential_storage = (
        self.MockGetCredentialStorage)
    cred = auth_helper.GetCredentialFromStore(['b', 'a'],
                                              force_reauth=True,
                                              ask_user=False)
    self.assertEqual(cred.credentials_file, CREDS_FILENAME)
    self.assertEqual(cred.client_id, auth_helper.OAUTH2_CLIENT_ID)
    self.assertEqual(cred.user_agent, auth_helper.USER_AGENT)
    self.assertEqual(cred.scopes, 'a b')
    self.assertEqual(cred.invalid, True)

  def testReauthFlow(self):
    oauth2_multistore_file.get_credential_storage = (
        self.MockGetCredentialStorage)
    oauth2_tools.run = self.MockOAuthFlowRun
    cred = auth_helper.GetCredentialFromStore(['b', 'a'],
                                              force_reauth=True,
                                              ask_user=True)
    self.assertEqual(cred.client_id, auth_helper.OAUTH2_CLIENT_ID)
    self.assertEqual(cred.client_secret, auth_helper.OAUTH2_CLIENT_SECRET)
    self.assertEqual(cred.user_agent, auth_helper.USER_AGENT)
    self.assertEqual(cred.scopes, 'a b')

  def testMetadataAuth(self):
    metadata = mock_metadata.MockMetadata()
    metadata.ExpectIsPresent(True)

    token = 'access token'
    expiry = datetime.datetime(1970, 1, 1)
    metadata.ExpectGetAccessToken((token, expiry))

    scope1 = 'https://www.googleapis.com/auth/compute'
    scope2 = 'scope2'

    metadata.ExpectGetAccessScopes([scope1, scope2])

    oauth2_multistore_file.get_credential_storage = (
        self.MockGetCredentialStorage)
    cred = auth_helper.GetCredentialFromStore([scope1, scope2],
                                              metadata=metadata)
    self.assertTrue(cred is not None)
    self.assertEquals(token, cred.access_token)
    self.assertEquals(expiry, cred.token_expiry)
    self.assertFalse(metadata.ExpectsMoreCalls())


if __name__ == '__main__':
  unittest.main()
