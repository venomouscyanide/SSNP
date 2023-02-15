import argparse
import json
import os
import time
from pathlib import Path

import torch
from ray import tune
from ray.tune import CLIReporter, Stopper
from ray.tune.schedulers import ASHAScheduler
from torch_geometric import seed_everything

import GLASSTest


class TimeStopper(Stopper):
    def __init__(self):
        self._start = time.time()
        self._deadline = 60 * 30  # 30 minutes max run across all experiments

    def __call__(self, trial_id, result):
        return False

    def stop_all(self):
        return time.time() - self._start > self._deadline


class HyperParameterTuning:
    MAX_EPOCHS = 300
    CPUS_AVAIL = 1
    GPUS_AVAIL = 0
    NUM_SAMPLES = 1

    seed = 42

    CONFIG = {
        "m": tune.choice([1, 5, 10, 25, 50]),
        "M": tune.choice([1, 5, 10, 25, 50]),
        "samples": tune.choice([0.1, 0.25, 0.50, 0.75, 1.0]),
        "stochastic": tune.choice([True, False]),
        "diffusion": tune.choice([True, False]),
    }


class ComGraphArguments:
    def __init__(self, dataset):
        self.model = 2
        self.use_nodeid = True
        self.repeat = 1
        self.use_seed = True
        self.dataset = dataset
        self.use_deg = False
        self.use_one = False
        self.use_maxzeroone = False


def ray_tune_helper(identifier, output_path, dataset):
    hyper_class = HyperParameterTuning

    scheduler = ASHAScheduler(
        metric="val_accuracy",
        mode="max",
        max_t=hyper_class.MAX_EPOCHS,
        grace_period=1,
        reduction_factor=2)
    reporter = CLIReporter(metric_columns=["loss", "val_accuracy", "training_iteration"])
    base_args = ComGraphArguments(dataset)

    device = torch.device('cpu')
    print(f"Using device: {device} for running ray tune")

    seed_everything(42)

    result = tune.run(
        tune.with_parameters(GLASSTest.ray_tune_run_helper, argument_class=base_args),
        resources_per_trial={"cpu": hyper_class.CPUS_AVAIL, "gpu": hyper_class.GPUS_AVAIL},
        config=hyper_class.CONFIG,
        num_samples=hyper_class.NUM_SAMPLES,
        scheduler=scheduler,
        progress_reporter=reporter,
        local_dir=os.path.join(identifier, output_path),
        log_to_file=True,
        stop=TimeStopper(),
        resume="AUTO"
    )
    best_trial = result.get_best_trial("val_accuracy", "max", "last-10-avg")

    print("Best trial config: {}".format(best_trial))
    with open(f'{str(Path.home())}/{identifier}_best_result.json', "w") as file:
        json.dump(best_trial.config, file)

    print("Best trial final train loss: {}".format(best_trial.last_result["loss"]))
    print("Best trial final validation accuracy: {}".format(best_trial.last_result["val_accuracy"]))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--identifier', type=str, required=True)
    parser.add_argument('--output_path', type=str, required=True)
    parser.add_argument('--dataset', type=str, required=True)

    args = parser.parse_args()
    ray_tune_helper(args.identifier, args.output_path, args.dataset)
