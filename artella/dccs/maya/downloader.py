#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains Maya DCC scene file parser implementation
"""

from __future__ import print_function, division, absolute_import

import sys
import time
import logging

from artella import api
from artella.core import utils, splash

from artella.externals.Qt import QtCore, QtWidgets

logger = logging.getLogger('artella')


class MayaDowndloaderWorkerSignals(QtCore.QObject):
    finished = QtCore.Signal()
    statusUpdated = QtCore.Signal(str, int, int, int, int, int)


class MayaDownloaderWorker(QtCore.QRunnable):
    def __init__(self, artella_drive_client, file_paths):
        super(MayaDownloaderWorker, self).__init__()

        self.signals = MayaDowndloaderWorkerSignals()

        self._artella_drive_client = artella_drive_client
        self._file_paths = file_paths

    def run(self):
        if not self._artella_drive_client or not self._file_paths:
            self.signals.finished.emit()
            return

        self._artella_drive_client.download(self._file_paths)

        # We force the waiting to a high value, otherwise Artella Drive Client will return that no download
        # is being processed
        time.sleep(3.5)

        while True:
            progress, fd, ft, bd, bt = self._artella_drive_client.get_progress()
            current = int(bd / 1024)
            total = int(bt / 1024)
            progress_status = '{}/{} KiB'.format(current, total)
            self.signals.statusUpdated.emit(progress_status, progress, current, total, fd, ft)
            if progress >= 100 or bd == bt:
                break

        self.signals.finished.emit()


class MayaSceneParserThreadPool(QtCore.QObject):

    poolStarted = QtCore.Signal(list)
    poolFinished = QtCore.Signal()
    workerFinished = QtCore.Signal()
    workerStatusUpdated = QtCore.Signal(str, int, int, int, int, int)

    def __init__(self, max_thread_count=1):
        super(MayaSceneParserThreadPool, self).__init__()

        self._pool = QtCore.QThreadPool()
        self._pool.setMaxThreadCount(max_thread_count)

    def _on_worker_finished(self):
        self.workerFinished.emit()
        self.poolFinished.emit()

    def start(self, artella_drive_client, file_paths):
        self._file_paths = file_paths
        self._processed = 0

        self.poolStarted.emit(file_paths)

        worker = MayaDownloaderWorker(artella_drive_client, file_paths)
        worker.signals.finished.connect(self._on_worker_finished)
        worker.signals.statusUpdated.connect(self.workerStatusUpdated.emit)
        self._pool.start(worker)
        time.sleep(0.1)


class MayaDownloader(QtCore.QObject, object):
    """
    Class that defines Maya scene parser functions
    """

    def __init__(self):
        super(MayaDownloader, self).__init__()

        self._finished = False
        self._total_files = 0
        self._downloaded_files = list()

        self._progress_splash = None

        self._thread_pool = MayaSceneParserThreadPool(max_thread_count=10)
        self._thread_pool.poolStarted.connect(self._on_start_parsing)
        # self._thread_pool.workerFinished.connect(self._on_worker_finished)
        self._thread_pool.poolFinished.connect(self._on_download_finished)
        self._thread_pool.workerStatusUpdated.connect(self._on_status_updated)

    @utils.timestamp
    def download(self, file_paths=None, show_dialogs=True):
        """
        Parses all the contents of the given file path looking for file paths

        :param str or None file_paths: Absolute local file paths of the DCC file we want to parse. If not given,
            current opened DCC scene file path will be used
        :return:
        """

        self._finished = False

        artella_drive_client = api.get_client()
        if not artella_drive_client or not artella_drive_client.check(update=True):
            self._finished = True
            return self._downloaded_files

        if show_dialogs:
            self._progress_splash = splash.DownloadSplashDialog(downloader=self)
            # self._thread_pool.workerStatusUpdated.connect(self._progress_splash.update_download)

        file_paths = utils.force_list(file_paths)
        if not file_paths:
            return

        self._thread_pool.start(artella_drive_client, file_paths)

        if self._progress_splash:
            self._progress_splash.download(file_paths)
        else:
            while not self._finished:
                time.sleep(0.1)

        return self._downloaded_files

    def _on_start_parsing(self, file_paths):
        """
        Internal callback function that is called just before parsing process
        """

        self._total_files = len(file_paths)
        if self._progress_splash:
            self._progress_splash.set_max_progress_value(100)
            self._progress_splash.set_min_progress_value(0)
            self._progress_splash.set_progress_value(0, 'Downloading files ...')
            self._progress_splash.set_infinite(True)
            self._progress_splash.repaint()

    def _on_status_updated(self, status, progress, download_size, total_size, downloaded_files, total_files):
        if self._progress_splash and progress:
            self._progress_splash.set_infinite(False)
            status = '{} ({} / {})'.format(status, downloaded_files, total_files)
            self._progress_splash.set_max_progress_value(total_size)
            self._progress_splash.set_progress_value(download_size, status)

    def _on_download_finished(self):
        if self._progress_splash:
            self._progress_splash.end()

        self._downloaded_files = list(set(self._downloaded_files))

        self._finished = True

    # def _on_worker_finished(self, file_path):
    #     self._downloaded_files.append(file_path)
    #     if self._progress_splash:
    #         next_progress = self._progress_splash.get_progress_value() + 1
    #         self._progress_splash.set_progress_value(
    #             next_progress, 'Downloading files ... ({} / {})'.format(next_progress, self._total_files))


if __name__ == '__main__':
    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication(sys.argv)

    import artella.loader
    plugin_paths = [r'D:\dev\artella\plugins']
    dcc_paths = [r'D:\dev\artella\dccs']
    artella.loader.init(dev=True, dcc_paths=dcc_paths, plugin_paths=plugin_paths)

    files_to_download = [
        r"D:\shorts\artella-files\Crucible\Production\Seq-001\Shot-001\Anim\Shot-001-anim.ma",
        r"D:\shorts\artella-files\Showcase 2020\Production\Shot_114\Assets\overlord_baker.ma"
    ]
    parser = MayaDownloader()
    parsed_files = parser.download(files_to_download, show_dialogs=True)
    for parsed_file in parsed_files:
        print(parsed_file)

    sys.exit(app.exec_())
