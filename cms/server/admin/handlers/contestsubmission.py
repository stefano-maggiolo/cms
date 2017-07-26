#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2016 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2017 Peyman Jabbarzade Ganje <peyman.jabarzade@gmail.com>
# Copyright © 2017 Kiarash Golezardi <kiarashgolezardi@gmail.com>
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

"""Submission-related handlers for AWS for a specific contest.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from tornado.web import MissingArgumentError

from cms.db import Contest, Submission, UserTest, Task, \
    SubmissionResult, Evaluation

from .base import BaseHandler, require_permission


class ContestSubmissionsHandler(BaseHandler):
    """Shows all submissions for this contest.

    """
    @require_permission(BaseHandler.AUTHENTICATED)
    def get(self, contest_id):
        contest = self.safe_get_item(Contest, contest_id)
        self.contest = contest

        query = self.sql_session.query(Submission).join(Task)\
            .filter(Task.contest == contest)
        filter_params = {
            "last_participation_id": None,
            "last_task_id": None,
            "last_outcome_filter": "",
            "last_details": ""
        }
        try:
            operation = self.get_argument("operation")
            if operation == "Filter":
                participation_id = self.get_argument("participation_id")
                if participation_id != 'null':
                    filter_params["last_participation_id"] = \
                        int(participation_id)
                    query = query.filter(Submission.participation_id ==
                                         participation_id)
                print(Exception.__class__.__name__)
                task_id = self.get_argument("task_id")
                if task_id != 'null':
                    filter_params["last_task_id"] = int(task_id)
                    query = query.filter(Task.id == task_id)
                outcome_filter = self.get_argument("outcome_filter")
                filter_params["last_outcome_filter"] = outcome_filter
                if outcome_filter != "":
                    outcome = "\"outcome\": \""+outcome_filter+"\""
                    query = query.join(SubmissionResult)\
                        .filter(SubmissionResult.score_details.
                                contains(outcome))
                details = self.get_argument("details")
                filter_params["last_details"] = details
                if details != "":
                    query = query.join(Evaluation)\
                        .filter(Evaluation.text.op('~')(details))\
                        .group_by(Submission.id)
        except MissingArgumentError:
            pass

        page = int(self.get_query_argument("page", 0))
        self.render_params_for_submissions(query, page)
        self.r_params.update(filter_params)
        self.render("contest_submissions.html", **self.r_params)


class AdvancedContestSubmissionsHandler(BaseHandler):
    @require_permission(BaseHandler.PERMISSION_ALL)
    def get(self, contest_id):
        contest = self.safe_get_item(Contest, contest_id)
        self.contest = contest

        self.r_params = self.render_params()

        self.r_params["next_page"] = ["contest", contest_id, "submissions"]
        invalidate_arguments = dict()
        invalidate_arguments["contest_id"] = contest_id
        self.r_params["invalidate_arguments"] = invalidate_arguments

        self.render("advanced_reevaluation.html", **self.r_params)


class ContestUserTestsHandler(BaseHandler):
    """Shows all user tests for this contest.

    """
    @require_permission(BaseHandler.AUTHENTICATED)
    def get(self, contest_id):
        contest = self.safe_get_item(Contest, contest_id)
        self.contest = contest

        query = self.sql_session.query(UserTest).join(Task)\
            .filter(Task.contest == contest)
        page = int(self.get_query_argument("page", 0))
        self.render_params_for_user_tests(query, page)

        self.render("contest_user_tests.html", **self.r_params)
