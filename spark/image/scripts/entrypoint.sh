#!/usr/bin/env bash
set -euo pipefail

DEFAULTS_FILE="/opt/bitnami/spark/conf.default/spark-defaults.conf"
ORIGINAL_ENTRYPOINT="/opt/bitnami/scripts/spark/entrypoint.sh"


load_minio_credentials() {
  local env_file="${MINIO_CONFIG_ENV_FILE:-/var/run/minio-tenant/config.env}"

  if [ -z "${env_file}" ] || [ ! -f "${env_file}" ]; then
    return 0
  fi

  local minio_user=""
  local minio_password=""
  while IFS= read -r line; do
    case "${line}" in
      export\ MINIO_ROOT_USER=*)
        minio_user="${line#export MINIO_ROOT_USER=}"
        ;;
      export\ MINIO_ROOT_PASSWORD=*)
        minio_password="${line#export MINIO_ROOT_PASSWORD=}"
        ;;
    esac
  done < "${env_file}"

  minio_user="${minio_user%\"}"
  minio_user="${minio_user#\"}"
  minio_password="${minio_password%\"}"
  minio_password="${minio_password#\"}"

  export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-${MINIO_ACCESS_KEY:-${minio_user}}}"
  export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-${MINIO_SECRET_KEY:-${minio_password}}}"
  export AWS_REGION="${AWS_REGION:-us-east-1}"
  export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"
}

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

load_minio_credentials

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
