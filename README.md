# test-enzo-dengo
workflow for testing different parameters enzo, dengo, music

- Run Experiments by tweaking tunables in config.yaml or specify your own!
- perform analysis across simulations with different parameters

EnzoWorkFlow object:
- reads parameter from YAML file to create Initial conditions from MUSIC
- and then run dengo, with parameters specified in YAML
- Again this assumes that you already have a Enzo/ Music executables
-

DengoWorkFlow:
- pretty much the same except it builds dengo too
-

RecenterHalo:
- similar to enzoworkflow
- just that it locates the most massive ones
