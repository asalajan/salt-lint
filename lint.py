# -*- coding: utf-8 -*-
'''
Lint states and sls files
'''
from __future__ import absolute_import

# Import python libs
import logging
from types import NoneType
from collections import OrderedDict
import re
from voluptuous import *
from inspect import getargspec
import importlib

# Import salt libs
import salt.config
import salt.utils
import salt.state
import salt.payload
from salt.ext.six import string_types
from salt.exceptions import SaltInvocationError

__outputter__ = {
    'validate_sls': 'highstate',
}

log = logging.getLogger(__name__)

def _getschema(state):

    # Get argspec for state. Return False is not available.
    (module, function) = state.split('.')
    try:
        package = importlib.import_module("salt.states.%s" % module)
    except:
        return False

    try:
        argspec = getargspec(getattr(package, function))
    except e:
      return False

    # Default schema for common functions
    schema = {
        'context': OrderedDict,
        'defaults': OrderedDict,
        'name': Coerce(str),
        'names': list,
        'check_cmd': str,
        'listen': list,
        'listen_in': list,
        'onchanges': list,
        'onchanges_in': list,
        'onfail': list,
        'onfail_in': list,
        'onlyif': Coerce(str),
        'order': int,
        'prereq': list,
        'prereq_in': list,
        'require': list,
        'require_in': list,
        'unless': Coerce(str),
        'use': list,
        'watch': list,
        'watch_in': list,
        'formatter': str
    }

    # Identify arguments and default value. Add to schema dict inheriting
    # type from default value. If no default value, assume string.
    for idx, arg in enumerate(argspec.args):
        if arg not in schema:
            try:
                default = argspec.defaults[idx]
            except:
                default = 'nodefault'
            if type(default) == bool:
                stype = bool
            elif type(default) == NoneType:
                stype = Coerce(str)
            else:
                stype = Coerce(type(default))
            schema[arg] = stype

    return Schema(schema)

def validate_sls(mods, saltenv='base', test=None, queue=False, env=None, **kwargs):

    schema = {}
    ret = {}
    errors = []
    data = __salt__['state.show_sls'](mods, saltenv, test, queue, env, kwargs=kwargs)
    prog = re.compile(r'.*\.')

    # iterate over ids
    for id, resource in data.items():

        # iterate over states
        for module, args in resource.items():

            # Ignore dunder dicts
            if module in ['__sls__', '__env__']:
                continue

            # find state name, i.e. cmd.run
            match = prog.match(module)
            if match:
                state = module
            else:
                state = "%s.%s" % (module, args.pop(0))

            # add state to schema, and check state is valid
            if state not in schema:
                schema[state] =  _getschema(state)
                if schema[state] == False:
                  ret.append("%s: %s not part of schema" % (file, state))
                  continue

            # iterate over arguments to make sure they're valid according to our schema
            for arg in args:
                try:
                    schema[state](arg)
                except Exception as e:
                    errors.append("%s %s: Got %s for %s but %s" % (id, state, arg.itervalues().next(), arg.iterkeys().next(), e.msg))
                ret[id] = { state: { 'result': True } }

    if len(errors) > 0:
       __context__['retcode'] = 1
       return errors
    return ret
