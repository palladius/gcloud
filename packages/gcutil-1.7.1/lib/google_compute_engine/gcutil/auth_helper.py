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

"""Google Compute Engine specific helpers to use the common auth library."""



import os

import oauth2client.client as oauth2_client
import oauth2client.multistore_file as oauth2_multistore_file
import oauth2client.tools as oauth2_tools

import gflags as flags

from gcutil import auto_auth
from gcutil import metadata_lib

FLAGS = flags.FLAGS

# These identifieres are required as part of the OAuth2 spec but have
# limited utility with a command line tool.  Note that the secret
# isn't really secret here.  These are copied from the Identity tab on
# the Google APIs Console <http://code.google.com/apis/console>
OAUTH2_CLIENT_ID = '1025389682001.apps.googleusercontent.com'
OAUTH2_CLIENT_SECRET = 'xslsVXhA7C8aOfSfb6edB6p6'
USER_AGENT = 'google-compute-cmdline/1.0'



flags.DEFINE_string(
    'credentials_file',
    '~/.gcutil_auth',
    'File where user authorization credentials are stored.')

flags.DEFINE_string(
    'auth_service_account',
    'default',
    'Service account to use for automatic authorization. '
    'Empty string disables automatic authorization.')

flags.DEFINE_string(
    'authorization_uri_base',
    'https://accounts.google.com/o/oauth2',
    'The base URI for authorization requests')


def GetCredentialFromStore(scopes,
                           ask_user=True,
                           force_reauth=False,
                           credentials_file=None,
                           authorization_uri_base=None,
                           client_id=OAUTH2_CLIENT_ID,
                           client_secret=OAUTH2_CLIENT_SECRET,
                           user_agent=USER_AGENT,
                           metadata=metadata_lib.Metadata(),
                           logger=None):
  """Get OAuth2 credentials for a specific scope.

  Args:
    scopes: A list of OAuth2 scopes to request.
    ask_user: If True, prompt the user to authenticate.
    force_reauth: If True, force users to reauth
    credentials_file: The file to use to get/store credentials. If left at None
      FLAGS.credentials_file will be used.
    authorization_uri_base: The base URI for auth requests. If left at None
      FLAGS.authorization_uri_base will be used.
    client_id: The OAuth2 client id
    client_secret: The OAuth2 client secret
    user_agent: The user agent for requests

  Returns:
    An OAuth2Credentials object or None
  """
  if not credentials_file:
    credentials_file = FLAGS.credentials_file
  if not authorization_uri_base:
    authorization_uri_base = FLAGS.authorization_uri_base

  # Ensure that the directory to contain the credentials file exists.
  credentials_dir = os.path.expanduser(os.path.dirname(credentials_file))
  if not os.path.exists(credentials_dir):
    os.makedirs(credentials_dir)


  scopes = sorted(scopes)
  scopes_str = ' '.join(scopes)

  metadata_present = False
  if FLAGS.auth_service_account:
    metadata_present = metadata.IsPresent()

  if FLAGS.auth_service_account and metadata_present:
    try:
      return auto_auth.Credentials(
          metadata,
          FLAGS.auth_service_account,
          scopes,
          any_available=True)
    except auto_auth.CredentialsNotPresentError, e:
      pass
    except auto_auth.CredentialsError, e:
      # We failed to get the scopes from the metadata server.
      if logger:
        logger.warn('Failed to automatically authenticate with service '
                    'account: %s' % (e))

  storage = oauth2_multistore_file.get_credential_storage(
      credentials_file, client_id, user_agent, scopes_str)

  credentials = storage.get()

  if force_reauth and credentials:
    credentials.invalid = True
  if (not credentials or credentials.invalid == True) and ask_user:

    if FLAGS.auth_service_account and metadata_present:
      print ('Service account scopes are not enabled for %s on this instance. '
             'Using manual authentication.') % (FLAGS.auth_service_account)

    flow = oauth2_client.OAuth2WebServerFlow(
        client_id=client_id,
        client_secret=client_secret,
        scope=scopes_str,
        user_agent=user_agent,
        auth_uri=authorization_uri_base + '/auth',
        token_uri=authorization_uri_base + '/token')
    credentials = oauth2_tools.run(flow, storage)
  return credentials
