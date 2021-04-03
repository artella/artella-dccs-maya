#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains Maya DCC scene file parser implementation
"""

from __future__ import print_function, division, absolute_import

import os
import sys
import time
import logging
import traceback
from collections import OrderedDict

from artella import api, dcc
from artella.core import utils, splash

from artella.externals.Qt import QtCore, QtWidgets

MAYA_AVAILBLE = True
try:
    import maya.cmds as cmds
    from artella.dccs.maya import utils as maya_utils
except ImportError:
    MAYA_AVAILBLE = False

from artella.dccs.maya import mayapy_parser

logger = logging.getLogger('artella')


class MayaSceneParserWorkerSignals(QtCore.QObject):
    finished = QtCore.Signal(str, dict)


class MayaSceneParserWorker(QtCore.QRunnable):
    def __init__(self, file_path, projects_path):
        super(MayaSceneParserWorker, self).__init__()

        self.signals = MayaSceneParserWorkerSignals()

        self._file_path = file_path
        self._projects_path = projects_path
        self._recursive = True

    def run(self):
        out_dict = mayapy_parser.parse(
            self._file_path, projects_path=self._projects_path, recursive=self._recursive) or dict()
        self.signals.finished.emit(self._file_path, out_dict)


class MayaAsciiSceneParserWorker(QtCore.QRunnable):
    def __init__(self, file_path):
        super(MayaAsciiSceneParserWorker, self).__init__()

        self.signals = MayaSceneParserWorkerSignals()

        self._file_path = file_path

    def run(self):
        ascii_parser = MayaAsciiParser()
        with open(self._file_path, 'rb') as file_object:
            ascii_parser.parse(file_object=file_object)

        parsed_file_paths = [utils.clean_path(parsed_path) for parsed_path in ascii_parser.get_depend_paths()]
        if self._file_path in parsed_file_paths:
            parsed_file_paths.pop(parsed_file_paths.index(self._file_path))

        parsed_file_paths = list(set(parsed_file_paths))

        out_dict = {
            'success': True,
            'result': {self._file_path: parsed_file_paths}
        }

        self.signals.finished.emit(self._file_path, out_dict)


class MayaSceneParserThreadPool(QtCore.QObject):

    poolStarted = QtCore.Signal(list)
    poolFinished = QtCore.Signal()
    workerFinished = QtCore.Signal(str, dict)
    workerStarted = QtCore.Signal(str)

    def __init__(self, max_thread_count=1):
        super(MayaSceneParserThreadPool, self).__init__()

        self._count = 0
        self._processed = 0
        self._has_errors = False

        self._pool = QtCore.QThreadPool()
        self._pool.setMaxThreadCount(max_thread_count)

    def _on_worker_finished(self, file_path, out_dict):
        self.workerFinished.emit(file_path, out_dict)
        self._processed += 1
        if self._processed == len(self._file_paths):
            self.poolFinished.emit()

    def start(self, file_paths, projects_path, force_mayapy_parser=False):
        self._file_paths = file_paths
        self._processed = 0
        self._has_errors = False

        self.poolStarted.emit(file_paths)

        for file_path in file_paths:

            as_ascii_file = False
            if not force_mayapy_parser:
                file_extension = os.path.splitext(file_path)[-1]
                if file_extension == '.ma':
                    as_ascii_file = True
                    file_size = utils.get_file_size(file_path)
                    if file_size > 60.0:        # 60MB
                        as_ascii_file = False

            # In MacOS, we force the usage of the old parser
            if sys.platform == 'darwin':
                as_ascii_file = True

            if as_ascii_file:
                worker = MayaAsciiSceneParserWorker(file_path)
            else:
                worker = MayaSceneParserWorker(file_path, projects_path)
            worker.signals.finished.connect(self._on_worker_finished)
            if len(file_paths) == 1:
                self.workerStarted.emit(file_path)
            self._pool.start(worker)
            time.sleep(0.1)


class MayaSceneParser(QtCore.QObject, object):
    """
    Class that defines Maya scene parser functions
    """

    def __init__(self):
        super(MayaSceneParser, self).__init__()

        self._out = dict()
        self._finished = False
        self._total_files = 0
        self._parsed_files = OrderedDict()

        self._progress_splash = None

        self._thread_pool = MayaSceneParserThreadPool(max_thread_count=10)
        self._thread_pool.poolStarted.connect(self._on_start_parsing)
        self._thread_pool.workerStarted.connect(self._on_worker_started)
        self._thread_pool.workerFinished.connect(self._on_worker_finished)
        self._thread_pool.poolFinished.connect(self._on_parsed_finished)

    @utils.timestamp
    def parse(self, file_paths=None, show_dialogs=True, projects_path=None, force_mayapy_parser=False):
        """
        Parses all the contents of the given file path looking for file paths

        :param str or None file_paths: Absolute local file paths of the DCC file we want to parse. If not given,
            current opened DCC scene file path will be used
        :return:
        """

        self._finished = False

        if show_dialogs:
            self._progress_splash = splash.ProgressSplashDialog()

        file_paths = utils.force_list(file_paths)
        if not file_paths:
            file_paths = [dcc.scene_name()]

        valid_file_paths = list()
        for file_path in file_paths:
            if not file_path or not os.path.isfile(file_path):
                logger.warning('Given file to parse does not exists! Skipping file ...'.format(file_path))
                continue
            file_path = utils.clean_path(file_path)
            file_ext = os.path.splitext(file_path)[-1]
            if file_ext not in ('.ma', '.mb'):
                logger.warning(
                    'Given file path extension ({}) is not a recognized Maya file extension (.ma, .mb).'.format(
                        file_ext))
                continue
            valid_file_paths.append(utils.clean_path(file_path))
        if not valid_file_paths:
            logger.warning('No valid file paths to parse. Stopping parsing operation ...')
            return

        valid_file_paths = list(set(valid_file_paths))
        self._thread_pool.start(valid_file_paths, projects_path, force_mayapy_parser)

        if self._progress_splash:
            self._progress_splash.start(reset=False, infinite=True)
        else:
            while not self._finished:
                time.sleep(0.1)

        return self._parsed_files

    def _on_start_parsing(self, file_paths):
        """
        Internal callback function that is called just before parsing process
        """

        self._total_files = len(file_paths)
        if self._progress_splash:
            self._progress_splash.set_max_progress_value(100)
            self._progress_splash.set_progress_value(0, 'Parsing files ... (0 / {})'.format(self._total_files))
            self._progress_splash.repaint()

    def _on_parsed_finished(self):

        try:
            for parsed_file, parsed_data in self._out.items():
                error = parsed_data.get('error', None)
                success = parsed_data.get('success', False)
                log = parsed_data.get('log', '')
                msg = parsed_data.get('msg', '')
                result = parsed_data.get('result', list())

                if not success:
                    logger.error('Something went wrong while parsing dependencies of file: "{}"'.format(parsed_file))
                    logger.error('Error message: {}'.format(error))
                    logger.error('Log message: {}'.format(log))
                    logger.error('Maya output: \n{}'.format(msg))
                    continue

                if msg:
                    logger.info('Something went wrong while getting dependencies. Check log file for more information.')
                    logger.debug(msg)
                logger.debug(log)

                self._parsed_files.update(result)

            if self._progress_splash:
                self._progress_splash.end()

            self._finished = True
        except Exception:
            logger.error(traceback.format_exc())
            if self._progress_splash:
                self._progress_splash.end()
            self._finished = True

    def _on_worker_started(self, file_path):
        if self._progress_splash:
            self._progress_splash.set_progress_text(os.path.basename(file_path))

    def _on_worker_finished(self, file_path, out_dict):
        self._out[file_path] = out_dict
        if self._progress_splash:
            next_progress = self._progress_splash.get_progress_value() + 1
            self._progress_splash.set_progress_value(
                next_progress, 'Parsing files ... ({} / {})'.format(next_progress, self._total_files))

    def update_paths(self, file_path=None):
        """
        Converts all file path of the given DCC file to make sure they point to valid Artella file paths

        :param str or None file_path: Absolute local file path of the DCC file we want to parse. If not given,
            current opened DCC scene file path will be used
        :return:
        """

        valid_update = False
        converted_file_paths = list()

        if not MAYA_AVAILBLE:
            logger.warning('Convert Paths functionality is only available if Maya instance is running!')
            return valid_update, converted_file_paths

        if not file_path:
            file_path = dcc.scene_name()

        if not file_path or not os.path.isfile(file_path):
            logger.warning('Given file to parse does not exists! Skipping convert paths process'.format(file_path))
            return valid_update, converted_file_paths

        file_ext = os.path.splitext(file_path)[-1]
        if file_ext not in dcc.extensions():
            logger.warning(
                'Given file path has an invalid extension: {}. Supported extensions: {}'.format(
                    file_ext, dcc.extensions()))
            return valid_update, converted_file_paths

        if file_path != dcc.scene_name():
            dcc.open_scene(file_path, save=True)

        cmds.filePathEditor(refresh=True)
        dirs = cmds.filePathEditor(query=True, listDirectories='')
        if not dirs:
            logger.debug('File "{}" has no paths to update!'.format(dirs))
            return valid_update, converted_file_paths

        valid_update = True

        file_path_editors = dict()
        for dir_name in dirs:
            try:
                file_path_editor = cmds.filePathEditor(query=True, listFiles=dir_name, withAttribute=True)
            except Exception as exc:
                logger.error(
                    'Querying scene files in dir "{}" looking for dependent files: {}'.format(dir_name, exc))
                return valid_update, converted_file_paths
            if not file_path_editor:
                continue
            file_path_editors[dir_name] = file_path_editor

        for dir_name, file_path_editor in file_path_editors.items():
            if not api.is_artella_path(dir_name):
                continue
            i = 0
            while i < len(file_path_editor):
                file_name = file_path_editor[i]
                node_attr_name = file_path_editor[i + 1]
                try:
                    reference_file_path = maya_utils.get_reference_file(node_attr_name, unresolved_name=True)
                    if api.is_path_translated(reference_file_path):
                        continue
                finally:
                    i += 2
                maya_dir = api.translate_path(dir_name)
                maya_file_path = utils.clean_path(os.path.join(dir_name, file_name))
                translated_path = utils.clean_path(os.path.join(maya_dir, file_name))
                converted_path = api.convert_path(translated_path)

                logger.info(
                    'Converting Path: {} | {} >>>>>>> {}'.format(node_attr_name, maya_file_path, converted_path))
                res = self._update_attr_path(node_attr_name, converted_path)
                if not res:
                    valid_update = False
                converted_file_paths.append(translated_path)
                converted_file_paths.append(converted_path)

        return valid_update, converted_file_paths

    def _update_attr_path(self, node_attr_name, file_path):

        node_name = node_attr_name.split('.')[0]

        if maya_utils.is_reference_node(node_name):
            valid_update = True
            try:
                maya_utils.replace_reference(node_name, file_path)
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


class MayaAsciiParser(object):
    """
    Class that defines Maya scene parser for Maya ASCII files
    """

    def __init__(self):
        super(MayaAsciiParser, self).__init__()

        self._command_handlers = {
            'file': self._handle_file,
            'setAttr': self._handle_set_attr
        }

        self._stream = None

        self._reference_file_paths = list()  # List of reference file paths in parsed Maya scene file

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

    @utils.timestamp
    def parse(self, file_object):
        """
        Parses all the contents of the given file path looking for file paths
        :param file file_object: Python file object that contains stream of text data we want to parse
        :return:
        """

        self._stream = file_object

        while self._parse_next_command():
            pass

        self._stream = None

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

        pass

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


if __name__ == '__main__':
    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication(sys.argv)
    projects_path = r'D:\shorts\artella-files'
    # file_paths = [r"D:\shorts\artella-files\06 Flight Assets\06 Flight Assets\Arc Dragon\arcTheDragon_v1.61.ma"]
    # file_paths = [r"D:\shorts\artella-files\Showcase 2020\Production\Shot_114\Assets\overlord_baker.ma"]

    file_paths = [
        r"D:\shorts\artella-files\Crucible\Production\Seq-001\Shot-001\Anim\Shot-001-anim.ma",
        r"D:\shorts\artella-files\Showcase 2020\Production\Shot_114\Assets\overlord_baker.ma"
    ]
    parser = MayaSceneParser()
    parsed_files = parser.parse(file_paths, projects_path=projects_path)
    for parsed_file in parsed_files:
        print(parsed_file)

    sys.exit(app.exec_())
