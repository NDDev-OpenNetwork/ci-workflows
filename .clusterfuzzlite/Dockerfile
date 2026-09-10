# Pinned by digest, like every other dependency here. OSS-Fuzz publishes
# base-builder:v1 as a rolling tag and expects projects to track it, so this
# trades automatic base updates for a reproducible fuzzing image -- the same
# trade this repository already makes for actions and downloads. Refresh with
# the digest the registry reports for :v1, never one copied from a message:
#   curl -sSI https://gcr.io/v2/oss-fuzz-base/base-builder/manifests/v1 \
#     -H 'Accept: application/vnd.docker.distribution.manifest.v2+json'
FROM gcr.io/oss-fuzz-base/base-builder:v1@sha256:8b4a73d83374b298a0a771eeec9a1d44ceff3416a678b7d7946303389d022aca
COPY . $SRC/ci-workflows
WORKDIR $SRC/ci-workflows
COPY .clusterfuzzlite/build.sh $SRC/
