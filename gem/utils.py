from __future__ import absolute_import, print_function, division

import collections
import numpy
from singledispatch import singledispatch
from gem.node import traversal
from gem.gem import (Terminal, Product, Sum, Comparison, Conditional,
                     Division, Indexed, FlexiblyIndexed, IndexSum, ListTensor,
                     MathFunction, LogicalAnd, LogicalNot, LogicalOr,
                     Constant, Variable, Power)


# This is copied from PyOP2, and it is here to be available for both
# FInAT and TSFC without depending on PyOP2.
class cached_property(object):
    """A read-only @property that is only evaluated once. The value is cached
    on the object itself rather than the function or class; this should prevent
    memory leakage."""
    def __init__(self, fget, doc=None):
        self.fget = fget
        self.__doc__ = doc or fget.__doc__
        self.__name__ = fget.__name__
        self.__module__ = fget.__module__

    def __get__(self, obj, cls):
        if obj is None:
            return self
        obj.__dict__[self.__name__] = result = self.fget(obj)
        return result


class OrderedSet(collections.MutableSet):
    """A set that preserves ordering, useful for deterministic code
    generation."""

    def __init__(self, iterable=None):
        self._list = list()
        self._set = set()

        if iterable is not None:
            for item in iterable:
                self.add(item)

    def __contains__(self, item):
        return item in self._set

    def __iter__(self):
        return iter(self._list)

    def __len__(self):
        return len(self._list)

    def __repr__(self):
        return "OrderedSet({0})".format(self._list)

    def add(self, value):
        if value not in self._set:
            self._list.append(value)
            self._set.add(value)

    def discard(self, value):
        # O(n) time complexity: do not use this!
        if value in self._set:
            self._list.remove(value)
            self._set.discard(value)


def make_proxy_class(name, cls):
    """Constructs a proxy class for a given class.  Instance attributes
    are supposed to be listed e.g. with the unset_attribute decorator,
    so that this function find them and create wrappers for them.

    :arg name: name of the new proxy class
    :arg cls: the wrapee class to create a proxy for
    """
    def __init__(self, wrapee):
        self._wrapee = wrapee

    def make_proxy_property(name):
        def getter(self):
            return getattr(self._wrapee, name)
        return property(getter)

    dct = {'__init__': __init__}
    for attr in dir(cls):
        if not attr.startswith('_'):
            dct[attr] = make_proxy_property(attr)
    return type(name, (), dct)


@singledispatch
def count_flop_node(node):
    """Count number of flops at a particular gem node, without recursing
    into childrens"""
    raise AssertionError("cannot handle type %s" % type(node))


@count_flop_node.register(Constant)
@count_flop_node.register(Terminal)
@count_flop_node.register(Indexed)
@count_flop_node.register(Variable)
@count_flop_node.register(ListTensor)
@count_flop_node.register(FlexiblyIndexed)
@count_flop_node.register(LogicalNot)
@count_flop_node.register(LogicalAnd)
@count_flop_node.register(LogicalOr)
@count_flop_node.register(Conditional)
def count_flop_node_zero(node):
    return 0


@count_flop_node.register(Power)
@count_flop_node.register(Comparison)
@count_flop_node.register(Sum)
@count_flop_node.register(Product)
@count_flop_node.register(Division)
@count_flop_node.register(MathFunction)
def count_flop_node_single(node):
    return numpy.prod([idx.extent for idx in node.free_indices])


@count_flop_node.register(IndexSum)
def count_flop_node_index_sum(node):
    return numpy.prod([idx.extent for idx in node.multiindex + node.free_indices])


def count_flop(node):
    """
    Count the total floating point operations required to compute a gem node.
    This function assumes that all subnodes that occur more than once induce a
    temporary, and are therefore only computed once.
    """
    return sum(map(count_flop_node, traversal([node])))
