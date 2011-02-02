# -*- coding: utf-8 -
#
# This file is part of restkit released under the MIT license. 
# See the NOTICE for more information.

from __future__ import with_statement

from collections import deque
import logging
import signal
import socket
import threading
import time

from ..sock import close

log = logging.getLogger(__name__)


class Scheduler(threading.Thread):

    running = False

    def __init__(self, cb, timeout):
        self.cb = cb
        self.timeout = timeout
        threading.Thread.__init__(self)
        
        self._shutdown = threading.Event()
        self._stopped = threading.Event()
        
        self.mutex = threading.Lock()
        self.not_empty = threading.Condition(self.mutex)
        self.setDaemon(True)
       
    def get_lock(self):
         return threading.Lock()

    def run(self):
        self.running = True
        while not self._shutdown.isSet():
            time.sleep(self.timeout)
            self.cb()

        try:
            self._stopped.set()
        except TypeError:
            pass
    
    def stop(self):
        if self.running:
            self._shutdown.set()
            self._stopped.wait()
            self.join(1e10)
            self.running = False

    def ensure_started(self):
        if not self.running and not self.isAlive():
            self.start()

class Manager(object):

    def __init__(self, max_conn=10, timeout=150):
        """
        If monitoring is used.
        """
        self.max_conn = max_conn
        self.timeout = timeout

        self.sockets = dict()
        self.active_sockets = dict()
        self.connections_count = dict()
        self._lock = self.get_lock()

        self._scheduler = None

        #if timeout is not None:
        self.start()

    def get_lock(self):
        return threading.RLock()

    def murder_connections(self, *args):
        self._lock.acquire()
        try:
            active_sockets = self.active_sockets.copy()
            for fno, (sock, t0) in active_sockets.items():
                diff = time.time() - t0
                if diff <= self.timeout:
                    continue
                close(sock)
                del self.active_sockets[fno]
        finally:
            self._lock.release()

    def close_connections(self):
        self._lock.acquire()
        try:
            active_sockets = self.active_sockets.copy()

            for fno, (sock, t0) in active_sockets.items():
                close(sock)
                del self.active_sockets[fno]
        finally:
            self._lock.release()

       
    def start(self):
        self._scheduler = Scheduler(self.murder_connections)
        self._scheduler.start()

    def stop(self):
        self._scheduler.stop()
        self.close_connections() 

    def all_connections_count(self):
        """ return all counts per address registered. """
        return self.connections_count.items()

    def connection_count(self, addr, ssl):
        """ get connections count for an address """
        self._lock.acquire()
        try:
            return self.connections_count[(addr, ssl)]
        finally:
            self._lock.release()

        return self.connections_count[(addr, ssl)]

    def find_socket(self, addr, ssl=False):
        """ find a socket from a its address in the pool and return if
        there is one available, else, return None """

        self._lock.acquire()
        try:
            key = (addr, ssl)
            try:
                socks = self.sockets[key]
                while True:
                    sock = socks.pop()
                    if sock.fileno() in self.active_sockets:
                        del self.active_sockets[sock.fileno()]
                        break
                self.sockets[key] = socks
                self.connections_count[key] -= 1
                log.debug("get connection from manager")
                return sock
            except (IndexError, KeyError,):
                return None
        finally:
            self._lock.release()

    def store_socket(self, sock, addr, ssl=False):
        """ store a socket in the pool to reuse it across threads """

        self._lock.acquire()
        try:
            key = (addr, ssl)
            try:
                socks = self.sockets[key]
            except KeyError:
                socks = deque()

            if len(socks) < self.max_conn:
                # add connection to the pool
                try:
                    self.active_sockets[sock.fileno()] = (sock, time.time())
                except (socket.error, AttributeError,):
                    # socket has been closed
                    log.info("socket closed")
                    return

                socks.appendleft(sock)
                self.sockets[key] = socks
                
                try:
                    self.connections_count[key] += 1
                except KeyError:
                    self.connections_count[key] = 1 

                log.debug("put connection in manager %s" %
                        self.all_connections_count())
            else:
                # close connection if we have enough connections in the
                # pool.
                close(sock)
        finally:
            self._lock.release()

class AsyncManager(Manager):

    def start(self):
        signal.signal(signal.SIGALRM, self.murder_connections)
        signal.alarm(self.timeout)

    def stop(self):
        self.close_connections() 
