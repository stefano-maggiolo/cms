#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2017-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Simple atomic integer implementation.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import gevent.lock


class AtomicInt(object):

    def __init__(self, value=0):
        self._lock = gevent.lock.RLock()
        self.value = value

    def get(self):
        with self._lock:
            return self.value

    def get_and_add(self, delta):
        with self._lock:
            r = self.value
            self.value += delta
        return r
