"""
Compatibility layer that uses native Pydantic v2 / BeautifulSoup4 / httpx when installed,
and falls back cleanly to Python 3.11+ standard library implementations when running
in an environment before `pip install -r requirements.txt` is executed.
"""

from __future__ import annotations

import copy
import json
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, get_type_hints

try:
    from pydantic import (
        BaseModel,
        ConfigDict,
        Field,
        ValidationError,
        field_validator,
        model_validator,
    )

    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False

    class ValidationError(ValueError):
        """Fallback ValidationError matching Pydantic v2 semantics."""

        def __init__(self, errors: List[Dict[str, Any]], model_name: str = "Model"):
            self. _errors = errors
            self.model_name = model_name
            msg = f"{len(errors)} validation error(s) for {model_name}: " + "; ".join(
                f"{e.get('loc')}: {e.get('msg')}" for e in errors
            )
            super().__init__(msg)

        def errors(self) -> List[Dict[str, Any]]:
            return self._errors

    def ConfigDict(**kwargs: Any) -> Dict[str, Any]:
        return dict(kwargs)

    class _FieldInfo:
        def __init__(
            self,
            default: Any = ...,
            default_factory: Optional[Callable[[], Any]] = None,
            description: str = "",
            ge: Optional[float] = None,
            gt: Optional[float] = None,
            le: Optional[float] = None,
            lt: Optional[float] = None,
            min_length: Optional[int] = None,
            max_length: Optional[int] = None,
            **kwargs: Any,
        ):
            self.default = default
            self.default_factory = default_factory
            self.description = description
            self.ge = ge
            self.gt = gt
            self.le = le
            self.lt = lt
            self.min_length = min_length
            self.max_length = max_length
            self.extra = kwargs

    def Field(
        default: Any = ...,
        *,
        default_factory: Optional[Callable[[], Any]] = None,
        description: str = "",
        ge: Optional[float] = None,
        gt: Optional[float] = None,
        le: Optional[float] = None,
        lt: Optional[float] = None,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        **kwargs: Any,
    ) -> Any:
        return _FieldInfo(
            default=default,
            default_factory=default_factory,
            description=description,
            ge=ge,
            gt=gt,
            le=le,
            lt=lt,
            min_length=min_length,
            max_length=max_length,
            **kwargs,
        )

    def field_validator(*fields: str, mode: str = "after") -> Callable[[ Any], Any]:
        def decorator(fn: Any) -> Any:
            raw_fn = fn.__func__ if isinstance(fn, classmethod) else fn
            raw_fn.__field_validator_info__ = (fields, mode)
            return classmethod(raw_fn)

        return decorator

    def model_validator(*, mode: str = "after") -> Callable[[Any], Any]:
        def decorator(fn: Any) -> Any:
            raw_fn = fn.__func__ if isinstance(fn, classmethod) else fn
            raw_fn.__model_validator_info__ = mode
            return raw_fn

        return decorator

    class BaseModel:
        """Lightweight Pydantic v2-compatible BaseModel for zero-install execution."""

        model_config: Dict[str, Any] = {}

        def __init__(self, **data: Any):
            cls = self.__class__
            errors: List[Dict[str, Any]] = []

            # Collect field definitions across MRO
            field_defs: Dict[str, Any] = {}
            annotations: Dict[str, Any] = {}
            field_validators_before: Dict[str, List[Callable[..., Any]]] = {}
            field_validators_after: Dict[str, List[Callable[..., Any]]] = {}
            model_validators_after: List[Callable[..., Any]] = []

            for base in reversed(cls.__mro__):
                if base is object or base is BaseModel:
                    continue
                base_ann = getattr(base, "__annotations__", {})
                for k, v in base_ann.items():
                    if not k.startswith("_") and k != "model_config":
                        annotations[k] = v
                        if hasattr(base, k):
                            field_defs[k] = getattr(base, k)
                for attr_name, attr_val in base.__dict__.items():
                    raw_fn = attr_val.__func__ if isinstance(attr_val, classmethod) else attr_val
                    if hasattr(raw_fn, "__field_validator_info__"):
                        v_fields, v_mode = raw_fn.__field_validator_info__
                        target = (
                            field_validators_before
                            if v_mode == "before"
                            else field_validators_after
                        )
                        for f_name in v_fields:
                            target.setdefault(f_name, []).append(raw_fn)
                    elif hasattr(raw_fn, "__model_validator_info__"):
                        model_validators_after.append(raw_fn)

            values: Dict[str, Any] = {}
            for field_name in annotations:
                f_info = field_defs.get(field_name, ...)
                if field_name in data:
                    val = data[field_name]
                elif isinstance(f_info, _FieldInfo):
                    if f_info.default_factory is not None:
                        val = f_info.default_factory()
                    elif f_info.default is not ...:
                        val = copy.deepcopy(f_info.default)
                    else:
                        errors.append(
                            {"loc": (field_name,), "msg": "Field required", "type": "missing"}
                        )
                        continue
                elif f_info is not ...:
                    val = copy.deepcopy(f_info)
                else:
                    errors.append(
                        {"loc": (field_name,), "msg": "Field required", "type": "missing"}
                    )
                    continue

                # Run 'before' field validators
                for v_fn in field_validators_before.get(field_name, []):
                    try:
                        val = v_fn(cls, val)
                    except Exception as exc:
                        errors.append(
                            {"loc": (field_name,), "msg": str(exc), "type": "value_error"}
                        )

                # Strip strings if configured (preserve str Enum instances)
                if (
                    isinstance(val, str)
                    and not isinstance(val, Enum)
                    and cls.model_config.get("str_strip_whitespace")
                ):
                    val = val.strip()

                # Constraint checks from Field()
                if isinstance(f_info, _FieldInfo) and val is not None:
                    if isinstance(val, (int, float)):
                        if f_info.ge is not None and val < f_info.ge:
                            errors.append(
                                {
                                    "loc": (field_name,),
                                    "msg": f"Input should be >= {f_info.ge}, got {val}",
                                    "type": "greater_than_equal",
                                }
                            )
                        if f_info.gt is not None and val <= f_info.gt:
                            errors.append(
                                {
                                    "loc": (field_name,),
                                    "msg": f"Input should be > {f_info.gt}, got {val}",
                                    "type": "greater_than",
                                }
                            )
                        if f_info.le is not None and val > f_info.le:
                            errors.append(
                                {
                                    "loc": (field_name,),
                                    "msg": f"Input should be <= {f_info.le}, got {val}",
                                    "type": "less_than_equal",
                                }
                            )
                        if f_info.lt is not None and val >= f_info.lt:
                            errors.append(
                                {
                                    "loc": (field_name,),
                                    "msg": f"Input should be < {f_info.lt}, got {val}",
                                    "type": "less_than",
                                }
                            )
                    if isinstance(val, str):
                        if f_info.min_length is not None and len(val) < f_info.min_length:
                            errors.append(
                                {
                                    "loc": (field_name,),
                                    "msg": f"String should have at least {f_info.min_length} characters",
                                    "type": "string_too_short",
                                }
                            )

                # Run 'after' field validators
                for v_fn in field_validators_after.get(field_name, []):
                    try:
                        val = v_fn(cls, val)
                    except Exception as exc:
                        errors.append(
                            {"loc": (field_name,), "msg": str(exc), "type": "value_error"}
                        )

                values[field_name] = val

            if errors:
                raise ValidationError(errors, model_name=cls.__name__)

            for k, v in values.items():
                object.__setattr__(self, k, v)

            # Run model validators
            for mv_fn in model_validators_after:
                try:
                    mv_fn(self)
                except Exception as exc:
                    raise ValidationError(
                        [{"loc": ("__root__",), "msg": str(exc), "type": "value_error"}],
                        model_name=cls.__name__,
                    ) from exc

        @classmethod
        def model_validate(cls: Type[Any], obj: Dict[str, Any]) -> Any:
            if isinstance(obj, cls):
                return obj
            return cls(**obj)

        def model_dump(self, mode: str = "python") -> Dict[str, Any]:
            result: Dict[str, Any] = {}
            for k, v in self.__dict__.items():
                if k.startswith("_"):
                    continue
                result[k] = self._serialize_val(v, mode=mode)
            return result

        @classmethod
        def _serialize_val(cls, val: Any, mode: str = "python") -> Any:
            if isinstance(val, BaseModel):
                return val.model_dump(mode=mode)
            if isinstance(val, Enum):
                return val.value if mode == "json" else val
            if isinstance(val, list):
                return [cls._serialize_val(item, mode=mode) for item in val]
            if isinstance(val, dict):
                return {k: cls._serialize_val(v, mode=mode) for k, v in val.items()}
            return val

        def model_dump_json(self, indent: Optional[int] = None) -> str:
            return json.dumps(self.model_dump(mode="json"), ensure_ascii=False, indent=indent)

        def __repr__(self) -> str:
            kv = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items() if not k.startswith("_"))
            return f"{self.__class__.__name__}({kv})"
