from artella import register
from artella.core.dcc import window


class MayaWindow(window.AbstractWindow, object):
    def __init__(self, parent=None, **kwargs):
        super(MayaWindow, self).__init__(parent, **kwargs)


register.register_class('Window', MayaWindow)
