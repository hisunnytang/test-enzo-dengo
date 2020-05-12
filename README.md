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

RecenterHalo:
- similar to enzoworkflow
- just that it locates the most massive ones
- and recenter the simulation

```mermaid
graph LR
    subgraph CN[Physics]
    cn1((Reactions))
    cn2((Cooling Rate))
    end

    style CN fill:#0496FF,stroke:#0496FF

    subgraph enzo[Hydro Simulations]
    id1[(Species + Internal Energy)]
    end

    style enzo fill:#7FB069, stroke:#7FB069

    subgraph d[Dengo]
    d1["symbolic differentiation"]
    d2["Solver template"]
    d3["right hand sided function f"]
    d4["Jacobian function J"]
    d1-->d2
    d1-->d3
    d1-->d4
    d3-->d2
    d4-->d2
    end
    cn1-->d1
    cn2-->d1

    style d fill:#FFBC42,stroke:#FFBC42

    subgraph k[ODEsolver]
    ode1[CVODE]
    ode2["Stand Alone BDF solver"]
    end

    style k fill:#D81159, stroke:D81159
    
    dcs["Dengo Generated Chemistry Solver"]
    d2-.->dcs
    ode1-.->dcs
    
    id1-->|Solve Chemistry| dcs
    dcs-->|Update state variables| id1
 ```
    
