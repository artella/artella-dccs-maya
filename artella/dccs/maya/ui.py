#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains Maya DCC UI implementation
"""

from __future__ import print_function, division, absolute_import

import maya.cmds as cmds

from artella.core import qtutils
from artella.dccs.maya import utils


def get_main_window():
    """
    Returns Qt object that references to the main DCC window we are working on

    :return: An instance of the current DCC Qt main window
    :rtype: QMainWindow or QWidget or None
    """

    return utils.get_maya_window()


def show_info(title, message):
    """
    Shows a confirmation dialog that users need to accept/reject.
    :param str title: text that is displayed in the title bar of the dialog
    :param str message: text which is shown to the user telling them what operation they need to confirm

    :return: True if the user accepted the operation; False otherwise.
    :rtype: bool
    """

    return qtutils.show_info_message_box(title=title, text=message)


def show_question(title, message, cancel=True):
    """
    Shows a question message box that can be used to show question text to users.

    :param str title: text that is displayed in the title bar of the dialog
    :param str message: text which is shown to the user telling them what operation they need to confirm
    :param bool cancel: Whether or not cancel button should appear in question message box
    :return: True if the user presses the Ok button; False if the user presses the No button; None if the user preses
        the Cancel button
    :rtype: bool or None
    """

    return qtutils.show_question_message_box(title=title, text=message, cancel=cancel)


def show_warning(title, message, print_message=False):
    """
    Shows a warning message box that can be used to show warning text to users.

    :param str title: text that is displayed in the title bar of the dialog
    :param str message: default text which is placed n the plain text edit
    :param bool print_message: whether or not print message in DCC output command window
    """

    if print_message:
        cmds.warning(message)

    qtutils.show_warning_message_box(title=title, text=message)


def show_error(title, message, print_message=False):
    """
    Shows an error message box that can be used to show critical text to users.

    :param str title: text that is displayed in the title bar of the dialog
    :param str message: default text which is placed n the plain text edit
    :param bool print_message: whether or not print message in DCC output command window
    """

    if print_message:
        cmds.error(message)

    qtutils.show_error_message_box(title=title, text=message)


def input_comment(title, label, text=''):
    """
    Shows a comment input dialog that users can use to input text.

    :param str title: text that is displayed in the title bar of the dialog
    :param str label: text which is shown to the user telling them what kind of text they need to input
    :param str text: default text which is placed in the comment section
    :return: Tuple containing as the first element the text typed by the user and as the second argument a boolean
        that will be True if the user clicked on the Ok button or False if the user cancelled the operation
    :rtype: tuple(str, bool)
    """

    return qtutils.show_comment_input_dialog(title=title, label=label, text=text)
