# Docker file for JuliaApiBox
# Version:16

FROM tanmaykm/juliabox:16

MAINTAINER Tanmay Mohapatra

RUN julia -e 'Pkg.init(); Pkg.add("PyPlot"); Pkg.add("SIUnits"); Pkg.add("Gadfly"); Pkg.add("DataStructures"); Pkg.add("HDF5"); Pkg.add("Iterators"); Pkg.add("MCMC"); Pkg.add("NumericExtensions"); Pkg.add("SymPy"); Pkg.add("Interact"); Pkg.add("Roots");'

RUN julia -e 'Pkg.add("DataFrames"); Pkg.add("RDatasets"); Pkg.add("Distributions"); Pkg.add("SVM"); Pkg.add("Clustering"); Pkg.add("GLM"); Pkg.add("MCMC");'

RUN julia -e 'Pkg.add("Optim"); Pkg.add("JuMP"); Pkg.add("GLPKMathProgInterface"); Pkg.add("Clp"); Pkg.add("NLopt"); Pkg.add("Ipopt");'

RUN julia -e 'Pkg.add("Cairo");'

RUN julia -e 'Pkg.add("Images"); Pkg.add("ImageView"); Pkg.add("WAV"); Pkg.add("ODE"); Pkg.add("Sundials"); Pkg.add("LinearLeastSquares");'

RUN julia -e 'Pkg.add("BayesNets"); Pkg.add("PGFPlots"); Pkg.add("GraphLayout");'

RUN julia -e 'Pkg.clone("https://github.com/tanmaykm/JuliaBox.jl.git");'

RUN mkdir /home/juser/.juliabox
ENTRYPOINT julia -e 'using JuliaBox; process()'

#COPY supervisord.conf /home/juser/.juliabox/supervisord.conf
#ENTRYPOINT /usr/bin/supervisord -n -c /home/juser/.juliabox/supervisord.conf -l /home/juser/.juliabox/supervisord.log -j /home/juser/.juliabox/supervisord.pid -q /home/juser/.juliabox
