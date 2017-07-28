#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2017 Peyman Jabbarzade Ganje <peyman.jabbarzade@gmail.com>
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

"""Task type for output only tasks.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging

from cms.grading.TaskType import \
    create_sandbox, delete_sandbox
from cms.grading import white_diff_step, evaluation_step, \
    extract_outcome_and_text
from cms.grading.tasktypes.OutputOnly import OutputOnly

logger = logging.getLogger(__name__)


# Dummy function to mark translatable string.
def N_(message):
    return message


class OutputOnly2017(OutputOnly):

    def evaluate(self, job, file_cacher):
        """See TaskType.evaluate."""
        sandbox = create_sandbox(file_cacher, job.multithreaded_sandbox)
        job.sandboxes.append(sandbox.path)

        # Immediately prepare the skeleton to return
        job.sandboxes = [sandbox.path]
        job.plus = {}

        outcome = None
        text = None

        # Since we allow partial submission, if the file is not
        # present we report that the outcome is 0.
        file_name = "%s.out" % job.operation["testcase_codename"]
        if file_name not in job.files:
            job.success = True
            job.outcome = "0.0"
            job.text = [N_("File not submitted")]
            return True

        # First and only one step: diffing (manual or with manager).
        output_digest = job.files[file_name].digest

        # Put the files into the sandbox
        sandbox.create_file_from_storage(
            "res.txt",
            job.output)
        sandbox.create_file_from_storage(
            "output.txt",
            output_digest)

        if self.parameters[0] == "diff":
            # No manager: I'll do a white_diff between the submission
            # file and the correct output res.txt.
            success = True
            outcome, text = white_diff_step(
                sandbox, "output.txt", "res.txt")

        elif self.parameters[0] == "comparator":
            # Manager present: wonderful, it will do all the work.
            manager_filename = "checker"
            if manager_filename not in job.managers:
                logger.error("Configuration error: missing or "
                             "invalid comparator (it must be "
                             "named `checker')", extra={"operation": job.info})
                success = False
            else:
                sandbox.create_file_from_storage(
                    manager_filename,
                    job.managers[manager_filename].digest,
                    executable=True)
                input_digest = job.input
                sandbox.create_file_from_storage(
                    "input.txt",
                    input_digest)
                success, _ = evaluation_step(
                    sandbox,
                    [["./%s" % manager_filename,
                      "input.txt", "res.txt", "output.txt"]])
                if success:
                    outcome, text = extract_outcome_and_text(sandbox)

        else:
            raise ValueError("Unrecognized first parameter "
                             "`%s' for OutputOnly tasktype. "
                             "Should be `diff' or `comparator'." %
                             self.parameters[0])

        # Whatever happened, we conclude.
        job.success = success
        job.outcome = "%s" % outcome if outcome is not None else None
        job.text = text

        delete_sandbox(sandbox, job.success)
