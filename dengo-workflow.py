import numpy as np
import matplotlib.pyplot as plt
import yaml
from jinja2 import FileSystemLoader, Environment
import os
import utilities
import logging
import subprocess
import sys
import importlib
import glob

MPI_CORE = 32
MUSIC_CONFIG = "init.music"
ENZO_CONFIG  = "music_input.enzo"

class ConfigReader:
    def __init__(self, config_file):
        self.config = self.parse_config(config_file)

    def parse_config(self, config_file):
        logging.info("Parsing Config File = {}".format(config_file))
        stream = open(config_file, 'r')
        data = yaml.load(stream, Loader=yaml.FullLoader)
        return data

    def run_subprocess(self, commands, outfile=None):
        p = subprocess.run(commands, check=True, stdout=subprocess.PIPE,
                           universal_newlines=True)
        if outfile:
            with open(outfile, 'w') as f:
                f.write(p.stdout)

class MUSICGenerator(ConfigReader):
    def __init__(self, config_file):
        ConfigReader.__init__(self, config_file)
        self.test_dir = self.config["run_directory"]

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

    def run_music(self):
        config = self.config
        music  = config["executables"]["music"]
        music_configs = self.write_music_configs()
        self.run_subprocess(["./"+music, MUSIC_CONFIG],
                            "run_music.out")
        music_out = ["input_powerspec.txt", "{0}".format(MUSIC_CONFIG), "{0}_log.txt".format(MUSIC_CONFIG)]
        self.run_subprocess(["mv", *music_out, self.test_dir])


class DengoNetworkBuilder(ConfigReader):
    def __init__(self, config_file):
        ConfigReader.__init__(self, config_file)

        config             = self.parse_config(config_file)
        self.dengo_configs = config['dengo_configs']
        self.paths         = config['paths']
        self.set_environment_variables()

    def set_environment_variables(self):
        for envar, path in self.paths.items():
            os.environ[envar] = path

    def write_dengo_network(self):
        configs       = self.dengo_configs
        solver_name   = configs['solver_name']
        solver_option = configs['solver_option']
        output_dir    = configs['output_dir']

        network_file  = configs['network_file']
        module        = importlib.import_module(network_file)
        network = module.setup_network()
        self.network = network

        if solver_option == "be_chem":
            solver_template = "be_chem_solve/rates_and_rate_tables"
            ode_solver_source = "BE_chem_solve.C"
        elif solver_option == "cv_omp":
            solver_template = "cv_omp/sundials_CVDls"
            ode_solver_source = "initialize_cvode_solver.C"
        else:
            raise Exception(f"Solver {solver_option} not implemented")


        network.write_solver(solver_name,
                             solver_template= solver_template,
                             ode_solver_source=ode_solver_source, output_dir= output_dir)

    def build_dengo_solver(self):
        self.write_dengo_network()
        current_path = os.getcwd()
        configs     = self.dengo_configs
        dengo_dir   = configs['output_dir']
        omp_threads = configs['omp_num_threads']

        os.chdir(dengo_dir)
        with open("Makefile", "r+") as f:
            lines = f.readlines()
            for i, l in enumerate(lines):
                if "-fopenmp" in l:
                    lines[i] = f"OPTIONS += -fopenmp -DNTHREADS={omp_threads}\n"
            f.seek(0)
            f.writelines(lines)
        out = subprocess.run("make")
        os.chdir(current_path)

    def write_simulation_templates(self, simulation='gamer'):
        """Write necessary simulations files for Dengo."""
        supported_simulations = ['enzo', 'gamer']
        network               = self.network
        solver_name           = self.dengo_configs['solver_name']

        if simulation not in supported_simulations:
            raise Exception(f"{simulation} templates not supported")
        outfiledir = f"autogen_{simulation}_templates"
        if not os.path.exists(outfiledir):
            os.mkdir(outfiledir)
        templatedir = f"../../{simulation}-templates/templates"
        self.write_from_templates(searchpath=templatedir, outdir=outfiledir)

    def write_from_templates(self, searchpath=".", outdir="."):
        """write templates file with Jinja2 based on chemistry network

        Parameters
        ----------
        searchpath : str, optional
            path where jinja2 templates files are located
        outdir     : str, optional
            location of the desired templates ouput directory,
            will be created if not existed
        """
        network     = self.network
        solver_name = self.dengo_configs['solver_name']

        templateLoader = FileSystemLoader(searchpath=searchpath)
        env = Environment(extensions=['jinja2.ext.loopcontrols'], loader=templateLoader)

        template_vars = dict(network=network, solver_name=solver_name)
        templateFiles = self.walk_template_files(searchpath, outdir)
        for infile in templateFiles:
            template_inst = env.get_template(infile)
            solver_out = template_inst.render(**template_vars)

            outfile = infile.replace(".template", "")
            with open(os.path.join(outdir,outfile), 'w') as f:
               f.write(solver_out)

    def walk_template_files(self, searchpath, outputdir):
        """collect relative paths of templates, and create local directory if needed"""
        templateRelPath = []
        for dirpath, dirnames, filenames in os.walk(searchpath):
            for f in filenames:
                filepath = os.path.join(dirpath, f)
                relpath  = os.path.relpath(filepath, searchpath)
                basedir = os.path.dirname(relpath)
                outsubdir = os.path.join(outputdir, basedir)
                if not os.path.exists(outsubdir):
                    os.mkdir(outsubdir)
                templateRelPath += [relpath]

        return templateRelPath


class EnzoWorkFlow(MUSICGenerator):
    def __init__(self, config_file):
        MUSICGenerator.__init__(self, config_file)

        self.MPI_CORE = MPI_CORE
        templateLoader = FileSystemLoader(searchpath='./templates')
        self.templateEnv = Environment(loader=templateLoader)
        self.test_dir = self.config["run_directory"]
        #logging.basicConfig(filename="logWorkFlow.log", level=logging.DEBUG)
        logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', filename='logWorkFlow.log')

    def build_enzo(self, outtemplatedir = "autogen_enzo_templates",
                   enzorepo = "enzo-dev", chem_solver='dengo'):
        if chem_solver == "grackle":
            # current path
            current_path = os.getcwd()
            os.chdir(f"{enzorepo}/src/enzo")
            self.run_subprocess(['make', 'dengo-no'])
            self.run_subprocess(['make', 'grackle-yes'])
            self.run_subprocess(["make", "-j32"])
            os.chdir(current_path)
            self.run_subprocess(["cp", f"{enzorepo}/bin/enzo","."])
            return

        # chem solver anything elese are Dengo
        if not os.path.exists(enzorepo):
            raise Exception("{enzorepo} does not exist")
        # move templates to enzo repo
        for f in glob.glob(f"{outtemplatedir}/*"):
            self.run_subprocess(["cp", f, f"{enzorepo}/src/enzo/"])

        # current path
        current_path = os.getcwd()
        os.chdir(f"{enzorepo}/src/enzo")
        self.run_subprocess(['make', 'clean'])
        self.run_subprocess(['make', 'dengo-yes'])
        self.run_subprocess(['make', 'grackle-no'])
        self.run_subprocess(["make", "-j32"])
        os.chdir(current_path)
        self.run_subprocess(["cp", f"{enzorepo}/bin/enzo","."])


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
        os.system(f"sed -i 's/CosmologyFinalRedshift                   = 0/CosmologyFinalRedshift = {config['enzo_configs']['FinalRedshift']}/g' {self.test_dir}/{ENZO_CONFIG}")

    def run_enzo(self):
        os.system("cp {} {}".format(self.config["executables"]["enzo"],
                                    self.test_dir))
        os.chdir(self.test_dir)
        command = "mpirun -np {0} ./enzo -d {1} > enzo_run.out 2>&1".format(self.MPI_CORE, ENZO_CONFIG)
        os.system(command)
        os.chdir("../")

class EnzoChemistryInitialCondition:
    """initialize the same condition as Grackle would for Enzo"""
    def __init__(self):
        self.H2_1Fraction = 2.0e-20
        self.H2_2Fraction = 3.0e-14
        self.H_1Fraction  = 0.76
        self.H_2Fraction  = 1.2e-5
        self.H_m0Fraction = 2.0e-9
        self.He_1Fraction = 0.24
        self.He_2Fraction = 1.0e-14
        self.He_3Fraction = 1.0e-17
        self.de_1Fraction = 1.2e-5

        self.CosmologySimulationOmegaBaryonNow       = 0.045000
        self.CosmologySimulationOmegaCDMNow          = 0.231000
        self.CosmologySimulationInitialTemperature   = 35.408777

    def calculate_fraction(self):
        self.OmegaMatterNow = 0.276
        self.HubbleConstantNow = 0.703

        h_2 = self.H_2Fraction*0.76*self.OmegaMatterNow**0.5 / (self.CosmologySimulationOmegaBaryonNow*self.HubbleConstantNow)

        he2 = self.He_2Fraction*4.0*0.24
        he3 = self.He_3Fraction*4*0.24
        he1 = 0.24 - he2 - he3

        hm   = self.H_m0Fraction*h_2*(self.CosmologySimulationInitialTemperature**0.88)
        h2_2 = self.H2_2Fraction*2.*h_2* (self.CosmologySimulationInitialTemperature**1.8)
        h2   = self.H2_1Fraction*0.76*301.0**5.1 * self.OmegaMatterNow**1.5 / self.CosmologySimulationOmegaBaryonNow/self.HubbleConstantNow*2.0
        h1   = 0.76-h2-h2_2-hm

        de   = h_2 + 0.25*he2+0.5*he3 + 0.5*h2_2 -hm

        return {"H2_1": h2, "H2_2": h2_2, "H_m0": hm, "He_1": he1,
                "He_2": he2, "He_3": he3, "H_2": h_2, "H_1":h1,
                'de': de}
    def add_primordial_initial_fraction(self, filename):
        initial_condition = self.calculate_fraction()
        with open(filename,'a') as f:
            for k in sorted(initial_condition):
                f.write(f"CosmologySimulation{k}Fraction = {initial_condition[k]}\n")

class EnzoDengoWorkflow(EnzoWorkFlow, DengoNetworkBuilder, EnzoChemistryInitialCondition):

    def __init__(self, config_file="dmonly.yaml"):
        EnzoWorkFlow.__init__(self,config_file)
        DengoNetworkBuilder.__init__(self,config_file)
        EnzoChemistryInitialCondition.__init__(self)

    def write_enzo_templates(self, searchpath=".", outdir="."):
        network = self.network
        solver_name = self.dengo_configs['solver_name']

        templateLoader = FileSystemLoader(searchpath=searchpath)
        env = Environment(extensions=['jinja2.ext.loopcontrols'], loader=templateLoader)

        template_vars = dict(network=network, solver_name=solver_name)

        templateFiles = list(map(os.path.basename, glob.glob(os.path.join(searchpath, "*.template"))))
        for infile in templateFiles:
            template_inst = env.get_template(infile)
            solver_out = template_inst.render(**template_vars)

            outfile = infile.replace(".template", "")
            with open(os.path.join(outdir,outfile), 'w') as f:
               f.write(solver_out)


    def run(self):
        print(self.dengo_configs)
        self.build_dengo_solver()
        self.run_music()
        self.write_simulation_templates(simulation='enzo')

        self.build_enzo()
        self.write_enzo_config()
        self.add_primordial_initial_fraction(f"{self.test_dir}/{ENZO_CONFIG}")

        # copy the rate data to the local directory
        import shutil
        shutil.copy(f"{self.paths['DENGO_INSTALL_PATH']}/{self.dengo_configs['solver_name']}_tables.h5",
                    f"{self.test_dir}")

        self.run_enzo()
        #self.run_enzo()




if __name__ == "__main__":
    config_file = sys.argv[1]

    enzo_dengo = EnzoDengoWorkflow(config_file)
    enzo_dengo.run()

    #enzo_grackle = EnzoWorkFlow(config_file)
    #enzo_grackle.run_music()
    #enzo_grackle.build_enzo(chem_solver='grackle')
    #enzo_grackle.write_enzo_config()
    #enzo_grackle.run_enzo()

    #workflow = dengo_workflow(config_file = config_file)
    #workflow.run_music()
    #workflow.build_dengo_network()
    #workflow.run_enzo()

    #network = DengoWorkflow(config_file)
    #network.run()

    #music = MUSICGenerator(config_file)
    #music.run_music()


