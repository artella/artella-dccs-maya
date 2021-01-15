#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains Maya DCC progress bar implementation
"""

from __future__ import print_function, division, absolute_import

import logging

import maya.cmds as cmds

from artella.core.dcc import progress
from artella.dccs.maya import utils

logger = logging.getLogger('artella')


class MayaProgressBar(progress.BaseProgressBar, object):
    """
    Class that defines progress bar Maya functions
    """

    PROGRESS_UI = None
    USE_WINDOW = True

    def __init__(self):
        super(MayaProgressBar, self).__init__()

        self._count = 0             # Variable used to store current progress bar progress value
        self._min_count = 0         # Variable used to store current progress bar minimum value
        self._max_count = 100       # Variable used to store current progress bar maximum value
        self._title = ''            # Variable used to store current progress bar title
        self._status = ''           # Variable used to store current progress bar status text

    def can_be_interrupted(self):
        """
        Returns whether or not DCC progress bar can be interrupted or not
        :return: True if the progress bar can be interrupted by the user; False otherwise.
        :rtype: bool
        """

        return True

    def is_cancelled(self):
        """
        Returns whether or not DCC progress bar has been cancelled by the user

        :return: True if the progres bar has been cancelled by the user; False otherwise.
        :rtype: bool
        """

        if self._is_batch():
            return self._max_count

        if self.USE_WINDOW:
            return cmds.progressWindow(query=True, isCancelled=True)
        else:
            if not self.PROGRESS_UI:
                return self._max_count
            return cmds.progressBar(self.PROGRESS_UI, query=True, isCancelled=True)

    def get_max_progress_value(self):
        """
        Returns the maximum value of the progress bar

        :return: Maximum value progress bar can accept
        :rtype: int
        """

        self._log_progress()

        if self._is_batch():
            return self._max_count

        if self.USE_WINDOW:
            return cmds.progressWindow(self.PROGRESS_UI, query=True, maxValue=True)
        else:
            if not self.PROGRESS_UI:
                return self._max_count
            return cmds.progressBar(self.PROGRESS_UI, query=True, maxValue=True)

    def set_max_progress_value(self, max_value):
        """
        Sets the maximum value of the progress bar

        :param int max_value: Maximum value progress bar can accept
        """

        self._max_count = int(max_value)
        self._log_progress()

        if self._is_batch():
            return

        if self.USE_WINDOW:
            cmds.progressWindow(edit=True, maxValue=self._max_count)
        else:
            if not self.PROGRESS_UI:
                return
            cmds.progressBar(self.PROGRESS_UI, edit=True, maxValue=self._max_count)

    def get_min_progress_value(self):
        """
        Returns the minimum value of the progress bar

        :return: Minimum value progress bar can accept
        :rtype: int
        """

        self._log_progress()

        if self._is_batch():
            return self._min_count

        if self.USE_WINDOW:
            return cmds.progressWindow(self.PROGRESS_UI, query=True, minValue=True)
        else:
            if not self.PROGRESS_UI:
                return self._min_count
            return cmds.progressBar(self.PROGRESS_UI, query=True, minValue=True)

    def set_min_progress_value(self, min_value):
        """
        Sets the minimum value of the progress bar

        :param int min_value: Minimum value progress bar can accept
        """

        self._min_count = int(min_value)
        self._log_progress()

        if self._is_batch():
            return

        if self.USE_WINDOW:
            cmds.progressWindow(edit=True, minValue=self._max_count)
        else:
            if not self.PROGRESS_UI:
                return
            cmds.progressBar(self.PROGRESS_UI, edit=True, minValue=self._max_count)

    def get_progress_value(self):
        """
        Returns current progress value of the progress bar

        :return: current progress value
        :rtype: int
        """

        self._log_progress()

        if self._is_batch():
            return self._count

        if self.USE_WINDOW:
            return cmds.progressWindow(query=True, progress=True)
        else:
            if not self.PROGRESS_UI:
                return self._count
            return cmds.progressBar(self.PROGRESS_UI, query=True, progress=True)

    def set_progress_value(self, value, status=None):
        """
        Sets the current progress value of the progress bar

        :param int value: current progress value
        :param str status: text used by progress bar
        """

        self._count = value
        if status is not None:
            self._status = status
        else:
            status = self._status
        self._log_progress()

        if self._is_batch():
            return

        if self.USE_WINDOW:
            cmds.progressWindow(edit=True, progress=self._count, status=status)
        else:
            if not self.PROGRESS_UI:
                return
            cmds.progressBar(self.PROGRESS_UI, edit=True, progress=self._count, status=status)

        cmds.refresh()

    def increment_value(self, increment=1):
        """
        Increments current progress value with the given increment

        :param int increment: Increment step we want to apply to current progress bar value
        """

        self._count += increment
        self._log_progress()

        if self._is_batch():
            return

        if self.USE_WINDOW:
            cmds.progressWindow(edit=True, step=increment)
        else:
            if not self.PROGRESS_UI:
                return
            cmds.progressBar(self.PROGRESS_UI, edit=True, step=increment)

    def get_status(self):
        """
        Returns current status text of the progress bar

        :return: status text of the progress bar
        :rtype: str
        """

        self._log_progress()

        if self._is_batch():
            return self._status

        if self.USE_WINDOW:
            return cmds.progressWindow(query=True, status=True)
        else:
            if not self.PROGRESS_UI:
                return self._status
            return cmds.progressBar(self.PROGRESS_UI, query=True, status=True)

    def set_status(self, status_text):
        """
        Sets current status text of the progress bar

        :param str status_text: text used by progress bar
        """

        self._status = str(status_text)
        self._log_progress()

        if self._is_batch():
            return

        if self.USE_WINDOW:
            cmds.progressWindow(edit=True, status=self._status)
        else:
            if not self.PROGRESS_UI:
                return
            cmds.progressBar(self.PROGRESS_UI, edit=True, status=self._status)

    def start(self, title='', status='', min_count=0, max_count=100):
        """
        Starts progress bar execution
        :param str title: Title of the progress bar (optional)
        :param str status: Initial text used by progress bar (optional)
        :param int min_count: Initial minimum progress bar value (optional)
        :param int max_count: Initial maximum progress bar value (optional)
        """

        self._count = 0
        self._min_count = min_count if min_count is not None else 0
        self._max_count = max_count if max_count is not None else 100
        self._title = title if title is not None else ''
        self._status = status if status is not None else ''

        if self._is_batch():
            self._log_progress()
            return

        if self.PROGRESS_UI or self.USE_WINDOW:
            self.end()

        if self.USE_WINDOW:
            cmds.progressWindow(
                title=self._title, progress=0, status=self._status,
                minValue=self._min_count, maxValue=self._max_count)
        else:
            self.PROGRESS_UI = utils.get_maya_progress_bar()

            self._count = 0
            self._status = status if status is not None else cmds.progressBar(self.PROGRESS_UI, query=True, status=True)
            self._min_count = min_count if min_count is not None else cmds.progressBar(
                self.PROGRESS_UI, query=True, minValue=True)
            self._max_count = max_count if max_count is not None else cmds.progressBar(
                self.PROGRESS_UI, query=True, maxValue=True)

            cmds.progressBar(
                self.PROGRESS_UI, edit=True, beginProgress=True, isInterruptable=self.can_be_interrupted(),
                status=self._status, minValue=self._min_count, maxValue=self._max_count)

    def end(self):
        """
        Ends progress bar execution
        """

        self._count = 0
        self._min_count = 0
        self._max_count = 100
        self._status = ''

        self._log_progress()

        if cmds.about(batch=True):
            return

        if self.USE_WINDOW:
            cmds.progressWindow(edit=True, endProgress=True)
        else:
            if not self.PROGRESS_UI:
                return
            if cmds.progressBar(self.PROGRESS_UI, query=True, isCancelled=True):
                cmds.progressBar(self.PROGRESS_UI, edit=True, beginProgress=True)
            cmds.progressBar(self.PROGRESS_UI, edit=True, endProgress=True)

            self.PROGRESS_UI = None

    def _is_batch(self):
        """
        Internal function that returns whether or not current Maya session is being executed in batch mode
        If that is the case, Maya UI is not available and we cannot use it (only logs)

        :return: True if current Maya session is being executed in batch mode; False otherwise
        :rtype: bool
        """

        return cmds.about(batch=True)

    def _log_progress(self):
        """
        Internal function that logs current progress into DCC output window
        """

        logger.debug('{} - {}'.format(self._status, self._count))
