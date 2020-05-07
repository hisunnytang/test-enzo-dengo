import os
import numpy as np
from dengo.chemical_network import \
    ChemicalNetwork, \
    reaction_registry, \
    cooling_registry, species_registry
import dengo.primordial_rates
import dengo.primordial_cooling
from dengo.chemistry_constants import tiny, kboltz, mh, G
import yt
import yt.units as u
import numpy
import pickle
import time
import pyximport
import sys
import matplotlib.pyplot as plt
import pytest
import h5py


def setup_primordial_network(enforce_conservation= True, equilibrium_species= ["H2_2"]):
    """Initial a ChemicalNetwork object
       for primordial network 9-species model
    Return:
        primordial: ChemicalNetwork with primordial reactions and cooling
    """
    # this register all the rates specified in `primordial_rates.py`
    dengo.primordial_rates.setup_primordial()

    # initialize the chmical network object
    primordial = ChemicalNetwork()

    # add all the reactions
    primordial.add_reaction("k01")
    primordial.add_reaction("k02")
    primordial.add_reaction("k03")
    primordial.add_reaction("k04")
    primordial.add_reaction("k05")
    primordial.add_reaction("k06")
    primordial.add_reaction("k07")
    primordial.add_reaction("k08")
    primordial.add_reaction("k09")
    primordial.add_reaction("k10")
    primordial.add_reaction("k11")
    primordial.add_reaction("k12")
    primordial.add_reaction("k13")
    primordial.add_reaction("k14")
    primordial.add_reaction("k15")
    primordial.add_reaction("k16")
    primordial.add_reaction("k17")
    primordial.add_reaction("k18")
    primordial.add_reaction("k19")
    primordial.add_reaction("k21")
    primordial.add_reaction("k22")
    primordial.add_reaction("k23")

    primordial.add_cooling("brem")
    primordial.add_cooling("reHII")
    primordial.add_cooling("reHeIII")
    primordial.add_cooling("gloverabel08")
    primordial.add_cooling("ceHI")
    primordial.add_cooling("h2formation")
    primordial.add_cooling("h2formation_extra")
    primordial.add_cooling("reHeII2")
    primordial.add_cooling("reHeII1")
    primordial.add_cooling("ciHeIS")
    primordial.add_cooling("ceHeII")
    primordial.add_cooling("ciHI")
    primordial.add_cooling("ceHeI")
    primordial.add_cooling("gammah")
    primordial.add_cooling("ciHeI")
    primordial.add_cooling("ciHeII")
    primordial.add_cooling("cie_cooling")
    primordial.add_cooling("compton")

    # This defines the temperature range for the rate tables
    primordial.init_temperature((1e0, 1e8))

    primordial.enforce_conservation = enforce_conservation
    for s in equilibrium_species:
        primordial.set_equilibrium_species(s)

    primordial._libtool = "/usr/bin/libtool"
    return primordial



def write_network(network, solver_options={"output_dir": "test_dir",
                                           "solver_name": "primordial",
                                           "use_omp": False,
                                           "use_cvode": False,
                                           "use_suitesparse": False}):
    """Write solver based on the ChemicalNetwork
    """
    # Write the initial conditions file
    # IF you need to use the Makefile, and c-library
    # you will have to specified the library_path

    output_dir = solver_options["output_dir"]
    solver_name = solver_options["solver_name"]
    use_omp = solver_options["use_omp"]
    use_cvode = solver_options["use_cvode"]
    use_suitesparse = solver_options["use_suitesparse"]

    if use_cvode:
        print(output_dir)
        network.write_solver(solver_name, output_dir=output_dir,
                             solver_template="cv_omp/sundials_CVDls",
                             ode_solver_source="initialize_cvode_solver.C")
        return

    if not(use_omp and use_cvode and use_suitesparse):
        network.write_solver(
            solver_name, output_dir=output_dir,
            solver_template="be_chem_solve/rates_and_rate_tables",
            ode_solver_source="BE_chem_solve.C")
        return

