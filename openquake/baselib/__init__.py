# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2017 GEM Foundation
#
# OpenQuake is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OpenQuake. If not, see <http://www.gnu.org/licenses/>.

import os
import collections
from openquake.baselib.python3compat import configparser
from openquake.baselib.general import git_suffix

# the version is managed by packager.sh with a sed
__version__ = '2.7.0'
__version__ += git_suffix(__file__)

PATHS = ['~/openquake.cfg', '/etc/openquake/openquake.cfg']
cfg = os.environ.get('OQ_CONFIG_FILE_VAR')
if cfg:  # has the precedence
    PATHS.insert(0, cfg)


class DotDict(collections.OrderedDict):
    """A string-valued dictionary that can be accessed with the "." notation"""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

config = DotDict()  # global configuration


def _read(*paths, **validators):
    # load the configuration file by looking at the given paths
    paths = list(paths) + PATHS
    parser = configparser.SafeConfigParser()
    found = parser.read(os.path.normpath(os.path.expanduser(p)) for p in paths)
    if not found:
        raise IOError('No configuration file found in %s' % str(paths))
    config.clear()
    for section in parser.sections():
        config[section] = sec = DotDict(parser.items(section))
        for k, v in sec.items():
            sec[k] = validators.get(k, lambda x: x)(v)
config.read = _read
