#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains Maya DCC callback implementation
"""

from __future__ import print_function, division, absolute_import

from artella.core.dcc import callback

import maya.api.OpenMaya as OpenMaya


class Callbacks(object):
    """
    Class that contains all supported callback definitions supported by Maya
    """

    class BeforeOpenCheckCallback(callback.AbstractCallback, object):
        """
        Callback that is called before a file is opened
        """

        @classmethod
        def filter(cls, *args):
            return True, args

        @classmethod
        def register(cls, fn):
            return OpenMaya.MSceneMessage.addCheckFileCallback(OpenMaya.MSceneMessage.kBeforeOpenCheck, fn)

        @classmethod
        def unregister(cls, token):
            if token:
                OpenMaya.MSceneMessage.removeCallback(token)

    class AfterOpenCallback(callback.AbstractCallback, object):
        """
        Callback that is called before opening a DCC scene
        """

        @classmethod
        def filter(cls, *args):
            return True, args

        @classmethod
        def register(cls, fn):
            return OpenMaya.MSceneMessage.addCallback(OpenMaya.MSceneMessage.kAfterOpen, fn)

        @classmethod
        def unregister(cls, token):
            if token:
                OpenMaya.MSceneMessage.removeCallback(token)

    class SceneBeforeSaveCallback(callback.AbstractCallback, object):
        """
        Callback that is called before a DCC scene is saved
        """

        @classmethod
        def filter(cls, *args):
            return True, args

        @classmethod
        def register(cls, fn):
            return OpenMaya.MSceneMessage.addCallback(OpenMaya.MSceneMessage.kBeforeSave, fn)

        @classmethod
        def unregister(cls, token):
            if token:
                OpenMaya.MSceneMessage.removeCallback(token)

    class SceneCreatedCallback(callback.AbstractCallback, object):
        """
        Callback that is called when a new DCC scene is created
        """

        _codes = [OpenMaya.MSceneMessage.kBeforeNew, OpenMaya.MSceneMessage.kBeforeOpen]

        @classmethod
        def filter(cls, *args):
            return True, args

        @classmethod
        def register(cls, fn):
            return [OpenMaya.MSceneMessage.addCallback(c, fn) for c in cls._codes]

        @classmethod
        def unregister(cls, token):
            for t in token:
                OpenMaya.MSceneMessage.removeCallback(t)

    class AfterLoadReferenceCallback(callback.AbstractCallback, object):
        """
        Callback that is called after a reference file is loaded
        """

        @classmethod
        def filter(cls, *args):
            return True, args

        @classmethod
        def register(cls, fn):
            return OpenMaya.MSceneMessage.addCallback(OpenMaya.MSceneMessage.kAfterLoadReference, fn)

        @classmethod
        def unregister(cls, token):
            if token:
                OpenMaya.MSceneMessage.removeCallback(token)

    class BeforeCreateReferenceCheckCallback(callback.AbstractCallback, object):
        """
        Callback that is called before a new reference is created
        """

        @classmethod
        def filter(cls, *args):
            return True, args

        @classmethod
        def register(cls, fn):
            return OpenMaya.MSceneMessage.addCheckFileCallback(OpenMaya.MSceneMessage.kBeforeCreateReferenceCheck, fn)

        @classmethod
        def unregister(cls, token):
            if token:
                OpenMaya.MSceneMessage.removeCallback(token)
