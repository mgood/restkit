# -*- coding: utf-8 -
#
# This file is part of restkit released under the MIT license. 
# See the NOTICE for more information.

import atexit
from .manager import Manager

_manager = None

def set_manager(manager_instance=None):
    global _manager
    _manager = manager_instance

def set_default_manager():
    global _manager
    if _manager is None:
        _manager = Manager()

def get_manager():
    global _manager
    return _manager

set_default_manager()


def _stop():
    global _manager
    if _manager is not None:
        _manager.stop()

atexit.register(_stop)
