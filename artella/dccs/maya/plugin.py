#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains Maya DCC plugin specific implementation
"""

from __future__ import print_function, division, absolute_import

import os
import json
import logging

import maya.cmds as cmds
import maya.mel as mel

import artella
from artella import dcc
from artella.core.dcc import callback
from artella.core import consts, callbacks, plugins, dccplugin, utils
from artella.dccs.maya import utils as maya_utils

logger = logging.getLogger('artella')


class ArtellaMayaPlugin(dccplugin.BaseArtellaDccPlugin):
    def __init__(self, artella_drive_client):
        super(ArtellaMayaPlugin, self).__init__(artella_drive_client=artella_drive_client)

        self._references_found = list()

    def get_version(self, force_update=False):
        """
        Returns current DCC plugin version

        :param bool force_update: Where or not force the update of the current Artella DCC plugin version
        :return: Version in string format (MAJOR.MINOR.PATH) of the current Artella DCC plugin
        :rtype: str or None
        """

        plugin_version = super(ArtellaMayaPlugin, self).get_version(force_update=force_update)

        if not plugin_version or force_update:
            version_var = self.get_version_variable_name()
            artella_path = artella.__path__[0]
            version_file_path = os.path.join(os.path.dirname(artella_path), 'plugin-version.json')
            if os.path.isfile(version_file_path):
                try:
                    with open(version_file_path) as fh:
                        version_data = json.load(fh)
                        version_found = version_data.get('version', None)
                        if version_found:
                            os.environ[version_var] = str(version_found)
                except Exception as exc:
                    logger.error('Impossible to retrieve Artella {} Plugin version data: {}!'.format(dcc.name(), exc))
            plugin_version = os.environ.get(version_var, None)

        return plugin_version

    def init(self, dev=False, show_dialogs=True, create_menu=True, create_callbacks=True, *args, **kwargs):
        """
        Initializes Artella DCC plugin

        :param bool dev: Whether plugin is initialized in development mode or not
        :param bool show_dialogs: Whether dialogs should appear during plugin initialization or not
        :param bool create_menu: Whether menu should be created or not
        :param bool create_callbacks: Whether or not DCC callbacks should be created
        :return: True if the initialization was successful; False otherwise.
        :rtype: bool
        """

        # Force Maya MEL stack trace on before we start using the plugin
        maya_utils.force_mel_stack_trace_on()

        super(ArtellaMayaPlugin, self).init(
            dev=dev, show_dialogs=show_dialogs, create_menu=create_menu, create_callbacks=create_callbacks,
            *args, **kwargs)

    def setup_callbacks(self):
        """
        Setup DCC Artella callbacks
        :return:
        """

        super(ArtellaMayaPlugin, self).setup_callbacks()

        callbacks.register(callback.Callbacks().AfterOpenCallback, self._after_open)
        callbacks.register(callback.Callbacks().SceneBeforeSaveCallback, self._before_save)
        callbacks.register(callback.Callbacks().BeforeOpenCheckCallback, self._before_open_check)
        callbacks.register(callback.Callbacks().AfterLoadReferenceCallback, self._after_load_reference)
        callbacks.register(callback.Callbacks().BeforeCreateReferenceCheckCallback, self._before_reference_check)

    def _post_update_paths(self, **kwargs):
        """
        Internal function that is called after update paths functionality is over.
        """

        files_updated = kwargs.get('files_updated', list())
        if not files_updated:
            return

        maya_utils.reload_textures(files_updated)

        # Dependencies are already reloaded during update paths process
        # maya_utils.reload_dependencies(files_updated)

    # ==============================================================================================================
    # FUNCTIONS
    # ==============================================================================================================

    def setup_project(self, artella_local_root_path):
        """
        Setup Artella local root as current DCC active project
        This function should be override in specific DCC plugin implementation
        Is not an abstract function because its implementation is not mandatory

        :param str artella_local_root_path: current user Artella local root path
        """

        artella_local_root_path = cmds.encodeString(artella_local_root_path)
        mel.eval('setProject "%s"' % artella_local_root_path.replace('\\', '\\\\'))
        cmds.workspace(directory=artella_local_root_path)
        cmds.workspace(fileRule=['sourceImages', ''])
        cmds.workspace(fileRule=['scene', ''])
        cmds.workspace(fileRule=['mayaAscii', ''])
        cmds.workspace(fileRule=['mayaBinary', ''])
        logger.info('Set Maya Workspace Path: {}'.format(artella_local_root_path))

    def validate_environment_for_callback(self, callback_name):
        """
        Checks that all necessary parts are available before executing a Maya callback

        :param str callback_name: name of the callback to validate
        """

        logger.info('validate_environment_for_callback for {}'.format(callback_name))
        client = self.get_client()
        if client:
            local_root = cmds.encodeString(client.get_local_root())
            if local_root:
                # We use this to make sure that Artella environment variable is set
                logger.debug('set local root in local environment: {}'.format(local_root))
                os.environ[consts.ALR] = local_root
                os.putenv(consts.ALR, local_root)
                mel.eval('putenv "{}" "{}"'.format(consts.ALR, local_root))

            if consts.ALR not in os.environ:
                msg = 'Unable to execute Maya "{}" callback, {} is not set in the environment'.format(
                    callback_name, consts.ALR)
                logger.error(msg)
                raise Exception(msg)

    # ==============================================================================================================
    # CALLBACKS
    # ==============================================================================================================

    def _after_open(self, *args):
        """
        Internal callback function that is called once a Maya scene is opened

        :param args:
        """

        if not self.is_artella_path():
            return

        self.validate_environment_for_callback('AfterOpen')

    def _before_save(self, *args):
        """
        Internal callback function that is called before saving a Maya scene

        :param args:
        """

        if not self.is_artella_path():
            return

        self.validate_environment_for_callback('BeforeSave')

        self.update_paths(show_dialogs=False, skip_save=True)

    def _before_open_check(self, maya_file, client_data=None):
        """
        Internal callback function that is called before a Maya scene is opened

        :param bool retcode: Flag that indicates if the file can opened or not
        :param MFileObject maya_file: Maya API object that contains info about the file we want to open
        :param dict client_data:
        """

        file_path = utils.clean_path(maya_file.resolvedFullName())

        if self.is_artella_path(file_path):

            logger.info('Opening file: "{}"'.format(file_path))
            self.validate_environment_for_callback('BeforeOpenCheck')

            logger.info('Checking missing dependencies ...')
            get_deps_plugin = plugins.get_plugin_by_id('artella-plugins-getdependencies')
            if not get_deps_plugin or not get_deps_plugin.is_loaded():
                msg = 'Get Dependencies plugin is not loaded. Get dependencies functionality is not available!'
                dcc.show_warning('Get Dependencies Plugin not available', msg)
                logger.warning(msg)
            else:
                get_deps_plugin.get_non_available_dependencies(file_path)

        return True

    def _after_load_reference(self, *args):
        """
        Internal callback function that is called after a Maya reference is loaded

        :param args:
        """

        if not self.is_artella_path():
            return

        self.validate_environment_for_callback('AfterLoadReference')

    def _before_reference_check(self, maya_file, client_data=None):
        """
        Internal callback function that is called before a Maya reference is opened

        :param bool retcode: Flag that indicates if the file can opened or not
        :param MFileObject maya_file: Maya API object that contains info about the file we want to open
        :param dict client_data:
        """

        if self.is_artella_path():
            self.validate_environment_for_callback('BeforeReferenceCheck')

            raw_full_name = maya_file.rawFullName()
            if not dccplugin.DccPlugin().is_path_translated(
                    raw_full_name) and dccplugin.DccPlugin().is_artella_path(raw_full_name):
                convert_path = dccplugin.DccPlugin().convert_path(raw_full_name)
                maya_file.setRawFullName(convert_path)

        return True
