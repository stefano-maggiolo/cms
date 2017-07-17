#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2015 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2017 Myungwoo Chun <mc.tamaki@gmail.com>
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

from cms.grading import compilation_step
from cms.grading.languagemanager import \
    LANGUAGES, get_language
from cms.grading.TaskType import create_sandbox, delete_sandbox
from cms.db import Executable
from cms.grading.tasktypes.Batch2017 import Batch2017

logger = logging.getLogger(__name__)


# Dummy function to mark translatable string.
def N_(message):
    return message


class Batch2017GraderCompile(Batch2017):

    def get_compilation_commands(self, submission_format):
        """See TaskType.get_compilation_commands."""
        source_filenames = []
        # If a grader is specified, we add to the command line (and to
        # the files to get) the corresponding manager.
        if self._uses_grader():
            source_filenames.append("grader.%l")
        source_filenames.append(submission_format[0])
        executable_filename = submission_format[0].replace(".%l", "")
        res = dict()
        for language in LANGUAGES:
            # For solutions using C or C++,
            # we first compile the grader source
            # file and then delete it from sandbox,
            # to prevent the user's solution
            # files from including it.
            additional_compile_command = []
            customized_source_filenames = list(source_filenames)
            if self._uses_grader():
                try:
                    additional_compile_command = language.\
                        get_compilation_no_link_command(
                            ["grader%s" % language.source_extension])
                    additional_compile_command += [
                        ["/bin/rm", "grader%s" % language.source_extension]
                    ]
                except NotImplementedError:
                    additional_compile_command = []
                else:
                    customized_source_filenames[0] = "grader%s" % \
                                                     language.object_extension

            res[language.name] = additional_compile_command + \
                language.get_compilation_commands(
                    [source.replace(".%l", language.source_extension)
                     for source in customized_source_filenames],
                    executable_filename)

        return res

    def compile(self, job, file_cacher):
        """See TaskType.compile."""
        # Detect the submission's language. The checks about the
        # formal correctedness of the submission are done in CWS,
        # before accepting it.
        language = get_language(job.language)
        source_ext = language.source_extension

        # TODO: here we are sure that submission.files are the same as
        # task.submission_format. The following check shouldn't be
        # here, but in the definition of the task, since this actually
        # checks that task's task type and submission format agree.
        if len(job.files) != 1:
            job.success = True
            job.compilation_success = False
            job.text = [N_("Invalid files in submission")]
            job.plus = {}
            logger.error("Submission contains %d files, expecting 1",
                         len(job.files), extra={"operation": job.info})
            return True

        # Create the sandbox
        sandbox = create_sandbox(file_cacher, job.multithreaded_sandbox)
        job.sandboxes.append(sandbox.path)

        # Prepare the source files in the sandbox
        files_to_get = {}
        format_filename = job.files.keys()[0]
        source_filenames = []
        source_filenames.append(format_filename.replace(".%l", source_ext))
        files_to_get[source_filenames[0]] = \
            job.files[format_filename].digest
        # If a grader is specified, we add to the command line (and to
        # the files to get) the corresponding manager. The grader must
        # be the first file in source_filenames.
        compile_command = []
        if self._uses_grader():
            files_to_get["grader%s" % source_ext] = \
                job.managers["grader%s" % source_ext].digest
            # For solutions using C or C++,
            # we first compile the grader source
            # file and then delete it from sandbox,
            # to prevent the user's solution
            # files from including it.
            try:
                compile_command = language.get_compilation_no_link_command(
                    ["grader%s" % source_ext])
                compile_command += [["/bin/rm", "grader%s" % source_ext]]
            except NotImplementedError:
                compile_command = []
                source_filenames.insert(0, "grader%s" % source_ext)
            else:
                source_filenames.insert(0, "grader%s" %
                                        language.object_extension)

        # Also copy all managers that might be useful during compilation.
        for filename in job.managers.iterkeys():
            if any(filename.endswith(header) for header in
                   language.header_extensions):
                files_to_get[filename] = \
                    job.managers[filename].digest
            elif any(filename.endswith(source) for source in
                     language.source_extensions):
                files_to_get[filename] = \
                    job.managers[filename].digest
            elif any(filename.endswith(obj) for obj in
                     language.object_extensions):
                files_to_get[filename] = \
                    job.managers[filename].digest

        for filename, digest in files_to_get.iteritems():
            sandbox.create_file_from_storage(filename, digest)

        # Prepare the compilation command
        executable_filename = format_filename.replace(".%l", "")
        commands = compile_command + language.get_compilation_commands(
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
