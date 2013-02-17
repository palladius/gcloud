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

"""A set of utility functions."""

import cStringIO
import numbers
import socket
import sys




def SimpleName(entity):
  if entity is None:
    return ''

  elif isinstance(entity, basestring):
    if 'projects/google/' in entity:
      return 'google/' + entity.split('/')[-1]
    else:
      return entity.split('/')[-1]

  elif isinstance(entity, numbers.Number):
    return str(entity)

  raise ValueError('Expected number or string: ' + str(entity))


def FlattenList(list):
  """Flattens a list of lists."""
  return [item for sublist in list for item in sublist]


def RegexesToFilterExpression(regexes, op='eq'):
  """Converts a list of regular expressions to a filter expression on name.

  Args:
    regexes: A list of regular expressions to use for matching
      resource names. Since resource names cannot contain whitespace
      characters, regular expressions are split on whitespace (e.g.,
      '[a-z]+ [0-9]+' will be treated as two separate regular expressions).

  Returns:
    The Google Compute Engine filter expression or None
      if regexes evaluates to False.
  """
  if not regexes:
    return None
  regexes = FlattenList(regex.split() for regex in regexes)
  return 'name %s %s' % (op, '|'.join(regexes))


def SimplePrint(text, *args, **kwargs):
  """Prints the given text without a new-line character at the end."""
  print text.format(*args, **kwargs),
  sys.stdout.flush()


def ListStrings(strings, prefix='  '):
  """Returns a string containing each item in strings on its own line.

  Args:
    strings: The list of strings to place in the result.
    prefix: A string to place before each name.

  Returns:
    A string containing the names.
  """
  strings = sorted(strings)
  buf = cStringIO.StringIO()
  for string in strings:
    buf.write(prefix + str(string) + '\n')
  return buf.getvalue().rstrip()


def Proceed(message=None):
  """Prompts the user to proceed.

  Args:
    message: An optional message to include before
      'Proceed? [y/N] ' is printed.

  Returns:
    True if the user answers yes.
  """
  message = ((message or '') + ' Proceed? [y/N] ').lstrip()
  return raw_input(message).strip().lower() == 'y'


def ParseProtocol(protocol_string):
  """Attempt to parse a protocol number from a string.

  Args:
    protocol_string: The string to parse.

  Returns:
    The corresponding protocol number.

  Raises:
    ValueError: If the protocol_string is not a valid protocol string.
  """
  try:
    protocol = socket.getprotobyname(protocol_string)
  except (socket.error, TypeError):
    try:
      protocol = int(protocol_string)
    except (ValueError, TypeError):
      raise ValueError('Invalid protocol: %s' % protocol_string)

  return protocol


def ReplacePortNames(port_range_string):
  """Replace port names with port numbers in a port-range string.

  Args:
    port_range_string: The string to parse.

  Returns:
    A port range string specifying ports only by number.

  Raises:
    ValueError: If the port_range_string is the wrong type or malformed.
  """
  if not isinstance(port_range_string, basestring):
    raise ValueError('Invalid port range: %s' % port_range_string)

  ports = port_range_string.split('-')
  if len(ports) not in [1, 2]:
    raise ValueError('Invalid port range: %s' % port_range_string)

  try:
    low_port = socket.getservbyname(ports[0])
  except socket.error:
    low_port = int(ports[0])

  try:
    high_port = socket.getservbyname(ports[-1])
  except socket.error:
    high_port = int(ports[-1])

  if low_port == high_port:
    return '%d' % low_port
  else:
    return '%d-%d' % (low_port, high_port)


def Singularize(string):
  """A naive function for singularizing Compute Engine collection names."""
  return string[:len(string) - 1] if string.endswith('s') else string


def All(func, project, max_results=None, filter=None, zone=None):
  """Calls the given list function while taking care of paging logic.

  Args:
    func: A Google Compute Engine list function.
    project: The project to query.
    max_results: The maximum number of items to return.
    filter: The filter expression to plumb through.
    zone: The zone for list functions that require a zone.

  Returns:
    A list of the resources.
  """
  params = {
      'project': project,
      'maxResults': max_results,
      'filter': filter}

  if zone:
    params['zone'] = zone

  items = []
  while True:
    res = func(**params).execute()
    kind = res.get('kind')
    items.extend(res.get('items', []))

    next_page_token = res.get('nextPageToken')
    if not next_page_token:
      break

    params['pageToken'] = next_page_token

  if max_results is not None:
    items = items[:max_results]
  return {'kind': kind,
          'items': items}


def AllNames(func, project, max_results=None, filter=None, zone=None):
  """Like All, except returns a list of the names of the resources."""
  list_res = All(
      func, project, max_results=max_results, filter=filter, zone=zone)
  return [resource.get('name') for resource in list_res.get('items', [])]
