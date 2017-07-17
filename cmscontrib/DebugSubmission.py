#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
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

"""Utility to compile and evaluate a submission.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import logging
import sys

from cms import utf8_decoder, config
from cms.grading.Job import CompilationJob, EvaluationJob
from cms.service.esoperations import ESOperation
from cms.grading.tasktypes import get_task_type
from cms.db import SessionGen, Submission, Dataset
from cms.db.filecacher import FileCacher


logger = logging.getLogger(__name__)


def debugSubmission(submission_id, dataset_id, testcase_codename):
    config.keep_sandbox = True
    file_cacher = FileCacher()

    with SessionGen() as session:
        submission = session.query(Submission)\
            .filter(Submission.id == submission_id)\
            .first()

        if submission is None:
            logger.error("There's no submission with id %d" % submission_id)
            return False

        if dataset_id is None:
            dataset = submission.task.active_dataset
            dataset_id = submission.task.active_dataset_id
        else:
            dataset = session.query(Dataset)\
                .filter(Dataset.id == dataset_id)\
                .first()

        # Compilation
        operation = ESOperation(ESOperation.COMPILATION,
                                submission_id, dataset_id)
        comp_job = CompilationJob.from_submission(
            operation, submission, dataset)

        task_type = get_task_type(comp_job.task_type,
                                  comp_job.task_type_parameters)
        task_type.execute_job(comp_job, file_cacher)

        for sandbox_path in comp_job.sandboxes:
            logger.info("Compilation sandbox created in %s" % sandbox_path)

        # Check if the compilation is successful
        result = submission.get_result(dataset)
        if result is None or result.compilation_failed():
            logger.error("Compilatoin Failed")
            return True

        # Evaluation
        operation = ESOperation(ESOperation.EVALUATION,
                                submission_id, dataset_id,
                                testcase_codename)
        eval_job = EvaluationJob.from_submission(
            operation, submission, dataset)

        task_type = get_task_type(eval_job.task_type,
                                  eval_job.task_type_parameters)
        task_type.execute_job(eval_job, file_cacher)

        for sandbox_path in eval_job.sandboxes:
            logger.info("Evaluation sandbox created in %s" % sandbox_path)

    return True


def main():
    """Parse arguments and launch process.

    return (int): exit code of the program.

    """
    parser = argparse.ArgumentParser(
        description="Compiles and evaluates a submission on this machine")
    parser.add_argument("-d", "--dataset-id", action="store", type=int,
                        help="id of the dataset to test the submission on - if"
                        " not provided the task's active dataset will be used")
    parser.add_argument("submission_id", action="store", type=int,
                        help="id of the submission to debug")
    parser.add_argument("testcase_codename", action="store", type=utf8_decoder,
                        help="codename of the testcase to debug")

    args = parser.parse_args()

    success = debugSubmission(submission_id=args.submission_id,
                              dataset_id=args.dataset_id,
                              testcase_codename=args.testcase_codename)
    return 0 if success is True else 1


if __name__ == "__main__":
    sys.exit(main())
