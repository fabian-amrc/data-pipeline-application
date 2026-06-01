#!/usr/bin/env bash
set -euo pipefail

DEFAULTS_FILE="/opt/bitnami/spark/conf.default/spark-defaults.conf"
ORIGINAL_ENTRYPOINT="/opt/bitnami/scripts/spark/entrypoint.sh"

merge_spark_properties() {
  local properties_file="$1"

  if [ ! -f "${DEFAULTS_FILE}" ] || [ ! -f "${properties_file}" ]; then
    return 0
  fi

  local merged_file
  merged_file="$(mktemp /tmp/spark-properties.XXXXXX)"

  awk '
    FNR == NR {
      line = $0
      sub(/^[[:space:]]+/, "", line)
      if (line == "" || line ~ /^#/) next
      split(line, parts, /[[:space:]=]+/)
      if (parts[1] != "") provided[parts[1]] = 1
      next
    }
    {
      line = $0
      sub(/^[[:space:]]+/, "", line)
      if (line == "" || line ~ /^#/) {
        print $0
        next
      }
      split(line, parts, /[[:space:]=]+/)
      if (parts[1] == "" || !(parts[1] in provided)) print $0
    }
  ' "${properties_file}" "${DEFAULTS_FILE}" > "${merged_file}"

  cat "${properties_file}" >> "${merged_file}"
  printf '%s' "${merged_file}"
}

if [ "$#" -gt 0 ] && [ "$1" = "driver" ]; then
  args=("$@")
  for i in "${!args[@]}"; do
    if [ "${args[$i]}" = "--properties-file" ] && [ $((i + 1)) -lt "${#args[@]}" ]; then
      merged_properties="$(merge_spark_properties "${args[$((i + 1))]}")"
      if [ -n "${merged_properties:-}" ]; then
        args[$((i + 1))]="${merged_properties}"
      fi
      break
    fi
  done
  exec "${ORIGINAL_ENTRYPOINT}" "${args[@]}"
fi

exec "${ORIGINAL_ENTRYPOINT}" "$@"
