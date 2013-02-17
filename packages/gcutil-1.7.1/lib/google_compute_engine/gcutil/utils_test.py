"""Unit tests for the utils module."""



import path_initializer
path_initializer.InitializeSysPath()

import unittest

from gcutil import mock_api
from gcutil import utils


class FlattenListTests(unittest.TestCase):
  """Tests for utils.FlattenList."""
  test_cases = (
      ([[1], [2], [3]], [1, 2, 3]),
      ([[1, 2, 3], [4, 5], [6]], [1, 2, 3, 4, 5, 6]),
      ([['a'], ['    b '], ['c       ']], ['a', '    b ', 'c       ']),
      )

  def testFlattenList(self):
    for arg, expected in self.test_cases:
      self.assertEqual(utils.FlattenList(arg), expected)


class GlobsToFilterTests(unittest.TestCase):
  """Tests for utils.RegexesToFilterExpression."""
  test_cases = (
      (None, None),
      ([], None),
      (['instance-1'], 'name eq instance-1'),
      (['instance-1 instance-2'], 'name eq instance-1|instance-2'),
      (['instance-1', 'i.*'], 'name eq instance-1|i.*'),
      (['a', 'b', 'c'], 'name eq a|b|c'),
      (['a          b c'], 'name eq a|b|c'),
      (['a          b c', 'd     e    f'], 'name eq a|b|c|d|e|f'),
      (['instance-[0-9]+'], 'name eq instance-[0-9]+'),
      (['a-[0-9]+', 'b-[0-9]+'], 'name eq a-[0-9]+|b-[0-9]+'),
      (['  a-[0-9]+     b-[0-9]+ '], 'name eq a-[0-9]+|b-[0-9]+'),
      )

  def testRegexesToFilterExpression(self):
    for arg, expected in self.test_cases:
      self.assertEqual(utils.RegexesToFilterExpression(arg), expected)


class ProtocolPortsTests(unittest.TestCase):

  def testParseProtocolFailures(self):
    failure_cases = (
        None, '', 'foo'
        )
    for failure_case in failure_cases:
      self.assertRaises(ValueError, utils.ParseProtocol, failure_case)

  def testParseProtocolSuccesses(self):
    test_cases = (
        (6, 6),
        ('6', 6),
        ('tcp', 6),
        ('udp', 17)
        )
    for arg, expected in test_cases:
      self.assertEqual(utils.ParseProtocol(arg), expected)

  def testReplacePortNamesFailures(self):
    failure_cases = (
        None, 22, '', 'foo', 'foo-bar', '24-42-2442'
        )
    for failure_case in failure_cases:
      self.assertRaises(ValueError, utils.ReplacePortNames, failure_case)

  def testReplacePortNameSuccesses(self):
    test_cases = (
        ('ssh', '22'),
        ('22', '22'),
        ('ssh-http', '22-80'),
        ('22-http', '22-80'),
        ('ssh-80', '22-80'),
        ('22-80', '22-80')
        )
    for arg, expected in test_cases:
      self.assertEqual(utils.ReplacePortNames(arg), expected)


class SingularizeTests(unittest.TestCase):
  """Tests for utils.Singularize."""

  test_cases = (
      ('instances', 'instance'),
      ('disks', 'disk'),
      ('firewalls', 'firewall'),
      ('snapshots', 'snapshot'),
      ('operations', 'operation'),
      ('images', 'image'),
      ('kernels', 'kernel'),
      ('networks', 'network'),
      ('machineTypes', 'machineType'),
      ('backendGroups', 'backendGroup'),
      ('publicEndpoints', 'publicEndpoint'),
      )

  def testSingularize(self):
    for arg, expected in self.test_cases:
      self.assertEqual(utils.Singularize(arg), expected)
      self.assertEqual(utils.Singularize(expected), expected)


class AllTests(unittest.TestCase):
  """Tests for utils.All."""

  def setUp(self):
    self._page = 0

  def testArgumentPlumbing(self):

    def mockFunc(project=None, maxResults=None, filter=None, pageToken=None):
      self.assertEqual(project, 'my-project')
      self.assertEqual(maxResults, 651)
      self.assertEqual(filter, 'name eq my-instance')
      self.assertEqual(pageToken, None)
      return mock_api.MockRequest(
          {'kind': 'numbers', 'items': [1, 2, 3]})

    utils.All(mockFunc, 'my-project',
              max_results=651,
              filter='name eq my-instance')

  def testWithZones(self):
    def mockFunc(project=None, maxResults=None, filter=None, pageToken=None,
                 zone=None):
      self.assertEqual('some-zone', zone)
      return mock_api.MockRequest(
          {'kind': 'numbers', 'items': [1, 2, 3]})

    utils.All(mockFunc, 'my-project', zone='some-zone')

  def testWithEmptyResponse(self):

    def mockFunc(project=None, maxResults=None, filter=None, pageToken=None):
      return mock_api.MockRequest({'kind': 'numbers', 'items': []})

    self.assertEqual(utils.All(mockFunc, 'my-project'),
                     {'kind': 'numbers', 'items': []})

  def testWithNoPaging(self):

    def mockFunc(project=None, maxResults=None, filter=None, pageToken=None):
      return mock_api.MockRequest({'kind': 'numbers', 'items': [1, 2, 3]})

    self.assertEqual(utils.All(mockFunc, 'my-project'),
                     {'kind': 'numbers', 'items': [1, 2, 3]})

  def testWithPaging(self):
    responses = [
        mock_api.MockRequest(
            {'kind': 'numbers', 'items': [1, 2, 3], 'nextPageToken': 'abc'}),
        mock_api.MockRequest(
            {'kind': 'numbers', 'items': [4, 5, 6]})]

    def mockFunc(project=None, maxResults=None, filter=None, pageToken=None):
      self._page += 1
      return responses[self._page - 1]

    self.assertEqual(utils.All(mockFunc, 'my-project'),
                     {'kind': 'numbers', 'items': [1, 2, 3, 4, 5, 6]})

  def testWithNoPagingAndSlicing(self):

    def mockFunc(project=None, maxResults=None, filter=None, pageToken=None):
      return mock_api.MockRequest({'kind': 'numbers', 'items': [1, 2, 3]})

    self.assertEqual(utils.All(mockFunc, 'my-project', max_results=2),
                     {'kind': 'numbers', 'items': [1, 2]})

  def testWithPagingAndSlicing(self):
    responses = [
        mock_api.MockRequest(
            {'kind': 'numbers', 'items': [1, 2, 3], 'nextPageToken': 'abc'}),
        mock_api.MockRequest(
            {'kind': 'numbers', 'items': [4, 5, 6]})]

    def mockFunc(project=None, maxResults=None, filter=None, pageToken=None):
      self._page += 1
      return responses[self._page - 1]

    self.assertEqual(utils.All(mockFunc, 'my-project', max_results=5),
                     {'kind': 'numbers', 'items': [1, 2, 3, 4, 5]})


if __name__ == '__main__':
  unittest.main()
