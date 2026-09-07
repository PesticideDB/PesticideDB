#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAMBA_DIR="$ROOT_DIR/.render-micromamba"
BIOENV_DIR="$ROOT_DIR/.render-bioenv"
BIN_DIR="$ROOT_DIR/bin"
MICROMAMBA="$MAMBA_DIR/bin/micromamba"

mkdir -p "$MAMBA_DIR" "$BIN_DIR"

if [[ ! -x "$MICROMAMBA" ]]; then
  echo "Installing micromamba for Render bioinformatics tools..."
  curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest \
    | tar -xvj -C "$MAMBA_DIR" bin/micromamba
fi

if [[ ! -x "$BIOENV_DIR/bin/diamond" || ! -x "$BIOENV_DIR/bin/hmmscan" || ! -x "$BIOENV_DIR/bin/prodigal" ]]; then
  echo "Installing DIAMOND, HMMER, and Prodigal..."
  "$MICROMAMBA" create -y -p "$BIOENV_DIR" \
    -c conda-forge -c bioconda \
    diamond hmmer prodigal
fi

ln -sf "$BIOENV_DIR/bin/diamond" "$BIN_DIR/diamond"
ln -sf "$BIOENV_DIR/bin/hmmscan" "$BIN_DIR/hmmscan"
ln -sf "$BIOENV_DIR/bin/prodigal" "$BIN_DIR/prodigal"

"$BIN_DIR/diamond" version
"$BIN_DIR/hmmscan" -h >/dev/null
"$BIN_DIR/prodigal" -v >/dev/null 2>&1 || true

echo "Render bioinformatics tools are installed in $BIN_DIR."
