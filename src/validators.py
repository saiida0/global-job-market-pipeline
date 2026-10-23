class ValidationError(ValueError):
    """Raised when API input cannot be safely converted."""


def _type_name(value) -> str:
    return type(value).__name__


def validate_string(value, field_name: str, allow_empty: bool = False) -> str | None:
    if value is None:
        if allow_empty:
            return None
        raise ValidationError(f"{field_name} must be a non-empty string, got None.")

    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValidationError(
            f"{field_name} must be string-compatible, got {_type_name(value)}: {value!r}"
        )

    text = str(value).strip()
    if not text:
        if allow_empty:
            return None
        raise ValidationError(f"{field_name} must be a non-empty string, got empty.")
    return text


def validate_list(value, field_name: str, item_type=str) -> list:
    if value is None:
        return []
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        raise ValidationError(
            f"{field_name} must be list or string, got {_type_name(value)}: {value!r}"
        )

    clean_items = []
    for item in items:
        if not isinstance(item, item_type):
            continue
        if item_type is str:
            item = item.strip()
            if not item:
                continue
        clean_items.append(item)
    return clean_items


def validate_int(value, field_name: str, min_val: int | None = None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValidationError(f"{field_name} must be int-compatible, got bool: {value!r}")

    try:
        int_value = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            f"{field_name} must be int-compatible, got {_type_name(value)}: {value!r}"
        ) from exc

    if min_val is not None and int_value < min_val:
        raise ValidationError(
            f"{field_name} must be >= {min_val}, got {int_value}: {value!r}"
        )
    return int_value
