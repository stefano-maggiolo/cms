#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2015 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
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

"""Manager for the set of workers.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa
from six import iteritems

import logging

from collections import deque
from datetime import timedelta
from functools import wraps

import gevent.lock

from gevent.event import Event

from cms.db import Dataset, SessionGen, Submission, UserTest
from cms.grading.Job import Job, JobGroup
from cmscommon.datetime import make_datetime, make_timestamp


logger = logging.getLogger(__name__)


class WorkerStatus(object):
    """Container for the possible statuses of a worker."""

    DISABLED = "disabled"
    INACTIVE = "inactive"
    ACTIVE = "active"

    @staticmethod
    def ensure_in(*statuses):
        """Return a decorator ensuring that the status is appropriate."""
        def decorator(f):
            @wraps(f)
            def wrapped(self, *args, **kwargs):
                if self._status not in statuses:
                    err_msg = "Trying to call %s in status %s." % (
                        f.__name__, self._status)
                    logger.error(err_msg)
                    raise ValueError(err_msg)
                return f(self, *args, **kwargs)
            return wrapped
        return decorator


class WorkerData(object):
    """The data associated to a worker in the worker pool."""

    def __init__(self, es, worker_coord, on_connect_handler,
                 action_finished_handler):
        """Initialization of the worker data.

        es (Service): EvaluationService controlling the workers.
        worker_coord (ServiceCoord): coordinates of the worker.
        on_connect_handler (function): function with no arguments to be called
            when the worker connects.
        action_finished_handler (function): function to be called when the
            worker signals the end of the work, with arguments (data, shard,
            error) and must call WorkerData.release().

        """
        self._shard = worker_coord.shard
        logger.debug("Worker %s added.", self._shard)

        self._contest_id = es.contest_id
        self._on_connect_handler = on_connect_handler
        self._action_finished_handler = action_finished_handler

        self._worker = es.connect_to(
            worker_coord, on_connect=self._on_worker_connected)

        # Status of the worker, can be disabled (connected but not used by ES),
        # inactive (i.e., ready to take operations), active (currently
        # performing operations.
        # Type: string
        self._status = WorkerStatus.INACTIVE
        # Operations the worker is currently executing. Non-empty if and only
        # if status is ACTIVE.
        # Type: [ESOperation]
        self._operations = list()
        # Operations the worker is currently executing but for which
        # the results should be ignored. Non-empty only if status is ACTIVE.
        # Type: {ESOperation}
        self._operations_to_ignore = set()
        # Time at which the worker started working on these operations.
        # Not None only if the status is ACTIVE.
        # Type: Datetime|None
        self._start_time = None

    def _on_worker_connected(self, unused_worker_coord):
        """Callback for when the worker comes back alive.

        We use this callback to instruct the worker to precache all files
        concerning the contest, and to call the master callback.

        unused_worker_coord (ServiceCoord): worker coordinates.

        """
        logger.info("Worker %s online again.", self._shard)
        self._worker.precache_files(contest_id=self._contest_id)
        self._on_connect_handler(self._shard)

    def _reset(self):
        """Reset the internal state to a default inactive or disabled worker.

        If the worker was disabled, we keep it that way, otherwise it is reset
        to an inactive worker.

        """
        if self._status != WorkerStatus.DISABLED:
            self._status = WorkerStatus.INACTIVE
        self._operations = []
        self._operations_to_ignore = set()
        self._start_time = None

    def get_status(self):
        """Return information about this worker.

        return ({}): a dict with some information.

        """
        start_time = \
            make_timestamp(self._start_time) \
            if self._start_time is not None else None
        return {
            'connected': self._worker.connected,
            'status': self._status,
            'start_time': start_time,
            'operations': [operation.to_dict()
                           for operation in self._operations],
        }

    @property
    def is_inactive(self):
        return self._status == WorkerStatus.INACTIVE

    @property
    def is_active(self):
        return self._status == WorkerStatus.ACTIVE

    @property
    def is_connected(self):
        return self._worker.connected

    @property
    def active_time(self):
        """Return for how long the worker has been active.

        return (timedelta): how long the worker has been active, or 0
            if the worker is not active.

        """
        if self._start_time is not None:
            return make_datetime() - self._start_time
        else:
            return timedelta(seconds=0)

    @WorkerStatus.ensure_in(WorkerStatus.INACTIVE)
    def set_active(self, operations):
        """Instruct the worker to perform the operations.

        operations ([ESOperation]): the operations the worker will perform.

        """
        self._start_time = make_datetime()
        self._operations = operations
        self._status = WorkerStatus.ACTIVE

        # Build the JobGroup object.
        with SessionGen() as session:
            jobs = []
            datasets = {}
            submissions = {}
            user_tests = {}
            for operation in operations:
                if operation.dataset_id not in datasets:
                    datasets[operation.dataset_id] = Dataset.get_from_id(
                        operation.dataset_id, session)
                if operation.for_submission():
                    if operation.object_id not in submissions:
                        submissions[operation.object_id] = \
                            Submission.get_from_id(
                                operation.object_id, session)
                    object_ = submissions[operation.object_id]
                else:
                    if operation.object_id not in user_tests:
                        user_tests[operation.object_id] = \
                            UserTest.get_from_id(operation.object_id, session)
                    object_ = user_tests[operation.object_id]
                logger.info("Asking worker %s to `%s'.",
                            self._shard, operation)

                jobs.append(Job.from_operation(
                    operation, object_, datasets[operation.dataset_id]))
            job_group_dict = JobGroup(jobs).export_to_dict()

        self._worker.execute_job_group(
            job_group_dict=job_group_dict,
            callback=self._action_finished_handler,
            plus=self._shard)

    def release(self):
        """To be called by ES when it receives a notification that an
        operation finished.

        The worker's result might have already been sent to ES as work
        to ignore, in case the worker was disabled or had some
        problems. In these cases, we send again those results, again
        as to be ignored.

        The worker status is set to inactive, unless the worker had
        already been disabled, in which case it stays as disabled.

        return (([ESOperation], [ESOperation])): the first element is the
            list of operations to consider, the second the list of operations
            to ignore.

        """
        to_consider = []
        to_ignore = []
        if self._status != WorkerStatus.ACTIVE:
            # Regardless of individual operation's ignoring, if the
            # worker is scheduled for disabling we do not use any of
            # its results. In the same way, we ignore all results if
            # the status is inactive, as that means that the worker had
            # already been released in the past (maybe because it was
            # stuck) and we already requeued its operations.
            to_ignore = self._operations
        else:
            for operation in self._operations:
                if operation in self._operations_to_ignore:
                    to_ignore.append(operation)
                else:
                    to_consider.append(operation)
        self._reset()
        return (to_consider, to_ignore)

    @WorkerStatus.ensure_in(WorkerStatus.INACTIVE, WorkerStatus.ACTIVE)
    def disable(self):
        """Disable the worker, ignoring all operations currently executing.

        return (([ESOperation], [ESOperation])): same as release().

        """
        self._status = WorkerStatus.DISABLED
        if self._status == WorkerStatus.ACTIVE:
            return self.release()
        else:  # self._status == WorkerStatus.INACTIVE
            return ([], [])

    def quit(self, reason):
        """Switch off the worker and disable it.

        return (([ESOperation], [ESOperation])): same as release().

        """
        self._worker.quit(reason=reason)
        return self.disable()

    @WorkerStatus.ensure_in(WorkerStatus.DISABLED)
    def enable(self):
        """Enable the worker."""
        self._status = WorkerStatus.INACTIVE

    def ignore(self, operation):
        """Ignore the operation.

        operation (ESOperation): the operation to ignore; must be in the list
            of currently executing, non-ignored, operations.

        raise (ValueError): if operation is not amongst the running operations.

        """
        if operation not in self._operations:
            raise ValueError("Asked to ignore operation not present %s.",
                             operation)
        self._operations_to_ignore.add(operation)


class WorkerPool(object):
    """This class keeps the state of the workers attached to ES, and
    allow the ES to get a usable worker when it needs it.

    """

    # Time since acquisition after which we declare a worker stale.
    WORKER_TIMEOUT = timedelta(seconds=600)

    def __init__(self, es):
        """es (Service): the EvaluationService using this WorkerPool.

        """
        self._es = es
        self._worker = {}

        # TODO: at the moment race conditions during the periodic
        # checks cannot be excluded. A refactoring of this class
        # should take that into account.

        # A reverse lookup dictionary mapping operations to shards.
        # Type: {ESOperation: int}
        self._operations_reverse = dict()

        # A lock to ensure that the reverse lookup stays in sync with
        # the operations lists.
        self._operation_lock = gevent.lock.RLock()

        # Shards that are (possibly) available for new operations.
        self._free_workers = deque()

        # Event set when there are workers available to take jobs. It
        # is only guaranteed that if a worker is available, then this
        # event is set. In other words, the fact that this event is
        # set does not mean that there is a worker available.
        self._free_workers_event = Event()

    def __len__(self):
        return len(self._worker)

    def __contains__(self, operation):
        return operation in self._operations_reverse

    def wait_for_workers(self):
        """Wait until a worker might be available.

        When this method returns, there might still be no workers available due
        to multiple greenlets/threads waiting. Callers must handle retries.

        """
        self._free_workers_event.wait()

    def add_worker(self, worker_coord):
        """Add a new worker to the worker pool.

        worker_coord (ServiceCoord): the coordinates of the worker.

        """
        if worker_coord.shard in self._worker:
            raise ValueError("Worker %s already in the pool" % worker_coord)
        self._worker[worker_coord.shard] = WorkerData(
            self._es, worker_coord,
            self._on_worker_maybe_free,
            self._action_finished)
        self._on_worker_maybe_free(worker_coord.shard)

    def _on_worker_maybe_free(self, shard):
        """Method to call when a worker connects.

        This method can be safely called even if the worker is not free, or
        multiple times for the same worker.

        On the other hand, it must be called when the worker is free, otherwise
        the worker will not get operations to perform.

        shard (int): the shard of the worker that might be free.

        """
        self._free_workers.append(shard)
        self._free_workers_event.set()

    def _action_finished(self, data, shard, error=None):
        """Callback for when a worker finishes an action.

        This method releases the worker, that becomes available for
        other operations (unless it had been disabled), and calls the
        action_finished method in ES.

        data (dict): the JobGroup, exported to dict.
        shard (int): the shard finishing the action.
        error (string|None): error from the worker, if not None.

        """
        with self._operation_lock:
            to_consider, to_ignore = self._worker[shard].release()
            for operation in to_consider + to_ignore:
                del self._operations_reverse[operation]
        if self._worker[shard].is_inactive:
            self._free_workers.append(shard)
            self._free_workers_event.set()
        self._es.action_finished(data, shard, to_consider, to_ignore, error)

    def acquire_worker(self, operations):
        """Tries to assign an operation to an available worker. If no workers
        are available then this returns None, otherwise this returns
        the chosen worker.

        operations ([ESOperation]): the operations to assign to a worker.

        return (int|None): None if no workers are available, the worker
            assigned to the operation otherwise.

        """
        # We look for an available worker.
        try:
            shard = self._free_workers.popleft()
        except IndexError:
            self._free_workers_event.clear()
            return None

        # The worker might have been disabled while it was in the queue.
        if not (self._worker[shard].is_inactive
                and self._worker[shard].is_connected):
            return None

        logger.debug("Worker %s acquired.", shard)

        # Then we fill the info for future memory.
        with self._operation_lock:
            self._worker[shard].set_active(operations)
            for operation in operations:
                self._operations_reverse[operation] = shard

        return shard

    def ignore_operation(self, operation):
        """Mark the operation to be ignored.

        operation (ESOperation): the operation to ignore.

        raise (LookupError): if operation is not found.

        """
        try:
            with self._operation_lock:
                shard = self._operations_reverse[operation]
                self._worker[shard].ignore(operation)
        except LookupError:
            logger.debug("Asked to ignore operation `%s' "
                         "that cannot be found.", operation)
            raise

    def get_status(self):
        """Returns a dict with info about the current status of all
        workers.

        return (dict): dict of info: current operation, starting time,
            number of errors, and additional data specified in the
            operation.

        """
        result = dict()
        for shard, worker in iteritems(self._worker):
            result["%d" % shard] = worker.get_status()
        return result

    def disable_worker(self, shard):
        """Disable a worker.

        shard (int): which worker to disable.

        return ([ESOperation]): list of non-ignored operations
            assigned to the worker.

        raise (ValueError): if worker is already disabled.

        """
        lost_operations, _ = self._worker[shard].disable()
        logger.info("Worker %s disabled.", shard)
        return lost_operations

    def enable_worker(self, shard):
        """Enable a worker that previously was disabled.

        shard (int): which worker to enable.

        raise (ValueError): if worker is not disabled.

        """
        self._worker[shard].enable()
        logger.info("Worker %s enabled.", shard)
        self._on_worker_maybe_free(shard)

    def check_timeouts(self):
        """Check if some worker is not responding in too much time.

        If this is the case, the worker is disabled, and we send it a
        message trying to shut it down.

        return ([ESOperation]): list of operations assigned to worker
            that timeout.

        """
        lost_operations = []
        for shard in self._worker:
            active_for = self._worker[shard].active_time
            if active_for > WorkerPool.WORKER_TIMEOUT:
                # Here shard is a working worker with no sign of
                # intelligent life for too much time.
                logger.error("Disabling and shutting down worker %d because "
                             "of no response in %s.", shard, active_for)

                lost, _ = self._worker[shard].quit(
                    "No response for a long time.")
                lost_operations += lost

        return lost_operations

    def check_connections(self):
        """Check if a worker we assigned an operation to disconnects. In this
        case, requeue the operation.

        return ([ESOperation]): list of operations assigned to worker
            that disconnected.

        """
        lost_operations = []
        for shard, worker in iteritems(self._worker):
            if not worker.is_connected and worker.is_active:
                lost, _ = self._worker[shard].release()
                lost_operations += lost

        return lost_operations
