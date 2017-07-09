#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2015-2016 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2017 Peyman Jabbarzade Ganje <peyman.jabarzade@gmail.com>
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

"""Communication-related handlers for CWS.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from cms import config

import logging
import requests

import tornado.web

from cms.db import Question
from cms.server import multi_contest

from .contest import ContestHandler, NOTIFICATION_ERROR, NOTIFICATION_SUCCESS


logger = logging.getLogger(__name__)


def send_mail(subject, message, recipients):
    Sender = "{} <{}>".format(config.email_sender, config.email_address)
    SMTP_Server = config.email_server
    SMTP_User = config.email_username
    SMTP_Pass = config.email_password

    if isinstance(recipients, str):
        recipients = [recipients]

    text_subtype = 'html'
    msg = MIMEMultipart()
    msg['From'] = Sender
    msg['To'] = ",".join(recipients)
    msg['Subject'] = subject

    msg.attach(MIMEText(message, text_subtype))
    mailserver = smtplib.SMTP(SMTP_Server, 587)
    mailserver.ehlo()
    # secure email with tls encryption
    mailserver.starttls()
    # re-identify as an encrypted connection
    mailserver.ehlo()
    mailserver.login(SMTP_User, SMTP_Pass)
    mailserver.sendmail(Sender, recipients, msg.as_string())
    mailserver.quit()
    logger.info('Email sent to %s', ",".join(recipients))


class CommunicationHandler(ContestHandler):
    """Displays the private conversations between the logged in user
    and the contest managers..

    """
    @tornado.web.authenticated
    @multi_contest
    def get(self):
        self.set_secure_cookie(self.contest.name + "_unread_count", "0")
        self.render("communication.html", **self.r_params)


class QuestionHandler(ContestHandler):
    """Called when the user submits a question.

    """
    @tornado.web.authenticated
    @multi_contest
    def post(self):
        participation = self.current_user

        # User can post only if we want.
        if not self.contest.allow_questions:
            raise tornado.web.HTTPError(404)

        fallback_page = self.contest_url("communication")

        subject_length = len(self.get_argument("question_subject", ""))
        text_length = len(self.get_argument("question_text", ""))
        if subject_length > 50 or text_length > 2000:
            logger.warning("Long question (%d, %d) dropped for user %s.",
                           subject_length, text_length,
                           self.current_user.user.username)
            self.application.service.add_notification(
                self.current_user.user.username,
                self.timestamp,
                self._("Question too big!"),
                self._("You have reached the question length limit."),
                NOTIFICATION_ERROR)
            self.redirect(fallback_page)
            return

        question = Question(self.timestamp,
                            self.get_argument("question_subject", ""),
                            self.get_argument("question_text", ""),
                            participation=participation)
        self.sql_session.add(question)
        self.sql_session.commit()

        logger.info(
            "Question submitted by user %s.", participation.user.username)

        if config.email_notification:
            send_mail('New Question Received', 'Please Check CMS.',
                      config.email_notification)

        # Add "All ok" notification.
        self.application.service.add_notification(
            participation.user.username,
            self.timestamp,
            self._("Question received"),
            self._("Your question has been received, you will be "
                   "notified when it is answered."),
            NOTIFICATION_SUCCESS)

        self.redirect(fallback_page)


class CallHandler(ContestHandler):
    """Called when the user Call staff.

    """
    @tornado.web.authenticated
    @multi_contest
    def get(self):
        self.set_secure_cookie(self.contest.name + "_unread_count", "0")
        self.render("call_a_staff.html", **self.r_params)

    def post(self):
        # User can post only if we want.
        if not self.contest.allow_questions:
            raise tornado.web.HTTPError(404)

        participation = self.current_user
        fallback_page = self.url("callstaff")
        request_type = self.get_argument("request_type", "")

        try:
            if not config.print_system_address:
                raise Exception("Print System Address not set!")
            response = requests.post(
                '%s/cms_request' % config.print_system_address,
                data={
                    'request_message': request_type,
                    'ip': str(participation.ip)
                }
            )
            response.raise_for_status()
        except Exception as e:
            self.application.service.add_notification(
                participation.user.username,
                self.timestamp,
                self._("System failed"),
                self._("The system has failed to deliver your request. "
                       "Please raise your hand for contacting staffs."),
                NOTIFICATION_ERROR)
            logger.error(e, exc_info=e)
        else:
            self.application.service.add_notification(
                participation.user.username,
                self.timestamp,
                self._("Request received"),
                self._("Your request has been received "
                       "and staffs have been informed. Please wait "
                       "until a staff reaches you for further guidance."),
                NOTIFICATION_SUCCESS)

        self.redirect(fallback_page)
