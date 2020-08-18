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

from artella.dccs.maya import utils as maya_utils

logger = logging.getLogger('artella')


def name():
    """
    Returns name of current DCC

    :return: Returns name of DCC without any info about version
    :rtype: str
    """

    return 'maya'


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


def new_scene(force=True):
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
