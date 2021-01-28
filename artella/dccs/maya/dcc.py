#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains Maya DCC application implementation
"""

from __future__ import print_function, division, absolute_import

import os
import string
import logging
import platform
import traceback

import maya.cmds as cmds
import maya.mel as mel
import maya.utils as utils

from artella.core import qtutils
from artella.dccs.maya import utils as maya_utils

logger = logging.getLogger('artella')


def name():
    """
    Returns name of current DCC

    :return: Returns name of DCC without any info about version
    :rtype: str
    """

    return 'maya'


def nice_name():
    """
    Returns nice name of current DCC

    :return: Returns formatted DCC name
    :rtype: str
    """

    return 'Maya'


def version():
    """
    Returns version of DCC application

    :return: Returns integer number indicating the version of the DCC application
    :rtype: int
    """

    return int(cmds.about(version=True))


def extensions():
    """
    Returns a list of available extension for DCC application

    :return: List of available extensions with the following format: .{EXTENSION}
    :rtype: list(str)
    """

    return ['.ma', '.mb']


def scene_name():
    """
    Returns the name of the current scene

    :return: Full file path name of the current scene. If no file is opened, None is returned.
    :rtype: str or None
    """

    return cmds.file(query=True, sceneName=True)


def new_scene(force=True, **kwargs):
    """
    Creates a new scene inside DCC
    :param force: True to skip saving of the current opened DCC scene; False otherwise.
    :return: True if the new scene is created successfully; False otherwise.
    :rtype: bool
    """

    if not force:
        save_scene()

    cmds.file(new=True, force=force)
    cmds.flushIdleQueue()

    return True


def scene_is_modified():
    """
    Returns whether or not current opened DCC file has been modified by the user or not

    :return: True if current DCC file has been modified by the user; False otherwise
    :rtype: bool
    """

    return cmds.file(query=True, modified=True)


def open_scene(file_path, save=True):
    """
    Opens DCC scene file
    :param str file_path: Absolute local file path we want to open in current DCC
    :param bool save: Whether or not save current opened DCC scene file
    :return: True if the save operation was successful; False otherwise
    :rtype: bool
    """

    if save:
        save_scene()

    file_path = cmds.encodeString(file_path)
    cmds.file(file_path, open=True, force=not save)
    file_path = file_path.replace('\\', '/')

    scene_ext = os.path.splitext(file_path)[-1]
    scene_type = None
    if scene_ext == '.ma':
        scene_type = 'mayaAscii'
    elif scene_ext == '.mb':
        scene_type = 'mayaBinary'
    if scene_type:
        mel.eval('$filepath = "{}";'.format(file_path))
        mel.eval('addRecentFile $filepath "{}";'.format(scene_type))

    return True


def save_scene(force=True, **kwargs):
    """
    Saves DCC scene file

    :param bool force: Whether to force the saving operation or not
    :return:
    """

    file_extension = kwargs.get('extension_to_save', extensions()[0])
    current_scene_name = scene_name()
    if current_scene_name:
        file_extension = os.path.splitext(current_scene_name)[-1]
    if not file_extension.startswith('.'):
        file_extension = '.{}'.format(file_extension)
    maya_scene_type = 'mayaAscii' if file_extension == '.ma' else 'mayaBinary'

    if force:
        cmds.SaveScene()
        return True
    else:
        if scene_is_modified():
            cmds.SaveScene()
            return True
        else:
            cmds.file(save=True, type=maya_scene_type)
            return True


def import_scene(file_path):
    """
    Opens scene file into current opened DCC scene file
    :param str file_path: Absolute local file path we want to import into current DCC
    :return: True if the import operation was successful; False otherwise
    :rtype: bool
    """

    file_path = cmds.encodeString(file_path)
    cmds.file(file_path, i=True, force=True, ignoreVersion=True, preserveReferences=True)

    return True


def reference_scene(file_path, **kwargs):
    """
    References scene file into current opened DCC scene file
    :param str file_path: Absolute local file path we want to reference into current DCC
    :return: True if the reference operation was successful; False otherwise
    :rtype: bool
    """

    namespace = kwargs.get('namespace', None)

    file_path = cmds.encodeString(file_path)

    track_nodes = maya_utils.TrackNodes(full_path=True)
    track_nodes.load()

    try:
        # If not namespace is given we generate one taking into account given file name
        if not namespace:
            use_rename = cmds.optionVar(query='referenceOptionsUseRenamePrefix')
            if use_rename:
                namespace = cmds.optionVar(q='referenceOptionsRenamePrefix')
                rsp = cmds.file(file_path, reference=True, mergeNamespacesOnClash=False, namespace=namespace)
                logger.debug(
                    '{} = file({}, reference=True, mergeNamespacesOnClash=False, namespace={})'.format(
                        rsp, file_path, namespace))
            else:
                namespace = os.path.basename(file_path)
                split_name = namespace.split('.')
                if split_name:
                    namespace = string.join(split_name[:-1], '_')
                rsp = cmds.file(file_path, reference=True, mergeNamespacesOnClash=False, namespace=namespace)
                logger.debug(
                    '{} = file({}, reference=True, mergeNamespacesOnClash=False, namespace={})'.format(
                        rsp, file_path, namespace))
    except Exception as exc:
        logger.exception(
            'Exception raised when referencing file "{}" | {} | {}'.format(file_path, exc, traceback.format_exc()))
        return False

    new_nodes = track_nodes.get_delta()
    logger.info('Maya reference event referenced {} nodes'.format(len(new_nodes)))

    return True


def supports_uri_scheme():
    """
    Returns whether or not current DCC support URI scheme implementation

    :return: True if current DCC supports URI scheme implementation; False otherwise
    """

    return True


def pass_message_to_main_thread_fn():
    """
    Returns function used by DCC to execute a function in DCC main thread in the next idle event of that thread.

    :return If DCC API supports it, returns function to call a function in main thread from other thread
    """

    return utils.executeInMainThreadWithResult


def eval_deferred(fn):
    """
    Evaluates given function in deferred mode

    :param fn: function
    """

    return cmds.evalDeferred(fn)


def is_batch():
    """
    Returns whether or not current DCC is being executed in batch mode (no UI)
    :return: True if current DCC session is being executed in batch mode; False otherwise.
    :rtype: bool
    """

    return cmds.about(batch=True)


def clean_path(file_path):
    """
    Cleans given path so it can be properly used by current DCC

    :param str file_path: file path we want to clean
    :return: Cleaned version of the given file path
    :rtype: str
    """

    return cmds.encodeString(file_path)


def get_installation_paths(versions=None):
    """
    Returns installation path of the given versions of current DCC

    :param list(int) versions: list of versions to find installation paths of. If not given, current DCC version
        installation path will be returned
    :return: Dictionary mapping given versions with installation paths
    :rtype: dict(str, str)
    """

    if versions is None:
        versions = [version()]

    installation_paths = dict()

    if platform.system().lower() =='windows':
        try:
            for maya_version in versions:
                from _winreg import HKEY_LOCAL_MACHINE, ConnectRegistry, OpenKey, QueryValueEx
                a_reg = ConnectRegistry(None, HKEY_LOCAL_MACHINE)
                a_key = OpenKey(a_reg, r"SOFTWARE\Autodesk\Maya\{}\Setup\InstallPath".format(maya_version))
                value = QueryValueEx(a_key, 'MAYA_INSTALL_LOCATION')
                maya_location = value[0]
                installation_paths['{}'.format(maya_version)] = maya_location
        except Exception:
            for maya_version in versions:
                path = 'C:/Program Files/Autodesk/Maya{}'.format(maya_version)
                if os.path.exists(path):
                    maya_location = path
                    installation_paths['{}'.format(maya_version)] = maya_location

    return installation_paths


def is_udim_path(file_path):
    """
    Returns whether or not given file path is an UDIM one

    :param str file_path: File path we want to check
    :return: True if the given paths is an UDIM path; False otherwise.
    :rtype: bool
    """

    return '<UDIM>' in file_path


def execute_deferred(fn):
    """
    Executes given function in deferred mode (once DCC UI has been loaded)
    :param callable fn: Function to execute in deferred mode
    :return:
    """

    utils.executeDeferred(fn)


def register_dcc_resource_path(resources_path):
    """
    Registers path into given DCC so it can find specific resources
    :param resources_path: str, path we want DCC to register
    """

    if not os.path.isdir(resources_path):
        return

    if not os.environ.get('XBMLANGPATH', None):
        os.environ['XBMLANGPATH'] = resources_path
    else:
        paths = os.environ['XBMLANGPATH'].split(os.pathsep)
        if resources_path not in paths and os.path.normpath(resources_path) not in paths:
            os.environ['XBMLANGPATH'] = os.environ['XBMLANGPATH'] + os.pathsep + resources_path


def main_menu_toolbar():
    """
    Returns Main menu toolbar where DCC menus are created by default
    :return: Native object that represents main menu toolbar in current DCC
    :rtype: object
    """

    return mel.eval('$tmp=$gMainWindow')


def get_menus():
    """
    Return all the available menus in current DCC. This function returns specific DCC objects that represents DCC
    UI menus.

    :return: List of all menus names in current DCC
    :rtype: list(object)
    """

    return cmds.lsUI(menus=True)


def get_menu_items():
    """
    Returns all available menu items in current DCC. This function returns specific DCC objects that represents DCC
    UI menu items.

    :return: List of all menu item names in current DCC
    :rtype: list(str)
    """

    return cmds.lsUI(menuItems=True)


def get_menu(menu_name):
    """
    Returns native DCC menu with given name
    :param str menu_name: name of the menu to search for
    :return: Native DCC menu object or None if the menu does not exists
    :rtype: str or None
    """

    for menu in get_menus():
        menu_label = cmds.menu(menu, query=True, label=True)
        if menu_label == menu_name or menu == menu_name:
            return menu

    return None


def get_menu_item(menu_item_name):
    """
    Returns native DCC menu item with given name
    :param str menu_item_name: name of the menu item to search for
    :return: Native DCC menu object or None if the menu does not exists
    :rtype: str or None
    """

    for menu_item in get_menu_items():
        menu_item_label = cmds.menuItem(menu_item, query=True, label=True)
        if menu_item_label == menu_item_name or menu_item == menu_item_name:
            return menu_item

    return None


def check_menu_exists(menu_name):
    """
    Returns whether or not menu with given name exists

    :param str menu_name: name of the menu to search for
    :return: True if the menu already exists; False otherwise
    :rtype: bool
    """

    for menu in get_menus():
        menu_label = cmds.menu(menu, query=True, label=True)
        if menu_label == menu_name or menu_name == menu:
            return True

    return False


def add_menu(menu_name, parent_menu=None, tear_off=True, icon='', **kwargs):
    """
    Creates a new DCC menu.

    :param str menu_name: name of the menu to create
    :param object parent_menu: parent menu to attach this menu into. If not given, menu will be added to
    specific DCC main menu toolbar. Must be specific menu DCC native object
    :param bool tear_off: whether or not new created menu can be teared off
    :param str icon: name of the icon to be used in this menu
    :return: True if the menu was created successfully; False otherwise
    :rtype: bool
    """

    if not parent_menu:
        parent_menu = main_menu_toolbar()

    if check_menu_exists(menu_name):
        logger.warning('Menu "{}" already exists. Skipping creation.'.format(menu_name))
        return None

    native_menu_name = '{}Menu'.format(menu_name.replace(' ', ''))
    try:
        native_menu = cmds.menu(
            native_menu_name, parent=parent_menu, tearOff=tear_off, label=menu_name, familyImage=icon)
    except RuntimeError:
        native_parent_menu = get_menu(parent_menu)
        native_menu = cmds.menu(
            native_menu_name, parent=native_parent_menu, tearOff=tear_off, label=menu_name, familyImage=icon)
    if not native_menu:
        logger.warning('Impossible to create native Maya menu "{}"'.format(menu_name))
        return None

    return native_menu


def remove_menu(menu_name):
    """
    Removes menu from current DCC if exists

    :param str menu_name: name of the menu to remove
    :return: True if the removal was successful; False otherwise
    :rtype: bool
    """

    for menu in get_menus():
        menu_label = cmds.menu(menu, query=True, label=True)
        if menu_label == menu_name:
            cmds.deleteUI(menu, menu=True)
            return True

    return False


def add_menu_item(menu_item_name, menu_item_command='', parent_menu=None, icon='', **kwargs):
    """
    Adds a new menu item to the given parent menu. When the item is clicked by the user the given command will be+
    executed
    :param str menu_item_name: name of the menu item to create
    :param str menu_item_command: command to execute when menu item is clicked
    :param object parent_menu: parent menu to attach this menu into. Must be specific menu DCC native object
    :param str icon: name of the icon to be used in this menu item
    :return: New DCC native menu item created or None if the menu item was not created successfully
    :rtype: object or None
    """

    native_menu_item = '{}MenuItem'.format(menu_item_name.replace(' ', ''))

    try:
        menu_item = cmds.menuItem(
            native_menu_item, parent=parent_menu, label=menu_item_name, command=menu_item_command, image=icon, **kwargs)
    except RuntimeError:
        try:
            native_parent_menu = get_menu(parent_menu)
            menu_item = cmds.menuItem(
                native_menu_item, parent=native_parent_menu, label=menu_item_name, image=icon,
                command=menu_item_command, **kwargs)
        except RuntimeError:
            native_parent_item = get_menu_item(parent_menu)
            menu_item = cmds.menuItem(
                native_menu_item, parent=native_parent_item, label=menu_item_name, image=icon,
                command=menu_item_command, **kwargs)

    return menu_item


def add_sub_menu_item(menu_item_name, menu_item_command='', icon='', parent_menu=None, **kwargs):
    """
    Adds a new sub menu item to the given parent menu. When the item is clicked by the user the given command will be+
    executed
    :param str menu_item_name: name of the menu item to create
    :param str menu_item_command: command to execute when menu item is clicked
    :param object parent_menu: parent menu to attach this menu into. Must be specific menu DCC native object
    :param str icon: name of the icon to be used in this menu item
    :return: New DCC native menu item object created or None if the menu item was not created successfully
    :rtype: object or None
    """

    return add_menu_item(menu_item_name, menu_item_command, parent_menu, icon=icon, subMenu=True)


def remove_menu_item(menu_item_name, parent_menu):
    """
    Removes a menu item from the given parent menu.
    :param str menu_item_name: name of the menu item to remove
    :param str parent_menu: parent menu to remove this menu from. Must be specific menu DCC native object
    :return: Try if the operation was successful; False otherwise.
    :rtype: bool
    """

    menu = get_menu(parent_menu)
    if not menu:
        return False

    menu_items = cmds.menu(menu, itemArray=True, query=True)
    if not menu_items:
        return False

    for item in menu_items:
        item_name = cmds.menuItem(item, label=True, query=True)
        if item_name == menu_item_name or item == menu_item_name:
            cmds.deleteUI(item, menuItem=True)
            return True

    return False


def add_menu_separator(parent_menu):
    """
    Adds a new separator to the given parent menu
    :param object parent_menu: parent menu to attach this menu into. Must be specific menu DCC native object
    """

    try:
        new_separator = cmds.menuItem(divider=True, parent=parent_menu)
    except RuntimeError:
        native_parent_menu = get_menu(parent_menu)
        new_separator = cmds.menuItem(divider=True, parent=native_parent_menu)

    return new_separator


def get_main_window():
    """
    Returns Qt object that references to the main DCC window we are working on

    :return: An instance of the current DCC Qt main window
    :rtype: QMainWindow or QWidget or None
    """

    return maya_utils.get_maya_window()


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
