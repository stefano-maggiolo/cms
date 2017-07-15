#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2016 Masaki Hara <ackie.h.gmai@gmail.com>
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
import os
import tempfile

from cms import config
from cms.grading.Sandbox import wait_without_std, Sandbox
from cms.grading import compilation_step, \
    human_evaluation_message, is_evaluation_passed, extract_outcome_and_text, \
    evaluation_step, evaluation_step_before_run, evaluation_step_after_run, \
    merge_evaluation_results, white_diff_step
from cms.grading.languagemanager import \
    LANGUAGES, HEADER_EXTS, SOURCE_EXTS, OBJECT_EXTS, get_language
from cms.grading.ParameterTypes import ParameterTypeInt, ParameterTypeChoice
from cms.grading.TaskType import TaskType, \
    create_sandbox, delete_sandbox
from cms.db import Executable
from cms.grading.tasktypes.Batch import Batch
from cms.io.GeventUtils import rmtree


logger = logging.getLogger(__name__)


# Dummy function to mark translatable string.
def N_(message):
    return message


class Communication2017Base(TaskType):
    """Task type class for tasks that requires:

    - a *manager* that reads the input file, work out the perfect
      solution on its own, and communicate the input (maybe with some
      modifications) on its standard output; it then reads the
      response of the user's solution from the standard input and
      write the outcome;

    - a *stub* that compiles with the user's source, reads from
      standard input what the manager says, and write back the user's
      solution to stdout.

    """
    ALLOW_PARTIAL_SUBMISSION = False

    SUBMISSION_PAGE_MESSAGE = ""

    name = "Communication"

    _NUM_PROCESSES = ParameterTypeInt(
        "Number of Processes",
        "num_processes",
        "")

    _EVALUATION = ParameterTypeChoice(
        "Output evaluation",
        "output_eval",
        "",
        {"diff": "Outputs compared with white diff",
         "comparator": "Outputs are compared by a comparator"})

    ACCEPTED_PARAMETERS = [_NUM_PROCESSES, _EVALUATION]

    def get_compilation_commands(self, submission_format):
        """See TaskType.get_compilation_commands."""
        res = dict()
        for language in LANGUAGES:
            source_ext = language.source_extension
            source_filenames = []
            source_filenames.append("grader%s" % source_ext)
            executable_filename = \
                "_".join(pattern.replace(".%l", "")
                         for pattern in submission_format)
            for filename in submission_format:
                source_filename = filename.replace(".%l", source_ext)
                source_filenames.append(source_filename)
            commands = language.get_compilation_commands(
                source_filenames, executable_filename)
            res[language.name] = commands
        return res

    def get_user_managers(self, unused_submission_format):
        """See TaskType.get_user_managers."""
        return []

    def get_auto_managers(self):
        """See TaskType.get_auto_managers."""
        return None

    def compile(self, job, file_cacher):
        """See TaskType.compile."""

        # Detect the submission's language. The checks about the
        # formal correctedness of the submission are done in CWS,
        # before accepting it.
        language = get_language(job.language)
        source_ext = language.source_extension

        # Create the sandbox
        sandbox = create_sandbox(file_cacher, job.multithreaded_sandbox)
        job.sandboxes.append(sandbox.path)

        # Prepare the source files in the sandbox
        files_to_get = {}
        source_filenames = []
        # Stub.
        stub_filename = "grader%s" % source_ext
        source_filenames.append(stub_filename)
        files_to_get[stub_filename] = job.managers[stub_filename].digest
        # User's submission.
        for filename, fileinfo in job.files.iteritems():
            source_filename = filename.replace(".%l", source_ext)
            source_filenames.append(source_filename)
            files_to_get[source_filename] = fileinfo.digest

        # Also copy all managers that might be useful during compilation.
        for filename in job.managers.iterkeys():
            if any(filename.endswith(header) for header in HEADER_EXTS):
                files_to_get[filename] = \
                    job.managers[filename].digest
            elif any(filename.endswith(source) for source in SOURCE_EXTS):
                files_to_get[filename] = \
                    job.managers[filename].digest
            elif any(filename.endswith(obj) for obj in OBJECT_EXTS):
                files_to_get[filename] = \
                    job.managers[filename].digest

        for filename, digest in files_to_get.iteritems():
            sandbox.create_file_from_storage(filename, digest)

        # Prepare the compilation command
        executable_filename = \
            "_".join(pattern.replace(".%l", "")
                     for pattern in job.files.keys())
        commands = language.get_compilation_commands(
            source_filenames, executable_filename)

        # Run the compilation
        operation_success, compilation_success, text, plus = \
            compilation_step(sandbox, commands)

        # Retrieve the compiled executables
        job.success = operation_success
        job.compilation_success = compilation_success
        job.plus = plus
        job.text = text
        if operation_success and compilation_success:
            digest = sandbox.get_file_to_storage(
                executable_filename,
                "Executable %s for %s" %
                (executable_filename, job.info))
            job.executables[executable_filename] = \
                Executable(executable_filename, digest)

        # Cleanup
        delete_sandbox(sandbox, job.success)

    def evaluate(self, job, file_cacher):
        """See TaskType.evaluate."""

        if len(self.parameters) <= 0:
            num_processes = 1
        else:
            num_processes = self.parameters[0]
        indices = range(num_processes)
        # Create sandboxes and FIFOs
        sandbox_mgr = create_sandbox(file_cacher, job.multithreaded_sandbox)
        sandbox_user = [create_sandbox(file_cacher, job.multithreaded_sandbox)
                        for i in indices]
        fifo_dir = [tempfile.mkdtemp(dir=config.temp_dir) for i in indices]
        fifo_in = [os.path.join(fifo_dir[i], "in%d" % i) for i in indices]
        fifo_out = [os.path.join(fifo_dir[i], "out%d" % i) for i in indices]
        for i in indices:
            os.mkfifo(fifo_in[i])
            os.mkfifo(fifo_out[i])
            os.chmod(fifo_dir[i], 0o755)
            os.chmod(fifo_in[i], 0o666)
            os.chmod(fifo_out[i], 0o666)

        # First step: we start the manager.
        manager_filename = "manager"
        manager_command = ["./%s" % manager_filename]
        for i in indices:
            manager_command.append(fifo_in[i])
            manager_command.append(fifo_out[i])
        manager_executables_to_get = {
            manager_filename:
            job.managers[manager_filename].digest
            }
        manager_files_to_get = {
            "input.txt": job.input
            }
        manager_allow_dirs = fifo_dir
        for filename, digest in manager_executables_to_get.iteritems():
            sandbox_mgr.create_file_from_storage(
                filename, digest, executable=True)
        for filename, digest in manager_files_to_get.iteritems():
            sandbox_mgr.create_file_from_storage(filename, digest)
        manager = evaluation_step_before_run(
            sandbox_mgr,
            manager_command,
            num_processes * job.time_limit,
            0,
            allow_dirs=manager_allow_dirs,
            writable_files=["output.txt"],
            stdin_redirect="input.txt",
            stdout_redirect="output.txt",
        )

        # Second step: we start the user submission compiled with the
        # stub.
        language = get_language(job.language)
        executable_filename = job.executables.keys()[0]
        executables_to_get = {
            executable_filename:
            job.executables[executable_filename].digest
            }
        processes = [None for i in indices]
        for i in indices:
            args = [fifo_out[i], fifo_in[i]]
            if num_processes != 1:
                args.append(str(i))
            commands = language.get_evaluation_commands(
                executable_filename,
                main="grader",
                args=args)
            user_allow_dirs = [fifo_dir[i]]
            for filename, digest in executables_to_get.iteritems():
                sandbox_user[i].create_file_from_storage(
                    filename, digest, executable=True)
            # Assumes that the actual execution of the user solution
            # is the last command in commands, and that the previous
            # are "setup" that doesn't need tight control.
            if len(commands) > 1:
                evaluation_step(sandbox_user[i], commands[:-1], 10, 256)
            processes[i] = evaluation_step_before_run(
                sandbox_user[i],
                commands[-1],
                job.time_limit,
                job.memory_limit,
                allow_dirs=user_allow_dirs)

        # Consume output.
        wait_without_std(processes + [manager])
        # TODO: check exit codes with translate_box_exitcode.

        user_results = [evaluation_step_after_run(s) for s in sandbox_user]
        success_user = all(r[0] for r in user_results)
        plus_user = reduce(merge_evaluation_results,
                           [r[1] for r in user_results])
        success_mgr, unused_plus_mgr = \
            evaluation_step_after_run(sandbox_mgr)

        if plus_user['exit_status'] == Sandbox.EXIT_OK and \
                plus_user["execution_time"] >= job.time_limit:
            plus_user['exit_status'] = Sandbox.EXIT_TIMEOUT

        # Merge results.
        job.sandboxes = [s.path for s in sandbox_user] + [sandbox_mgr.path]
        job.plus = plus_user

        # If at least one evaluation had problems, we report the
        # problems.
        if not success_user or not success_mgr:
            success, outcome, text = False, None, None
        # If the user sandbox detected some problem (timeout, ...),
        # the outcome is 0.0 and the text describes that problem.
        elif not is_evaluation_passed(plus_user):
            success = True
            outcome, text = 0.0, human_evaluation_message(plus_user)
            if job.get_output:
                job.user_output = None
        # Otherwise, we use the manager to obtain the outcome.
        else:
            success = True
            outcome = None
            text = None

            input_filename = "input.txt"
            output_filename = "output.txt"
            # Check that the output file was created
            if not sandbox_mgr.file_exists(output_filename):
                outcome = 0.0
                text = [N_("Evaluation didn't produce file %s"),
                        output_filename]
                if job.get_output:
                    job.user_output = None

            else:
                # If asked so, put the output file into the storage
                if job.get_output:
                    job.user_output = sandbox_mgr.get_file_to_storage(
                        output_filename,
                        "Output file in job %s" % job.info,
                        trunc_len=1024 * 1024 * 10)

                # If just asked to execute, fill text and set dummy
                # outcome.
                if job.only_execution:
                    outcome = 0.0
                    text = [N_("Execution completed successfully")]

                # Otherwise evaluate the output file.
                else:

                    # Put the reference solution into the sandbox
                    sandbox_mgr.create_file_from_storage(
                        "res.txt",
                        job.output)

                    # Check the solution with white_diff
                    if self.parameters[1] == "diff":
                        outcome, text = white_diff_step(
                            sandbox_mgr, output_filename, "res.txt")

                    # Check the solution with a comparator
                    elif self.parameters[1] == "comparator":
                        manager_filename = "checker"

                        if manager_filename not in job.managers:
                            logger.error("Configuration error: missing or "
                                         "invalid comparator (it must be "
                                         "named 'checker')",
                                         extra={"operation": job.info})
                            success = False

                        else:
                            sandbox_mgr.create_file_from_storage(
                                manager_filename,
                                job.managers[manager_filename].digest,
                                executable=True)
                            # Rewrite input file. The untrusted
                            # contestant program should not be able to
                            # modify it; however, the grader may
                            # destroy the input file to prevent the
                            # contestant's program from directly
                            # accessing it. Since we cannot create
                            # files already existing in the sandbox,
                            # we try removing the file first.
                            try:
                                sandbox_mgr.remove_file(input_filename)
                            except OSError as e:
                                # Let us be extra sure that the file
                                # was actually removed and we did not
                                # mess up with permissions.
                                assert not sandbox_mgr.file_exists(input_filename)
                            sandbox_mgr.create_file_from_storage(
                                input_filename,
                                job.input)

                            # Allow using any number of processes (because e.g.
                            # one may want to write a bash checker who calls
                            # other processes). Set to a high number because
                            # to avoid fork-bombing the worker.
                            sandbox_mgr.max_processes = 1000

                            success, _ = evaluation_step(
                                sandbox_mgr,
                                [["./%s" % manager_filename,
                                  input_filename, "res.txt", output_filename]])
                        if success:
                            try:
                                outcome, text = \
                                    extract_outcome_and_text(sandbox_mgr)
                            except ValueError as e:
                                logger.error("Invalid output from "
                                             "comparator: %s", e.message,
                                             extra={"operation": job.info})
                                success = False

                    else:
                        raise ValueError("Unrecognized second parameter"
                                         " `%s' for Communication tasktype." %
                                         self.parameters[2])

        # Whatever happened, we conclude.
        job.success = success
        job.outcome = "%s" % outcome if outcome is not None else None
        job.text = text

        delete_sandbox(sandbox_mgr, job.success)
        for s in sandbox_user:
            delete_sandbox(s, job.success)
        if not config.keep_sandbox:
            for d in fifo_dir:
                rmtree(d)
