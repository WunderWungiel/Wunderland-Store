import re

def generate_pages(page, total_pages):

    return {
        'current': page,
        'next': page + 1 if page < total_pages else None,
        'previous': page - 1 if page > 1 else None,
        'total': total_pages
    }

def to_version(symbian_version):
    match = re.match(r"(\d+)\.(\d+)\((\d+)\)", symbian_version)
    if not match:
        print(symbian_version)
        raise ValueError("Invalid Symbian version format")
    
    major, minor, patch = match.groups()
    if len(minor) == 2 and minor.startswith("0"):
        minor = minor[1]

    return f"{major}.{minor}.{patch}"

def to_symbian_version(version):
    parts = version.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid version format")

    major, minor, patch = parts

    if len(minor) < 2:
        minor = minor.zfill(2)

    return f"{major}.{minor}({patch})"
