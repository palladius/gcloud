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

"""Test utilities for mocking out metadata_lib.Metadata."""




class MockMetadata(object):
  def __init__(self):
    self._is_present_calls = []
    self._get_access_token_calls = []
    self._get_access_scopes_calls = []
    self._is_present_return_values = []
    self._get_access_token_return_values = []
    self._get_access_scopes_return_values = []

  def ExpectIsPresent(self, and_return):
    self._is_present_return_values.append(and_return)

  def ExpectGetAccessToken(self, and_return):
    self._get_access_token_return_values.append(and_return)

  def ExpectGetAccessScopes(self, and_return):
    self._get_access_scopes_return_values.append(and_return)

  def IsPresent(self):
    self._is_present_calls.append({})
    return self._is_present_return_values.pop(0)

  def GetAccessToken(self, scopes, service_account='default',
                     any_available=True):
    self._get_access_token_calls.append(
        {'scopes': ' '.join(scopes),
         'service_account': service_account,
         'any_available': any_available})
    return self._get_access_token_return_values.pop(0)

  def GetAccessScopes(self, service_account='default'):
    self._get_access_scopes_calls.append(
        {'service_account': service_account})
    return self._get_access_scopes_return_values.pop(0)

  def ExpectsMoreCalls(self):
    return sum(map(len, [self._is_present_return_values,
                         self._get_access_token_return_values,
                         self._get_access_scopes_return_values])) > 0
