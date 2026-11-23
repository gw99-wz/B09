#!/bin/bash
export CUDA_VISIBLE_DEVICES=0
python train.py --config config.yaml --seed 42 --batch_size 64
python eval.py --checkpoint best.pt --split test
