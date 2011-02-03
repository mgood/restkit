# -*- coding: utf-8 -
#
# This file is part of restkit released under the MIT license. 
# See the NOTICE for more information.

"""
gevent connection manager. 
"""
import os
import time

import gevent
from gevent.coros import Semaphore, RLock
from gevent.event import Event
from gevent.hub import get_hub

from .base import Manager


class GeventConnectionReaper(object):

    running = False

    def __init__(self, manager, delay=150):
        self.manager = manager
        self.delay = delay
        self.g = None

    def start(self):
        self.running = "false"
        self._spawn()

    def _spawn(self):
        g = gevent.spawn_later(self.delay, self._exec)
        g.link(self._exit)
        self._g = g
        gevent.sleep(0)

    def _exit(self, g):
        try:
            g.wait()
        except:
            pass       

    def _exec(self):
        self.manager.murder_connections()
        self._spawn()
        gevent.sleep(0)

    def ensure_started(self):
        if not self.running:
            self.start()

class GeventManager(Manager):

    def get_lock(self):
        return RLock()
           
    def start(self):
        if self.with_signaling:
            signal.signal(signal.SIGALRM, self.murder_connections)
            signal.alarm(self.timeout)
        else:
            self._reaper = GeventConnectionReaper(self, delay=self.timeout)
            self._reaper.ensure_started()
