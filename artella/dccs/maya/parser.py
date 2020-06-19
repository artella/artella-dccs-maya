#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains Maya DCC scene file parser implementation
"""

from __future__ import print_function, division, absolute_import

import os
import logging

import artella
import artella.dcc as dcc
import artella. register as register
from artella.core import utils, qtutils, splash
from artella.core.dcc import parser

if qtutils.QT_AVAILABLE:
    from artella.externals.Qt import QtWidgets

MAYA_AVAILBLE = True
try:
    import maya.cmds as cmds
    from artella.dccs.maya import utils as maya_utils
except ImportError:
    MAYA_AVAILBLE = False

logger = logging.getLogger('artella')


class MayaSceneParser(parser.AbstractSceneParser, object):
    """
    Class that defines Maya scene parser functions
    """

    def __init__(self):
        super(MayaSceneParser, self).__init__()

    def parse(self, file_path=None):
        """
        Parses all the contents of the given file path looking for file paths

        :param str or None file_path: Absolute local file path of the DCC file we want to parse. If not given,
            current opened DCC scene file path will be used
        :return:
        """

        if not file_path:
            file_path = dcc.scene_name()

        if not file_path or not os.path.isfile(file_path):
            logger.warning('Given file to parse does not exists! Skipping parsing process ...'.format(file_path))
            return list()

        file_path = utils.clean_path(file_path)
        file_ext = os.path.splitext(file_path)[-1]
        if file_ext == '.ma':
            parser = MayaSceneParser.MayaAsciiParser()
        elif file_ext == '.mb':
            parser = MayaSceneParser.MayaBinaryParser()
        else:
            logger.warning(
                'Given file path extension ({}) is not a recognized Maya file extension (.ma, .mb).'.format(file_ext))
            return list()

        with open(file_path, 'rb') as file_object:
            parser.parse(file_object=file_object)

        parsed_file_paths = [utils.clean_path(parsed_path) for parsed_path in parser.get_depend_paths()]
        if file_path in parsed_file_paths:
            parsed_file_paths.pop(parsed_file_paths.index(file_path))

        return list(set(parsed_file_paths))

    def update_paths(self, file_path=None):
        """
        Converts all file path of the given DCC file to make sure they point to valid Artella file paths

        :param str or None file_path: Absolute local file path of the DCC file we want to parse. If not given,
            current opened DCC scene file path will be used
        :return:
        """

        if not MAYA_AVAILBLE:
            logger.warning('Convert Paths functionality is only available if Maya instance is running!')
            return False

        if not file_path:
            file_path = dcc.scene_name()

        if not file_path or not os.path.isfile(file_path):
            logger.warning('Given file to parse does not exists! Skipping convert paths process'.format(file_path))
            return False

        file_ext = os.path.splitext(file_path)[-1]
        if file_ext not in dcc.extensions():
            logger.warning(
                'Given file path has an invalid extension: {}. Supported extensions: {}'.format(
                    file_ext, dcc.extensions()))
            return False

        if file_path != dcc.scene_name():
            dcc.open_scene(file_path, save=True)

        cmds.filePathEditor(refresh=True)
        dirs = cmds.filePathEditor(query=True, listDirectories='')
        if not dirs:
            logger.debug('File "{}" has no paths to update!'.format(dirs))
            return False

        valid_update = True

        file_path_editors = dict()
        for dir_name in dirs:
            try:
                file_path_editor = cmds.filePathEditor(query=True, listFiles=dir_name, withAttribute=True)
            except Exception as exc:
                logger.error(
                    'Querying scene files in dir "{}" looking for dependent files: {}'.format(dir_name, exc))
                return
            if not file_path_editor:
                continue
            file_path_editors[dir_name] = file_path_editor

        for dir_name, file_path_editor in file_path_editors.items():
            i = 0
            while i < len(file_path_editor):
                file_name = file_path_editor[i]
                node_attr_name = file_path_editor[i + 1]
                i += 2
                maya_dir = artella.DccPlugin().translate_path(dir_name)
                maya_file_path = utils.clean_path(os.path.join(dir_name, file_name))
                translated_path = utils.clean_path(os.path.join(maya_dir, file_name))
                converted_path = artella.DccPlugin().convert_path(translated_path)

                logger.info(
                    'Converting Path: {} | {} >>>>>>> {}'.format(node_attr_name, maya_file_path, converted_path))
                res = self._update_attr_path(node_attr_name, converted_path)
                if not res:
                    valid_update = False

        return valid_update

    def _update_attr_path(self, node_attr_name, file_path):

        node_name = node_attr_name.split('.')[0]

        if maya_utils.is_reference_node(node_name):
            is_loaded = maya_utils.is_reference_loaded(node_name)
            valid_update = True
            if is_loaded:
                try:
                    maya_utils.unload_reference(node_name)
                except RuntimeError as exc:
                    logger.error(
                        'Encountered an error while attempting to unload reference file: "{}" | {}'.format(
                            node_name, exc))
                    valid_update = False
            try:
                maya_utils.load_reference(file_path, node_name)
            except RuntimeError as exc:
                logger.error(
                    'Encountered an error while attempting to load reference file "{}" '
                    'using the updated file path: "{}" | {}'.format(node_name, file_path, exc))
                valid_update = False
        else:
            if '.' not in node_attr_name:
                logger.warning(
                    'Unable to identify attribute of {} for file value {}'.format(node_attr_name, file_path))
                return False

            try:
                attr_value = cmds.getAttr(node_attr_name, sl=True)
            except Exception as exc:
                logger.warning('Unable to query attributes for "{}" | {}'.format(node_attr_name, exc))
                return False

            if isinstance(attr_value, list):
                valid_update = True
                for value in attr_value:
                    res = self._update_attribute_value(node_attr_name, file_path, value)
                    if not res:
                        valid_update = False
            else:
                valid_update = self._update_attribute_value(node_attr_name, file_path, attr_value)

        return valid_update

    def _update_attribute_value(self, node_attr_name, file_path, current_value):

        if current_value == file_path:
            return True
        node_name = node_attr_name.split('.')[0]
        valid_update = maya_utils.replace_reference(node_name, file_path)
        if not valid_update:
            cmds.setAttr(node_attr_name, file_path, type='string')
            new_value = cmds.getAttr(node_attr_name, sl=True)
            if new_value != file_path:
                valid_update = False
                logger.warning(
                    'Attempted {} updated was not successful for {} current value is {}'.format(
                        node_attr_name, file_path, new_value))
            else:
                valid_update = True

        return valid_update

    class MayaParserBase(object):
        """
        Class that defines base Maya scene parser
        """

        def __init__(self):
            super(MayaSceneParser.MayaParserBase, self).__init__()

            self._command_handlers = {
                'file': self._handle_file,
                'setAttr': self._handle_set_attr
            }

            self._stream = None

            self._reference_file_paths = list()     # List of reference file paths in parsed Maya scene file

        def get_depend_paths(self):
            """
            Returns all file paths parsed file path depends on

            :return: List of absolute local file paths current parsed DCC scene depends on
            :rtype: list(str)
            """

            return self._reference_file_paths

        def has_command(self, command):
            """
            Returns whether or not given command should be parsed
            :param str command: Maya command ('fileInfo', file', 'setAttr', etc)

            :return: True if the parser should parse given command; False otherwise.
            :rtype: bool
            """

            return command in self._command_handlers

        def handle_command(self, command, args):
            """
            Handles command with given arguments by calling specific parsing command function
            This parsing is defined in _command_handlers variable.

            :param str command: command parser needs to handle
            :param list(args) args: list of arguments the command expects to have
            """

            handler_fn = self._command_handlers.get(command, None)
            if handler_fn:
                handler_fn(args)

        def _handle_file(self, args):

            arg_index = 0
            while arg_index < len(args):
                arg = args[arg_index]
                if arg in ("-r", "--reference"):
                    arg_index += 1
                elif arg in ("-rdi", "--referenceDepthInfo"):
                    arg_index += 2
                elif arg in ("-ns", "--namespace"):
                    arg_index += 2
                elif arg in ("-dr", "--deferReference"):
                    arg_index += 2
                elif arg in ("-rfn", "--referenceNode"):
                    arg_index += 2
                elif arg in ('-op'):
                    arg_index += 2
                elif arg in ('-typ'):
                    arg_index += 2
                else:
                    break

            if arg_index < len(args):
                file_path = args[arg_index]
                if file_path not in self._reference_file_paths:
                    self._reference_file_paths.append(file_path)

        def _handle_set_attr(self, args):

            name = args.pop(0)[1:]
            attr_type = None
            value = None

            arg_index = 1
            while arg_index < len(args):
                arg = args[arg_index]
                if arg in ("-type", "--type"):
                    attr_type = args[arg_index + 1]
                    value = args[arg_index + 2:]
                    arg_index += 2
                else:
                    arg_index += 1

            if not value:
                value = args[-1]

            if not attr_type:
                attr_type = 'string'

            if attr_type == 'string' and name in ['ftn']:
                self._reference_file_paths.append(value)

    class MayaAsciiParser(MayaParserBase, object):
        """
        Class that defines Maya scene parser for Maya ASCII files
        """

        def __init__(self):
            super(MayaSceneParser.MayaAsciiParser, self).__init__()

            self._progress_splash = None

        @utils.timestamp
        def parse(self, file_object, show_dialogs=True):
            """
            Parses all the contents of the given file path looking for file paths

            :param file file_object: Python file object that contains stream of text data we want to parse
            :return:
            """

            self._stream = file_object
            file_name = os.path.basename(self._stream.name)

            if show_dialogs and qtutils.QT_AVAILABLE:
                self._progress_splash = splash.ProgressSplashDialog()
                self._progress_splash.set_progress_text('Please wait ...'.format(file_name))
                self._progress_splash.start()

            value = 0
            while self._parse_next_command():
                value += 1
                if value > 250:
                    next_index = self._progress_splash.get_progress_value() + 1
                    if next_index > 100:
                        next_index = 1
                    self._progress_splash.set_progress_value(next_index, 'Parsing file: {}'.format(file_name))
                    QtWidgets.QApplication.instance().processEvents()
                    value = 0

            if self._progress_splash:
                self._progress_splash.close()

        def _parse_next_command(self):
            """
            Internal function that parses next command available in the Maya ASCII currently being parsed

            :return: True if the parse command operation is successful; False otherwise
            :rtype: bool
            """

            lines = list()

            line = self._stream.readline()
            while True:
                if not line:
                    break
                elif line.startswith('//'):
                    pass
                else:
                    line = line.rstrip('\r\n')
                    if line and line.endswith(';'):
                        lines.append(line[:-1])
                        break
                    elif line:
                        lines.append(line)
                line = self._stream.readline()

            if lines:
                self._parse_command_lines(lines)
                return True

            return False

        def _parse_command_lines(self, lines):
            """
            Internal function that parses all the lines of a specific Maya command found in Maya ASCII file

            :param list(str) lines: List of lines a Maya specific command is composed of
            :return:
            """

            command, _, lines[0] = lines[0].partition(' ')
            command = command.lstrip()

            if not self.has_command(command):
                return None

            args = list()
            for line in lines:
                while True:
                    line = line.strip()
                    if not line:
                        break

                    if line[0] in "'\"":
                        string_delim = line[0]
                        escaped = False
                        string_end = len(line)

                        for i in range(1, len(line)):
                            if not escaped and line[i] == string_delim:
                                string_end = i
                                break
                            elif not escaped and line[i] == "\\":
                                escaped = True
                            else:
                                escaped = False
                        arg, line = line[1:string_end], line[string_end + 1:]
                    else:
                        arg, _, line = line.partition(" ")

                    args.append(arg)

            self.handle_command(command, args)

    class MayaBinaryParser(MayaParserBase, object):
        """
        Class that defines Maya scene parser for Maya binary files
        """

        def __init__(self):
            super(MayaSceneParser.MayaBinaryParser, self).__init__()

            self._maya64 = False
            self._node_chunk_type = None
            self._list_chunk_type = None
            self._iff_parser = None
            self._mtypeid_to_typename = dict()

            self.MAYA_BINARY_32 = maya_utils.IffParser.IffFormat(
                endianness=maya_utils.IffParser.IFF_BIG_ENDIAN, typeid_bytes=4,
                size_bytes=4, header_alignment=4, chunk_alignment=4)

            self.MAYA_BINARY_64 = maya_utils.IffParser.IffFormat(
                endianness=maya_utils.IffParser.IFF_BIG_ENDIAN, typeid_bytes=4,
                size_bytes=8, header_alignment=8, chunk_alignment=8)

        # ==============================================================================================================
        # PARSE
        # ==============================================================================================================

        def parse(self, file_object):
            """
            Parses all the contents of the given file path looking for file paths

            :param file file_object: Python file object that contains stream of binary data we want to parse
            :return:
            """

            self._stream = file_object

            # Check Maya binary format based on magic number
            # Maya 2014+ files begin with a FOR8 block, indicating a 64-bit format
            magic_number = self._stream.read(4)
            self._stream.seek(0)
            if magic_number == 'FOR4':
                iff_format = self.MAYA_BINARY_32
            elif magic_number == 'FOR8':
                iff_format = self.MAYA_BINARY_64
            else:
                logger.error('Bad magic number found in Maya Binary File. Was not possible to read!')
                return

            self._maya64 = iff_format == self.MAYA_BINARY_64

            self._iff_parser = maya_utils.MayaIffParser(self._stream, iff_format, maya64=self._maya64)

            self._iff_parser.parse()

            utils.clear_list(self._reference_file_paths)
            for ref_path in self._iff_parser.references:
                if ref_path not in self._reference_file_paths:
                    self._reference_file_paths.append(ref_path)


register.register_class('Parser', MayaSceneParser)
