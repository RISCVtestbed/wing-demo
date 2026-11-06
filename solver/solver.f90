subroutine solver()
!determines the flow profile around the object. In order to do this we have to solve 2
!coupled equations:
! - calculate the streamfunction (psi) by solving Poisson's equation
! - update the vorticity by solving the vorticity transport equation (from the NS equations)
!
!First of all a potential flow is calculated around the object (solving Laplace's equation)
!then (optionally) the vorticity is turned on and alternately Poisson's equation and the
!vorticity transport equation are iterated to determine the fluid flow.

    use vars
    use omp_lib

    implicit none

    real :: time
    double precision :: tstart, tstop

    !$OMP PARALLEL
    !solve Laplace's equation for the irrotational flow profile (vorticity=0)
    call poisson(iterations)
    !$OMP END PARALLEL

    !get the vorticity on the surface of the object

    call getvort()

    !write out the potential flow to file.

    call writetofile("potential.dat")




    !if the user has chosen to allow vorticity:
    if (vorticity) then


        ! set CFL conditions (dt << cell crossing time or cell diffusion time for stability)
        cfl_r0 = 0.25*dx*dy*R0
        cfl_v = 0.25*dx/1. !assume velocty is 1



        !dt is set according to the most restrictive CFL condition
        dt = minval((/ cfl_r0, cfl_v /))



        print*,''
        print*,"CFL (Reynolds, velocity)", cfl_r0, cfl_v
        print *, "Timestep=",dt
        print *, ""

        time=0.
        tstart=omp_get_wtime()

        !$OMP PARALLEL

        do while (time .lt. real(nx)*crossing_times)


            call getv() !get the velocity

            call navier_stokes() !solve dw/dt=f(w,psi) for a timestep

            call poisson(2) !2 poisson 'relaxation' steps

            !$OMP SINGLE
            time=time+dt
            !$OMP END SINGLE
            !$OMP BARRIER

        enddo

        !$OMP END PARALLEL

        tstop=omp_get_wtime()
        print*,''
        print*, "Time to complete =",tstop-tstart
        print*,''

        call getvort()

    endif


end subroutine
