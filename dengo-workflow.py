import numpy as np
import matplotlib.pyplot as plt
import yaml
import jinja2
import os
import utilities
import logging
import subprocess
import sys
from EnzoWorkFlow import EnzoWorkFlow

MPI_CORE = 32
MUSIC_CONFIG = "init.music"
ENZO_CONFIG  = "music_input.enzo"

class dengo_workflow(EnzoWorkFlow):

    def __init__(self, config_file="dmonly.yaml"):
        super().__init__(config_file)
        self.MPI_CORE = MPI_CORE

    def set_environment_variables(self):
        paths = self.config["paths"]
        for envVar, path in paths.items():
            os.environ[envVar] = path

    def write_dengo_network(self):
        self.set_environment_variables()

        dengo_config = self.config["dengo_configs"]
        conserved = dengo_config["enforce_conservation"]
        eq_species = dengo_config["equilibrium_species"]
        pN = utilities.setup_primordial_network(enforce_conservation = conserved,
                                                equilibrium_species = eq_species)
        utilities.write_network(pN, solver_options= dengo_config)

    def build_dengo_network(self):
        dengo_config = self.config["dengo_configs"]
        self.write_dengo_network()
        os.chdir(dengo_config["output_dir"])
        self.run_subprocess(["make"], outfile="build_dengo.out")
        os.chdir("../")



if __name__ == "__main__":
    config_file = sys.argv[1]
    workflow = dengo_workflow(config_file = config_file)
    workflow.run_music()
    workflow.build_dengo_network()
    workflow.run_enzo()
