#!/bin/bash
# Add local Berkeley ABC to PATH
export PATH="$(pwd)/../abc:$PATH"

# Add local Yosys (from OSS CAD Suite) to PATH
export PATH="$(pwd)/../oss-cad-suite/bin:$PATH"

# Add local Kissat build to PATH
export PATH="$(pwd)/../kissat/build:$PATH"

echo "Yosys, ABC, and Kissat are ready."

