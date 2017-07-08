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

from cms.grading.scoretypes.GroupMin import GroupMin

# Dummy function to mark translatable string.


def N_(message):
    return message


class GroupMinWithMaxScore(GroupMin):
    def __init__(self, parameters, public_testcases):
        super(GroupMinWithMaxScore, self).__init__(
            parameters[1:],
            public_testcases
        )
        self.max_score = min(self.max_score, parameters[0])
        self.max_public_score = min(self.max_public_score, self.max_score)

    def compute_total_score(self, *args, **kwargs):
        score, score_details, \
            public_score, public_score_details, ranking_details = \
            super(GroupMinWithMaxScore, self).compute_total_score(
                *args, **kwargs
            )
        score = min(score, self.max_score)
        public_score = min(public_score, self.max_score)
        return score, score_details, \
            public_score, public_score_details, ranking_details
