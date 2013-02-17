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

"""Unit tests for the base command classes."""

from __future__ import with_statement



import path_initializer
path_initializer.InitializeSysPath()

import copy
import datetime
import os
import sys
import tempfile




from google.apputils import app
import gflags as flags
import unittest

from gcutil import command_base
from gcutil import gcutil_logging
from gcutil import mock_api

FLAGS = flags.FLAGS


class CommandBaseTest(unittest.TestCase):

  class ListMockCommandBase(command_base.GoogleComputeListCommand):
    """A list mock command that specifies no default sort field."""

    summary_fields = (('name', 'id'),
                      ('id', 'number'),
                      ('description', 'description'))

    def __init__(self, name, flag_values):
      super(CommandBaseTest.ListMockCommandBase, self).__init__(
          name, flag_values)

    def SetApi(self, api):
      pass

    def ListFunc(self):

      def Func(project=None, maxResults=None, filter=None, pageToken=None):
        return mock_api.MockRequest(
            {'items': [{'description': 'Object C',
                        'id': 'projects/user/objects/my-object-c',
                        'kind': 'cloud#object',
                        'number': 123},
                       {'description': 'Object A',
                        'id': 'projects/user/objects/my-object-a',
                        'kind': 'cloud#object',
                        'number': 789},
                       {'description': 'Object B',
                        'id': 'projects/user/objects/my-object-b',
                        'kind': 'cloud#object',
                        'number': 456},
                       {'description': 'Object D',
                        'id': 'projects/user/objects/my-object-d',
                        'kind': 'cloud#object',
                        'number': 999}],
             'kind': 'cloud#objectList'})

      return Func

  class ListMockCommand(ListMockCommandBase):
    """A list mock command that specifies a default sort field."""
    default_sort_field = 'name'

    def __init__(self, name, flag_values):
      super(CommandBaseTest.ListMockCommand, self).__init__(name, flag_values)

  class MockDetailCommand(command_base.GoogleComputeCommand):

    detail_fields = (('name', 'id'),
                     ('id', 'number'),
                     ('description', 'description'),
                     ('additional', 'moreStuff'))

    def __init__(self, name, flag_values):
      super(CommandBaseTest.MockDetailCommand, self).__init__(name, flag_values)

    def SetApi(self, api):
      pass

    def Handle(self):
      return {'description': 'Object C',
              'id': 'projects/user/objects/my-object-c',
              'kind': 'cloud#object',
              'number': 123,
              'moreStuff': 'foo'}

  class MockSafetyCommand(command_base.GoogleComputeCommand):

    safety_prompt = 'Take scary action'

    def __init__(self, name, flag_values):
      super(CommandBaseTest.MockSafetyCommand, self).__init__(name, flag_values)

    def SetApi(self, api):
      pass

    def Handle(self):
      pass

  class MockSafetyCommandWithArgs(MockSafetyCommand):
    safety_prompt = 'Act on'

    def Handle(self, argument, arg2):
      pass

  class FakeExit(object):
    """A fake version of exit to capture exit status."""

    def __init__(self):
      self.__status__ = []

    def __call__(self, value):
      self.__status__.append(value)

    def GetStatuses(self):
      return self.__status__

  class CaptureOutput(object):

    def __init__(self):
      self._capture_text = ''

    # Purposefully name this 'write' to mock an output stream
    # pylint: disable-msg=C6409
    def write(self, text):
      self._capture_text += text

    # Purposefully name this 'flush' to mock an output stream
    # pylint: disable-msg=C6409
    def flush(self):
      pass

    def GetCapturedText(self):
      return self._capture_text

  class MockInput(object):

    def __init__(self, input_string):
      self._input_string = input_string

    # Purposefully name this 'readline' to mock an input stream
    # pylint: disable-msg=C6409
    def readline(self):
      return self._input_string

  def ClearLogger(self):
    for h in gcutil_logging.LOGGER.handlers:
      gcutil_logging.LOGGER.removeHandler(h)

  def test_PresentElement(self):
    class MockCommand(command_base.GoogleComputeCommand):
      def __init__(self, name, flag_values):
        super(MockCommand, self).__init__(name, flag_values)

    flag_values = copy.deepcopy(FLAGS)
    command = MockCommand('mock_command', flag_values)
    flag_values.project = 'user'
    flag_values.service_version = 'v1beta13'
    command.SetFlags(flag_values)

    self.assertEqual(
        'user',
        command._PresentElement('https://www.googleapis.com/compute/v1/'
                               'projects/user'))
    self.assertEqual(
        'user',
        command._PresentElement('https://www.googleapis.com/compute/v1/'
                               'projects/user/'))
    self.assertEqual('user', command._PresentElement('projects/user'))
    self.assertEqual('user', command._PresentElement('projects/user/'))
    self.assertEqual(
        'standard-2-cpu',
        command._PresentElement('https://www.googleapis.com/compute/v1/'
                               'projects/user/machine-types/standard-2-cpu'))
    self.assertEqual(
        'standard-2-cpu',
        command._PresentElement('https://www.googleapis.com/compute/v1/'
                               'projects/user/machine-types/standard-2-cpu/'))
    self.assertEqual(
        'standard-2-cpu',
        command._PresentElement('projects/user/machine-types/standard-2-cpu'))
    self.assertEqual(
        'standard-2-cpu',
        command._PresentElement('projects/user/machine-types/standard-2-cpu/'))
    self.assertEqual(
        'foo/bar/baz',
        command._PresentElement('https://www.googleapis.com/compute/v1/'
                               'projects/user/shared-fate-zones/foo/bar/baz'))
    self.assertEqual(
        'foo/bar/baz',
        command._PresentElement('projects/user/shared-fate-zones/foo/bar/baz'))
    self.assertEqual('foo/bar/baz', command._PresentElement('foo/bar/baz'))

    # Tests eliding feature
    test_str = ('I am the very model of a modern Major-General. I\'ve '
                'information vegetable, animal, and mineral. I know the kings '
                'of England and quote the fights historical; from Marathon to '
                'Waterloo in order categorical.')
    self.assertEqual(
        'I am the very model of a modern.. Waterloo in order categorical.',
        command._PresentElement(test_str))

    flag_values.long_values_display_format = 'full'
    command.SetFlags(flag_values)
    self.assertEqual(test_str, command._PresentElement(test_str))

  def testDenormalizeProjectName(self):
    denormalize = command_base.GoogleComputeCommand.DenormalizeProjectName
    flag_values = flags.FlagValues()
    flags.DEFINE_string('project',
                        None,
                        'Project Name',
                        flag_values=flag_values)
    flags.DEFINE_string('project_id',
                        None,
                        'Obsolete Project Name',
                        flag_values=flag_values)

    self.assertRaises(command_base.CommandError,
                      denormalize,
                      flag_values)

    flag_values.project = 'project_collection/google'
    self.assertRaises(command_base.CommandError,
                      denormalize,
                      flag_values)

    flag_values.project = 'projects/google'
    denormalize(flag_values)
    self.assertEqual(flag_values.project, 'google')
    denormalize(flag_values)
    self.assertEqual(flag_values.project, 'google')

    flag_values.project = '/google'
    denormalize(flag_values)
    self.assertEqual(flag_values.project, 'google')

    flag_values.project = 'google/'
    denormalize(flag_values)
    self.assertEqual(flag_values.project, 'google')

    flag_values.project = '/google/'
    denormalize(flag_values)
    self.assertEqual(flag_values.project, 'google')

    flag_values.project = '/projects/google'
    denormalize(flag_values)
    self.assertEqual(flag_values.project, 'google')

    flag_values.project = 'projects/google/'
    denormalize(flag_values)
    self.assertEqual(flag_values.project, 'google')

    flag_values.project = '/projects/google/'
    denormalize(flag_values)
    self.assertEqual(flag_values.project, 'google')

    flag_values.project_id = 'my-obsolete-project-1'
    flag_values.project = 'my-new-project-1'
    denormalize(flag_values)
    self.assertEqual(flag_values.project, 'my-new-project-1')
    self.assertEqual(flag_values.project_id, None)

    flag_values.project_id = 'my-new-project-2'
    flag_values.project = None
    denormalize(flag_values)
    self.assertEqual(flag_values.project, 'my-new-project-2')
    self.assertEqual(flag_values.project_id, None)

    flag_values.project_id = 'MyUppercaseProject-1'
    flag_values.project = None
    self.assertRaises(command_base.CommandError, denormalize, flag_values)

    flag_values.project = 'MyUppercaseProject-2'
    flag_values.project_id = None
    self.assertRaises(command_base.CommandError, denormalize, flag_values)

  def testDenormalizeResourceName(self):
    denormalize = command_base.GoogleComputeCommand.DenormalizeResourceName
    self.assertEqual('dual-cpu',
                     denormalize('projects/google/machine_types/dual-cpu'))
    self.assertEqual('dual-cpu',
                     denormalize('/projects/google/machine_types/dual-cpu'))
    self.assertEqual('dual-cpu',
                     denormalize('projects/google/machine_types/dual-cpu/'))
    self.assertEqual('dual-cpu',
                     denormalize('/projects/google/machine_types/dual-cpu/'))
    self.assertEqual('dual-cpu',
                     denormalize('//projects/google/machine_types/dual-cpu//'))
    self.assertEqual('dual-cpu',
                     denormalize('dual-cpu'))
    self.assertEqual('dual-cpu',
                     denormalize('/dual-cpu'))
    self.assertEqual('dual-cpu',
                     denormalize('dual-cpu/'))
    self.assertEqual('dual-cpu',
                     denormalize('/dual-cpu/'))

  def _DoTestNormalizeResourceName(self, service_version):
    class MockCommand(command_base.GoogleComputeCommand):
      def __init__(self, name, flag_values):
        super(MockCommand, self).__init__(name, flag_values)

    flag_values = copy.deepcopy(FLAGS)
    flag_values.project = 'google'
    flag_values.service_version = service_version

    command = MockCommand('mock_command', flag_values)
    command.SetFlags(flag_values)

    prefix = 'https://www.googleapis.com/compute/%s' % service_version
    expected = '%s/projects/google/machine_types/dual-cpu' % prefix

    self.assertEqual(
        expected,
        command.NormalizeResourceName('google', None, 'machine_types',
                                      'dual-cpu'))
    self.assertEqual(
        expected,
        command.NormalizeResourceName('google', None, 'machine_types',
                                      '/dual-cpu'))
    self.assertEqual(
        expected,
        command.NormalizeResourceName('google', None, 'machine_types',
                                      'dual-cpu/'))
    self.assertEqual(
        expected,
        command.NormalizeResourceName('google', None, 'machine_types',
                                      '/dual-cpu/'))
    self.assertEqual(
        expected,
        command.NormalizeResourceName(
            'google',
            None,
            'machine_types',
            'projects/google/machine_types/dual-cpu'))
    self.assertEqual(
        expected,
        command.NormalizeResourceName(
            'google',
            None,
            'machine_types',
            '/projects/google/machine_types/dual-cpu'))
    self.assertEqual(
        expected,
        command.NormalizeResourceName(
            'google',
            None,
            'machine_types',
            'projects/google/machine_types/dual-cpu/'))
    self.assertEqual(
        expected,
        command.NormalizeResourceName(
            'google',
            None,
            'machine_types',
            '/projects/google/machine_types/dual-cpu/'))
    self.assertEqual(
        '%s/projects/google/kernels/default' % prefix,
        command.NormalizeResourceName(
            'my-project',
            None,
            'kernels',
            'projects/google/kernels/default'))

  def testNormalizeResourceName(self):
    for version in command_base.SUPPORTED_VERSIONS:
      self._DoTestNormalizeResourceName(version)

  def testNormalizeScopedResourceName(self):
    class MockCommand(command_base.GoogleComputeCommand):
      def __init__(self, name, flag_values):
        super(MockCommand, self).__init__(name, flag_values)

    flag_values = copy.deepcopy(FLAGS)
    flag_values.project = 'my-project'

    command = MockCommand('mock_command', flag_values)
    command.SetFlags(flag_values)

    # Validate scope is ignored downlevel
    flag_values.service_version = 'v1beta13'
    prefix = 'https://www.googleapis.com/compute/v1beta13'
    expected = '%s/projects/my-project/objects/foo-bar' % prefix
    self.assertEqual(
        expected,
        command.NormalizeResourceName('my-project', 'scope', 'objects',
                                      'foo-bar'))

    # Validate scope is expected in v1beta14 and above
    flag_values.service_version = 'v1beta14'
    prefix = 'https://www.googleapis.com/compute/v1beta14'

    expected = '%s/projects/my-project/scope/objects/foo-bar' % prefix
    self.assertEqual(
        expected,
        command.NormalizeResourceName('my-project', 'scope', 'objects',
                                      'foo-bar'))

    # Validate helper wrappers
    expected = '%s/projects/my-project/objects/foo-bar' % prefix
    self.assertEqual(
        expected,
        command.NormalizeTopLevelResourceName('my-project', 'objects',
                                              'foo-bar'))

    expected = '%s/projects/my-project/global/objects/foo-bar' % prefix
    self.assertEqual(
        expected,
        command.NormalizeGlobalResourceName('my-project', 'objects',
                                            'foo-bar'))

    expected = '%s/projects/my-project/zones/zone-a/objects/foo-bar' % prefix
    self.assertEqual(
        expected,
        command.NormalizePerZoneResourceName('my-project', 'zone-a', 'objects',
                                             'foo-bar'))

  def testFlattenToDict(self):
    class TestClass(command_base.GoogleComputeCommand):
      fields = (('name', 'id'),
                ('simple', 'path.to.object'),
                ('multiple', 'more.elements'),
                ('multiple', 'even_more.elements'),
                ('repeated', 'things'),
                ('long', 'l'),
                ('does not exist', 'dne'),
                ('partial match', 'path.to.nowhere'),
               )

    data = {'id': ('https://www.googleapis.com/compute/v1beta1/' +
                   'projects/test/object/foo'),
            'path': {'to': {'object': 'bar'}},
            'more': [{'elements': 'a'}, {'elements': 'b'}],
            'even_more': [{'elements': 800}, {'elements': 800}],
            'things': [1, 2, 3],
            'l': 'n' * 80}
    expected_result = ['foo', 'bar', 'a,b', '800,800', '1,2,3',
                       '%s..%s' % ('n' * 31, 'n' * 31), '', '']
    flag_values = copy.deepcopy(FLAGS)
    flag_values.project = 'test'
    test_class = TestClass('foo', flag_values)
    test_class.SetFlags(flag_values)
    flattened = test_class._FlattenObjectToList(data, test_class.fields)
    self.assertEquals(flattened, expected_result)

  def testFlattenToDictWithMultipleTargets(self):
    class TestClass(command_base.GoogleComputeCommand):
      fields = (('name', ('name', 'id')),
                ('simple', ('path.to.object', 'foo')),
                ('multiple', 'more.elements'),
                ('multiple', 'even_more.elements'),
                ('repeated', 'things'),
                ('long', ('l', 'longer')),
                ('does not exist', 'dne'),
                ('partial match', 'path.to.nowhere'),
               )

    data = {'name': ('https://www.googleapis.com/compute/v1beta1/' +
                     'projects/test/object/foo'),
            'path': {'to': {'object': 'bar'}},
            'more': [{'elements': 'a'}, {'elements': 'b'}],
            'even_more': [{'elements': 800}, {'elements': 800}],
            'things': [1, 2, 3],
            'longer': 'n' * 80}
    expected_result = ['foo', 'bar', 'a,b', '800,800', '1,2,3',
                       '%s..%s' % ('n' * 31, 'n' * 31), '', '']
    flag_values = copy.deepcopy(FLAGS)
    flag_values.project = 'test'
    test_class = TestClass('foo', flag_values)
    test_class.SetFlags(flag_values)
    flattened = test_class._FlattenObjectToList(data, test_class.fields)
    self.assertEquals(flattened, expected_result)

  def testPositionArgumentParsing(self):
    class MockCommand(command_base.GoogleComputeCommand):

      def __init__(self, name, flag_values):
        super(MockCommand, self).__init__(name, flag_values)
        flags.DEFINE_string('mockflag',
                            'wrong_mock_flag',
                            'Mock Flag',
                            flag_values=flag_values)

      def Handle(self, arg1, arg2, arg3):
        pass

    flag_values = copy.deepcopy(FLAGS)
    command = MockCommand('mock_command', flag_values)

    expected_arg1 = 'foo'
    expected_arg2 = 'bar'
    expected_arg3 = 'baz'
    expected_flagvalue = 'wow'

    command_line = ['mock_command', expected_arg1, expected_arg2,
                    expected_arg3, '--mockflag=' + expected_flagvalue]

    # Verify the positional argument parser correctly identifies the parameters
    # and flags.
    result = command._ParseArgumentsAndFlags(flag_values, command_line)

    self.assertEqual(result[0], expected_arg1)
    self.assertEqual(result[1], expected_arg2)
    self.assertEqual(result[2], expected_arg3)
    self.assertEqual(flag_values.mockflag, expected_flagvalue)

  def testErroneousKeyWordArgumentParsing(self):
    class MockCommand(command_base.GoogleComputeCommand):

      def __init__(self, name, flag_values):
        super(MockCommand, self).__init__(name, flag_values)
        flags.DEFINE_integer('mockflag',
                             10,
                             'Mock Flag',
                             flag_values=flag_values,
                             lower_bound=0)

      def Handle(self, arg1, arg2, arg3):
        pass

    flag_values = copy.deepcopy(FLAGS)
    command = MockCommand('mock_command', flag_values)

    # Ensures that a type mistmatch for a keyword argument causes a
    # CommandError to be raised.
    bad_values = [-100, -2, 0.2, .30, 100.1]
    for val in bad_values:
      command_line = ['mock_command', '--mockflag=%s' % val]
      self.assertRaises(command_base.CommandError,
                        command._ParseArgumentsAndFlags,
                        flag_values, command_line)

    # Ensures that passing a nonexistent keyword argument also causes
    # a CommandError to be raised.
    command_line = ['mock_command', '--nonexistent_flag=boo!']
    self.assertRaises(command_base.CommandError,
                      command._ParseArgumentsAndFlags,
                      flag_values, command_line)

  def testSafetyPromptYes(self):
    flag_values = copy.deepcopy(FLAGS)
    command_line = ['mock_command']

    command = CommandBaseTest.MockSafetyCommand('mock_command', flag_values)
    args = command._ParseArgumentsAndFlags(flag_values, command_line)
    command.SetFlags(flag_values)

    mock_output = mock_api.MockOutput()
    mock_input = mock_api.MockInput('Y\n\r')

    oldin = sys.stdin
    sys.stdin = mock_input
    oldout = sys.stdout
    sys.stdout = mock_output

    result = command._HandleSafetyPrompt(args)

    self.assertEqual(mock_output.GetCapturedText(),
                     'Take scary action? [y/N]\n>>> ')
    self.assertEqual(result, True)

    sys.stdin = oldin
    sys.stdout = oldout

  def testSafetyPromptWithArgsYes(self):
    flag_values = copy.deepcopy(FLAGS)
    command_line = ['mock_cmd', 'arg1', 'arg2']

    command = CommandBaseTest.MockSafetyCommandWithArgs('mock_cmd', flag_values)
    args = command._ParseArgumentsAndFlags(flag_values, command_line)
    command.SetFlags(flag_values)

    mock_output = CommandBaseTest.CaptureOutput()
    mock_input = CommandBaseTest.MockInput('Y\n\r')

    oldin = sys.stdin
    sys.stdin = mock_input
    oldout = sys.stdout
    sys.stdout = mock_output

    result = command._HandleSafetyPrompt(args)

    self.assertEqual(mock_output.GetCapturedText(),
                     'Act on arg1, arg2? [y/N]\n>>> ')
    self.assertEqual(result, True)

    sys.stdin = oldin
    sys.stdout = oldout

  def testSafetyPromptMissingArgs(self):
    flag_values = copy.deepcopy(FLAGS)
    command_line = ['mock_cmd', 'arg1']

    command = CommandBaseTest.MockSafetyCommandWithArgs('mock_cmd', flag_values)

    command_base.sys.exit = CommandBaseTest.FakeExit()
    sys.stderr = CommandBaseTest.CaptureOutput()

    gcutil_logging.SetupLogging()
    self.assertRaises(command_base.CommandError,
                      command._ParseArgumentsAndFlags,
                      flag_values, command_line)

  def testSafetyPromptExtraArgs(self):
    flag_values = copy.deepcopy(FLAGS)
    command_line = ['mock_cmd', 'arg1', 'arg2', 'arg3']

    command = CommandBaseTest.MockSafetyCommandWithArgs('mock_cmd', flag_values)

    command_base.sys.exit = CommandBaseTest.FakeExit()
    sys.stderr = CommandBaseTest.CaptureOutput()

    gcutil_logging.SetupLogging()
    self.assertRaises(command_base.CommandError,
                      command._ParseArgumentsAndFlags,
                      flag_values, command_line)

  def testSafetyPromptNo(self):
    flag_values = copy.deepcopy(FLAGS)
    command_line = ['mock_command']

    command = CommandBaseTest.MockSafetyCommand('mock_command', flag_values)
    args = command._ParseArgumentsAndFlags(flag_values, command_line)
    command.SetFlags(flag_values)

    mock_output = mock_api.MockOutput()
    mock_input = mock_api.MockInput('garbage\n\r')

    oldin = sys.stdin
    sys.stdin = mock_input
    oldout = sys.stdout
    sys.stdout = mock_output

    result = command._HandleSafetyPrompt(args)

    self.assertEqual(mock_output.GetCapturedText(),
                     'Take scary action? [y/N]\n>>> ')
    self.assertEqual(result, False)

    sys.stdin = oldin
    sys.stdout = oldout

  def testSafetyPromptForce(self):
    flag_values = copy.deepcopy(FLAGS)
    command_line = ['mock_command', '--force']

    command = CommandBaseTest.MockSafetyCommand('mock_command', flag_values)
    args = command._ParseArgumentsAndFlags(flag_values, command_line)
    command.SetFlags(flag_values)

    mock_output = mock_api.MockOutput()

    oldout = sys.stdout
    sys.stdout = mock_output

    result = command._HandleSafetyPrompt(args)

    sys.stdout = oldout

    self.assertEqual(result, True)
    self.assertEqual(mock_output.GetCapturedText(), '')

  def testPromptForEntryWithZeroItems(self):

    class MockCollectionApi(object):

      def list(self, project=None, maxResults=None, filter=None, pageToken=None):
        return mock_api.MockRequest(
               {'kind': 'compute#collectionList',
                'id': 'projects/p/collection',
                'selfLink':
                  'https://www.googleapis.com/compute/v1/projects/p/collection'
                })

    flag_values = copy.deepcopy(FLAGS)
    flag_values.project = 'p'

    command = command_base.GoogleComputeCommand('mock_command', flag_values)
    command.SetFlags(flag_values)
    self.assertEqual(
        command._PromptForEntry(MockCollectionApi(), 'collection'),
        None)

  def testPromptForEntryWithOneItem(self):

    class MockCollectionApi(object):

      def list(self, project=None, maxResults=None, filter=None, pageToken=None):
        return mock_api.MockRequest(
               {'kind': 'compute#collectionList',
                'id': 'projects/p/collection',
                'selfLink':
                  'https://www.googleapis.com/compute/v1/projects/p/collection',
                'items': [{'name': 'item-1'}]
                })

    flag_values = copy.deepcopy(FLAGS)
    flag_values.project = 'p'

    command = command_base.GoogleComputeCommand('mock_command', flag_values)
    command.SetFlags(flag_values)

    # Tests _PromptForEntry with auto selecting on.
    self.assertEqual(command._PromptForEntry(MockCollectionApi(), 'collection',
                                             auto_select=True),
                     {'name': 'item-1'})

    # Tests _PromptForEntry with auto selecting off.
    mock_output = CommandBaseTest.CaptureOutput()
    mock_input = CommandBaseTest.MockInput('1\n')

    oldin = sys.stdin
    sys.stdin = mock_input
    oldout = sys.stdout
    sys.stdout = mock_output

    result = command._PromptForEntry(MockCollectionApi(), 'collection',
                                     auto_select=False)

    self.assertEqual(mock_output.GetCapturedText(),
                     '1: item-1\n>>> ')
    self.assertEqual(result, {'name': 'item-1'})

    sys.stdin = oldin
    sys.stdout = oldout

  def testPromptForEntryWithManyItems(self):

    class MockCollectionApi(object):

      def list(self, project=None, maxResults=None, filter=None, pageToken=None):
        return mock_api.MockRequest(
               {'kind': 'compute#collectionList',
                'id': 'projects/p/collection',
                'selfLink':
                  'https://www.googleapis.com/compute/v1/projects/p/collection',
                'items': [{'name': 'item-1'},
                          {'name': 'item-2'},
                          {'name': 'item-3'},
                          {'name': 'item-4'}]})

    flag_values = copy.deepcopy(FLAGS)
    flag_values.project = 'p'

    command = command_base.GoogleComputeCommand('mock_command', flag_values)
    command.SetFlags(flag_values)

    mock_output = CommandBaseTest.CaptureOutput()
    mock_input = CommandBaseTest.MockInput('3\n')

    oldin = sys.stdin
    sys.stdin = mock_input
    oldout = sys.stdout
    sys.stdout = mock_output

    result = command._PromptForEntry(MockCollectionApi(), 'collection',
                                     auto_select=False)

    self.assertEqual(
        mock_output.GetCapturedText(),
        '\n'.join(('1: item-1', '2: item-2', '3: item-3', '4: item-4', '>>> ')))
    self.assertEqual(result, {'name': 'item-3'})

    sys.stdin = oldin
    sys.stdout = oldout

  def testPromptForEntryWithManyItemsAndAdditionalKeyFunc(self):

    class MockCollectionApi(object):

      def list(self, project=None, maxResults=None, filter=None,
               pageToken=None):
        return mock_api.MockRequest(
               {'kind': 'compute#machineTypeList',
                'id': 'projects/p/machineTypes',
                'selfLink': ('https://www.googleapis.com/compute/v1/projects/p/'
                             'machineTypes'),
                'items': [{'name': 'n1-highcpu-4-d'},
                          {'name': 'n1-standard-2'},
                          {'name': 'n1-standard-1-d'},
                          {'name': 'n1-standard-8-d'},
                          {'name': 'n1-highcpu-8-d'},
                          {'name': 'n1-standard-2-d'},
                          {'name': 'n1-standard-1'},
                          {'name': 'n1-standard-4'},
                          {'name': 'n1-highmem-4'},
                          {'name': 'n1-highcpu-4'},
                          {'name': 'n1-highcpu-2'},
                          {'name': 'n1-standard-4-d'},
                          {'name': 'n1-standard-8'},
                          {'name': 'n1-highmem-2'},
                          {'name': 'n1-highmem-2-d'},
                          {'name': 'n1-highcpu-2-d'},
                          {'name': 'n1-highmem-8'},
                          {'name': 'n1-highcpu-8'},
                          {'name': 'n1-highmem-8-d'},
                          {'name': 'n1-highmem-4-d'}]})

    flag_values = copy.deepcopy(FLAGS)
    flag_values.project = 'p'

    command = command_base.GoogleComputeCommand('mock_command', flag_values)
    command.SetFlags(flag_values)

    mock_output = CommandBaseTest.CaptureOutput()
    mock_input = CommandBaseTest.MockInput('3\n')

    oldin = sys.stdin
    sys.stdin = mock_input
    oldout = sys.stdout
    sys.stdout = mock_output

    result = command._PromptForEntry(
        MockCollectionApi(), 'machine type', auto_select=False,
        additional_key_func=command._GetMachineTypeSecondarySortScore)

    self.assertEqual(
        mock_output.GetCapturedText(),
        '\n'.join((
            '1: n1-standard-1',
            '2: n1-standard-1-d',
            '3: n1-standard-2',
            '4: n1-standard-2-d',
            '5: n1-standard-4',
            '6: n1-standard-4-d',
            '7: n1-standard-8',
            '8: n1-standard-8-d',
            '9: n1-highcpu-2',
            '10: n1-highcpu-2-d',
            '11: n1-highcpu-4',
            '12: n1-highcpu-4-d',
            '13: n1-highcpu-8',
            '14: n1-highcpu-8-d',
            '15: n1-highmem-2',
            '16: n1-highmem-2-d',
            '17: n1-highmem-4',
            '18: n1-highmem-4-d',
            '19: n1-highmem-8',
            '20: n1-highmem-8-d',
            '>>> ')))
    self.assertEqual(result, {'name': 'n1-standard-2'})

    sys.stdin = oldin
    sys.stdout = oldout

  def testPromptForEntryWithDeprecatedItems(self):

    class MockCollectionApi(object):

      def list(self, project=None, maxResults=None, filter=None, pageToken=None):
        return mock_api.MockRequest(
            {'kind': 'compute#collectionList',
             'id': 'projects/p/collection',
             'selfLink':
             'https://www.googleapis.com/compute/v1/projects/p/collection',
             'items': [{'name': 'item-1',
                        'deprecated':
                        {'state': 'DEPRECATED'}},
                       {'name': 'item-2'},
                       {'name': 'item-3',
                        'deprecated':
                        {'state': 'OBSOLETE'}},
                       {'name': 'item-4'},
                       {'name': 'item-5',
                        'deprecated':
                        {'state': 'DEPRECATED'}},
                       {'name': 'item-6',
                        'deprecated':
                        {'state': 'DELETED'}}]})

    flag_values = copy.deepcopy(FLAGS)
    flag_values.project = 'p'

    command = command_base.GoogleComputeCommand('mock_command', flag_values)
    command.SetFlags(flag_values)

    mock_output = CommandBaseTest.CaptureOutput()
    mock_input = CommandBaseTest.MockInput('3\n')

    oldin = sys.stdin
    sys.stdin = mock_input
    oldout = sys.stdout
    sys.stdout = mock_output

    result = command._PromptForEntry(MockCollectionApi(), 'collection',
                                     auto_select=False)

    self.assertEqual(
        mock_output.GetCapturedText(),
        '\n'.join(('1: item-2', '2: item-4', '3: item-1 (DEPRECATED)',
                   '4: item-5 (DEPRECATED)', '>>> ')))
    self.assertEqual(result, {'name': 'item-1', 'deprecated':
                              {'state': 'DEPRECATED'}})
    sys.stdin = oldin
    sys.stdout = oldout

  def testPromptForChoicesWithOneDeprecatedItem(self):
    class MockCollectionApi(object):

      def list(self, project=None, maxResults=None, filter=None, pageToken=None):
        return mock_api.MockRequest(
            {'kind': 'compute#collectionList',
             'id': 'projects/p/collection',
             'selfLink':
             'https://www.googleapis.com/compute/v1/projects/p/collection',
             'items': [{'name': 'item-1',
                        'deprecated':
                        {'state': 'DEPRECATED'}}]})

    flag_values = copy.deepcopy(FLAGS)
    flag_values.project = 'p'

    command = command_base.GoogleComputeCommand('mock_command', flag_values)
    command.SetFlags(flag_values)

    mock_output = CommandBaseTest.CaptureOutput()

    oldout = sys.stdout
    sys.stdout = mock_output

    result = command._PromptForEntry(MockCollectionApi(), 'collection')

    self.assertEqual(
        mock_output.GetCapturedText(),
        'Selecting the only available collection: item-1\n')
    self.assertEqual(result, {'name': 'item-1', 'deprecated':
                              {'state': 'DEPRECATED'}})
    sys.stdout = oldout

  def testDetailOutput(self):
    flag_values = copy.deepcopy(FLAGS)
    flag_values.project = 'user'

    command = CommandBaseTest.MockDetailCommand('mock_command', flag_values)
    expected_output = (u'+-------------+-------------+\n'
                       '|  property   |    value    |\n'
                       '+-------------+-------------+\n'
                       '| name        | my-object-c |\n'
                       '| id          | 123         |\n'
                       '| description | Object C    |\n'
                       '| additional  | foo         |\n'
                       '+-------------+-------------+\n')
    mock_output = mock_api.MockOutput()

    oldout = sys.stdout
    sys.stdout = mock_output

    command.SetFlags(flag_values)
    result = command.Handle()
    command.PrintResult(result)

    sys.stdout = oldout

    self.assertEqual(mock_output.GetCapturedText(), expected_output)

  def testEmptyList(self):
    flag_values = copy.deepcopy(FLAGS)
    flag_values.project = 'user'

    class ListEmptyMockCommand(CommandBaseTest.ListMockCommand):
      def __init__(self, name, flag_values):
        super(ListEmptyMockCommand, self).__init__(name, flag_values)

      def Handle(self):
        return {'kind': 'cloud#objectsList'}

    command = ListEmptyMockCommand('empty_list', flag_values)
    expected_output = (u'+------+----+-------------+\n'
                       '| name | id | description |\n'
                       '+------+----+-------------+\n'
                       '+------+----+-------------+\n')
    mock_output = mock_api.MockOutput()

    oldout = sys.stdout
    sys.stdout = mock_output

    command.SetFlags(flag_values)
    result = command.Handle()
    command.PrintResult(result)

    sys.stdout = oldout

    self.assertEqual(mock_output.GetCapturedText(), expected_output)

  def testSortingNone(self):
    flag_values = copy.deepcopy(FLAGS)
    flag_values.project = 'user'

    command = CommandBaseTest.ListMockCommandBase('mock_command', flag_values)
    expected_output = (u'+-------------+-----+-------------+\n'
                       '|    name     | id  | description |\n'
                       '+-------------+-----+-------------+\n'
                       '| my-object-c | 123 | Object C    |\n'
                       '| my-object-a | 789 | Object A    |\n'
                       '| my-object-b | 456 | Object B    |\n'
                       '| my-object-d | 999 | Object D    |\n'
                       '+-------------+-----+-------------+\n')
    mock_output = mock_api.MockOutput()

    oldout = sys.stdout
    sys.stdout = mock_output

    command.SetFlags(flag_values)
    result = command.Handle()
    command.PrintResult(result)

    sys.stdout = oldout

    self.assertEqual(mock_output.GetCapturedText(), expected_output)

  def testSortingDefault(self):
    flag_values = copy.deepcopy(FLAGS)
    flag_values.project = 'user'

    command = CommandBaseTest.ListMockCommand('mock_command', flag_values)
    mock_output = mock_api.MockOutput()
    expected_output = (u'+-------------+-----+-------------+\n'
                       '|    name     | id  | description |\n'
                       '+-------------+-----+-------------+\n'
                       '| my-object-a | 789 | Object A    |\n'
                       '| my-object-b | 456 | Object B    |\n'
                       '| my-object-c | 123 | Object C    |\n'
                       '| my-object-d | 999 | Object D    |\n'
                       '+-------------+-----+-------------+\n')

    oldout = sys.stdout
    sys.stdout = mock_output

    command.SetFlags(flag_values)
    result = command.Handle()
    command.PrintResult(result)

    sys.stdout = oldout

    self.assertEqual(mock_output.GetCapturedText(), expected_output)

  def testSortingSpecifiedInAscendingOrder(self):
    flag_values = copy.deepcopy(FLAGS)
    flag_values.project = 'user'

    command = CommandBaseTest.ListMockCommand('mock_command', flag_values)
    mock_output = mock_api.MockOutput()

    flag_values.sort_by = 'id'

    expected_output = (u'+-------------+-----+-------------+\n'
                       '|    name     | id  | description |\n'
                       '+-------------+-----+-------------+\n'
                       '| my-object-c | 123 | Object C    |\n'
                       '| my-object-b | 456 | Object B    |\n'
                       '| my-object-a | 789 | Object A    |\n'
                       '| my-object-d | 999 | Object D    |\n'
                       '+-------------+-----+-------------+\n')

    oldout = sys.stdout
    sys.stdout = mock_output

    command.SetFlags(flag_values)
    result = command.Handle()
    command.PrintResult(result)

    sys.stdout = oldout

    self.assertEqual(mock_output.GetCapturedText(), expected_output)

  def testSortingSpecifiedInDescendingOrder(self):
    flag_values = copy.deepcopy(FLAGS)
    flag_values.project = 'user'

    command = CommandBaseTest.ListMockCommand('mock_command', flag_values)
    mock_output = mock_api.MockOutput()

    flag_values.sort_by = '-id'

    expected_output = (u'+-------------+-----+-------------+\n'
                       '|    name     | id  | description |\n'
                       '+-------------+-----+-------------+\n'
                       '| my-object-d | 999 | Object D    |\n'
                       '| my-object-a | 789 | Object A    |\n'
                       '| my-object-b | 456 | Object B    |\n'
                       '| my-object-c | 123 | Object C    |\n'
                       '+-------------+-----+-------------+\n')

    oldout = sys.stdout
    sys.stdout = mock_output

    command.SetFlags(flag_values)
    result = command.Handle()
    command.PrintResult(result)

    sys.stdout = oldout

    self.assertEqual(mock_output.GetCapturedText(), expected_output)

  def testGracefulHandlingOfInvalidDefaultSortField(self):

    class ListMockCommandWithBadDefaultSortField(
        CommandBaseTest.ListMockCommandBase):

      default_sort_field = 'bad-field-name'

      def __init__(self, name, flag_values):
        super(ListMockCommandWithBadDefaultSortField, self).__init__(
            name, flag_values)

    flag_values = copy.deepcopy(FLAGS)
    flag_values.project = 'user'

    command = ListMockCommandWithBadDefaultSortField(
        'mock_command', flag_values)

    # The output is expected to remain unsorted if the default sort
    # field is invalid.
    expected_output = (u'+-------------+-----+-------------+\n'
                       '|    name     | id  | description |\n'
                       '+-------------+-----+-------------+\n'
                       '| my-object-c | 123 | Object C    |\n'
                       '| my-object-a | 789 | Object A    |\n'
                       '| my-object-b | 456 | Object B    |\n'
                       '| my-object-d | 999 | Object D    |\n'
                       '+-------------+-----+-------------+\n')
    mock_output = mock_api.MockOutput()

    oldout = sys.stdout
    sys.stdout = mock_output

    command.SetFlags(flag_values)
    result = command.Handle()
    command.PrintResult(result)

    sys.stdout = oldout

    self.assertEqual(mock_output.GetCapturedText(), expected_output)

  def testVersionComparison(self):
    class MockCommand(CommandBaseTest.ListMockCommand):
      def __init__(self, name, flag_values):
        super(MockCommand, self).__init__(name, flag_values)

    flag_values = copy.deepcopy(FLAGS)

    command = MockCommand('mock_command', flag_values)
    command.supported_versions = ['v1beta2', 'v1beta3', 'v1beta4',
                                  'v1beta5', 'v1beta6']

    flag_values.service_version = 'v1beta4'
    command.SetFlags(flag_values)
    self.assertFalse(command._IsUsingAtLeastApiVersion('v1beta6'))
    self.assertFalse(command._IsUsingAtLeastApiVersion('v1beta5'))
    self.assertTrue(command._IsUsingAtLeastApiVersion('v1beta4'))
    self.assertTrue(command._IsUsingAtLeastApiVersion('v1beta2'))

    flag_values.service_version = 'v1beta6'
    command.SetFlags(flag_values)
    self.assertTrue(command._IsUsingAtLeastApiVersion('v1beta6'))
    self.assertTrue(command._IsUsingAtLeastApiVersion('v1beta5'))
    self.assertTrue(command._IsUsingAtLeastApiVersion('v1beta4'))
    self.assertTrue(command._IsUsingAtLeastApiVersion('v1beta2'))

  def testTracing(self):
    class MockComputeApi(object):
      def __init__(self, trace_calls):
        self._trace_calls = trace_calls

      def Disks(self):
        class MockDisksApi(object):
          def __init__(self, trace_calls):
            self._trace_calls = trace_calls

          def Insert(self, trace=None):
            if trace:
              self._trace_calls.append(trace)

        return MockDisksApi(self._trace_calls)

    # Expect no tracing if flag is not set.
    trace_calls = []
    compute = command_base.GoogleComputeCommand.WrapApiIfNeeded(
        MockComputeApi(trace_calls))
    compute.Disks().Insert()
    self.assertEqual(0, len(trace_calls))

    # Expect tracing if trace_token flag is set.
    trace_calls = []
    FLAGS.trace_token = 'THE_TOKEN'
    compute = command_base.GoogleComputeCommand.WrapApiIfNeeded(
        MockComputeApi(trace_calls))
    compute.Disks().Insert()
    self.assertEqual(1, len(trace_calls))
    self.assertEqual('token:THE_TOKEN', trace_calls[0])
    FLAGS.trace_token = ''


  def testWaitForOperation(self):
    complete_name = 'operation-complete'
    running_name = 'operation-running'
    pending_name = 'operation-pending'
    stuck_name = 'operation-stuck'

    base_operation = {'kind': 'cloud#operation',
                      'targetLink': ('https://www.googleapis.com/compute/'
                                     'v1beta100/projects/p/instances/i1'),
                      'operationType': 'insert'}

    completed_operation = dict(base_operation)
    completed_operation.update({'name': complete_name,
                                'status': 'DONE'})
    running_operation = dict(base_operation)
    running_operation.update({'name': running_name,
                              'status': 'RUNNING'})
    pending_operation = dict(base_operation)
    pending_operation.update({'name': pending_name,
                              'status': 'PENDING'})
    stuck_operation = dict(base_operation)
    stuck_operation.update({'name': stuck_name,
                            'status': 'PENDING'})

    next_operation = {complete_name: completed_operation,
                      running_name: completed_operation,
                      pending_name: running_operation,
                      stuck_name: stuck_operation}


    class MockHttpResponse(object):
      def __init__(self, status, reason):
        self.status = status
        self.reason = reason

    class MockHttp(object):
      def request(self_, url, method='GET', body=None, headers=None):
        response = MockHttpResponse(200, 'OK')
        data = '{ "kind": "compute#instance", "name": "i1" }'
        return response, data

    class MockCommand(command_base.GoogleComputeCommand):
      def __init__(self, name, flag_values):
        super(MockCommand, self).__init__(name, flag_values)

      def SetApi(self, api):
        pass

      def Handle(self):
        pass

      def CreateHttp(self):
        return MockHttp()

    class MockTimer(object):
      def __init__(self):
        self._current_time = 0

      def time(self):
        return self._current_time

      def sleep(self, time_to_sleep):
        self._current_time += time_to_sleep
        return self._current_time

    class LocalMockOperationsApi(object):
      def __init__(self):
        self._get_call_count = 0

      def GetCallCount(self):
        return self._get_call_count

      def get(self, project='unused project', operation='operation'):
        unused_project = project
        self._get_call_count += 1
        return mock_api.MockRequest(next_operation[operation])

    flag_values = copy.deepcopy(FLAGS)
    flag_values.sleep_between_polls = 1
    flag_values.max_wait_time = 30
    flag_values.service_version = 'v1beta13'
    flag_values.synchronous_mode = False
    flag_values.project = 'test'

    # Ensure a synchronous result returns immediately.
    timer = MockTimer()
    command = MockCommand('mock_command', flag_values)
    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._global_operations_api = LocalMockOperationsApi()
    diskResult = {'kind': 'cloud#disk'}
    result = command.WaitForOperation(flag_values, timer, diskResult)
    self.assertEqual(0, command._global_operations_api.GetCallCount())

    # Ensure an asynchronous result loops until complete.
    timer = MockTimer()
    command = MockCommand('mock_command', flag_values)
    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._global_operations_api = LocalMockOperationsApi()
    result = command.WaitForOperation(flag_values, timer, pending_operation)
    self.assertEqual(2, command._global_operations_api.GetCallCount())

    # Ensure an asynchronous result eventually times out
    timer = MockTimer()
    command = MockCommand('mock_command', flag_values)
    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._global_operations_api = LocalMockOperationsApi()
    result = command.WaitForOperation(flag_values, timer, stuck_operation)
    self.assertEqual(30, command._global_operations_api.GetCallCount())
    self.assertEqual(result['status'], 'PENDING')

  def testBuildComputeApi(self):
    """Ensures that building of the API from the discovery succeeds."""
    flag_values = copy.deepcopy(FLAGS)
    command = command_base.GoogleComputeCommand('test_cmd', flag_values)
    command._BuildComputeApi(None)

  def testGetZone(self):
    zones = {
        'zone-a': {
            'kind': 'compute#zone',
            'id': '1',
            'creationTimestamp': '2011-07-27T20:04:06.171',
            'selfLink': (
                'https://googleapis.com/compute/v1/projects/p/zones/zone-a'),
            'name': 'zone-a',
            'description': 'Zone zone/a',
            'status': 'UP'},
        'zone-b': {
            'kind': 'compute#zone',
            'id': '2',
            'creationTimestamp': '2012-01-12T00:20:42.057',
            'selfLink': (
                'https://googleapis.com/compute/v1/projects/p/zones/zone-b'),
            'name': 'zone-b',
            'description': 'Zone zone/b',
            'status': 'UP',
            'maintenanceWindows': [
                {
                    'name': '2012-06-24-planned-outage',
                    'description': 'maintenance zone',
                    'beginTime': '2012-06-24T07:00:00.000',
                    'endTime': '2012-07-08T07:00:00.000'
                    }
                ]
            }
        }

    class MockCommand(command_base.GoogleComputeCommand):
      def __init__(self, name, flag_values):
        super(MockCommand, self).__init__(name, flag_values)

      def SetApi(self, api):
        pass

      def Handle(self):
        pass

    class MockZonesApi(object):

      def get(self, zone, **unused_kwargs):
        return mock_api.MockRequest(zones[zone])

    def _PromptForZone():
      return zones['zone-a']

    flag_values = copy.deepcopy(FLAGS)
    command = MockCommand('mock_command', flag_values)
    flag_values.project = 'p'
    command.SetFlags(flag_values)
    command._zones_api = MockZonesApi()
    command._PromptForZone = _PromptForZone

    self.assertEqual(command._GetZone('zone-a'), 'zone-a')
    self.assertEqual(command._GetZone('zone-b'), 'zone-b')
    self.assertEqual(command._GetZone(None), 'zone-a')

  def testGetNextMaintenanceStart(self):
    zone = {
        'kind': 'compute#zone',
        'name': 'zone',
        'maintenanceWindows': [
            {
                'name': 'january',
                'beginTime': '2013-01-01T00:00:00.000',
                'endTime': '2013-01-31T00:00:00.000'
                },
            {
                'name': 'march',
                'beginTime': '2013-03-01T00:00:00.000',
                'endTime': '2013-03-31T00:00:00.000'
                },
            ]
        }

    gnms = command_base.GoogleComputeCommand._GetNextMaintenanceStart
    start = gnms(zone, datetime.datetime(2012, 12, 1))
    self.assertEqual(start, datetime.datetime(2013, 1, 1))
    start = gnms(zone, datetime.datetime(2013, 2, 14))
    self.assertEqual(start, datetime.datetime(2013, 3, 1))
    start = gnms(zone, datetime.datetime(2013, 3, 15))
    self.assertEqual(start, datetime.datetime(2013, 3, 1))

  def testGetZoneForResource(self):
    flag_values = copy.deepcopy(FLAGS)
    expected_project = 'google'
    flag_values.project = expected_project
    flag_values.service_version = 'v1beta13'

    class MockCommand(command_base.GoogleComputeCommand):

      resource_collection_name = 'foos'

      def __init__(self, name, flag_values):
        super(MockCommand, self).__init__(name, flag_values)
        flags.DEFINE_string('zone',
                            None,
                            'Zone name.',
                            flag_values=flag_values)
        self.params = None

      def RunWithFlagsAndPositionalArgs(self, flag_values, pos_arg_values):
        if self._flags != flag_values:
          raise RuntimeError('Flags mismatch')
        self.Handle(*pos_arg_values)

      def Handle(self, param1, param2):
        self.params = (param1, param2)
        return None

    class MockApi(object):
      list_response = None

      def __init__(self):
        pass

      def list(self, **kwargs):
        self.list_parameters = kwargs
        return self.list_response

    class LocalMockZonesApi(object):
      def list(self, project='unused project', maxResults='unused',
               filter='unused'):
        return mock_api.MockRequest({'items': [{'name': 'zone1'}]})

    command = MockCommand('mock_command', flag_values)
    command._zones_api = LocalMockZonesApi()
    api = MockApi()
    command.SetFlags(flag_values)

    # Project-qualified name.
    self.assertEqual(
        command.GetZoneForResource(None, 'projects/foo/zones/bar'), 'bar')

    # Special 'global' zone.
    flag_values.zone = 'global'
    command.SetFlags(flag_values)
    self.assertEqual(
        command.GetZoneForResource(None, command_base.GLOBAL_ZONE_NAME),
        None)

    # Zone name explicitly set.
    flag_values.zone = 'explicitly-set-zone'
    command.SetFlags(flag_values)
    self.assertEqual(
        command.GetZoneForResource(None, 'some-resource'),
        'explicitly-set-zone')


  def testGetUsageWithPositionalArgs(self):

    class MockCommand(command_base.GoogleComputeCommand):
      positional_args = '<arg-1> ... <arg-n>'

    flag_values = copy.deepcopy(FLAGS)
    command = MockCommand('mock_command', flag_values)
    self.assertTrue(command._GetUsage().endswith(
        ' [--global_flags] mock_command [--command_flags] <arg-1> ... <arg-n>'))

  def testGetUsageWithNoPositionalArgs(self):

    class MockCommand(command_base.GoogleComputeCommand):
      pass

    flag_values = copy.deepcopy(FLAGS)
    command = MockCommand('mock_command', flag_values)
    self.assertTrue(command._GetUsage().endswith(
        ' [--global_flags] mock_command [--command_flags]'))


  def testGoogleComputeListCommandPerZone(self):
    flag_values = copy.deepcopy(FLAGS)
    expected_project = 'foo'
    flag_values.project = expected_project
    flag_values.service_version = 'v1beta14'

    object_a = {'description': 'Object A',
                'id': 'projects/user/zones/a/objects/my-object-a',
                'kind': 'cloud#object'}
    object_b = {'description': 'Object B',
                'id': 'projects/user/zones/b/objects/my-object-b',
                'kind': 'cloud#object'}
    list_a = {'items': [object_a],
              'kind': 'cloud#objectList'}
    list_b = {'items': [object_b],
              'kind': 'cloud#objectList'}
    list_all = {'items': [object_a, object_b],
                'kind': 'cloud#objectList'}

    class LocalMockZonesApi(object):
      def list(self, project='unused project', maxResults='unused',
               filter='unused'):
        return mock_api.MockRequest({'items': [{'name': 'a'},
                                               {'name': 'b'}]})

    class ZoneListMockCommand(CommandBaseTest.ListMockCommandBase):
      """A list mock command that represents a zone-scoped collection."""
      is_global_level_collection = False
      is_zone_level_collection = True

      def __init__(self, name, flag_values):
        super(CommandBaseTest.ListMockCommandBase, self).__init__(name,
                                                                  flag_values)
        flags.DEFINE_string('zone',
                            None,
                            'The zone to list.',
                            flag_values=flag_values)

      def ListZoneFunc(self):
        def Func(project=None, maxResults=None, filter=None, pageToken=None,
                 zone=None):
          if zone == 'a':
            return mock_api.MockRequest(list_a)
          else:
            return mock_api.MockRequest(list_b)

        return Func

    command = ZoneListMockCommand('mock_command', flag_values)
    command._zones_api = LocalMockZonesApi()

    # Test single zone
    flag_values.zone = 'a'
    command.SetFlags(flag_values)
    self.assertEqual(list_a, command.Handle())

    # Test all zones
    flag_values.zone = None
    command.SetFlags(flag_values)
    self.assertEqual(list_all, command.Handle())

  def testGoogleComputeListCommandZoneAndGlobal(self):
    flag_values = copy.deepcopy(FLAGS)
    expected_project = 'foo'
    flag_values.project = expected_project
    flag_values.service_version = 'v1beta14'

    object_a = {'description': 'Object A',
                'id': 'projects/user/zones/a/objects/my-object-a',
                'kind': 'cloud#object'}
    object_b = {'description': 'Object B',
                'id': 'projects/user/zones/b/objects/my-object-b',
                'kind': 'cloud#object'}
    object_c = {'description': 'Object C',
                'id': 'projects/user/objects/my-object-c',
                'kind': 'cloud#object'}
    list_global = {'items': [object_c],
                   'kind': 'cloud#objectList'}
    list_a = {'items': [object_a],
              'kind': 'cloud#objectList'}
    list_b = {'items': [object_b],
              'kind': 'cloud#objectList'}
    list_all = {'items': [object_c, object_a, object_b],
                'kind': 'cloud#objectList'}

    class LocalMockZonesApi(object):
      def list(self, project='unused project', maxResults='unused',
               filter='unused'):
        return mock_api.MockRequest({'items': [{'name': 'a'},
                                               {'name': 'b'}]})

    class GlobalAndZoneListMockCommand(CommandBaseTest.ListMockCommandBase):
      """A list mock command that represents a zone-scoped collection."""
      is_global_level_collection = True
      is_zone_level_collection = True

      def __init__(self, name, flag_values):
        super(CommandBaseTest.ListMockCommandBase, self).__init__(name,
                                                                  flag_values)
        flags.DEFINE_string('zone',
                            None,
                            'The zone to list.',
                            flag_values=flag_values)

      def ListZoneFunc(self):
        def Func(project=None, maxResults=None, filter=None, pageToken=None,
                 zone=None):
          if zone == 'a':
            return mock_api.MockRequest(list_a)
          else:
            return mock_api.MockRequest(list_b)
        return Func

      def ListFunc(self):
        def Func(project=None, maxResults=None, filter=None, pageToken=None):
          return mock_api.MockRequest(list_global)
        return Func

    command = GlobalAndZoneListMockCommand('mock_command', flag_values)
    command._zones_api = LocalMockZonesApi()

    # Test single zone
    flag_values.zone = 'a'
    command.SetFlags(flag_values)
    self.assertEqual(list_a, command.Handle())

    # Test 'global' zone
    flag_values.zone = 'global'
    command.SetFlags(flag_values)
    self.assertEqual(list_global, command.Handle())

    # Test all
    flag_values.zone = None
    command.SetFlags(flag_values)
    self.assertEqual(list_all, command.Handle())


if __name__ == '__main__':
  unittest.main()
