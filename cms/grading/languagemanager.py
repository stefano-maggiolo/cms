#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Provide utilities to work with programming language classes."""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from cms import plugin_list


__all__ = [
    "LANGUAGES",
    "HEADER_EXTS", "SOURCE_EXTS", "OBJECT_EXTS",
    "get_language", "filename_to_language",
    "filename_to_language_names"
]


LANGUAGES = []
_BY_NAME = dict()
HEADER_EXTS = set()
OBJECT_EXTS = set()
SOURCE_EXTS = set()


def get_language(name):
    """Return the language object corresponding to the given name.

    name (unicode): name of the requested language.
    return (Language): language object.

    raise (KeyError): if the name does not correspond to a language.

    """
    if name not in _BY_NAME:
        raise KeyError("Language `%s' not supported." % name)
    return _BY_NAME[name]


def filename_to_language(filename):
    """Return one of the languages inferred from the given filename.

    filename (string): the file to test.

    return (Language|None): one (arbitrary, but deterministic)
        language matching the given filename, or None if none
        match.

    """
    names = filename_to_language_names(filename)
    return None if len(names) == 0 else get_language(names[0])


def filename_to_language_names(filename):
    """Return all of the languages inferred from the given filename.

    filename (string): the file to test.

    return (string): name of all languages matching the given filename
    """
    ext_index = filename.rfind(".")
    if ext_index == -1:
        return []
    ext = filename[ext_index:]
    names = sorted([language.name
                    for language in LANGUAGES
                    if ext in language.source_extensions])
    return names


def _load_languages():
    """Load the available languages and fills all other data structures."""
    global LANGUAGES, _BY_NAME, HEADER_EXTS, OBJECT_EXTS, SOURCE_EXTS
    if LANGUAGES != []:
        return

    LANGUAGES = [
        language()
        for language in plugin_list("cms.grading.languages", "languages")
    ]
    _BY_NAME = dict(
        (language.name, language) for language in LANGUAGES)
    for lang in LANGUAGES:
        HEADER_EXTS |= set(lang.header_extensions)
        OBJECT_EXTS |= set(lang.object_extensions)
        SOURCE_EXTS |= set(lang.source_extensions)


# Initialize!
_load_languages()
