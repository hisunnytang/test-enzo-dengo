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
from EnzoWorkFlow import EnzoWorkFlow


class FindHaloWorkFlow(EnzoWorkFlow):
    def __init__(self, config_file="dmonly.yaml", random_seed=12345):
        super().__init__(config_file)
        self.random_seed = random_seed
        np.random.seed(self.random_seed)
        self.MPI_CORE = 1

    def update_music_center(self, center):
        config = self.config["music_configs"]["setup"]
        config["ref_center"] = str(list(center))[1:-1]

    def update_music_random_seed(self):
        config = self.config["music_configs"]["setup"]
        print(config)
        lmin = config["levelmin"]
        lmax = config["levelmax"]
        rand = np.random.randint(1e4,1e5,lmax-lmin+1)
        seed_dict = {}
        for l, r in zip(range(lmin, lmax+1), rand):
            seed_dict["seed[{0:d}]".format(l)] = r
        self.config["music_configs"]["random"].update(seed_dict)
        print(self.config["music_configs"]["random"])

    def find_halos(self):

        final_output = os.popen("tail -1 {}/OutputLog".format(self.test_dir)).read()
        fname = final_output.split(" ")[2]

        ds = yt.load(os.path.join(self.test_dir, fname))

        hc = HaloCatalog(data_ds = ds, finder_method='hop')
        hc.create()
        hc.load("halo_catalogs/catalog/catalog.0.h5")

        f, ax = plt.subplots(1,3, figsize=(9,3),sharex=True, sharey=True)

        halo_positions = []
        halo_mass = []
        dw = ds.domain_width

        def get_relative_position( halo_dict, dw ):
            k = "particle_position_{}"
            relpos = []
            for orient in ["x", "y", "z"]:
                key = k.format(orient)
                relpos.append( halo_dict[key]/ dw[0] )
            return relpos

        for h in hc.catalog:
            halo_positions.append( get_relative_position(h,dw ))
            halo_mass.append(h["particle_mass"].in_units("Msun").v)

        halo_positions = np.array(halo_positions).transpose()
        if (len(halo_positions) < 1):
            return False

        ax[0].scatter( halo_positions[0], halo_positions[1], s = np.log10(halo_mass)*10)
        ax[1].scatter( halo_positions[0], halo_positions[2], s = np.log10(halo_mass)*10)
        ax[2].scatter( halo_positions[1], halo_positions[2], s = np.log10(halo_mass)*10)
        ax[0].set_xlim(0,1)
        ax[0].set_ylim(0,1)

        f.savefig("halo_position.png")

        np.save(self.test_dir+"_halo_positions.npy", halo_positions)
        np.save(self.test_dir+"_halo_mass.npy", halo_mass)

        self.halo_positions = halo_positions
        self.halo_mass = halo_mass
        return True


if __name__ == "__main__":

    np.random.seed(33127)

    seed = np.random.randint(1e5,1e6,size=10)
    for s in seed:
        fhw = FindHaloWorkFlow("dmonly.yaml", random_seed = s)
        fhw.test_dir += str(s)
        # the difference here is that the random seed in MUSIC is generated
        # by the numpy random seed
        fhw.update_music_random_seed()
        fhw.find_halos()
        break
        fhw.run_music()
        fhw.run_enzo()
        if fhw.find_halos():
            break

    print("SEED!!!!! {}".format(s))


    # now recenter the halos to see if the halos are now really centered!
    pos = fhw.halo_positions
    midx = np.argsort(fhw.halo_mass)[-1]
    print(midx)
    print("Centering On the Most Massive Halos")
    print(fhw.halo_mass[midx], " Msun")
    new_center = pos[:,midx]
    print(new_center)

    fhw.update_music_center(new_center)
    fhw.test_dir += "_recentered"
    fhw.run_music()
    fhw.run_enzo()
    fhw.find_halos()
