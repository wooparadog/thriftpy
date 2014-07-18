# -*- coding: utf-8 -*-

"""
    thriftpy.thrift
    ~~~~~~~~~~~~~~~~~~

    Thrift simplified.
"""

import functools

from ._compat import init_func_generator, with_metaclass


def args2kwargs(thrift_spec, *args):
    arg_names = [item[1][1] for item in sorted(thrift_spec.items())]
    return dict(zip(arg_names, args))


class TType(object):
    STOP = 0
    VOID = 1
    BOOL = 2
    BYTE = 3
    I08 = 3
    DOUBLE = 4
    I16 = 6
    I32 = 8
    I64 = 10
    STRING = 11
    UTF7 = 11
    BINARY = 11  # This here just for parsing. For all purposes, it's a string
    STRUCT = 12
    MAP = 13
    SET = 14
    LIST = 15
    UTF8 = 16
    UTF16 = 17

    _VALUES_TO_NAMES = {
        STOP: 'STOP',
        VOID: 'VOID',
        BOOL: 'BOOL',
        BYTE: 'BYTE',
        I08: 'BYTE',
        DOUBLE: 'DOUBLE',
        I16: 'I16',
        I32: 'I32',
        I64: 'I64',
        STRING: 'STRING',
        UTF7: 'STRING',
        BINARY: 'STRING',
        STRUCT: 'STRUCT',
        MAP: 'MAP',
        SET: 'SET',
        LIST: 'LIST',
        UTF8: 'UTF8',
        UTF16: 'UTF16'
    }


class TMessageType(object):
    CALL = 1
    REPLY = 2
    EXCEPTION = 3
    ONEWAY = 4


class TPayloadMeta(type):
    def __new__(cls, name, bases, attrs):
        if "default_spec" in attrs:
            attrs["__init__"] = init_func_generator(attrs["default_spec"])
            attrs.pop('default_spec')
        return super(TPayloadMeta, cls).__new__(cls, name, bases, attrs)


class TPayload(with_metaclass(TPayloadMeta, object)):

    def read(self, iprot):
        iprot.read_struct(self)

    def write(self, oprot):
        oprot.write_struct(self)

    def __repr__(self):
        l = ['%s=%r' % (key, value) for key, value in self.__dict__.items()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(l))

    def __str__(self):
        return repr(self)

    def __eq__(self, other):
        return isinstance(other, self.__class__) and \
            self.__dict__ == other.__dict__

    def __ne__(self, other):
        return self != other


class TClient(object):
    def __init__(self, service, iprot, oprot=None):
        self._service = service
        self._iprot = self._oprot = iprot
        if oprot is not None:
            self._oprot = oprot
        self._seqid = 0
        self.last_call_meta = ""

    def __getattr__(self, api):
        if api in self._service.thrift_services:
            return functools.partial(self._req, api)

    def __dir__(self):
        return self._service.thrift_services

    def _req(self, api, *args, **kwargs):
        _kw = args2kwargs(getattr(self._service, api + "_args").thrift_spec,
                          *args)
        kwargs.update(_kw)
        self._send(api, **kwargs)
        return self._recv(api)

    def _send(self, api, **kwargs):
        self._oprot.write_message_begin(api, TMessageType.CALL, self._seqid)
        args = getattr(self._service, api + "_args")()
        for k, v in kwargs.items():
            setattr(args, k, v)
        args.write(self._oprot)
        self._oprot.write_message_end()
        self._oprot.trans.flush()

    def _recv(self, api):
        fname, mtype, rseqid, version, meta = self._iprot.read_message_begin()
        self.last_call_meta = meta

        if mtype == TMessageType.EXCEPTION:
            x = TApplicationException()
            x.read(self._iprot)
            self._iprot.read_message_end()
            raise x
        result = getattr(self._service, api + "_result")()
        result.read(self._iprot)
        self._iprot.read_message_end()

        if not hasattr(result, "success"):
            return

        if result.success is not None:
            return result.success

        # check throws
        for k, v in result.__dict__.items():
            if k != "success" and v is not None:
                raise v

        raise TApplicationException(TApplicationException.MISSING_RESULT)


def default_meta_builder(api, **kwards):
    return "[%s] - %s" % (api, kwards)


class TProcessor(object):
    """Base class for procsessor, which works on two streams."""

    def __init__(self, service, handler):
        self._service = service
        self._handler = handler

    def process(self, iprot, oprot):
        api, type, seqid, version, meta = iprot.read_message_begin()
        oprot.target_version = version
        if api not in self._service.thrift_services:
            iprot.skip(TType.STRUCT)
            iprot.read_message_end()
            exc = TApplicationException(TApplicationException.UNKNOWN_METHOD)
            oprot.write_message_begin(api, TMessageType.EXCEPTION, seqid)
            exc.write(oprot)

        else:
            args = getattr(self._service, api + "_args")()
            args.read(iprot)
            iprot.read_message_end()
            result = getattr(self._service, api + "_result")()
            try:
                result.success = getattr(self._handler, api)(**args.__dict__)
            except Exception as e:
                # raise if api don't have throws
                if len(result.thrift_spec) == 1:
                    raise

                # check throws
                cached = False
                for k in sorted(result.thrift_spec)[1:]:
                    _, exc_name, exc_cls = result.thrift_spec[k]
                    if isinstance(e, exc_cls):
                        setattr(result, exc_name, e)
                        cached = True
                        break

                # if exc not defined in throws, raise
                if not cached:
                    raise

            thrift_meta = getattr(
                self._handler, 'build_thrift_meta', default_meta_builder
                )(api, **args.__dict__)

            oprot.write_message_begin(api, TMessageType.REPLY, seqid,
                                      thrift_meta)
            result.write(oprot)

        oprot.write_message_end()
        oprot.trans.flush()


class TException(TPayload, Exception):
    """Base class for all thrift exceptions."""


class TApplicationException(TException):
    """Application level thrift exceptions."""

    thrift_spec = {
        1: (TType.STRING, 'message'),
        2: (TType.I32, 'type'),
    }

    UNKNOWN = 0
    UNKNOWN_METHOD = 1
    INVALID_MESSAGE_TYPE = 2
    WRONG_METHOD_NAME = 3
    BAD_SEQUENCE_ID = 4
    MISSING_RESULT = 5
    INTERNAL_ERROR = 6
    PROTOCOL_ERROR = 7

    def __init__(self, type=UNKNOWN, message=None):
        super(TApplicationException, self).__init__()
        self.type = type
        self.message = message

    def __str__(self):
        if self.message:
            return self.message

        if self.type == self.UNKNOWN_METHOD:
            return 'Unknown method'
        elif self.type == self.INVALID_MESSAGE_TYPE:
            return 'Invalid message type'
        elif self.type == self.WRONG_METHOD_NAME:
            return 'Wrong method name'
        elif self.type == self.BAD_SEQUENCE_ID:
            return 'Bad sequence ID'
        elif self.type == self.MISSING_RESULT:
            return 'Missing result'
        else:
            return 'Default (unknown) TApplicationException'
