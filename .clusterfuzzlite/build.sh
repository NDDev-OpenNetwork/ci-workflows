#!/bin/bash -eu

"$CXX" $CXXFLAGS -std=c++17 \
  "$SRC/ci-workflows/tests/fixtures/fuzzing/checksum_fuzzer.cpp" \
  -o "$OUT/checksum_fuzzer" $LIB_FUZZING_ENGINE
