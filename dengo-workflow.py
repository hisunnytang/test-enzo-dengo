import numpy as np
import matplotlib.pyplot as plt
import yaml
import jinja2
import os
import utilities
import logging
import subprocess

MUSIC_CONFIG = "init.music"
ENZO_CONFIG  = "music_input.enzo"

class dengo_workflow:
    def __init__(self, config_file="config.yaml"):
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
        #self.run_subprocess(["mv", "wnoise*", self.test_dir])


    def write_enzo_config(self):
        config = self.config
        fenzo  = open(os.path.join(self.test_dir,ENZO_CONFIG), 'w')
        fmusic = open(os.path.join(self.test_dir, "parameter_file.txt"), "r")

        enzo_baryon_templates = self.templateEnv.get_template( "enzo_baryons.template")
        out = enzo_baryon_templates.render(config["enzo_configs"])
        fenzo.write("# [Configurations from MUSIC]")
        fenzo.write(fmusic.read())

        fenzo.write("# [Enzo Simulation Configs]")
        fenzo.write(out)

        fenzo.close()
        fmusic.close()

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

    def run_enzo(self):
        self.write_enzo_config()

        os.chdir(self.test_dir)
        os.system("./enzo -d {} &> run_enzo.out".format(ENZO_CONFIG))

if __name__ == "__main__":
    workflow = dengo_workflow(config_file = "config.yaml")
    workflow.run_music()
    workflow.build_dengo_network()
    workflow.run_enzo()
