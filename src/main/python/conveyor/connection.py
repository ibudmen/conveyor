# vim:ai:et:ff=unix:fileencoding=utf-8:sw=4:ts=4:
# conveyor/src/main/python/conveyor/connection.py
#
# conveyor - Printing dispatch engine for 3D objects and their friends.
# Copyright © 2012 Matthew W. Samsonoff <matthew.samsonoff@makerbot.com>
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from __future__ import (absolute_import, print_function, unicode_literals)

import errno
import logging
import os
import os.path
import select
import socket
import threading

import conveyor.stoppable

class Connection(conveyor.stoppable.Stoppable):
    def __init__(self):
        conveyor.stoppable.Stoppable.__init__(self)
        self._log = logging.getLogger(self.__class__.__name__)

    def read(self):
        raise NotImplementedError

    def write(self, data):
        raise NotImplementedError

class ConnectionWriteException(Exception):
    pass

class _AbstractSocketConnection(Connection):
    def __init__(self, socket, address):
        Connection.__init__(self)
        self._condition = threading.Condition()
        self._stopped = False
        self._socket = socket
        self._address = address

    def stop(self):
        self._stopped = True

    def write(self, data):
        with self._condition:
            try:
                self._socket.sendall(data)
            except IOError as e:
                if e.args[0] in (errno.EINTR, errno.EAGAIN, errno.EWOULDBLOCK):
                    # NOTE: too spammy
                    # self._log.debug('handled exception', exc_info=True)
                    pass
                elif e.args[0] in (errno.EBADF, errno.EPIPE):
                    self._log.debug('handled exception', exc_info=True)
                    raise ConnectionWriteException
                else:
                    raise

if 'nt' != os.name:
    class _PosixSocketConnection(_AbstractSocketConnection):
        def stop(self):
            _AbstractSocketConnection.stop(self)
            # NOTE: use SHUT_RD instead of SHUT_RDWR or you will get annoying
            # 'Connection reset by peer' errors.
            try:
                self._socket.shutdown(socket.SHUT_RD)
                self._socket.close()
            except IOError as e:
                # NOTE: the Python socket implementation throws EBADF when you
                # invoke methods on a closed socket.
                if errno.EBADF != e.args[0]:
                    raise
                else:
                    self._log.debug('handled exception', exc_info=True)

        def read(self):
            while True:
                if self._stopped:
                    return ''
                else:
                    try:
                        data = self._socket.recv(4096)
                    except IOError as e:
                        if e.args[0] in (errno.EINTR, errno.EAGAIN, errno.EWOULDBLOCK):
                            # NOTE: too spammy
                            # self._log.debug('handled exception', exc_info=True)
                            continue
                        elif errno.ECONNRESET == e.args[0]:
                            self._log.debug('handled exception', exc_info=True)
                            return ''
                        else:
                            raise
                    else:
                        return data

    PipeConnection = _PosixSocketConnection
    SocketConnection = _PosixSocketConnection

else:
    import ctypes
    import ctypes.wintypes
    import conveyor.platform.win32 as win32

    # The size of the read buffer.
    _SIZE = 4096

    # The read polling timeout.
    _TIMEOUT = 1000

    class _Win32PipeConnection(Connection):
        @staticmethod
        def create(handle):
            buffer = ctypes.create_string_buffer(_SIZE)
            overlapped_read = _Win32PipeConnection.createoverlapped()
            overlapped_write = _Win32PipeConnection.createoverlapped()
            connection = conveyor.connection.PipeConnection(
                handle, buffer, overlapped_read, overlapped_write)
            return connection

        @staticmethod
        def createoverlapped():
            overlapped = win32.OVERLAPPED()
            overlapped.hEvent = win32.CreateEventW(None, False, False, None)
            return overlapped

        def __init__(self, handle, buffer, overlapped_read, overlapped_write):
            Connection.__init__(self)
            self._condition = threading.Condition()
            self._stopped = False
            self._handle = handle
            self._buffer = buffer
            self._overlapped_read = overlapped_read
            self._overlapped_write = overlapped_write

        def stop(self):
            self._stopped = True

        def read(self):
            count = ctypes.wintypes.DWORD()
            result = win32.ReadFile(
                self._handle, self._buffer, _SIZE, ctypes.byref(count),
                ctypes.byref(self._overlapped_read))
            if result:
                s = str(self._buffer[:count.value])
                return s
            else:
                error = win32.GetLastError()
                if win32.ERROR_BROKEN_PIPE == error:
                    return ''
                elif win32.ERROR_MORE_DATA == error:
                    s = str(self._buffer[:count.value])
                    return s
                elif win32.ERROR_IO_PENDING == error:
                    s = self._read_pending(count)
                    return s
                else:
                    raise win32.create_WindowsError(error)

        def _read_pending(self, count):
            while True:
                if self._stopped:
                    return ''
                else:
                    result = win32.WaitForSingleObject(
                        self._overlapped_read.hEvent, _TIMEOUT)
                    if win32.WAIT_TIMEOUT == result:
                        continue
                    elif win32.WAIT_OBJECT_0 == result:
                        result = win32.GetOverlappedResult(
                            self._handle, ctypes.byref(self._overlapped_read),
                            ctypes.byref(count), True)
                        if result:
                            s = str(self._buffer[:count.value])
                            return s
                        else:
                            error = win32.GetLastError()
                            if win32.ERROR_BROKEN_PIPE == error:
                                return ''
                            elif win32.ERROR_MORE_DATA == error:
                                s = str(self._buffer[:count.value])
                                return s
                            else:
                                raise win32.create_WindowsError(error)
                    else:
                        raise ValueError(result)

        def write(self, data):
            with self._condition:
                s = str(data)
                result = win32.WriteFile(
                    self._handle, s, len(s), None, self._overlapped_write)
                if not result:
                    error = win32.GetLastError()
                    if win32.ERROR_BROKEN_PIPE == error:
                        raise ConnectionWriteException
                    elif win32.ERROR_IO_PENDING == error:
                        count = ctypes.wintypes.DWORD()
                        result = win32.GetOverlappedResult(
                            self._handle, ctypes.byref(self._overlapped_write),
                            ctypes.byref(count), True)
                        if not result:
                            error = win32.GetLastError()
                            if win32.ERROR_BROKEN_PIPE == error:
                                raise ConnectionWriteException
                            else:
                                raise win32.create_WindowsError(error)
                    else:
                        raise win32.create_WindowsError(error)

    class _Win32SocketConnection(_AbstractSocketConnection):
        def read(self):
            while True:
                if self._stopped:
                    return ''
                else:
                    rlist, wlist, xlist = select.select([self._socket], [], [], 1.0)
                    if 0 != len(rlist):
                        try:
                            data = self._socket.recv(4096)
                        except IOError as e:
                            if errno.EINTR != e.args[0] and not self._stopped:
                                raise
                            else:
                                # NOTE: too spammy
                                # self._log.debug('handled exception', exc_info=True)
                                continue
                        else:
                            return data

    PipeConnection = _Win32PipeConnection
    SocketConnection = _Win32SocketConnection
