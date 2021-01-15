#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains Maya window implementation
"""

from __future__ import print_function, division, absolute_import

from artella.core.dcc import window


class MayaWindow(window.BaseWindow, object):
    def __init__(self, parent=None, **kwargs):
        super(MayaWindow, self).__init__(parent, **kwargs)
