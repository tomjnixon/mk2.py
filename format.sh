#!/usr/bin/env bash
cd $(dirname $0)

nixpkgs-fmt flake.nix mk2_py.nix

black -q mk2
isort -q mk2
flake8 mk2
mypy mk2
