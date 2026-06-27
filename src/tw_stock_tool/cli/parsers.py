import argparse

def parse_int_tuple(value: str) -> tuple[int, ...]:
    if not value.strip():
        raise argparse.ArgumentTypeError("range cannot be empty")
    try:
        return tuple(int(x.strip()) for x in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid integer list: '{value}'") from exc
