#!/bin/bash
# Run visible and held-out split scoring over existing method outputs.

set -e

cd /home/user

bash scripts/evaluate_train.sh /home/user/checkpoints
bash scripts/evaluate_test.sh /home/user/checkpoints
