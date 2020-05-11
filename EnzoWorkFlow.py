import numpy as np
import subprocess
import sys
import yaml
import yt
import os
import logging
import jinja2
from yt.analysis_modules.halo_analysis.api import HaloCatalog
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

MPI_CORE = 32
MUSIC_CONFIG = "init.music"
ENZO_CONFIG  = "music_input.enzo"

class EnzoWorkFlow:
    def __init__(self, config_file):
        self.config = self.parse_config(config_file)
        templateLoader = jinja2.FileSystemLoader(searchpath='./templates')
        self.templateEnv = jinja2.Environment(loader=templateLoader)
        self.test_dir = self.config["run_directory"]
        #logging.basicConfig(filename="logWorkFlow.log", level=logging.DEBUG)
        logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', filename='logWorkFlow.log')

    def parse_config(self, config_file):
        logging.info("Parsing Config File = {}".format(config_file))
        stream = open(config_file, 'r')
        data = yaml.load(stream, Loader=yaml.FullLoader)
        return data

    def write_music_configs(self):
        config = self.config["music_configs"]
        print(self.config["music_configs"]["random"])
        if config["setup"]["baryons"] == "no":
            self.baryons = False
        else:
            self.baryons = True
        logging.info("Write Music configurations = {}".format(config))
        with open(MUSIC_CONFIG, 'w') as f:
            for k, v in config.items():
                f.write("[{}]\n".format(k))
                for param, val in  v.items():
                    f.write("{0:10} = {1}\n".format(param, val))
            f.write( "filename = {0}".format(self.test_dir))

    def run_subprocess(self, commands, outfile=None):
        p = subprocess.run(commands, check=True, stdout=subprocess.PIPE,
                           universal_newlines=True)
        if outfile:
            with open(outfile, 'w') as f:
                f.write(p.stdout)

    def run_music(self):
        config = self.config
        music  = config["executables"]["music"]
        music_configs = self.write_music_configs()
        self.run_subprocess(["./"+music, MUSIC_CONFIG],
                            "run_music.out")
        music_out = ["input_powerspec.txt", "{0}".format(MUSIC_CONFIG), "{0}_log.txt".format(MUSIC_CONFIG)]
        self.run_subprocess(["mv", *music_out, self.test_dir])


    def write_enzo_config(self):
        config = self.config
        fenzo  = open(os.path.join(self.test_dir,ENZO_CONFIG), 'w')
        fmusic = open(os.path.join(self.test_dir, "parameter_file.txt"), "r")

        fenzo.write("# [Configurations from MUSIC]\n")
        fenzo.write(fmusic.read())

        if self.baryons:
            enzo_baryon_templates = self.templateEnv.get_template( "enzo_baryons.template")
            out = enzo_baryon_templates.render(config["enzo_configs"])
        else:
            enzo_dmonly = open("templates/enzo_dmonly.template")
            out = enzo_dmonly.read()

        fenzo.write("# [Enzo Simulation Configs]\n")
        fenzo.write(out)

        fenzo.close()
        fmusic.close()

        # specify the final redshift
        os.system("sed -i 's/CosmologyFinalRedshift                   = 0/CosmologyFinalRedshift = 18/g' {}/{}".format(self.test_dir, "music_input.enzo"))

    def run_enzo(self):
        self.write_enzo_config()

        os.system("cp {} {}".format(self.config["executables"]["enzo"],
                                    self.test_dir))
        os.chdir(self.test_dir)
        command = "mpirun -np {0} ./enzo -d {1} > enzo_run.out 2>&1".format(self.MPI_CORE, ENZO_CONFIG)
        os.system(command)
        os.chdir("../")

