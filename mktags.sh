#!/bin/sh
set -xve
while read -r line; do
  tag -a $line
done < "$1"
