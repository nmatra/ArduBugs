#!/usr/bin/env python3
from typing import List
from enum import Enum
from pprint import pprint as pp
import re
import git
import os
import operator


# buckets:
# { copter, rover, plane, sub, gcs, libraries, sitl, tools }


CATEGORY_MAPPING = {
    'apmrover2': 'rover',
    'apmrover': 'rover',
    'copte': 'copter',
    'rangefilnder': 'rangefinder',
    'ardcucopter': 'copter',
    'doc': 'docs',
    'documentation': 'docs',
    'simulator': 'sitl'
}

# a list of categories that we're not interested in
DROP_CATEGORIES = [
    'waf',
    'cli',
    'github',
    'web',
    'docs',
    'travis',
    'ci',
    'build',
    'readme',
    'autotest',
    'desktop',
    'pysim'
]

REGEX_HIL = re.compile('\bhil\b')
REGEX_CATEGORY = re.compile("^\w+(?=:)")


class Package(Enum):
    copter = 'copter'
    rover = 'rover'
    plane = 'plane'
    sub = 'sub'
    gcs = 'gcs'
    library = 'library'
    sitl = 'sitl'
    tools = 'tools'


class BugFix(object):
    def __init__(self, commit: git.Commit, category: str) -> None:
        self.__commit = commit
        self.__category = category
        self.__description = commit.message.partition(':')[2].strip()

    
    @property
    def hex8(self) -> str:
        return self.id[:8]


    @property
    def id(self) -> str:
        return str(self.commit)


    @property
    def commit(self) -> git.Commit:
        return self.__commit


    @property
    def category(self) -> str:
        return self.__category


    @property
    def description(self) -> str:
        return self.__description

    
    @property
    def short_description(self) -> str:
        return self.description.partition('\n')[0]


def contains_any(string: str, substrings: List[str]) -> bool:
    for substring in substrings:
        if substring in string:
            return True
    return False


if __name__ == '__main__':
    if not os.path.exists('ardu'):
        print('cloning repo...')
        git.Repo.clone_from('https://github.com/ArduPilot/ArduPilot.git', 'ardu')

    repo = git.Repo('ardu')
    commits = list(repo.iter_commits())
    print("# commits: {}".format(len(commits)))

    bugs = []
    categories = {}
    for c in commits:
        msg = c.message.lower()

        # 1. must contain the term "bug" or "fix"
        if not contains_any(msg, ['bug', 'fix']):
            continue

        # 2. must not contain any of the terms:
        #       "build", "compile", "hil"
        if REGEX_HIL.match(msg):
            continue

        if contains_any(msg, ['build', 'compile', 'comment', 'indent-tabs-mode', 'fix example', 'spelling']):
            continue

        # determine the category name
        category = REGEX_CATEGORY.match(c.message)
        if not category: # ill-formed description; discard
            continue

        # normalise the category name
        category = category.group(0).lower()
        category = category.replace('ardu', '')
        category = category.replace('ap_', '')
        category = CATEGORY_MAPPING.get(category, category)

        # drop board-specific bugs
        if 'px4' in category:
            continue

        # discard categories that we're not interested in
        if category in DROP_CATEGORIES:
            continue
        
        # keep track of the number of commits belonging to each category
        if category not in categories:
            categories[category] = 1
        else:
            categories[category] += 1

        # construct a bug fix object
        fix = BugFix(c, category)

        # record the commit as a bug fix
        bugs.append(fix)
    
    categories = sorted(categories.items(), key=operator.itemgetter(1), reverse=True)
    pp(categories)
    print('# bug fixes: {}'.format(len(bugs)))
    for b in bugs:
         print("{}: {}".format(b.hex8, b.short_description))