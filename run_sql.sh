#!/usr/bin/env bash
# Execute a .sql file statement-by-statement via the Databricks Statement Execution API.
# Statements are split on ";" at end-of-line. No semicolons inside string literals in our SQL.
# Usage: ./run_sql.sh sql/00_schema_and_vocab.sql
set -euo pipefail

PROFILE="pulse-azure"
WAREHOUSE_ID="148ccb90800933a1"
FILE="$1"

# Split file into statements on ';' followed by newline; strip comments-only chunks.
python3 - "$FILE" <<'PY' | while IFS= read -r -d $'\0' stmt; do
import sys, re
sql = open(sys.argv[1]).read()
# remove /* */ block comments and -- line comments
sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.S)
sql = re.sub(r'--[^\n]*', '', sql)
parts = [s.strip() for s in sql.split(';')]
for p in parts:
    if p:
        sys.stdout.write(p + '\0')
PY
  # show first line of statement for progress
  first=$(printf '%s' "$stmt" | head -1 | cut -c1-90)
  printf '>> %s\n' "$first"
  resp=$(databricks api post /api/2.0/sql/statements --profile "$PROFILE" --json "$(python3 -c 'import json,sys; print(json.dumps({"warehouse_id":sys.argv[1],"statement":sys.argv[2],"wait_timeout":"50s"}))' "$WAREHOUSE_ID" "$stmt")")
  state=$(printf '%s' "$resp" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("status",{}).get("state","?"))')
  if [ "$state" != "SUCCEEDED" ]; then
    echo "   STATE=$state"
    printf '%s' "$resp" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("   ERROR:", d.get("status",{}).get("error",{}).get("message","")[:500])'
    exit 1
  fi
done
echo "ALL STATEMENTS SUCCEEDED: $FILE"
