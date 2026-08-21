#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 11 ]]; then
  echo 'usage: render-public-promotion-record.sh VERSION PUBLIC_REPOSITORY PUBLIC_COMMIT GENERATED_AT EXPIRES_AT CI_SOURCE CI_DIGEST CONTRACT_SOURCE CONTRACT_DIGEST SECURITY_SOURCE SECURITY_DIGEST' >&2
  exit 2
fi
version=$1 repository=$2 commit=$3 generated_at=$4 expires_at=$5
ci_source=$6 ci_digest=$7 contract_source=$8 contract_digest=$9
shift 9
security_source=$1 security_digest=$2

[[ ${version} =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]
[[ ${repository} =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]
[[ ${commit} =~ ^[0-9a-f]{40}$ ]]
[[ ${generated_at} =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
[[ ${expires_at} =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
for digest in "${ci_digest}" "${contract_digest}" "${security_digest}"; do
  [[ ${digest} =~ ^sha256:[0-9a-f]{64}$ ]]
done
for source in "${ci_source}" "${contract_source}" "${security_source}"; do
  [[ ${source} == https://github.com/${repository}/* ]]
done

jq -S -c -n \
  --arg schema nddev-public-release-promotion/v2 \
  --arg version "${version}" --arg public_repository "${repository}" \
  --arg public_commit "${commit}" --arg generated_at "${generated_at}" --arg expires_at "${expires_at}" \
  --arg ci_source "${ci_source}" --arg ci_digest "${ci_digest}" \
  --arg contract_source "${contract_source}" --arg contract_digest "${contract_digest}" \
  --arg security_source "${security_source}" --arg security_digest "${security_digest}" \
  '{schema:$schema,version:$version,public_repository:$public_repository,public_commit:$public_commit,
    generated_at:$generated_at,expires_at:$expires_at,evidence:[
      {role:"public-ci",result:"success",public_commit:$public_commit,observed_at:$generated_at,source:$ci_source,digest:$ci_digest},
      {role:"public-contract",result:"success",public_commit:$public_commit,observed_at:$generated_at,source:$contract_source,digest:$contract_digest},
      {role:"public-security",result:"success",public_commit:$public_commit,observed_at:$generated_at,source:$security_source,digest:$security_digest}
    ]}'
