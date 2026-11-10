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

class AccountChangeVerdict(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ACCOUNT_CHANGE_VERDICT_UNSPECIFIED: _ClassVar[AccountChangeVerdict]
    ACCOUNT_CHANGE_VERDICT_ALLOWED: _ClassVar[AccountChangeVerdict]
    ACCOUNT_CHANGE_VERDICT_CONFIRMATION_REQUIRED: _ClassVar[AccountChangeVerdict]
    ACCOUNT_CHANGE_VERDICT_REFUSED: _ClassVar[AccountChangeVerdict]
    ACCOUNT_CHANGE_VERDICT_UNPROVABLE: _ClassVar[AccountChangeVerdict]
SHARD_STATUS_UNSPECIFIED: ShardStatus
SHARD_STATUS_UNCHANGED: ShardStatus
SHARD_STATUS_CHANGED: ShardStatus
SHARD_STATUS_CLOSED: ShardStatus
SUBMIT_STATUS_UNSPECIFIED: SubmitStatus
SUBMIT_STATUS_ACCEPTED: SubmitStatus
SUBMIT_STATUS_REJECTED: SubmitStatus
ACCOUNT_CHANGE_VERDICT_UNSPECIFIED: AccountChangeVerdict
ACCOUNT_CHANGE_VERDICT_ALLOWED: AccountChangeVerdict
ACCOUNT_CHANGE_VERDICT_CONFIRMATION_REQUIRED: AccountChangeVerdict
ACCOUNT_CHANGE_VERDICT_REFUSED: AccountChangeVerdict
ACCOUNT_CHANGE_VERDICT_UNPROVABLE: AccountChangeVerdict

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
    __slots__ = ("shard", "status", "view", "digest", "read_only")
    SHARD_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    VIEW_FIELD_NUMBER: _ClassVar[int]
    DIGEST_FIELD_NUMBER: _ClassVar[int]
    READ_ONLY_FIELD_NUMBER: _ClassVar[int]
    shard: str
    status: ShardStatus
    view: bytes
    digest: str
    read_only: bool
    def __init__(self, shard: _Optional[str] = ..., status: _Optional[_Union[ShardStatus, str]] = ..., view: _Optional[bytes] = ..., digest: _Optional[str] = ..., read_only: _Optional[bool] = ...) -> None: ...

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

class CheckAccountChangeRequest(_message.Message):
    __slots__ = ("account", "target_state", "security_version", "requester", "confirmation", "second_person")
    ACCOUNT_FIELD_NUMBER: _ClassVar[int]
    TARGET_STATE_FIELD_NUMBER: _ClassVar[int]
    SECURITY_VERSION_FIELD_NUMBER: _ClassVar[int]
    REQUESTER_FIELD_NUMBER: _ClassVar[int]
    CONFIRMATION_FIELD_NUMBER: _ClassVar[int]
    SECOND_PERSON_FIELD_NUMBER: _ClassVar[int]
    account: str
    target_state: str
    security_version: int
    requester: str
    confirmation: str
    second_person: bool
    def __init__(self, account: _Optional[str] = ..., target_state: _Optional[str] = ..., security_version: _Optional[int] = ..., requester: _Optional[str] = ..., confirmation: _Optional[str] = ..., second_person: _Optional[bool] = ...) -> None: ...

class CheckAccountChangeResponse(_message.Message):
    __slots__ = ("verdict", "reason", "administrator")
    VERDICT_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    ADMINISTRATOR_FIELD_NUMBER: _ClassVar[int]
    verdict: AccountChangeVerdict
    reason: str
    administrator: bool
    def __init__(self, verdict: _Optional[_Union[AccountChangeVerdict, str]] = ..., reason: _Optional[str] = ..., administrator: _Optional[bool] = ...) -> None: ...

class CheckLinkChangeRequest(_message.Message):
    __slots__ = ("employee", "account", "action", "employee_version", "requester", "confirmation")
    EMPLOYEE_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    EMPLOYEE_VERSION_FIELD_NUMBER: _ClassVar[int]
    REQUESTER_FIELD_NUMBER: _ClassVar[int]
    CONFIRMATION_FIELD_NUMBER: _ClassVar[int]
    employee: str
    account: str
    action: str
    employee_version: int
    requester: str
    confirmation: str
    def __init__(self, employee: _Optional[str] = ..., account: _Optional[str] = ..., action: _Optional[str] = ..., employee_version: _Optional[int] = ..., requester: _Optional[str] = ..., confirmation: _Optional[str] = ...) -> None: ...

class CheckLinkChangeResponse(_message.Message):
    __slots__ = ("verdict", "reason")
    VERDICT_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    verdict: AccountChangeVerdict
    reason: str
    def __init__(self, verdict: _Optional[_Union[AccountChangeVerdict, str]] = ..., reason: _Optional[str] = ...) -> None: ...

class AdministratorsRequest(_message.Message):
    __slots__ = ("accounts",)
    ACCOUNTS_FIELD_NUMBER: _ClassVar[int]
    accounts: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, accounts: _Optional[_Iterable[str]] = ...) -> None: ...

class AdministratorsResponse(_message.Message):
    __slots__ = ("administrators",)
    ADMINISTRATORS_FIELD_NUMBER: _ClassVar[int]
    administrators: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, administrators: _Optional[_Iterable[str]] = ...) -> None: ...

class SourcesRequest(_message.Message):
    __slots__ = ("since",)
    SINCE_FIELD_NUMBER: _ClassVar[int]
    since: str
    def __init__(self, since: _Optional[str] = ...) -> None: ...

class SourceState(_message.Message):
    __slots__ = ("component", "stream", "state", "applied")
    COMPONENT_FIELD_NUMBER: _ClassVar[int]
    STREAM_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    APPLIED_FIELD_NUMBER: _ClassVar[int]
    component: str
    stream: str
    state: str
    applied: bool
    def __init__(self, component: _Optional[str] = ..., stream: _Optional[str] = ..., state: _Optional[str] = ..., applied: _Optional[bool] = ...) -> None: ...

class SourcesResponse(_message.Message):
    __slots__ = ("as_of", "sources", "all_applied")
    AS_OF_FIELD_NUMBER: _ClassVar[int]
    SOURCES_FIELD_NUMBER: _ClassVar[int]
    ALL_APPLIED_FIELD_NUMBER: _ClassVar[int]
    as_of: str
    sources: _containers.RepeatedCompositeFieldContainer[SourceState]
    all_applied: bool
    def __init__(self, as_of: _Optional[str] = ..., sources: _Optional[_Iterable[_Union[SourceState, _Mapping]]] = ..., all_applied: _Optional[bool] = ...) -> None: ...

class ReplayDeferredRequest(_message.Message):
    __slots__ = ("record", "recovery")
    RECORD_FIELD_NUMBER: _ClassVar[int]
    RECOVERY_FIELD_NUMBER: _ClassVar[int]
    record: bytes
    recovery: str
    def __init__(self, record: _Optional[bytes] = ..., recovery: _Optional[str] = ...) -> None: ...

class ReplayDeferredResponse(_message.Message):
    __slots__ = ("outcome", "detail")
    OUTCOME_FIELD_NUMBER: _ClassVar[int]
    DETAIL_FIELD_NUMBER: _ClassVar[int]
    outcome: str
    detail: str
    def __init__(self, outcome: _Optional[str] = ..., detail: _Optional[str] = ...) -> None: ...

class CheckRequest(_message.Message):
    __slots__ = ("recovery", "review_subjects")
    RECOVERY_FIELD_NUMBER: _ClassVar[int]
    REVIEW_SUBJECTS_FIELD_NUMBER: _ClassVar[int]
    recovery: str
    review_subjects: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, recovery: _Optional[str] = ..., review_subjects: _Optional[_Iterable[str]] = ...) -> None: ...

class CheckResponse(_message.Message):
    __slots__ = ("admin_state", "ended", "held", "review", "closed", "admins_not_closed", "unprovable")
    ADMIN_STATE_FIELD_NUMBER: _ClassVar[int]
    ENDED_FIELD_NUMBER: _ClassVar[int]
    HELD_FIELD_NUMBER: _ClassVar[int]
    REVIEW_FIELD_NUMBER: _ClassVar[int]
    CLOSED_FIELD_NUMBER: _ClassVar[int]
    ADMINS_NOT_CLOSED_FIELD_NUMBER: _ClassVar[int]
    UNPROVABLE_FIELD_NUMBER: _ClassVar[int]
    admin_state: str
    ended: int
    held: int
    review: int
    closed: _containers.RepeatedScalarFieldContainer[str]
    admins_not_closed: _containers.RepeatedScalarFieldContainer[str]
    unprovable: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, admin_state: _Optional[str] = ..., ended: _Optional[int] = ..., held: _Optional[int] = ..., review: _Optional[int] = ..., closed: _Optional[_Iterable[str]] = ..., admins_not_closed: _Optional[_Iterable[str]] = ..., unprovable: _Optional[_Iterable[str]] = ...) -> None: ...
