FC = gfortran
FFLAGS = -O3 -Wall -fopenmp

objects = vars.o windtunnel.o solver.o setup.o navier_stokes.o poisson.o getv.o writetofile.o getvort.o get_params.o

windtunnel : $(objects)
	$(FC) $(FFLAGS) $(objects) -o windtunnel

%.o : %.f90 vars.o
	$(FC) -c $(FFLAGS) $<

vars.o : vars.f90
	$(FC) -c $(FFLAGS) vars.f90

clean :
	rm -f *.o *.mod windtunnel
