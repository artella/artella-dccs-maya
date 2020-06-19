#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains Maya DCC utils functions
"""

from __future__ import print_function, division, absolute_import

import os
import struct
import logging
from collections import namedtuple
from contextlib import contextmanager

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


def get_reference_file(reference_node, without_copy_number=True):
    """
    Returns the reference file associated with the given referenced object or reference node

    :param str reference_node: str, reference node to query
    :param bool without_copy_number: Flag that indicates that the file name returned will have or not a copy
        number (e.g. '{1}') appended to the end.
    :return: File path given node belongs to
    :rtype: str
    """

    if not is_reference_node(reference_node) and not is_referenced_node(reference_node):
        logger.warning(
            'Node "{}" is not a valid reference node or a node from a reference file!'.format(reference_node))
        return ''

    ref_file = cmds.referenceQuery(reference_node, filename=True, wcn=without_copy_number)

    return ref_file


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


def reload_textures():
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


def reload_dependencies():
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


def be_word4(buf):
    return struct.unpack(">L", buf)[0]


def le_word4(buf):
    return struct.unpack("<L", buf)[0]


def be_word8(buf):
    return struct.unpack(">Q", buf)[0]


def le_word8(buf):
    return struct.unpack("<Q", buf)[0]


def be_read4(stream):
    return struct.unpack(">L", stream.read(4))[0]


def le_read4(stream):
    return struct.unpack("<L", stream.read(4))[0]


def be_read8(stream):
    return struct.unpack(">Q", stream.read(8))[0]


def le_read8(stream):
    return struct.unpack("<Q", stream.read(8))[0]


def align(size, stride):
    return stride * int(1 + ((size - 1) / stride))


def read_null_terminated(stream):
    result = ""
    next_byte = stream.read(1)
    while stream and next_byte != '\0':
        result += next_byte
        next_byte = stream.read(1)

    return result


def plug_element_count(plug):
    lbracket = plug.rfind("[")
    if lbracket != -1:
        rbracket = plug.rfind("]")
        if rbracket != -1 and lbracket < rbracket:
            slice_str = plug[lbracket + 1:rbracket]
            bounds = slice_str.split(":")
            if len(bounds) > 1:
                return int(bounds[1]) - int(bounds[0]) + 1

    return 1


class IffChunks(object):

    # IFF chunk type IDs
    FOR4 = be_word4("FOR4")
    LIS4 = be_word4("LIS4")
    # 64 bits
    FOR8 = be_word4("FOR8")
    LIS8 = be_word4("LIS8")

    # General
    MAYA = be_word4("Maya")

    # File referencing
    FREF = be_word4("FREF")
    FRDI = be_word4("FRDI")

    # Header fields
    HEAD = be_word4("HEAD")
    VERS = be_word4("VERS")
    PLUG = be_word4("PLUG")
    FINF = be_word4("FINF")
    AUNI = be_word4("AUNI")
    LUNI = be_word4("LUNI")
    TUNI = be_word4("TUNI")

    # Node creation
    CREA = be_word4("CREA")
    SLCT = be_word4("SLCT")
    ATTR = be_word4("ATTR")

    CONS = be_word4("CONS")
    CONN = be_word4("CONN")

    # Data types
    FLGS = be_word4("FLGS")
    DBLE = be_word4("DBLE")
    DBL3 = be_word4("DBL3")
    STR_ = be_word4("STR ")
    FLT2 = be_word4("FLT2")
    CMPD = be_word4("CMPD")
    MESH = be_word4("MESH")


class IffParser(object):
    """
    Class that handles the parsing of Iff files
    https://en.wikipedia.org/wiki/Interchange_File_Format
    https://github.com/mottosso/maya-scenefile-parser/blob/master/maya_scenefile_parser/iff.py
    """

    IFF_NATIVE_ENDIAN = 0
    IFF_BIG_ENDIAN = 1
    IFF_LITTLE_ENDIAN = 2

    ENDIAN_FORMATS = {
        IFF_NATIVE_ENDIAN: '=',
        IFF_BIG_ENDIAN: '>',
        IFF_LITTLE_ENDIAN: '<'
    }

    BYTE_FORMATS = {
        1: 'B',
        2: 'H',
        4: 'L',
        8: 'Q'
    }

    IffFormat = namedtuple('IffFormat',
                           ['endianness', 'typeid_bytes', 'size_bytes', 'header_alignment', 'chunk_alignment'])
    IffChunk = namedtuple('IffChunk', ['typeid', 'data_offset', 'data_length'])

    def __init__(self, stream, iff_format):
        self._stream = stream
        self._format = iff_format
        self._current_chunk = None
        self._current_chunk_end = None
        self._chunk_handlers = dict()
        self._header_struct = self._get_header_struct(iff_format)

    # ==============================================================================================================
    # PROPERTIES
    # ==============================================================================================================

    @property
    def stream(self):
        return self._stream

    @property
    def chunk(self):
        return self._current_chunk

    # ==============================================================================================================
    # PARSE
    # ==============================================================================================================

    def parse(self):
        self.reset()
        self._handle_all_chunks()

    def realign(self):
        chunk = self._current_chunk
        base_offset = self._get_offset()
        base_delta = chunk.data_offset + chunk.data_length - base_offset
        self._current_chunk_end = base_offset + align(base_delta, self._format.chunk_alignment)

    def reset(self):
        self._current_chunk = None
        self._current_chunk_end = None
        self._stream.seek(0)

    # ==============================================================================================================
    # INTERNAL
    # ==============================================================================================================

    def _get_header_struct(self, iff_format):
        if iff_format.endianness not in self.ENDIAN_FORMATS:
            logger.error('Iff: Invalid endianess.')
            return False
        if iff_format.typeid_bytes not in self.BYTE_FORMATS:
            logger.error('Iff: Invalid typeid format.')
            return False
        if iff_format.size_bytes not in self.BYTE_FORMATS:
            logger.error('Iff: Invalid size format.')
            return False

        typeid_padding = 'x' * max(0, iff_format.header_alignment - iff_format.typeid_bytes)
        size_padding = 'x' * max(0, iff_format.header_alignment - iff_format.size_bytes)

        fmt = (self.ENDIAN_FORMATS[iff_format.endianness] +
               self.BYTE_FORMATS[iff_format.typeid_bytes] + typeid_padding +
               self.BYTE_FORMATS[iff_format.size_bytes] + size_padding)

        return struct.Struct(fmt)

    def on_iff_chunk(self, chunk):
        pass

    def _realign(self):
        chunk = self._current_chunk
        base_offset = self._get_offset()
        base_delta = chunk.data_offset + chunk.data_length - base_offset
        self._current_chunk_end = base_offset + align(base_delta, self._format.chunk_alignment)

    def _get_chunk_handler(self, typeid):
        return self._chunk_handlers.get(typeid, self.on_iff_chunk)

    def _handle_all_chunks(self, types=None, alignment=None):
        for chunk in self._iter_chunks(types=types):
            self._get_chunk_handler(chunk.typeid)(chunk)

    def _get_offset(self):
        return self._stream.tell()

    def _set_offset(self, offset):
        self._stream.seek(offset)

    def _is_past_the_end(self):
        if self._current_chunk_end:
            return self._get_offset() >= self._current_chunk_end
        else:
            return not self._stream

    def _read_next_chunk_header(self):
        buf = self._stream.read(self._header_struct.size)
        if len(buf) == self._header_struct.size:
            return self._header_struct.unpack(buf)
        else:
            return None

    def _read_next_chunk(self):
        if self._is_past_the_end():
            return None

        header = self._read_next_chunk_header()
        if not header:
            return None

        typeid, data_length = header
        data_offset = self._get_offset()
        return self.IffChunk(typeid=typeid, data_offset=data_offset, data_length=data_length)

    def _read_chunk_data(self, chunk=None):
        chunk = chunk or self._current_chunk
        if chunk:
            self._stream.seek(chunk.data_offset)
            return self._stream.read(chunk.data_length)
        else:
            return ""

    @contextmanager
    def _using_chunk(self, chunk, alignment=None):
        data_end = chunk.data_offset + chunk.data_length
        chunk_end = chunk.data_offset + align(chunk.data_length, self._format.chunk_alignment)
        try:
            old_chunk = self._current_chunk
            old_chunk_end = self._current_chunk_end
            self._current_chunk = chunk
            self._current_chunk_end = chunk_end
            self._set_offset(chunk.data_offset)
            yield chunk
        finally:
            chunk_end = self._current_chunk_end
            self._current_chunk = old_chunk
            self._current_chunk_end = old_chunk_end
            self._set_offset(chunk_end)

    def _iter_chunks(self, types=None):
        chunk = self._read_next_chunk()
        while chunk:
            with self._using_chunk(chunk):
                if types is None or chunk.typeid in types:
                    yield chunk
            chunk = self._read_next_chunk()


class MayaIffParser(IffParser, object):
    def __init__(self, stream, iff_format, maya64):
        super(MayaIffParser, self).__init__(stream, iff_format)

        self._maya64 = maya64
        node_chunk_type = IffChunks.FOR8 if self._maya64 else IffChunks.FOR4
        list_chunk_type = IffChunks.LIS8 if self._maya64 else IffChunks.LIS4

        self._node_chunk_type = node_chunk_type
        self._list_chunk_type = list_chunk_type

        self._version = None
        self._required_plugins = list()
        self._file_infos = list()
        self._angle_unit = None
        self._linear_unit = None
        self._time_unit = None
        self._nodes = list()
        self._references = list()
        self._connections = list()
        self._attributes = list()

        self._mtypeid_to_typename = dict()
        self._load_mtypeid_database(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'typeids.dat'))

    # ==============================================================================================================
    # PROPERTIES
    # ==============================================================================================================

    @property
    def version(self):
        return self._version

    @property
    def required_plugins(self):
        return self._required_plugins

    @property
    def file_infos(self):
        return self._file_infos

    @property
    def angle_unit(self):
        return self._angle_unit

    @property
    def linear_unit(self):
        return self._linear_unit

    @property
    def time_unit(self):
        return self._time_unit

    @property
    def references(self):
        return self._references

    @property
    def connections(self):
        return self._connections

    @property
    def nodes(self):
        return self._nodes

    @property
    def attributes(self):
        return self._attributes

    # ==============================================================================================================
    # OVERRIDES
    # ==============================================================================================================

    def on_iff_chunk(self, chunk):
        if chunk.typeid == self._node_chunk_type:
            mtypeid = self._read_mtypeid()
            if mtypeid == IffChunks.MAYA:
                self._handle_all_chunks()
            elif mtypeid == IffChunks.HEAD:
                self._parse_maya_header()
            elif mtypeid == IffChunks.FREF:
                self._parse_file_reference()
            elif mtypeid == IffChunks.CONN:
                self._parse_connection()
            else:
                self._parse_node(mtypeid)
        elif chunk.typeid == self._list_chunk_type:
            mtypeid = self._read_mtypeid()
            if mtypeid == IffChunks.CONS:
                self._handle_all_chunks()

    # ==============================================================================================================
    # INTERNAL
    # ==============================================================================================================

    def _load_mtypeid_database(self, path):
        with open(path) as f:
            line = f.readline()
            while line:
                mtypeid = be_word4(line[:4])
                typename = line[5:].rstrip()
                self._mtypeid_to_typename[mtypeid] = typename
                line = f.readline()

    def _read_mtypeid(self):
        # 64-bit format still uses 32-bit MTypeIds
        result = be_read4(self._stream)
        self._realign()

        return result

    def _parse_maya_header(self):
        angle_unit = None
        linear_unit = None
        time_unit = None

        for chunk in self._iter_chunks():
            # requires (maya)
            if chunk.typeid == IffChunks.VERS:
                self._version = self._read_chunk_data(chunk)

            # requires (plugin)
            elif chunk.typeid == IffChunks.PLUG:
                plugin = read_null_terminated(self._stream)
                version = read_null_terminated(self._stream)
                self._required_plugins.append((plugin, version))

            # fileInfo
            elif chunk.typeid == IffChunks.FINF:
                key = read_null_terminated(self.stream)
                value = read_null_terminated(self.stream)
                self._file_infos.append((key, value))

            # currentUnit (angle)
            elif chunk.typeid == IffChunks.AUNI:
                angle_unit = self._read_chunk_data(chunk)
            # currentUnit (linear)
            elif chunk.typeid == IffChunks.LUNI:
                linear_unit = self._read_chunk_data(chunk)
            # currentUnit (time)
            elif chunk.typeid == IffChunks.TUNI:
                time_unit = self._read_chunk_data(chunk)

            # Got all three units
            if angle_unit and linear_unit and time_unit:
                self._angle_unit = angle_unit
                self._linear_unit = linear_unit
                self._time_unit = time_unit

                angle_unit = None
                linear_unit = None
                time_unit = None

        # Didn't get all three units (this is non standard)
        if angle_unit or linear_unit or time_unit:
            logger.warning('Not all three units (angle, linear, time) were retrieved. Non-standard behaviour!')

    def _parse_file_reference(self):
        for chunk in self._iter_chunks(types=[IffChunks.FREF]):
            self._references.append(read_null_terminated(self._stream))

    def _parse_connection(self):
        self.stream.read(17 if self._maya64 else 9)
        src = read_null_terminated(self._stream)
        dst = read_null_terminated(self._stream)
        self._connections.append((src, dst))

    def _parse_node(self, mtypeid):
        for chunk in self._iter_chunks():
            # Create node
            if chunk.typeid == IffChunks.CREA:
                typename = self._mtypeid_to_typename.get(mtypeid, "unknown")
                name_parts = self._read_chunk_data(chunk)[1:-1].split("\0")
                name = name_parts[0]
                parent_name = name_parts[1] if len(name_parts) > 1 else None
                self._nodes.append((typename, name, parent_name))

            # Select the current node
            elif chunk.typeid == IffChunks.SLCT:
                pass

            # Dynamic attribute
            elif chunk.typeid == IffChunks.ATTR:
                pass

            # Flags
            elif chunk.typeid == IffChunks.FLGS:
                pass

            # Set attribute
            else:
                self._parse_attribute(chunk.typeid)

    def _parse_attribute(self, mtypeid):
        # TODO Support more primitive types
        if mtypeid == IffChunks.STR_:
            self._parse_string_attribute()
        elif mtypeid == IffChunks.DBLE:
            self._parse_double_attribute()
        elif mtypeid == IffChunks.DBL3:
            self._parse_double3_attribute()
        else:
            self._parse_mpxdata_attribute(mtypeid)

    def _parse_attribute_info(self):
        attr_name = read_null_terminated(self.stream)
        self.stream.read(1)  # mystery flag
        count = plug_element_count(attr_name)
        return attr_name, count

    def _parse_string_attribute(self):
        attr_name, count = self._parse_attribute_info()
        value = read_null_terminated(self.stream)
        self._attributes.append((attr_name, value, 'string'))

    def _parse_double_attribute(self):
        attr_name, count = self._parse_attribute_info()
        value = struct.unpack(">" + "d" * count,
                              self.stream.read(8 * count))
        value = value[0] if count == 1 else value
        self._attributes.append((attr_name, value, 'double'))

    def _parse_double3_attribute(self):
        attr_name, count = self._parse_attribute_info()
        value = struct.unpack(">" + "ddd" * count,
                              self.stream.read(24 * count))
        self._attributes.append((attr_name, value, 'double3'))

    def _parse_mpxdata_attribute(self, tyepid):
        # TODO
        pass
