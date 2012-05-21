# vim:ai:et:ff=unix:fileencoding=utf-8:sw=4:ts=4:
# conveyor/src/main/python/conveyor/client/__main__.py
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

import json
import logging.config
import sys
import threading

try:
    import unittest2 as unittest
except ImportError:
    import unittest

import conveyor.client
import conveyor.log
import conveyor.main

class _ClientMain(conveyor.main.AbstractMain):
    def __init__(self):
        conveyor.main.AbstractMain.__init__(self, 'conveyor')

    def _initparser(self):
        parser = conveyor.main.AbstractMain._initparser(self)
        for method in (
            self._initparser_config,
            self._initparser_logging,
            self._initparser_version,
            self._initparser_subparsers,
            ):
                method(parser)
        return parser

    def _initparser_config(self, parser):
        parser.add_argument(
            '-c',
            '--config',
            default='/etc/conveyor/conveyor.conf',
            type=str,
            help='the configuration file',
            metavar='FILE')

    def _initparser_subparsers(self, parser):
        subparsers = parser.add_subparsers(dest='command', title='Commands')
        self._initsubparser_print(subparsers)
        self._initsubparser_printtofile(subparsers)

    def _initsubparser_print(self, subparsers):
        parser = subparsers.add_parser('print', help='print a .thing')
        parser.set_defaults(func=self._run_print)
        self._initparser_common(parser)

    def _initsubparser_printtofile(self, subparsers):
        parser = subparsers.add_parser('printtofile', help='print a .thing to an .s3g file')
        parser.set_defaults(func=self._run_printtofile)
        self._initparser_common(parser)
        parser.add_argument(
            's3g', help='the output path for the .s3g file', metavar='S3G')

    def _initparser_common(self, parser):
        for method in (
            self._initparser_config,
            self._initparser_logging,
            self._initparser_version,
            ):
                method(parser)
        parser.add_argument(
            'thing', help='the path to the .thing file', metavar='THING')

    def _setdefaults(self, config):
        config.setdefault('socket', 'unix:/var/run/conveyor/conveyord.socket')

    def _run(self, parser, args):
        try:
            with open(args.config, 'r') as fp:
                config = json.load(fp)
        except EnvironmentError as e:
            code = 1
            self._log.critical(
                'failed to open configuration file: %s: %s', args.config,
                e.strerror, exc_info=True)
        except ValueError:
            code = 1
            self._log.critical(
                'failed to parse configuration file: %s', args.config,
                exc_info=True)
        else:
            self._setdefaults(config)
            code = self._run_logging(args, config)
        return code

    # These are the methods called during initialization. Each method makes a
    # tail call (non-optimized, of course) to the next method.
    #
    # 1. _run_logging
    # 2. _run_eventqueue
    # 3. _run_socket
    # 4. _run_print or _run_printtofile
    # 5. _run_client

    def _run_logging(self, args, config):
        try:
            dct = config.get('logging')
            if None is not dct:
                dct['incremental'] = False
                dct['disable_existing_loggers'] = False
                logging.config.dictConfig(dct)
                if args.level:
                    root = logging.getLogger()
                    root.setLevel(args.level)
        except ValueError as e:
            code = 1
            self._log.critical(
                'invalid logging configuration: %s', e.message,
                exc_info=True)
        else:
            code = self._run_eventqueue(args, config)
        return code

    def _run_eventqueue(self, args, config):
        value = config.get('eventthreads')
        try:
            count = int(value)
        except ValueError:
            code = 1
            self._log.critical('invalid value for "eventthreads": %s', value)
        else:
            eventqueue = conveyor.event.geteventqueue()
            threads = []
            for i in range(count):
                name = 'eventqueue-%d' % (i,)
                thread = threading.Thread(target=eventqueue.run, name=name)
                thread.start()
                threads.append(thread)
            try:
                code = self._run_socket(args, config)
            finally:
                eventqueue.quit()
                for thread in threads:
                    thread.join(1)
                    if thread.is_alive():
                        self._log.debug('thread not terminated: %r', thread)
        return code

    def _run_socket(self, args, config):
        value = config['socket']
        address = self._getaddress(value)
        if None == address:
            # NOTE: _getaddress has issues the error message itself.
            code = 1
        else:
            with address:
                try:
                    sock = address.connect()
                except EnvironmentError as e:
                    code = 1
                    self._log.critical(
                        'failed to open socket: %s: %s', value,
                        e.strerror, exc_info=True)
                else:
                    code = args.func(args, config, sock)
        return code

    def _run_print(self, args, config, sock):
        params = [args.thing]
        self._log.info('printing: %s', args.thing)
        code = self._run_client(args, config, sock, 'print', params)
        return code

    def _run_printtofile(self, args, config, sock):
        params = [args.thing, args.s3g]
        self._log.info('printing to file: %s -> %s', args.thing, args.s3g)
        code = self._run_client(args, config, sock, 'printtofile', params)
        return code

    def _run_client(self, args, config, sock, method, params):
        client = conveyor.client.Client.create(sock, method, params)
        code = client.run()
        return code

class _ClientMainTestCase(unittest.TestCase):
    pass

def _main(argv): # pragma: no cover
    conveyor.log.earlylogging('conveyor')
    main = _ClientMain()
    code = main.main(argv)
    return code

if '__main__' == __name__: # pragma: no cover
    sys.exit(_main(sys.argv))
