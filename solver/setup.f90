subroutine setup()
!Sets up the arrays and defines the shape of the object.

    use vars
    
    implicit none
    
    integer :: i,j
    
    real :: ysum, yhat
    integer :: nums
    
        
    !allocate arrays
    call setup_arrays()
    
    
    
    ! generate x and y coordinates
    
    do i=1,nx
        x(i) = xrange(1) + (i-1)*dxx
    enddo
    
    do j=1,ny
        y(j) = yrange(1) + (j-1)*dyy
    enddo
    
    
    
    ! define shape of object. Save it to mask (1=object, 0 = not object)
    
    mask(:,:)=0
    
    do j=1,ny
        do i=1,nx
            if (shape .eq. 1) then
                mask(i,j)=ellipse(x(i),y(j))
            else
                mask(i,j)=aerofoil(x(i),y(j))
            endif
        enddo
    enddo
    
    
    !set up boundary array. Points on the edge of the object are set to ±1
    !(depending on whether they are on the top (+1) or bottom (-1) of the object)
    
    boundary(:,:)=0
    
    do i=1,nx
        !bottom boundary
        do j=1,ny
        if (mask(i,j) .eq. 1) then
            boundary(i,j) = boundary(i,j) - 1
            exit
            endif
        enddo
        !top boundary (don't do if the top boundary isn't found)
        if (j .ne. ny) then
            do j=ny,1,-1
                if (mask(i,j) .eq. 1) then
                    boundary(i,j) = boundary(i,j) + 1
                    exit
                endif
            enddo
        endif
    enddo
    
    
    !calculate the value of psi in the object
    
    yhat=0. !yhat is the value of psi in the object
    
    if (nose .eq. 1) then !We want the flow to diverge at the first part of the object it reaches
    
        ysum=0.
        nums=0
        

        do i=1,nx !skim along in the x direction looking for the first occurrance of the object
            do j=1,ny
                if (mask(i,j) .eq. 1) then !found it! sum up all instances of it crossing this x=const line
                    nums=nums+1
                    ysum=ysum+real(j)
                endif
            enddo
        
            if (nums .gt. 0) then !if we found the nose
                yhat=ysum/real(nums) !find the mean location of the nose in the y coordinate
                exit !we are done here. Leave the loop
            endif
        enddo
    
    else if (nose .eq. 0) then
    
        yhat=real((ny-1))/2+1 !set yhat to the centre value of psi
    
    else 
    
        print *, "Error - invalid option (nose)"
        stop
        
    endif
                
    
    
    
    ! now set the initial condition for psi, psi(x,y) = vx * y (unless in the object where its constant)
    
    do j=1,ny
        do i=1,nx
            if (mask(i,j) .eq. 1) then
                psi(i,j)=yhat
            else
                psi(i,j)=real(j)
            endif
        enddo
    enddo
    

    
    ! initialise vorticity to zero
    vort = 0

    !boundary conditions for psi:
    !top/bottom
    psi(:,ny+1) = psi(:,ny)+1
    psi(:,0) = psi(:,1)-1
    
    !left/right
    psi(0,:) = psi(1,:)
    psi(nx+1,:) = 2.*psi(nx,:) - psi(nx-1,:)
    
    


end subroutine
