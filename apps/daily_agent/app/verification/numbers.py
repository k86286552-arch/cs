from __future__ import annotations


def verify_numbers(resource_rows: list[dict]) -> list[str]:
    issues: list[str] = []

    for i, row in enumerate(resource_rows):
        label = f"Resource row {i + 1} ({row.get('category', '?')})"

        tonnage = row.get("ore_tonnage")
        if tonnage is not None:
            if tonnage <= 0:
                issues.append(f"{label}: ore_tonnage must be positive, got {tonnage}")
            if tonnage > 100000:
                issues.append(f"{label}: ore_tonnage {tonnage} Mt seems unrealistically large")

        grade = row.get("grade")
        if grade is not None:
            if grade <= 0:
                issues.append(f"{label}: grade must be positive, got {grade}")
            if grade > 100:
                issues.append(f"{label}: grade {grade} seems unrealistically high")

        contained = row.get("contained_metal")
        if contained is not None and contained < 0:
            issues.append(f"{label}: contained_metal must be non-negative, got {contained}")

    return issues
