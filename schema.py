from inspect import isclass

__version__ = '0.3.2.dev0'


class SchemaError(Exception):
    """Error during Schema validation."""

    def __init__(self, autos, errors):
        self.autos = autos if type(autos) is list else [autos]
        self.errors = errors if type(errors) is list else [errors]
        Exception.__init__(self, self.code)

    @property
    def code(self):
        def uniq(seq):
            seen = set()
            seen_add = seen.add
            # This way removes duplicates while preserving the order.
            return [x for x in seq if x not in seen and not seen_add(x)]

        a = uniq(i for i in self.autos if i is not None)
        e = uniq(i for i in self.errors if i is not None)
        if e:
            return '\n'.join(e)
        return '\n'.join(a)


def schema(schema_, error=None):
    flavor = priority(schema_)
    if flavor == ITERABLE:
        return Iterable(schema_, error)
    if flavor == DICT:
        return Dict(schema_, error)
    if flavor == TYPE:
        return Type(schema_, error)
    if flavor == VALIDATOR:
        return schema_
    if flavor == CALLABLE:
        return Callable(schema_, error)
    return Comparable(schema_, error)


COMPARABLE, CALLABLE, VALIDATOR, TYPE, DICT, ITERABLE = range(6)


def priority(s):
    """Return priority for a given object."""
    if type(s) in (list, tuple, set, frozenset):
        return ITERABLE
    if type(s) is dict:
        return DICT
    if isclass(s):
        return TYPE
    if hasattr(s, 'validate'):
        return VALIDATOR
    if callable(s):
        return CALLABLE
    else:
        return COMPARABLE


class Schema(object):
    pass


class And(Schema):
    def __init__(self, *args, **kw):
        self._error = kw.get('error')
        self._schemas = [schema(x, error=self._error) for x in args]
        self.priority = min(x.priority
                            for x in self._schemas) if self._schemas else ()

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ', '.join(repr(a) for a in self._schemas))

    def validate(self, data):
        for s in self._schemas:
            data = s.validate(data)
        return data


class Or(And):
    def validate(self, data):
        x = SchemaError([], [])
        for s in self._schemas:
            try:
                return s.validate(data)
            except SchemaError as _x:
                x = _x
        raise SchemaError(['%r did not validate %r' % (self, data)] + x.autos,
                          [self._error] + x.errors)


class Use(Schema):

    priority = (CALLABLE, )

    def __init__(self, callable_, error=None):
        assert callable(callable_)
        self._callable = callable_
        self._error = error

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           _callable_str(self._callable))

    def validate(self, data):
        try:
            return self._callable(data)
        except SchemaError as x:
            raise SchemaError([None] + x.autos, [self._error] + x.errors)
        except BaseException as x:
            raise SchemaError('%s(%r) raised %r' % (
                _callable_str(self._callable), data, x), self._error)


class Iterable(Schema):
    def __init__(self, iterable, error=None):
        self._type = schema(type(iterable), error)
        self._or = Or(*iterable, error=error)
        self.priority = (ITERABLE, ) + self._or.priority

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__,
                           self._type._type(self._or._schemas))

    def validate(self, data):
        data = self._type.validate(data)
        or_ = self._or
        return type(data)(or_.validate(d) for d in data)


class Dict(Schema):
    def __init__(self, dict_, error=None):
        self._error = error
        self._type = schema(type(dict_), error)
        self._items = sorted(((schema(k, error), schema(v, error))
                              for k, v in dict_.items()),
                             key=lambda tup: tup[0].priority)
        self.priority = (DICT, ) + (
            self._items[0][0].priority if self._items else ())

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self._items)

    def validate(self, data):
        data = self._type.validate(data)
        schema_items = self._items
        valid_data = type(data)()
        matched_schema_keys = set()

        for key, value in data.items():
            for skey, svalue in schema_items:
                try:
                    key = skey.validate(key)
                except SchemaError:
                    pass
                else:
                    valid_data[key] = svalue.validate(value)
                    matched_schema_keys.add(skey)
                    break

        # Apply default-having optionals that haven't been used:
        defaults = set(k for k, _ in schema_items
                       if isinstance(k, Optional) and hasattr(k, 'default'))
        for default in defaults - matched_schema_keys:
            valid_data[default.key] = default.default

        if len(valid_data) < len(data):
            wrong_keys = set(data.keys()) - set(valid_data.keys())
            s_wrong_keys = ', '.join(sorted(repr(k) for k in wrong_keys))
            raise SchemaError('Wrong keys %s in %r' % (s_wrong_keys, data),
                              self._error)

        required = set(k for k, _ in schema_items
                       if not isinstance(k, Optional))
        if not required.issubset(matched_schema_keys):
            missing_keys = required - matched_schema_keys
            s_missing_keys = ', '.join(sorted(repr(k) for k in missing_keys))
            raise SchemaError('Missing keys: ' + s_missing_keys, self._error)

        return valid_data


class Type(Schema):

    priority = (TYPE, )

    def __init__(self, type_, error=None):
        self._error = error
        self._type = type_

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, self._type.__name__)

    def validate(self, data):
        if isinstance(data, self._type):
            return data
        else:
            raise SchemaError('%r should be instance of %r' %
                              (data, self._type.__name__), self._error)


class Callable(Schema):

    priority = (CALLABLE, )

    def __init__(self, callable_, error=None):
        self._error = error
        self._callable = callable_

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__,
                           _callable_str(self._callable))

    def validate(self, data):
        try:
            if self._callable(data):
                return data
        except SchemaError as x:
            raise SchemaError([None] + x.autos, [self._error] + x.errors)
        except BaseException as x:
            raise SchemaError('%s(%r) raised %r' %
                              (_callable_str(self._callable), data, x),
                              self._error)
        else:
            raise SchemaError('%s(%r) should evaluate to True' %
                              (_callable_str(self._callable), data),
                              self._error)


class Comparable(Schema):

    priority = (COMPARABLE, )

    def __init__(self, object_, error=None):
        self._object = object_
        self._error = error

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self._object)

    def validate(self, data):
        if self._object == data:
            return data
        else:
            raise SchemaError('%r does not match %r' % (self._object, data),
                              self._error)


class Optional(Schema):
    """Marker for an optional part of Schema."""

    _marker = object()
    priority = (VALIDATOR, )

    def __init__(self, key, **kwargs):
        self._error = kwargs.get('error')
        default = kwargs.get('default', self._marker)
        if default is not self._marker:
            self.default = default
        self.key = schema(key)
        self.priority = (VALIDATOR, ) + self.key.priority

    def __repr__(self):
        default = (", default=%r" % (self.default, )
                   ) if hasattr(self, "default") else ""
        return "%s(%r%s)" % (self.__class__.__name__, self.key, default)

    def validate(self, data):
        return self.key.validate(data)


def _callable_str(callable_):
    if hasattr(callable_, '__name__'):
        return callable_.__name__
    return str(callable_)
