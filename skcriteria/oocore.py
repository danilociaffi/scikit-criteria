#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2016-2017, Cabral, Juan; Luczywo, Nadia
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:

# * Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.

# * Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.

# * Neither the name of the copyright holder nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.


# =============================================================================
# IMPORTS
# =============================================================================

from __future__ import unicode_literals

import sys
import abc
import operator
import uuid
from collections import Mapping

import six

import numpy as np

from tabulate import tabulate

from . import util, norm


# =============================================================================
# CONSTANTS
# =============================================================================

CRITERIA_AS_ATR = {
    util.MIN: "min",
    util.MAX: "max"
}

TABULATE_PARAMS = {
    "headers": "firstrow",
    "numalign": "center",
    "stralign": "center",
}


# =============================================================================
# DATA PROXY
# =============================================================================

class Data(object):

    def __init__(self, mtx, criteria, weights=None, anames=None, cnames=None):
        self._mtx = np.asarray(mtx)
        self._criteria = util.criteriarr(criteria)
        self._weights = np.asarray(weights) if weights is not None else None
        util.validate_data(self._mtx, self._criteria, self._weights)

        self._anames = (
            anames if anames is not None else
            ["A{}".format(idx) for idx in range(len(mtx))])
        if len(self._anames) != len(self._mtx):
            msg = "{} names given for {} alternatives".format(
                len(self._anames), len(self._mtx))
            raise util.DataValidationError(msg)

        self._cnames = (
            cnames if cnames is not None else
            ["C{}".format(idx) for idx in range(len(criteria))])
        if len(self._cnames) != len(self._criteria):
            msg = "{} names for given {} criteria".format(
                len(self._cnames), len(self._criteria))
            raise util.DataValidationError(msg)

    def _iter_rows(self):
        direction = map(CRITERIA_AS_ATR.get, self._criteria)
        title = ["ALT./CRIT."]
        if self._weights is None:
            cstr = zip(self._cnames, direction)
            criteria = ["{} ({})".format(n, c) for n, c in cstr]
        else:
            cstr = zip(self._cnames, direction, self._weights)
            criteria = ["{} ({}) W.{}".format(n, c, w) for n, c, w in cstr]
        yield title + criteria

        for an, row in zip(self._anames, self._mtx):
            yield [an] + list(row)

    def __eq__(self, obj):
        return (
            isinstance(obj, Data) and
            util.iter_equal(self._mtx, obj._mtx) and
            util.iter_equal(self._criteria, obj._criteria) and
            util.iter_equal(self._weights, obj._weights))

    def __ne__(self, obj):
        return not self == obj

    def __unicode__(self):
        return self.to_str()

    def __bytes__(self):
        encoding = sys.getdefaultencoding()
        return self.__unicode__().encode(encoding, 'replace')

    def __str__(self):
        """Return a string representation for a particular Object

        Invoked by str(df) in both py2/py3.
        Yields Bytestring in Py2, Unicode String in py3.
        """
        if six.PY3:
            return self.__unicode__()
        return self.__bytes__()

    def __repr__(self):
        return str(self)

    def _repr_html_(self):
        return self.to_str(tablefmt="html")

    def to_str(self, **params):
        params.update({
            k: v for k, v in TABULATE_PARAMS.items() if k not in params})
        rows = self._iter_rows()
        return tabulate(rows, **params)

    @property
    def anames(self):
        return tuple(self._anames)

    @property
    def cnames(self):
        return tuple(self._cnames)

    @property
    def mtx(self):
        return self._mtx

    @property
    def criteria(self):
        return self._criteria

    @property
    def weights(self):
        return self._weights


# =============================================================================
# DECISION MAKER
# =============================================================================

@six.add_metaclass(abc.ABCMeta)
class Manipulator(object):

    def __repr__(self):
        cls_name = type(self).__name__
        data = sorted(self.as_dict().items())
        data = ", ".join(
            "{}={}".format(k, v) for k, v in data)
        return "<{} ({})>".format(cls_name, data)


    def decide(self, data, criteria=None, weights=None):
        if isinstance(data, Data):
            if criteria or weights:
                msg = (
                    "If 'data' is instance of Data, 'criteria' and 'weights' "
                    "must be empty")
                raise ValueError(msg)
            anames, cnames = data.anames, data.cnames
            mtx, criteria, weights = data.mtx, data.criteria, data.weights
        else:
            if criteria is None:
                msg = (
                    "If 'data' is not instance of Data you must provide a "
                    "'criteria' array")
                raise ValueError(msg)
            anames, cnames, mtx = None, None, data
            util.validate_data(mtx, criteria, weights)
        nmtx, ncriteria, nweights = self.normalize(mtx, criteria, weights)
        kernel, rank, extra = self.solve(
            nmtx=nmtx, ncriteria=ncriteria, nweights=nweights)
        decision = self.make_decision(
            mtx=mtx, criteria=criteria, weights=weights,
            kernel=kernel, rank=rank, extra=extra,
            anames=anames, cnames=cnames)
        return decision

    @abc.abstractmethod
    def process(self, nmtx, ncriteria, nweights):
        return NotImplemented