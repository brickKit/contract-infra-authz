from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ShardStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SHARD_STATUS_UNSPECIFIED: _ClassVar[ShardStatus]
    SHARD_STATUS_UNCHANGED: _ClassVar[ShardStatus]
    SHARD_STATUS_CHANGED: _ClassVar[ShardStatus]
    SHARD_STATUS_CLOSED: _ClassVar[ShardStatus]

class SubmitStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SUBMIT_STATUS_UNSPECIFIED: _ClassVar[SubmitStatus]
    SUBMIT_STATUS_ACCEPTED: _ClassVar[SubmitStatus]
    SUBMIT_STATUS_REJECTED: _ClassVar[SubmitStatus]
SHARD_STATUS_UNSPECIFIED: ShardStatus
SHARD_STATUS_UNCHANGED: ShardStatus
SHARD_STATUS_CHANGED: ShardStatus
SHARD_STATUS_CLOSED: ShardStatus
SUBMIT_STATUS_UNSPECIFIED: SubmitStatus
SUBMIT_STATUS_ACCEPTED: SubmitStatus
SUBMIT_STATUS_REJECTED: SubmitStatus

class RevisionRef(_message.Message):
    __slots__ = ("domain", "value", "epoch", "instance")
    DOMAIN_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    EPOCH_FIELD_NUMBER: _ClassVar[int]
    INSTANCE_FIELD_NUMBER: _ClassVar[int]
    domain: str
    value: str
    epoch: str
    instance: str
    def __init__(self, domain: _Optional[str] = ..., value: _Optional[str] = ..., epoch: _Optional[str] = ..., instance: _Optional[str] = ...) -> None: ...

class HeldShard(_message.Message):
    __slots__ = ("shard", "digest")
    SHARD_FIELD_NUMBER: _ClassVar[int]
    DIGEST_FIELD_NUMBER: _ClassVar[int]
    shard: str
    digest: str
    def __init__(self, shard: _Optional[str] = ..., digest: _Optional[str] = ...) -> None: ...

class VerifyRequest(_message.Message):
    __slots__ = ("component", "held", "nonce")
    COMPONENT_FIELD_NUMBER: _ClassVar[int]
    HELD_FIELD_NUMBER: _ClassVar[int]
    NONCE_FIELD_NUMBER: _ClassVar[int]
    component: str
    held: _containers.RepeatedCompositeFieldContainer[HeldShard]
    nonce: str
    def __init__(self, component: _Optional[str] = ..., held: _Optional[_Iterable[_Union[HeldShard, _Mapping]]] = ..., nonce: _Optional[str] = ...) -> None: ...

class ShardAnswer(_message.Message):
    __slots__ = ("shard", "status", "view", "digest")
    SHARD_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    VIEW_FIELD_NUMBER: _ClassVar[int]
    DIGEST_FIELD_NUMBER: _ClassVar[int]
    shard: str
    status: ShardStatus
    view: bytes
    digest: str
    def __init__(self, shard: _Optional[str] = ..., status: _Optional[_Union[ShardStatus, str]] = ..., view: _Optional[bytes] = ..., digest: _Optional[str] = ...) -> None: ...

class VerifyResponse(_message.Message):
    __slots__ = ("nonce", "computed_at", "instance", "recovery_generation", "shards")
    NONCE_FIELD_NUMBER: _ClassVar[int]
    COMPUTED_AT_FIELD_NUMBER: _ClassVar[int]
    INSTANCE_FIELD_NUMBER: _ClassVar[int]
    RECOVERY_GENERATION_FIELD_NUMBER: _ClassVar[int]
    SHARDS_FIELD_NUMBER: _ClassVar[int]
    nonce: str
    computed_at: str
    instance: str
    recovery_generation: RevisionRef
    shards: _containers.RepeatedCompositeFieldContainer[ShardAnswer]
    def __init__(self, nonce: _Optional[str] = ..., computed_at: _Optional[str] = ..., instance: _Optional[str] = ..., recovery_generation: _Optional[_Union[RevisionRef, _Mapping]] = ..., shards: _Optional[_Iterable[_Union[ShardAnswer, _Mapping]]] = ...) -> None: ...

class Definition(_message.Message):
    __slots__ = ("record", "digest")
    RECORD_FIELD_NUMBER: _ClassVar[int]
    DIGEST_FIELD_NUMBER: _ClassVar[int]
    record: bytes
    digest: str
    def __init__(self, record: _Optional[bytes] = ..., digest: _Optional[str] = ...) -> None: ...

class SubmitRequest(_message.Message):
    __slots__ = ("component", "version", "definitions")
    COMPONENT_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    DEFINITIONS_FIELD_NUMBER: _ClassVar[int]
    component: str
    version: str
    definitions: _containers.RepeatedCompositeFieldContainer[Definition]
    def __init__(self, component: _Optional[str] = ..., version: _Optional[str] = ..., definitions: _Optional[_Iterable[_Union[Definition, _Mapping]]] = ...) -> None: ...

class Rejection(_message.Message):
    __slots__ = ("digest", "reason", "detail")
    DIGEST_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    DETAIL_FIELD_NUMBER: _ClassVar[int]
    digest: str
    reason: str
    detail: str
    def __init__(self, digest: _Optional[str] = ..., reason: _Optional[str] = ..., detail: _Optional[str] = ...) -> None: ...

class SubmitResponse(_message.Message):
    __slots__ = ("status", "set_digest", "rejections")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    SET_DIGEST_FIELD_NUMBER: _ClassVar[int]
    REJECTIONS_FIELD_NUMBER: _ClassVar[int]
    status: SubmitStatus
    set_digest: str
    rejections: _containers.RepeatedCompositeFieldContainer[Rejection]
    def __init__(self, status: _Optional[_Union[SubmitStatus, str]] = ..., set_digest: _Optional[str] = ..., rejections: _Optional[_Iterable[_Union[Rejection, _Mapping]]] = ...) -> None: ...
