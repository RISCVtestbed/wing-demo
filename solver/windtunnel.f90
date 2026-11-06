program windtunnel
!simulates an object in a windtunnel

    use vars

    implicit none

    call get_params()

    call setup()

    call solver()

    call writetofile('output.dat')

end program
