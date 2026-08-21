#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 8 ]]; then
  echo 'usage: render-public-promotion-record.sh VERSION PUBLIC_REPOSITORY PUBLIC_COMMIT GENERATED_AT EXPIRES_AT CI_RUN_URL CONTRACT_JOB_URL SECURITY_RUN_URL' >&2
  exit 2
fi
version=$1 repository=$2 commit=$3 generated_at=$4 expires_at=$5
ci_source=$6 contract_source=$7 security_source=$8

[[ ${version} =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]
[[ ${repository} =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]
[[ ${commit} =~ ^[0-9a-f]{40}$ ]]
[[ ${generated_at} =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
[[ ${expires_at} =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
for source in "${ci_source}" "${contract_source}" "${security_source}"; do
  [[ ${source} == https://github.com/${repository}/actions/runs/* ]]
done
[[ ${ci_source} != "${contract_source}" && ${ci_source} != "${security_source}" && ${contract_source} != "${security_source}" ]]

command -v gh >/dev/null
command -v jq >/dev/null
command -v sha256sum >/dev/null

prefix="https://github.com/${repository}/actions/runs/"
ci_path=${ci_source#"${prefix}"}
contract_path=${contract_source#"${prefix}"}
security_path=${security_source#"${prefix}"}
[[ ${ci_path} =~ ^[1-9][0-9]*$ ]]
[[ ${contract_path} =~ ^([1-9][0-9]*)/job/([1-9][0-9]*)$ ]]
contract_job_id=${BASH_REMATCH[2]}
[[ ${security_path} =~ ^[1-9][0-9]*$ ]]

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/nddev-public-promotion.XXXXXX")
trap 'rm -rf -- "${work_dir}"' EXIT
chmod 700 "${work_dir}"
gh api "repos/${repository}/actions/runs/${ci_path}" >"${work_dir}/ci.json"
gh api "repos/${repository}/actions/jobs/${contract_job_id}" >"${work_dir}/contract.json"
gh api "repos/${repository}/actions/runs/${security_path}" >"${work_dir}/security.json"

jq -e --arg sha "${commit}" --arg url "${ci_source}" \
  '.status == "completed" and .conclusion == "success" and .head_sha == $sha and
   .html_url == $url and .event == "push" and .run_attempt == 1 and .name == "ci"' \
  "${work_dir}/ci.json" >/dev/null
jq -e --arg sha "${commit}" --arg url "${contract_source}" \
  '.status == "completed" and .conclusion == "success" and .head_sha == $sha and
   .html_url == $url and .name == "static validators"' \
  "${work_dir}/contract.json" >/dev/null
jq -e --arg sha "${commit}" --arg url "${security_source}" \
  '.status == "completed" and .conclusion == "success" and .head_sha == $sha and
   .html_url == $url and .event == "push" and .run_attempt == 1 and
   (.name == "codeql" or .name == "gitleaks" or .name == "scorecard")' \
  "${work_dir}/security.json" >/dev/null

jq -j -S -c '{conclusion,created_at,event,head_sha,html_url,id,name,run_attempt,status,updated_at,workflow_id}' \
  "${work_dir}/ci.json" >"${work_dir}/ci.canonical"
jq -j -S -c '{completed_at,conclusion,head_sha,html_url,id,name,run_id,started_at,status}' \
  "${work_dir}/contract.json" >"${work_dir}/contract.canonical"
jq -j -S -c '{conclusion,created_at,event,head_sha,html_url,id,name,run_attempt,status,updated_at,workflow_id}' \
  "${work_dir}/security.json" >"${work_dir}/security.canonical"

ci_digest="sha256:$(sha256sum "${work_dir}/ci.canonical" | cut -d' ' -f1)"
contract_digest="sha256:$(sha256sum "${work_dir}/contract.canonical" | cut -d' ' -f1)"
security_digest="sha256:$(sha256sum "${work_dir}/security.canonical" | cut -d' ' -f1)"
ci_observed_at=$(jq -er '.updated_at' "${work_dir}/ci.json")
contract_observed_at=$(jq -er '.completed_at' "${work_dir}/contract.json")
security_observed_at=$(jq -er '.updated_at' "${work_dir}/security.json")
[[ ${ci_digest} != "${contract_digest}" && ${ci_digest} != "${security_digest}" && ${contract_digest} != "${security_digest}" ]]

jq -S -c -n \
  --arg schema nddev-public-release-promotion/v2 \
  --arg version "${version}" --arg public_repository "${repository}" \
  --arg public_commit "${commit}" --arg generated_at "${generated_at}" --arg expires_at "${expires_at}" \
  --arg ci_source "${ci_source}" --arg ci_digest "${ci_digest}" \
  --arg ci_observed_at "${ci_observed_at}" \
  --arg contract_source "${contract_source}" --arg contract_digest "${contract_digest}" \
  --arg contract_observed_at "${contract_observed_at}" \
  --arg security_source "${security_source}" --arg security_digest "${security_digest}" \
  --arg security_observed_at "${security_observed_at}" \
  '{schema:$schema,version:$version,public_repository:$public_repository,public_commit:$public_commit,
    generated_at:$generated_at,expires_at:$expires_at,evidence:[
      {role:"public-ci",result:"success",public_commit:$public_commit,observed_at:$ci_observed_at,source:$ci_source,digest:$ci_digest},
      {role:"public-contract",result:"success",public_commit:$public_commit,observed_at:$contract_observed_at,source:$contract_source,digest:$contract_digest},
      {role:"public-security",result:"success",public_commit:$public_commit,observed_at:$security_observed_at,source:$security_source,digest:$security_digest}
    ]}'
