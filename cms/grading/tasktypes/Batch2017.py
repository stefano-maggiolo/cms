#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2017 Amir Keivan Mohtashami <akmohtashami97@gmail.com>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging
import json

from cms.grading.ParameterTypes import ParameterTypeString
from cms.grading.tasktypes.Batch import Batch

logger = logging.getLogger(__name__)


class Batch2017(Batch):

    _USER_MANAGERS = ParameterTypeString(
        "User managers",
        "user_managers",
        "a JSON-encoded list of managers that should be provided by user when testing. "
    )

    ACCEPTED_PARAMETERS = Batch.ACCEPTED_PARAMETERS + [_USER_MANAGERS]

    def get_user_managers(self, unused_submission_format):
        """See TaskType.get_user_managers."""
        if self._uses_grader():
            try:
                user_managers = json.loads(self.parameters[3])
            except ValueError:
                user_managers = []
            return user_managers
        else:
            return []
