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

    @utils.timestamp
    def run(self):
        out_dict = mayapy_parser.parse(
            self._file_path, projects_path=self._projects_path, recursive=self._recursive) or dict()
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

    def start(self, file_paths, projects_path):
        self._file_paths = file_paths
        self._processed = 0
        self._has_errors = False

        self.poolStarted.emit(file_paths)

        for file_path in file_paths:
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
    def parse(self, file_paths=None, show_dialogs=True, projects_path=None):
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
        self._thread_pool.start(valid_file_paths, projects_path)

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
        for parsed_file, parsed_data in self._out.items():
            error = parsed_data.get('error', None)
            success = parsed_data.get('success', False)
            log = parsed_data.get('log', '')
            msg = parsed_data.get('msg', '')
            result = parsed_data.get('result', list())

            if not success:
                logger.error('Something went wrong while parsing dependencies of file: "{}"'.format(parsed_file))
                logger.error('Error message: {}'.format(msg))
                logger.error('Log message: {}'.format(log))
                logger.error('Maya output: \n{}'.format(error))
                continue

            if msg:
                logger.info('Something went wrong while getting dependencies. Check log file for more information.')
                logger.debug(msg)
            logger.debug(log)

            self._parsed_files.update(result)

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

        # with open(file_path, 'rb') as file_object:
        #     parser.parse(file_object=file_object, show_dialogs=show_dialogs)
        #
        # parsed_file_paths = [utils.clean_path(parsed_path) for parsed_path in parser.get_depend_paths()]
        # if file_path in parsed_file_paths:
        #     parsed_file_paths.pop(parsed_file_paths.index(file_path))
        #
        # return list(set(parsed_file_paths))

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

        converted_file_paths = list()
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
