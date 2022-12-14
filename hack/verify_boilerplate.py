#!/usr/bin/env python

# +skip_license_check

# Copyright 2015 The Kubernetes Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Verifies that all source files contain the necessary copyright boilerplate
# snippet.

from __future__ import print_function

import argparse
import datetime
import glob
import os
import re
import sys


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "filenames", help="list of files to check, all files if unspecified", nargs='*')

    rootdir = f"{os.path.dirname(__file__)}/../"
    rootdir = os.path.abspath(rootdir)
    parser.add_argument("--rootdir", default=rootdir,
                        help="root directory to examine")

    default_boilerplate_dir = os.path.join(rootdir, "hack/boilerplate")
    parser.add_argument("--boilerplate-dir", default=default_boilerplate_dir)
    return parser.parse_args()


def get_refs():
    refs = {}

    for path in glob.glob(os.path.join(ARGS.boilerplate_dir, "boilerplate.*.txt")):
        extension = os.path.basename(path).split(".")[1]

        with open(path, 'r', encoding="utf-8") as ref_file:
            ref = ref_file.read().splitlines()
        refs[extension] = ref

    return refs


def file_passes(filename, refs, regexs):  # pylint: disable=too-many-locals
    try:
        with open(filename, 'r', encoding="utf-8") as fp:
            data = fp.read()
    except IOError:
        return False

    if "zz_generate" in filename:
        # Skip all zz_generate files
        return True

    basename = os.path.basename(filename)
    extension = file_extension(filename)
    ref = refs[extension] if extension != "" else refs[basename]
    # remove build tags from the top of Go files
    if extension == "go":
        con = regexs["go_build_constraints"]
        (data, found) = con.subn("", data, 1)

    # remove shebang from the top of shell files
    if extension in ["sh", "py"]:
        she = regexs["shebang"]
        (data, found) = she.subn("", data, 1)

    data = data.splitlines()

    # if our test file is smaller than the reference it surely fails!
    if len(ref) > len(data):
        return False

    # trim our file to the same number of lines as the reference file
    data = data[:len(ref)]

    year = regexs["year"]
    for datum in data:
        if year.search(datum):
            return False

    # Replace all occurrences of the regex "2017|2016|2015|2014" with "YEAR"
    when = regexs["date"]
    for idx, datum in enumerate(data):
        (data[idx], found) = when.subn('YEAR', datum)
        if found != 0:
            break

    # if we don't match the reference at this point, fail
    return ref == data


def file_extension(filename):
    return os.path.splitext(filename)[1].split(".")[-1].lower()


SKIPPED_DIRS = [
    'Godeps', 'third_party', '_gopath', '_output',
    'external', '.git', 'vendor', '__init__.py',
    'node_modules', 'bin'
]

# even when generated by bazel we will complain about some generated files
# not having the headers. since they're just generated, ignore them
IGNORE_HEADERS = [
    '// Code generated by',
    '// +skip_license_check',
    '# +skip_license_check',
]


def has_ignored_header(pathname):
    with open(pathname, 'r', encoding="utf-8") as myfile:
        try:
            data = myfile.read()
        except Exception as e:
            # read() can fail if, e.g., the script tries to read a binary file;
            # we could handle UnicodeDecodeError but if the script is recursing
            # into a folder with binaries we probably want to know about it
            # so print the name of the failed file and fail loudly
            print("failed to read", pathname)
            raise

        for header in IGNORE_HEADERS:
            if header in data:
                return True
    return False


def normalize_files(files):
    newfiles = [
        pathname
        for pathname in files
        if all(x not in pathname for x in SKIPPED_DIRS)
    ]
    for idx, pathname in enumerate(newfiles):
        if not os.path.isabs(pathname):
            newfiles[idx] = os.path.join(ARGS.rootdir, pathname)
    return newfiles


def get_files(extensions):
    files = []
    if ARGS.filenames:
        files = ARGS.filenames
    else:
        for root, dirs, walkfiles in os.walk(ARGS.rootdir):
            # don't visit certain dirs. This is just a performance improvement
            # as we would prune these later in normalize_files(). But doing it
            # cuts down the amount of filesystem walking we do and cuts down
            # the size of the file list
            for dpath in SKIPPED_DIRS:
                if dpath in dirs:
                    dirs.remove(dpath)

            for name in walkfiles:
                pathname = os.path.join(root, name)
                files.append(pathname)

    files = normalize_files(files)
    outfiles = []
    for pathname in files:
        basename = os.path.basename(pathname)
        extension = file_extension(pathname)
        if (
            extension in extensions or basename in extensions
        ) and not has_ignored_header(pathname):
            outfiles.append(pathname)
    return outfiles

def get_dates():
    years = datetime.datetime.now().year
    return f"({'|'.join(str(year) for year in range(2014, years + 1))})"

def get_regexs():
    regexs = {"year": re.compile('YEAR')}
    # dates can be 2014, 2015, 2016 or 2017, company holder names can be anything
    regexs["date"] = re.compile(get_dates())
    # strip the following build constraints/tags:
    # //go:build
    # // +build \n\n
    regexs["go_build_constraints"] = re.compile(
        r"^(//(go:build| \+build).*\n)+\n", re.MULTILINE)
    # strip #!.* from shell/python scripts
    regexs["shebang"] = re.compile(r"^(#!.*\n)\n*", re.MULTILINE)
    return regexs


def main():
    regexs = get_regexs()
    refs = get_refs()
    filenames = get_files(refs.keys())
    if nonconforming_files := [
        filename
        for filename in filenames
        if not file_passes(filename, refs, regexs)
    ]:
        print('%d files have incorrect boilerplate headers:' %
              len(nonconforming_files))
        for filename in sorted(nonconforming_files):
            print(os.path.relpath(filename, ARGS.rootdir))
        sys.exit(1)


if __name__ == "__main__":
    ARGS = get_args()
    main()
