#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains Maya DCC utils functions
"""

from __future__ import print_function, division, absolute_import

import os
import logging

import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMayaUI as OpenMayaUI

from artella.core import qtutils

from artella.externals.Qt import QtWidgets

logger = logging.getLogger('artella')


def force_mel_stack_trace_on():
    """
    Forces enabling Maya Stack Trace
    """

    try:
        mel.eval('stackTrace -state on')
        cmds.optionVar(intValue=('stackTraceIsOn', True))
        what_is = mel.eval('whatIs "$gLastFocusedCommandReporter"')
        if what_is != 'Unknown':
            last_focused_command_reporter = mel.eval('$tmp = $gLastFocusedCommandReporter')
            if last_focused_command_reporter and last_focused_command_reporter != '':
                mel.eval('synchronizeScriptEditorOption 1 $stackTraceMenuItemSuffix')
    except Exception as exc:
        logger.debug(str(exc))


def get_maya_window():
    """
    Returns Qt object wrapping main Maya window object

    :return: window object representing Maya Qt main window
    :rtype: QMainWindow
    """

    maya_window_ptr = OpenMayaUI.MQtUtil.mainWindow()

    return qtutils.wrapinstance(maya_window_ptr, QtWidgets.QMainWindow)


def get_maya_progress_bar():
    """
    Returns Maya internal progress bar object
    :return: Object name of the Maya progress bar
    :rtype: str
    """

    return mel.eval('$tmp = $gMainProgressBar')


def list_references(parent_namespace=None):
    """
    Returns a list of reference nodes found in the current Maya scene

    :param parent_namespace: str or None, parent namespace to query references nodes from
    :return: List of reference nodes in the current Maya scene
    :rtype: list(str)
    """

    ref_nodes = list()
    for ref in cmds.ls(type='reference'):
        if 'sharedReferenceNode' in ref or '_UNKNOWN_REF_NODE_' in ref:
            continue
        if parent_namespace:
            if not ref.startswith(parent_namespace):
                continue
        ref_nodes.append(ref)

    return ref_nodes


def is_reference_node(node_name):
    """
    Returns whether or not given node is a reference one or not

    :param str node_name: name of a node of name of a node attribute
    :return: True if the node is a reference one; False otherwise.
    :rtype: bool
    """

    return node_name in list_references()


def is_referenced_node(node_name):
    """
    Returns whether the given node is referenced from an external file or not

    :param str node_name: name of the node we want to check
    :return: True if the given node is referenced from an external file; False otherwise.
    :rtype: bool
    """

    return cmds.referenceQuery(node_name, isNodeReferenced=True)


def is_reference_loaded(reference_node):
    """
    Returns whether or not current node is referenced or not

    :param str reference_node: str, reference node
    :return: True if the given node is referenced; False otherwise.
    :rtype: bool
    """

    if not is_reference_node(reference_node):
        return False

    return cmds.referenceQuery(reference_node, isLoaded=True)


def get_reference_file(reference_node, without_copy_number=True, unresolved_name=False):
    """
    Returns the reference file associated with the given referenced object or reference node

    :param str reference_node: str, reference node to query
    :param bool without_copy_number: Flag that indicates that the file name returned will have or not a copy
        number (e.g. '{1}') appended to the end.
    :param bool unresolved_name: Flag that indicates if the reference file path should be returned with environment
        variables unresolved or not.
    :return: File path given node belongs to
    :rtype: str
    """

    if not is_reference_node(reference_node) and not is_referenced_node(reference_node):
        logger.warning(
            'Node "{}" is not a valid reference node or a node from a reference file!'.format(reference_node))
        return ''

    ref_file = cmds.referenceQuery(
        reference_node, filename=True, wcn=without_copy_number, unresolvedName=unresolved_name)

    return ref_file


def get_reference_files(without_copy_number=True, unresolved_name=False):
    """
    Returns a list with all file paths of the reference nodes in current scene

    :param bool without_copy_number: Flag that indicates that the file name returned will have or not a copy
        number (e.g. '{1}') appended to the end.
    :param bool unresolved_name: Flag that indicates if the reference file path should be returned with environment
    variables unresolved or not.
    :return: List of referenced nodes file paths
    :rtype: list(str)
    """

    all_refs = list_references()
    all_ref_files = [get_reference_file(
        ref, without_copy_number=without_copy_number, unresolved_name=unresolved_name) for ref in all_refs]

    return all_ref_files


def replace_reference(reference_node, reference_file_path):
    """
    Replaces the reference file path for a given reference node

    :param reference_node: str, reference node to replace file path for
    :param reference_file_path: str, new reference file path
    :return: True if the replace operation is completed successfully; False otherwise.
    :rtype: bool
    """

    if not is_reference_node(reference_node):
        return False

    if get_reference_file(reference_node, without_copy_number=True) == reference_file_path:
        logger.warning('Reference "{}" already referencing "{}"!'.format(reference_node, reference_file_path))
        return False

    if reference_file_path.endswith('.ma'):
        ref_type = 'mayaAscii'
    elif reference_file_path.endswith('.mb'):
        ref_type = 'mayaBinary'
    else:
        logger.warning('Invalid file type for reference file path: "{}"'.format(reference_file_path))
        return False

    cmds.file(reference_file_path, loadReference=reference_node, typ=ref_type, options='v=0')

    logger.debug('Replaced reference "{}" using file: "{}"'.format(reference_node, reference_file_path))

    return reference_file_path


def unload_reference(reference_node):
    """
    Unloads the reference associated with the given reference node

    :param reference_node: str, reference node to unload
    """

    if not is_reference_node(reference_node):
        return False

    is_loaded = cmds.file(referenceNode=reference_node, unloadReference=True)

    # logger.debug('Unloaded reference "{}"! ("{}")'.format(reference_node, get_reference_file(reference_node)))

    return is_loaded


def load_reference(file_path, reference_name):
    """
    Loads a new reference with given name pointing to given path
    :param str file_path:
    :param str reference_name:
    :return:
    """

    is_loaded = cmds.file(file_path, loadReference=reference_name)

    logger.debug('Loaded reference "{}"! ("{}")'.format(reference_name, file_path))

    return is_loaded


def reload_reference(reference_node):
    """
    Reloads the reference associated with the given reference node

    :param str reference_node:
    """

    if not is_reference_node(reference_node):
        return False

    is_loaded = cmds.file(referenceNode=reference_node, loadReference=True)

    logger.debug('Reloaded reference "{}"! ("{}")'.format(reference_node, get_reference_file(reference_node)))

    return is_loaded


def reload_textures(files_to_check=None):
    """
    Reloads all the textures of the current Maya scene
    """

    if not files_to_check:
        reload_all_textures()
    else:
        files_to_check = [os.path.normpath(texture_to_check) for texture_to_check in files_to_check]
        textures_to_update = list()

        try:
            cmds.waitCursor(state=True)
            texture_files = cmds.ls(type="file")
            for texture in texture_files:
                texture_file_path = cmds.getAttr(texture + ".fileTextureName")
                if not texture_file_path:
                    continue
                if os.path.normpath(texture_file_path) not in files_to_check:
                    continue
                textures_to_update.append(texture)
            for texture in textures_to_update:
                texture_file_path = cmds.getAttr(texture + ".fileTextureName")
                cmds.setAttr(texture + ".fileTextureName", texture_file_path, type="string")
        except Exception as exc:
            logger.warning('Error while reloading textures: {}'.format(exc))
        finally:
            cmds.waitCursor(state=False)


def reload_all_textures():
    """
    Reloads all the textures of the current Maya scene
    """

    try:
        cmds.waitCursor(state=True)
        texture_files = cmds.ls(type="file")
        for texture in texture_files:
            texture_file_path = cmds.getAttr(texture + ".fileTextureName")
            cmds.setAttr(texture + ".fileTextureName", texture_file_path, type="string")
    except Exception as exc:
        logger.warning('Error while reloading textures: {}'.format(exc))
    finally:
        cmds.waitCursor(state=False)


def reload_dependencies(files_to_check=None):
    """
    Reloads all the references nodes of the current Maya scene
    """

    if not files_to_check:
        reload_all_dependencies()
    else:
        reference_nodes_to_reload = list()
        files_to_check = [os.path.normpath(texture_to_check) for texture_to_check in files_to_check]
        all_reference_nodes = list_references() or list()
        for reference_node in all_reference_nodes:
            reference_file_path = get_reference_file(reference_node)
            if not reference_file_path:
                continue
            if not os.path.normpath(reference_file_path) in files_to_check:
                continue
            reference_nodes_to_reload.append(reference_node)
        for ref_node in reference_nodes_to_reload:
            try:
                cmds.file(referenceNode=ref_node, loadReference=True)
            except RuntimeError:
                logger.warning('Impossible to reload reference: {}'.format(ref_node))


def reload_all_dependencies():
    """
    Reloads all the references nodes of the current Maya scene
    """

    ref_nodes = cmds.ls(type='reference')
    if not ref_nodes:
        return

    for ref_node in ref_nodes:
        try:
            cmds.file(referenceNode=ref_node, loadReference=True)
        except RuntimeError:
            logger.warning('Impossible to reload reference: {}'.format(ref_node))


class TrackNodes(object):
    """
    Helps track new nodes that get added to a scene after a function is called

    track_nodes = TrackNodes()
    track_nodes.load()
    fn()
    new_nodes = track_nodes.get_delta()
    """

    def __init__(self, full_path=False):
        self._nodes = None
        self._node_type = None
        self._delta = None
        self._full_path = full_path

    def load(self, node_type=None):
        """
        Initializes TrackNodes states

        :param str node_type: Maya node type we want to track. If not given, all current scene objects wil lbe tracked
        """

        self._node_type = node_type
        if self._node_type:
            self._nodes = cmds.ls(type=node_type, long=self._full_path)
        else:
            self._nodes = cmds.ls()

    def get_delta(self):
        """
        Returns the new nodes in the Maya scene created after load() was executed

        :return: List with all new nodes available in current DCC scene
        :rtype: list(str)
        """

        if self._node_type:
            current_nodes = cmds.ls(type=self._node_type, long=self._full_path)
        else:
            current_nodes = cmds.ls(long=self._full_path)

        new_set = set(current_nodes).difference(self._nodes)

        return list(new_set)
