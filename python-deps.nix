# Single source of truth for the portal's Python runtime dependencies.
# Consumed as `import ./python-deps.nix python3Packages`, so the versioned
# package set stays with the caller.
ps:
with ps;
[
  fastapi
  uvicorn
  sqlalchemy
  pydantic
  python-multipart
  psycopg2
  websockets
  jsonschema
]
