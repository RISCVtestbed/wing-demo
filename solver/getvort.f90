subroutine getvort()
!Calculates the vorticity on the edge of the object.
!The vorticity is taken to be a constant on the surface:
! vortcoeff on the top edge, and -vortcoeff on the bottom edge
    use vars

    implicit none

    integer :: i, j
    
    call getv() !get the velocity


    do j=1,ny
        do i=1,nx
            if (boundary(i,j) .ne. 0) vort(i,j) = real(boundary(i,j))*vortcoeff
        enddo
    enddo


    vort(nx+1,:) = 0.

end subroutine
